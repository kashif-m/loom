from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.ui.router import build_ui_router
from loom.ui.security import UIUser


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise RuntimeError(f"route not found: {method} {path}")


def test_ui_api_crud_and_task_flow(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui.db", disable_scheduler=True))
    router = build_ui_router(container)

    publish = _endpoint(router, "/api/workflows/publish", "POST")
    list_workflows = _endpoint(router, "/api/workflows", "GET")
    intake = _endpoint(router, "/api/tasks/intake", "POST")
    bootstrap = _endpoint(router, "/api/bootstrap/docs-pack", "POST")
    upsert_model_provider = _endpoint(router, "/api/model-providers", "POST")
    upsert_model = _endpoint(router, "/api/models", "POST")
    upsert_service_model = _endpoint(router, "/api/service-models", "POST")
    resolve_service_model = _endpoint(router, "/api/service-models/resolve/{service_id}", "GET")
    admin = UIUser(role="admin", identity="test-admin")
    bootstrap(user=admin)

    markdown = """
## Title
Custom Flow
## Purpose
Custom
## Trigger
custom
## Required Inputs
- topic
## Steps
1. Do thing
- id: do_thing
- owned_by: docs_ops
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
"""

    from loom.ui.router import PublishWorkflowRequest, IntakeRequest

    publish(
        PublishWorkflowRequest(
            workflow_id="wf_custom",
            version=1,
            title="Custom",
            domain_pack="custom",
            intent_group="custom_local",
            markdown=markdown,
            activate=True,
        ),
        user=admin,
    )
    workflows = list_workflows(user=admin)
    assert any(w["workflow_id"] == "wf_custom" for w in workflows)

    task_resp = intake(IntakeRequest(request="run custom local workflow", domain_pack="custom"), user=admin)
    assert task_resp["task"]["task_id"]

    from loom.models import ModelDefinition, ModelProviderDefinition, ServiceModelBinding

    upsert_model_provider(
        ModelProviderDefinition(
            provider_id="litellm_local",
            provider_type="litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
            status="active",
        ),
        user=admin,
    )
    upsert_model(
        ModelDefinition(
            model_id="docs_fast",
            provider_id="litellm_local",
            model_name="openai/gpt-4.1-mini",
            status="active",
        ),
        user=admin,
    )
    upsert_service_model(
        ServiceModelBinding(
            service_id="step_execution",
            model_id="docs_fast",
            status="active",
        ),
        user=admin,
    )
    resolved = resolve_service_model("step_execution", user=admin)
    assert resolved["provider_type"] == "litellm"
