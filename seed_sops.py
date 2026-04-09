"""
Seed Universal SOPs
===================
Seeds the 7 universal standing orders that every Gorm follows.
Run once on first setup. Idempotent — checks for existing SOPs.

STAGED: needs GORMERS_URL + MFYP_BRIDGE_SECRET set.

Usage: python3 seed_sops.py
"""

import asyncio
import os
import sys
import time

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")

if not BRIDGE_SECRET:
    print("[SOPs] MFYP_BRIDGE_SECRET not set")
    sys.exit(1)

UNIVERSAL_SOPS = [
    {
        "sop_id": "budget_constraint",
        "title": "Zero Budget / Spending Constraint",
        "trigger_text": "When a mission has $0 budget or when any step would cost money",
        "procedure": "HALT. Report via Telegram: spending required, amount, reason. Await approval. If denied: find free alternative.",
        "priority": 1,
    },
    {
        "sop_id": "download_approval",
        "title": "Download / Installation Approval",
        "trigger_text": "When any step requires downloading software, files, or installing packages",
        "procedure": "HALT before download. Report: name, source, size, purpose, open source status. Await explicit approval.",
        "priority": 1,
    },
    {
        "sop_id": "account_creation",
        "title": "Account / Registration",
        "trigger_text": "When any step requires creating an account, signing up, or registering",
        "procedure": "HALT. Report: service name, free tier, email needed. Never create accounts autonomously.",
        "priority": 1,
    },
    {
        "sop_id": "time_hack_report",
        "title": "Time Hack Status Report",
        "trigger_text": "At each scheduled time hack checkpoint",
        "procedure": "Send status: TASK, STATUS (on track/behind/blocked), WHAT I DID, WHAT I FOUND, WHAT'S NEXT, BLOCKERS.",
        "priority": 2,
    },
    {
        "sop_id": "spot_check_response",
        "title": "Responding to Spot Checks",
        "trigger_text": "When owner sends spot check command during active mission",
        "procedure": "Suspend current activity. Send full status report. Resume after report. If owner redirects: acknowledge and update.",
        "priority": 2,
    },
    {
        "sop_id": "standards_verification",
        "title": "Self-Assessment Against Standards",
        "trigger_text": "Before marking any deliverable as complete",
        "procedure": "Check each standard explicitly. Report: met/partial/no per standard. If any 'no': do not submit, continue work.",
        "priority": 2,
    },
    {
        "sop_id": "mission_blocked",
        "title": "Mission Blocked / Cannot Proceed",
        "trigger_text": "When Gorm cannot proceed due to constraint, missing capability, or unknown",
        "procedure": "HALT. Report: blocked step, exact reason, three possible paths forward. Do not silently work around blockers.",
        "priority": 1,
    },
]


async def seed():
    print(f"[SOPs] Seeding {len(UNIVERSAL_SOPS)} universal SOPs to {GORMERS_URL}")

    async with aiohttp.ClientSession() as session:
        for sop in UNIVERSAL_SOPS:
            async with session.post(
                f"{GORMERS_URL}/api/sops/seed",
                headers={"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
                json={**sop, "is_universal": 1, "source": "universal"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status == 200:
                    print(f"  + {sop['sop_id']}: {sop['title']}")
                else:
                    # Fallback: try direct insert description
                    print(f"  x {sop['sop_id']}: HTTP {r.status} — may need /api/sops/seed endpoint")

    print(f"\n[SOPs] Done. {len(UNIVERSAL_SOPS)} SOPs seeded.")


if __name__ == "__main__":
    asyncio.run(seed())
