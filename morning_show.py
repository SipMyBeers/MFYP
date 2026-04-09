"""
Morning Show Generator
======================
Runs at 0500 on Ghengis. Generates colony OPORD + per-Gorm voice lines.
Saves to /api/morning-show. Telegram notification at 0730.

STAGED: needs Ghengis + Ollama + active Gorms with overnight signals.
"""

import asyncio
import json
import os
import random
import time
from datetime import date, datetime

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


async def run_morning_show_generation(user_id: int):
    """Main entry. Generates OPORD + voice lines for today."""
    today = date.today().isoformat()
    print(f"[MorningShow] Generating for {today}...")

    # Load colony
    gorms = await _load_gorms(user_id)
    if not gorms:
        print("[MorningShow] No active Gorms")
        return

    # Load overnight signals
    signals = await _load_overnight(user_id)

    # Load life mission
    life_mission = await _load_life_mission(user_id)

    # Planning Gorm rotates daily
    day = datetime.now().timetuple().tm_yday
    planning = gorms[day % len(gorms)]
    print(f"[MorningShow] Planning Gorm: {planning['name']}")

    # Generate OPORD
    opord = await _generate_opord(planning, gorms, signals, life_mission)

    # Generate voice lines
    voice_lines = await _generate_voice_lines(gorms, signals)

    # Priority sort + interrupt marking
    ordered = _prioritize(voice_lines)

    # Save
    await _save(user_id, planning["id"], opord, ordered, today)
    print(f"[MorningShow] Saved for {today}")

    # Telegram at 0730
    await _notify(user_id, opord, len(ordered))


async def _load_gorms(user_id: int) -> list:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GORMERS_URL}/api/pets", headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
                return [g for g in (await r.json() if r.status == 200 else []) if g.get("is_active")]
    except:
        return []


async def _load_overnight(user_id: int) -> list:
    cutoff = int((time.time() - 8 * 3600) * 1000)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{GORMERS_URL}/api/signals/overnight",
                params={"userId": user_id, "since": cutoff},
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                return await r.json() if r.status == 200 else []
    except:
        return []


async def _load_life_mission(user_id: int) -> dict | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{GORMERS_URL}/api/life/mission",
                headers={**HEADERS, "x-internal-user-id": str(user_id)},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return await r.json() if r.status == 200 else None
    except:
        return None


async def _generate_opord(planning: dict, gorms: list, signals: list, mission: dict | None) -> dict:
    high = [s for s in signals if s.get("signalStrength") == "HIGH"]
    flash = [s for s in signals if s.get("isFlash")]

    situation = f"{len(signals)} signals overnight. "
    if flash:
        situation += f"{len(flash)} FLASH. "
    if high:
        situation += f"{len(high)} HIGH. "

    tasks = []
    for g in gorms:
        gs = [s for s in signals if s.get("gormId") == g["id"]]
        top = "HIGH" if any(s.get("signalStrength") == "HIGH" for s in gs) else ("MED" if gs else None)
        tasks.append({
            "gormId": g["id"], "gormName": g["name"],
            "domain": g.get("primary_niche", "general"),
            "signalCount": len(gs), "topStrength": top or "LOW",
            "task": f"Brief on {g.get('primary_niche', 'domain')} intelligence",
        })

    quarterly = ""
    if mission:
        objs = json.loads(mission.get("quarterly_objectives", "[]"))
        if objs:
            quarterly = objs[0].get("objective", "")

    prompt = f"""You are {planning['name']}, today's planning Gorm.

OVERNIGHT: {situation}
{f"FLASH: {flash[0].get('content', '')[:100]}" if flash else "No FLASH."}
QUARTERLY: {quarterly or "None set"}

Generate a concise colony OPORD. Reply JSON:
{{"situation": "2 sentences", "mission": "colony mission", "commanders_intent": "end state + principle", "service_support": "escalate via Telegram", "command_signal": "codeword + succession"}}"""

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 300, "temperature": 0.7}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                import re
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    opord = json.loads(match.group())
                    opord["tasks"] = tasks
                    return opord
    except Exception as e:
        print(f"[MorningShow] OPORD error: {e}")

    return {
        "situation": situation,
        "mission": "Monitor assigned domains. Deliver actionable intel by 1800.",
        "commanders_intent": "HIGH signals first. Brief clearly.",
        "service_support": "Escalate blockers via Telegram.",
        "command_signal": "Codeword: RALLY.",
        "tasks": tasks,
    }


