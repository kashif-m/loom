# CODING_GUIDELINES.md

## Guiding principle

This is an orchestration system. The primary concerns are correctness, traceability, and predictability — not cleverness. When in doubt, write the boring, explicit version.

---

## Language and runtime

- Python 3.11+
- `uv` for package management. Never use pip directly.
- All async. Use `async/await` everywhere I/O is involved.
- Type hints on every function signature. No exceptions.
- Pydantic v2 for all data models, configs, and event schemas.

---

## Project structure

```
src/
  core/
    llm/          — LLM abstraction layer (LiteLLM wrapper)
    task_store/   — Task store operations and models
    event_bus/    — Redis Streams producer and consumer
    workflow_engine/ — Markdown parser, registry, matcher, runtime
  agents/
    base/         — Identity loader, memory access, reflection loop
    kite_runner/  — KR agent logic
    generalist/   — Generalist agent logic
    specialist/   — Specialist agent logic
  memory/
    graphiti/     — Graphiti client, tiered writer, cascade reader
    event_worker/ — State transition consumer + extraction worker
  evaluation/     — 3-signal evaluation on task close
  api/            — FastAPI gateway

workflows/        — Human-authored markdown files (NOT in src/)
agents_config/    — Agent identity JSON files (NOT in src/)
tests/
  unit/
  integration/
infra/
```

---

## Invariant enforcement in code

The 10 org kernel invariants (see ARCHITECTURE.md) must be enforced structurally where possible — not just documented.

**Practical rules:**

- Task state transitions must go through `task_store.operations.transition_state()` only. If you find yourself setting `task.current_state =` anywhere else, stop.
- Memory writes must go through the extraction worker only. Agents do not write to memory directly — they emit events.
- Agents import `complete()` from `core.llm.client` only. Never import `anthropic`, `openai`, or any provider SDK in agent code.
- Cross-team handoffs are initiated only in `agents/generalist/agent.py` or `agents/kite_runner/agent.py`. Never in specialist code.

---

## LLM calls

All LLM calls use the abstraction layer. This is non-negotiable.

```python
# CORRECT
from core.llm.client import complete
from core.llm.models import ModelRole

response = await complete(
    role=ModelRole.REASONING,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
)

# WRONG — never do this
import anthropic
client = anthropic.Anthropic()
```

**Model role selection:**
- Use `ModelRole.FAST` for: workflow matching, memory extraction, intent tagging, summarisation. These run frequently — keep them cheap.
- Use `ModelRole.REASONING` for: specialist task execution, generalist decisions, self-reflection loops. These run less often and need better reasoning.
- Never hardcode a model string. Never.

---

## Event emission

Every significant action emits an event. Events are the audit trail.

```python
# Every event must include these fields
event = TaskStateTransitionEvent(
    event_id=uuid4(),
    idempotency_key=f"{task_id}:{from_state}:{to_state}",
    sequence_number=next_sequence(task_id),
    produced_at=utcnow(),
    task_id=task_id,
    from_state=from_state,
    to_state=to_state,
    agent_id=agent_id,
)
await event_bus.emit(event)
```

**Rules:**
- Every event has an `idempotency_key`. No exceptions.
- Never emit events and then update task state in the same transaction without ordering guarantees. Emit event first, then update — or use a transactional outbox pattern.
- All consumers check `event_id` before processing. If already seen, skip silently — never raise.

---

## Task store operations

Use only the defined operations. Never write raw SQL against the tasks table from outside `core/task_store/`.

```python
# CORRECT
from core.task_store.operations import transition_state, attach_artifact

await transition_state(
    task_id=task_id,
    to_state="investigating",
    current_version=task.version,  # optimistic lock
    agent_id=agent_id,
)

# WRONG — never do this
await db.execute("UPDATE tasks SET current_state = 'investigating' WHERE ...")
```

**The `version` field is sacred.** Always pass the current version when transitioning. If the version has changed since you read the task (concurrent update), the operation raises `StaleTaskVersionError`. Catch it, re-read the task, and retry.

---

## Agent identity

Every agent loads its config from a JSON file in `/agents_config/`. Identity is immutable per agent instance.

```python
# agents/base/identity.py loads this
{
  "agent_id": "frontend-specialist-01",
  "name": "Frontend Specialist",
  "authority_level": "specialist",
  "team_id": "engineering",
  "model_role": "reasoning",
  "permitted_tools": ["code_execution", "file_read", "web_search"],
  "memory_scope": "agentic_only"
}
```

- `agent_id` must be stable. Do not generate it at runtime.
- `model_role` must be `"fast"` or `"reasoning"`. This is how the agent communicates its LLM tier — not a model string.
- `permitted_tools` is enforced by OpenFang. Never bypass it.

