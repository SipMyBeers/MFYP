"""
Action Extractor
================
Runs after signal scoring. Asks Gemma 4: is there an executable strategy here?
If yes, generates a plan and submits to gormers.com for user approval.
"""

import json
import aiohttp
import os

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")

DOMAIN_TOOLS = {
    "law": ["wyoming_sos", "delaware_sos", "irs_ein", "courtlistener", "google_docs", "gmail"],
    "finance": ["sec_edgar", "mercury_bank", "google_docs", "google_calendar"],
    "startups": ["wyoming_sos", "delaware_sos", "irs_ein", "stripe", "google_docs", "gmail"],
    "patents": ["uspto", "google_docs"],
    "market": ["google_docs", "gmail"],
    "_default": ["google_docs", "gmail", "google_calendar"],
}


def get_available_tools(domain: str) -> list[str]:
    specific = DOMAIN_TOOLS.get(domain.lower(), [])
    defaults = DOMAIN_TOOLS["_default"]
    return list(set(specific + defaults))


async def extract_action(content: str, gorm: dict, source_url: str = "") -> dict | None:
    """
    Given HIGH-scored content, determine if there's an executable strategy.
    Returns a plan dict or None.
    """
    domain = gorm.get("primaryDomain", "general")
    gorm_name = gorm.get("name", "Gorm")
    available_tools = get_available_tools(domain)

    prompt = f"""You are {gorm_name}, an expert in {domain}.

You just watched this content:
"{content[:600]}"
Source: {source_url}

Your available tools: {", ".join(available_tools)}

Does this content contain an EXECUTABLE STRATEGY you could help implement?

Executable = concrete steps exist, you have tools for some steps, it's relevant to {domain}.

If YES, generate a plan. If NO, reply {{"executable": false}}.

Reply ONLY valid JSON:
{{
  "executable": true/false,
  "strategy": "one sentence",
  "steps": [
    {{
      "title": "Step title",
      "description": "What you'll do",
      "tool": "tool from your list, or 'research' or 'user_action'",
      "requiresHardStop": false,
      "isUserAction": false
    }}
  ],
  "requiredConnections": [
    {{"serviceId": "service_id", "reason": "why needed"}}
  ],
  "confidence": 0.0-1.0
}}

RULES:
- requiresHardStop: true for submit/pay/sign actions
- isUserAction: true for things ONLY the user can do (enter SSN, sign)
- Max 8 steps
- confidence < 0.7 = set executable to false"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 600, "temperature": 0.1},
                },
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                result = json.loads(text.replace("```json", "").replace("```", "").strip())

                if not result.get("executable") or result.get("confidence", 0) < 0.7:
                    return None
                return result
    except Exception as e:
        print(f"[ActionExtractor] Error: {e}")
        return None


async def submit_plan_to_gormers(gorm_id: int, plan: dict, trigger_summary: str, trigger_content_id: int | None = None):
    """Push an extracted plan to gormers.com for user approval."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{GORMERS_URL}/api/gorms/{gorm_id}/plans",
            headers={"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
            json={
                "strategy": plan["strategy"],
                "steps": plan["steps"],
                "requiredConnections": plan.get("requiredConnections", []),
                "triggerSummary": trigger_summary,
                "triggerContentId": trigger_content_id,
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status == 200:
                data = await r.json()
                print(f"[ActionExtractor] Plan submitted: {plan['strategy']} (planId: {data.get('planId')})")
                return data.get("planId")
            else:
                print(f"[ActionExtractor] Plan submission failed: {r.status}")
                return None
