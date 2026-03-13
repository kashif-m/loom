from __future__ import annotations

from loom.models import CapabilityDefinition


class CapabilityRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, capability: CapabilityDefinition) -> None:
        self.repositories.capabilities.upsert(
            capability.capability_id,
            capability.model_dump(),
            status=capability.status.value,
        )

    def get(self, capability_id: str) -> CapabilityDefinition | None:
        row = self.repositories.capabilities.get(capability_id)
        return CapabilityDefinition(**row["data"]) if row else None

    def exists(self, capability_id: str) -> bool:
        return self.get(capability_id) is not None

    def list(self, status: str | None = None) -> list[CapabilityDefinition]:
        return [CapabilityDefinition(**row["data"]) for row in self.repositories.capabilities.list(status=status)]
