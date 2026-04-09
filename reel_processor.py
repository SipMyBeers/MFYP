"""
Reel Processor
==============
Full video/reel ingestion pipeline on Ghengis.
Layers: metadata + Whisper transcript + vision description + comments.
"""

import asyncio
import base64
import os
import re
import time
import tempfile
from pathlib import Path

import aiohttp

from content_sanitizer import sanitize_for_llm

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.environ.get("VISION_MODEL", "llava")
MAX_VIDEO_DURATION = 180  # 3 min max
TEMP_DIR = Path(tempfile.gettempdir()) / "gormers_reels"
TEMP_DIR.mkdir(exist_ok=True)


class ReelProcessor:
    def __init__(self):
        self._whisper_model = None

    def get_whisper(self):
        if self._whisper_model is None:
            import whisper
            print(f"[ReelProcessor] Loading Whisper {WHISPER_MODEL}...")
            self._whisper_model = whisper.load_model(WHISPER_MODEL)
        return self._whisper_model

    async def process(self, url: str, content_type: str) -> dict:
        """Main entry. Returns structured content dict with all layers."""
        print(f"[ReelProcessor] Processing {content_type}: {url[:60]}")
        start = time.time()

        result = {"url": url, "content_type": content_type, "layers": {}, "combined_content": "", "processing_time_secs": 0}

        # Layer 1: Metadata
        result["layers"]["metadata"] = await self._extract_metadata(url)

        # Layer 2: Whisper transcript
        transcript = await self._extract_transcript(url)
        if transcript:
            result["layers"]["transcript"] = transcript

        # Layer 3: Vision description
        visual = await self._describe_visual(url)
        if visual:
            result["layers"]["visual"] = visual

        # Layer 4: YouTube comments
        if content_type == "youtube":
            comments = await self._youtube_comments(url)
            if comments:
                result["layers"]["comments"] = comments

        result["combined_content"] = self._combine_layers(result["layers"])
        result["processing_time_secs"] = round(time.time() - start, 1)
        print(f"[ReelProcessor] Done in {result['processing_time_secs']}s — {len(result['combined_content'])} chars")
        return result

    async def _extract_metadata(self, url: str) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": "GormersBot/1.0"},
                                       timeout=aiohttp.ClientTimeout(total=10)) as r:
                    html = await r.text()

            def meta(prop):
                for pat in [
                    rf'<meta[^>]+(?:property|name)=["\'](?:og:|twitter:)?{re.escape(prop)}["\'][^>]+content=["\'](.*?)["\']',
                    rf'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:property|name)=["\'](?:og:|twitter:)?{re.escape(prop)}["\']',
                ]:
                    m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
                    if m:
                        return m.group(1).strip()
                return ""

            title = meta("title") or (re.search(r"<title[^>]*>([^<]+)", html, re.IGNORECASE) or [None, ""])[1]
            description = meta("description")
            thumbnail = meta("image")
            hashtags = list(set(re.findall(r"#([a-zA-Z0-9_]+)", (description or "") + " " + (title or ""))))[:20]

            creator = ""
            m = re.search(r"tiktok\.com/@([a-zA-Z0-9_.]+)", url)
            if m:
                creator = f"@{m.group(1)}"
            else:
                m = re.search(r"instagram\.com/(?:reel/)?([^/?]+)", url)
                if m and m.group(1) not in ("reel", "p", "tv"):
                    creator = f"@{m.group(1)}"

            return {
                "title": sanitize_for_llm(str(title or ""), 200),
                "description": sanitize_for_llm(description, 500),
                "creator": creator,
                "hashtags": hashtags,
                "thumbnail_url": thumbnail,
            }
        except Exception as e:
            print(f"[ReelProcessor] Metadata error: {e}")
            return {}

    async def _extract_transcript(self, url: str) -> dict | None:
        audio_path = TEMP_DIR / f"audio_{hash(url) & 0xFFFF}.m4a"
        try:
            # Check duration
            duration = await self._get_duration(url)
            if duration and duration > MAX_VIDEO_DURATION:
                print(f"[ReelProcessor] Skipping transcript — too long ({duration}s)")
                return None

            # Download audio only
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp", "--format", "bestaudio[ext=m4a]/bestaudio",
                "--output", str(audio_path), "--no-playlist", "--quiet", "--no-warnings",
                "--socket-timeout", "30", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            if proc.returncode != 0 or not audio_path.exists():
                print(f"[ReelProcessor] yt-dlp failed: {stderr.decode()[:200]}")
                return None

            # Whisper transcribe
            model = self.get_whisper()
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: model.transcribe(str(audio_path), language=None, task="transcribe")
            )
            text = result.get("text", "").strip()
            if not text:
                return None

            return {"text": sanitize_for_llm(text, 3000), "language": result.get("language", "unknown"), "duration_secs": duration}

        except asyncio.TimeoutError:
            print(f"[ReelProcessor] Transcript timeout")
            return None
        except Exception as e:
            print(f"[ReelProcessor] Transcript error: {e}")
            return None
        finally:
            if audio_path.exists():
                audio_path.unlink()

    async def _get_duration(self, url: str) -> float | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp", "--get-duration", "--no-playlist", "--quiet", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            s = stdout.decode().strip()
            if ":" in s:
                parts = s.split(":")
                return sum(int(p) * (60 ** i) for i, p in enumerate(reversed(parts)))
        except:
            pass
        return None

    async def _describe_visual(self, url: str) -> dict | None:
        # Check vision model availability
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{OLLAMA_BASE}/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as r:
                    if r.status != 200:
                        return None
                    models = await r.json()
                    names = [m["name"] for m in models.get("models", [])]
                    if not any(vm in n for n in names for vm in ["llava", "bakllava", "moondream", "gemma3"]):
                        return None
        except:
            return None

        # Get thumbnail
        thumbnail_url = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp", "--get-thumbnail", "--no-playlist", "--quiet", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            thumbnail_url = stdout.decode().strip()
        except:
            pass
        if not thumbnail_url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(thumbnail_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    img_b64 = base64.b64encode(await r.read()).decode()

                async with session.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={
                        "model": VISION_MODEL,
                        "prompt": "Describe this video thumbnail concisely (under 150 words). What is shown, any text, the main topic.",
                        "images": [img_b64],
                        "stream": False,
                        "options": {"num_predict": 200},
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        return {"description": sanitize_for_llm(data.get("response", "").strip(), 500)}
        except Exception as e:
            print(f"[ReelProcessor] Vision error: {e}")
        return None

    async def _youtube_comments(self, url: str) -> dict | None:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            return None

        vid_match = re.search(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})", url)
        if not vid_match:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.googleapis.com/youtube/v3/commentThreads",
                    params={"part": "snippet", "videoId": vid_match.group(1), "maxResults": 20, "order": "relevance", "key": api_key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    if r.status != 200:
                        return None
                    data = await r.json()

            comments = []
            for item in data.get("items", []):
                s = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                text = s.get("textDisplay", "")
                if text and len(text) > 10:
                    comments.append({"text": sanitize_for_llm(text, 200), "likes": s.get("likeCount", 0)})
            comments.sort(key=lambda c: c["likes"], reverse=True)
            return {"comments": comments[:5]}
        except Exception as e:
            print(f"[ReelProcessor] Comments error: {e}")
            return None

    def _combine_layers(self, layers: dict) -> str:
        parts = []
        if meta := layers.get("metadata"):
            if meta.get("title"):
                parts.append(f"Title: {meta['title']}")
            if meta.get("creator"):
                parts.append(f"Creator: {meta['creator']}")
            if meta.get("description"):
                parts.append(f"Description: {meta['description']}")
            if meta.get("hashtags"):
                parts.append(f"Tags: {' '.join('#' + t for t in meta['hashtags'][:10])}")
        if visual := layers.get("visual"):
            if visual.get("description"):
                parts.append(f"Visual: {visual['description']}")
        if transcript := layers.get("transcript"):
            if transcript.get("text"):
                parts.append(f"Transcript: {transcript['text'][:1500]}")
        if comments := layers.get("comments"):
            if cl := comments.get("comments"):
                parts.append(f"Top comments: {' | '.join(c['text'] for c in cl[:3])}")
        return "\n\n".join(parts)


reel_processor = ReelProcessor()
