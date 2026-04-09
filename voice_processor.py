"""
Voice Processor
===============
VibeVoice-ASR transcription + TTS for Telegram voice messages.
STAGED: needs VibeVoice installed on Ghengis.
"""

import asyncio
import os
import tempfile

import aiohttp

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
VIBEVOICE_ENABLED = os.environ.get("VIBEVOICE_TTS_ENABLED", "false") == "true"

BIOME_VOICES = {
    "signal": "Emma", "scholar": "Frank", "craft": "Alice",
    "void": "Adam", "special": "Josh",
}


async def transcribe_telegram_voice(file_id: str) -> str:
    """Download Telegram voice message and transcribe."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile",
            params={"file_id": file_id},
        ) as r:
            data = await r.json()
            file_path = data["result"]["file_path"]

        async with session.get(
            f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        ) as r:
            audio_data = await r.read()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_data)
        temp_path = f.name

    try:
        return await _run_asr(temp_path)
    finally:
        os.unlink(temp_path)


async def _run_asr(audio_path: str) -> str:
    loop = asyncio.get_event_loop()

    def _transcribe():
        from transformers import pipeline
        asr = pipeline("automatic-speech-recognition", model="microsoft/VibeVoice-ASR")
        gorm_hotwords = ["Fiuto", "Lumin", "Ponda", "Suro", "Wex", "Gormers", "WARNO", "OPORD", "spotcheck"]
        result = asr(audio_path, generate_kwargs={"hotwords": gorm_hotwords})
        return result["text"].strip()

    return await loop.run_in_executor(None, _transcribe)


async def generate_voice_reply(text: str, gorm_biome: str = "signal", gorm_name: str = "Gorm") -> bytes | None:
    """Generate TTS voice note. Returns OGG bytes or None."""
    if not VIBEVOICE_ENABLED:
        return None

    speaker = BIOME_VOICES.get(gorm_biome, "Emma")
    try:
        import subprocess
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(text)
            txt_path = f.name
        out_path = txt_path.replace(".txt", ".wav")
        ogg_path = txt_path.replace(".txt", ".ogg")

        subprocess.run([
            "python", "demo/streaming_inference_from_file.py",
            "--model_path", "microsoft/VibeVoice-Realtime-0.5B",
            "--txt_path", txt_path, "--speaker_name", speaker, "--output_path", out_path,
        ], cwd=os.path.expanduser("~/VibeVoice"), capture_output=True, timeout=30)

        subprocess.run(["ffmpeg", "-i", out_path, "-c:a", "libopus", ogg_path, "-y"],
                       capture_output=True, timeout=15)

        with open(ogg_path, "rb") as f:
            audio = f.read()

        for p in [txt_path, out_path, ogg_path]:
            try: os.unlink(p)
            except: pass

        return audio
    except Exception as e:
        print(f"[Voice] TTS error: {e}")
        return None


async def send_voice_to_telegram(chat_id: str, audio_bytes: bytes, caption: str = ""):
    """Send voice note to Telegram."""
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field("chat_id", chat_id)
        form.add_field("voice", audio_bytes, filename="voice.ogg", content_type="audio/ogg")
        if caption:
            form.add_field("caption", caption)
        await session.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice", data=form)
