from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from loom.models import (
    CapabilityDefinition,
    MemoryGroupDefinition,
    MemoryGroupMembership,
    MemoryRoleEdge,
    Organization,
    PolicyDefinition,
    PromptProfile,
    RoleDefinition,
    WorkflowDefinitionMetadata,
    WorkflowMarkdownDocument,
)


def load_bundle_spec(path: str) -> tuple[dict[str, Any], Path]:
    source = Path(path)
    if not source.exists():
        raise ValueError(f"spec file not found: {source}")
    loaded = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"spec file must contain a YAML object: {source}")
    return loaded, source.parent


def apply_bundle_spec(
    container,
    spec: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "organization": False,
        "capabilities": 0,
        "policies": 0,
        "prompts": 0,
        "agents": 0,
        "memory_groups": 0,
        "memory_memberships": 0,
        "memory_edges": 0,
        "workflows": 0,
    }
    target_org_id = "default"

    organization = spec.get("organization")
    if organization:
        org_id = str(organization.get("org_id", "default"))
        target_org_id = org_id
        current = container.repositories.organization.get_or_create(org_id)
        org = Organization(
            org_id=org_id,
            name=organization.get("name", current.name),
            litellm_base_url=organization.get("litellm_base_url", current.litellm_base_url),
            litellm_api_key=organization.get("litellm_api_key", current.litellm_api_key),
            litellm_default_model=organization.get("litellm_default_model", current.litellm_default_model),
            openai_api_key=organization.get("openai_api_key", current.openai_api_key),
            openai_model=organization.get("openai_model", current.openai_model),
            opencode_enabled=organization.get("opencode_enabled", current.opencode_enabled),
            opencode_cmd=organization.get("opencode_cmd", current.opencode_cmd),
        )
        container.repositories.organization.upsert(org)
        summary["organization"] = True

    for capability in spec.get("capabilities", []):
        container.capability_registry.upsert(CapabilityDefinition(**capability))
        summary["capabilities"] += 1

    for policy in spec.get("policies", []):
        container.policy_registry.upsert(PolicyDefinition(**policy))
        summary["policies"] += 1

    for prompt in spec.get("prompts", []):
        container.prompt_registry.upsert(PromptProfile(**prompt))
        summary["prompts"] += 1

    for role in spec.get("agents", []):
        container.role_registry.upsert(RoleDefinition(**role))
        summary["agents"] += 1

    for group in spec.get("memory_groups", []):
        payload = dict(group)
        if not payload.get("organization_id") or payload.get("organization_id") == "default":
            payload["organization_id"] = target_org_id
        container.memory_group_registry.upsert(MemoryGroupDefinition(**payload))
        summary["memory_groups"] += 1

    for membership in spec.get("memory_memberships", []):
        payload = dict(membership)
        if not payload.get("organization_id") or payload.get("organization_id") == "default":
            payload["organization_id"] = target_org_id
        container.memory_membership_registry.upsert(MemoryGroupMembership(**payload))
        summary["memory_memberships"] += 1

    for edge in spec.get("memory_edges", []):
        payload = dict(edge)
        if not payload.get("organization_id") or payload.get("organization_id") == "default":
            payload["organization_id"] = target_org_id
        container.memory_edge_registry.upsert(MemoryRoleEdge(**payload))
        summary["memory_edges"] += 1

    for workflow in spec.get("workflows", []):
        workflow_id = workflow["workflow_id"]
        version = int(workflow.get("version", 1))
        title = workflow["title"]
        domain_pack = workflow.get("domain_pack", "custom")
        intent_group = workflow["intent_group"]
        activate = bool(workflow.get("activate", True))

        markdown: str
        if workflow.get("markdown") is not None:
            markdown = str(workflow["markdown"])
        else:
            markdown_file = workflow.get("markdown_file")
            if not markdown_file:
                raise ValueError(
                    f"workflow '{workflow_id}' requires either 'markdown' or 'markdown_file' in spec"
                )
            markdown_path = Path(markdown_file)
            if not markdown_path.is_absolute():
                if base_dir is None:
                    raise ValueError(
                        f"workflow '{workflow_id}' uses relative markdown_file but no base_dir was provided"
                    )
                markdown_path = base_dir / markdown_path
            if not markdown_path.exists():
                raise ValueError(f"markdown file not found: {markdown_path}")
            markdown = markdown_path.read_text(encoding="utf-8")

        metadata = WorkflowDefinitionMetadata(
            workflow_id=workflow_id,
            version=version,
            title=title,
            domain_pack=domain_pack,
            intent_group=intent_group,
        )
        doc = WorkflowMarkdownDocument(workflow_id=workflow_id, version=version, markdown=markdown)
        container.compiler_service.publish_from_markdown(metadata, doc, activate=activate)
        summary["workflows"] += 1

    return summary


