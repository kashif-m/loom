from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StatusEnum(str, Enum):
    draft = "draft"
    active = "active"
    retired = "retired"
    archived = "archived"


class Organization(BaseModel):
    org_id: str = Field(default="default")
    name: str = "My Organization"
    litellm_base_url: str | None = None
    litellm_api_key: str | None = None
    litellm_default_model: str = "open-large"
    litellm_start_cmd: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    opencode_enabled: bool = False
    opencode_cmd: str = "opencode"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskStatus(str, Enum):
    created = "created"
    triaging = "triaging"
    workflow_selected = "workflow_selected"
    running = "running"
    awaiting_input = "awaiting_input"
    blocked = "blocked"
    failed = "failed"
    completed = "completed"
    archived = "archived"


class PolicyEnforcement(str, Enum):
    warn = "warn"
    block = "block"


class MemoryType(str, Enum):
    working = "working"
    episodic = "episodic"
    semantic = "semantic"


class MemoryScopeReference(BaseModel):
    workflow_id: str
    workflow_version: int
    role_id: str | None = None
    domain_pack: str | None = None
    linked_entities: dict[str, str] = Field(default_factory=dict)
    task_lineage: list[str] = Field(default_factory=list)


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str = "default"
    raw_request: str
    normalized_request: str | None = None
    domain_pack: str | None = None
    workflow_id: str | None = None
    workflow_version: int | None = None
    current_status: TaskStatus = TaskStatus.created
    current_step_id: str | None = None
    linked_entities: dict[str, str] = Field(default_factory=dict)
    memory_scope_refs: list[MemoryScopeReference] = Field(default_factory=list)
    execution_refs: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowDefinitionMetadata(BaseModel):
    workflow_id: str
    version: int
    title: str
    domain_pack: str
    intent_group: str
    status: StatusEnum = StatusEnum.draft
    selection_hints: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class PackageArtifact(BaseModel):
    package_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str = "default"
    title: str
    workflow_id: str
    workflow_version: int
    task_id: str | None = None
    content: str
    status: StatusEnum = StatusEnum.active
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GroundingReference(BaseModel):
    reference_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str = "default"
    reference_type: str
    source_ref: str
    claim: str
    evidence: str | None = None
    workflow_id: str | None = None
    task_id: str | None = None
    status: StatusEnum = StatusEnum.active
    created_at: datetime = Field(default_factory=utc_now)


class PRContext(BaseModel):
    pr_context_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str = "default"
    pr_ref: str
    repo_ref: str
    fork_or_main: str
    current_head_sha: str | None = None
    review_state_last_fetched_at: datetime | None = None
    promotion_state: str | None = None
    cleanup_state: str | None = None
    terminal_outcome: str | None = None
    status: StatusEnum = StatusEnum.active
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditResult(BaseModel):
    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str = "default"
    task_id: str | None = None
    workflow_id: str | None = None
    checklist_id: str
    passed: bool
    findings: list[str] = Field(default_factory=list)
    status: StatusEnum = StatusEnum.active
    created_at: datetime = Field(default_factory=utc_now)


class RepoTargetMapping(BaseModel):
    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str = "default"
    source_url: str
    repository: str
    file_paths: list[str] = Field(default_factory=list)
    branch: str | None = None
    confidence: float = 1.0
    status: StatusEnum = StatusEnum.active
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowMarkdownDocument(BaseModel):
    workflow_id: str
    version: int
    markdown: str


class CompletionSemantics(BaseModel):
    type: Literal[
        "all_outputs_present",
        "predicate",
        "approval_received",
        "all_participants_complete",
        "any_participant_complete",
    ]
    predicate: str | None = None


class StepTransitions(BaseModel):
    on_success: str
    on_blocked: str | None = None
    on_failure: str | None = None
    on_retry: str | None = None


class CompiledWorkflowStep(BaseModel):
    step_id: str
    title: str
    owned_by: str
    participants: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    spawn_strategy: Literal[
        "single_owner",
        "primary_with_support",
        "parallel_research",
        "consensus_required",
        "any_one_can_complete",
    ] = "single_owner"
    merge_strategy: Literal[
        "owner_synthesizes",
        "first_valid_output",
        "consensus_summary",
        "explicit_human_choice",
    ] = "owner_synthesizes"
    completion: CompletionSemantics = Field(
        default_factory=lambda: CompletionSemantics(type="all_outputs_present")
    )
    transitions: StepTransitions
    policy_bindings: list[str] = Field(default_factory=list)
    prompt_profile_id: str | None = None
    memory_hints: dict[str, Any] = Field(default_factory=dict)


