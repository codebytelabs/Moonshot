import os
import asyncio
import json
import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_PRIMARY_MODEL = os.environ.get("OPENROUTER_PRIMARY_MODEL", "qwen/qwen3.5-397b-a17b")
OPENROUTER_FALLBACK_MODEL = os.environ.get("OPENROUTER_FALLBACK_MODEL", "moonshotai/kimi-k2.5")
EVM_WALLET = os.environ.get("EVM_WALLET_ADDRESS", "")
SOL_WALLET = os.environ.get("SOL_WALLET_ADDRESS", "")

# ─── GLOBALS ─────────────────────────────────────────────────────────
db = None
scanner_task = None
swarm_running = False
ws_clients: list[WebSocket] = []

# ─── WEBSOCKET BROADCAST ────────────────────────────────────────────
async def broadcast(event_type: str, data: dict):
    msg = json.dumps({"type": event_type, "data": data, "ts": datetime.now(timezone.utc).isoformat()})
    disconnected = []
    for ws in ws_clients:
        try:
            await asyncio.wait_for(ws.send_text(msg), timeout=2.0)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        try:
            ws_clients.remove(ws)
        except ValueError:
            pass

# ─── OPENROUTER CLIENT ──────────────────────────────────────────────
async def llm_complete(prompt: str, system: str = "You are a crypto trading AI agent.", model: str = None, temperature: float = 0.3, max_tokens: int = 1200) -> str:
    chosen = model or OPENROUTER_PRIMARY_MODEL
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": chosen,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        if chosen != OPENROUTER_FALLBACK_MODEL:
            try:
                payload["model"] = OPENROUTER_FALLBACK_MODEL
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
            except Exception as e2:
                return f"[LLM_ERROR] Both models failed: {e}, {e2}"
        return f"[LLM_ERROR] {e}"

# ─── DEXSCREENER CLIENT ─────────────────────────────────────────────
DEXSCREENER_BASE = "https://api.dexscreener.com"

async def dex_get(path: str) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{DEXSCREENER_BASE}{path}")
            r.raise_for_status()
            return r.json()
    except Exception:
        return None

async def dex_latest_profiles():
    return await dex_get("/token-profiles/latest/v1") or []

async def dex_boosted_tokens():
    return await dex_get("/token-boosts/latest/v1") or []

async def dex_top_boosted():
    return await dex_get("/token-boosts/top/v1") or []

async def dex_search_pairs(query: str):
    data = await dex_get(f"/latest/dex/search?q={query}")
    return data.get("pairs", []) if data else []

async def dex_get_pairs(chain_id: str, pair_address: str):
    data = await dex_get(f"/latest/dex/pairs/{chain_id}/{pair_address}")
    return data.get("pairs", []) if data else []

async def dex_token_pairs(chain_id: str, token_address: str):
    return await dex_get(f"/token-pairs/v1/{chain_id}/{token_address}") or []

async def dex_tokens(chain_id: str, addresses: str):
    return await dex_get(f"/tokens/v1/{chain_id}/{addresses}") or []

