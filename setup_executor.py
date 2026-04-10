"""
Autonomous Setup Executor — Gorm does the work, user answers questions.
SSH-based infrastructure agent. Only pauses for approvals and physical blocks.
"""

import asyncio
import json
import os
import re
import time

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


class SetupExecutor:
    """SSH-based autonomous setup. Only stops for approvals and physical blocks."""

    def __init__(self, user_id: int, target_host: str, target_user: str = "beers"):
        self.user_id = user_id
        self.host = target_host
        self.user = target_user
        self.log: list[str] = []
        self._connected = False

    async def connect(self) -> bool:
        """Try SSH connection. Returns True if successful."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
                f"{self.user}@{self.host}", "echo", "connected",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0 and b"connected" in stdout:
                self._connected = True
                await self._report(f"Connected to {self.host}")
                return True
            await self._report(f"Cannot reach {self.host}: {stderr.decode()[:100]}")
            return False
        except asyncio.TimeoutError:
            await self._report(f"Timeout connecting to {self.host}")
            return False
        except Exception as e:
            await self._report(f"Connection error: {e}")
            return False

    async def run_cmd(self, cmd: str, timeout: int = 120) -> tuple[int, str, str]:
        """Execute command on remote host via SSH."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ssh", "-o", "ConnectTimeout=10", f"{self.user}@{self.host}", cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()
        except asyncio.TimeoutError:
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    async def check_installed(self, cmd: str) -> bool:
        code, _, _ = await self.run_cmd(f"which {cmd} 2>/dev/null || command -v {cmd} 2>/dev/null")
        return code == 0

    # ── Reporting ──

    async def _report(self, msg: str, silent: bool = False):
        self.log.append(msg)
        print(f"[Setup] {msg}")
        if not silent:
            await self._telegram(msg)

    async def _telegram(self, msg: str, keyboard: dict | None = None):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{GORMERS_URL}/api/telegram/mission-report",
                    headers=HEADERS,
                    json={"userId": self.user_id, "message": msg, "keyboard": keyboard,
                          "priority": 1 if keyboard else 3},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except:
            pass

    async def _request_approval(self, msg: str, yes: str = "✓ Yes", no: str = "✗ No") -> bool:
        """Category 2: pause for one-tap approval."""
        approval_id = f"setup_{int(time.time())}"
        await self._telegram(msg, keyboard={
            "inline_keyboard": [[
                {"text": yes, "callback_data": f"approve_{approval_id}"},
                {"text": no, "callback_data": f"deny_{approval_id}"},
            ]]
        })
        # Poll for response (5 min timeout)
        for _ in range(300):
            await asyncio.sleep(1)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{GORMERS_URL}/api/permissions/{approval_id}",
                        headers=HEADERS, timeout=aiohttp.ClientTimeout(total=3),
                    ) as r:
                        data = await r.json() if r.status == 200 else {}
                        if data.get("resolved"):
                            return data.get("approved", False)
            except:
                pass
        return False

    # ── Ghengis Setup ──

    async def run_ghengis_setup(self, fly_app: str = "dittomethis") -> bool:
        """Full Ghengis setup. User effort: 2 taps max."""
        await self._report("◈ Starting Ghengis setup\nI'll handle everything. Only interrupting for decisions.")

        # Step 1: Connect
        if not await self.connect():
            await self._report(
                "Cannot reach Ghengis.\n\n"
                "Check:\n1. Is Ghengis powered on?\n2. Same WiFi as your MacBook?\n\n"
                "Reply 'retry' when ready."
            )
            return False

        # Step 2: Homebrew
        if not await self.check_installed("brew"):
            await self._report("Installing Homebrew (3-5 min)...", silent=True)
            code, _, err = await self.run_cmd(
                '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                timeout=600
            )
            if code != 0:
                await self._report(f"Homebrew install failed: {err[:200]}")
                return False
            await self.run_cmd('echo \'eval "$(/opt/homebrew/bin/brew shellenv)"\' >> ~/.zshrc')
        await self._report("Homebrew ready", silent=True)

        # Step 3: Ollama
        if not await self.check_installed("ollama"):
            await self._report("Installing Ollama...", silent=True)
            code, _, err = await self.run_cmd("brew install ollama", timeout=300)
            if code != 0:
                await self._report(f"Ollama install failed: {err[:200]}")
                return False

        # Start ollama serve
        await self.run_cmd("pgrep -x ollama || (ollama serve > /tmp/ollama.log 2>&1 &)")
        await asyncio.sleep(3)

        code, out, _ = await self.run_cmd("curl -s http://localhost:11434/api/tags")
        if "models" not in out:
            await asyncio.sleep(5)
            await self.run_cmd("curl -s http://localhost:11434/api/tags")
        await self._report("Ollama running", silent=True)

        # Step 4: Gemma model
        code, out, _ = await self.run_cmd("ollama list 2>/dev/null | grep gemma2")
        if "gemma2" not in (out or ""):
            await self._report("Downloading Gemma 2 (5GB, ~20 min). Go do something else 🤙")
            code, _, err = await self.run_cmd("ollama pull gemma2:9b", timeout=1800)
            if code != 0:
                await self._report(f"Model download failed: {err[:200]}")
                return False
            await self._report("◈ Gemma 2 ready")

        # Step 5: Cloudflare tunnel
        if not await self.check_installed("cloudflared"):
            await self.run_cmd("brew install cloudflared", timeout=120)

        await self.run_cmd("nohup cloudflared tunnel --url http://localhost:11434 > /tmp/tunnel.log 2>&1 &")
        tunnel_url = None
        for _ in range(30):
            await asyncio.sleep(2)
            _, log, _ = await self.run_cmd("cat /tmp/tunnel.log 2>/dev/null")
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", log or "")
            if match:
                tunnel_url = match.group()
                break

        if not tunnel_url:
            await self._report("Tunnel failed to start. Check Ghengis internet.")
            return False

        # Step 6: Category 2 — approve secrets update
        approved = await self._request_approval(
            f"Tunnel live. Update Fly.io secrets?\n\nOLLAMA_BASE_URL → {tunnel_url}",
            yes="✓ Update secrets", no="✗ Skip",
        )
        if approved:
            import subprocess
            subprocess.run(["fly", "secrets", "set", f"OLLAMA_BASE_URL={tunnel_url}", "-a", fly_app],
                           capture_output=True, timeout=30)

        # Step 7: Start MFYP
        await self._report("Starting MFYP...", silent=True)
        env = f"OLLAMA_BASE_URL={tunnel_url} GORMERS_URL={GORMERS_URL} MFYP_BRIDGE_SECRET={BRIDGE_SECRET}"
        _, pid, _ = await self.run_cmd(
            f"cd ~/Projects/MFYP && {env} nohup python3 mfyp_orchestrator.py > /tmp/mfyp.log 2>&1 & echo $!",
            timeout=15
        )
        await asyncio.sleep(5)

        # Verify
        code, out, _ = await self.run_cmd(f"curl -s {tunnel_url}/api/tags | grep models")
        if "models" in (out or ""):
            await self._report(
                f"◈ GHENGIS ONLINE ✓\n\n"
                f"MFYP running (PID {pid.strip()})\n"
                f"Tunnel: {tunnel_url}\n\n"
                "Colony is operational. First briefing at 0730."
            )
            return True
        else:
            _, log, _ = await self.run_cmd("tail -20 /tmp/mfyp.log")
            await self._report(f"Loop test issue. MFYP log:\n{(log or '')[:500]}")
            return False
