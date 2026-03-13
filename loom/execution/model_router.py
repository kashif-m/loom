from __future__ import annotations

from typing import Any

from loom.models import (
    ModelDefinition,
    ModelProviderDefinition,
    ServiceModelBinding,
    StatusEnum,
)


DEFAULT_STEP_SERVICE = "step_execution"


class ModelRouter:
    def __init__(
        self,
        settings,
        model_provider_registry,
        model_registry,
        service_model_registry,
    ):
        self.settings = settings
        self.model_provider_registry = model_provider_registry
        self.model_registry = model_registry
        self.service_model_registry = service_model_registry

    def bootstrap_default_litellm(self) -> None:
        if not self.settings.litellm_enabled:
            return
        if not self.settings.litellm_base_url or not self.settings.litellm_api_key:
            return

        provider_id = "litellm_default"
        model_id = "litellm_default_model"

        if not self.model_provider_registry.get(provider_id):
            self.model_provider_registry.upsert(
                ModelProviderDefinition(
                    provider_id=provider_id,
                    provider_type="litellm",
                    base_url=self.settings.litellm_base_url,
                    api_key=self.settings.litellm_api_key,
                    status=StatusEnum.active,
                )
            )

        if not self.model_registry.get(model_id):
            self.model_registry.upsert(
                ModelDefinition(
                    model_id=model_id,
                    provider_id=provider_id,
                    model_name=self.settings.litellm_default_model,
                    status=StatusEnum.active,
                )
            )

        if not self.service_model_registry.get(DEFAULT_STEP_SERVICE):
            self.service_model_registry.upsert(
                ServiceModelBinding(
                    service_id=DEFAULT_STEP_SERVICE,
                    model_id=model_id,
                    status=StatusEnum.active,
                )
            )

    def resolve(self, service_id: str) -> dict[str, Any] | None:
        binding = self.service_model_registry.get(service_id)
        if binding and binding.status == StatusEnum.active:
            model = self.model_registry.get(binding.model_id)
            if model and model.status == StatusEnum.active:
                provider = self.model_provider_registry.get(model.provider_id)
                if provider and provider.status == StatusEnum.active:
                    return {
                        "service_id": service_id,
                        "binding_source": "registry",
                        "provider_id": provider.provider_id,
                        "provider_type": provider.provider_type,
                        "base_url": provider.base_url,
                        "api_key": provider.api_key,
                        "model_id": model.model_id,
                        "model_name": model.model_name,
                        "temperature": model.temperature,
                        "max_tokens": model.max_tokens,
                    }

        return self._resolve_from_settings(service_id)

    def resolve_public(self, service_id: str) -> dict[str, Any] | None:
        route = self.resolve(service_id)
        if not route:
            return None
        return {k: v for k, v in route.items() if k != "api_key"}

    def _resolve_from_settings(self, service_id: str) -> dict[str, Any] | None:
        if self.settings.litellm_enabled and self.settings.litellm_base_url and self.settings.litellm_api_key:
            return {
                "service_id": service_id,
                "binding_source": "settings",
                "provider_id": "settings_litellm",
                "provider_type": "litellm",
                "base_url": self.settings.litellm_base_url,
                "api_key": self.settings.litellm_api_key,
                "model_id": "settings_default",
                "model_name": self.settings.litellm_default_model,
                "temperature": None,
                "max_tokens": None,
            }
        return None
