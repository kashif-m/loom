"""Task routes."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.api.state import app_state
from src.core.task_store.models import TaskStatus

router = APIRouter()


class SubmitTaskRequest(BaseModel):
    """Submit task request."""
    description: str
    priority: str = "normal"  # low, normal, urgent


class TaskResponse(BaseModel):
    """Task response."""
    task_id: str
    status: str
    message: str | None = None


class TaskDetailResponse(BaseModel):
    """Task detail response."""
    task_id: str
    status: str
    current_state: str
    team_id: str
    owner_agent_id: str
    description: str
    created_at: datetime
    updated_at: datetime
    history: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]


@router.post("/tasks", response_model=TaskResponse)
async def submit_task(request: SubmitTaskRequest):
    """Submit a new task."""
    if not app_state.kite_runner:
        raise HTTPException(status_code=503, detail="Kite Runner not initialized")

    result = await app_state.kite_runner.submit_task(request.description)

    if not result.get("success"):
        return TaskResponse(
            task_id="",
            status="failed",
            message=result.get("reason", "Unknown error"),
        )

    return TaskResponse(
        task_id=result["task_id"],
        status="created",
    )


@router.get("/tasks")
async def list_tasks(
    status: str | None = Query(None, description="Filter by status"),
    team_id: str | None = Query(None, description="Filter by team"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List tasks with optional filters."""
    if not app_state.task_store:
        raise HTTPException(status_code=503, detail="Task store not initialized")

    task_status = TaskStatus(status) if status else None

    tasks = await app_state.task_store.list_tasks(
        status=task_status,
        team_id=team_id,
        limit=limit,
        offset=offset,
    )

    return {
        "tasks": [task.model_dump() for task in tasks],
        "total": len(tasks),
    }


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str):
    """Get task details."""
    if not app_state.task_store:
        raise HTTPException(status_code=503, detail="Task store not initialized")

    task = await app_state.task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get related data
    history = await app_state.task_store.get_task_history(task_id)
    blockers = await app_state.task_store.get_task_blockers(task_id)
    artifacts = await app_state.task_store.get_task_artifacts(task_id)

    return TaskDetailResponse(
        task_id=task.task_id,
        status=task.status.value,
        current_state=task.current_state,
        team_id=task.team_id,
        owner_agent_id=task.owner_agent_id,
        description=task.description,
        created_at=task.created_at,
        updated_at=task.updated_at,
        history=[h.model_dump() for h in history],
        blockers=[b.model_dump() for b in blockers],
        artifacts=[a.model_dump() for a in artifacts],
    )


class EscalationResponseRequest(BaseModel):
    """Escalation response request."""
    message: str


@router.post("/tasks/{task_id}/respond")
async def respond_to_escalation(task_id: str, request: EscalationResponseRequest):
    """Respond to an escalated task."""
    if not app_state.kite_runner:
        raise HTTPException(status_code=503, detail="Kite Runner not initialized")

    result = await app_state.kite_runner.respond_to_escalation(
        task_id=task_id,
        response=request.message,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason", "Failed"))

    return {"success": True, "task_id": task_id}


class ReassignRequest(BaseModel):
    """Reassign request."""
    team_id: str
    reason: str


@router.post("/tasks/{task_id}/reassign")
async def reassign_task(task_id: str, request: ReassignRequest):
    """Reassign task to different team."""
    if not app_state.task_store:
        raise HTTPException(status_code=503, detail="Task store not initialized")

    # Get task
    task = await app_state.task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Escalate with reassign info
    await app_state.task_store.escalate(
        task_id=task_id,
        reason=f"Reassigned to {request.team_id}: {request.reason}",
        agent_id=task.owner_agent_id,
    )

    return {"success": True, "task_id": task_id, "new_team": request.team_id}
