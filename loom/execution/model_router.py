from __future__ import annotations

from typing import Any

from loom.models import (
    Organization,
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
        organization_repository=None,
        role_registry=None,
    ):
        self.settings = settings
        self.model_provider_registry = model_provider_registry
        self.model_registry = model_registry
        self.service_model_registry = service_model_registry
        self.organization_repository = organization_repository
        self.role_registry = role_registry

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

    def resolve(
        self,
        service_id: str,
        organization_id: str = "default",
        role_id: str | None = None,
    ) -> dict[str, Any] | None:
        role_route = self._resolve_from_role(service_id, role_id=role_id)
        if role_route:
            return role_route

        binding = self.service_model_registry.get(service_id)
        if binding and binding.status == StatusEnum.active:
            model = self.model_registry.get(binding.model_id)
            if model and model.status == StatusEnum.active:
                provider = self.model_provider_registry.get(model.provider_id)
                if provider and provider.status == StatusEnum.active:
                    registry_route = {
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
                    if self._should_prefer_org_route(service_id, registry_route):
                        org_route = self._resolve_from_organization(service_id, organization_id=organization_id)
                        if org_route:
                            return org_route
                    return registry_route

        org_route = self._resolve_from_organization(service_id, organization_id=organization_id)
        if org_route:
            return org_route

        return self._resolve_from_settings(service_id)

    def resolve_public(
        self,
        service_id: str,
        organization_id: str = "default",
        role_id: str | None = None,
    ) -> dict[str, Any] | None:
        route = self.resolve(service_id, organization_id=organization_id, role_id=role_id)
        if not route:
            return None
        return {k: v for k, v in route.items() if k != "api_key"}

    def _resolve_from_role(self, service_id: str, *, role_id: str | None) -> dict[str, Any] | None:
        if self.role_registry is None or not role_id:
            return None
        role = self.role_registry.get(role_id)
        if role is None or not role.preferred_model_id:
            return None

        model = self.model_registry.get(role.preferred_model_id)
        if model is None or model.status != StatusEnum.active:
            return None
        provider = self.model_provider_registry.get(model.provider_id)
        if provider is None or provider.status != StatusEnum.active:
            return None

        return {
            "service_id": service_id,
            "binding_source": "role",
            "role_id": role_id,
            "provider_id": provider.provider_id,
            "provider_type": provider.provider_type,
            "base_url": provider.base_url,
            "api_key": provider.api_key,
            "model_id": model.model_id,
            "model_name": model.model_name,
            "temperature": model.temperature,
            "max_tokens": model.max_tokens,
        }

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
        if self.settings.openai_enabled and self.settings.openai_api_key:
            return {
                "service_id": service_id,
                "binding_source": "settings",
                "provider_id": "settings_openai",
                "provider_type": "openai",
                "base_url": None,
                "api_key": self.settings.openai_api_key,
                "model_id": "settings_openai_default",
                "model_name": self.settings.openai_model,
                "temperature": None,
                "max_tokens": None,
            }
        return None

    def _resolve_from_organization(
        self,
        service_id: str,
        *,
        organization_id: str = "default",
    ) -> dict[str, Any] | None:
        if self.organization_repository is None:
            return None

        org = self.organization_repository.get(organization_id)
        if org is None:
            return None

        return self._build_org_route(org, service_id)

    def _build_org_route(self, org: Organization, service_id: str) -> dict[str, Any] | None:
        if org.litellm_base_url and org.litellm_api_key:
            return {
                "service_id": service_id,
                "binding_source": "organization",
                "provider_id": "organization_litellm",
                "provider_type": "litellm",
                "base_url": org.litellm_base_url,
                "api_key": org.litellm_api_key,
                "model_id": "organization_litellm_default",
                "model_name": org.litellm_default_model,
                "temperature": None,
                "max_tokens": None,
            }

        if org.openai_api_key:
            return {
                "service_id": service_id,
                "binding_source": "organization",
                "provider_id": "organization_openai",
                "provider_type": "openai",
                "base_url": None,
                "api_key": org.openai_api_key,
                "model_id": "organization_openai_default",
                "model_name": org.openai_model,
                "temperature": None,
                "max_tokens": None,
            }

        return None

    def _should_prefer_org_route(self, service_id: str, registry_route: dict[str, Any]) -> bool:
        # Keep explicit service-model bindings authoritative, but allow org
        # config to override the bootstrap default step_execution route.
        if service_id != DEFAULT_STEP_SERVICE:
            return False
        return registry_route.get("provider_id") == "litellm_default"
