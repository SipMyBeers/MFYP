"""
TCS Generator — auto-generates Task/Conditions/Standards from end state.
No user needs to write TCS manually.
"""

import json
import os
import re

import aiohttp

from mission_archive import classify_type

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")

UNIVERSAL_CONDITIONS = [
    "Public data sources only — no paid data without approval",
    "Zero budget — free tools and public resources only",
    "No accounts created without owner approval",
    "No sending, publishing, or deploying without review",
]


async def generate_tcs(end_state: dict, gorm: dict, colony_capability: dict = None) -> dict:
    """Auto-generate complete TCS from an end state specification."""
    mission_type = classify_type(end_state.get("deliverable", ""))
    est_hours = (colony_capability or {}).get("avg_completion_hours", 4)
    times_done = (colony_capability or {}).get("times_executed", 0)

    prompt = f"""Generate a complete TCS for this mission.

DELIVERABLE: {end_state.get('deliverable')}
QUALITY: {end_state.get('qualityMarker', 'Completed successfully')}
GORM: {gorm.get('name', 'Gorm')} ({gorm.get('primaryDomain', 'general')})
COLONY EXPERIENCE: {times_done} similar missions, avg {est_hours:.1f}h

Generate:
- task: one clear sentence
- standards: 4-6 specific measurable criteria
- time_hacks: checkpoints at 25/50/75/100%

Include these universal conditions:
{chr(10).join(f'- {c}' for c in UNIVERSAL_CONDITIONS)}

Reply JSON:
{{"task":"...","conditions":["..."],"standards":["..."],"time_hacks":[{{"hours":1.0,"deliverable":"..."}}],"estimated_hours":4.0,"spot_check_interval_mins":60}}"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 400, "temperature": 0.5}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    return json.loads(match.group())
    except Exception as e:
        print(f"[TCS] Generation error: {e}")

    return {
        "task": end_state.get("deliverable"),
        "conditions": UNIVERSAL_CONDITIONS,
        "standards": end_state.get("impliedStandards", ["Task completed"]),
        "time_hacks": [
            {"hours": est_hours / 2, "deliverable": "Research complete"},
            {"hours": est_hours, "deliverable": "Final delivery"},
        ],
        "estimated_hours": est_hours,
        "spot_check_interval_mins": 60,
    }
