"""
AI Chatlog Importer — seeds Gorm knowledge from conversation history.
Privacy: raw content processed locally on Ghengis. Only patterns sent to platform.
"""

import asyncio
import json
import os

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


async def import_chatgpt_history(user_id: int, export_path: str) -> dict:
    """Process ChatGPT conversations.json. Raw content stays local."""
    print(f"[ChatlogImport] Processing: {export_path}")

    with open(export_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    conversations = raw if isinstance(raw, list) else raw.get("conversations", [])
    print(f"[ChatlogImport] Found {len(conversations)} conversations")

    # Extract user messages
    messages = []
    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        mapping = conv.get("mapping", {})
        for node in mapping.values():
            msg = node.get("message")
            if msg and msg.get("author", {}).get("role") == "user":
                content = msg.get("content", {})
                text = ""
                if isinstance(content, dict):
                    parts = content.get("parts", [])
                    text = " ".join(p for p in parts if isinstance(p, str))
                elif isinstance(content, str):
                    text = content
                if text.strip():
                    messages.append(text.strip())

    if not messages:
        return {"error": "No user messages found"}

    print(f"[ChatlogImport] Extracted {len(messages)} user messages")

    # Sample for analysis
    step = max(1, len(messages) // 200)
    sample = messages[::step][:100]
    combined = "\n---\n".join(sample)

    # Extract insights via Gemma (LOCAL — raw never leaves)
    insights = await _extract_insights(combined, len(messages))
    if not insights:
        return {"error": "Extraction failed"}

    # Send insights (not raw) to platform
    result = await _send_insights(user_id, insights, len(conversations))
    print(f"[ChatlogImport] Done: {result}")
    return result


async def _extract_insights(sample: str, total: int) -> dict | None:
    prompt = f"""Analyze {total} AI conversation samples from one person.
Extract patterns WITHOUT quoting private content.

SAMPLE (local only):
{sample[:4000]}

Reply JSON:
{{
  "primary_domains": [{{"domain":"...", "frequency":"high|med", "depth":"expert|intermediate", "suggested_gorm_biome":"signal|scholar|craft|void", "suggested_gorm_name":"Fiuto|Lumin|etc"}}],
  "communication_style": {{"question_type":"specific|broad", "depth_preference":"deep|practical", "preferred_format":"bullets|prose", "tone":"formal|casual|technical"}},
  "active_challenges": ["recurring unsolved problem"],
  "unresolved_questions": ["topic they kept returning to"],
  "skill_seeds": [{{"claim":"factual claim discussed", "domain":"domain", "confidence":0.7}}],
  "worldview_signals": ["repeated belief or value"],
  "resonant_language": ["frequently used terms"]
}}
Max 5 primary_domains, 5 skill_seeds, 3 challenges."""

    try:
        import re
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": 600, "temperature": 0.3}},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                match = re.search(r"\{.*\}", text, re.DOTALL)
                return json.loads(match.group()) if match else None
    except Exception as e:
        print(f"[ChatlogImport] Extraction error: {e}")
        return None


async def _send_insights(user_id: int, insights: dict, conv_count: int) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{GORMERS_URL}/api/users/{user_id}/chatlog-import",
                headers=HEADERS,
                json={
                    "conversationCount": conv_count,
                    "primaryDomains": insights.get("primary_domains", []),
                    "communicationStyle": insights.get("communication_style", {}),
                    "activeChallenges": insights.get("active_challenges", []),
                    "unresolvedQuestions": insights.get("unresolved_questions", []),
                    "skillSeeds": insights.get("skill_seeds", []),
                    "worldviewSignals": insights.get("worldview_signals", []),
                    "resonantLanguage": insights.get("resonant_language", []),
                    "source": "chatgpt_export",
                    "processedLocally": True,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                return await r.json() if r.status == 200 else {"error": r.status}
    except Exception as e:
        return {"error": str(e)}
