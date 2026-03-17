"""Workflow routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.state import app_state
from src.core.workflow_engine.registry import get_registry
from src.core.workflow_engine.schemas import WorkflowStatus

router = APIRouter()


class WorkflowListResponse(BaseModel):
    """Workflow list response."""
    workflows: list[dict]


class WorkflowDetailResponse(BaseModel):
    """Workflow detail response."""
    id: str
    version: str
    level: str
    status: str
    trigger: str
    tags: list[str]
    states: list[str]
    success_condition: str
    escalate_if: str


class WorkflowStatusUpdateRequest(BaseModel):
    """Workflow status update request."""
    status: str  # active, deprecated


@router.get("/workflows")
async def list_workflows():
    """List all workflows."""
    registry = get_registry()
    workflows = registry.get_all()

    return {
        "workflows": [
            {
                "id": w.id,
                "version": w.version,
                "level": w.level.value,
                "status": w.status.value,
                "trigger": w.trigger,
                "tags": w.tags,
            }
            for w in workflows
        ]
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow details."""
    registry = get_registry()
    workflow = registry.get_by_id(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowDetailResponse(
        id=workflow.id,
        version=workflow.version,
        level=workflow.level.value,
        status=workflow.status.value,
        trigger=workflow.trigger,
        tags=workflow.tags,
        states=workflow.states,
        success_condition=workflow.success_condition,
        escalate_if=workflow.escalate_if,
    )


@router.patch("/workflows/{workflow_id:path}")
async def update_workflow_status(
    workflow_id: str,
    request: WorkflowStatusUpdateRequest,
):
    """Update workflow status (approve/deprecate)."""
    registry = get_registry()

    # Get workflow
    workflow = registry.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate status
    try:
        new_status = WorkflowStatus(request.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

    # Update status
    success = registry.set_status(workflow_id, workflow.version, new_status)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update workflow")

    return {
        "success": True,
        "workflow_id": workflow_id,
        "status": new_status.value,
    }
