from __future__ import annotations

from loom.models import MemoryGroupDefinition


class MemoryGroupRegistry:
    def __init__(self, repositories, role_registry):
        self.repositories = repositories
        self.role_registry = role_registry

    def _repo_key(self, organization_id: str, group_id: str) -> str:
        return f"{organization_id}:{group_id}"

    def upsert(self, group: MemoryGroupDefinition) -> None:
        if group.owner_role_id and self.role_registry.get(group.owner_role_id) is None:
            raise KeyError(f"owner role not found: {group.owner_role_id}")
        self.repositories.memory_groups.upsert(
            self._repo_key(group.organization_id, group.group_id),
            group.model_dump(),
            status=group.status.value,
        )

    def get(self, organization_id: str, group_id: str) -> MemoryGroupDefinition | None:
        row = self.repositories.memory_groups.get(self._repo_key(organization_id, group_id))
        return MemoryGroupDefinition(**row["data"]) if row else None

    def list(
        self,
        *,
        organization_id: str | None = None,
        status: str | None = None,
    ) -> list[MemoryGroupDefinition]:
        rows = [MemoryGroupDefinition(**row["data"]) for row in self.repositories.memory_groups.list(status=status)]
        if organization_id:
            rows = [row for row in rows if row.organization_id == organization_id]
        return rows

    def delete(self, organization_id: str, group_id: str) -> None:
        self.repositories.memory_groups.delete(self._repo_key(organization_id, group_id))
