"""Graphiti memory schemas for Loom MVP."""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class MemoryTier(str, Enum):
    """Memory tier enum."""
    AGENTIC = "agentic"
    TEAM = "team"
    ORG = "org"


class MemoryNode(BaseModel):
    """Memory node in the knowledge graph."""
    id: str | None = None
    content: str
    node_type: str = "fact"  # fact, observation, conclusion
    provenance: dict  # {event_id, task_id}
    created_at: datetime = Field(default_factory=utc_now)
    tier: MemoryTier
    agent_id: str | None = None  # For agentic tier
    team_id: str | None = None  # For team tier
    org_id: str | None = None  # For org tier

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MemoryEdge(BaseModel):
    """Memory edge connecting nodes."""
    id: str | None = None
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    created_at: datetime = Field(default_factory=utc_now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MemoryQuery(BaseModel):
    """Memory query."""
    query: str
    tier: MemoryTier | None = None
    agent_id: str | None = None
    team_id: str | None = None
    limit: int = 10
