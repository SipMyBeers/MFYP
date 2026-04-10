"""
Process Guardian — keeps MFYP running on Ghengis.
Auto-restarts on crash. Notifies user only after 3 consecutive failures.
"""

import asyncio
import os
import subprocess
import time

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
MFYP_DIR = os.path.expanduser("~/Projects/MFYP")


async def watch_mfyp(user_id: int):
    """Monitor MFYP. Restart on crash. Notify after 3 failures."""
    consecutive_fails = 0

    while True:
        result = subprocess.run(["pgrep", "-f", "mfyp_orchestrator"], capture_output=True)

        if result.returncode != 0:
            print("[Guardian] MFYP not running — restarting...")
            subprocess.Popen(
                ["python3", "mfyp_orchestrator.py"],
                cwd=MFYP_DIR,
                stdout=open("/tmp/mfyp.log", "a"),
                stderr=subprocess.STDOUT,
            )
            await asyncio.sleep(10)

            check = subprocess.run(["pgrep", "-f", "mfyp_orchestrator"], capture_output=True)
            if check.returncode != 0:
                consecutive_fails += 1
                if consecutive_fails >= 3:
                    try:
                        async with aiohttp.ClientSession() as session:
                            await session.post(
                                f"{GORMERS_URL}/api/telegram/mission-report",
                                headers={"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
                                json={"userId": user_id, "message": "⚠️ MFYP keeps crashing on Ghengis.\nCheck: tail -50 /tmp/mfyp.log", "priority": 1},
                                timeout=aiohttp.ClientTimeout(total=5),
                            )
                    except:
                        pass
                    consecutive_fails = 0
            else:
                consecutive_fails = 0
                print("[Guardian] MFYP restarted successfully")

        await asyncio.sleep(60)


# launchd plist for auto-start on boot
LAUNCHD_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.beerslabs.mfyp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/beers/Projects/MFYP/mfyp_orchestrator.py</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/mfyp.log</string>
    <key>StandardErrorPath</key><string>/tmp/mfyp-error.log</string>
</dict>
</plist>"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        plist_path = os.path.expanduser("~/Library/LaunchAgents/com.beerslabs.mfyp.plist")
        with open(plist_path, "w") as f:
            f.write(LAUNCHD_PLIST)
        os.system(f"launchctl load {plist_path}")
        print(f"[Guardian] Installed launchd agent: {plist_path}")
    else:
        asyncio.run(watch_mfyp(user_id=1))
