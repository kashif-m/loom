from pathlib import Path

import pytest

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import CapabilityDefinition, PromptProfile, RoleDefinition, WorkflowDefinitionMetadata, WorkflowMarkdownDocument


def _markdown(title: str) -> str:
    return f"""
## Title
{title}
## Purpose
immutability test
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Execute
- id: execute
- owned_by: immut_agent
- required_capabilities: immut_cap
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


def test_workflow_version_is_immutable(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/immut.db", disable_scheduler=True))
    container.capability_registry.upsert(
        CapabilityDefinition(
            capability_id="immut_cap",
            description="immut cap",
            connector_binding="none",
            status="active",
        )
    )
    container.prompt_registry.upsert(
        PromptProfile(
            profile_id="immut_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="immut",
            status="active",
        )
    )
    container.role_registry.upsert(
        RoleDefinition(
            role_id="immut_agent",
            title="Immut Agent",
            domain_pack="custom",
            capability_ids=["immut_cap"],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )

    metadata = WorkflowDefinitionMetadata(
        workflow_id="immut_flow",
        version=1,
        title="Immut Flow",
        domain_pack="custom",
        intent_group="custom_local",
    )
    container.compiler_service.publish_from_markdown(
        metadata,
        WorkflowMarkdownDocument(workflow_id="immut_flow", version=1, markdown=_markdown("Immut Flow")),
        activate=True,
    )

    with pytest.raises(ValueError, match="immutable"):
        container.compiler_service.publish_from_markdown(
            metadata,
            WorkflowMarkdownDocument(
                workflow_id="immut_flow",
                version=1,
                markdown=_markdown("Immut Flow Updated"),
            ),
            activate=True,
        )


def test_workflow_republish_same_version_same_content_is_idempotent(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/immut-idem.db", disable_scheduler=True))
    container.capability_registry.upsert(
        CapabilityDefinition(
            capability_id="immut_cap",
            description="immut cap",
            connector_binding="none",
            status="active",
        )
    )
    container.prompt_registry.upsert(
        PromptProfile(
            profile_id="immut_prompt",
            version=1,
            domain_pack="custom",
            system_prompt="immut",
            status="active",
        )
    )
    container.role_registry.upsert(
        RoleDefinition(
            role_id="immut_agent",
            title="Immut Agent",
            domain_pack="custom",
            capability_ids=["immut_cap"],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        )
    )
    markdown = _markdown("Idempotent Flow")
    metadata = WorkflowDefinitionMetadata(
        workflow_id="idem_flow",
        version=1,
        title="Idempotent Flow",
        domain_pack="custom",
        intent_group="custom_local",
    )
    doc = WorkflowMarkdownDocument(workflow_id="idem_flow", version=1, markdown=markdown)
    container.compiler_service.publish_from_markdown(metadata, doc, activate=True)
    container.compiler_service.publish_from_markdown(metadata, doc, activate=True)
    assert container.workflow_registry.get_version("idem_flow", 1) is not None
