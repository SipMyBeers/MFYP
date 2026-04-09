"""
4-File Context Export — generates portable agent files from Gorm's database state.
Works with Claude Code, Codex, Cowork, any agent framework.
"""

import asyncio
import json
import os
from pathlib import Path

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET}


async def export_gorm_context(gorm_id: int, output_dir: str = "./gorm-context") -> dict[str, str]:
    """Export Gorm's full context as 4 standard agent files."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GORMERS_URL}/api/gorms/{gorm_id}/export?format=json",
            headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                print(f"[Export] Failed to load Gorm {gorm_id}")
                return {}
            gorm = await r.json()

    name = gorm.get("name", "gorm").lower()
    out = Path(output_dir) / name
    out.mkdir(parents=True, exist_ok=True)

    files = {}

    # 1. agent.md
    agent = _gen_agent_md(gorm)
    (out / "agent.md").write_text(agent)
    files["agent.md"] = agent

    # 2. memory.md
    memory = _gen_memory_md(gorm)
    (out / "memory.md").write_text(memory)
    files["memory.md"] = memory

    # 3. skills/
    skills_dir = out / "skills"
    skills_dir.mkdir(exist_ok=True)
    skill_files = _gen_skills(gorm, skills_dir)
    files.update(skill_files)

    # 4. mcp.json
    mcp = _gen_mcp(gorm)
    (out / "mcp.json").write_text(json.dumps(mcp, indent=2))
    files["mcp.json"] = json.dumps(mcp, indent=2)

    print(f"[Export] {gorm.get('name')}: {len(files)} files → {out}/")
    return files


def _gen_agent_md(g: dict) -> str:
    skills = sorted(
        [s for s in g.get("skillClaims", []) if s.get("importanceTier") == 1],
        key=lambda s: s.get("confidence", 0), reverse=True,
    )[:10]
    tools = [s for s in g.get("skillClaims", []) if s.get("isToolSkill")]

    skill_lines = "\n".join(f"- [{int(s.get('confidence',0)*100)}%] {s.get('claim','')}" for s in skills)
    tool_lines = "\n".join(f"- **{t.get('toolName','')}**: {t.get('claim','')}" for t in tools)

    return f"""# {g.get('name','')} — Agent Context File
Species: #{str(g.get('speciesNum','?')).zfill(3)} · Biome: {g.get('biome','signal').capitalize()}
Level: {g.get('level',1)} · Domain: {g.get('primaryDomain','general')}

## Identity
**Soul:** {g.get('soul','')}

## Core Knowledge
{skill_lines or 'No verified claims yet.'}

## Tools
{tool_lines or 'No tools registered yet.'}

## Rules
1. End state focus — receive TCS, determine the path
2. SOP compliance — check SOPs before any risky action
3. Source verification — distinguish verified from inference
4. Escalate, don't guess — report blockers via SALUTE

---
*Auto-generated from Gormers database*
"""


def _gen_memory_md(g: dict) -> str:
    return f"""# {g.get('name','')} — Memory File

## Corrections
(Append corrections and learned preferences here)

## Style Preferences
- Briefing: {g.get('userBriefingStyle','direct')}

---
*Auto-synced from Gormers database*
"""


def _gen_skills(g: dict, skills_dir: Path) -> dict[str, str]:
    files = {}
    clusters: dict[str, list] = {}
    for claim in g.get("skillClaims", []):
        tag = claim.get("clusterTag", "general")
        clusters.setdefault(tag, []).append(claim)

    for tag, claims in clusters.items():
        sorted_c = sorted(claims, key=lambda c: c.get("confidence", 0), reverse=True)
        content = f"# Skill: {tag.replace('_',' ').title()}\n{len(claims)} claims\n\n"
        content += f"## Trigger\n{sorted_c[0].get('triggerContext', f'When working with {tag}')}\n\n"
        content += "## Knowledge\n\n"
        for c in sorted_c[:8]:
            conf = int(c.get("confidence", 0) * 100)
            peer = " 🔵" if c.get("peerStatus") == "consensus" else ""
            content += f"- [{conf}%]{peer} {c.get('claim','')}\n"
        content += f"\n---\n*{len(claims)} total claims*\n"
        (skills_dir / f"{tag}.md").write_text(content)
        files[f"skills/{tag}.md"] = content

    return files


def _gen_mcp(g: dict) -> dict:
    tools = [s for s in g.get("skillClaims", []) if s.get("isToolSkill")]
    return {
        "gorm": g.get("name", ""),
        "domain": g.get("primaryDomain", "general"),
        "mcpServers": [],
        "localTools": [{"name": t.get("toolName", ""), "description": t.get("claim", "")} for t in tools],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--gorm-id", type=int, required=True)
    parser.add_argument("--output", default="./gorm-context")
    args = parser.parse_args()
    asyncio.run(export_gorm_context(args.gorm_id, args.output))