# ─── AGENT: @alpha_scanner ──────────────────────────────────────────
async def alpha_scanner_cycle():
    await log_agent("alpha_scanner", "SCANNING", "Initiating deep scan across all chains...")

    profiles = await dex_latest_profiles()
    boosted = await dex_boosted_tokens()
    top_boost = await dex_top_boosted()

    discoveries = []

    # Process latest token profiles
    if isinstance(profiles, list):
        for p in profiles[:30]:
            chain = p.get("chainId", "unknown")
            addr = p.get("tokenAddress", "")
            if not addr:
                continue
            discoveries.append({
                "source": "profile",
                "chainId": chain,
                "tokenAddress": addr,
                "description": p.get("description", ""),
                "icon": p.get("icon", ""),
            })

    # Process boosted tokens (trending/promoted)
    boosted_list = boosted if isinstance(boosted, list) else [boosted] if isinstance(boosted, dict) else []
    for b in boosted_list[:20]:
        chain = b.get("chainId", "unknown")
        addr = b.get("tokenAddress", "")
        if not addr:
            continue
        discoveries.append({
            "source": "boosted",
            "chainId": chain,
            "tokenAddress": addr,
            "totalAmount": b.get("totalAmount", 0),
            "icon": b.get("icon", ""),
        })

    await log_agent("alpha_scanner", "DETECTED", f"Found {len(discoveries)} potential targets from profiles+boosts")

    # Deep-scan top candidates for pair data
    scored = []
    scanned_addrs = set()
    for d in discoveries[:15]:
        chain = d["chainId"]
        addr = d["tokenAddress"]
        key = f"{chain}:{addr}"
        if key in scanned_addrs:
            continue
        scanned_addrs.add(key)

        pairs = await dex_token_pairs(chain, addr)
        if not pairs:
            continue

        for pair in pairs[:2]:
            price_usd = pair.get("priceUsd")
            volume = pair.get("volume") or {}
            txns = pair.get("txns") or {}
            liquidity = pair.get("liquidity") or {}
            price_change = pair.get("priceChange") or {}
            fdv = pair.get("fdv")
            mc = pair.get("marketCap")
            created = pair.get("pairCreatedAt")

            vol_5m = volume.get("m5", 0) or 0
            vol_1h = volume.get("h1", 0) or 0
            vol_24h = volume.get("h24", 0) or 0
            m5_txns = txns.get("m5") or {}
            buys_5m = m5_txns.get("buys", 0) or 0
            sells_5m = m5_txns.get("sells", 0) or 0
            liq_usd = liquidity.get("usd", 0) or 0
            change_5m = price_change.get("m5", 0) or 0
            change_1h = price_change.get("h1", 0) or 0

            # Scoring: aggressive momentum
            score = 0
            if vol_5m > 1000:
                score += 20
            if vol_1h > 10000:
                score += 15
            if buys_5m > sells_5m * 1.5 and buys_5m > 3:
                score += 25
            if change_5m > 5:
                score += 20
            if change_1h > 10:
                score += 10
            if liq_usd > 5000:
                score += 10
            if fdv and fdv < 1_000_000:
                score += 15  # micro-cap bonus
            if created and (datetime.now(timezone.utc).timestamp() * 1000 - created) < 86400000:
                score += 15  # new pair bonus (<24h)

            if score >= 30:
                entry = {
                    "id": str(uuid.uuid4()),
                    "chainId": chain,
                    "tokenAddress": addr,
                    "pairAddress": pair.get("pairAddress", ""),
                    "dexId": pair.get("dexId", ""),
                    "baseToken": pair.get("baseToken", {}),
                    "quoteToken": pair.get("quoteToken", {}),
                    "priceUsd": price_usd,
                    "volume": {"m5": vol_5m, "h1": vol_1h, "h24": vol_24h},
                    "txns": {"buys_5m": buys_5m, "sells_5m": sells_5m},
                    "liquidity_usd": liq_usd,
                    "fdv": fdv,
                    "marketCap": mc,
                    "priceChange": {"m5": change_5m, "h1": change_1h},
                    "score": score,
                    "source": d.get("source", "scan"),
                    "pairCreatedAt": created,
                    "scannedAt": datetime.now(timezone.utc).isoformat(),
                    "url": pair.get("url", ""),
                }
                scored.append(entry)

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:10]

    if top:
        await log_agent("alpha_scanner", "LOCKED", f"Top target: {top[0].get('baseToken', {}).get('symbol', '?')} on {top[0]['chainId']} | Score: {top[0]['score']} | Vol5m: ${top[0]['volume']['m5']:,.0f}")

    # Store in DB
    if db is not None and top:
        for t in top:
            t["_type"] = "alpha_hit"
            await db.alpha_hits.insert_one(t)

    # Broadcast radar hits
    for t in top:
        safe_hit = {k: v for k, v in t.items() if k != "_id"}
        await broadcast("radar_hit", safe_hit)

    return top

