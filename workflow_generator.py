"""
Workflow Generator — planning Gorm decomposes multi-Gorm missions.
"""

import json
import os
import re

import aiohttp

from mission_archive import get_exemplar, classify_type

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


def should_generate_workflow(mission: dict, colony: list) -> bool:
    """Detect multi-Gorm missions."""
    task = mission.get("task", "").lower()
    multi_signals = ["competitive analysis", "strategy", "comprehensive", "and then",
                     "followed by", "draft and send", "research and create", "analyze and recommend"]
    return any(s in task for s in multi_signals) or len(colony) > 3


async def generate_colony_workflow(mission: dict, colony: list, planning_gorm: dict) -> dict:
    """Decompose mission into multi-Gorm workflow."""
    steps = await _generate_steps(mission, colony, planning_gorm)

    return {
        "userId": mission.get("userId") or mission.get("user_id"),
        "name": _name_workflow(mission.get("task", "")),
        "triggerType": "mission",
        "steps": steps,
        "sourceMissionId": mission.get("id"),
        "status": "pending",
    }


async def _generate_steps(mission: dict, colony: list, planning: dict) -> list:
    gorm_desc = "\n".join([
        f"- {g['name']} ({g.get('primary_niche', g.get('primaryDomain', 'general'))}, {g.get('biome', 'signal')})"
        for g in colony
    ])

    prompt = f"""You are {planning['name']}, planning Gorm.

Decompose this mission for the colony. Assign each step to the best Gorm.

MISSION: {mission.get('task', '')}
CONDITIONS: {mission.get('conditions', '')}
STANDARDS: {mission.get('standards', '')}

GORMS: {gorm_desc}

Rules: Void/Skeptic Gorms review, not lead. Max 5 steps. Parallel where possible.

Reply JSON array only:
[{{"id":"step_1","gorm_name":"Fiuto","task":"specific task","depends_on":[],"standards":["standard1"]}}]"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 500, "temperature": 0.5}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            steps = json.loads(match.group())
            gorm_by_name = {g["name"]: g for g in colony}
            for step in steps:
                g = gorm_by_name.get(step.get("gorm_name"))
                if g:
                    step["gorm_id"] = g["id"]
                    step["gorm_domain"] = g.get("primary_niche", g.get("primaryDomain", "general"))
            return steps
    except Exception as e:
        print(f"[Workflow] Generation error: {e}")

    return [{"id": "step_1", "gorm_id": colony[0]["id"], "gorm_name": colony[0]["name"],
             "task": mission.get("task"), "depends_on": [], "standards": [mission.get("standards", "Complete")]}]


def _name_workflow(task: str) -> str:
    lower = task.lower()
    if "competitive" in lower: return "Competitive Analysis"
    if "website" in lower: return "Website Build"
    if "research" in lower and "draft" in lower: return "Research + Draft"
    if "market" in lower: return "Market Research"
    return task[:40]
