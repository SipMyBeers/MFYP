"""
Influencer Profiler
===================
Researches influencers detected via ACE or onboarding.
Derives user profile from the constellation.

STAGED: needs Ghengis + Ollama.
"""

import asyncio
import json
import os
import re

import aiohttp

from content_sanitizer import sanitize_for_llm

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


async def research_influencer(user_id: int, name: str, platform: str) -> dict | None:
    """Research an influencer and extract profile."""
    print(f"[Profiler] Researching: {name}")

    # Search
    results = await _search(f"{name} philosophy worldview beliefs")
    if not results:
        return None

    # Extract content from top results
    content_pieces = []
    for r in results[:3]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(r["url"], headers={"User-Agent": "GormersBot/1.0"},
                                       timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    html = await resp.text()
                    # Simple extraction
                    desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
                    title = re.search(r"<title[^>]*>([^<]+)", html, re.IGNORECASE)
                    text = sanitize_for_llm((desc.group(1) if desc else "") + " " + (title.group(1) if title else ""), 500)
                    if text.strip():
                        content_pieces.append(text)
        except:
            continue

    if not content_pieces:
        return None

    # Analyze with Gemma
    combined = "\n---\n".join(content_pieces)
    profile = await _analyze(name, platform, combined)

    if profile:
        await _save(user_id, name, platform, profile)

    return profile


async def _search(query: str) -> list[dict]:
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
                headers={"User-Agent": "GormersBot/1.0"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                data = await r.json(content_type=None)
                if data.get("AbstractURL"):
                    results.append({"url": data["AbstractURL"]})
                for topic in data.get("RelatedTopics", [])[:3]:
                    if isinstance(topic, dict) and topic.get("FirstURL"):
                        results.append({"url": topic["FirstURL"]})
    except:
        pass
    return results


async def _analyze(name: str, platform: str, content: str) -> dict | None:
    prompt = f"""Analyze {name} ({platform}) from this content:

{content[:2000]}

Reply ONLY valid JSON:
{{
  "core_philosophy": "2 sentence summary",
  "values_promoted": ["val1", "val2", "val3"],
  "spiral_level": 5,
  "communication_style": "direct|narrative|analytical|emotional",
  "worldview": "red_pill|mainstream|spiritual|libertarian|contrarian",
  "key_themes": ["theme1", "theme2"],
  "research_summary": "1 sentence"
}}

Spiral: 4=Blue/rules, 5=Orange/success, 6=Green/meaning, 7=Yellow/systems"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 400, "temperature": 0.3}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                match = re.search(r"\{.*\}", text, re.DOTALL)
                return json.loads(match.group()) if match else None
    except Exception as e:
        print(f"[Profiler] Analysis error: {e}")
        return None


async def _save(user_id: int, name: str, platform: str, profile: dict):
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/users/influencers/save",
                headers=HEADERS,
                json={"userId": user_id, "name": name, "platform": platform, "profile": profile},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        print(f"[Profiler] Saved: {name}")
    except:
        pass


async def derive_user_profile(user_id: int) -> dict | None:
    """Derive user profile from influencer constellation."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/users/{user_id}/influencers",
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                influencers = await r.json() if r.status == 200 else []
    except:
        return None

    if not influencers:
        return None

    total = sum(i.get("detection_count", 1) for i in influencers)
    summary = "\n".join([
        f"- {i['name']} ({i.get('detection_count',1)/total:.0%}): {i.get('core_philosophy','unknown')}"
        for i in sorted(influencers, key=lambda x: x.get("detection_count", 1), reverse=True)[:8]
    ])

    prompt = f"""Based on this influencer constellation, derive the user's profile.

{summary}

Reply ONLY valid JSON:
{{
  "derived_spiral_level": 5,
  "derived_spiral_label": "orange",
  "value_priorities": ["freedom", "success"],
  "worldview_summary": "2 sentences",
  "briefing_style": "metrics|meaning|systems|direct",
  "preferred_framing": "competitive|values|integral|anti-establishment",
  "resonant_language": ["execute", "leverage"],
  "language_to_avoid": ["perhaps", "diverse perspectives"]
}}"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 400, "temperature": 0.5}},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    profile = json.loads(match.group())
                    # Save derived profile
                    top5 = sorted(influencers, key=lambda x: x.get("detection_count", 1), reverse=True)[:5]
                    constellation = [{"name": i["name"], "weight": i.get("detection_count", 1)} for i in top5]

                    async with aiohttp.ClientSession() as s2:
                        await s2.patch(
                            f"{GORMERS_URL}/api/life/profile",
                            headers={**HEADERS, "x-internal-user-id": str(user_id)},
                            json={
                                "spiralLevel": profile.get("derived_spiral_level"),
                                "spiralLevelLabel": profile.get("derived_spiral_label"),
                                "briefingStyle": profile.get("briefing_style"),
                                "preferredFraming": profile.get("preferred_framing"),
                                "resonantLanguage": json.dumps(profile.get("resonant_language", [])),
                                "derivedWorldview": profile.get("worldview_summary"),
                                "influencerConstellation": json.dumps(constellation),
                                "profileSource": "influencer",
                            },
                            timeout=aiohttp.ClientTimeout(total=10),
                        )
                    print(f"[Profiler] User {user_id} profile derived from {len(influencers)} influencers")
                    return profile
    except Exception as e:
        print(f"[Profiler] Derivation error: {e}")
    return None


async def process_unresearched(user_id: int):
    """Research all unresearched influencers for a user."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/users/{user_id}/influencers?unresearched=1",
                headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                unresearched = await r.json() if r.status == 200 else []
    except:
        return

    for inf in unresearched[:5]:  # Max 5 per run
        await research_influencer(user_id, inf["name"], inf.get("platform", "unknown"))
        await asyncio.sleep(2)  # Rate limit

    # If we researched new ones, re-derive
    if unresearched:
        await derive_user_profile(user_id)
