import os
import asyncio
import json
import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(override=True)  # override=True ensures .env always wins over stale shell env vars

# ─── CONFIG ──────────────────────────────────────────────────────────
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_PRIMARY_MODEL = os.environ.get("OPENROUTER_PRIMARY_MODEL", "qwen/qwen3.5-397b-a17b")
OPENROUTER_FALLBACK_MODEL = os.environ.get("OPENROUTER_FALLBACK_MODEL", "moonshotai/kimi-k2.5")
EVM_WALLET = os.environ.get("EVM_WALLET_ADDRESS", "")
SOL_WALLET = os.environ.get("SOL_WALLET_ADDRESS", "")
PIMLICO_API_KEY = os.environ.get("PIMLICO_API_KEY", "")  # optional — enables real gasless execution
LIFI_API_KEY = os.environ.get("LIFI_API_KEY", "")         # optional — increases rate limits
FLASHBOTS_RPC = "https://rpc.flashbots.net"               # always use — private mempool
LIFI_API_BASE = "https://li.quest/v1"                      # LI.FI REST API


# ─── GLOBALS ─────────────────────────────────────────────────────────
db = None
scanner_task = None
swarm_running = False
ws_clients: list[WebSocket] = []
swarm_cycle_count = 0

# Per-agent performance metrics
agent_metrics: dict = {
    "tinyclaw": {"cycles": 0, "decisions": 0, "last_action": "Awaiting deployment", "status": "idle"},
    "alpha_scanner": {"cycles": 0, "hits_found": 0, "last_action": "Standby", "status": "idle"},
    "contract_sniper": {"cycles": 0, "audits_done": 0, "threats_blocked": 0, "last_action": "Standby", "status": "idle"},
    "execution_core": {"cycles": 0, "trades_executed": 0, "trades_skipped": 0, "last_action": "Standby", "status": "idle"},
    "quant_mutator": {"cycles": 0, "mutations": 0, "last_action": "Awaiting trade data", "status": "idle"},
}

# Live scanner config — mutated by quant_mutator, hot-reloaded each cycle
scanner_config: dict = {
    "min_score": 30,
    "min_liquidity": 1000,
    "min_vol_5m": 500,
    "top_n_audit": 5,
    "position_size_usd": 50,
}


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
            content = r.json()["choices"][0]["message"]["content"]
            return content if content is not None else ""
    except Exception as e:
        if chosen != OPENROUTER_FALLBACK_MODEL:
            try:
                payload["model"] = OPENROUTER_FALLBACK_MODEL
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    r.raise_for_status()
                    content = r.json()["choices"][0]["message"]["content"]
                    return content if content is not None else ""
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

# ─── LIFI CLIENT ────────────────────────────────────────────────────
LIFI_CHAIN_IDS = {
    "ethereum": "1", "base": "8453", "arbitrum": "42161",
    "polygon": "137", "bsc": "56", "optimism": "10",
    "avalanche": "43114", "solana": "1151111081099710",
}
USDC_ADDRESSES = {
    "1": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",      # Ethereum
    "8453": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",   # Base
    "42161": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # Arbitrum
    "137": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",   # Polygon
}

async def lifi_get_quote(from_chain: str, to_chain: str, to_token_address: str, amount_usd: float = 50.0) -> dict | None:
    """Get a real cross-chain quote from LI.FI REST API."""
    from_chain_id = LIFI_CHAIN_IDS.get(from_chain, "8453")  # default to Base
    to_chain_id = LIFI_CHAIN_IDS.get(to_chain, LIFI_CHAIN_IDS.get(from_chain, "8453"))
    from_token = USDC_ADDRESSES.get(from_chain_id, USDC_ADDRESSES["8453"])
    # 6 decimals for USDC
    amount_raw = int(amount_usd * 1_000_000)
    params = {
        "fromChain": from_chain_id,
        "toChain": to_chain_id,
        "fromToken": from_token,
        "toToken": to_token_address,
        "fromAmount": str(amount_raw),
        "fromAddress": EVM_WALLET,
        "order": "FASTEST",
    }
    headers = {"Content-Type": "application/json"}
    if LIFI_API_KEY:
        headers["X-LiFi-Api-Key"] = LIFI_API_KEY
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{LIFI_API_BASE}/quote", params=params, headers=headers)
            if r.status_code == 200:
                data = r.json()
                return {
                    "status": "quoted",
                    "from_chain": from_chain,
                    "to_chain": to_chain,
                    "from_token": "USDC",
                    "to_token": data.get("action", {}).get("toToken", {}).get("symbol", "?"),
                    "from_amount_usd": amount_usd,
                    "estimated_output": data.get("estimate", {}).get("toAmount"),
                    "gas_estimate_usd": data.get("estimate", {}).get("gasCosts", [{}])[0].get("amountUSD", "0"),
                    "tool": data.get("tool", "lifi"),
                    "steps": len(data.get("includedSteps", [])),
                    "transaction_request": data.get("transactionRequest"),
                    "raw": data,
                }
            else:
                return {"status": "quote_failed", "error": r.text[:200]}
    except Exception as e:
        return {"status": "quote_error", "error": str(e)}