def export_bundle_spec(
    container,
    *,
    organization_id: str = "default",
    domain_pack: str | None = None,
) -> dict[str, Any]:
    org = container.repositories.organization.get_or_create(organization_id)
    roles = container.role_registry.list(status="active")
    prompts = container.prompt_registry.list(status="active")
    workflows = container.workflow_registry.list_all()

    if domain_pack:
        roles = [role for role in roles if role.domain_pack == domain_pack]
        prompts = [prompt for prompt in prompts if prompt.domain_pack == domain_pack]
        workflows = [wf for wf in workflows if (wf.get("metadata") or {}).get("domain_pack") == domain_pack]

    capability_ids: set[str] = set()
    policy_ids: set[str] = set()
    for role in roles:
        capability_ids.update(role.capability_ids)
        policy_ids.update(role.policy_ids)
    for workflow in workflows:
        compiled = workflow.get("compiled_ir") or {}
        for step in compiled.get("steps", []):
            capability_ids.update(step.get("required_capabilities", []) or [])

    role_ids = {role.role_id for role in roles}
    memory_groups = container.memory_group_registry.list(organization_id=organization_id, status="active")
    memory_memberships = container.memory_membership_registry.list(
        organization_id=organization_id,
        status="active",
    )
    memory_edges = container.memory_edge_registry.list(
        organization_id=organization_id,
        status="active",
    )
    if domain_pack:
        memory_memberships = [item for item in memory_memberships if item.role_id in role_ids]
        referenced_group_ids = {item.group_id for item in memory_memberships}
        memory_edges = [
            item
            for item in memory_edges
            if item.parent_role_id in role_ids and item.child_role_id in role_ids
        ]
        for edge in memory_edges:
            if edge.shared_group_id:
                referenced_group_ids.add(edge.shared_group_id)
        memory_groups = [item for item in memory_groups if item.group_id in referenced_group_ids]

    capabilities = [
        cap.model_dump(mode="json")
        for cap in container.capability_registry.list(status="active")
        if cap.capability_id in capability_ids
    ]
    policies = [
        pol.model_dump(mode="json")
        for pol in container.policy_registry.list(status="active")
        if pol.policy_id in policy_ids
    ]
    workflow_items = [
        {
            "workflow_id": wf["workflow_id"],
            "version": int(wf["version"]),
            "title": (wf.get("metadata") or {}).get("title", wf["workflow_id"]),
            "domain_pack": (wf.get("metadata") or {}).get("domain_pack", "custom"),
            "intent_group": (wf.get("metadata") or {}).get("intent_group", "custom_local"),
            "activate": wf.get("status") == "active",
            "markdown": wf.get("markdown", ""),
        }
        for wf in workflows
    ]

    return {
        "organization": {
            "org_id": org.org_id,
            "name": org.name,
            "litellm_base_url": org.litellm_base_url,
            "litellm_api_key": org.litellm_api_key,
            "litellm_default_model": org.litellm_default_model,
            "openai_api_key": org.openai_api_key,
            "openai_model": org.openai_model,
            "opencode_enabled": org.opencode_enabled,
            "opencode_cmd": org.opencode_cmd,
        },
        "capabilities": capabilities,
        "policies": policies,
        "prompts": [item.model_dump(mode="json") for item in prompts],
        "agents": [item.model_dump(mode="json") for item in roles],
        "memory_groups": [item.model_dump(mode="json") for item in memory_groups],
        "memory_memberships": [item.model_dump(mode="json") for item in memory_memberships],
        "memory_edges": [item.model_dump(mode="json") for item in memory_edges],
        "workflows": workflow_items,
    }
