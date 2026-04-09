"""
Gorm Executor
=============
Executes approved plans using Playwright + available tools.
Runs on Ghengis. Never executes without an approved plan.

Run: python3 gorm_executor.py
"""

import asyncio
import json
import os
import base64
from pathlib import Path
from email.mime.text import MIMEText

import aiohttp

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
SCREENSHOT_DIR = Path(os.path.expanduser("~/gormers-receipts"))
SCREENSHOT_DIR.mkdir(exist_ok=True)

HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


async def poll_and_execute():
    """Main executor loop. Polls for approved plans every 30 seconds."""
    print("[Executor] Starting Gorm Executor. Polling for approved plans...")

    while True:
        try:
            plans = await fetch_approved_plans()
            for plan in plans:
                await execute_plan(plan)
        except Exception as e:
            print(f"[Executor] Poll error: {e}")

        await asyncio.sleep(30)


async def fetch_approved_plans() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GORMERS_URL}/api/plans/approved",
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            return await r.json() if r.status == 200 else []


async def execute_plan(plan: dict):
    """Execute a single approved plan. One step at a time. Screenshot everything."""
    plan_id = plan["planId"]
    gorm_name = plan["gormName"]
    steps = plan["steps"]

    print(f"\n[Executor] {gorm_name} beginning plan: {plan['strategy']}")
    print(f"[Executor] {len(steps)} steps to execute")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[Executor] Playwright not installed. Run: pip install playwright && playwright install chromium")
        await report_step(plan_id, 1, "Setup", "system", "Playwright setup",
                          "Playwright not installed on this machine", None, True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        for i, step in enumerate(steps):
            step_num = i + 1
            title = step.get("title", f"Step {step_num}")
            tool = step.get("tool", "research")
            description = step.get("description", "")
            requires_hard_stop = step.get("requiresHardStop", False)
            is_user_action = step.get("isUserAction", False)

            print(f"\n[Executor] Step {step_num}/{len(steps)}: {title}")

            if is_user_action:
                await report_step(plan_id, step_num, title, "user_action", description,
                                  f"This step requires your direct action: {description}",
                                  None, True)
                break

            if requires_hard_stop:
                await report_step(plan_id, step_num, title, tool, description,
                                  f"Ready to {description}. Hard stop — approval needed.",
                                  None, True)
                break

            try:
                result_url = None
                result_summary = ""

                if tool == "google_docs":
                    result_url, result_summary = await execute_google_docs_step(plan, step)
                elif tool == "gmail":
                    result_url, result_summary = await execute_gmail_draft_step(plan, step)
                elif tool in ("wyoming_sos", "delaware_sos", "sec_edgar", "irs_ein",
                              "courtlistener", "uspto", "research", "web"):
                    result_url, result_summary = await execute_web_research_step(page, step, tool)
                else:
                    result_url, result_summary = await execute_web_research_step(page, step, "web")

                # Screenshot
                screenshot_path = SCREENSHOT_DIR / f"plan_{plan_id}_step_{step_num}.png"
                await page.screenshot(path=str(screenshot_path))

                await report_step(plan_id, step_num, title, tool, description,
                                  result_summary, result_url, False)
                print(f"[Executor] Step {step_num} complete: {result_summary[:80]}")
                await asyncio.sleep(2)

            except Exception as e:
                print(f"[Executor] Step {step_num} failed: {e}")
                await report_step(plan_id, step_num, title, tool, description,
                                  f"Step failed: {str(e)}", None, False)
                break

        await browser.close()

    await mark_plan_complete(plan_id)
    print(f"\n[Executor] {gorm_name} plan complete: {plan['strategy']}")


TOOL_URLS = {
    "wyoming_sos": "https://wyobiz.wyo.gov/Business/FilingSearch.aspx",
    "delaware_sos": "https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx",
    "sec_edgar": "https://efts.sec.gov/LATEST/search-index?q={query}",
    "irs_ein": "https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online",
    "courtlistener": "https://www.courtlistener.com/?q={query}",
    "uspto": "https://ppubs.uspto.gov/pubwebapp/static/pages/searchable-indexes.html",
}


async def execute_web_research_step(page, step: dict, tool: str) -> tuple[str | None, str]:
    """Use Playwright to research on public web services."""
    query = step.get("searchQuery", step.get("description", ""))
    base_url = TOOL_URLS.get(tool, f"https://www.google.com/search?q={query}")
    if "{query}" in base_url:
        from urllib.parse import quote
        base_url = base_url.replace("{query}", quote(query[:100]))

    await page.goto(base_url, timeout=15000)
    await page.wait_for_load_state("networkidle", timeout=10000)

    content = await page.inner_text("body")
    summary = content[:300].strip().replace("\n", " ")

    return page.url, f"Researched {tool}: {summary[:200]}"


async def execute_google_docs_step(plan: dict, step: dict) -> tuple[str | None, str]:
    """Create a Google Doc via API."""
    token = _find_token(plan, "google_docs")
    if not token:
        return None, "Google Docs not connected"

    title = f"{plan['gormName']} — {step['title']}"
    content = step.get("documentContent", step["description"])

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://docs.googleapis.com/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": title},
        ) as r:
            if r.status != 200:
                return None, f"Failed to create doc: {r.status}"
            doc = await r.json()
            doc_id = doc["documentId"]

        await session.post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            headers={"Authorization": f"Bearer {token}"},
            json={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        )

    return f"https://docs.google.com/document/d/{doc_id}/edit", f"Created Google Doc: {title}"


async def execute_gmail_draft_step(plan: dict, step: dict) -> tuple[str | None, str]:
    """Create a Gmail draft — never sends."""
    token = _find_token(plan, "gmail")
    if not token:
        return None, "Gmail not connected"

    subject = step.get("emailSubject", f"{plan['gormName']} — {step['title']}")
    body = step.get("emailBody", step["description"])
    to = step.get("emailTo", "")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["To"] = to
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": {"raw": raw}},
        ) as r:
            if r.status == 200:
                data = await r.json()
                return f"https://mail.google.com/mail/#drafts/{data.get('id', '')}", f"Draft created: {subject}"
            return None, f"Failed to create draft: {r.status}"


def _find_token(plan: dict, service_id: str) -> str | None:
    for conn in plan.get("availableConnections", []):
        if conn["serviceId"] == service_id:
            return conn.get("encryptedToken")
    return None


async def report_step(plan_id: int, step_num: int, title: str, tool: str,
                      description: str, result_summary: str,
                      result_url: str | None, requires_hard_stop: bool):
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{GORMERS_URL}/api/plans/{plan_id}/step-complete",
            headers=HEADERS,
            json={
                "stepNum": step_num,
                "stepTitle": title,
                "tool": tool,
                "actionDescription": description,
                "resultSummary": result_summary,
                "resultUrl": result_url,
                "requiresHardStop": requires_hard_stop,
            },
            timeout=aiohttp.ClientTimeout(total=10),
        )


async def mark_plan_complete(plan_id: int):
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{GORMERS_URL}/api/plans/{plan_id}/complete",
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=5),
        )


if __name__ == "__main__":
    asyncio.run(poll_and_execute())
