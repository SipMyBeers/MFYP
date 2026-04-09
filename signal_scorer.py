"""
Signal Scorer
=============
Gemma 4 rates signals HIGH/MED/LOW with claim extraction.
Returns (strength, claim, is_source_verified) tuple.
"""

import json
import os
import aiohttp
from content_sanitizer import sanitize_for_llm, wrap_for_llm

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")


async def score_signal(
    content: str,
    domain: str,
    gorm_name: str,
    source_url: str = "",
    context_hint: str = "",
) -> tuple[str, str, bool]:
    """
    Score a signal using Gemma.
    Returns: (strength, claim, is_source_verified)
    - strength: 'HIGH' | 'MED' | 'LOW' | 'IGNORE'
    - claim: extracted insight in 15 words or less
    - is_source_verified: True if source_url is present
    """
    has_source = bool(source_url and source_url.startswith("http"))
    sanitized = sanitize_for_llm(content, 600)

    if not sanitized or len(sanitized) < 20:
        return ("IGNORE", "", has_source)

    # Quick keyword pre-filter — skip inference for obviously irrelevant content
    domain_words = domain.lower().split()
    content_lower = sanitized.lower()
    has_domain_signal = any(w in content_lower for w in domain_words if len(w) > 3)

    if not has_domain_signal and not context_hint:
        return ("LOW", sanitized[:80], has_source)

    prompt = f"""You are {gorm_name}, monitoring "{domain}".

{wrap_for_llm(sanitized, "SIGNAL_CONTENT")}

Source: {source_url or "unknown"}
{f"Context: {context_hint}" if context_hint else ""}

Rate this signal's relevance to {domain}. Reply ONLY with valid JSON:
{{"strength":"HIGH|MED|LOW|IGNORE","claim":"core insight in 15 words or null"}}

HIGH = directly relevant, significant, actionable
MED = relevant, worth tracking
LOW = tangentially related
IGNORE = not related to {domain}"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": 60, "temperature": 0.1},
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    return ("LOW", sanitized[:80], has_source)
                data = await r.json()
                text = data.get("message", {}).get("content", "")
                parsed = json.loads(text.replace("```json", "").replace("```", "").strip())
                strength = parsed.get("strength", "LOW")
                claim = parsed.get("claim") or sanitized[:80]
                if strength not in ("HIGH", "MED", "LOW", "IGNORE"):
                    strength = "LOW"
                return (strength, claim, has_source)
    except Exception as e:
        print(f"[Scorer] Error for {gorm_name}: {e}")
        # Fallback: keyword-based scoring
        if has_domain_signal:
            return ("MED", sanitized[:80], has_source)
        return ("LOW", sanitized[:80], has_source)


async def score_batch(
    items: list[dict],
    domain: str,
    gorm_name: str,
) -> list[tuple[str, str, bool]]:
    """Score multiple items. Returns list of (strength, claim, is_source_verified)."""
    results = []
    for item in items:
        result = await score_signal(
            content=item.get("content", item.get("title", "")),
            domain=domain,
            gorm_name=gorm_name,
            source_url=item.get("url", ""),
        )
        results.append(result)
    return results
