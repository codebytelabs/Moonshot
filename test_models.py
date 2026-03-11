"""
Model Benchmark Suite — Compare OpenRouter AI Models
Tests: Latency, JSON quality, reliability, token usage, cost efficiency.

Models under test:
  1. deepseek/deepseek-v3.2-exp    (general AI tasks)
  2. z-ai/glm-5                    (general AI tasks)
  3. google/gemini-3-flash-preview  (general AI tasks)
  4. perplexity/sonar-pro-search    (news/research only)
"""

import asyncio
import json
import time
import os
import sys

from dotenv import load_dotenv
load_dotenv(".env", override=True)

import httpx

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")

MODELS = [
    "deepseek/deepseek-v3.2-exp",
    "z-ai/glm-5",
    "google/gemini-3-flash-preview",
    "perplexity/sonar-pro-search",
]

# ── Test Prompts ──────────────────────────────────────────────────────────────

# Test 1: Structured JSON output (critical for trading bot)
JSON_PROMPT = """Analyze these 3 crypto tokens: BTC, ETH, SOL.
For each, provide sentiment analysis.
Return ONLY a valid JSON array. No markdown, no explanation.
Schema: [{"symbol": "BTC", "sentiment": "bullish"|"bearish"|"neutral", "confidence": 0.0-1.0, "catalysts": ["reason1"], "risks": ["risk1"], "summary": "1 sentence"}]"""

# Test 2: Quick decision support (used by DecisionEngine)
DECISION_PROMPT = """Given: BTC price $95,000, RSI=72, MACD bullish crossover, volume +40% vs avg.
Should a trading bot BUY, SELL, or HOLD? Reply with ONLY a JSON object:
{"action": "BUY"|"SELL"|"HOLD", "confidence": 0.0-1.0, "reasoning": "brief reason"}"""

# Test 3: Event explanation (used by BigBrother)
EXPLAIN_PROMPT = """Explain this trading bot event in 2-3 sentences:
Type: mode_change
Message: Mode changed: normal → safety
Details: drawdown_pct=0.08, daily_pnl=-450, can_trade=true
Current mode: safety"""

# Test 4: News/Research (Perplexity specialty)
NEWS_PROMPT = """What are the top 3 crypto market events happening RIGHT NOW that could impact BTC price?
Return a JSON array: [{"event": "description", "impact": "bullish"|"bearish", "magnitude": "high"|"medium"|"low"}]"""

SYSTEM_PROMPT = "You are a crypto trading AI assistant. Always respond with valid JSON when asked for JSON output. Never use markdown code blocks."


async def call_model(model: str, prompt: str, system: str = SYSTEM_PROMPT, timeout: int = 60) -> dict:
    """Call a single model and measure performance."""
    result = {
        "model": model,
        "success": False,
        "latency_s": 0,
        "json_valid": False,
        "response": "",
        "error": None,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "tokens_total": 0,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://moonshot-trading-bot.local",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 800,
                },
            )

        elapsed = time.monotonic() - t0
        result["latency_s"] = round(elapsed, 2)

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            result["success"] = True
            result["response"] = content[:500]

            # Token usage
            usage = data.get("usage", {})
            result["tokens_prompt"] = usage.get("prompt_tokens", 0)
            result["tokens_completion"] = usage.get("completion_tokens", 0)
            result["tokens_total"] = usage.get("total_tokens", 0)

            # JSON validity check
            try:
                clean = content
                start = clean.find("[")
                end = clean.rfind("]")
                if start == -1:
                    start = clean.find("{")
                    end = clean.rfind("}")
                if start != -1 and end != -1:
                    clean = clean[start:end + 1]
                clean = clean.replace("```json", "").replace("```", "").strip()
                json.loads(clean)
                result["json_valid"] = True
            except (json.JSONDecodeError, ValueError):
                result["json_valid"] = False
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            result["latency_s"] = round(time.monotonic() - t0, 2)

    except httpx.TimeoutException:
        result["error"] = "TIMEOUT"
        result["latency_s"] = round(time.monotonic() - t0, 2)
    except Exception as e:
        result["error"] = str(e)
        result["latency_s"] = round(time.monotonic() - t0, 2)

    return result


