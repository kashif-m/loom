from __future__ import annotations

from loom.models import RoleDefinition


class RoleRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, role: RoleDefinition) -> None:
        existing = self.repositories.roles.get(role.role_id)
        if existing and existing["data"].get("role_id") != role.role_id:
            raise ValueError("duplicate role id")
        self.repositories.roles.upsert(role.role_id, role.model_dump(), status=role.status.value)

    def get(self, role_id: str) -> RoleDefinition | None:
        row = self.repositories.roles.get(role_id)
        return RoleDefinition(**row["data"]) if row else None

    def list(self, status: str | None = None) -> list[RoleDefinition]:
        return [RoleDefinition(**row["data"]) for row in self.repositories.roles.list(status=status)]

    def retire(self, role_id: str) -> None:
        role = self.get(role_id)
        if not role:
            raise KeyError(role_id)
        role.status = role.status.retired
        self.upsert(role)