class CompiledWorkflowIR(BaseModel):
    workflow_id: str
    version: int
    title: str
    purpose: str
    required_inputs: list[str] = Field(default_factory=list)
    steps: list[CompiledWorkflowStep]
    terminal_states: list[str] = Field(default_factory=lambda: ["completed", "blocked", "failed"])
    rules: list[str] = Field(default_factory=list)
    policy_hints: list[str] = Field(default_factory=list)
    memory_hints: dict[str, Any] = Field(default_factory=dict)


class MemoryGroupDefinition(BaseModel):
    group_id: str
    organization_id: str = "default"
    title: str
    description: str | None = None
    visibility: Literal["shared", "private"] = "shared"
    owner_role_id: str | None = None
    status: StatusEnum = StatusEnum.active


class MemoryGroupMembership(BaseModel):
    membership_id: str | None = None
    organization_id: str = "default"
    group_id: str
    role_id: str
    access: Literal["read", "write", "read_write"] = "read_write"
    status: StatusEnum = StatusEnum.active

    @model_validator(mode="after")
    def ensure_membership_id(self) -> MemoryGroupMembership:
        if not self.membership_id:
            self.membership_id = f"{self.organization_id}:{self.group_id}:{self.role_id}"
        return self


class MemoryRoleEdge(BaseModel):
    edge_id: str | None = None
    organization_id: str = "default"
    parent_role_id: str
    child_role_id: str
    shared_group_id: str | None = None
    status: StatusEnum = StatusEnum.active

    @model_validator(mode="after")
    def ensure_edge_id(self) -> MemoryRoleEdge:
        if not self.edge_id:
            group = self.shared_group_id or "none"
            self.edge_id = f"{self.organization_id}:{self.parent_role_id}:{self.child_role_id}:{group}"
        return self


class RoleDefinition(BaseModel):
    role_id: str
    title: str
    domain_pack: str
    capability_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    memory_visibility: list[str] = Field(default_factory=list)
    preferred_model_id: str | None = None
    status: StatusEnum = StatusEnum.draft


class RuntimeParticipant(BaseModel):
    participant_id: str = Field(default_factory=lambda: str(uuid4()))
    role_id: str
    capability_ids: list[str] = Field(default_factory=list)
    task_id: str | None = None
    active: bool = True


class CapabilityDefinition(BaseModel):
    capability_id: str
    description: str
    connector_binding: str | None = None
    validation_requirements: list[str] = Field(default_factory=list)
    status: StatusEnum = StatusEnum.active


class PromptProfile(BaseModel):
    profile_id: str
    version: int
    domain_pack: str
    system_prompt: str
    status: StatusEnum = StatusEnum.active


class ModelProviderDefinition(BaseModel):
    provider_id: str
    provider_type: Literal["litellm"] = "litellm"
    base_url: str
    api_key: str
    extra_headers: dict[str, str] = Field(default_factory=dict)
    status: StatusEnum = StatusEnum.active


class ModelDefinition(BaseModel):
    model_id: str
    provider_id: str
    model_name: str
    max_tokens: int | None = None
    temperature: float | None = None
    status: StatusEnum = StatusEnum.active


class ServiceModelBinding(BaseModel):
    service_id: str
    model_id: str
    status: StatusEnum = StatusEnum.active


class PolicyDefinition(BaseModel):
    policy_id: str
    description: str
    scope: Literal["global", "workflow", "role", "step"] = "global"
    enforcement: PolicyEnforcement = PolicyEnforcement.block
    rules: dict[str, Any] = Field(default_factory=dict)
    status: StatusEnum = StatusEnum.active


class DomainPackManifest(BaseModel):
    pack_id: str
    version: str
    description: str
    workflows: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    prompt_profiles: list[str] = Field(default_factory=list)
    connectors: list[str] = Field(default_factory=list)
    validations: list[str] = Field(default_factory=list)
    status: StatusEnum = StatusEnum.draft


class ScheduleDefinition(BaseModel):
    schedule_id: str
    cron: str
    action_type: Literal["workflow", "maintenance"]
    target: str
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class TaskEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ParsedWorkflowDocument(BaseModel):
    title: str
    purpose: str
    trigger: str
    required_inputs: list[str]
    steps: list[dict[str, Any]]
    completion_criteria: str
    blocked_conditions: str
    failure_conditions: str
    rules: list[str]
    source_locations: dict[str, int] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    intent_group: str
    confidence: float
    outcome: Literal["supported", "unsupported", "needs_clarification"]

    @model_validator(mode="after")
    def validate_confidence(self) -> ClassificationResult:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return self
