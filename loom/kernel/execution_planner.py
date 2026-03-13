from __future__ import annotations

from loom.models import CompiledWorkflowIR


class ExecutionPlanner:
    def __init__(self, workflow_registry):
        self.workflow_registry = workflow_registry

    def load_ir(self, workflow_id: str, version: int) -> CompiledWorkflowIR:
        row = self.workflow_registry.get_version(workflow_id, version)
        if not row or not row.get("compiled_ir"):
            raise ValueError(f"compiled workflow not found for {workflow_id}:{version}")
        return CompiledWorkflowIR(**row["compiled_ir"])

    def first_step(self, ir: CompiledWorkflowIR):
        return ir.steps[0]

    def next_target(self, step, outcome: str) -> str:
        if outcome == "success":
            return step.transitions.on_success
        if outcome == "blocked":
            return step.transitions.on_blocked or "blocked"
        if outcome == "failed":
            return step.transitions.on_failure or "failed"
        if outcome == "retry":
            return step.transitions.on_retry or step.step_id
        return "failed"
