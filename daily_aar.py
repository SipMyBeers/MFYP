"""
Daily AAR (After Action Review)
================================
Generates structured AAR at 2100 from ACE data + mission log.
Sends to Telegram with reflection questions.

STAGED: needs Ghengis + Ollama + MFYP_BRIDGE_SECRET.
"""

import asyncio
import json
import os
import time
from datetime import date

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


async def generate_daily_aar(user_id: str, planning_gorm: dict) -> dict | None:
    """Generate daily AAR from today's data."""
    today = date.today().isoformat()
    gorm_name = planning_gorm.get("name", "Planning Gorm")

    # Get today's OPORD intent
    opord = await _get_opord(user_id, today)
    planned_intent = opord.get("commanders_intent", "No formal OPORD today") if opord else "No formal OPORD today"

    # Get completed missions
    missions = await _get_missions(user_id, today)
    missions_text = "\n".join([
        f"- {m.get('task', '?')[:80]} [{m.get('status', '?')}]"
        for m in missions
    ]) or "No missions executed today."

    # Get life mission for context
    life_mission = await _get_life_mission(user_id)
    mission_text = life_mission.get("mission", "Not set") if life_mission else "Not set"

    prompt = f"""You are {gorm_name}, the planning Gorm.

Generate a daily After Action Review for {today}.

PLANNED INTENT: {planned_intent}
MISSIONS TODAY: {missions_text}
LIFE MISSION: {mission_text}

Write the AAR in this format:

WHAT WAS PLANNED:
- [bullet]

WHAT ACTUALLY HAPPENED:
- [bullet]

SUSTAINED (keep doing):
[one thing that worked]

IMPROVED (change tomorrow):
[one specific actionable change]

REFLECTION QUESTIONS (2, specific to today):
1. [question]
2. [question]

TOMORROW:
[2 specific recommendations]

Keep it under 200 words. Be direct."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 400, "temperature": 0.7}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                aar_text = data.get("message", {}).get("content", "").strip()
    except Exception as e:
        aar_text = (
            f"AAR for {today}\n\n"
            f"Planned: {planned_intent[:100]}\n"
            f"Missions: {len(missions)} executed\n"
            f"[Inference offline — manual review recommended]"
        )

    # Save AAR
    await _save_aar(user_id, today, planned_intent, aar_text)

    # Send to Telegram
    await _send_telegram(user_id, f"◈ DAILY AAR — {today}\n\n{aar_text}")

    return {"date": today, "text": aar_text}


async def _get_opord(user_id: str, today: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/colony/opord?userId={user_id}&date={today}",
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return await r.json() if r.status == 200 else None
    except Exception:
        return None


async def _get_missions(user_id: str, today: str) -> list:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/missions/pending",  # reuse — filter by date client-side
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                if r.status == 200:
                    all_missions = await r.json()
                    return [m.get("mission", {}) for m in all_missions if m.get("mission", {}).get("status") in ("complete", "failed")]
                return []
    except Exception:
        return []


async def _get_life_mission(user_id: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/life/mission",
                headers={**HEADERS, "x-internal-user-id": str(user_id)},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return await r.json() if r.status == 200 else None
    except Exception:
        return None


async def _save_aar(user_id: str, today: str, planned: str, aar_text: str):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/aars",
                headers=HEADERS,
                json={"userId": user_id, "date": today, "plannedIntent": planned, "aarText": aar_text},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except Exception:
        pass


async def _send_telegram(user_id: str, message: str):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/cron/telegram",
                headers=HEADERS,
                json={"chatId": str(user_id), "message": message, "messageType": "briefing", "priority": 5},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except Exception:
        pass


async def run_nightly_aar():
    """Called from orchestrator at 2100. Generates AAR for all active users."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/pets",
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return
                gorms = await r.json()

        # Group by user, pick first Gorm as planning Gorm
        users: dict = {}
        for g in gorms:
            uid = str(g.get("user_id", ""))
            if uid and uid not in users:
                users[uid] = g

        for user_id, planning_gorm in users.items():
            try:
                await generate_daily_aar(user_id, planning_gorm)
                print(f"[AAR] Generated for user {user_id}")
            except Exception as e:
                print(f"[AAR] Failed for user {user_id}: {e}")

    except Exception as e:
        print(f"[AAR] Nightly run error: {e}")