# ─── AGENT: @contract_sniper ────────────────────────────────────────
async def contract_sniper_analyze(token: dict) -> dict:
    symbol = token.get("baseToken", {}).get("symbol", "UNKNOWN")
    chain = token.get("chainId", "unknown")
    addr = token.get("tokenAddress", "")
    liq = token.get("liquidity_usd", 0)
    fdv = token.get("fdv", 0)
    vol_5m = token.get("volume", {}).get("m5", 0)
    buys = token.get("txns", {}).get("buys_5m", 0)
    sells = token.get("txns", {}).get("sells_5m", 0)
    change_5m = token.get("priceChange", {}).get("m5", 0)

    await log_agent("contract_sniper", "DECOMPILING", f"Auditing {symbol} on {chain} | Addr: {addr[:16]}...")

    # Heuristic-based analysis (works without LLM)
    risk_score = 5
    verdict = "CAUTION"
    reasons = []

    # Liquidity check
    if liq < 1000:
        risk_score += 3
        reasons.append("Very low liquidity")
    elif liq < 5000:
        risk_score += 1
        reasons.append("Low liquidity")
    else:
        risk_score -= 1

    # Buy/sell ratio check
    if sells > 0 and buys / max(sells, 1) < 0.3:
        risk_score += 2
        reasons.append("Sell pressure dominant")
    elif buys > sells * 2:
        risk_score -= 1

    # FDV check
    if fdv and fdv < 10000:
        risk_score += 2
        reasons.append("Extremely low FDV")
    elif fdv and fdv > 100_000_000:
        risk_score -= 1

    # Volume spike without liquidity
    if vol_5m > liq * 0.5 and liq < 10000:
        risk_score += 2
        reasons.append("Volume/liquidity mismatch")

    risk_score = max(1, min(10, risk_score))
    if risk_score <= 3:
        verdict = "SAFE"
    elif risk_score >= 7:
        verdict = "DANGER"

    # Try LLM enhancement if available
    analysis = {
        "honeypot_risk": "high" if risk_score >= 7 else "medium" if risk_score >= 4 else "low",
        "risk_score": risk_score,
        "liquidity_safe": liq >= 5000,
        "verdict": verdict,
        "reason": "; ".join(reasons) if reasons else "Heuristic analysis"
    }

    if OPENROUTER_API_KEY:
        prompt = f"""Analyze this DEX token for safety. Be extremely brief. Output ONLY a JSON object.
Token: {symbol}, Chain: {chain}, Liquidity: ${liq:,.0f}, FDV: ${fdv:,.0f}, 5min Vol: ${vol_5m:,.0f}, Buys/Sells: {buys}/{sells}, 5min Change: {change_5m}%
Return JSON: {{"honeypot_risk": "low/medium/high", "risk_score": 1-10, "liquidity_safe": true/false, "verdict": "SAFE/CAUTION/DANGER", "reason": "brief"}}"""

        result = await llm_complete(prompt, system="You are a DeFi security auditor. Respond only with valid JSON. No markdown.")
        if not result.startswith("[LLM_ERROR]"):
            try:
                clean = result.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                start = clean.find("{")
                end = clean.rfind("}") + 1
                if start >= 0 and end > start:
                    analysis = json.loads(clean[start:end])
            except Exception:
                pass  # Keep heuristic analysis

    verdict = analysis.get("verdict", "CAUTION")
    risk = analysis.get("risk_score", 5)

    if verdict == "SAFE":
        await log_agent("contract_sniper", "CLEAR", f"{symbol} SAFE | Risk: {risk}/10 | {analysis.get('reason', '')}")
    elif verdict == "DANGER":
        await log_agent("contract_sniper", "BLOCKED", f"{symbol} DANGER | Risk: {risk}/10 | {analysis.get('reason', '')}")
    else:
        await log_agent("contract_sniper", "CAUTION", f"{symbol} CAUTION | Risk: {risk}/10 | {analysis.get('reason', '')}")

    return {**token, "security": analysis}

