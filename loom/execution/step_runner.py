from __future__ import annotations

from typing import Any

from loom.models import MemoryType, TaskEvent


class StepRunner:
    def __init__(
        self,
        completion_evaluator,
        event_bus,
        agent_adapter=None,
        model_router=None,
        memory_service=None,
        memory_topology_service=None,
    ):
        self.completion_evaluator = completion_evaluator
        self.event_bus = event_bus
        self.agent_adapter = agent_adapter
        self.model_router = model_router
        self.memory_service = memory_service
        self.memory_topology_service = memory_topology_service

    def _resolve_memory_scopes(self, task, role_id: str) -> dict[str, list[dict]]:
        if not task.workflow_id or task.workflow_version is None:
            return {"read": [], "write": []}
        if self.memory_topology_service is None:
            scope = {
                "organization_id": task.organization_id,
                "domain_pack": task.domain_pack or "global",
                "workflow_id": task.workflow_id,
                "workflow_version": task.workflow_version,
                "role": role_id,
                "scope_id": role_id,
                "memory_group_id": f"private.{role_id}",
            }
            return {"read": [scope], "write": [scope]}
        return self.memory_topology_service.resolve_scopes(
            organization_id=task.organization_id,
            role_id=role_id,
            domain_pack=task.domain_pack or "global",
            workflow_id=task.workflow_id,
            workflow_version=task.workflow_version,
        )

    def _read_memory_slice(self, read_scopes: list[dict]) -> list[dict]:
        if self.memory_service is None:
            return []
        rows: list[dict] = []
        for scope in read_scopes:
            for item in self.memory_service.retrieve(scope, MemoryType.episodic, active_only=True):
                enriched = dict(item)
                enriched.setdefault("memory_group_id", scope.get("memory_group_id"))
                rows.append(enriched)
        rows.sort(key=lambda row: str(row.get("id", "")))
        return rows

    def _write_step_memory(self, task, step, participant, summary: str, write_scopes: list[dict]) -> None:
        if self.memory_service is None:
            return
        entry_id = f"{task.task_id}:{step.step_id}:{participant.role_id}"
        for scope in write_scopes:
            payload = {
                "id": entry_id,
                "task_id": task.task_id,
                "workflow_id": task.workflow_id,
                "workflow_version": task.workflow_version,
                "step_id": step.step_id,
                "role_id": participant.role_id,
                "memory_group_id": scope.get("memory_group_id"),
                "summary": summary,
            }
            self.memory_service.write(scope, MemoryType.episodic, payload)

    def _llm_execute(
        self,
        step,
        participant,
        task,
        memory_slice: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if self.agent_adapter is None:
            return "", {"ok": False, "error_code": "MODEL_ADAPTER_MISSING", "error": "model adapter unavailable"}

        routing = None
        if self.model_router is not None:
            routing = self.model_router.resolve(
                "step_execution",
                organization_id=task.organization_id,
                role_id=participant.role_id,
            )
        if routing is None:
            return (
                "",
                {
                    "ok": False,
                    "error_code": "MODEL_ROUTE_MISSING",
                    "error": "no model route configured for step execution",
                },
            )

        memory_slice = memory_slice or []
        memory_summary = "\n".join(
            f"- [{item.get('memory_group_id', 'unknown')}] {item.get('summary', '')}"
            for item in memory_slice[:5]
            if item.get("summary")
        )
        prompt = (
            f"Task: {task.raw_request}\n"
            f"Step: {step.title}\n"
            f"Role: {participant.role_id}\n"
            f"Memory Context:\n{memory_summary if memory_summary else '- none'}\n"
            "Return concise actionable output."
        )
        model = routing["model_name"] if routing else None
        base_url = routing["base_url"] if routing else None
        api_key = routing["api_key"] if routing else None

        result = self.agent_adapter.run(
            system_prompt=f"You are role {participant.role_id} in Loom workflow execution.",
            user_prompt=prompt,
            tools=[],
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
        if routing:
            result["routing"] = {k: v for k, v in routing.items() if k != "api_key"}
        return (result.get("output", "") if result.get("ok") else ""), result

    def run(self, task, step, participant):
        self.event_bus.emit(
            TaskEvent(task_id=task.task_id, event_type="step_entered", payload={"step": step.step_id})
        )

        scopes = self._resolve_memory_scopes(task, participant.role_id)
        memory_slice = self._read_memory_slice(scopes["read"])
        llm_text, llm_raw = self._llm_execute(step, participant, task, memory_slice=memory_slice)
        llm_ok = bool(llm_raw.get("ok"))
        if llm_ok:
            summary = llm_text or f"step {step.step_id} executed by {participant.role_id}"
        else:
            error_code = str(llm_raw.get("error_code", "STEP_EXECUTION_FAILED"))
            error_text = str(llm_raw.get("error", "step execution failed"))
            summary = f"{error_code}: {error_text}"
        self._write_step_memory(task, step, participant, summary, scopes["write"])
        output = {
            "participant_id": participant.participant_id,
            "role_id": participant.role_id,
            "step_id": step.step_id,
            "complete": llm_ok,
            "ok": llm_ok,
            "summary": summary,
            "model_output": llm_raw,
            "memory_scopes_written": scopes["write"],
        }
        completed = self.completion_evaluator.evaluate(step.completion, [output], context={})
        outcome = "success" if completed else "blocked"

        event_type = "step_completed" if outcome == "success" else "step_blocked"
        self.event_bus.emit(
            TaskEvent(
                task_id=task.task_id,
                event_type=event_type,
                payload={
                    "step": step.step_id,
                    "reason": None if outcome == "success" else llm_raw.get("error_code"),
                },
            )
        )

        return outcome, output
