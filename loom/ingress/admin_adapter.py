from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from loom.ingress.permissions import CallerContext, ensure_admin
from loom.ingress.request_models import AdminInvalidateMemoryRequest, AdminWorkflowPublishRequest
from loom.ingress.security import admin_auth
from loom.memory.invalidation_service import InvalidationService
from loom.models import (
    DomainPackManifest,
    PromptProfile,
    RoleDefinition,
    ScheduleDefinition,
    StatusEnum,
    WorkflowDefinitionMetadata,
    WorkflowMarkdownDocument,
)
from loom.observability.audit_log_service import AuditLogService
from loom.observability.trace_service import TraceService


def _caller(x_role: str | None = Header(default=None)) -> CallerContext:
    return CallerContext(role=x_role or "viewer")


CallerDep = Depends(_caller)


def _require_admin(caller: CallerContext = CallerDep) -> None:
    try:
        ensure_admin(caller)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def build_admin_router(container) -> APIRouter:
    router = APIRouter(
        prefix="/admin",
        tags=["admin"],
        dependencies=[Depends(admin_auth(container.settings.api_auth_enabled, container.settings.admin_api_key))],
    )

    @router.post("/workflow/publish", dependencies=[Depends(_require_admin)])
    def publish_workflow(req: AdminWorkflowPublishRequest) -> dict:
        metadata = WorkflowDefinitionMetadata(
            workflow_id=req.workflow_id,
            version=req.version,
            title=req.title,
            domain_pack=req.domain_pack,
            intent_group=req.intent_group,
            status=StatusEnum.draft,
        )
        doc = WorkflowMarkdownDocument(
            workflow_id=req.workflow_id,
            version=req.version,
            markdown=req.markdown,
        )
        container.compiler_service.publish_from_markdown(metadata, doc, activate=req.activate)
        return {"ok": True}

    @router.post("/workflow/{workflow_id}/{version}/activate", dependencies=[Depends(_require_admin)])
    def activate_workflow(workflow_id: str, version: int) -> dict:
        container.workflow_registry.activate_version(workflow_id, version)
        return {"ok": True}

    @router.post("/workflow/{workflow_id}/{version}/deprecate", dependencies=[Depends(_require_admin)])
    def deprecate_workflow(workflow_id: str, version: int) -> dict:
        container.workflow_registry.deprecate_version(workflow_id, version)
        return {"ok": True}

    @router.post("/role/upsert", dependencies=[Depends(_require_admin)])
    def upsert_role(role: RoleDefinition) -> dict:
        container.role_registry.upsert(role)
        return {"ok": True}

    @router.post("/domain-pack/upsert", dependencies=[Depends(_require_admin)])
    def upsert_pack(manifest: DomainPackManifest) -> dict:
        container.domain_pack_registry.upsert(manifest)
        return {"ok": True}

    @router.post("/schedule/upsert", dependencies=[Depends(_require_admin)])
    def upsert_schedule(schedule: ScheduleDefinition) -> dict:
        container.schedule_registry.upsert(schedule)
        container.scheduler_service.reload()
        return {"ok": True}

    @router.delete("/schedule/{schedule_id}", dependencies=[Depends(_require_admin)])
    def delete_schedule(schedule_id: str) -> dict:
        container.schedule_registry.delete(schedule_id)
        container.scheduler_service.reload()
        return {"ok": True}

    @router.post("/memory/invalidate", dependencies=[Depends(_require_admin)])
    def invalidate_memory(req: AdminInvalidateMemoryRequest) -> dict:
        svc = InvalidationService(container.memory_service)
        scope = {
            "organization_id": req.organization_id,
            "domain_pack": req.domain_pack,
            "workflow_id": req.workflow_id,
            "workflow_version": req.workflow_version,
            "role": req.role,
        }
        changed = svc.hard_invalidate(scope) if req.hard else svc.soft_invalidate(scope)
        return {"ok": True, "changed": changed}

    @router.post("/prompt/upsert", dependencies=[Depends(_require_admin)])
    def upsert_prompt(profile: PromptProfile) -> dict:
        container.prompt_registry.upsert(profile)
        return {"ok": True}

    @router.get("/tasks/{task_id}/trace")
    def task_trace(task_id: str) -> dict:
        trace = TraceService(
            AuditLogService(container.repositories),
            langsmith_adapter=container.langsmith_adapter,
        ).trace_for_task(task_id)
        return trace

    return router
