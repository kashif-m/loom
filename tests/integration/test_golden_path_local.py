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


def test_local_golden_path(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/golden.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test")

    upsert_cap = _endpoint(router, "/api/capabilities", "POST")
    upsert_prompt = _endpoint(router, "/api/prompts", "POST")
    upsert_role = _endpoint(router, "/api/roles", "POST")
    publish = _endpoint(router, "/api/workflows/publish", "POST")
    intake = _endpoint(router, "/api/tasks/intake", "POST")
    run_task = _endpoint(router, "/api/tasks/{task_id}/run", "POST")
    trace = _endpoint(router, "/api/tasks/{task_id}/trace", "GET")

    from loom.models import CapabilityDefinition, PromptProfile, RoleDefinition
    from loom.ui.router import IntakeRequest, PublishWorkflowRequest

    upsert_cap(
        CapabilityDefinition(
            capability_id="custom_cap",
            description="custom capability",
            connector_binding="none",
            validation_requirements=[],
            status="active",
        ),
        user=admin,
    )

    upsert_prompt(
        PromptProfile(
            profile_id="custom_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="you are custom",
            status="active",
        ),
        user=admin,
    )

    upsert_role(
        RoleDefinition(
            role_id="custom_agent",
            title="Custom Agent",
            domain_pack="custom",
            capability_ids=["custom_cap"],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        ),
        user=admin,
    )

    markdown = """
## Title
Golden Flow
## Purpose
Golden flow
## Trigger
golden
## Required Inputs
- topic
## Steps
1. Execute custom
- id: custom_step
- owned_by: custom_agent
- required_capabilities: custom_cap
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

    publish(
        PublishWorkflowRequest(
            workflow_id="golden_flow",
            version=1,
            title="Golden Flow",
            domain_pack="custom",
            intent_group="custom_local",
            markdown=markdown,
            activate=True,
        ),
        user=admin,
    )

    task_payload = intake(IntakeRequest(request="run custom local workflow", domain_pack="custom"), user=admin)
    task_id = task_payload["task"]["task_id"]

    ran = run_task(task_id, user=admin)
    assert ran["task_id"] == task_id

    tr = trace(task_id, user=admin)
    assert tr["task_id"] == task_id
