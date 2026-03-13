from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from loom.domainpacks.docs.loader import load_docs_pack
from loom.integrations.health import connector_health
from loom.models import (
    CapabilityDefinition,
    DomainPackManifest,
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
    async_run: bool = False


class GenericDeleteResponse(BaseModel):
    ok: bool


class MemoryQueryRequest(BaseModel):
    domain_pack: str
    workflow_id: str
    workflow_version: int
    role: str = "any"
    memory_type: str = "episodic"
    active_only: bool = True


class MemoryInvalidateRequest(BaseModel):
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
    name: str
    litellm_base_url: str | None = None
    litellm_api_key: str | None = None


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
    def get_organization(user: UIUser = user_dependency) -> dict:
        _ = user
        org = container.repositories.organization.get_or_create()
        return org.model_dump(mode="json")

    @router.post("/organization", dependencies=[Depends(csrf_dep)])
    def update_organization(payload: OrganizationRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        org = Organization(
            org_id="default",
            name=payload.name,
            litellm_base_url=payload.litellm_base_url,
            litellm_api_key=payload.litellm_api_key,
        )
        container.repositories.organization.upsert(org)
        return org.model_dump(mode="json")

    @router.get("/integrations/status")
    def integration_status(user: UIUser = user_dependency) -> dict:
        _ = user
        return {
            "graphiti": {
                "enabled": container.settings.graphiti_enabled,
                "base_url": container.settings.graphiti_base_url,
            },
            "openclaw": {"enabled": container.settings.openclaw_enabled},
            "openai": {
                "enabled": container.settings.openai_enabled,
                "model": container.settings.openai_model,
            },
            "litellm": {
                "enabled": container.settings.litellm_enabled,
                "base_url": container.settings.litellm_base_url,
                "default_model": container.settings.litellm_default_model,
            },
            "langsmith": {
                "enabled": container.settings.langsmith_enabled,
                "project": container.settings.langsmith_project,
            },
            "opencode": {
                "enabled": container.settings.opencode_enabled,
                "cmd": container.settings.opencode_cmd,
                "available": shutil.which(container.settings.opencode_cmd) is not None,
            },
            "connectors": {
                "git": shutil.which("git") is not None,
                "gh": shutil.which("gh") is not None,
                "plantuml": shutil.which("plantuml") is not None,
                "node": shutil.which("node") is not None,
                "java": shutil.which("java") is not None,
            },
            "database_url": container.settings.database_url,
            "integration_profile": container.settings.integration_profile,
            "model_routing": {
                "step_execution": container.model_router.resolve_public("step_execution"),
            },
        }

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
    def resolve_service_model(service_id: str, user: UIUser = user_dependency) -> dict:
        _ = user
        resolved = container.model_router.resolve_public(service_id)
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
    def list_tasks(user: UIUser = user_dependency) -> list[dict]:
        _ = user
        return [t.model_dump(mode="json") for t in container.repositories.tasks.list()]

    @router.post("/tasks/intake", dependencies=[Depends(csrf_dep)])
    def intake_task(req: IntakeRequest, user: UIUser = user_dependency) -> dict:
        require_role(user, "operator")
        task = container.intake_service.intake(req.request, domain_pack=req.domain_pack)
        if req.async_run and container.settings.async_workers_enabled and task.workflow_id:
            job = container.async_worker.submit_task(task.task_id)
            return {
                "task": task.model_dump(mode="json"),
                "job": {"job_id": job.job_id, "status": job.status},
            }
        return {"task": task.model_dump(mode="json")}

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
        return task.model_dump(mode="json")

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
        return task.model_dump(mode="json")

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
        return task.model_dump(mode="json")

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
            "domain_pack": payload.domain_pack,
            "workflow_id": payload.workflow_id,
            "workflow_version": payload.workflow_version,
            "role": payload.role,
        }
        changed = container.memory_service.invalidate(scope, hard=payload.hard)
        return {"ok": True, "changed": changed}

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
