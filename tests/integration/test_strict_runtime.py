from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import RoleDefinition, WorkflowDefinitionMetadata, WorkflowMarkdownDocument


def test_strict_runtime_blocks_without_model_route(tmp_path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/strict-runtime.db", disable_scheduler=True))

    container.role_registry.upsert(
        RoleDefinition(
            role_id="strict_owner",
            title="Strict Owner",
            domain_pack="custom",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )

    markdown = """
## Title
Strict Flow
## Purpose
Validate strict runtime.
## Trigger
custom_local
## Required Inputs
- request
## Steps
1. Execute strict step
- id: strict_step
- owned_by: strict_owner
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
    metadata = WorkflowDefinitionMetadata(
        workflow_id="strict.flow",
        version=1,
        title="Strict Flow",
        domain_pack="custom",
        intent_group="custom_local",
    )
    doc = WorkflowMarkdownDocument(workflow_id="strict.flow", version=1, markdown=markdown)
    container.compiler_service.publish_from_markdown(metadata, doc, activate=True)

    task = container.intake_service.intake_with_workflow(
        "run strict flow",
        workflow_id="strict.flow",
        workflow_version=1,
        domain_pack="custom",
    )
    task = container.execution_coordinator.run_task(task)
    container.repositories.tasks.update(task)

    assert task.current_status.value == "blocked"
    assert (task.result_summary or "").startswith("MODEL_ROUTE_MISSING")
    assert task.execution_refs.get("preflight", {}).get("code") == "MODEL_ROUTE_MISSING"
    assert "mocked-model-output" not in str(task.execution_refs)
