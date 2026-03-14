from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import CapabilityDefinition, PolicyDefinition, PromptProfile, RoleDefinition
from loom.ui.router import PublishWorkflowRequest


class _DeterministicAdapter:
    def run(self, *args, **kwargs):
        return {
            "ok": True,
            "output": "deterministic-test-output",
            "model": kwargs.get("model", "test-model"),
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }


def _strict_test_container(tmp_path: Path, db_name: str) -> Container:
    container = Container(
        Settings(
            database_url=f"sqlite:///{tmp_path}/{db_name}",
            disable_scheduler=True,
            openai_enabled=True,
            openai_api_key="test-key",
        )
    )
    container.step_runner.agent_adapter = _DeterministicAdapter()
    return container


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise RuntimeError(f"route not found: {method} {path}")


def _publish(router, user, workflow_id: str, markdown: str, domain_pack: str = "custom", intent: str = "custom_local"):

    publish = _endpoint(router, "/api/workflows/publish", "POST")
    publish(
        PublishWorkflowRequest(
            workflow_id=workflow_id,
            version=1,
            title=workflow_id,
            domain_pack=domain_pack,
            intent_group=intent,
            markdown=markdown,
            activate=True,
        ),
        user=user,
    )


def test_intake_many_fanout_by_document_urls(tmp_path: Path):
    from loom.ui.security import UIUser
    from loom.ui.router import build_ui_router

    container = _strict_test_container(tmp_path, "fanout.db")
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test")

    upsert_cap = _endpoint(router, "/api/capabilities", "POST")
    upsert_prompt = _endpoint(router, "/api/prompts", "POST")
    upsert_role = _endpoint(router, "/api/roles", "POST")

    upsert_cap(
        CapabilityDefinition(
            capability_id="custom_cap",
            description="custom",
            connector_binding="none",
            status="active",
        ),
        user=admin,
    )
    upsert_prompt(
        PromptProfile(
            profile_id="fanout_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="fanout",
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

    _publish(
        router,
        admin,
        "fanout_flow",
        """
## Title
Fanout Flow
## Purpose
Fanout flow
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Execute
- id: execute
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
""",
    )

    tasks = container.intake_service.intake_many(
        "enhance docs https://example.com/a and https://example.com/b",
        domain_pack="custom",
        workflow_id="fanout_flow",
        workflow_version=1,
    )
    assert len(tasks) == 2
    assert all(t.linked_entities.get("fanout_group") for t in tasks)
    assert tasks[0].linked_entities.get("task_object_ref") != tasks[1].linked_entities.get("task_object_ref")
    for task in tasks:
        assert task.linked_entities.get("document_url") == task.linked_entities.get("task_object_ref")
    summary = container.intake_service.fanin_summary(tasks[0].linked_entities["fanout_group"])
    assert summary["count"] == 2


def test_subworkflow_dispatch_creates_child_task(tmp_path: Path):
    from loom.ui.security import UIUser
    from loom.ui.router import build_ui_router

    container = _strict_test_container(tmp_path, "subflow.db")
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test")

    upsert_cap = _endpoint(router, "/api/capabilities", "POST")
    upsert_prompt = _endpoint(router, "/api/prompts", "POST")
    upsert_role = _endpoint(router, "/api/roles", "POST")

    for cap_id in ("parent_cap", "child_cap"):
        upsert_cap(
            CapabilityDefinition(
                capability_id=cap_id,
                description=cap_id,
                connector_binding="none",
                status="active",
            ),
            user=admin,
        )
    upsert_prompt(
        PromptProfile(
            profile_id="subflow_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="subflow",
            status="active",
        ),
        user=admin,
    )
    upsert_role(
        RoleDefinition(
            role_id="parent_role",
            title="Parent Role",
            domain_pack="custom",
            capability_ids=["parent_cap"],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        ),
        user=admin,
    )
    upsert_role(
        RoleDefinition(
            role_id="child_role",
            title="Child Role",
            domain_pack="custom",
            capability_ids=["child_cap"],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        ),
        user=admin,
    )

    _publish(
        router,
        admin,
        "child_flow",
        """
## Title
Child Flow
## Purpose
child
## Trigger
child
## Required Inputs
- topic
## Steps
1. Child execute
- id: child_execute
- owned_by: child_role
- required_capabilities: child_cap
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
""",
    )
    _publish(
        router,
        admin,
        "parent_flow",
        """
## Title
Parent Flow
## Purpose
parent
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Parent execute
- id: parent_execute
- owned_by: parent_role
- required_capabilities: parent_cap
- subworkflow_id: child_flow
- subworkflow_version: 1
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
""",
    )

    task = container.intake_service.intake_with_workflow(
        "run parent",
        workflow_id="parent_flow",
        workflow_version=1,
        domain_pack="custom",
    )
    task = container.execution_coordinator.run_task(task)
    container.repositories.tasks.update(task)

    assert task.current_status.value in {"completed", "blocked", "failed"}
    sub = task.execution_refs["parent_execute"]["subworkflow"]
    assert sub["workflow_id"] == "child_flow"
    assert sub["task_id"]
    children = [t for t in container.repositories.tasks.list() if t.linked_entities.get("parent_task_id") == task.task_id]
    assert children


def test_state_ownership_policy_blocks_wrong_writer(tmp_path: Path):
    from loom.ui.security import UIUser
    from loom.ui.router import build_ui_router

    container = _strict_test_container(tmp_path, "state-owner.db")
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test")

    upsert_cap = _endpoint(router, "/api/capabilities", "POST")
    upsert_prompt = _endpoint(router, "/api/prompts", "POST")
    upsert_role = _endpoint(router, "/api/roles", "POST")
    upsert_policy = _endpoint(router, "/api/policies", "POST")

    upsert_cap(
        CapabilityDefinition(
            capability_id="state_write",
            description="state write",
            connector_binding="none",
            status="active",
        ),
        user=admin,
    )
    upsert_prompt(
        PromptProfile(
            profile_id="state_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="state",
            status="active",
        ),
        user=admin,
    )
    upsert_policy(
        PolicyDefinition(
            policy_id="pr_lifecycle_state_owner_guard",
            description="only product_analyst can write pr lifecycle state",
            scope="role",
            enforcement="block",
            rules={"state_partition": "pr_lifecycle", "owner_roles": ["product_analyst"]},
            status="active",
        ),
        user=admin,
    )
    upsert_role(
        RoleDefinition(
            role_id="kite_runner",
            title="Kite Runner",
            domain_pack="custom",
            capability_ids=["state_write"],
            policy_ids=["pr_lifecycle_state_owner_guard"],
            memory_visibility=[],
            status="active",
        ),
        user=admin,
    )

    _publish(
        router,
        admin,
        "ownership_flow",
        """
## Title
Ownership Flow
## Purpose
ownership
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Write state
- id: write_state
- owned_by: kite_runner
- required_capabilities: state_write
- state_partition: pr_lifecycle
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
""",
    )

    task = container.intake_service.intake_with_workflow(
        "write state",
        workflow_id="ownership_flow",
        workflow_version=1,
        domain_pack="custom",
    )
    task = container.execution_coordinator.run_task(task)
    container.repositories.tasks.update(task)
    assert task.current_status.value == "failed"
    assert "state partition" in (task.result_summary or "")


def test_state_ownership_policy_allows_owner_and_persists_partition_state(tmp_path: Path):
    from loom.ui.security import UIUser
    from loom.ui.router import build_ui_router

    container = _strict_test_container(tmp_path, "state-owner-ok.db")
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test")

    upsert_cap = _endpoint(router, "/api/capabilities", "POST")
    upsert_prompt = _endpoint(router, "/api/prompts", "POST")
    upsert_role = _endpoint(router, "/api/roles", "POST")
    upsert_policy = _endpoint(router, "/api/policies", "POST")

    upsert_cap(
        CapabilityDefinition(
            capability_id="state_write",
            description="state write",
            connector_binding="none",
            status="active",
        ),
        user=admin,
    )
    upsert_prompt(
        PromptProfile(
            profile_id="state_ok_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="state",
            status="active",
        ),
        user=admin,
    )
    upsert_policy(
        PolicyDefinition(
            policy_id="pr_lifecycle_state_owner_guard_ok",
            description="only product_analyst can write pr lifecycle state",
            scope="role",
            enforcement="block",
            rules={"state_partition": "pr_lifecycle", "owner_roles": ["product_analyst"]},
            status="active",
        ),
        user=admin,
    )
    upsert_role(
        RoleDefinition(
            role_id="product_analyst",
            title="Product Analyst",
            domain_pack="custom",
            capability_ids=["state_write"],
            policy_ids=["pr_lifecycle_state_owner_guard_ok"],
            memory_visibility=[],
            status="active",
        ),
        user=admin,
    )

    _publish(
        router,
        admin,
        "ownership_flow_ok",
        """
## Title
Ownership Flow OK
## Purpose
ownership
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Write state
- id: write_state
- owned_by: product_analyst
- required_capabilities: state_write
- state_partition: pr_lifecycle
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
""",
    )

    task = container.intake_service.intake_with_workflow(
        "write state",
        workflow_id="ownership_flow_ok",
        workflow_version=1,
        domain_pack="custom",
    )
    task = container.execution_coordinator.run_task(task)
    container.repositories.tasks.update(task)
    assert task.current_status.value == "completed"
    rows = container.state_partition_service.list(partition_id="pr_lifecycle")
    assert rows
