from __future__ import annotations

from loom.models import ModelDefinition


class ModelRegistry:
    def __init__(self, repositories, model_provider_registry):
        self.repositories = repositories
        self.model_provider_registry = model_provider_registry

    def upsert(self, model: ModelDefinition) -> None:
        provider = self.model_provider_registry.get(model.provider_id)
        if not provider:
            raise KeyError(f"provider not found: {model.provider_id}")
        self.repositories.models.upsert(
            model.model_id,
            model.model_dump(),
            status=model.status.value,
        )

    def get(self, model_id: str) -> ModelDefinition | None:
        row = self.repositories.models.get(model_id)
        return ModelDefinition(**row["data"]) if row else None

    def list(self, status: str | None = None) -> list[ModelDefinition]:
        return [ModelDefinition(**row["data"]) for row in self.repositories.models.list(status=status)]

    def delete(self, model_id: str) -> None:
        self.repositories.models.delete(model_id)
