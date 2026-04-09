"""
Gormverse Doomscroll Mode
=========================
When user's share queue is empty, MFYP doomscrolls on their behalf.
Finds content similar to recent user shares across Reddit + HN.
Pushes discovered content back to gormverse_queue via /api/share/ingest-mfyp.

Run: python3 gormverse_doomscroll.py
Runs forever, checking every 5 minutes.
"""

import asyncio
import aiohttp
import json
import os
import sys
from urllib.parse import quote

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")

if not BRIDGE_SECRET:
    print("[MFYP] MFYP_BRIDGE_SECRET not set — exiting")
    sys.exit(1)

HEADERS = {
    "x-gorm-secret": BRIDGE_SECRET,
    "Content-Type": "application/json",
}


async def fetch_queue(session: aiohttp.ClientSession, pending_only: bool = False) -> list:
    """Fetch the gormverse queue from gormers.com."""
    params = "?limit=20"
    if pending_only:
        params += "&pending=1"
    try:
        async with session.get(
            f"{GORMERS_URL}/api/share/queue{params}",
            headers=HEADERS,
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"[MFYP] Queue fetch failed: {e}")
    return []


async def search_reddit(session: aiohttp.ClientSession, topic: str) -> list:
    """Search Reddit for content matching a topic."""
    items = []
    try:
        url = f"https://www.reddit.com/search.json?q={quote(topic)}&sort=hot&limit=5"
        async with session.get(url, headers={"User-Agent": "GormersMFYP/1.0"}) as r:
            if r.status == 200:
                data = await r.json()
                for child in data.get("data", {}).get("children", [])[:3]:
                    post = child.get("data", {})
                    if post.get("url"):
                        items.append({
                            "url": post["url"],
                            "title": post.get("title", ""),
                            "content": post.get("selftext", "")[:500],
                            "source": "reddit",
                        })
    except Exception as e:
        print(f"[MFYP] Reddit search failed for '{topic}': {e}")
    return items


async def search_hn(session: aiohttp.ClientSession, topic: str) -> list:
    """Search Hacker News via Algolia API."""
    items = []
    try:
        url = f"https://hn.algolia.com/api/v1/search?query={quote(topic)}&tags=story&hitsPerPage=5"
        async with session.get(url) as r:
            if r.status == 200:
                data = await r.json()
                for hit in data.get("hits", [])[:2]:
                    story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                    items.append({
                        "url": story_url,
                        "title": hit.get("title", ""),
                        "content": "",
                        "source": "hn",
                    })
    except Exception as e:
        print(f"[MFYP] HN search failed for '{topic}': {e}")
    return items


def extract_topics_from_shares(shares: list) -> list[str]:
    """Extract doomscroll topics from recent user shares."""
    topics = []
    for share in shares[:10]:
        # Tags
        try:
            tags = json.loads(share.get("tags", "[]"))
            topics.extend(t.strip("#").lower() for t in tags if t)
        except (json.JSONDecodeError, TypeError):
            pass
        # Creator
        if creator := share.get("creator"):
            topics.append(creator.strip("@").lower())
        # Title keywords
        if title := share.get("title"):
            words = [w.lower() for w in title.split() if len(w) > 4 and w.isalpha()]
            topics.extend(words[:3])

    # Deduplicate
    return list(dict.fromkeys(topics))[:15]


async def doomscroll(session: aiohttp.ClientSession, recent_shares: list):
    """Find content similar to recent shares across public sources."""
    topics = extract_topics_from_shares(recent_shares)
    if not topics:
        print("[MFYP] No topics extracted from recent shares — skipping doomscroll")
        return

    print(f"[MFYP] Doomscroll topics: {', '.join(topics[:5])}...")

    discovered = []
    for topic in topics[:5]:
        reddit_items = await search_reddit(session, topic)
        hn_items = await search_hn(session, topic)
        for item in reddit_items + hn_items:
            item["mfyp_topic"] = topic
            discovered.append(item)

    # Push discovered content to gormverse_queue
    pushed = 0
    for item in discovered[:20]:
        if not item.get("url"):
            continue
        try:
            async with session.post(
                f"{GORMERS_URL}/api/share/ingest-mfyp",
                headers=HEADERS,
                json={
                    "url": item["url"],
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "mfyp_topic": item.get("mfyp_topic", ""),
                },
            ) as r:
                if r.status == 200:
                    pushed += 1
        except Exception as e:
            print(f"[MFYP] Push failed for {item['url']}: {e}")

    print(f"[MFYP] Doomscroll complete — pushed {pushed} items to Gormverse queue")


async def gormverse_loop():
    """Main loop. Checks queue every 5 minutes. Doomscrolls when empty."""
    print(f"[MFYP] Gormverse doomscroll loop starting — target: {GORMERS_URL}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Check for pending user shares
                pending = await fetch_queue(session, pending_only=True)

                if pending:
                    print(f"[MFYP] {len(pending)} pending items in queue — Gorms are processing")
                else:
                    # Queue empty — time to doomscroll
                    print("[MFYP] Queue empty — entering doomscroll mode")
                    recent = await fetch_queue(session, pending_only=False)
                    await doomscroll(session, recent)

            except Exception as e:
                print(f"[MFYP] Loop error: {e}")

            await asyncio.sleep(5 * 60)  # 5 minutes


if __name__ == "__main__":
    asyncio.run(gormverse_loop())