# ─── AGENT: @execution_core ─────────────────────────────────────────
async def execution_core_trade(token: dict) -> dict:
    symbol = token.get("baseToken", {}).get("symbol", "UNKNOWN")
    chain = token.get("chainId", "unknown")
    verdict = token.get("security", {}).get("verdict", "CAUTION")

    if verdict == "DANGER":
        await log_agent("execution_core", "ABORTED", f"Skipping {symbol} - flagged DANGER by sniper")
        return {**token, "trade_status": "skipped", "reason": "danger"}

    await log_agent("execution_core", "ROUTING", f"Finding optimal route for {symbol} on {chain}...")
    await asyncio.sleep(0.5)  # Simulate route calculation

    # Simulated trade execution for MVP
    trade = {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "chainId": chain,
        "tokenAddress": token.get("tokenAddress", ""),
        "pairAddress": token.get("pairAddress", ""),
        "side": "BUY",
        "price": token.get("priceUsd", "0"),
        "amount_usd": 50.0,  # simulated position size
        "status": "SIMULATED",
        "route": f"USDC({chain}) -> {symbol}({chain})",
        "gas_strategy": "EIP-7702 Sponsored",
        "mev_protection": "Flashbots Protect",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": token.get("score", 0),
        "security": token.get("security", {}),
    }

    if db is not None:
        await db.trades.insert_one({**trade})

    await log_agent("execution_core", "EXECUTED", f"BUY {symbol} @ ${token.get('priceUsd', '?')} | Route: {trade['route']} | Status: SIMULATED")

    safe_trade = {k: v for k, v in trade.items() if k != "_id"}
    await broadcast("trade_executed", safe_trade)
    return trade

# ─── AGENT: @quant_mutator ──────────────────────────────────────────
async def quant_mutator_evaluate():
    await log_agent("quant_mutator", "ANALYZING", "Evaluating strategy performance...")

    if db is None:
        return

    trades = await db.trades.find({}, {"_id": 0}).sort("timestamp", -1).limit(50).to_list(50)
    total = len(trades)
    if total == 0:
        await log_agent("quant_mutator", "IDLE", "No trades to evaluate yet")
        return

    safe_count = sum(1 for t in trades if t.get("security", {}).get("verdict") == "SAFE")
    avg_score = sum(t.get("score", 0) for t in trades) / total if total else 0
    hit_rate = safe_count / total if total else 0

    # Heuristic-based strategy mutation
    suggestions = []
    if hit_rate < 0.3:
        suggestions.append("Increase minimum score threshold to filter noise")
    if avg_score < 40:
        suggestions.append("Focus on tokens with higher volume spikes")
    if hit_rate > 0.7:
        suggestions.append("Strategy performing well - consider increasing position size")
    if not suggestions:
        suggestions.append("Maintain current parameters")

    analysis = {"hit_rate": hit_rate, "suggestions": suggestions, "confidence": min(0.9, total / 50)}

    await log_agent("quant_mutator", "MUTATED", f"Hit rate: {hit_rate:.1%} | Avg score: {avg_score:.0f} | {suggestions[0]}")

    if db is not None:
        await db.strategy_mutations.insert_one({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_trades": total,
            "analysis": analysis,
        })

    await broadcast("strategy_update", analysis)

