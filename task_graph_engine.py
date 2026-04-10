"""
Task Graph Engine — converts abstract goals into atomic actionable steps.
Pre-built graphs for known blockers. Gemma generates for unknown goals.
"""

import asyncio
import json
import os
import re

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}

# Pre-built graph for the #1 blocker
GHENGIS_ONLINE_GRAPH = {
    "goal": "Get Ghengis online",
    "why": "Blocks all MFYP signal processing. Colony cannot run until this works.",
    "nodes": [
        {
            "id": "n1", "title": "SSH into Ghengis",
            "primary": {"instruction": "Open Terminal on MacBook:", "command": "ssh beers@ghengis.local", "expected": "Ghengis command prompt"},
            "alternatives": [
                {"label": "Screen Sharing", "instruction": "Finder → Go → Connect to Server → vnc://ghengis.local", "when": "SSH fails"},
                {"label": "Direct keyboard", "instruction": "Plug USB keyboard into Ghengis directly, wake screen", "when": "Network unreachable"},
            ],
            "troubleshooting": [
                "If 'Could not resolve': both devices must be on same WiFi",
                "If 'Connection refused': enable Remote Login in System Settings → Sharing",
                "If 'Host key failed': ssh-keygen -R ghengis.local, then retry",
            ],
            "depends_on": [], "gates": ["n2"], "minutes": 3,
        },
        {
            "id": "n2", "title": "Verify Homebrew installed",
            "primary": {"instruction": "On Ghengis:", "command": "brew --version || /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"", "expected": "Homebrew version number"},
            "alternatives": [],
            "troubleshooting": ["If brew not found after install: eval $(/opt/homebrew/bin/brew shellenv)", "If Xcode tools needed: press Enter to accept"],
            "depends_on": ["n1"], "gates": ["n3"], "minutes": 8,
        },
        {
            "id": "n3", "title": "Install and start Ollama",
            "primary": {"instruction": "Install + start:", "command": "brew install ollama && ollama serve &", "expected": "Ollama running on :11434"},
            "alternatives": [{"label": "Direct download", "instruction": "Download from ollama.ai/download → install .dmg", "when": "Homebrew fails"}],
            "troubleshooting": ["If port in use: Ollama already running! curl localhost:11434/api/tags", "Wait 10s for server startup"],
            "depends_on": ["n2"], "gates": ["n4"], "minutes": 5,
        },
        {
            "id": "n4", "title": "Pull Gemma 2 9B model",
            "primary": {"instruction": "Download model (5GB, 15-20 min):", "command": "ollama pull gemma2:9b", "expected": "Model in: ollama list"},
            "alternatives": [{"label": "Smaller model first", "command": "ollama pull gemma2:2b", "instruction": "Faster test, upgrade later", "when": "Slow internet"}],
            "troubleshooting": ["Takes 15-20 min. Leave terminal open.", "If fails partway: run same command again (resumes)"],
            "depends_on": ["n3"], "gates": ["n5"], "minutes": 20,
        },
        {
            "id": "n5", "title": "Set up Cloudflare tunnel",
            "primary": {"instruction": "Expose Ollama:", "command": "brew install cloudflared && cloudflared tunnel --url http://localhost:11434", "expected": "URL like https://abc-def.trycloudflare.com — COPY THIS"},
            "alternatives": [{"label": "Already have cloudflared", "command": "cloudflared tunnel --url http://localhost:11434", "instruction": "Just run tunnel", "when": "cloudflared installed"}],
            "troubleshooting": ["URL changes on restart (use named tunnel for permanent)", "Keep this terminal OPEN", "If 'failed to dial': check Ghengis internet"],
            "depends_on": ["n4"], "gates": ["n6"], "minutes": 3,
        },
        {
            "id": "n6", "title": "Update Fly.io secrets",
            "primary": {"instruction": "On MacBook (separate terminal):", "command": "fly secrets set OLLAMA_BASE_URL=https://YOUR-TUNNEL-URL.trycloudflare.com -a dittomethis", "expected": "Secrets set successfully"},
            "alternatives": [],
            "troubleshooting": ["Replace YOUR-TUNNEL-URL with actual URL from step 5", "If 'fly not found': brew install flyctl", "If auth error: fly auth login"],
            "depends_on": ["n5"], "gates": ["n7"], "minutes": 2,
        },
        {
            "id": "n7", "title": "Start MFYP and verify loop",
            "primary": {"instruction": "On Ghengis:", "command": "cd ~/Projects/MFYP && python3 mfyp_orchestrator.py", "expected": "[MFYP] Starting... Gorms loaded... signal processing begins"},
            "alternatives": [{"label": "Missing deps", "command": "pip3 install aiohttp requests --break-system-packages", "instruction": "Install first", "when": "ModuleNotFoundError"}],
            "troubleshooting": ["If module not found: pip3 install <module>", "If 0 Gorms: check you have active Gorms on gormers.com", "SUCCESS: signal processing logs within 60s"],
            "depends_on": ["n6"], "gates": [], "minutes": 5,
        },
    ],
}

KNOWN_GRAPHS = {"ghengis_online": GHENGIS_ONLINE_GRAPH}


async def get_current_step(user_id: int, goal: str) -> dict:
    """Returns the specific actionable instruction for the current step."""
    key = goal.lower().replace(" ", "_")
    graph = KNOWN_GRAPHS.get(key)

    if graph:
        progress = await _load_progress(user_id, goal)
        completed = set(progress.get("completed", []))
        current = _find_current(graph["nodes"], completed)

        if not current:
            return {"complete": True, "message": f"{goal} complete!"}

        step_num = next((i + 1 for i, n in enumerate(graph["nodes"]) if n["id"] == current["id"]), 1)
        return {
            "goal": goal,
            "why": graph.get("why", ""),
            "step": current["title"],
            "step_number": step_num,
            "total_steps": len(graph["nodes"]),
            "minutes": current.get("minutes", 5),
            "primary": current["primary"],
            "alternatives": current.get("alternatives", []),
            "troubleshooting": current.get("troubleshooting", []),
            "node_id": current["id"],
        }

    # Generate for unknown goal
    return await _generate_step(user_id, goal)


def _find_current(nodes: list, completed: set) -> dict | None:
    for node in nodes:
        if node["id"] in completed:
            continue
        if all(d in completed for d in node.get("depends_on", [])):
            return node
    return None


async def _load_progress(user_id: int, goal: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/task-graphs/progress",
                params={"userId": user_id, "goal": goal},
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                return await r.json() if r.status == 200 else {"completed": []}
    except:
        return {"completed": []}


async def mark_complete(user_id: int, goal: str, node_id: str):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/task-graphs/progress",
                headers=HEADERS,
                json={"userId": user_id, "goal": goal, "nodeId": node_id, "status": "complete"},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except:
        pass


async def report_stuck(user_id: int, goal: str, node_id: str, reason: str):
    """Send specific troubleshooting via Telegram."""
    key = goal.lower().replace(" ", "_")
    graph = KNOWN_GRAPHS.get(key, {})
    node = next((n for n in graph.get("nodes", []) if n["id"] == node_id), None)
    if not node:
        return

    msg = f"◈ Let's get you unstuck\n\nStep: *{node['title']}*\nIssue: {reason[:100]}\n\n"
    if node.get("troubleshooting"):
        msg += "*Common fixes:*\n" + "\n".join(f"• {f}" for f in node["troubleshooting"][:3]) + "\n\n"
    if node.get("alternatives"):
        msg += "*Alternatives:*\n"
        for alt in node["alternatives"]:
            msg += f"*{alt['label']}*: {alt['instruction']}\n"
            if alt.get("command"):
                msg += f"`{alt['command']}`\n"

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/telegram/mission-report",
                headers=HEADERS,
                json={"userId": user_id, "message": msg, "priority": 1},
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except:
        pass


async def _generate_step(user_id: int, goal: str) -> dict:
    """Gemma generates step for unknown goals."""
    prompt = f"""Generate the NEXT SPECIFIC ACTION for: "{goal}"
Reply JSON: {{"step":"title","instruction":"what to do","command":"exact command or null","expected":"success looks like","minutes":5}}"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 200, "temperature": 0.3}},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    return json.loads(match.group())
    except:
        pass
    return {"step": goal, "instruction": "What specifically is blocking you?", "command": None, "minutes": 30}
