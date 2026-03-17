"""Task store models for Loom MVP."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    """Task status enum."""
    OPEN = "open"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Task(BaseModel):
    """Main task model."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str | None = None
    workflow_version: int | None = None
    owner_agent_id: str
    team_id: str
    current_state: str
    version: int = 1
    retry_count: int = 0
    escalation_count: int = 0
    sla_deadline: datetime | None = None
    status: TaskStatus = TaskStatus.OPEN
    description: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskHistory(BaseModel):
    """Task state transition history."""
    id: int | None = None
    task_id: str
    from_state: str | None
    to_state: str
    agent_id: str
    event_id: str
    transitioned_at: datetime = Field(default_factory=utc_now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskArtifact(BaseModel):
    """Task artifact reference."""
    id: int | None = None
    task_id: str
    artifact_type: str
    reference_url: str
    agent_id: str
    created_at: datetime = Field(default_factory=utc_now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskBlocker(BaseModel):
    """Task blocker record."""
    id: int | None = None
    task_id: str
    description: str
    raised_by: str
    raised_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RawEvent(BaseModel):
    """Raw event log entry."""
    event_id: str
    stream: str
    payload: dict[str, Any]
    received_at: datetime = Field(default_factory=utc_now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HumanReviewQueue(BaseModel):
    """Dead task queue for human review."""
    id: int | None = None
    task_id: str
    reason: str
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TaskEvaluation(BaseModel):
    """Task evaluation signals."""
    id: int | None = None
    task_id: str
    completed_successfully: bool
    rework_count: int = 0
    false_escalation: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