---

## Memory access

Agents access memory through `agents/base/memory.py` only. Tier access is enforced by scope.

```python
from agents.base.memory import query_memory

# Returns assembled context from correct tiers
context = await query_memory(
    agent_id=agent_id,
    memory_scope=config.memory_scope,  # from identity config
    query="payment button rendering issue",
)
```

**Access rules (enforced in code):**
- `agentic_only` — reads only own agentic memory
- `agentic_and_team` — reads own memory, then team memory
- `agentic_team_and_org` — reads all three tiers (generalists and KR only)

Specialists always have `agentic_only`. This is checked at runtime — raising `MemoryAccessDeniedError` if violated.

---

## Workflow files

Workflow files live in `/workflows/`. They are not source code. Do not put them in `/src/`.

Minimum required fields for the parser to accept a file:

```yaml
id: engineering/fix-bug
version: v1
level: team
trigger: "bug reported on production system"
tags: [bug, fix, production, engineering]
states:
  - received
  - investigating
  - fixing
  - in_review
  - done
success_condition: "Fix merged and verified in production"
escalate_if: "No state change after 2 retries OR blocker unresolved after 4 hours"
```

- `id` must be unique across all workflow files
- `tags` are used for deterministic matching — the more specific, the better
- `states` are ordered — V1 transitions are linear only
- Missing any required field causes the parser to reject the file and log an error — it does not crash the service

---

## Error handling

Use custom exception types. Never raise bare `Exception`.

```python
# Define in core/exceptions.py
class StaleTaskVersionError(Exception): ...
class WorkflowMatchError(Exception): ...
class MemoryAccessDeniedError(Exception): ...
class EscalationRequiredError(Exception): ...
class AgentToolError(Exception): ...
```

**Escalation is not an error.** When an agent hits a condition it cannot resolve, it raises `EscalationRequiredError`. The escalation manager catches this and emits a `workflow.escalated` event. This is normal control flow — not an exception in the exceptional sense.

---

## Testing

Every phase has an integration test that acts as a gate. Do not move to the next phase until the gate passes.

```
tests/integration/test_phase1.py  — task created → event emitted → log appended
tests/integration/test_phase2.py  — workflow loaded → task matched → states transitioned
tests/integration/test_phase3.py  — human task → KR → generalist → specialist → complete
tests/integration/test_phase4.py  — task completed → memory written → context retrieved
tests/integration/test_phase5.py  — unhappy paths: retry, escalation, SLA, idempotency
```

**Unit test rules:**
- Mock `complete()` from `core.llm.client` — never make real LLM calls in unit tests
- Use `pytest-asyncio` for all async tests
- Use Postgres and Redis test instances via docker-compose (not mocked — use real infra)
- Test each task store operation independently before wiring agents

---

## Logging

Use Loguru. Structured logging everywhere.

```python
from loguru import logger

# Include context in every log
logger.info("Task state transitioned", task_id=task_id, from_state=from_state, to_state=to_state, agent_id=agent_id)
logger.error("Workflow match failed", task_id=task_id, error=str(e))
```

**Rules:**
- Every log line at INFO or above includes `task_id` if in a task context
- Every LLM call is logged at DEBUG with `model_used` and `tokens_used` from the response
- Every tool call is logged at DEBUG with `tool_name` and `agent_id`
- Never log secrets, API keys, or raw message content at INFO or above

---

## Configuration

Use Pydantic Settings. All config from environment variables. No hardcoded values anywhere.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    fast_model: str
    reasoning_model: str
    fallback_model: str
    local_model: str | None = None
    database_url: str
    redis_url: str
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    class Config:
        env_file = ".env"
```

Copy `.env.example` to `.env` to run locally. Never commit `.env`.

---

## What not to build (V1 scope)

Do not implement these in V1. When the temptation arises, add to V2 backlog instead:

- Parallel workflow branches (sequential only in V1)
- Priority queues or preemption (FIFO only)
- Semver workflow versioning (v1/v2 labels only)
- Fact vs interpretation split in memory
- Compensation workflows
- Automatic SLA breach escalation
- Background pattern extraction (Hands)
- Full access control matrix enforcement

---

## PR checklist

Before merging any PR, verify:

- [ ] No provider SDK imported directly in agent code
- [ ] No raw SQL against tasks table outside `core/task_store/`
- [ ] No direct memory writes from agents (must go via extraction worker)
- [ ] All new events include `event_id`, `idempotency_key`, `sequence_number`
- [ ] All consumers handle duplicate events safely
- [ ] Type hints on all new function signatures
- [ ] Integration test for the affected phase still passes
- [ ] None of the 10 invariants in ARCHITECTURE.md are violated