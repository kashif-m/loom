from __future__ import annotations

from loom.models import MemoryRoleEdge


class MemoryEdgeRegistry:
    def __init__(self, repositories, memory_group_registry, role_registry):
        self.repositories = repositories
        self.memory_group_registry = memory_group_registry
        self.role_registry = role_registry

    def upsert(self, edge: MemoryRoleEdge) -> None:
        if self.role_registry.get(edge.parent_role_id) is None:
            raise KeyError(f"parent role not found: {edge.parent_role_id}")
        if self.role_registry.get(edge.child_role_id) is None:
            raise KeyError(f"child role not found: {edge.child_role_id}")
        if edge.shared_group_id:
            group = self.memory_group_registry.get(edge.organization_id, edge.shared_group_id)
            if group is None:
                raise KeyError(
                    f"shared memory group not found: {edge.organization_id}:{edge.shared_group_id}"
                )
        self.repositories.memory_edges.upsert(
            edge.edge_id or f"{edge.organization_id}:{edge.parent_role_id}:{edge.child_role_id}:{edge.shared_group_id or 'none'}",
            edge.model_dump(),
            status=edge.status.value,
        )

    def get(self, edge_id: str) -> MemoryRoleEdge | None:
        row = self.repositories.memory_edges.get(edge_id)
        return MemoryRoleEdge(**row["data"]) if row else None

    def list(
        self,
        *,
        organization_id: str | None = None,
        parent_role_id: str | None = None,
        child_role_id: str | None = None,
        status: str | None = None,
    ) -> list[MemoryRoleEdge]:
        rows = [MemoryRoleEdge(**row["data"]) for row in self.repositories.memory_edges.list(status=status)]
        if organization_id:
            rows = [row for row in rows if row.organization_id == organization_id]
        if parent_role_id:
            rows = [row for row in rows if row.parent_role_id == parent_role_id]
        if child_role_id:
            rows = [row for row in rows if row.child_role_id == child_role_id]
        return rows

    def delete(self, edge_id: str) -> None:
        self.repositories.memory_edges.delete(edge_id)
