"""
Mission Executor
================
Executes TCS missions autonomously. Phases:
  0. Briefing — Gorm reads and acknowledges TCS
  1. Research — autonomous web search, skill building
  2. Execute — attempt task, self-evaluate against standards, iterate
  3. Report — submit deliverable with standards check

STAGED: needs Ghengis + Ollama + MFYP_BRIDGE_SECRET.
"""

import asyncio
import json
import os
import re
import time

import aiohttp

from content_sanitizer import sanitize_for_llm
from signal_scorer import score_signal
from skill_manager import save_skill_entry

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma2:9b")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


class MissionExecutor:
    def __init__(self, mission: dict, gorm: dict, sops: list[dict]):
        self.mission = mission
        self.gorm = gorm
        self.sops = sops
        self.research_log: list[dict] = []
        self.attempt_log: list[dict] = []

    # ── Phase 0: Briefing ──

    async def brief(self):
        """Gorm confirms it understands the TCS."""
        prompt = f"""You are {self.gorm['name']}, a Gorm agent.

TASK: {self.mission['task']}
CONDITIONS: {self.mission['conditions']}
STANDARDS: {self.mission['standards']}
TIME: {self.mission.get('total_hours', 'unlimited')} hours

SOPs in effect:
{self._format_sops()}

Confirm you understand. Identify main challenges. State your approach.
Keep it brief — you're about to start."""

        response = await self._ask(prompt, 400)
        await self._telegram(f"◈ {self.gorm['name']} — MISSION BRIEFING\n\n{response}")
        await self._status("researching")

    # ── Phase 1: Research ──

    async def research(self):
        """Decompose task → search → score → save skill entries."""
        questions = await self._decompose()
        print(f"[Mission] {self.gorm['name']} researching {len(questions)} questions")

        for q in questions:
            results = await self._web_search(q)
            for result in results[:3]:
                url = result.get("url", "")
                if not url:
                    continue

                # Extract content
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers={"User-Agent": "GormersBot/1.0"},
                                               timeout=aiohttp.ClientTimeout(total=10)) as r:
                            html = await r.text()
                    # Simple extraction
                    title_match = re.search(r"<title[^>]*>([^<]+)", html, re.IGNORECASE)
                    title = title_match.group(1).strip() if title_match else url[:60]
                    desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
                    content = sanitize_for_llm(desc_match.group(1) if desc_match else title, 500)
                except Exception:
                    continue

                strength, claim, verified = await score_signal(
                    content=content,
                    domain=self.gorm.get("primaryDomain", "general"),
                    gorm_name=self.gorm["name"],
                    source_url=url,
                )

                if strength in ("HIGH", "MED"):
                    await save_skill_entry(
                        gorm_id=self.gorm["id"],
                        gorm_name=self.gorm["name"],
                        domain=self.gorm.get("primaryDomain", "general"),
                        claim=claim,
                        confidence=strength,
                        source_url=url,
                    )
                    self.research_log.append({
                        "query": q, "url": url, "finding": claim[:200],
                        "strength": strength, "ts": int(time.time() * 1000),
                    })
                    print(f"[Mission] {strength}: {claim[:80]}")

        await self._save_log("researchLog", self.research_log)

    async def _decompose(self) -> list[str]:
        prompt = f"""Task: "{self.mission['task']}"
Constraints: "{self.mission['conditions']}"

Generate 5-8 specific web search queries to research this task.
Reply ONLY a JSON array of strings."""

        resp = await self._ask(prompt, 300)
        try:
            match = re.search(r"\[.*?\]", resp, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return [line.strip("- ").strip() for line in resp.split("\n") if len(line.strip()) > 10][:8]

    async def _web_search(self, query: str) -> list[dict]:
        results = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                    headers={"User-Agent": "GormersBot/1.0"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    data = await r.json(content_type=None)
                    if data.get("AbstractURL"):
                        results.append({"url": data["AbstractURL"], "title": data.get("Heading", "")})
                    for topic in data.get("RelatedTopics", [])[:5]:
                        if isinstance(topic, dict) and topic.get("FirstURL"):
                            results.append({"url": topic["FirstURL"], "title": topic.get("Text", "")[:100]})
        except Exception as e:
            print(f"[Mission] Search error: {e}")

        # HN fallback
        if len(results) < 3:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://hn.algolia.com/api/v1/search",
                        params={"query": query, "tags": "story", "hitsPerPage": 3},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as r:
                        data = await r.json()
                        for hit in data.get("hits", []):
                            if hit.get("url"):
                                results.append({"url": hit["url"], "title": hit.get("title", "")})
            except Exception:
                pass
        return results[:5]

    # ── Phase 2: Execute ──

    async def execute(self):
        """Attempt task, self-evaluate, iterate up to 3 times."""
        for iteration in range(3):
            print(f"[Mission] {self.gorm['name']} — attempt {iteration + 1}")
            await self._status("executing", iteration=iteration)

            attempt = await self._attempt(iteration)
            evaluation = await self._evaluate(attempt)

            self.attempt_log.append({
                "iteration": iteration, "attempt_summary": str(attempt)[:500],
                "evaluation": evaluation, "ts": int(time.time() * 1000),
            })
            await self._save_log("attemptLog", self.attempt_log)

            if evaluation.get("meets_standards"):
                await self._submit(attempt, evaluation)
                return

            gaps = evaluation.get("gaps", "unknown")
            await self._telegram(
                f"◈ {self.gorm['name']} — ATTEMPT {iteration + 1}\n\n"
                f"Standards not fully met:\n{gaps}\n\nResearching gaps..."
            )
            for gap in evaluation.get("gap_list", [])[:3]:
                results = await self._web_search(f"how to fix: {gap}")
                for r in results[:2]:
                    if r.get("url"):
                        self.research_log.append({
                            "query": f"gap: {gap}", "url": r["url"],
                            "finding": r.get("title", "")[:100], "strength": "gap_research",
                            "ts": int(time.time() * 1000),
                        })

        await self._telegram(
            f"◈ {self.gorm['name']} — MISSION INCOMPLETE\n\n"
            f"3 attempts made. Standards not fully met.\n"
            f"Last gaps: {self.attempt_log[-1]['evaluation'].get('gaps', 'unknown')}\n\n"
            f"Awaiting direction."
        )
        await self._status("failed")

    async def _attempt(self, iteration: int) -> dict:
        skill_ctx = "\n".join([f"- {r['finding']}" for r in self.research_log[-10:]])
        prev = ""
        if self.attempt_log:
            prev = f"\nPREVIOUS GAPS: {self.attempt_log[-1]['evaluation'].get('gaps', '')}"

        prompt = f"""You are {self.gorm['name']}.

TASK: {self.mission['task']}
CONDITIONS: {self.mission['conditions']}
STANDARDS: {self.mission['standards']}
{prev}

KNOWLEDGE BUILT FROM RESEARCH:
{skill_ctx}

Attempt the task. Be specific and concrete. Generate the actual artifact/output."""

        response = await self._ask(prompt, 2000)

        # SOP check
        sop = self._check_sops(response)
        if sop:
            await self._telegram(
                f"⚠️ SOP TRIGGERED — {self.gorm['name']}\n\n"
                f"{sop['title']}: {sop['procedure'][:300]}"
            )
            await self._status("awaiting_approval", pending=sop["procedure"])
            return {"status": "awaiting_approval", "sop": sop["sop_id"]}

        return {"status": "attempted", "output": response, "iteration": iteration}

    async def _evaluate(self, attempt: dict) -> dict:
        if attempt.get("status") == "awaiting_approval":
            return {"meets_standards": False, "gaps": "Awaiting approval", "gap_list": []}

        prompt = f"""Evaluate your own work against these standards:

STANDARDS: {self.mission['standards']}

YOUR ATTEMPT:
{str(attempt.get('output', ''))[:1000]}

Reply JSON:
{{"meets_standards": true/false, "gaps": "what's missing", "gap_list": ["gap1", "gap2"]}}"""

        resp = await self._ask(prompt, 300)
        try:
            match = re.search(r"\{.*\}", resp, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"meets_standards": False, "gaps": resp[:200], "gap_list": [resp[:100]]}

    # ── Time Hacks + Spot Checks ──

    async def time_hack(self, hack: dict):
        research_summary = "\n".join([f"- {r['finding'][:80]}" for r in self.research_log[-5:]]) or "Gathering info"
        report = (
            f"◈ TIME HACK — Hour {hack.get('hours', '?')} — {self.gorm['name']}\n\n"
            f"TASK: {self.mission['task'][:80]}\n"
            f"STATUS: {self.mission.get('status', 'unknown')}\n"
            f"EXPECTED: {hack.get('deliverable', 'update')}\n\n"
            f"RESEARCH:\n{research_summary}\n\n"
            f"ATTEMPTS: {len(self.attempt_log)}\n"
            f"BLOCKERS: {'None' if self.mission.get('status') != 'awaiting_approval' else 'Awaiting approval'}"
        )
        await self._telegram(report)

    async def spot_check(self):
        await self.time_hack({"hours": "?", "deliverable": "Spot check"})

    # ── SOP Enforcement ──

    def _format_sops(self) -> str:
        return "\n".join([
            f"- [{s['title']}] Trigger: {s.get('trigger_text', '')[:80]}"
            for s in self.sops[:7]
        ])

    def _check_sops(self, content: str) -> dict | None:
        content_lower = content.lower()
        keywords = {
            "budget_constraint": ["buy", "purchase", "pay", "$", "cost", "price"],
            "download_approval": ["download", "install", "pip install", "npm install", "brew"],
            "account_creation": ["sign up", "register", "create account", "email address"],
        }
        for sop in sorted(self.sops, key=lambda s: s.get("priority", 5)):
            kws = keywords.get(sop.get("sop_id", ""), [])
            if any(kw in content_lower for kw in kws):
                return sop
        return None

    # ── Utilities ──

    async def _ask(self, prompt: str, max_tokens: int = 500) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                          "stream": False, "options": {"num_predict": max_tokens, "temperature": 0.7}},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as r:
                    data = await r.json()
                    return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"[Gemma unavailable: {e}]"

    async def _telegram(self, message: str):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{GORMERS_URL}/api/cron/telegram",
                    headers=HEADERS,
                    json={"chatId": str(self.gorm.get("userId", "")), "message": message,
                          "messageType": "alert", "priority": 3},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception:
            pass

    async def _status(self, status: str, iteration: int | None = None, pending: str | None = None):
        body: dict = {"status": status}
        if iteration is not None:
            body["iteration"] = iteration
        if pending:
            body["pendingApproval"] = pending
        try:
            async with aiohttp.ClientSession() as session:
                await session.patch(
                    f"{GORMERS_URL}/api/missions/{self.mission['id']}",
                    headers=HEADERS, json=body,
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception:
            pass

    async def _save_log(self, field: str, data: list):
        try:
            async with aiohttp.ClientSession() as session:
                await session.patch(
                    f"{GORMERS_URL}/api/missions/{self.mission['id']}",
                    headers=HEADERS, json={field: json.dumps(data)},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception:
            pass

    async def _submit(self, attempt: dict, evaluation: dict):
        checks = "\n".join([
            f"{'✓' if c.get('met') else '⚠'} {c.get('standard', '?')}: {c.get('reason', '')}"
            for c in evaluation.get("standard_checks", [])
        ]) or "All standards met."

        await self._telegram(
            f"◈ MISSION COMPLETE — {self.gorm['name']}\n\n"
            f"TASK: {self.mission['task']}\n\n"
            f"STANDARDS CHECK:\n{checks}\n\n"
            f"DELIVERABLE:\n{str(attempt.get('output', ''))[:500]}"
        )
        await self._status("complete")


# ── Runner (called from mfyp_orchestrator.py) ──

async def run_pending_missions():
    """Poll for pending missions and execute them."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GORMERS_URL}/api/missions/pending",
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as r:
                missions = await r.json() if r.status == 200 else []
    except Exception:
        return

    for data in missions:
        executor = MissionExecutor(data["mission"], data["gorm"], data["sops"])

        await executor.brief()
        await asyncio.sleep(5)
        await executor.research()

        # Schedule time hacks
        time_hacks = json.loads(data["mission"].get("time_hacks", "[]"))
        for hack in time_hacks:
            delay = float(hack.get("hours", 1)) * 3600
            asyncio.create_task(_delayed_hack(executor, hack, delay))

        await executor.execute()


async def _delayed_hack(executor: MissionExecutor, hack: dict, delay: float):
    await asyncio.sleep(delay)
    await executor.time_hack(hack)
