from __future__ import annotations

from loom.models import CompiledWorkflowIR


class IRValidator:
    def __init__(self, role_registry, capability_registry, policy_registry):
        self.role_registry = role_registry
        self.capability_registry = capability_registry
        self.policy_registry = policy_registry

    def validate(self, ir: CompiledWorkflowIR) -> list[str]:
        errors: list[str] = []
        if not ir.workflow_id:
            errors.append("workflow_id is required")
        if ir.version < 1:
            errors.append("version must be >= 1")

        step_ids = [s.step_id for s in ir.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append("all step ids must be unique")

        valid_targets = set(step_ids) | set(ir.terminal_states)

        for step in ir.steps:
            if not step.owned_by:
                errors.append(f"step {step.step_id}: owned_by is required")
            if self.role_registry.get(step.owned_by) is None:
                errors.append(f"step {step.step_id}: unknown role {step.owned_by}")

            for participant in step.participants:
                if self.role_registry.get(participant) is None:
                    errors.append(f"step {step.step_id}: unknown participant role {participant}")

            for cap in step.required_capabilities:
                if not self.capability_registry.exists(cap):
                    errors.append(f"step {step.step_id}: unknown capability {cap}")

            for policy_id in step.policy_bindings:
                if self.policy_registry.get(policy_id) is None:
                    errors.append(f"step {step.step_id}: unknown policy {policy_id}")

            targets = [
                step.transitions.on_success,
                step.transitions.on_blocked,
                step.transitions.on_failure,
                step.transitions.on_retry,
            ]
            for target in targets:
                if target and target not in valid_targets:
                    errors.append(f"step {step.step_id}: invalid transition target {target}")

            if step.completion.type == "predicate" and not step.completion.predicate:
                errors.append(f"step {step.step_id}: predicate completion requires predicate")

        return errors
