"""
Colony Workflow Executor — runs multi-Gorm workflows with dependencies.
"""

import asyncio
import json
import os
import time

import aiohttp

from mission_executor import MissionExecutor

GORMERS_URL = os.environ.get("GORMERS_URL", "https://gormers.com")
BRIDGE_SECRET = os.environ.get("MFYP_BRIDGE_SECRET", "")
HEADERS = {"x-gorm-secret": BRIDGE_SECRET, "Content-Type": "application/json"}


class ColonyWorkflowExecutor:
    def __init__(self, workflow: dict, gorms: dict, sops: list):
        self.workflow = workflow
        self.gorms = gorms  # {gorm_id: gorm_dict}
        self.sops = sops
        self.step_outputs: dict[str, dict] = {}
        self.step_statuses: dict[str, str] = {}

    async def execute(self):
        steps = self.workflow.get("steps", [])
        if not steps:
            return

        print(f"[Workflow] Starting: {self.workflow.get('name')} ({len(steps)} steps)")

        for step in steps:
            self.step_statuses[step["id"]] = "pending"

        remaining = list(steps)
        while remaining:
            ready = [s for s in remaining if all(
                self.step_statuses.get(d) == "complete" for d in s.get("depends_on", [])
            )]

            if not ready:
                print(f"[Workflow] Blocked: {[s['id'] for s in remaining]}")
                break

            await asyncio.gather(*[self._execute_step(s) for s in ready])
            remaining = [s for s in remaining if self.step_statuses.get(s["id"]) not in ("complete", "failed")]

        all_done = all(s == "complete" for s in self.step_statuses.values())
        await self._update_status("complete" if all_done else "failed")
        print(f"[Workflow] {'SUCCESS' if all_done else 'FAILED'}: {self.workflow.get('name')}")

    async def _execute_step(self, step: dict):
        gorm = self.gorms.get(step.get("gorm_id"))
        if not gorm:
            self.step_statuses[step["id"]] = "failed"
            return

        print(f"[Workflow] Step {step['id']}: {gorm['name']} → {step['task'][:60]}")
        self.step_statuses[step["id"]] = "running"

        step_mission = {
            "id": f"wf_{self.workflow['id']}_{step['id']}",
            "userId": self.workflow.get("userId"),
            "gormId": gorm.get("id"),
            "gormName": gorm.get("name"),
            "gormDomain": step.get("gorm_domain", gorm.get("primaryDomain", "general")),
            "task": step["task"],
            "conditions": "Standard operating conditions",
            "standards": "\n".join(step.get("standards", ["Complete the task"])),
        }

        executor = MissionExecutor(step_mission, gorm, self.sops)
        try:
            await executor.brief()
            await executor.research()
            await executor.execute()
            output = executor.attempt_log[-1] if executor.attempt_log else {}
            self.step_outputs[step["id"]] = {"output": str(output)[:500], "gorm_name": gorm["name"]}
            self.step_statuses[step["id"]] = "complete"
        except Exception as e:
            print(f"[Workflow] Step {step['id']} error: {e}")
            self.step_statuses[step["id"]] = "failed"

    async def _update_status(self, status: str):
        try:
            async with aiohttp.ClientSession() as session:
                await session.patch(
                    f"{GORMERS_URL}/api/workflows/{self.workflow.get('id', 0)}",
                    headers=HEADERS,
                    json={"status": status, "completedAt": int(time.time() * 1000)},
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except:
            pass
