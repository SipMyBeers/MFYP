"""
Skill Manager
=============
Manages skill file creation with auto-generated trigger_context + cluster_tag.
Checks GormHub thresholds after every N entries.
"""

import json
import os
import re

import aiohttp

from content_sanitizer import sanitize_for_llm

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")

HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}

GORMHUB_MIN_ENTRIES = 50
GORMHUB_MIN_CONFIDENCE = 0.75
GORMHUB_CHECK_EVERY = 10


async def save_skill_entry(
    gorm_id: int,
    gorm_name: str,
    domain: str,
    claim: str,
    confidence: str,
    source_url: str = "",
) -> dict | None:
    """Save a skill entry with auto-generated trigger_context + cluster_tag."""

    trigger = await generate_trigger_context(claim, domain, gorm_name)
    cluster = await generate_cluster_tag(claim, domain)

    # Auto tier based on confidence
    tier = 1 if confidence == "HIGH" else 2 if confidence == "MED" else 3

    payload = {
        "claim": sanitize_for_llm(claim, 300),
        "confidence": confidence,
        "triggerContext": trigger,
        "importanceTier": tier,
        "clusterTag": cluster,
        "sourceUrl": source_url,
        "subdomain": cluster,
        "inferenceFlag": 0 if source_url else 1,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{GORMERS_URL}/api/gorms/{gorm_id}/skills",
            headers=HEADERS,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status == 200:
                data = await r.json()
                count = data.get("totalEntries", 0)
                print(f"[Skills] {gorm_name}: '{claim[:60]}' (tier {tier}, cluster: {cluster})")

                if count % GORMHUB_CHECK_EVERY == 0:
                    await check_gormhub_threshold(gorm_id, gorm_name, domain)

                return data
            else:
                print(f"[Skills] Failed to save: {r.status}")
                return None


async def generate_trigger_context(claim: str, domain: str, gorm_name: str) -> str:
    """Generate a 'when reasoning about...' trigger phrase."""
    prompt = f"""Knowledge learned by {gorm_name} ({domain} expert):
"{claim[:200]}"

Write a trigger in under 20 words starting with "when reasoning about":
Describe when this knowledge is relevant.
Reply with ONLY the trigger phrase."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 40, "temperature": 0.1},
                },
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                data = await r.json()
                trigger = data.get("message", {}).get("content", "").strip()
                if not trigger.lower().startswith("when"):
                    trigger = "when reasoning about " + trigger
                return trigger[:150]
    except:
        return f"when reasoning about {domain} topics"


async def generate_cluster_tag(claim: str, domain: str) -> str:
    """Generate a hyphenated cluster tag for grouping."""
    prompt = f"""Domain: {domain}
Claim: "{claim[:150]}"

Generate a 2-4 word hyphenated cluster tag. Lowercase.
Reply with ONLY the tag.
Examples: wyoming-llc, sec-8k-filings, ebay-resale-pricing"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 15, "temperature": 0.1},
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                data = await r.json()
                tag = data.get("message", {}).get("content", "").strip().lower()
                tag = re.sub(r"[^a-z0-9\-]", "", tag).strip("-")
                return tag[:50] or domain.replace(" ", "-").lower()[:50]
    except:
        return domain.replace(" ", "-").lower()[:50]


async def check_gormhub_threshold(gorm_id: int, gorm_name: str, domain: str):
    """Check if any cluster hit GormHub proposal threshold."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GORMERS_URL}/api/gorms/{gorm_id}/skill-clusters",
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as r:
            if r.status != 200:
                return
            clusters = await r.json()

    for cluster in clusters:
        if (cluster["entry_count"] >= GORMHUB_MIN_ENTRIES
                and cluster["avg_confidence"] >= GORMHUB_MIN_CONFIDENCE
                and not cluster.get("hub_proposed")):

            description = await generate_gormhub_description(gorm_name, domain, cluster)

            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{GORMERS_URL}/api/gormhub/propose",
                    headers=HEADERS,
                    json={
                        "gormId": gorm_id,
                        "clusterTag": cluster["tag"],
                        "title": cluster["suggested_title"],
                        "description": description,
                        "domain": domain,
                        "entryCount": cluster["entry_count"],
                        "avgConfidence": cluster["avg_confidence"],
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                )
            print(f"[GormHub] {gorm_name} proposed: {cluster['tag']}")


async def generate_gormhub_description(gorm_name: str, domain: str, cluster: dict) -> str:
    """Gorm writes its own skill pack description."""
    samples = "\n".join(f"- {c}" for c in cluster.get("sample_claims", [])[:5])

    prompt = f"""You are {gorm_name}, a {domain} specialist.
You have {cluster['entry_count']} knowledge entries in "{cluster['tag']}".

Sample knowledge:
{samples}

Write a 2-3 sentence description of this skill pack for other Gorms.
Your voice. Specific. Under 60 words. Don't start with "I"."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 100, "temperature": 0.7},
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "").strip()
    except:
        return f"{cluster['entry_count']} entries on {cluster['tag']} in {domain}. Avg confidence: {cluster['avg_confidence']:.0%}."
