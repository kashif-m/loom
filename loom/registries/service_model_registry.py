from __future__ import annotations

from loom.models import ServiceModelBinding


class ServiceModelRegistry:
    def __init__(self, repositories, model_registry):
        self.repositories = repositories
        self.model_registry = model_registry

    def upsert(self, binding: ServiceModelBinding) -> None:
        model = self.model_registry.get(binding.model_id)
        if not model:
            raise KeyError(f"model not found: {binding.model_id}")
        self.repositories.service_models.upsert(
            binding.service_id,
            binding.model_dump(),
            status=binding.status.value,
        )

    def get(self, service_id: str) -> ServiceModelBinding | None:
        row = self.repositories.service_models.get(service_id)
        return ServiceModelBinding(**row["data"]) if row else None

    def list(self, status: str | None = None) -> list[ServiceModelBinding]:
        return [
            ServiceModelBinding(**row["data"])
            for row in self.repositories.service_models.list(status=status)
        ]

    def delete(self, service_id: str) -> None:
        self.repositories.service_models.delete(service_id)
