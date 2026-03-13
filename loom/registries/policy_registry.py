from __future__ import annotations

from loom.models import PolicyDefinition


class PolicyRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, policy: PolicyDefinition) -> None:
        self.repositories.policies.upsert(policy.policy_id, policy.model_dump(), status=policy.status.value)

    def get(self, policy_id: str) -> PolicyDefinition | None:
        row = self.repositories.policies.get(policy_id)
        return PolicyDefinition(**row["data"]) if row else None

    def resolve_effective(
        self,
        global_policy_ids: list[str],
        workflow_policy_ids: list[str],
        role_policy_ids: list[str],
        step_policy_ids: list[str],
    ) -> list[PolicyDefinition]:
        ordered = [*global_policy_ids, *workflow_policy_ids, *role_policy_ids, *step_policy_ids]
        out: list[PolicyDefinition] = []
        for pid in ordered:
            p = self.get(pid)
            if p:
                out.append(p)
        return out

    def list(self, status: str | None = None) -> list[PolicyDefinition]:
        return [PolicyDefinition(**row["data"]) for row in self.repositories.policies.list(status=status)]
