"""
DittoMe Tool — Ponda calls DittoMe analysis as a tool skill.
Used during competitive intelligence missions.
"""

import asyncio
import os

import aiohttp

DITTOME_URL = os.environ.get("DITTOME_URL", "https://dittomethis.com")
DITTOME_API_KEY = os.environ.get("DITTOME_API_KEY", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")


async def analyze_competitor(url: str, analysis_type: str = "full") -> dict:
    """
    Ponda calls this during competitive intelligence missions.

    analysis_type: tech_stack | onboarding | pricing | features | full
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DITTOME_URL}/api/analyze",
                headers={
                    "Authorization": f"Bearer {DITTOME_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"url": url, "type": analysis_type, "depth": "standard"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                if r.status == 200:
                    return await r.json()
                return {"error": f"DittoMe returned {r.status}", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


async def run_competitive_intel_mission(
    user_id: int,
    competitors: list[str],
    focus: str = "full",
) -> str:
    """
    Weekly Ponda mission: analyze all competitors.
    Returns synthesized intelligence brief.
    """
    results = []
    for url in competitors:
        print(f"[DittoMe] Analyzing: {url}")
        analysis = await analyze_competitor(url, focus)
        results.append({"url": url, "analysis": analysis})

    summary = "\n".join(
        f"- {r['url']}: {r['analysis'].get('error', 'analyzed')}"
        for r in results
    )

    prompt = f"""You are Ponda, a skeptic and competitive intelligence analyst.

You analyzed {len(competitors)} competitors using reverse engineering tools.

RAW RESULTS:
{summary}

Generate a competitive intelligence brief:
1. What each competitor does well (be honest)
2. Gaps vs Gormers
3. Features worth copying
4. Features we have that they don't
5. Overall threat: LOW / MED / HIGH

Be specific. No generic observations. 3-4 sentences per competitor."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 600, "temperature": 0.4},
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "Analysis failed")
    except Exception as e:
        return f"Synthesis failed: {e}"


# Competitor watch lists — Ponda runs these weekly
GORMERS_COMPETITORS = [
    "https://relevanceai.com",
    "https://clay.com",
    "https://make.com",
    "https://zapier.com/ai",
    "https://coworkai.com",
    "https://manus.ai",
]

LOOTLENS_COMPETITORS = [
    "https://calai.app",
    "https://scoutiq.com",
    "https://sellozo.com",
]

KILLSESH_COMPETITORS = [
    "https://haveibeenpwned.com",
    "https://1password.com",
    "https://bitwarden.com",
]