# ─── AGENT LOG HELPER ───────────────────────────────────────────────
async def log_agent(agent: str, status: str, message: str):
    entry = {
        "agent": agent,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if db is not None:
            await asyncio.wait_for(db.agent_logs.insert_one({**entry}), timeout=5.0)
    except Exception as e:
        print(f"[LOG_AGENT] DB insert failed: {e}", flush=True)
    try:
        await broadcast("agent_log", entry)
    except Exception as e:
        print(f"[LOG_AGENT] Broadcast failed: {e}", flush=True)

# ─── MAIN SCAN LOOP ─────────────────────────────────────────────────
async def swarm_loop():
    global swarm_running
    cycle = 0
    while swarm_running:
        cycle += 1
        await log_agent("system", "CYCLE", f"=== SWARM CYCLE #{cycle} INITIATED ===")

        try:
            # Phase 1: Scan
            hits = await alpha_scanner_cycle()

            # Phase 2: Audit top hits
            audited = []
            for hit in hits[:5]:
                result = await contract_sniper_analyze(hit)
                audited.append(result)
                await asyncio.sleep(0.3)

            # Phase 3: Execute safe trades
            for token in audited:
                if token.get("security", {}).get("verdict") in ("SAFE", "CAUTION"):
                    await execution_core_trade(token)
                    await asyncio.sleep(0.2)

            # Phase 4: Mutator evaluates every 5 cycles
            if cycle % 5 == 0:
                await quant_mutator_evaluate()

            await log_agent("system", "COMPLETE", f"Cycle #{cycle} complete. Next scan in 60s.")

        except Exception as e:
            await log_agent("system", "ERROR", f"Cycle error: {str(e)}")

        # Wait 60 seconds before next cycle
        for _ in range(60):
            if not swarm_running:
                break
            await asyncio.sleep(1)

    await log_agent("system", "HALTED", "Swarm loop stopped.")

# ─── SEED DATA ───────────────────────────────────────────────────────
async def seed_data():
    # Seed some initial portfolio data
    existing = await db.portfolio.count_documents({})
    if existing == 0:
        base_time = datetime.now(timezone.utc)
        values = [10000, 10050, 10120, 10080, 10200, 10350, 10300, 10450, 10600, 10550,
                  10700, 10850, 10900, 11000, 10950, 11100, 11250, 11200, 11350, 11500]
        for i, v in enumerate(values):
            ts = datetime(2026, 1, 10 + i // 4, 6 + (i % 4) * 6, 0, 0, tzinfo=timezone.utc)
            await db.portfolio.insert_one({"value": v, "timestamp": ts.isoformat()})

    # Seed initial positions
    existing_pos = await db.positions.count_documents({})
    if existing_pos == 0:
        positions = [
            {"id": str(uuid.uuid4()), "symbol": "PEPE", "chainId": "ethereum", "side": "BUY", "entry_price": "0.00001234", "current_price": "0.00001456", "amount_usd": 150.0, "pnl_pct": 18.0, "status": "open", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"id": str(uuid.uuid4()), "symbol": "WIF", "chainId": "solana", "side": "BUY", "entry_price": "2.15", "current_price": "2.48", "amount_usd": 200.0, "pnl_pct": 15.3, "status": "open", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"id": str(uuid.uuid4()), "symbol": "BRETT", "chainId": "base", "side": "BUY", "entry_price": "0.042", "current_price": "0.039", "amount_usd": 100.0, "pnl_pct": -7.1, "status": "open", "timestamp": datetime.now(timezone.utc).isoformat()},
        ]
        for p in positions:
            await db.positions.insert_one(p)

    # Seed initial agent logs
    existing_logs = await db.agent_logs.count_documents({})
    if existing_logs == 0:
        logs = [
            {"agent": "system", "status": "BOOT", "message": "APEX-SWARM v1.0 initialized. All agents standing by.", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"agent": "alpha_scanner", "status": "READY", "message": "DexScreener feed connected. Monitoring 60+ chains.", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"agent": "contract_sniper", "status": "READY", "message": "Contract audit engine online. AI model loaded.", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"agent": "execution_core", "status": "READY", "message": "Routing engine standby. LI.FI + Pimlico ready.", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"agent": "quant_mutator", "status": "READY", "message": "Strategy evaluator initialized. Waiting for trade data.", "timestamp": datetime.now(timezone.utc).isoformat()},
        ]
        for log in logs:
            await db.agent_logs.insert_one(log)


# ─── LIFESPAN ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    mongo_client = AsyncIOMotorClient(MONGO_URL)
    db = mongo_client[DB_NAME]
    await seed_data()
    yield
    mongo_client.close()

# ─── APP ─────────────────────────────────────────────────────────────
app = FastAPI(title="APEX-SWARM", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ─── WEBSOCKET ───────────────────────────────────────────────────────
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)

# ─── REST ENDPOINTS ──────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "alive", "swarm_active": swarm_running, "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/api/swarm/start")
async def start_swarm():
    global swarm_running, scanner_task
    if swarm_running:
        return {"status": "already_running"}
    swarm_running = True
    scanner_task = asyncio.create_task(swarm_loop())
    return {"status": "started"}

@app.post("/api/swarm/stop")
async def stop_swarm():
    global swarm_running, scanner_task
    swarm_running = False
    if scanner_task:
        scanner_task.cancel()
        scanner_task = None
    return {"status": "stopped"}

@app.get("/api/swarm/status")
async def swarm_status():
    return {"active": swarm_running, "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/agent-logs")
async def get_agent_logs(limit: int = Query(100, le=500)):
    logs = await db.agent_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return logs

@app.get("/api/alpha-hits")
async def get_alpha_hits(limit: int = Query(50, le=200)):
    hits = await db.alpha_hits.find({}, {"_id": 0}).sort("scannedAt", -1).limit(limit).to_list(limit)
    return hits

@app.get("/api/trades")
async def get_trades(limit: int = Query(50, le=200)):
    trades = await db.trades.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return trades

@app.get("/api/positions")
async def get_positions():
    positions = await db.positions.find({}, {"_id": 0}).to_list(100)
    return positions

@app.get("/api/portfolio")
async def get_portfolio():
    data = await db.portfolio.find({}, {"_id": 0}).sort("timestamp", 1).to_list(1000)
    return data

@app.get("/api/dashboard")
async def get_dashboard():
    portfolio = await db.portfolio.find({}, {"_id": 0}).sort("timestamp", -1).limit(1).to_list(1)
    current_value = portfolio[0]["value"] if portfolio else 10000
    positions = await db.positions.find({"status": "open"}, {"_id": 0}).to_list(100)
    recent_trades = await db.trades.find({}, {"_id": 0}).sort("timestamp", -1).limit(5).to_list(5)
    total_trades = await db.trades.count_documents({})
    alpha_hits = await db.alpha_hits.count_documents({})
    
    # Chain distribution
    chains = {}
    all_hits = await db.alpha_hits.find({}, {"_id": 0, "chainId": 1}).to_list(500)
    for h in all_hits:
        c = h.get("chainId", "unknown")
        chains[c] = chains.get(c, 0) + 1

    return {
        "portfolio_value": current_value,
        "positions": positions,
        "recent_trades": recent_trades,
        "total_trades": total_trades,
        "total_alpha_hits": alpha_hits,
        "active_positions": len(positions),
        "chain_distribution": chains,
        "swarm_active": swarm_running,
        "wallets": {"evm": EVM_WALLET, "sol": SOL_WALLET},
    }

# ─── DEXSCREENER PROXY ENDPOINTS ────────────────────────────────────
@app.get("/api/dex/search")
async def search_dex(q: str = Query(...)):
    pairs = await dex_search_pairs(q)
    return {"pairs": pairs[:20]}

@app.get("/api/dex/token/{chain_id}/{token_address}")
async def get_token_data(chain_id: str, token_address: str):
    pairs = await dex_token_pairs(chain_id, token_address)
    return {"pairs": pairs}

@app.get("/api/dex/trending")
async def get_trending():
    boosted = await dex_boosted_tokens()
    top = await dex_top_boosted()
    return {"boosted": boosted[:20] if isinstance(boosted, list) else [], "top": top[:20] if isinstance(top, list) else []}

@app.get("/api/settings")
async def get_settings():
    return {
        "primary_model": OPENROUTER_PRIMARY_MODEL,
        "fallback_model": OPENROUTER_FALLBACK_MODEL,
        "evm_wallet": EVM_WALLET,
        "sol_wallet": SOL_WALLET,
        "scan_interval": 60,
        "max_position_size": 50,
        "chains": ["ethereum", "solana", "base", "bsc", "polygon", "arbitrum", "optimism", "avalanche"],
    }
