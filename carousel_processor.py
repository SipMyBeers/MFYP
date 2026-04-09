"""
Carousel Processor
==================
Processes Instagram/TikTok multi-slide posts.
Each slide gets vision-described individually. Narrative preserved.
Runs on Ghengis via Playwright.
"""

import asyncio
import base64
import os
import re

import aiohttp

from content_sanitizer import sanitize_for_llm

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.environ.get("VISION_MODEL", "llava")


async def process_carousel(url: str, metadata: dict) -> dict:
    """Process a carousel post. Extract and describe each slide."""
    print(f"[Carousel] Processing: {url[:60]}")

    slides = await extract_carousel_slides(url)
    if not slides:
        return {"slide_count": 1, "narrative": metadata.get("description", ""), "slides": []}

    print(f"[Carousel] Found {len(slides)} slides")

    described = []
    for i, slide in enumerate(slides):
        desc = await describe_slide(slide, i + 1, len(slides))
        described.append({"slide_num": i + 1, "description": desc})

    narrative = build_narrative(described, metadata)
    return {"slide_count": len(slides), "narrative": narrative, "slides": described}


async def extract_carousel_slides(url: str) -> list[dict] | None:
    """Use Playwright to capture each carousel slide."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Carousel] Playwright not installed")
        return None

    slides = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_context(
            viewport={"width": 1080, "height": 1080},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        ).then(lambda c: c.new_page()) if False else await (await browser.new_context(
            viewport={"width": 1080, "height": 1080},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        )).new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(2)

            is_instagram = "instagram.com" in url

            for i in range(10):  # Max 10 slides
                # Screenshot current
                screenshot = await page.screenshot(type="jpeg", quality=80)
                slides.append({"screenshot_b64": base64.b64encode(screenshot).decode()})

                # Try next button
                next_selectors = (
                    ['button[aria-label="Next"]', '[class*="next"]', '[class*="coreSpriteRightChevron"]']
                    if is_instagram
                    else ['[class*="arrow-right"]', '[class*="next"]', '[data-e2e="arrow-right"]']
                )

                clicked = False
                for sel in next_selectors:
                    try:
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(0.8)
                            clicked = True
                            break
                    except:
                        continue
                if not clicked:
                    break

        except Exception as e:
            print(f"[Carousel] Playwright error: {e}")
        finally:
            await browser.close()

    return slides if slides else None


async def describe_slide(slide: dict, num: int, total: int) -> str:
    """Vision model describes one slide."""
    if not slide.get("screenshot_b64"):
        return f"Slide {num}: [no image]"

    prompt = f"This is slide {num} of {total} in a carousel. Describe what you see in under 100 words: visible text, subject matter, main message."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE}/api/generate",
                json={
                    "model": VISION_MODEL,
                    "prompt": prompt,
                    "images": [slide["screenshot_b64"]],
                    "stream": False,
                    "options": {"num_predict": 150},
                },
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return sanitize_for_llm(data.get("response", "").strip(), 300)
    except Exception as e:
        print(f"[Carousel] Vision error slide {num}: {e}")

    return f"Slide {num}: [vision unavailable]"


def build_narrative(slides: list[dict], metadata: dict) -> str:
    """Combine slide descriptions into narrative for scoring."""
    parts = []
    if caption := metadata.get("description"):
        parts.append(f"Caption: {caption[:300]}")
    parts.append(f"Carousel ({len(slides)} slides):")
    for s in slides:
        parts.append(f"  Slide {s['slide_num']}: {s['description']}")
    return "\n".join(parts)
