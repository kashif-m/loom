from __future__ import annotations

import difflib
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from loom.app.bundle_ops import apply_bundle_spec, export_bundle_spec
from loom.domainpacks.docs.loader import load_docs_pack
from loom.integrations.health import connector_health
from loom.models import (
    CapabilityDefinition,
    DomainPackManifest,
    MemoryGroupDefinition,
    MemoryGroupMembership,
    MemoryRoleEdge,
    ModelDefinition,
    ModelProviderDefinition,
    Organization,
    PolicyDefinition,
    PromptProfile,
    RoleDefinition,
    ScheduleDefinition,
    ServiceModelBinding,
    TaskStatus,
)
from loom.observability.audit_log_service import AuditLogService
from loom.observability.trace_service import TraceService
from loom.ui.security import (
    UIUser,
    generate_csrf_token,
    require_role,
    ui_user_dependency,
    validate_csrf,
)


class PublishWorkflowRequest(BaseModel):
    workflow_id: str
    version: int
    title: str
    domain_pack: str
    intent_group: str
    markdown: str
    activate: bool = True


class ValidateWorkflowRequest(BaseModel):
    workflow_id: str
    version: int
    markdown: str


class IntakeRequest(BaseModel):
    request: str
    domain_pack: str = "docs"
    organization_id: str = "default"
    async_run: bool = False
    workflow_id: str | None = None
    workflow_version: int | None = None
    fanout: bool = False


class GenericDeleteResponse(BaseModel):
    ok: bool


class MemoryQueryRequest(BaseModel):
    organization_id: str = "default"
    domain_pack: str
    workflow_id: str
    workflow_version: int
    role: str = "any"
    memory_type: str = "episodic"
    active_only: bool = True


class MemoryInvalidateRequest(BaseModel):
    organization_id: str = "default"
    domain_pack: str
    workflow_id: str
    workflow_version: int
    role: str = "any"
    hard: bool = False


class IncidentRequest(BaseModel):
    severity: str
    title: str
    summary: str
    task_id: str | None = None
    workflow_id: str | None = None


class AgentBuilderRequest(BaseModel):
    role: RoleDefinition
    capabilities: list[CapabilityDefinition]
    policies: list[PolicyDefinition]
    prompt_profile: PromptProfile


class OrganizationRequest(BaseModel):
    org_id: str = "default"
    name: str
    litellm_base_url: str | None = None
    litellm_api_key: str | None = None
    litellm_default_model: str = "open-large"
    litellm_start_cmd: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    opencode_enabled: bool = False
    opencode_cmd: str = "opencode"


class OrganizationRuntimeRequest(BaseModel):
    org_id: str = "default"


class BundleApplyRequest(BaseModel):
    bundle_yaml: str


class ArtifactUpsertRequest(BaseModel):
    payload: dict[str, Any]


class DesignerDraftRequest(BaseModel):
    draft: dict[str, Any]


class DesignerBundleApplyRequest(BaseModel):
    draft: dict[str, Any] | None = None


def _csrf_dependency(settings):
    def _dep(
        x_csrf_token: str | None = Header(default=None),
        loom_csrf: str | None = Cookie(default=None),
    ) -> None:
        if settings.ui_auth_mode == "token":
            validate_csrf(x_csrf_token, loom_csrf)

    return _dep


def _stream_events(events: list[dict[str, Any]]):
    for event in events:
        yield f"event: task_event\ndata: {json.dumps(event)}\n\n"


def _workflow_diff(markdown_a: str, markdown_b: str) -> dict[str, list[str]]:
    a_lines = markdown_a.splitlines()
    b_lines = markdown_b.splitlines()
    removed = [line for line in a_lines if line not in b_lines]
    added = [line for line in b_lines if line not in a_lines]
    return {"added": added[:200], "removed": removed[:200]}


def _role_compatibility(container, role_id: str) -> dict[str, Any]:
    role = container.role_registry.get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="role not found")

    compatible = []
    incompatible = []
    for wf in container.workflow_registry.list_all():
        ir = wf.get("compiled_ir") or {}
        for step in ir.get("steps", []):
            if step.get("owned_by") != role_id:
                continue
            required = set(step.get("required_capabilities", []))
            has = set(role.capability_ids)
            if required.issubset(has):
                compatible.append({"workflow_id": wf["workflow_id"], "step_id": step.get("step_id")})
            else:
                incompatible.append(
                    {
                        "workflow_id": wf["workflow_id"],
                        "step_id": step.get("step_id"),
                        "missing": sorted(required - has),
                    }
                )

    return {
        "role_id": role_id,
        "compatible": compatible,
        "incompatible": incompatible,
    }


def _task_payload(task) -> dict[str, Any]:
    payload = task.model_dump(mode="json")
    failed_steps = []
    for step_id, ref in (task.execution_refs or {}).items():
        model_output = (ref or {}).get("model_output") or {}
        if ref and ref.get("ok") is False:
            failed_steps.append(
                {
                    "step_id": step_id,
                    "reason": model_output.get("error_code") or "STEP_EXECUTION_FAILED",
                    "detail": model_output.get("error"),
                }
            )
    payload["operator_summary"] = {
        "status": payload.get("current_status"),
        "message": payload.get("result_summary") or "task execution finished",
        "failed_steps": failed_steps,
    }
    payload["debug"] = {
        "execution_refs": payload.get("execution_refs", {}),
        "current_step_id": payload.get("current_step_id"),
    }
    return payload


