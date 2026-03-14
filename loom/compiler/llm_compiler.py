from __future__ import annotations

from loom.models import (
    CompiledWorkflowIR,
    CompiledWorkflowStep,
    CompletionSemantics,
    ParsedWorkflowDocument,
    StepTransitions,
)


class DeterministicLLMCompiler:
    @staticmethod
    def _parse_int_or_none(raw: str | None) -> int | None:
        if raw is None or raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def compile(self, workflow_id: str, version: int, doc: ParsedWorkflowDocument) -> CompiledWorkflowIR:
        steps: list[CompiledWorkflowStep] = []
        for i, s in enumerate(doc.steps):
            attrs = s.get("attributes", {})
            step_id = attrs.get("id", f"step_{i+1}")
            success = attrs.get("on_success", f"step_{i+2}" if i + 1 < len(doc.steps) else "completed")
            step = CompiledWorkflowStep(
                step_id=step_id,
                title=s["text"],
                owned_by=attrs.get("owned_by", "docs_ops"),
                participants=[p.strip() for p in attrs.get("participants", "").split(",") if p.strip()],
                required_capabilities=[
                    c.strip() for c in attrs.get("required_capabilities", "").split(",") if c.strip()
                ],
                spawn_strategy=attrs.get("spawn_strategy", "single_owner"),
                merge_strategy=attrs.get("merge_strategy", "owner_synthesizes"),
                completion=CompletionSemantics(
                    type=attrs.get("completion_type", "all_outputs_present"),
                    predicate=attrs.get("completion_predicate"),
                ),
                transitions=StepTransitions(
                    on_success=success,
                    on_blocked=attrs.get("on_blocked", "blocked"),
                    on_failure=attrs.get("on_failure", "failed"),
                    on_retry=attrs.get("on_retry"),
                ),
                policy_bindings=[p.strip() for p in attrs.get("policy_bindings", "").split(",") if p.strip()],
                prompt_profile_id=attrs.get("prompt_profile_id"),
                memory_hints={
                    "notes": attrs.get("memory_hints", ""),
                    "state_partition": attrs.get("state_partition"),
                    "subworkflow_id": attrs.get("subworkflow_id"),
                    "subworkflow_version": self._parse_int_or_none(attrs.get("subworkflow_version")),
                },
            )
            steps.append(step)

        return CompiledWorkflowIR(
            workflow_id=workflow_id,
            version=version,
            title=doc.title,
            purpose=doc.purpose,
            required_inputs=doc.required_inputs,
            steps=steps,
            rules=doc.rules,
            memory_hints={"blocked_conditions": doc.blocked_conditions, "failure_conditions": doc.failure_conditions},
        )
