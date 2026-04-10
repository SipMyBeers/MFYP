"""
Autonomous Setup Executor — Gorm does the work, user answers questions.
SSH-based infrastructure agent. Only pauses for approvals and physical blocks.
Supports dual Mac Mini setup: Ghengis (primary) + Nikola (secondary).
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

# SSH key for automated access (generated via ssh-keygen -t ed25519 -f ~/.ssh/mfyp_automation)
SSH_KEY_PATH = os.path.expanduser("~/.ssh/mfyp_automation")


class SetupExecutor:
    """SSH-based autonomous setup. Only stops for approvals and physical blocks."""

    def __init__(self, user_id: int, target_host: str, target_user: str = "beers", role: str = "primary"):
        self.user_id = user_id
        self.host = target_host
        self.user = target_user
        self.role = role  # "primary" (MFYP) or "secondary" (OpenClaw/Burrow)
        self.log: list[str] = []
        self._connected = False

    def _ssh_args(self) -> list[str]:
        """SSH args with automation key if available."""
        args = ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no"]
        if os.path.exists(SSH_KEY_PATH):
            args += ["-i", SSH_KEY_PATH]
        return args

    async def connect(self) -> bool:
        """Try SSH connection. Returns True if successful."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._ssh_args(), f"{self.user}@{self.host}", "echo", "connected",
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
                *self._ssh_args(), f"{self.user}@{self.host}", cmd,
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

    # ── Shared install steps ──

    async def _install_homebrew(self) -> bool:
        if await self.check_installed("brew"):
            await self._report("Homebrew ready", silent=True)
            return True
        await self._report("Installing Homebrew (3-5 min)...", silent=True)
        code, _, err = await self.run_cmd(
            '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
            timeout=600,
        )
        if code != 0:
            await self._report(f"Homebrew install failed: {err[:200]}")
            return False
        await self.run_cmd('echo \'eval "$(/opt/homebrew/bin/brew shellenv)"\' >> ~/.zshrc')
        return True

    async def _install_ollama(self) -> bool:
        if await self.check_installed("ollama"):
            await self._report("Ollama already installed", silent=True)
        else:
            await self._report("Installing Ollama...", silent=True)
            code, _, err = await self.run_cmd("brew install ollama", timeout=300)
            if code != 0:
                await self._report(f"Ollama install failed: {err[:200]}")
                return False
        # Start ollama serve
        await self.run_cmd("pgrep -x ollama || (ollama serve > /tmp/ollama.log 2>&1 &)")
        await asyncio.sleep(3)
        code, out, _ = await self.run_cmd("curl -s http://localhost:11434/api/tags")
        if "models" not in (out or ""):
            await asyncio.sleep(5)
        await self._report("Ollama running", silent=True)
        return True

    async def _pull_gemma(self) -> bool:
        code, out, _ = await self.run_cmd("ollama list 2>/dev/null | grep gemma2")
        if "gemma2" in (out or ""):
            await self._report("Gemma 2 already downloaded", silent=True)
            return True
        await self._report("Downloading Gemma 2 (5GB, ~20 min). Go do something else.")
        code, _, err = await self.run_cmd("ollama pull gemma2:9b", timeout=1800)
        if code != 0:
            await self._report(f"Model download failed: {err[:200]}")
            return False
        await self._report("Gemma 2 ready")
        return True

    async def _start_named_tunnel(self, tunnel_name: str) -> str | None:
        """Start a named Cloudflare tunnel. Returns stable URL or None."""
        if not await self.check_installed("cloudflared"):
            await self.run_cmd("brew install cloudflared", timeout=120)

        # Check if named tunnel exists
        code, out, _ = await self.run_cmd(f"cloudflared tunnel list 2>/dev/null | grep {tunnel_name}")
        if tunnel_name not in (out or ""):
            # Try creating named tunnel (requires login)
            code, _, err = await self.run_cmd(f"cloudflared tunnel create {tunnel_name}", timeout=30)
            if code != 0:
                await self._report(f"Named tunnel create failed (need `cloudflared tunnel login` first?): {err[:200]}")
                # Fallback: quick tunnel
                return await self._start_quick_tunnel()

        # Write config
        config = (
            f"tunnel: {tunnel_name}\n"
            f"credentials-file: /Users/{self.user}/.cloudflared/{tunnel_name}.json\n\n"
            "ingress:\n"
            "  - service: http://localhost:11434\n"
        )
        await self.run_cmd(f"mkdir -p ~/.cloudflared && cat > ~/.cloudflared/config.yml << 'CFEOF'\n{config}CFEOF")
        await self.run_cmd(f"nohup cloudflared tunnel run {tunnel_name} > /tmp/tunnel.log 2>&1 &")
        await asyncio.sleep(5)

        # Get tunnel info
        _, info, _ = await self.run_cmd(f"cloudflared tunnel info {tunnel_name} 2>/dev/null")
        match = re.search(r"https://[a-z0-9-]+\.cfargotunnel\.com", info or "")
        if match:
            return match.group()

        # Try extracting from tunnel list
        _, lst, _ = await self.run_cmd("cloudflared tunnel list 2>/dev/null")
        match = re.search(r"([a-f0-9-]{36})", lst or "")
        if match:
            return f"https://{match.group()}.cfargotunnel.com"

        await self._report("Named tunnel URL not found, falling back to quick tunnel")
        return await self._start_quick_tunnel()

    async def _start_quick_tunnel(self) -> str | None:
        """Fallback: ephemeral quick tunnel."""
        await self.run_cmd("nohup cloudflared tunnel --url http://localhost:11434 > /tmp/tunnel.log 2>&1 &")
        for _ in range(30):
            await asyncio.sleep(2)
            _, log, _ = await self.run_cmd("cat /tmp/tunnel.log 2>/dev/null")
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", log or "")
            if match:
                return match.group()
        return None

    # ── Nikola Setup ──

    async def run_nikola_setup(self, fly_app: str = "gormers") -> bool:
        """
        Nikola setup — secondary colony node.
        Same Ollama/Gemma stack, registered as OLLAMA_SECONDARY_URL.
        """
        await self._report("◈ Starting Nikola setup — secondary colony node")

        if not await self.connect():
            await self._report(
                "Cannot reach Nikola.\n\n"
                "Check:\n1. Is Nikola powered on?\n2. Tailscale running? (`tailscale status`)\n"
            )
            return False

        for step in [self._install_homebrew, self._install_ollama, self._pull_gemma]:
            if not await step():
                return False

        tunnel_url = await self._start_named_tunnel("mfyp-nikola")
        if not tunnel_url:
            await self._report("Tunnel failed on Nikola. Check internet.")
            return False

        approved = await self._request_approval(
            f"Nikola tunnel live: {tunnel_url}\nRegister as secondary inference node?",
            yes="✓ Register", no="✗ Skip",
        )
        if approved:
            import subprocess
            subprocess.run(
                ["fly", "secrets", "set", f"OLLAMA_SECONDARY_URL={tunnel_url}", "-a", fly_app],
                capture_output=True, timeout=30,
            )

        # Verify Ollama responds through tunnel
        code, out, _ = await self.run_cmd(f"curl -s {tunnel_url}/api/tags | grep models")
        if "models" in (out or ""):
            await self._report(
                f"◈ NIKOLA ONLINE ✓ — secondary node active\n\n"
                f"Tunnel: {tunnel_url}\n"
                "Ghengis: Primary MFYP\n"
                "Nikola: Secondary inference + overflow\n\n"
                "Colony running on two machines."
            )
            return True
        else:
            await self._report("Nikola tunnel up but Ollama not responding through it. Check logs.")
            return False


# ── CLI entry point ──

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Mac Mini setup for Gormers colony")
    parser.add_argument("--host", default="ghengis", help="Target hostname (Tailscale MagicDNS name)")
    parser.add_argument("--role", default="primary", choices=["primary", "secondary"],
                        help="primary = runs MFYP, secondary = inference overflow")
    parser.add_argument("--user-id", default=1, type=int)
    parser.add_argument("--fly-app", default="gormers", help="Fly.io app name for secrets")
    args = parser.parse_args()

    executor = SetupExecutor(
        user_id=args.user_id,
        target_host=args.host,
        target_user="beers",
        role=args.role,
    )

    if args.role == "primary":
        success = await executor.run_ghengis_setup(fly_app=args.fly_app)
    else:
        success = await executor.run_nikola_setup(fly_app=args.fly_app)

    if success:
        print(f"[Setup] {args.host} online and operational")
    else:
        print(f"[Setup] {args.host} setup failed — check Telegram for details")


if __name__ == "__main__":
    asyncio.run(main())
