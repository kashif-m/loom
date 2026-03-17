"""LLM schemas for Loom MVP."""
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Chat message."""
    role: str  # system, user, assistant, tool
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class Tool(BaseModel):
    """Tool definition."""
    type: str = "function"
    function: dict[str, Any]


class ToolCall(BaseModel):
    """Tool call."""
    id: str
    type: str = "function"
    function: dict[str, Any]


class LLMResponse(BaseModel):
    """LLM response."""
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model_used: str
    tokens_used: int = 0
    finish_reason: str | None = None


class LLMConfig(BaseModel):
    """LLM configuration."""
    base_url: str = "http://localhost:4000"
    api_key: str
    model: str = "open-large"
    max_retries: int = 3
    timeout_seconds: float = 60.0


# =============================================================================
# Instructor Structured Output Models
# =============================================================================

class WorkflowMatchResponse(BaseModel):
    """Structured response for workflow matching.
    
    Used by: workflow_engine.matcher
    """
    selection: int = Field(
        description="Index of the selected workflow (1-based)",
        ge=1,
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        description="Explanation of why this workflow was selected",
        min_length=10,
    )


class SelfReflectionResponse(BaseModel):
    """Structured response for self-reflection evaluation.
    
    Used by: agents.base.reflection
    """
    approved: bool = Field(
        description="Whether the output meets the success criteria",
    )
    reasoning: str = Field(
        description="Explanation of the evaluation",
        min_length=10,
    )
    score: float = Field(
        description="Quality score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )


class MemoryFact(BaseModel):
    """A single extracted memory fact."""
    content: str = Field(
        description="The factual content to remember",
        min_length=5,
    )
    entity_ids: list[str] = Field(
        description="IDs of entities mentioned in this fact",
        default_factory=list,
    )
    importance: int = Field(
        description="Importance score from 1-10",
        ge=1,
        le=10,
    )


class MemoryExtractionResponse(BaseModel):
    """Structured response for memory extraction from events.
    
    Used by: memory.event_worker.processor
    """
    facts: list[MemoryFact] = Field(
        description="List of facts extracted from the event",
        default_factory=list,
    )
    summary: str = Field(
        description="Brief summary of what happened",
        min_length=10,
    )
    entities: list[str] = Field(
        description="Named entities found in the event (agents, tasks, teams)",
        default_factory=list,
    )


class TaskClassificationResponse(BaseModel):
    """Structured response for task classification.
    
    Used by: kite_runner for initial triage
    """
    priority: str = Field(
        description="Task priority: low, normal, urgent, or critical",
        pattern="^(low|normal|urgent|critical)$",
    )
    category: str = Field(
        description="Task category: bug, feature, docs, refactor, or other",
        pattern="^(bug|feature|docs|refactor|other)$",
    )
    estimated_effort: str = Field(
        description="Estimated effort: small, medium, or large",
        pattern="^(small|medium|large)$",
    )
    reasoning: str = Field(
        description="Explanation for the classification",
        min_length=10,
    )
