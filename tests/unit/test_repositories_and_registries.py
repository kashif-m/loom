from pathlib import Path

from loom.models import (
    CapabilityDefinition,
    ModelDefinition,
    ModelProviderDefinition,
    RoleDefinition,
    ServiceModelBinding,
    StatusEnum,
)
from loom.persistence.db import init_db
from loom.persistence.repositories import Repositories
from loom.registries.capability_registry import CapabilityRegistry
from loom.registries.model_provider_registry import ModelProviderRegistry
from loom.registries.model_registry import ModelRegistry
from loom.registries.role_registry import RoleRegistry
from loom.registries.service_model_registry import ServiceModelRegistry


def test_registry_crud(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    repos = Repositories(init_db(db_url))

    roles = RoleRegistry(repos)
    caps = CapabilityRegistry(repos)
    providers = ModelProviderRegistry(repos)
    models = ModelRegistry(repos, providers)
    service_models = ServiceModelRegistry(repos, models)

    caps.upsert(
        CapabilityDefinition(capability_id="repo_read", description="read", connector_binding="opencode")
    )
    roles.upsert(
        RoleDefinition(
            role_id="docs_ops",
            title="Docs Ops",
            domain_pack="docs",
            capability_ids=["repo_read"],
            status=StatusEnum.active,
        )
    )

    providers.upsert(
        ModelProviderDefinition(
            provider_id="litellm_local",
            provider_type="litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
            status=StatusEnum.active,
        )
    )
    models.upsert(
        ModelDefinition(
            model_id="docs_fast",
            provider_id="litellm_local",
            model_name="openai/gpt-4.1-mini",
            status=StatusEnum.active,
        )
    )
    service_models.upsert(
        ServiceModelBinding(
            service_id="step_execution",
            model_id="docs_fast",
            status=StatusEnum.active,
        )
    )

    assert roles.get("docs_ops") is not None
    assert caps.get("repo_read") is not None
    assert providers.get("litellm_local") is not None
    assert models.get("docs_fast") is not None
    assert service_models.get("step_execution") is not None