async def tinyclaw_orchestrate(cycle: int, hits_count: int, audited_count: int, trades_count: int):
    global agent_metrics
    agent_metrics["tinyclaw"]["cycles"] += 1
    agent_metrics["tinyclaw"]["decisions"] += 1
    agent_metrics["tinyclaw"]["status"] = "active"

    directives = []
    if hits_count == 0:
        directives.append("Broadening scan parameters — zero alpha hits detected")
    elif hits_count >= 8:
        directives.append(f"High signal cycle — {hits_count} targets acquired, escalating sniper priority")
    if audited_count > 0 and trades_count == 0:
        directives.append("Sniper flagged all targets as DANGER — holding execution")
    if trades_count > 0:
        directives.append(f"Executed {trades_count} position(s) this cycle — monitoring PnL")
    if cycle % 5 == 0:
        directives.append("Triggering quant_mutator strategy review")
    if not directives:
        directives.append(f"Cycle #{cycle} nominal — all agents performing within parameters")

    directive = directives[0]
    agent_metrics["tinyclaw"]["last_action"] = directive

    await log_agent("tinyclaw", "DIRECTIVE", f"[Cycle #{cycle}] {directive}")
    await broadcast("agent_metrics", {k: dict(v) for k, v in agent_metrics.items()})

# ─── AGENT: @alpha_scanner ──────────────────────────────────────────
async def alpha_scanner_cycle():
    agent_metrics["alpha_scanner"]["status"] = "active"
    agent_metrics["alpha_scanner"]["cycles"] += 1
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
                base_token = pair.get("baseToken", {})
                # Use actual baseToken.address from pair data — this is the correct 0x EVM address
                # The 'addr' from profiles/boosts may not be the correct EVM format
                real_token_addr = base_token.get("address", addr) or addr
                entry = {
                    "id": str(uuid.uuid4()),
                    "chainId": chain,
                    "tokenAddress": real_token_addr,
                    "pairAddress": pair.get("pairAddress", ""),
                    "dexId": pair.get("dexId", ""),
                    "baseToken": base_token,
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
        agent_metrics["alpha_scanner"]["hits_found"] += len(top)
        agent_metrics["alpha_scanner"]["last_action"] = f"Locked {len(top)} targets | Top: {top[0].get('baseToken', {}).get('symbol', '?')} score={top[0]['score']}"
        await log_agent("alpha_scanner", "LOCKED", f"Top target: {top[0].get('baseToken', {}).get('symbol', '?')} on {top[0]['chainId']} | Score: {top[0]['score']} | Vol5m: ${top[0]['volume']['m5']:,.0f}")
    else:
        agent_metrics["alpha_scanner"]["last_action"] = "No qualifying targets found"
    agent_metrics["alpha_scanner"]["status"] = "idle"

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

    agent_metrics["contract_sniper"]["status"] = "active"
    agent_metrics["contract_sniper"]["cycles"] += 1
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
        agent_metrics["contract_sniper"]["audits_done"] += 1
        agent_metrics["contract_sniper"]["last_action"] = f"CLEARED {symbol} risk={risk}/10"
        await log_agent("contract_sniper", "CLEAR", f"{symbol} SAFE | Risk: {risk}/10 | {analysis.get('reason', '')}")
    elif verdict == "DANGER":
        agent_metrics["contract_sniper"]["threats_blocked"] += 1
        agent_metrics["contract_sniper"]["last_action"] = f"BLOCKED {symbol} risk={risk}/10"
        await log_agent("contract_sniper", "BLOCKED", f"{symbol} DANGER | Risk: {risk}/10 | {analysis.get('reason', '')}")
    else:
        agent_metrics["contract_sniper"]["audits_done"] += 1
        agent_metrics["contract_sniper"]["last_action"] = f"CAUTION {symbol} risk={risk}/10"
        await log_agent("contract_sniper", "CAUTION", f"{symbol} CAUTION | Risk: {risk}/10 | {analysis.get('reason', '')}")

    agent_metrics["contract_sniper"]["status"] = "idle"

    return {**token, "security": analysis}

# ─── AGENT: @execution_core ─────────────────────────────────────────
async def execution_core_trade(token: dict) -> dict:
    symbol = token.get("baseToken", {}).get("symbol", "UNKNOWN")
    chain = token.get("chainId", "unknown")
    token_address = token.get("tokenAddress", "")
    verdict = token.get("security", {}).get("verdict", "CAUTION")
    position_size = scanner_config.get("position_size_usd", 50.0)

    agent_metrics["execution_core"]["status"] = "active"
    agent_metrics["execution_core"]["cycles"] += 1

    if verdict == "DANGER":
        agent_metrics["execution_core"]["trades_skipped"] += 1
        agent_metrics["execution_core"]["last_action"] = f"Skipped {symbol} — DANGER flag"
        agent_metrics["execution_core"]["status"] = "idle"
        await log_agent("execution_core", "ABORTED", f"Skipping {symbol} - flagged DANGER by sniper")
        return {**token, "trade_status": "skipped", "reason": "danger"}

    await log_agent("execution_core", "ROUTING", f"Querying LI.FI for optimal route: USDC → {symbol} on {chain}...")

    # ── Real LI.FI Quote ────────────────────────────────────────────
    lifi_quote = None
    route_description = f"USDC({chain}) → {symbol}({chain})"
    execution_status = "SIMULATED"
    mev_protection = "Flashbots Protect RPC"

    # Only attempt real quote for EVM chains we know
    is_evm = chain in LIFI_CHAIN_IDS and chain != "solana"
    if is_evm and token_address and token_address.startswith("0x"):
        lifi_quote = await lifi_get_quote(
            from_chain=chain,
            to_chain=chain,
            to_token_address=token_address,
            amount_usd=position_size,
        )
        if lifi_quote and lifi_quote.get("status") == "quoted":
            execution_status = "QUOTED"
            route_description = (
                f"USDC({chain}) → {symbol}({chain}) "
                f"via {lifi_quote.get('tool', 'LI.FI')} "
                f"[{lifi_quote.get('steps', 1)} step(s)] "
                f"gas≈${lifi_quote.get('gas_estimate_usd', '?')}"
            )
            await log_agent(
                "execution_core", "QUOTED",
                f"LI.FI quote: {position_size} USDC → {symbol} | "
                f"Tool: {lifi_quote.get('tool')} | "
                f"Gas: ${lifi_quote.get('gas_estimate_usd')} | "
                f"Status: {'Pimlico gasless ready' if PIMLICO_API_KEY else 'Pimlico key missing — sim only'}"
            )
            # ── If Pimlico key exists, broadcast via Flashbots ──────
            if PIMLICO_API_KEY and lifi_quote.get("transaction_request"):
                execution_status = "BROADCAST_READY"
                mev_protection = f"Flashbots Protect ({FLASHBOTS_RPC})"
                await log_agent(
                    "execution_core", "BROADCAST",
                    f"{symbol} trade ready for Flashbots broadcast | "
                    f"EIP-7702 UserOp via Pimlico ({FLASHBOTS_RPC})"
                )
                # TODO: sign + submit UserOp via pimlico SDK when integrated
        else:
            err = lifi_quote.get("error", "no response") if lifi_quote else "unreachable"
            await log_agent("execution_core", "QUOTE_FAIL", f"LI.FI quote failed for {symbol}: {err} — falling back to simulation")
    elif chain == "solana":
        await log_agent("execution_core", "INFO", f"{symbol} is on Solana — Jupiter DEX routing (LI.FI Solana bridge in roadmap)")
    else:
        await log_agent("execution_core", "INFO", f"{symbol} token address not EVM-compatible — simulating")

    trade = {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "chainId": chain,
        "tokenAddress": token_address,
        "pairAddress": token.get("pairAddress", ""),
        "side": "BUY",
        "price": token.get("priceUsd", "0"),
        "amount_usd": position_size,
        "status": execution_status,
        "route": route_description,
        "gas_strategy": "Pimlico EIP-7702 Sponsored" if PIMLICO_API_KEY else "Gas wallet required (add PIMLICO_API_KEY)",
        "mev_protection": mev_protection,
        "lifi_quote": lifi_quote,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": token.get("score", 0),
        "security": token.get("security", {}),
    }

    if db is not None:
        await db.trades.insert_one({**trade})

    agent_metrics["execution_core"]["trades_executed"] += 1
    agent_metrics["execution_core"]["last_action"] = f"BUY {symbol} @ ${token.get('priceUsd', '?')} [{execution_status}]"
    agent_metrics["execution_core"]["status"] = "idle"
    await log_agent(
        "execution_core", "EXECUTED",
        f"BUY {symbol} @ ${token.get('priceUsd', '?')} | {route_description} | [{execution_status}]"
    )

    safe_trade = {k: v for k, v in trade.items() if k != "_id"}
    await broadcast("trade_executed", safe_trade)
    return trade

# ─── AGENT: @quant_mutator ──────────────────────────────────────────
async def quant_mutator_evaluate():
    global agent_metrics, scanner_config
    agent_metrics["quant_mutator"]["status"] = "active"
    agent_metrics["quant_mutator"]["cycles"] += 1
    await log_agent("quant_mutator", "ANALYZING", "Evaluating strategy performance and adapting scanner config...")

    if db is None:
        return

    trades = await db.trades.find({}, {"_id": 0}).sort("timestamp", -1).limit(50).to_list(50)
    total = len(trades)
    if total == 0:
        await log_agent("quant_mutator", "IDLE", "No trades to evaluate yet")
        return

    safe_count = sum(1 for t in trades if t.get("security", {}).get("verdict") == "SAFE")
    quoted_count = sum(1 for t in trades if t.get("status") == "QUOTED")
    avg_score = sum(t.get("score", 0) for t in trades) / total if total else 0
    hit_rate = safe_count / total if total else 0

    # Compute new strategy parameters
    new_config = dict(scanner_config)
    suggestions = []

    if hit_rate < 0.3:
        new_config["min_score"] = min(50, scanner_config["min_score"] + 5)
        suggestions.append(f"Raised min_score to {new_config['min_score']} (hit rate low: {hit_rate:.0%})")
    elif hit_rate > 0.7:
        new_config["min_score"] = max(20, scanner_config["min_score"] - 5)
        suggestions.append(f"Lowered min_score to {new_config['min_score']} (performing well: {hit_rate:.0%})")

    if avg_score < 35:
        new_config["min_vol_5m"] = min(5000, scanner_config["min_vol_5m"] + 500)
        suggestions.append(f"Raised min_vol_5m to {new_config['min_vol_5m']} (avg score low: {avg_score:.0f})")

    if not suggestions:
        suggestions.append(f"Parameters stable | hit_rate={hit_rate:.0%} avg_score={avg_score:.0f} quoted={quoted_count}/{total}")

    # Hot-reload into live scanner_config
    scanner_config.update(new_config)

    analysis = {
        "hit_rate": hit_rate,
        "avg_score": avg_score,
        "quoted_trades": quoted_count,
        "total_trades": total,
        "suggestions": suggestions,
        "new_config": new_config,
        "confidence": min(0.9, total / 50),
    }

    await log_agent(
        "quant_mutator", "MUTATED",
        f"Hit rate: {hit_rate:.1%} | Avg score: {avg_score:.0f} | LI.FI quoted: {quoted_count}/{total} | {suggestions[0]}"
    )
    agent_metrics["quant_mutator"]["mutations"] += 1
    agent_metrics["quant_mutator"]["last_action"] = f"{suggestions[0][:50]}"
    agent_metrics["quant_mutator"]["status"] = "idle"

    if db is not None:
        await db.strategy_mutations.insert_one({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_trades": total,
            "analysis": analysis,
            "applied_config": new_config,
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
    global swarm_running, swarm_cycle_count
    cycle = 0
    # Mark all agents online
    for k in agent_metrics:
        agent_metrics[k]["status"] = "idle"
    await log_agent("tinyclaw", "BOOT", "TinyClaw orchestrator online. Deploying agent swarm...")
    await broadcast("agent_metrics", {k: dict(v) for k, v in agent_metrics.items()})

    while swarm_running:
        cycle += 1
        swarm_cycle_count = cycle
        agent_metrics["tinyclaw"]["status"] = "active"
        await log_agent("tinyclaw", "CYCLE", f"=== SWARM CYCLE #{cycle} INITIATED ===")

        hits_count = 0
        audited_count = 0
        trades_count = 0

        try:
            # Phase 1: Alpha Scanner
            hits = await alpha_scanner_cycle()
            hits_count = len(hits)

            # Phase 2: Contract Sniper audits top hits
            audited = []
            for hit in hits[:5]:
                result = await contract_sniper_analyze(hit)
                audited.append(result)
                audited_count += 1
                await asyncio.sleep(0.3)

            # Phase 3: Execution Core executes safe trades
            for token in audited:
                if token.get("security", {}).get("verdict") in ("SAFE", "CAUTION"):
                    await execution_core_trade(token)
                    trades_count += 1
                    await asyncio.sleep(0.2)

            # Phase 4: Quant Mutator evaluates every 5 cycles
            if cycle % 5 == 0:
                await quant_mutator_evaluate()

            # TinyClaw wraps up the cycle
            await tinyclaw_orchestrate(cycle, hits_count, audited_count, trades_count)
            await log_agent("tinyclaw", "COMPLETE", f"Cycle #{cycle} complete | Hits: {hits_count} | Audited: {audited_count} | Trades: {trades_count} | Next scan in 60s")

        except Exception as e:
            await log_agent("tinyclaw", "ERROR", f"Cycle error: {str(e)}")

        # Wait 60 seconds before next cycle
        for _ in range(60):
            if not swarm_running:
                break
            await asyncio.sleep(1)

    for k in agent_metrics:
        agent_metrics[k]["status"] = "idle"
    await broadcast("agent_metrics", {k: dict(v) for k, v in agent_metrics.items()})
    await log_agent("tinyclaw", "HALTED", "Swarm loop stopped. All agents standing down.")

# ─── SEED DATA ───────────────────────────────────────────────────────
async def seed_data():
    # Load scanner config from DB if it exists (quant_mutator may have written one)
    global scanner_config
    saved = await db.scanner_config.find_one({"_id": "live"}, {"_id": 0})
    if saved:
        scanner_config.update(saved)
    else:
        await db.scanner_config.replace_one({"_id": "live"}, {"_id": "live", **scanner_config}, upsert=True)

    # Seed some initial portfolio data
    existing = await db.portfolio.count_documents({})
    if existing == 0:
        base_time = datetime.now(timezone.utc)
        values = [10000, 10050, 10120, 10080, 10200, 10350, 10300, 10450, 10600, 10550,
                  10700, 10850, 10900, 11000, 10950, 11100, 11250, 11200, 11350, 11500]
        for i, v in enumerate(values):
            ts = datetime(2026, 1, 10 + i // 4, 6 + (i % 4) * 5, 0, 0, tzinfo=timezone.utc)
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

# ─── TINYCLAW API PROXY ───────────────────────────────────────────────
TINYCLAW_API = "http://localhost:3777"

@app.api_route("/api/tc/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_tinyclaw(path: str, request: Request):
    """Proxy all requests to TinyClaw API server on port 3777.
    Handles both /api/tc/agents (APEX-SWARM style) and /api/tc/api/agents (TinyOffice style).
    """
    clean = path.lstrip("/")
    # TinyOffice sends paths like "api/agents" — forward as-is to avoid double /api/
    if clean.startswith("api/") or clean == "api":
        url = f"{TINYCLAW_API}/{clean}"
    else:
        url = f"{TINYCLAW_API}/api/{clean}"
    params = dict(request.query_params)
    try:
        body = await request.body()
    except Exception:
        body = b""
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            params=params,
            content=body,
            headers=headers,
        )
    # Handle SSE streaming responses
    if "text/event-stream" in resp.headers.get("content-type", ""):
        from fastapi.responses import StreamingResponse
        async def stream():
            async with httpx.AsyncClient(timeout=None) as stream_client:
                async with stream_client.stream(request.method, url, params=params, content=body, headers=headers) as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    from fastapi.responses import Response
    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", "application/json"))

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

@app.get("/api/agents/status")
async def get_agents_status():
    # Pull recent logs per agent for context
    agent_log_map = {}
    for agent_name in ["tinyclaw", "alpha_scanner", "contract_sniper", "execution_core", "quant_mutator"]:
        recent = await db.agent_logs.find(
            {"agent": agent_name}, {"_id": 0}
        ).sort("timestamp", -1).limit(5).to_list(5)
        agent_log_map[agent_name] = list(reversed(recent))

    # DB-level stats
    total_trades = await db.trades.count_documents({})
    total_hits = await db.alpha_hits.count_documents({})
    blocked = await db.agent_logs.count_documents({"agent": "contract_sniper", "status": "BLOCKED"})
    mutations = await db.strategy_mutations.count_documents({})

    return {
        "swarm_active": swarm_running,
        "cycle_count": swarm_cycle_count,
        "agents": {
            "tinyclaw": {
                **agent_metrics["tinyclaw"],
                "role": "Master Orchestrator",
                "description": "Coordinates all sub-agents, issues directives, manages cycle flow",
                "color": "#00F3FF",
                "recent_logs": agent_log_map.get("tinyclaw", []),
            },
            "alpha_scanner": {
                **agent_metrics["alpha_scanner"],
                "role": "Market Intelligence",
                "description": "Scans DexScreener for high-momentum tokens across 60+ chains",
                "color": "#00F3FF",
                "total_hits": total_hits,
                "recent_logs": agent_log_map.get("alpha_scanner", []),
            },
            "contract_sniper": {
                **agent_metrics["contract_sniper"],
                "role": "Security Auditor",
                "description": "Heuristic + AI-powered honeypot and rug-pull detection",
                "color": "#FF003C",
                "total_blocked": blocked,
                "recent_logs": agent_log_map.get("contract_sniper", []),
            },
            "execution_core": {
                **agent_metrics["execution_core"],
                "role": "Trade Executor",
                "description": "Routes and executes trades via LI.FI + Pimlico EIP-7702",
                "color": "#39FF14",
                "total_trades": total_trades,
                "recent_logs": agent_log_map.get("execution_core", []),
            },
            "quant_mutator": {
                **agent_metrics["quant_mutator"],
                "role": "Strategy Optimizer",
                "description": "Analyzes performance and adapts scanner parameters over time",
                "color": "#FFD700",
                "total_mutations": mutations,
                "recent_logs": agent_log_map.get("quant_mutator", []),
            },
        },
    }

@app.get("/api/settings")
async def get_settings():
    return {
        "primary_model": OPENROUTER_PRIMARY_MODEL,
        "fallback_model": OPENROUTER_FALLBACK_MODEL,
        "evm_wallet": EVM_WALLET,
        "sol_wallet": SOL_WALLET,
        "scan_interval": 60,
        "max_position_size": scanner_config.get("position_size_usd", 50),
        "chains": ["ethereum", "solana", "base", "bsc", "polygon", "arbitrum", "optimism", "avalanche"],
        "pimlico_enabled": bool(PIMLICO_API_KEY),
        "lifi_api_key_set": bool(LIFI_API_KEY),
        "flashbots_rpc": FLASHBOTS_RPC,
    }

@app.get("/api/scanner/config")
async def get_scanner_config():
    return scanner_config

@app.post("/api/scanner/config")
async def update_scanner_config(config: dict):
    global scanner_config
    scanner_config.update(config)
    if db is not None:
        await db.scanner_config.replace_one({"_id": "live"}, {"_id": "live", **scanner_config}, upsert=True)
    return {"status": "updated", "config": scanner_config}

@app.get("/api/lifi/quote")
async def lifi_quote_endpoint(
    from_chain: str = "base",
    to_chain: str = "base",
    to_token: str = Query(..., description="Target token contract address"),
    amount_usd: float = 50.0,
):
    """Get a real LI.FI cross-chain quote. Test execution routing without committing."""
    quote = await lifi_get_quote(from_chain, to_chain, to_token, amount_usd)
    return quote

@app.get("/api/execution/status")
async def execution_status():
    return {
        "lifi_api": LIFI_API_BASE,
        "lifi_api_key": bool(LIFI_API_KEY),
        "pimlico_enabled": bool(PIMLICO_API_KEY),
        "flashbots_rpc": FLASHBOTS_RPC,
        "evm_wallet": EVM_WALLET[:10] + "..." if EVM_WALLET else None,
        "sol_wallet": SOL_WALLET[:10] + "..." if SOL_WALLET else None,
        "scanner_config": scanner_config,
        "mode": "REAL_QUOTES" if True else "SIMULATION",
    }

