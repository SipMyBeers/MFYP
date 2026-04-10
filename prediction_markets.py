"""
Prediction Market Intelligence for Arb Gorm.
Polymarket CLOB API + primary source monitoring.
Speed + reasoning + discipline = edge.
"""

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass

import aiohttp

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
PAPER_TRADING = os.environ.get("PREDICTION_PAPER_TRADING", "true").lower() == "true"

# Non-waivable SOPs
MIN_EDGE = 0.05      # 5%
MIN_CONFIDENCE = 0.80
MIN_VOLUME = 100_000
MAX_POSITION_PCT = 0.02  # 2% of bankroll
CIRCUIT_BREAKER_LOSSES = 3


@dataclass
class MarketSignal:
    market_id: str
    question: str
    yes_price: float
    volume: float
    arb_probability: float
    edge: float
    confidence: float
    time_sensitive: bool
    reasoning: str
    source: str
    recommendation: str
    kelly_pct: float


async def get_active_markets(min_volume: float = MIN_VOLUME) -> list[dict]:
    """Fetch active Polymarket markets with sufficient volume."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://gamma-api.polymarket.com/markets",
                params={"active": "true", "closed": "false", "limit": 100, "order": "volume24hr", "ascending": "false"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                data = await r.json()

        markets = []
        items = data.get("markets", data if isinstance(data, list) else [])
        for m in items:
            vol = float(m.get("volume", 0))
            if vol >= min_volume:
                prices = m.get("outcomePrices", ["0.5"])
                markets.append({
                    "id": m.get("id", m.get("condition_id", "")),
                    "question": m.get("question", ""),
                    "yes_price": float(prices[0]) if prices else 0.5,
                    "volume": vol,
                    "end_date": m.get("endDate", ""),
                })
        return markets
    except Exception as e:
        print(f"[Arb] Market fetch error: {e}")
        return []


async def analyze_news_impact(
    news_text: str, news_source: str, markets: list[dict], skill_context: str,
) -> list[MarketSignal]:
    """Core reasoning — analyze news impact on open markets."""
    news_lower = news_text.lower()
    news_words = set(w for w in news_lower.split() if len(w) > 5)

    relevant = []
    for m in markets[:20]:
        q_words = set(w for w in m["question"].lower().split() if len(w) > 5)
        if len(news_words & q_words) >= 2:
            relevant.append(m)

    signals = []
    for market in relevant[:5]:
        prompt = f"""You are Arb, a prediction market analyst.

DOMAIN KNOWLEDGE:
{skill_context[:800]}

NEWS: {news_text[:500]}
Source: {news_source}

MARKET: {market['question']}
Current YES: {market['yes_price']*100:.1f}% · Volume: ${market['volume']:,.0f}

Analyze. Reply JSON only:
{{"relevant":true/false,"arb_probability":0.72,"edge":0.07,"confidence":0.85,"time_sensitive":true,"recommendation":"buy_yes","reasoning":"one sentence"}}

Rules: Only recommend if |edge|>5% AND confidence>80%. Acknowledge uncertainty."""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                          "stream": False, "options": {"num_predict": 200, "temperature": 0.2}},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r:
                    data = await r.json()
                    text = data.get("message", {}).get("content", "")

            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                continue
            result = json.loads(match.group())

            if not result.get("relevant"):
                continue

            edge = result.get("edge", 0)
            conf = result.get("confidence", 0)
            if abs(edge) < MIN_EDGE or conf < MIN_CONFIDENCE:
                continue

            # Kelly sizing
            yp = market["yes_price"]
            b = (1 - yp) / max(yp, 0.01)
            kelly = max(0, min((conf * (b + 1) - 1) / max(b, 0.01), 0.25)) * 0.25

            signals.append(MarketSignal(
                market_id=market["id"], question=market["question"],
                yes_price=yp, volume=market["volume"],
                arb_probability=result.get("arb_probability", yp),
                edge=edge, confidence=conf,
                time_sensitive=result.get("time_sensitive", False),
                reasoning=result.get("reasoning", ""),
                source=news_source,
                recommendation=result.get("recommendation", "hold"),
                kelly_pct=kelly,
            ))
        except Exception as e:
            print(f"[Arb] Analysis error: {e}")

    return sorted(signals, key=lambda s: abs(s.edge) * s.confidence, reverse=True)


# Primary source monitoring
WATCHED_SOURCES = [
    {"name": "FDA Approvals", "url": "https://www.fda.gov/drugs/development-approval-process-drugs/drug-approvals-and-databases", "interval": 30},
    {"name": "SEC EDGAR", "url": "https://efts.sec.gov/LATEST/search-index?q=&dateRange=custom&startdt={today}", "interval": 60},
    {"name": "Federal Register", "url": "https://www.federalregister.gov/api/v1/documents.json?per_page=5&order=newest", "interval": 120},
]

_hashes: dict[str, str] = {}


async def monitor_primary_sources(user_id: int, gorm_id: int, markets: list, skill_ctx: str):
    """Monitor gov sources. Change detected → analyze immediately."""
    print("[Arb] Starting primary source monitoring...")
    while True:
        for source in WATCHED_SOURCES:
            try:
                today = __import__("datetime").date.today().isoformat()
                url = source["url"].replace("{today}", today)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers={"User-Agent": "GormersBot/1.0"},
                                           timeout=aiohttp.ClientTimeout(total=15)) as r:
                        content = (await r.text())[:3000]

                h = hashlib.md5(content.encode()).hexdigest()
                if source["name"] in _hashes and _hashes[source["name"]] != h:
                    print(f"[Arb] CHANGE: {source['name']}")
                    signals = await analyze_news_impact(content, source["name"], markets, skill_ctx)
                    for sig in signals[:3]:
                        await _notify(user_id, gorm_id, sig)

                _hashes[source["name"]] = h
                await asyncio.sleep(source["interval"])
            except Exception as e:
                print(f"[Arb] Monitor error {source['name']}: {e}")
                await asyncio.sleep(60)


async def _notify(user_id: int, gorm_id: int, signal: MarketSignal):
    """Send trade signal to Telegram."""
    direction = "BUY YES" if signal.edge > 0 else "BUY NO"
    urgency = "⚡ " if signal.time_sensitive else ""

    msg = (
        f"{urgency}◈ Arb — Trade Signal\n\n"
        f"{signal.question[:80]}\n\n"
        f"Market: {signal.yes_price*100:.1f}% | Arb: {signal.arb_probability*100:.1f}%\n"
        f"Edge: {signal.edge*100:+.1f}% → {direction}\n"
        f"Confidence: {signal.confidence*100:.0f}%\n"
        f"Size: {signal.kelly_pct*100:.1f}% Kelly\n\n"
        f"{signal.reasoning}\n\n"
        f"Source: {signal.source}\n"
        f"{'📋 PAPER' if PAPER_TRADING else '⚠️ LIVE'}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/telegram/mission-report",
                headers={"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
                json={"userId": user_id, "message": msg, "priority": 1 if signal.time_sensitive else 2},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except:
        pass
