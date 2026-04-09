"""
Colony Tool Registry — auto-discovers CLIs on Ghengis and expands Gorm move set.
STAGED: needs Ghengis + Ollama.
"""

import asyncio
import json
import os
import shutil
import subprocess

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}

TOOL_MANIFEST = {
    "ffmpeg":      {"biomes": ["craft"], "purpose": "video and audio processing", "help": "-help", "example": "ffmpeg -i input.mp4 -vn output.mp3"},
    "yt-dlp":      {"biomes": ["signal", "craft"], "purpose": "video site download", "help": "--help", "example": "yt-dlp --dump-json 'URL'"},
    "rg":          {"biomes": ["scholar"], "purpose": "fast full-text search", "help": "--help", "example": "rg 'term' ~/Documents --type txt -l"},
    "jq":          {"biomes": ["signal", "scholar"], "purpose": "JSON extraction", "help": "--help", "example": "cat data.json | jq '.results[].title'"},
    "gh":          {"biomes": ["scholar", "signal"], "purpose": "GitHub querying", "help": "--help", "example": "gh api repos/owner/repo/issues --jq '.[].title'"},
    "pandoc":      {"biomes": ["craft"], "purpose": "document conversion", "help": "--help", "example": "pandoc input.docx -o output.md"},
    "curl":        {"biomes": ["signal"], "purpose": "HTTP requests", "help": "--help", "example": "curl -s 'URL' | jq '.'"},
    "sqlite3":     {"biomes": ["signal", "scholar"], "purpose": "query SQLite databases", "help": "--help", "example": "sqlite3 db.db 'SELECT * FROM t LIMIT 10'"},
    "exiftool":    {"biomes": ["signal"], "purpose": "read file metadata", "help": "-help", "example": "exiftool -json image.jpg"},
}


async def discover_and_register_tools(user_id: int) -> list[dict]:
    """Scan for installed tools, generate usage guides, register as Gorm skills."""
    discovered = []

    for name, manifest in TOOL_MANIFEST.items():
        if not shutil.which(name):
            continue

        print(f"[ToolRegistry] Found: {name}")
        help_text = _get_help(name, manifest["help"])
        guide = await _generate_guide(name, manifest, help_text)
        if not guide:
            continue

        discovered.append({"name": name, "biomes": manifest["biomes"], "purpose": manifest["purpose"], "guide": guide})
        await _register(user_id, name, manifest, guide)

    print(f"[ToolRegistry] Discovered {len(discovered)} tools")
    return discovered


def _get_help(name: str, flag: str) -> str:
    try:
        result = subprocess.run([name, flag], capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr)[:2000]
    except:
        return f"Tool: {name}"


async def _generate_guide(name: str, manifest: dict, help_text: str) -> str | None:
    prompt = f"""Write a 3-5 sentence usage guide for an AI agent about this CLI tool.
TOOL: {name} — {manifest['purpose']}
EXAMPLE: {manifest['example']}
HELP: {help_text[:800]}
Include: what it does, 2-3 command patterns, expected output format, gotchas."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 200, "temperature": 0.3}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "").strip()
    except:
        return None


async def _register(user_id: int, name: str, manifest: dict, guide: str):
    try:
        async with aiohttp.ClientSession() as session:
            # Get user's Gorms
            async with session.get(f"{GORMERS_URL}/api/pets", headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                gorms = await r.json() if r.status == 200 else []

        relevant = [g for g in gorms if g.get("biome") in manifest["biomes"] and g.get("is_active")]
        for gorm in relevant:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{GORMERS_URL}/api/gorms/{gorm['id']}/skills",
                    headers=HEADERS,
                    json={
                        "claim": f"Can use {name} for {manifest['purpose']}",
                        "sourceUrl": f"local://tool/{name}",
                        "confidence": "HIGH",
                        "importanceTier": 1,
                        "clusterTag": f"tool_{name}",
                        "triggerContext": f"when using {name}, processing {manifest['purpose']}, or executing local commands",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                )
            print(f"[ToolRegistry] Registered {name} for {gorm.get('name', '?')}")
    except Exception as e:
        print(f"[ToolRegistry] Register error: {e}")
