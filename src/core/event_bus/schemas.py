"""Event bus schemas for Loom MVP."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Event types."""
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STATE_TRANSITION = "task.state_transition"
    TASK_BLOCKED = "task.blocked"
    TASK_COMPLETED = "task.completed"
    WORKFLOW_ESCALATED = "workflow.escalated"
    MEMORY_WRITE = "memory.write"
    AGENT_TOOL_CALL = "agent.tool_call"


class BaseEvent(BaseModel):
    """Base event model."""
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    idempotency_key: str
    sequence_number: int
    produced_at: datetime = Field(default_factory=utc_now)
    task_id: str


class TaskCreatedEvent(BaseEvent):
    """Task created event."""
    event_type: EventType = EventType.TASK_CREATED
    description: str
    workflow_id: str | None = None
    team_id: str


class TaskStateTransitionEvent(BaseEvent):
    """Task state transition event."""
    event_type: EventType = EventType.TASK_STATE_TRANSITION
    from_state: str | None
    to_state: str
    agent_id: str


class TaskBlockedEvent(BaseEvent):
    """Task blocked event."""
    event_type: EventType = EventType.TASK_BLOCKED
    blocker_description: str
    agent_id: str


class TaskCompletedEvent(BaseEvent):
    """Task completed event."""
    event_type: EventType = EventType.TASK_COMPLETED
    outcome: str
    agent_id: str


class WorkflowEscalatedEvent(BaseEvent):
    """Workflow escalated event."""
    event_type: EventType = EventType.WORKFLOW_ESCALATED
    reason: str
    agent_id: str


class MemoryWriteEvent(BaseEvent):
    """Memory write event."""
    event_type: EventType = EventType.MEMORY_WRITE
    content: str
    tier: str
    agent_id: str


class AgentToolCallEvent(BaseEvent):
    """Agent tool call event."""
    event_type: EventType = EventType.AGENT_TOOL_CALL
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: dict[str, Any] | None = None
    agent_id: str


EventUnion = (
    TaskCreatedEvent
    | TaskStateTransitionEvent
    | TaskBlockedEvent
    | TaskCompletedEvent
    | WorkflowEscalatedEvent
    | MemoryWriteEvent
    | AgentToolCallEvent
)