async def run_benchmark():
    """Run full benchmark suite."""
    if not API_KEY:
        print("❌ OPENROUTER_API_KEY not found in .env")
        return

    print(f"🔑 API Key: {API_KEY[:10]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    print("=" * 80)

    tests = [
        ("JSON Structured Output", JSON_PROMPT),
        ("Quick Decision Support", DECISION_PROMPT),
        ("Event Explanation", EXPLAIN_PROMPT),
        ("News/Research", NEWS_PROMPT),
    ]

    # Store all results
    all_results = {}  # model -> list of test results

    for model in MODELS:
        all_results[model] = []
        print(f"\n{'─' * 80}")
        print(f"🤖 MODEL: {model}")
        print(f"{'─' * 80}")

        for test_name, prompt in tests:
            print(f"\n  📝 Test: {test_name}...", end=" ", flush=True)
            result = await call_model(model, prompt)
            all_results[model].append({"test": test_name, **result})

            if result["success"]:
                json_icon = "✅" if result["json_valid"] else "⚠️"
                print(f"✅ {result['latency_s']}s | JSON: {json_icon} | Tokens: {result['tokens_total']}")
            else:
                print(f"❌ {result.get('error', 'Unknown error')} ({result['latency_s']}s)")

            # Small delay between tests
            await asyncio.sleep(0.5)

    # ── Summary Report ────────────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("📊 BENCHMARK SUMMARY")
    print("=" * 80)

    # Header
    print(f"\n{'Model':<35} {'Avg Latency':>12} {'Success':>8} {'JSON OK':>8} {'Avg Tokens':>11}")
    print("─" * 80)

    model_scores = {}

    for model in MODELS:
        results = all_results[model]
        successes = [r for r in results if r["success"]]
        json_ok = [r for r in successes if r["json_valid"]]

        avg_lat = sum(r["latency_s"] for r in results) / len(results) if results else 0
        avg_tokens = sum(r["tokens_total"] for r in successes) / len(successes) if successes else 0
        success_rate = len(successes) / len(results) * 100 if results else 0
        json_rate = len(json_ok) / len(results) * 100 if results else 0

        print(f"{model:<35} {avg_lat:>10.2f}s {success_rate:>7.0f}% {json_rate:>7.0f}% {avg_tokens:>10.0f}")

        # Score: lower latency = better, higher success = better, higher json = better
        # Weighted: latency 30%, success 35%, json 35%
        lat_score = max(0, 100 - avg_lat * 5)  # 0s=100, 20s=0
        model_scores[model] = {
            "avg_latency": avg_lat,
            "success_rate": success_rate,
            "json_rate": json_rate,
            "avg_tokens": avg_tokens,
            "overall_score": round(lat_score * 0.3 + success_rate * 0.35 + json_rate * 0.35, 1),
        }

    # ── Ranking ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 80}")
    print("🏆 OVERALL RANKING (weighted: 30% speed, 35% reliability, 35% JSON quality)")
    print(f"{'─' * 80}")

    ranked = sorted(model_scores.items(), key=lambda x: x[1]["overall_score"], reverse=True)
    for i, (model, scores) in enumerate(ranked, 1):
        medal = ["🥇", "🥈", "🥉", "4️⃣"][i - 1]
        print(f"  {medal} {model:<35} Score: {scores['overall_score']:>6.1f}")

    # ── Recommendations ───────────────────────────────────────────────────────
    print(f"\n{'─' * 80}")
    print("💡 RECOMMENDATIONS")
    print(f"{'─' * 80}")

    # Filter out perplexity for general tasks
    general_models = {k: v for k, v in model_scores.items() if "perplexity" not in k}
    best_general = max(general_models.items(), key=lambda x: x[1]["overall_score"])

    print(f"\n  🔧 PRIMARY MODEL (general AI tasks):")
    print(f"     → {best_general[0]}")
    print(f"       Score: {best_general[1]['overall_score']} | Latency: {best_general[1]['avg_latency']:.1f}s")

    # Second best for backup
    sorted_general = sorted(general_models.items(), key=lambda x: x[1]["overall_score"], reverse=True)
    if len(sorted_general) > 1:
        backup = sorted_general[1]
        print(f"\n  🔄 SECONDARY MODEL (fallback):")
        print(f"     → {backup[0]}")
        print(f"       Score: {backup[1]['overall_score']} | Latency: {backup[1]['avg_latency']:.1f}s")

    print(f"\n  📰 NEWS/RESEARCH MODEL:")
    print(f"     → perplexity/sonar-pro-search (dedicated, has live search)")

    # ── Detailed Results ──────────────────────────────────────────────────────
    print(f"\n\n{'=' * 80}")
    print("📋 DETAILED TEST RESULTS")
    print("=" * 80)

    for model in MODELS:
        print(f"\n{'─' * 60}")
        print(f"  {model}")
        print(f"{'─' * 60}")
        for r in all_results[model]:
            status = "✅" if r["success"] else "❌"
            json_status = "JSON ✅" if r.get("json_valid") else "JSON ❌"
            print(f"  {status} {r['test']:<25} {r['latency_s']:>6.1f}s  {json_status}  {r.get('tokens_total', 0)} tok")
            if r.get("error"):
                print(f"       Error: {r['error']}")
            elif r["success"]:
                resp_preview = r["response"][:120].replace("\n", " ")
                print(f"       Response: {resp_preview}...")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
