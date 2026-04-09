"""
Financial Signal Monitoring for Wex Gorm.
SEC EDGAR + options flow scanning. Free data sources only.
"""

import asyncio
import json
import os
from datetime import datetime

import aiohttp

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")


async def scan_insider_filings(watchlist: list[str] = None) -> list[dict]:
    """Scan SEC EDGAR for today's Form 4 insider transactions. Free, no API key."""
    signals = []
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt={today}&enddt={today}",
                headers={"User-Agent": "GormersBot dylan@beerslabs.com"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    return []
                data = await r.json()

            for hit in data.get("hits", {}).get("hits", [])[:20]:
                source = hit.get("_source", {})
                entity = source.get("entity_name", "").upper()
                if watchlist and not any(t.upper() in entity for t in watchlist):
                    continue
                signals.append({
                    "type": "insider_filing", "entity": entity, "date": source.get("period_of_report", today),
                    "url": f"https://sec.gov/cgi-bin/browse-edgar?company={entity}&type=4&owner=include&count=5",
                    "strength": "MED",
                })
    except Exception as e:
        print(f"[FinSignals] EDGAR error: {e}")

    return signals


async def analyze_signal(signal: dict, gorm_soul: str = "") -> str:
    """Wex analyzes a signal — intelligence framing, never investment advice."""
    prompt = f"""You are Wex, a financial intelligence Gorm.
Analyze this signal. Provide intelligence, NOT investment advice.
Say "data suggests" not "you should buy".

SIGNAL: {json.dumps(signal)[:500]}

2-3 sentence intelligence brief:"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 150, "temperature": 0.4}},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "").strip()
    except:
        return signal.get("content", "Signal detected.")
