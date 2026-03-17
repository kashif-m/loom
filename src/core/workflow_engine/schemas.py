"""Workflow engine schemas for Loom MVP."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class WorkflowLevel(str, Enum):
    """Workflow level enum."""
    ORG = "org"
    TEAM = "team"
    AGENTIC = "agentic"


class WorkflowStatus(str, Enum):
    """Workflow status enum."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class WorkflowDefinition(BaseModel):
    """Workflow definition model."""
    id: str
    version: str
    level: WorkflowLevel
    trigger: str
    tags: list[str]
    states: list[str]
    success_condition: str
    escalate_if: str
    status: WorkflowStatus = WorkflowStatus.DRAFT
    loaded_at: datetime = Field(default_factory=utc_now)
    source_file: str | None = None


class WorkflowMatchResult(BaseModel):
    """Workflow match result."""
    workflow: WorkflowDefinition
    confidence: float
    match_type: str  # "tag", "llm", "none"


class StateTransition(BaseModel):
    """State transition definition."""
    from_state: str | None
    to_state: str
    condition: str | None = None


class WorkflowExecutionState(BaseModel):
    """Workflow execution state."""
    task_id: str
    workflow_id: str
    current_state: str
    state_history: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
