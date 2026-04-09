"""
URL Discoverer
==============
Playwright-based adapter discovery for JS-heavy sites (Rumble, Odysee, etc.).
Runs on Ghengis. Saves discovered adapters platform-wide via /api/adapters/save.

STAGED: Needs `playwright install chromium` on Ghengis.
"""

import asyncio
import base64
import os

import aiohttp

from content_sanitizer import sanitize_for_llm

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.environ.get("VISION_MODEL", "llava")

CONTENT_SELECTORS = [
    '[data-testid="video-title"]',
    ".video-title", "#video-title",
    "h1.title", 'h1[class*="title"]',
    '[class*="description"]',
    ".post-content", "article",
    '[class*="content"]',
]


async def discover_with_playwright(url: str, domain: str, gorm_id: int | None = None) -> dict | None:
    """Use Playwright to discover how to extract content from a JS-heavy site."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Discoverer] Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    print(f"[Discoverer] Running Playwright discovery for {domain}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await page.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)

            title = await page.title()
            content = ""
            working_selectors = []

            for selector in CONTENT_SELECTORS:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        text = await el.inner_text()
                        if text and len(text) > 20:
                            content += text[:500] + "\n"
                            working_selectors.append(selector)
                except:
                    continue

            if not content:
                content = (await page.inner_text("body"))[:1000]

            # Check for paywall
            paywall_indicators = ["sign in", "log in", "subscribe", "create account", "premium"]
            is_paywall = any(ind in content.lower() for ind in paywall_indicators)

            adapter_type = "paywall" if is_paywall else "playwright_text"
            config = {
                "selectors": working_selectors,
                "notes": f"Discovered via Playwright{f' by Gorm #{gorm_id}' if gorm_id else ''}",
            }

            await save_adapter(domain, adapter_type, config, gorm_id)
            await browser.close()

            if is_paywall:
                return None

            return {
                "title": sanitize_for_llm(title, 200),
                "content": sanitize_for_llm(content.strip(), 2000),
                "adapter_used": adapter_type,
                "domain": domain,
            }

        except Exception as e:
            print(f"[Discoverer] Playwright failed for {domain}: {e}")
            await browser.close()
            return None


async def save_adapter(domain: str, adapter_type: str, config: dict, gorm_id: int | None = None):
    """Push discovered adapter to gormers.com."""
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{GORMERS_URL}/api/adapters/save",
                headers={"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"},
                json={
                    "domain": domain,
                    "adapterType": adapter_type,
                    "config": config,
                    "discoveredByGormId": gorm_id,
                },
                timeout=aiohttp.ClientTimeout(total=5),
            )
        print(f"[Discoverer] Saved {adapter_type} adapter for {domain}")
    except Exception as e:
        print(f"[Discoverer] Save failed: {e}")
