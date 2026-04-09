"""
MFYP Orchestrator
==================
Main entry point for the Gormers intelligence hub.
Runs on Ghengis Mac Mini. Manages per-Gorm sessions,
background watching, signal scoring, skill extraction,
and the Gormverse doomscroll loop.

Run: python3 mfyp_orchestrator.py

Requires:
  OLLAMA_BASE_URL  — Ollama endpoint (localhost or Cloudflare tunnel)
  GORMERS_URL      — https://gormers.com
  MFYP_BRIDGE_SECRET — shared secret for API auth
"""

import asyncio
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import aiohttp

from gorm_session import GormSession, get_sources_for_domain
from signal_scorer import score_signal
from skill_manager import save_skill_entry
from action_extractor import extract_action, submit_plan_to_gormers
from content_sanitizer import sanitize_for_llm

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

if not BRIDGE_SECRET:
    print("[MFYP] MFYP_BRIDGE_SECRET not set — exiting")
    sys.exit(1)

HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}
WATCHER_INTERVAL = 300  # 5 minutes between source checks


async def load_gorm_sessions() -> list[GormSession]:
    """Load active Gorms from gormers.com and create sessions."""
    sessions = []
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                f"{GORMERS_URL}/api/pets",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    print(f"[MFYP] Failed to load Gorms: {r.status}")
                    return []
                gorms = await r.json()

        for gorm in gorms:
            if not gorm.get("is_active"):
                continue
            session = GormSession(
                gorm_id=gorm["id"],
                gorm_name=gorm.get("name", "Gorm"),
                user_id=str(gorm.get("user_id", "")),
                domain=gorm.get("primary_niche", "general"),
                biome=gorm.get("biome", "signal"),
                level=gorm.get("level", 1),
            )
            sessions.append(session)
            print(f"[MFYP] Session: {session.gorm_name} ({session.domain}) — {len(session.sources)} sources")

    except Exception as e:
        print(f"[MFYP] Error loading sessions: {e}")

    return sessions


