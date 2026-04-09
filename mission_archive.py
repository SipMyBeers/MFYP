"""
Mission Archive — DGM-inspired self-improvement.
Every successful mission teaches the colony something.
"""

import json
import os
import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


async def record_to_archive(mission: dict, outcome: dict):
    """Record a successful mission outcome to the archive."""
    standards_met = outcome.get("standard_checks", [])
    pct = sum(1 for s in standards_met if s.get("met")) / max(len(standards_met), 1)
    if pct < 0.70:
        return

    mission_type = classify_type(mission.get("task", ""))
    approach = await _summarize_approach(mission, outcome)

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/mission-archive",
                headers=HEADERS,
                json={
                    "userId": mission.get("userId") or mission.get("user_id"),
                    "missionType": mission_type,
                    "domain": mission.get("gormDomain", "general"),
                    "gormId": mission.get("gormId") or mission.get("gorm_id"),
                    "missionId": mission.get("id"),
                    "researchStrategy": json.dumps(mission.get("research_log", [])[:5]),
                    "successfulApproach": approach,
                    "standardsMetPct": pct,
                    "iterationsNeeded": outcome.get("iterations", 1),
                    "hoursTaken": mission.get("hours_taken", 0),
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
        print(f"[Archive] Recorded: {mission_type} ({pct:.0%})")
    except Exception as e:
        print(f"[Archive] Record error: {e}")


async def get_exemplar(user_id: int, mission_type: str, domain: str) -> dict | None:
    """Get the best past approach for a mission type."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/mission-archive/exemplar",
                params={"userId": user_id, "missionType": mission_type, "domain": domain},
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return await r.json() if r.status == 200 else None
    except:
        return None


async def _summarize_approach(mission: dict, outcome: dict) -> str:
    findings = [r.get("finding", "")[:100] for r in mission.get("research_log", [])[:5]]
    prompt = f"""Summarize what made this mission succeed (2-3 sentences):
TASK: {mission.get('task', '')[:200]}
KEY FINDINGS: {chr(10).join(f'- {f}' for f in findings)}
Keep it actionable for future similar missions."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 100, "temperature": 0.3}},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "").strip()
    except:
        return f"Mission completed with {outcome.get('standards_met_pct', 0):.0%} standards met."


def classify_type(task: str) -> str:
    lower = task.lower()
    if any(w in lower for w in ["sprite", "pixel", "draw"]): return "sprite_creation"
    if any(w in lower for w in ["llc", "legal", "contract"]): return "legal_research"
    if any(w in lower for w in ["market", "price", "ebay"]): return "market_analysis"
    if any(w in lower for w in ["website", "web app"]): return "website_build"
    if any(w in lower for w in ["email", "draft"]): return "email_draft"
    if any(w in lower for w in ["competitive", "analysis"]): return "competitive_analysis"
    if any(w in lower for w in ["research"]): return "research"
    return "general_task"