def _memory_topology_graph(container, org_id: str) -> dict[str, Any]:
    groups = container.memory_group_registry.list(organization_id=org_id, status="active")
    memberships = container.memory_membership_registry.list(organization_id=org_id, status="active")
    role_edges = container.memory_edge_registry.list(organization_id=org_id, status="active")
    roles = container.role_registry.list(status="active")

    role_ids = {role.role_id for role in roles}
    group_ids = {group.group_id for group in groups}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for role in sorted(roles, key=lambda r: r.role_id):
        nodes.append(
            {
                "id": f"role:{role.role_id}",
                "kind": "role",
                "label": role.title or role.role_id,
                "role_id": role.role_id,
                "domain_pack": role.domain_pack,
            }
        )
    for group in sorted(groups, key=lambda g: g.group_id):
        nodes.append(
            {
                "id": f"group:{group.group_id}",
                "kind": "group",
                "label": group.title or group.group_id,
                "group_id": group.group_id,
                "visibility": group.visibility,
                "owner_role_id": group.owner_role_id,
            }
        )

    duplicate_keys: dict[str, int] = {}
    for membership in sorted(memberships, key=lambda m: m.membership_id or ""):
        edge_key = f"membership:{membership.group_id}:{membership.role_id}:{membership.access}"
        duplicate_keys[edge_key] = duplicate_keys.get(edge_key, 0) + 1
        edges.append(
            {
                "id": membership.membership_id,
                "kind": "membership",
                "from": f"group:{membership.group_id}",
                "to": f"role:{membership.role_id}",
                "access": membership.access,
            }
        )
    for edge in sorted(role_edges, key=lambda e: e.edge_id or ""):
        edge_key = f"role_edge:{edge.parent_role_id}:{edge.child_role_id}:{edge.shared_group_id or 'none'}"
        duplicate_keys[edge_key] = duplicate_keys.get(edge_key, 0) + 1
        edges.append(
            {
                "id": edge.edge_id,
                "kind": "role_edge",
                "from": f"role:{edge.parent_role_id}",
                "to": f"role:{edge.child_role_id}",
                "shared_group_id": edge.shared_group_id,
            }
        )

    missing_owner_roles = sorted(
        group.group_id for group in groups if group.owner_role_id and group.owner_role_id not in role_ids
    )
    orphan_memberships = sorted(
        membership.membership_id or f"{membership.group_id}:{membership.role_id}"
        for membership in memberships
        if membership.group_id not in group_ids or membership.role_id not in role_ids
    )
    invalid_edges = sorted(
        edge.edge_id or f"{edge.parent_role_id}:{edge.child_role_id}"
        for edge in role_edges
        if edge.parent_role_id not in role_ids
        or edge.child_role_id not in role_ids
        or (edge.shared_group_id and edge.shared_group_id not in group_ids)
    )
    duplicates = sorted(k for k, count in duplicate_keys.items() if count > 1)

    validation = {
        "missing_owner_roles": missing_owner_roles,
        "orphan_memberships": orphan_memberships,
        "invalid_edges": invalid_edges,
        "duplicate_edges": duplicates,
        "ok": not (missing_owner_roles or orphan_memberships or invalid_edges or duplicates),
    }
    return {
        "organization_id": org_id,
        "nodes": nodes,
        "edges": edges,
        "validation": validation,
    }


def _designer_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _designer_default_draft(container, org_id: str) -> dict[str, Any]:
    org = container.repositories.organization.get_or_create(org_id)
    roles = sorted(container.role_registry.list(status="active"), key=lambda r: r.role_id)
    workflows = sorted(container.workflow_registry.list_all(), key=lambda w: w["workflow_id"])
    groups = sorted(
        container.memory_group_registry.list(organization_id=org_id, status="active"),
        key=lambda g: g.group_id,
    )
    memberships = sorted(
        container.memory_membership_registry.list(organization_id=org_id, status="active"),
        key=lambda m: m.membership_id or "",
    )
    edges = sorted(
        container.memory_edge_registry.list(organization_id=org_id, status="active"),
        key=lambda e: e.edge_id or "",
    )

    role_layout = []
    for idx, role in enumerate(roles):
        col = idx % 4
        row = idx // 4
        role_layout.append(
            {
                "role_id": role.role_id,
                "title": role.title,
                "domain_pack": role.domain_pack,
                "capability_ids": role.capability_ids,
                "policy_ids": role.policy_ids,
                "memory_visibility": role.memory_visibility,
                "x": 40 + col * 240,
                "y": 40 + row * 140,
            }
        )

    draft_workflows: list[dict[str, Any]] = []
    for workflow in workflows:
        metadata = workflow.get("metadata") or {}
        ir = workflow.get("compiled_ir") or {}
        steps = []
        for step in ir.get("steps", []):
            transitions = step.get("transitions") or {}
            steps.append(
                {
                    "step_id": step.get("step_id"),
                    "title": step.get("title") or step.get("step_id"),
                    "owned_by": step.get("owned_by"),
                    "participants": step.get("participants", []),
                    "required_capabilities": step.get("required_capabilities", []),
                    "on_success": transitions.get("on_success", "completed"),
                    "on_blocked": transitions.get("on_blocked"),
                    "on_failure": transitions.get("on_failure"),
                    "state_partition": (step.get("memory_hints") or {}).get("state_partition"),
                }
            )
        draft_workflows.append(
            {
                "workflow_id": workflow["workflow_id"],
                "version": int(workflow["version"]),
                "title": metadata.get("title", workflow["workflow_id"]),
                "domain_pack": metadata.get("domain_pack", "custom"),
                "intent_group": metadata.get("intent_group", "custom_local"),
                "activate": workflow.get("status") == "active",
                "purpose": ir.get("purpose", "workflow purpose"),
                "required_inputs": ir.get("required_inputs", []),
                "completion_criteria": "workflow completed",
                "blocked_conditions": "blocked by validation or runtime preflight",
                "failure_conditions": "runtime execution failure",
                "rules": ir.get("rules", []),
                "steps": steps,
            }
        )

    return {
        "organization": {
            "org_id": org.org_id,
            "name": org.name,
            "litellm_base_url": org.litellm_base_url,
            "litellm_default_model": org.litellm_default_model,
            "opencode_enabled": org.opencode_enabled,
            "opencode_cmd": org.opencode_cmd,
        },
        "roles": role_layout,
        "memory_topology": {
            "groups": [item.model_dump(mode="json") for item in groups],
            "memberships": [item.model_dump(mode="json") for item in memberships],
            "edges": [item.model_dump(mode="json") for item in edges],
        },
        "workflows": draft_workflows,
    }


def _designer_draft_record(container, org_id: str) -> dict[str, Any]:
    row = container.repositories.designer_drafts.get(org_id)
    if row:
        data = dict(row["data"])
        data.setdefault("org_id", org_id)
        data.setdefault("version", 1)
        data.setdefault("history", [])
        data.setdefault("updated_at", _designer_now_iso())
        return data
    return {
        "org_id": org_id,
        "version": 1,
        "updated_at": _designer_now_iso(),
        "history": [],
        "draft": _designer_default_draft(container, org_id),
    }