async def _generate_voice_lines(gorms: list, signals: list) -> list:
    lines = []
    for g in gorms:
        gs = [s for s in signals if s.get("gormId") == g["id"]]
        high = [s for s in gs if s.get("signalStrength") == "HIGH"]
        domain = g.get("primary_niche", "general")

        if high:
            vl = await _voice_high(g, high[0], len(gs))
        elif gs:
            vl = await _voice_med(g, gs[0], len(gs))
        else:
            vl = random.choice([
                f"{domain.capitalize()} was quiet overnight. Watching.",
                "Nothing notable. Still here.",
                "Quiet sector. Monitoring continues.",
            ])

        lines.append({
            "gormId": g["id"], "gormName": g["name"], "biome": g.get("biome", "signal"),
            "domain": domain, "voiceLine": vl, "signalCount": len(gs),
            "topSignalStrength": "HIGH" if high else ("MED" if gs else None),
            "level": g.get("level", 1),
        })
    return lines


async def _voice_high(gorm: dict, signal: dict, count: int) -> str:
    content = signal.get("content", "")[:200]
    prompt = f"""You are {gorm['name']}, a {gorm.get('primary_niche', 'general')} specialist.
HIGH signal overnight: {content}
Total: {count} signals.
Write 1-2 sentence voice line. Specific. In character. Don't start with your name."""
    return await _ask_short(prompt, gorm.get("primary_niche", "general"))


async def _voice_med(gorm: dict, signal: dict, count: int) -> str:
    content = signal.get("content", "")[:150]
    prompt = f"""You are {gorm['name']}, monitoring {gorm.get('primary_niche', 'general')}.
{count} signals overnight, nothing urgent. Top: {content}
Write 1-2 sentence voice line. Calm but specific. Don't start with your name."""
    return await _ask_short(prompt, gorm.get("primary_niche", "general"))


async def _ask_short(prompt: str, domain: str) -> str:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 60, "temperature": 0.8}},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "").strip()
    except:
        return f"{domain.capitalize()} intelligence processed overnight."


def _prioritize(lines: list) -> list:
    strength = {"HIGH": 100, "MED": 10, None: 0}
    ordered = sorted(lines, key=lambda v: (-strength.get(v.get("topSignalStrength"), 0), -v.get("signalCount", 0), -v.get("level", 1)))
    for i, line in enumerate(ordered):
        line["isInterrupt"] = i > 0 and line.get("topSignalStrength") == "HIGH" and ordered[i-1].get("topSignalStrength") != "HIGH"
        line["presentationOrder"] = i + 1
    return ordered


async def _save(user_id: int, planning_id: int, opord: dict, lines: list, today: str):
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"{GORMERS_URL}/api/morning-show",
                headers=HEADERS,
                json={
                    "userId": user_id, "planningGormId": planning_id, "date": today,
                    "situation": opord.get("situation"), "mission": opord.get("mission"),
                    "commandersIntent": opord.get("commanders_intent"),
                    "tasks": json.dumps(opord.get("tasks", [])),
                    "serviceSupport": opord.get("service_support"),
                    "commandSignal": opord.get("command_signal"),
                    "gormVoiceLines": json.dumps(lines),
                    "priorityOrder": json.dumps([v["gormId"] for v in lines]),
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        print(f"[MorningShow] Save error: {e}")


async def _notify(user_id: int, opord: dict, gorm_count: int):
    mission = opord.get("mission", "")[:100]
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(
                f"{GORMERS_URL}/api/cron/telegram",
                headers=HEADERS,
                json={
                    "chatId": str(user_id),
                    "message": f"◈ MORNING BRIEF — Colony Ready\n\n{mission}\n\n{gorm_count} Gorms reporting.",
                    "messageType": "briefing", "priority": 1,
                },
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except:
        pass
