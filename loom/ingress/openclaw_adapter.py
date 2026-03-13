from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from loom.ingress.openclaw_models import OpenClawEvent, OpenClawFFRequest
from loom.ingress.request_models import FFRequest
from loom.ingress.response_models import FFResponse
from loom.ingress.security import ingress_auth
from loom.integrations.openclaw_adapter_runtime import OpenClawRuntimeAdapter


def _stream_events(events: list[OpenClawEvent]):
    for event in events:
        yield f"event: {event.event}\ndata: {json.dumps(event.payload)}\n\n"


def build_router(container) -> APIRouter:
    router = APIRouter(
        prefix="/ingress",
        tags=["ingress"],
        dependencies=[Depends(ingress_auth(container.settings.api_auth_enabled, container.settings.ingress_api_key))],
    )

    @router.post("/ff", response_model=FFResponse)
    def ff(request: FFRequest) -> FFResponse:
        task = container.intake_service.intake(request.request, domain_pack=request.domain_pack)
        if request.async_run and container.settings.async_workers_enabled and task.workflow_id:
            job = container.async_worker.submit_task(task.task_id)
            return FFResponse(
                task_id=task.task_id,
                status="queued",
                workflow_id=task.workflow_id,
                workflow_version=task.workflow_version,
                summary=task.result_summary,
                job_id=job.job_id,
            )
        return FFResponse(
            task_id=task.task_id,
            status=task.current_status.value,
            workflow_id=task.workflow_id,
            workflow_version=task.workflow_version,
            summary=task.result_summary,
        )

    @router.post("/tasks/{task_id}/run", response_model=FFResponse)
    def run_task(task_id: str) -> FFResponse:
        task = container.repositories.tasks.get(task_id)
        if not task:
            return FFResponse(task_id=task_id, status="not_found", summary="task not found")
        if not task.workflow_id or task.workflow_version is None:
            return FFResponse(task_id=task_id, status=task.current_status.value, summary="workflow not selected")

        if container.settings.async_workers_enabled:
            job = container.async_worker.submit_task(task.task_id)
            return FFResponse(
                task_id=task.task_id,
                status="queued",
                workflow_id=task.workflow_id,
                workflow_version=task.workflow_version,
                summary="task queued",
                job_id=job.job_id,
            )

        task = container.execution_coordinator.run_task(task)
        container.repositories.tasks.update(task)
        return FFResponse(
            task_id=task.task_id,
            status=task.current_status.value,
            workflow_id=task.workflow_id,
            workflow_version=task.workflow_version,
            summary=task.result_summary,
        )

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = container.async_worker.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @router.get("/topology")
    def topology() -> dict[str, str]:
        return {"mermaid": container.topology_service.generate_mermaid()}

    @router.post("/openclaw/ff")
    def openclaw_ff(payload: OpenClawFFRequest):
        if not container.settings.openclaw_enabled:
            raise HTTPException(status_code=400, detail="openclaw integration disabled")

        runtime = OpenClawRuntimeAdapter(container.settings.openclaw_shared_secret)
        if not runtime.verify(payload.text, payload.session_id, payload.signature):
            raise HTTPException(status_code=401, detail="invalid openclaw signature")

        task = container.intake_service.intake(payload.text, domain_pack="docs")
        events = [
            OpenClawEvent(event="task_created", payload={"task_id": task.task_id, "status": task.current_status.value}),
            OpenClawEvent(
                event="workflow_selected",
                payload={"workflow_id": task.workflow_id, "workflow_version": task.workflow_version},
            ),
        ]

        if payload.stream:
            return StreamingResponse(_stream_events(events), media_type="text/event-stream")
        return {"events": [e.model_dump() for e in events]}

    return router
