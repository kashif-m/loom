from __future__ import annotations

from typing import Any

from loom.models import TaskEvent


class StepRunner:
    def __init__(self, completion_evaluator, event_bus, agent_adapter=None, model_router=None):
        self.completion_evaluator = completion_evaluator
        self.event_bus = event_bus
        self.agent_adapter = agent_adapter
        self.model_router = model_router

    def _llm_execute(self, step, participant, task) -> tuple[str, dict[str, Any]]:
        if self.agent_adapter is None:
            return "", {}

        routing = None
        if self.model_router is not None:
            routing = self.model_router.resolve("step_execution")

        prompt = (
            f"Task: {task.raw_request}\n"
            f"Step: {step.title}\n"
            f"Role: {participant.role_id}\n"
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
        return result.get("output", ""), result

    def run(self, task, step, participant):
        self.event_bus.emit(
            TaskEvent(task_id=task.task_id, event_type="step_entered", payload={"step": step.step_id})
        )

        llm_text, llm_raw = self._llm_execute(step, participant, task)
        output = {
            "participant_id": participant.participant_id,
            "role_id": participant.role_id,
            "step_id": step.step_id,
            "complete": True,
            "ok": True,
            "summary": llm_text or f"step {step.step_id} executed by {participant.role_id}",
            "model_output": llm_raw,
        }
        completed = self.completion_evaluator.evaluate(step.completion, [output], context={})
        outcome = "success" if completed else "blocked"

        event_type = "step_completed" if outcome == "success" else "step_blocked"
        self.event_bus.emit(
            TaskEvent(task_id=task.task_id, event_type=event_type, payload={"step": step.step_id})
        )

        return outcome, output
