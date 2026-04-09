"""
Inference Router — routes to local Ollama or cloud based on model requirements.
"""

import os
import aiohttp

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
CLOUD_URL = os.environ.get("CLOUD_INFERENCE_URL", "https://gormers.com/api/inference")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")

MODEL_REQUIREMENTS = {
    "gemma2:9b":    {"ram_gb": 8,  "tier": "any"},
    "gemma2:27b":   {"ram_gb": 16, "tier": "ghengis"},
    "llama3:70b":   {"ram_gb": 48, "tier": "gpu"},
    "mixtral:8x7b": {"ram_gb": 48, "tier": "gpu"},
}

_capability_cache: dict | None = None


async def detect_capability() -> dict:
    global _capability_cache
    if _capability_cache:
        return _capability_cache

    import platform
    try:
        import psutil
        ram = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        ram = 16  # assume reasonable default

    models = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_BASE}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
                models = [m["name"] for m in data.get("models", [])]
    except:
        pass

    _capability_cache = {
        "ram_gb": ram,
        "is_apple_silicon": platform.machine() == "arm64" and platform.system() == "Darwin",
        "available_models": models,
        "tier": "ghengis" if ram >= 16 else "any",
    }
    return _capability_cache


async def route_inference(prompt: str, model: str = "gemma2:9b", max_tokens: int = 500,
                          user_id: int = 0, gorm_id: int = 0) -> str:
    """Route to local or cloud based on capability."""
    cap = await detect_capability()
    req = MODEL_REQUIREMENTS.get(model, MODEL_REQUIREMENTS["gemma2:9b"])

    can_local = model in cap["available_models"] and cap["ram_gb"] >= req["ram_gb"]

    if can_local:
        return await _local(prompt, model, max_tokens)
    else:
        return await _cloud(prompt, model, user_id, gorm_id, max_tokens)


async def _local(prompt: str, model: str, max_tokens: int) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "stream": False, "options": {"num_predict": max_tokens, "temperature": 0.7}},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as r:
                data = await r.json()
                return data.get("message", {}).get("content", "")
    except Exception as e:
        print(f"[InferenceRouter] Local error: {e}")
        return ""


async def _cloud(prompt: str, model: str, user_id: int, gorm_id: int, max_tokens: int) -> str:
    """Cloud fallback — $0.03/call."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CLOUD_URL}/generate",
                headers={"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
                json={"userId": user_id, "gormId": gorm_id, "model": model,
                      "prompt": prompt, "maxTokens": max_tokens},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as r:
                data = await r.json()
                return data.get("content", "")
    except Exception as e:
        print(f"[InferenceRouter] Cloud error: {e}")
        return ""
