from __future__ import annotations


class PolicyEngine:
    def __init__(self, policy_registry):
        self.policy_registry = policy_registry

    def enforce(
        self,
        global_policy_ids: list[str],
        workflow_policy_ids: list[str],
        role_policy_ids: list[str],
        step_policy_ids: list[str],
        context: dict,
    ) -> None:
        policies = self.policy_registry.resolve_effective(
            global_policy_ids,
            workflow_policy_ids,
            role_policy_ids,
            step_policy_ids,
        )
        for policy in policies:
            if policy.policy_id == "no_direct_merge" and context.get("operation") == "merge":
                raise PermissionError("no direct merge policy violation")
            if policy.policy_id == "approval_required_before_promotion":
                if context.get("operation") == "promote" and not context.get("approved"):
                    raise PermissionError("approval required before promotion")
            if context.get("operation") == "state_write":
                owner_roles = policy.rules.get("owner_roles")
                state_partition = policy.rules.get("state_partition")
                if owner_roles and state_partition and state_partition == context.get("state_partition"):
                    actor_role = context.get("actor_role")
                    if actor_role not in owner_roles:
                        raise PermissionError(
                            f"state partition '{state_partition}' is owned by {owner_roles}, actor={actor_role}"
                        )
            if policy.enforcement.value == "block" and policy.rules.get("deny_operation") == context.get("operation"):
                raise PermissionError(f"operation blocked by policy {policy.policy_id}")
