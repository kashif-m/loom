from __future__ import annotations

from loom.models import MemoryGroupDefinition, MemoryGroupMembership


class MemoryTopologyService:
    PRIVATE_PREFIX = "private."

    def __init__(self, memory_group_registry, memory_membership_registry, role_registry):
        self.memory_group_registry = memory_group_registry
        self.memory_membership_registry = memory_membership_registry
        self.role_registry = role_registry

    def private_group_id(self, role_id: str) -> str:
        return f"{self.PRIVATE_PREFIX}{role_id}"

    def ensure_private_membership(self, organization_id: str, role_id: str) -> None:
        if self.role_registry.get(role_id) is None:
            raise KeyError(f"role not found: {role_id}")
        group_id = self.private_group_id(role_id)
        group = self.memory_group_registry.get(organization_id, group_id)
        if group is None:
            self.memory_group_registry.upsert(
                MemoryGroupDefinition(
                    group_id=group_id,
                    organization_id=organization_id,
                    title=f"Private Memory for {role_id}",
                    description="Role-private memory scope.",
                    visibility="private",
                    owner_role_id=role_id,
                    status="active",
                )
            )
        membership_id = f"{organization_id}:{group_id}:{role_id}"
        membership = self.memory_membership_registry.get(membership_id)
        if membership is None:
            self.memory_membership_registry.upsert(
                MemoryGroupMembership(
                    membership_id=membership_id,
                    organization_id=organization_id,
                    group_id=group_id,
                    role_id=role_id,
                    access="read_write",
                    status="active",
                )
            )

    def _membership_groups(self, organization_id: str, role_id: str) -> list[MemoryGroupMembership]:
        self.ensure_private_membership(organization_id, role_id)
        return self.memory_membership_registry.list(
            organization_id=organization_id,
            role_id=role_id,
            status="active",
        )

    def _scope(
        self,
        *,
        organization_id: str,
        domain_pack: str,
        workflow_id: str,
        workflow_version: int,
        group_id: str,
    ) -> dict:
        scope_id = f"group:{group_id}"
        return {
            "organization_id": organization_id,
            "domain_pack": domain_pack,
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "role": scope_id,
            "scope_id": scope_id,
            "memory_group_id": group_id,
        }

    def resolve_scopes(
        self,
        *,
        organization_id: str,
        role_id: str,
        domain_pack: str,
        workflow_id: str,
        workflow_version: int,
    ) -> dict[str, list[dict]]:
        memberships = self._membership_groups(organization_id, role_id)
        readable = []
        writable = []

        def _is_private(group_id: str) -> bool:
            return group_id.startswith(self.PRIVATE_PREFIX)

        sorted_memberships = sorted(
            memberships,
            key=lambda m: (0 if _is_private(m.group_id) else 1, m.group_id),
        )
        for membership in sorted_memberships:
            scope = self._scope(
                organization_id=organization_id,
                domain_pack=domain_pack,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                group_id=membership.group_id,
            )
            if membership.access in {"read", "read_write"}:
                readable.append(scope)
            if membership.access in {"write", "read_write"}:
                writable.append(scope)
        return {"read": readable, "write": writable}