async def fetch_rss(url: str) -> list[dict]:
    """Fetch and parse an RSS feed. Returns list of {title, content, url, published}."""
    items = []
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                url,
                headers={"User-Agent": "GormersMFYP/1.0"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    return []
                xml_text = await r.text()

        root = ET.fromstring(xml_text)

        # RSS 2.0
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            desc = item.findtext("description", "").strip()
            items.append({
                "title": title,
                "content": sanitize_for_llm(f"{title}. {desc}", 500),
                "url": link,
            })

        # Atom
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns)[:10]:
                title = (entry.findtext("atom:title", "", ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                summary = (entry.findtext("atom:summary", "", ns) or "").strip()
                items.append({
                    "title": title,
                    "content": sanitize_for_llm(f"{title}. {summary}", 500),
                    "url": link,
                })

    except Exception as e:
        print(f"[MFYP] RSS fetch error for {url[:50]}: {e}")

    return items


async def background_watcher_tick(session: GormSession):
    """One tick of background watching for a single Gorm."""
    for source in session.sources:
        url = source.get("url", "")
        label = source.get("label", url[:30])

        items = await fetch_rss(url)
        if not items:
            continue

        new_items = [item for item in items if not session.has_seen(item.get("content", ""))]
        if not new_items:
            continue

        print(f"[MFYP] {session.gorm_name}: {len(new_items)} new items from {label}")

        for item in new_items[:5]:
            # Score the signal
            strength, claim, is_verified = await score_signal(
                content=item["content"],
                domain=session.domain,
                gorm_name=session.gorm_name,
                source_url=item.get("url", ""),
            )

            if strength == "IGNORE":
                continue

            session.record_signal(strength)

            # Push signal to gormers.com watcher_findings
            await push_signal(session, item, strength, claim)

            # Save skill entry for MED+ signals
            if strength in ("HIGH", "MED"):
                await save_skill_entry(
                    gorm_id=session.gorm_id,
                    gorm_name=session.gorm_name,
                    domain=session.domain,
                    claim=claim,
                    confidence=strength,
                    source_url=item.get("url", ""),
                )

            # Check for executable strategies in HIGH signals
            if strength == "HIGH":
                plan = await extract_action(
                    content=item["content"],
                    gorm={"name": session.gorm_name, "primaryDomain": session.domain},
                    source_url=item.get("url", ""),
                )
                if plan:
                    await submit_plan_to_gormers(
                        session.gorm_id,
                        plan,
                        trigger_summary=f"Signal from {label}: {claim[:60]}",
                    )


async def push_signal(session: GormSession, item: dict, strength: str, claim: str):
    """Push a scored signal to gormers.com/watcher_findings."""
    import uuid
    finding_id = f"mfyp:{session.gorm_id}:{uuid.uuid4().hex[:8]}"
    importance = 9 if strength == "HIGH" else 6 if strength == "MED" else 3

    try:
        async with aiohttp.ClientSession() as http:
            # Use the relay endpoint to insert findings
            await http.post(
                f"{GORMERS_URL}/api/relay",
                headers=HEADERS,
                json={
                    "finding_id": finding_id,
                    "gorm_id": session.gorm_id,
                    "user_id": session.user_id,
                    "title": item.get("title", claim[:80]),
                    "summary": claim,
                    "url": item.get("url", ""),
                    "importance_score": importance,
                    "extraction_method": "mfyp_rss",
                    "channel": "background",
                    "source": "mfyp",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
    except Exception as e:
        print(f"[MFYP] Push signal error: {e}")


async def process_ace_labels(sessions: list[GormSession]):
    """Poll ACE labels and trigger live research for matching Gorms."""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                f"{GORMERS_URL}/api/ace/pending",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return
                labels = await r.json()

        for label in labels:
            domain = label.get("domain", "")
            topic = label.get("topic_hint", "")
            print(f"[MFYP] ACE label: {label.get('context')} @ {domain} ({topic})")

            # Find Gorms whose domain matches this ACE label
            for session in sessions:
                domain_lower = session.domain.lower()
                if domain.lower() in domain_lower or any(
                    w in topic.lower() for w in domain_lower.split() if len(w) > 3
                ):
                    print(f"[MFYP] {session.gorm_name} triggered by ACE label: {topic}")
                    # Could trigger targeted research here
                    # For now: just log the match

    except Exception as e:
        print(f"[MFYP] ACE polling error: {e}")


async def main_loop():
    """Main orchestrator loop."""
    print(f"[MFYP] Starting orchestrator")
    print(f"[MFYP] Gormers URL: {GORMERS_URL}")
    print(f"[MFYP] Ollama URL: {OLLAMA_BASE}")

    # Verify Ollama is reachable
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{OLLAMA_BASE}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    models = [m["name"] for m in data.get("models", [])]
                    print(f"[MFYP] Ollama models: {', '.join(models)}")
                else:
                    print(f"[MFYP] WARNING: Ollama returned {r.status}")
    except Exception as e:
        print(f"[MFYP] WARNING: Ollama unreachable: {e}")
        print(f"[MFYP] Continuing anyway — scoring will fallback to keywords")

    # Load Gorm sessions
    sessions = await load_gorm_sessions()
    if not sessions:
        print("[MFYP] No active Gorms found. Waiting...")

    # Start doomscroll loop in background
    from gormverse_doomscroll import gormverse_loop
    asyncio.create_task(gormverse_loop())

    # Start executor polling in background
    from gorm_executor import poll_and_execute
    asyncio.create_task(poll_and_execute())

    # Start mission executor polling in background
    from mission_executor import run_pending_missions
    async def mission_loop():
        while True:
            try:
                await run_pending_missions()
            except Exception as e:
                print(f"[MFYP] Mission executor error: {e}")
            await asyncio.sleep(30)
    asyncio.create_task(mission_loop())

    print(f"[MFYP] Running with {len(sessions)} Gorm sessions. Watching every {WATCHER_INTERVAL}s.")

    tick = 0
    while True:
        tick += 1

        # Reload sessions every 20 ticks (100 min) to pick up new Gorms
        if tick % 20 == 0:
            sessions = await load_gorm_sessions()

        # Background watcher tick for each Gorm
        for session in sessions:
            try:
                await background_watcher_tick(session)
            except Exception as e:
                print(f"[MFYP] Watcher error for {session.gorm_name}: {e}")

        # Process ACE labels
        await process_ace_labels(sessions)

        # Status
        total_signals = sum(s.signal_count for s in sessions)
        total_high = sum(s.high_count for s in sessions)
        if tick % 6 == 0:  # Every 30 min
            print(f"[MFYP] Status: {len(sessions)} Gorms, {total_signals} signals total ({total_high} HIGH)")

        await asyncio.sleep(WATCHER_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main_loop())
