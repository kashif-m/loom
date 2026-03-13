from __future__ import annotations

from loom.models import ModelProviderDefinition


class ModelProviderRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, provider: ModelProviderDefinition) -> None:
        self.repositories.model_providers.upsert(
            provider.provider_id,
            provider.model_dump(),
            status=provider.status.value,
        )

    def get(self, provider_id: str) -> ModelProviderDefinition | None:
        row = self.repositories.model_providers.get(provider_id)
        return ModelProviderDefinition(**row["data"]) if row else None

    def list(self, status: str | None = None) -> list[ModelProviderDefinition]:
        return [
            ModelProviderDefinition(**row["data"])
            for row in self.repositories.model_providers.list(status=status)
        ]

    def delete(self, provider_id: str) -> None:
        self.repositories.model_providers.delete(provider_id)