def _validate_designer_draft(container, draft: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    roles = draft.get("roles") or []
    role_ids = [str(role.get("role_id", "")).strip() for role in roles]
    role_id_set = {role_id for role_id in role_ids if role_id}
    if len(role_id_set) != len([item for item in role_ids if item]):
        errors.append("duplicate role_id values in designer roles")
    if any(not role_id for role_id in role_ids):
        errors.append("all roles must define role_id")

    groups = (draft.get("memory_topology") or {}).get("groups") or []
    group_ids = [str(group.get("group_id", "")).strip() for group in groups]
    group_id_set = {group_id for group_id in group_ids if group_id}
    if len(group_id_set) != len([item for item in group_ids if item]):
        errors.append("duplicate memory group_id values")

    for group in groups:
        owner = str(group.get("owner_role_id") or "").strip()
        if owner and owner not in role_id_set:
            errors.append(f"group '{group.get('group_id')}' references missing owner role '{owner}'")

    memberships = (draft.get("memory_topology") or {}).get("memberships") or []
    for membership in memberships:
        group_id = str(membership.get("group_id", "")).strip()
        role_id = str(membership.get("role_id", "")).strip()
        if group_id not in group_id_set:
            errors.append(f"membership references missing group '{group_id}'")
        if role_id not in role_id_set:
            errors.append(f"membership references missing role '{role_id}'")

    role_edges = (draft.get("memory_topology") or {}).get("edges") or []
    for edge in role_edges:
        parent = str(edge.get("parent_role_id", "")).strip()
        child = str(edge.get("child_role_id", "")).strip()
        shared_group = str(edge.get("shared_group_id") or "").strip()
        if parent not in role_id_set:
            errors.append(f"edge references missing parent role '{parent}'")
        if child not in role_id_set:
            errors.append(f"edge references missing child role '{child}'")
        if shared_group and shared_group not in group_id_set:
            errors.append(f"edge references missing shared group '{shared_group}'")

    capability_map = {cap.capability_id: cap for cap in container.capability_registry.list(status="active")}
    workflows = draft.get("workflows") or []
    workflow_ids = [str(workflow.get("workflow_id", "")).strip() for workflow in workflows]
    if len({item for item in workflow_ids if item}) != len([item for item in workflow_ids if item]):
        errors.append("duplicate workflow_id values in draft")
    for workflow in workflows:
        workflow_id = str(workflow.get("workflow_id", "")).strip()
        if not workflow_id:
            errors.append("workflow entry missing workflow_id")
            continue
        steps = workflow.get("steps") or []
        step_ids = [str(step.get("step_id", "")).strip() for step in steps]
        step_id_set = {item for item in step_ids if item}
        if len(step_id_set) != len([item for item in step_ids if item]):
            errors.append(f"workflow '{workflow_id}' has duplicate step_id values")
        for step in steps:
            step_id = str(step.get("step_id", "")).strip()
            if not step_id:
                errors.append(f"workflow '{workflow_id}' has step missing step_id")
                continue
            owner = str(step.get("owned_by", "")).strip()
            if owner not in role_id_set:
                errors.append(f"workflow '{workflow_id}' step '{step_id}' owner '{owner}' is missing")
            for cap_id in step.get("required_capabilities", []) or []:
                cap_key = str(cap_id).strip()
                if cap_key and cap_key not in capability_map:
                    errors.append(
                        f"workflow '{workflow_id}' step '{step_id}' references missing capability '{cap_key}'"
                    )
            target = str(step.get("on_success", "completed")).strip()
            if target not in {"completed", "blocked", "failed"} and target not in step_id_set:
                warnings.append(
                    f"workflow '{workflow_id}' step '{step_id}' on_success target '{target}' is unresolved"
                )

            workflow_domain = str(workflow.get("domain_pack") or "").strip()
            owner_role = next((role for role in roles if role.get("role_id") == owner), None)
            if owner_role and workflow_domain:
                role_domain = str(owner_role.get("domain_pack") or "").strip()
                if role_domain and role_domain != workflow_domain:
                    warnings.append(
                        f"workflow '{workflow_id}' step '{step_id}' owner '{owner}' domain '{role_domain}' "
                        f"differs from workflow domain '{workflow_domain}'"
                    )

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def _designer_workflow_markdown(workflow: dict[str, Any]) -> str:
    lines = [
        "## Title",
        str(workflow.get("title") or workflow.get("workflow_id") or "Untitled Workflow"),
        "",
        "## Purpose",
        str(workflow.get("purpose") or "Generated workflow purpose."),
        "",
        "## Trigger",
        str(workflow.get("intent_group") or "custom_local"),
        "",
        "## Required Inputs",
    ]
    for item in workflow.get("required_inputs", []) or ["request"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Steps"])

    steps = workflow.get("steps") or []
    for idx, step in enumerate(steps, start=1):
        title = str(step.get("title") or step.get("step_id") or f"Step {idx}")
        lines.append(f"{idx}. {title}")
        lines.append(f"- id: {step.get('step_id')}")
        lines.append(f"- owned_by: {step.get('owned_by')}")
        participants = ",".join(step.get("participants") or [])
        if participants:
            lines.append(f"- participants: {participants}")
        caps = ",".join(step.get("required_capabilities") or [])
        if caps:
            lines.append(f"- required_capabilities: {caps}")
        if step.get("state_partition"):
            lines.append(f"- state_partition: {step.get('state_partition')}")
        on_success = step.get("on_success") or ("completed" if idx == len(steps) else "")
        if on_success:
            lines.append(f"- on_success: {on_success}")
        if step.get("on_blocked"):
            lines.append(f"- on_blocked: {step.get('on_blocked')}")
        if step.get("on_failure"):
            lines.append(f"- on_failure: {step.get('on_failure')}")
        lines.append("")

    lines.extend(
        [
            "## Completion Criteria",
            str(workflow.get("completion_criteria") or "Workflow reaches terminal completion state."),
            "",
            "## Blocked Conditions",
            str(workflow.get("blocked_conditions") or "Execution preflight or policy checks block progress."),
            "",
            "## Failure Conditions",
            str(workflow.get("failure_conditions") or "Step execution fails after retries."),
            "",
            "## Rules",
        ]
    )
    rules = workflow.get("rules") or ["Follow configured workflow and policy constraints."]
    for rule in rules:
        lines.append(f"- {rule}")
    return "\n".join(lines).strip() + "\n"


def _bundle_from_designer_draft(container, org_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    org = container.repositories.organization.get_or_create(org_id)
    organization = dict(draft.get("organization") or {})
    organization.setdefault("org_id", org_id)
    organization.setdefault("name", org.name)
    organization.setdefault("litellm_base_url", org.litellm_base_url)
    organization.setdefault("litellm_api_key", org.litellm_api_key)
    organization.setdefault("litellm_default_model", org.litellm_default_model)
    organization.setdefault("openai_api_key", org.openai_api_key)
    organization.setdefault("openai_model", org.openai_model)
    organization.setdefault("opencode_enabled", org.opencode_enabled)
    organization.setdefault("opencode_cmd", org.opencode_cmd)

    roles = []
    capability_ids: set[str] = set()
    policy_ids: set[str] = set()
    for role in draft.get("roles") or []:
        item = {
            "role_id": role.get("role_id"),
            "title": role.get("title") or role.get("role_id"),
            "domain_pack": role.get("domain_pack") or "custom",
            "capability_ids": sorted(set(role.get("capability_ids") or [])),
            "policy_ids": sorted(set(role.get("policy_ids") or [])),
            "memory_visibility": sorted(set(role.get("memory_visibility") or [])),
            "status": "active",
        }
        roles.append(item)
        capability_ids.update(item["capability_ids"])
        policy_ids.update(item["policy_ids"])

    workflows = []
    for workflow in draft.get("workflows") or []:
        workflow_entry = {
            "workflow_id": workflow.get("workflow_id"),
            "version": int(workflow.get("version") or 1),
            "title": workflow.get("title") or workflow.get("workflow_id"),
            "domain_pack": workflow.get("domain_pack") or "custom",
            "intent_group": workflow.get("intent_group") or "custom_local",
            "activate": bool(workflow.get("activate", True)),
            "markdown": _designer_workflow_markdown(workflow),
        }
        for step in workflow.get("steps") or []:
            capability_ids.update(step.get("required_capabilities") or [])
        workflows.append(workflow_entry)

    capability_defs = {
        cap.capability_id: cap.model_dump(mode="json")
        for cap in container.capability_registry.list(status="active")
    }
    policy_defs = {
        policy.policy_id: policy.model_dump(mode="json")
        for policy in container.policy_registry.list(status="active")
    }
    prompt_defs = {
        prompt.profile_id: prompt.model_dump(mode="json")
        for prompt in container.prompt_registry.list(status="active")
    }

    capabilities = sorted(
        [capability_defs[cid] for cid in capability_ids if cid in capability_defs],
        key=lambda item: item["capability_id"],
    )
    policies = sorted(
        [policy_defs[pid] for pid in policy_ids if pid in policy_defs],
        key=lambda item: item["policy_id"],
    )
    prompts = sorted(prompt_defs.values(), key=lambda item: (item.get("domain_pack", ""), item.get("profile_id", "")))

    memory_topology = draft.get("memory_topology") or {}
    memory_groups = sorted(memory_topology.get("groups") or [], key=lambda item: item.get("group_id", ""))
    memory_groups = [
        {
            **item,
            "organization_id": org_id,
            "status": item.get("status", "active"),
        }
        for item in memory_groups
    ]
    memory_memberships = sorted(
        memory_topology.get("memberships") or [],
        key=lambda item: item.get("membership_id") or f"{item.get('group_id')}:{item.get('role_id')}",
    )
    memory_memberships = [
        {
            **item,
            "organization_id": org_id,
            "status": item.get("status", "active"),
        }
        for item in memory_memberships
    ]
    memory_edges = sorted(
        memory_topology.get("edges") or [],
        key=lambda item: item.get("edge_id")
        or f"{item.get('parent_role_id')}:{item.get('child_role_id')}:{item.get('shared_group_id')}",
    )
    memory_edges = [
        {
            **item,
            "organization_id": org_id,
            "status": item.get("status", "active"),
        }
        for item in memory_edges
    ]

    return {
        "organization": organization,
        "capabilities": capabilities,
        "policies": policies,
        "prompts": prompts,
        "agents": sorted(roles, key=lambda item: item["role_id"]),
        "memory_groups": memory_groups,
        "memory_memberships": memory_memberships,
        "memory_edges": memory_edges,
        "workflows": sorted(workflows, key=lambda item: (item["workflow_id"], item["version"])),
    }


def _bundle_drift(current_spec: dict[str, Any], generated_spec: dict[str, Any]) -> dict[str, Any]:
    current_yaml = yaml.safe_dump(current_spec, sort_keys=False)
    generated_yaml = yaml.safe_dump(generated_spec, sort_keys=False)
    diff = list(
        difflib.unified_diff(
            current_yaml.splitlines(),
            generated_yaml.splitlines(),
            fromfile="current",
            tofile="generated",
            lineterm="",
        )
    )
    return {
        "same": current_yaml == generated_yaml,
        "diff": diff[:400],
        "current_hash": hashlib.sha256(current_yaml.encode("utf-8")).hexdigest(),
        "generated_hash": hashlib.sha256(generated_yaml.encode("utf-8")).hexdigest(),
    }


def build_ui_router(container) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["ui-api"])
    user_dep = ui_user_dependency(container.settings)
    csrf_dep = _csrf_dependency(container.settings)
    user_dependency = Depends(user_dep)

    @router.get("/auth/me")
    def auth_me(user: UIUser = user_dependency) -> dict:
        return {"identity": user.identity, "role": user.role, "auth_mode": container.settings.ui_auth_mode}

    @router.get("/auth/csrf")
    def auth_csrf(user: UIUser = user_dependency):
        token = generate_csrf_token()
        resp = JSONResponse({"csrf": token, "role": user.role})
        resp.set_cookie("loom_csrf", token, httponly=False, samesite="strict")
        return resp

    @router.get("/organization")
    def get_organization(org_id: str = "default", user: UIUser = user_dependency) -> dict:
        _ = user
        org = container.repositories.organization.get_or_create(org_id)
        return org.model_dump(mode="json")

    @router.get("/organizations")
    def list_organizations(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [org.model_dump(mode="json") for org in container.repositories.organization.list()]

    @router.post("/organization", dependencies=[Depends(csrf_dep)])
    def update_organization(payload: OrganizationRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        org = Organization(
            org_id=payload.org_id,
            name=payload.name,
            litellm_base_url=payload.litellm_base_url,
            litellm_api_key=payload.litellm_api_key,
            litellm_default_model=payload.litellm_default_model,
            litellm_start_cmd=payload.litellm_start_cmd,
            openai_api_key=payload.openai_api_key,
            openai_model=payload.openai_model,
            opencode_enabled=payload.opencode_enabled,
            opencode_cmd=payload.opencode_cmd,
        )
        container.repositories.organization.upsert(org)
        return org.model_dump(mode="json")

    @router.post("/bundle/apply", dependencies=[Depends(csrf_dep)])
    def apply_bundle(payload: BundleApplyRequest, org_id: str = "default", user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        try:
            spec = yaml.safe_load(payload.bundle_yaml) or {}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=f"invalid YAML: {exc}") from exc
        if not isinstance(spec, dict):
            raise HTTPException(status_code=400, detail="bundle YAML must parse to an object")
        if "organization" in spec and isinstance(spec["organization"], dict):
            spec["organization"].setdefault("org_id", org_id)
        try:
            summary = apply_bundle_spec(container, spec, base_dir=None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "summary": summary}

    @router.get("/bundle/export")
    def export_bundle(
        org_id: str = "default",
        domain_pack: str | None = None,
        user: UIUser = user_dependency,
    ) -> Response:
        _ = user
        spec = export_bundle_spec(container, organization_id=org_id, domain_pack=domain_pack)
        return Response(content=yaml.safe_dump(spec, sort_keys=False), media_type="application/x-yaml")

    @router.get("/designer/draft")
    def get_designer_draft(org_id: str = "default", user: UIUser = user_dependency) -> dict:
        _ = user
        return _designer_draft_record(container, org_id)

    @router.put("/designer/draft", dependencies=[Depends(csrf_dep)])
    def put_designer_draft(
        payload: DesignerDraftRequest,
        org_id: str = "default",
        user: UIUser = user_dependency,
    ) -> dict:
        require_role(user, "operator")
        current = _designer_draft_record(container, org_id)
        next_version = int(current.get("version", 0)) + 1
        now = _designer_now_iso()
        history = list(current.get("history", []))
        history.append(
            {
                "version": current.get("version", 1),
                "updated_at": current.get("updated_at"),
                "draft": current.get("draft", {}),
            }
        )
        validation = _validate_designer_draft(container, payload.draft)
        record = {
            "org_id": org_id,
            "version": next_version,
            "updated_at": now,
            "history": history[-20:],
            "draft": payload.draft,
            "validation": validation,
        }
        container.repositories.designer_drafts.upsert(
            org_id,
            record,
            status="active",
            version=next_version,
        )
        return record

    @router.post("/designer/validate")
    def validate_designer_draft(
        payload: DesignerDraftRequest | None = None,
        org_id: str = "default",
        user: UIUser = user_dependency,
    ) -> dict:
        _ = user
        draft = payload.draft if payload else _designer_draft_record(container, org_id).get("draft", {})
        validation = _validate_designer_draft(container, draft)
        return {"organization_id": org_id, **validation}

    @router.post("/designer/bundle/generate")
    def generate_designer_bundle(
        payload: DesignerBundleApplyRequest | None = None,
        org_id: str = "default",
        user: UIUser = user_dependency,
    ) -> dict:
        _ = user
        draft = payload.draft if payload and payload.draft is not None else _designer_draft_record(container, org_id).get(
            "draft", {}
        )
        validation = _validate_designer_draft(container, draft)
        generated = _bundle_from_designer_draft(container, org_id, draft)
        current = export_bundle_spec(container, organization_id=org_id, domain_pack=None)
        drift = _bundle_drift(current, generated)
        return {
            "ok": validation["ok"],
            "organization_id": org_id,
            "validation": validation,
            "bundle": generated,
            "bundle_yaml": yaml.safe_dump(generated, sort_keys=False),
            "drift": drift,
        }

    @router.post("/designer/bundle/apply", dependencies=[Depends(csrf_dep)])
    def apply_designer_bundle(
        payload: DesignerBundleApplyRequest | None = None,
        org_id: str = "default",
        user: UIUser = user_dependency,
    ) -> dict:
        require_role(user, "operator")
        draft = payload.draft if payload and payload.draft is not None else _designer_draft_record(container, org_id).get(
            "draft", {}
        )
        validation = _validate_designer_draft(container, draft)
        if not validation["ok"]:
            raise HTTPException(status_code=400, detail={"validation": validation})
        generated = _bundle_from_designer_draft(container, org_id, draft)
        summary = apply_bundle_spec(container, generated, base_dir=None)
        current = export_bundle_spec(container, organization_id=org_id, domain_pack=None)
        drift = _bundle_drift(current, generated)
        return {
            "ok": True,
            "organization_id": org_id,
            "summary": summary,
            "bundle_yaml": yaml.safe_dump(generated, sort_keys=False),
            "drift": drift,
        }

    @router.get("/integrations/status")
    def integration_status(org_id: str = "default", user: UIUser = user_dependency) -> dict:
        _ = user
        org = container.repositories.organization.get_or_create(org_id)
        effective_opencode_cmd = org.opencode_cmd or container.settings.opencode_cmd
        commands = {
            "git": shutil.which("git") is not None,
            "gh": shutil.which("gh") is not None,
            "plantuml": shutil.which("plantuml") is not None,
            "node": shutil.which("node") is not None,
            "java": shutil.which("java") is not None,
            effective_opencode_cmd: shutil.which(effective_opencode_cmd) is not None,
        }
        litellm_configured = bool(org.litellm_base_url and org.litellm_api_key)
        openai_configured = bool(org.openai_api_key)
        return {
            "organization": {
                "org_id": org.org_id,
                "name": org.name,
            },
            "graphiti": {
                "enabled": container.settings.graphiti_enabled,
                "base_url": container.settings.graphiti_base_url,
            },
            "openclaw": {"enabled": container.settings.openclaw_enabled},
            "openai": {
                "enabled": openai_configured or container.settings.openai_enabled,
                "configured": openai_configured,
                "model": org.openai_model or container.settings.openai_model,
            },
            "litellm": {
                "enabled": litellm_configured or container.settings.litellm_enabled,
                "configured": litellm_configured,
                "base_url": org.litellm_base_url or container.settings.litellm_base_url,
                "default_model": org.litellm_default_model or container.settings.litellm_default_model,
                "start_cmd": org.litellm_start_cmd or container.settings.litellm_start_cmd,
            },
            "langsmith": {
                "enabled": container.settings.langsmith_enabled,
                "project": container.settings.langsmith_project,
            },
            "opencode": {
                "enabled": org.opencode_enabled or container.settings.opencode_enabled,
                "cmd": effective_opencode_cmd,
                "available": commands.get(effective_opencode_cmd, False),
            },
            "commands": commands,
            "connectors": commands,  # backwards-compatible alias
            "database_url": container.settings.database_url,
            "integration_profile": container.settings.integration_profile,
            "model_routing": {
                "step_execution": container.model_router.resolve_public("step_execution", organization_id=org.org_id),
            },
            "runtime": container.organization_runtime_service.status(org.org_id),
        }

    @router.get("/organization/runtime")
    def organization_runtime_status(org_id: str = "default", user: UIUser = user_dependency) -> dict:
        _ = user
        return container.organization_runtime_service.status(org_id)

    @router.post("/organization/runtime/run", dependencies=[Depends(csrf_dep)])
    def organization_runtime_run(payload: OrganizationRuntimeRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        return container.organization_runtime_service.run(payload.org_id)

    @router.post("/organization/runtime/stop", dependencies=[Depends(csrf_dep)])
    def organization_runtime_stop(payload: OrganizationRuntimeRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        return container.organization_runtime_service.stop(payload.org_id)

    @router.get("/integrations/health")
    def integrations_health(user: UIUser = user_dependency) -> dict:
        _ = user
        return connector_health(container.settings)

    @router.get("/integrations/bindings")
    def integrations_bindings(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return container.repositories.integration_bindings.list(status="active")

    @router.post("/bootstrap/docs-pack", dependencies=[Depends(csrf_dep)])
    def bootstrap_docs_pack(user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        load_docs_pack(container)
        return {"ok": True}

    @router.get("/workflows")
    def list_workflows(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return container.workflow_registry.list_all()

    @router.get("/workflows/{workflow_id}/versions")
    def workflow_versions(workflow_id: str, user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return container.workflow_registry.list_versions(workflow_id)

    @router.post("/workflows/validate")
    def validate_workflow(req: ValidateWorkflowRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        parsed = container.parser.parse(req.markdown)
        compiled = container.compiler.compile(req.workflow_id, req.version, parsed)
        errors = container.ir_validator.validate(compiled)
        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "compiled_ir": compiled.model_dump(mode="json"),
        }

    @router.post("/workflows/publish", dependencies=[Depends(csrf_dep)])
    def publish_workflow(req: PublishWorkflowRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        from loom.models import WorkflowDefinitionMetadata, WorkflowMarkdownDocument

        metadata = WorkflowDefinitionMetadata(
            workflow_id=req.workflow_id,
            version=req.version,
            title=req.title,
            domain_pack=req.domain_pack,
            intent_group=req.intent_group,
        )
        doc = WorkflowMarkdownDocument(
            workflow_id=req.workflow_id,
            version=req.version,
            markdown=req.markdown,
        )
        container.compiler_service.publish_from_markdown(metadata, doc, activate=req.activate)
        return {"ok": True}

    @router.post("/workflows/{workflow_id}/{version}/activate", dependencies=[Depends(csrf_dep)])
    def activate_workflow(workflow_id: str, version: int, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.workflow_registry.activate_version(workflow_id, version)
        return {"ok": True}

    @router.post("/workflows/{workflow_id}/{version}/deprecate", dependencies=[Depends(csrf_dep)])
    def deprecate_workflow(workflow_id: str, version: int, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.workflow_registry.deprecate_version(workflow_id, version)
        return {"ok": True}

    @router.post("/workflows/{workflow_id}/{version}/archive", dependencies=[Depends(csrf_dep)])
    def archive_workflow(workflow_id: str, version: int, user: UIUser = user_dependency) -> dict:
        require_role(user, "admin")
        container.workflow_registry.archive_version(workflow_id, version)
        return {"ok": True}

    @router.post("/workflows/{workflow_id}/{version}/rollback", dependencies=[Depends(csrf_dep)])
    def rollback_workflow(workflow_id: str, version: int, user: UIUser = user_dependency) -> dict:
        require_role(user, "admin")
        container.workflow_registry.rollback(workflow_id, version)
        return {"ok": True}

    @router.get("/workflows/{workflow_id}/diff/{from_version}/{to_version}")
    def workflow_diff(workflow_id: str, from_version: int, to_version: int, user: UIUser = user_dependency) -> dict:
        _ = user
        from_w = container.workflow_registry.get_version(workflow_id, from_version)
        to_w = container.workflow_registry.get_version(workflow_id, to_version)
        if not from_w or not to_w:
            raise HTTPException(status_code=404, detail="workflow version not found")
        return {
            "markdown": _workflow_diff(from_w["markdown"], to_w["markdown"]),
            "ir_from": from_w.get("compiled_ir") or {},
            "ir_to": to_w.get("compiled_ir") or {},
        }

    @router.get("/roles")
    def list_roles(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.role_registry.list()]

    @router.post("/roles", dependencies=[Depends(csrf_dep)])
    def upsert_role(payload: RoleDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.role_registry.upsert(payload)
        return {"ok": True}

    @router.delete("/roles/{role_id}", response_model=GenericDeleteResponse, dependencies=[Depends(csrf_dep)])
    def delete_role(role_id: str, user: UIUser = user_dependency) -> GenericDeleteResponse:
        require_role(user, "operator")
        container.role_registry.retire(role_id)
        return GenericDeleteResponse(ok=True)

    @router.get("/capabilities")
    def list_capabilities(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.capability_registry.list()]

    @router.post("/capabilities", dependencies=[Depends(csrf_dep)])
    def upsert_capability(payload: CapabilityDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.capability_registry.upsert(payload)
        return {"ok": True}

    @router.get("/policies")
    def list_policies(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.policy_registry.list()]

    @router.post("/policies", dependencies=[Depends(csrf_dep)])
    def upsert_policy(payload: PolicyDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.policy_registry.upsert(payload)
        return {"ok": True}

    @router.get("/prompts")
    def list_prompts(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.prompt_registry.list()]

    @router.post("/prompts", dependencies=[Depends(csrf_dep)])
    def upsert_prompt(payload: PromptProfile, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.prompt_registry.upsert(payload)
        return {"ok": True}

    @router.get("/model-providers")
    def list_model_providers(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.model_provider_registry.list()]

    @router.post("/model-providers", dependencies=[Depends(csrf_dep)])
    def upsert_model_provider(payload: ModelProviderDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.model_provider_registry.upsert(payload)
        return {"ok": True}

    @router.delete(
        "/model-providers/{provider_id}",
        response_model=GenericDeleteResponse,
        dependencies=[Depends(csrf_dep)],
    )
    def delete_model_provider(provider_id: str, user: UIUser = user_dependency) -> GenericDeleteResponse:
        require_role(user, "admin")
        for model in container.model_registry.list():
            if model.provider_id == provider_id:
                raise HTTPException(status_code=409, detail="provider still referenced by model")
        container.model_provider_registry.delete(provider_id)
        return GenericDeleteResponse(ok=True)

    @router.get("/models")
    def list_models(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.model_registry.list()]

    @router.post("/models", dependencies=[Depends(csrf_dep)])
    def upsert_model(payload: ModelDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.model_registry.upsert(payload)
        return {"ok": True}

    @router.delete("/models/{model_id}", response_model=GenericDeleteResponse, dependencies=[Depends(csrf_dep)])
    def delete_model(model_id: str, user: UIUser = user_dependency) -> GenericDeleteResponse:
        require_role(user, "admin")
        for binding in container.service_model_registry.list():
            if binding.model_id == model_id:
                raise HTTPException(status_code=409, detail="model still referenced by service binding")
        container.model_registry.delete(model_id)
        return GenericDeleteResponse(ok=True)

    @router.get("/service-models")
    def list_service_models(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.service_model_registry.list()]

    @router.post("/service-models", dependencies=[Depends(csrf_dep)])
    def upsert_service_model(payload: ServiceModelBinding, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.service_model_registry.upsert(payload)
        return {"ok": True}

    @router.delete(
        "/service-models/{service_id}",
        response_model=GenericDeleteResponse,
        dependencies=[Depends(csrf_dep)],
    )
    def delete_service_model(service_id: str, user: UIUser = user_dependency) -> GenericDeleteResponse:
        require_role(user, "admin")
        container.service_model_registry.delete(service_id)
        return GenericDeleteResponse(ok=True)

    @router.get("/service-models/resolve/{service_id}")
    def resolve_service_model(
        service_id: str,
        org_id: str = "default",
        role_id: str | None = None,
        user: UIUser = user_dependency,
    ) -> dict:
        _ = user
        resolved = container.model_router.resolve_public(service_id, organization_id=org_id, role_id=role_id)
        if not resolved:
            raise HTTPException(status_code=404, detail="no model routing for service")
        return resolved

    @router.get("/domainpacks")
    def list_domainpacks(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.domain_pack_registry.list()]

    @router.post("/domainpacks", dependencies=[Depends(csrf_dep)])
    def upsert_domainpack(payload: DomainPackManifest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.domain_pack_registry.upsert(payload)
        return {"ok": True}

    @router.get("/schedules")
    def list_schedules(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [item.model_dump(mode="json") for item in container.schedule_registry.list()]

    @router.post("/schedules", dependencies=[Depends(csrf_dep)])
    def upsert_schedule(payload: ScheduleDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.schedule_registry.upsert(payload)
        container.scheduler_service.reload()
        return {"ok": True}

    @router.delete("/schedules/{schedule_id}", response_model=GenericDeleteResponse, dependencies=[Depends(csrf_dep)])
    def delete_schedule(schedule_id: str, user: UIUser = user_dependency) -> GenericDeleteResponse:
        require_role(user, "operator")
        container.schedule_registry.delete(schedule_id)
        container.scheduler_service.reload()
        return GenericDeleteResponse(ok=True)

    @router.post("/agents/builder", dependencies=[Depends(csrf_dep)])
    def agent_builder(payload: AgentBuilderRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        if payload.role.preferred_model_id and not container.model_registry.get(payload.role.preferred_model_id):
            raise HTTPException(status_code=400, detail="preferred_model_id does not exist")
        for capability in payload.capabilities:
            container.capability_registry.upsert(capability)
        for policy in payload.policies:
            container.policy_registry.upsert(policy)
        container.prompt_registry.upsert(payload.prompt_profile)
        container.role_registry.upsert(payload.role)
        return {
            "ok": True,
            "compatibility": _role_compatibility(container, payload.role.role_id),
        }

    @router.get("/agents/compat/{role_id}")
    def agent_compatibility(role_id: str, user: UIUser = user_dependency) -> dict:
        _ = user
        return _role_compatibility(container, role_id)

    @router.get("/tasks")
    def list_tasks(organization_id: str | None = None, user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [_task_payload(t) for t in container.repositories.tasks.list(organization_id=organization_id)]

    @router.get("/tasks/fanout/{fanout_group}/summary")
    def fanout_summary(fanout_group: str, user: UIUser = user_dependency) -> dict:
        _ = user
        return container.intake_service.fanin_summary(fanout_group)

    @router.post("/tasks/intake", dependencies=[Depends(csrf_dep)])
    def intake_task(req: IntakeRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        if req.fanout:
            tasks = container.intake_service.intake_many(
                req.request,
                domain_pack=req.domain_pack,
                workflow_id=req.workflow_id,
                workflow_version=req.workflow_version,
                organization_id=req.organization_id,
            )
            payload: dict[str, Any] = {"tasks": [_task_payload(t) for t in tasks]}
            if req.async_run and container.settings.async_workers_enabled:
                jobs = []
                for task in tasks:
                    if not task.workflow_id:
                        continue
                    job = container.async_worker.submit_task(task.task_id)
                    jobs.append({"task_id": task.task_id, "job_id": job.job_id, "status": job.status})
                if jobs:
                    payload["jobs"] = jobs
            return payload

        if req.workflow_id:
            task = container.intake_service.intake_with_workflow(
                req.request,
                workflow_id=req.workflow_id,
                workflow_version=req.workflow_version,
                domain_pack=req.domain_pack,
                organization_id=req.organization_id,
            )
        else:
            task = container.intake_service.intake(
                req.request,
                domain_pack=req.domain_pack,
                organization_id=req.organization_id,
            )
        if req.async_run and container.settings.async_workers_enabled and task.workflow_id:
            job = container.async_worker.submit_task(task.task_id)
            return {
                "task": _task_payload(task),
                "job": {"job_id": job.job_id, "status": job.status},
            }
        return {"task": _task_payload(task)}

    @router.post("/tasks/{task_id}/run", dependencies=[Depends(csrf_dep)])
    def run_task(task_id: str, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        task = container.repositories.tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        if not task.workflow_id:
            raise HTTPException(status_code=400, detail="workflow not selected")
        task = container.execution_coordinator.run_task(task)
        container.repositories.tasks.update(task)
        return _task_payload(task)

    @router.post("/tasks/{task_id}/retry", dependencies=[Depends(csrf_dep)])
    def retry_task(task_id: str, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        task = container.repositories.tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        task.current_status = TaskStatus.workflow_selected
        container.repositories.tasks.update(task)
        task = container.execution_coordinator.run_task(task)
        container.repositories.tasks.update(task)
        return _task_payload(task)

    @router.post("/tasks/{task_id}/mark/{status}", dependencies=[Depends(csrf_dep)])
    def mark_task(task_id: str, status: str, reason: str = "", user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        if status not in {"blocked", "failed"}:
            raise HTTPException(status_code=400, detail="status must be blocked or failed")
        task = container.repositories.tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        task.current_status = TaskStatus(status)
        task.result_summary = reason or f"manually marked {status}"
        container.repositories.tasks.update(task)
        return _task_payload(task)

    @router.get("/tasks/{task_id}/trace")
    def task_trace(task_id: str, user: UIUser = user_dependency) -> dict:
        _ = user
        return TraceService(AuditLogService(container.repositories), container.langsmith_adapter).trace_for_task(task_id)

    @router.get("/tasks/{task_id}/events")
    def task_events(task_id: str, user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return AuditLogService(container.repositories).list_task_events(task_id)

    @router.get("/tasks/{task_id}/events/stream")
    def task_events_stream(task_id: str, user: UIUser = user_dependency):
        _ = user
        events = AuditLogService(container.repositories).list_task_events(task_id)
        return StreamingResponse(_stream_events(events), media_type="text/event-stream")

    @router.get("/audit/events")
    def audit_events(
        task_id: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
        user: UIUser = user_dependency,
    ) -> list[dict]:
        _ = user
        return AuditLogService(container.repositories).list_events(
            task_id=task_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )

    @router.post("/memory/query")
    def memory_query(payload: MemoryQueryRequest, user: UIUser = user_dependency) -> dict:
        _ = user
        scope = {
            "organization_id": payload.organization_id,
            "domain_pack": payload.domain_pack,
            "workflow_id": payload.workflow_id,
            "workflow_version": payload.workflow_version,
            "role": payload.role,
        }
        return {
            "items": container.memory_service.retrieve(
                scope,
                memory_type=payload.memory_type,
                active_only=payload.active_only,
            )
        }

    @router.post("/memory/invalidate", dependencies=[Depends(csrf_dep)])
    def memory_invalidate(payload: MemoryInvalidateRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        scope = {
            "organization_id": payload.organization_id,
            "domain_pack": payload.domain_pack,
            "workflow_id": payload.workflow_id,
            "workflow_version": payload.workflow_version,
            "role": payload.role,
        }
        changed = container.memory_service.invalidate(scope, hard=payload.hard)
        return {"ok": True, "changed": changed}

    @router.get("/memory/groups")
    def list_memory_groups(org_id: str = "default", user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [
            item.model_dump(mode="json")
            for item in container.memory_group_registry.list(organization_id=org_id, status="active")
        ]

    @router.post("/memory/groups", dependencies=[Depends(csrf_dep)])
    def upsert_memory_group(payload: MemoryGroupDefinition, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.memory_group_registry.upsert(payload)
        return {"ok": True}

    @router.delete("/memory/groups/{group_id}", dependencies=[Depends(csrf_dep)])
    def delete_memory_group(group_id: str, org_id: str = "default", user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.memory_group_registry.delete(org_id, group_id)
        return {"ok": True}

    @router.get("/memory/memberships")
    def list_memory_memberships(
        org_id: str = "default",
        group_id: str | None = None,
        role_id: str | None = None,
        user: UIUser = user_dependency,
    ) -> list[dict]:
        _ = user
        return [
            item.model_dump(mode="json")
            for item in container.memory_membership_registry.list(
                organization_id=org_id,
                group_id=group_id,
                role_id=role_id,
                status="active",
            )
        ]

    @router.post("/memory/memberships", dependencies=[Depends(csrf_dep)])
    def upsert_memory_membership(payload: MemoryGroupMembership, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.memory_membership_registry.upsert(payload)
        return {"ok": True}

    @router.delete("/memory/memberships/{membership_id}", dependencies=[Depends(csrf_dep)])
    def delete_memory_membership(membership_id: str, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.memory_membership_registry.delete(membership_id)
        return {"ok": True}

    @router.get("/memory/edges")
    def list_memory_edges(
        org_id: str = "default",
        parent_role_id: str | None = None,
        child_role_id: str | None = None,
        user: UIUser = user_dependency,
    ) -> list[dict]:
        _ = user
        return [
            item.model_dump(mode="json")
            for item in container.memory_edge_registry.list(
                organization_id=org_id,
                parent_role_id=parent_role_id,
                child_role_id=child_role_id,
                status="active",
            )
        ]

    @router.post("/memory/edges", dependencies=[Depends(csrf_dep)])
    def upsert_memory_edge(payload: MemoryRoleEdge, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.memory_edge_registry.upsert(payload)
        return {"ok": True}

    @router.delete("/memory/edges/{edge_id}", dependencies=[Depends(csrf_dep)])
    def delete_memory_edge(edge_id: str, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        container.memory_edge_registry.delete(edge_id)
        return {"ok": True}

    @router.get("/memory/topology/graph")
    def memory_topology_graph(org_id: str = "default", user: UIUser = user_dependency) -> dict:
        _ = user
        return _memory_topology_graph(container, org_id)

    @router.get("/memory/scopes/resolve")
    def resolve_memory_scopes(
        org_id: str,
        role_id: str,
        domain_pack: str,
        workflow_id: str,
        workflow_version: int,
        user: UIUser = user_dependency,
    ) -> dict:
        _ = user
        return container.memory_topology_service.resolve_scopes(
            organization_id=org_id,
            role_id=role_id,
            domain_pack=domain_pack,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
        )

    @router.get("/state-partitions")
    def state_partitions(
        partition_id: str | None = None,
        limit: int = 200,
        user: UIUser = user_dependency,
    ) -> list[dict]:
        _ = user
        return container.state_partition_service.list(partition_id=partition_id, limit=limit)

    @router.get("/state-partitions/{partition_id}/{key}")
    def state_partition_get(partition_id: str, key: str, user: UIUser = user_dependency) -> dict:
        _ = user
        data = container.state_partition_service.get(partition_id, key)
        if data is None:
            raise HTTPException(status_code=404, detail="state partition entry not found")
        return data

    @router.get("/artifacts/{artifact_type}")
    def list_artifacts(
        artifact_type: str,
        status: str | None = None,
        organization_id: str | None = None,
        user: UIUser = user_dependency,
    ) -> list[dict]:
        _ = user
        try:
            return container.artifact_service.list(
                artifact_type,
                status=status,
                organization_id=organization_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/artifacts/{artifact_type}", dependencies=[Depends(csrf_dep)])
    def upsert_artifact(
        artifact_type: str,
        payload: ArtifactUpsertRequest,
        user: UIUser = user_dependency,
    ) -> dict:
        require_role(user, "operator")
        body = dict(payload.payload)
        body.setdefault("organization_id", "default")
        try:
            item = container.artifact_service.upsert(artifact_type, body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "artifact": item}

    @router.get("/incidents")
    def incidents(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return container.repositories.incidents.list()

    @router.post("/incidents", dependencies=[Depends(csrf_dep)])
    def create_incident(payload: IncidentRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        incident_id = str(uuid4())
        data = {
            "incident_id": incident_id,
            "severity": payload.severity,
            "title": payload.title,
            "summary": payload.summary,
            "task_id": payload.task_id,
            "workflow_id": payload.workflow_id,
        }
        container.repositories.incidents.upsert(incident_id, data, status="active")
        return {"ok": True, "incident": data}

    @router.get("/incidents/export")
    def export_incidents(user: UIUser = user_dependency) -> Response:
        _ = user
        rows = container.repositories.incidents.list()
        return Response(content=json.dumps(rows, indent=2), media_type="application/json")

    @router.get("/topology")
    def topology(user: UIUser = user_dependency) -> dict:
        _ = user
        return {"mermaid": container.topology_service.generate_mermaid()}

    return router


def mount_ui(app) -> None:
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="ui-static")

    @app.get("/ui", include_in_schema=False)
    def ui_index():
        return FileResponse(static_dir / "index.html")
