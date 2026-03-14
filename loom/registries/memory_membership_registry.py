from __future__ import annotations

from loom.models import MemoryGroupMembership


class MemoryMembershipRegistry:
    def __init__(self, repositories, memory_group_registry, role_registry):
        self.repositories = repositories
        self.memory_group_registry = memory_group_registry
        self.role_registry = role_registry

    def upsert(self, membership: MemoryGroupMembership) -> None:
        group = self.memory_group_registry.get(membership.organization_id, membership.group_id)
        if group is None:
            raise KeyError(
                f"memory group not found: {membership.organization_id}:{membership.group_id}"
            )
        if self.role_registry.get(membership.role_id) is None:
            raise KeyError(f"role not found: {membership.role_id}")
        self.repositories.memory_memberships.upsert(
            membership.membership_id or f"{membership.organization_id}:{membership.group_id}:{membership.role_id}",
            membership.model_dump(),
            status=membership.status.value,
        )

    def get(self, membership_id: str) -> MemoryGroupMembership | None:
        row = self.repositories.memory_memberships.get(membership_id)
        return MemoryGroupMembership(**row["data"]) if row else None

    def list(
        self,
        *,
        organization_id: str | None = None,
        group_id: str | None = None,
        role_id: str | None = None,
        status: str | None = None,
    ) -> list[MemoryGroupMembership]:
        rows = [
            MemoryGroupMembership(**row["data"])
            for row in self.repositories.memory_memberships.list(status=status)
        ]
        if organization_id:
            rows = [row for row in rows if row.organization_id == organization_id]
        if group_id:
            rows = [row for row in rows if row.group_id == group_id]
        if role_id:
            rows = [row for row in rows if row.role_id == role_id]
        return rows

    def delete(self, membership_id: str) -> None:
        self.repositories.memory_memberships.delete(membership_id)
