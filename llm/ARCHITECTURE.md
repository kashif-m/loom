# ARCHITECTURE.md

## What this system is

A virtual organisation orchestration system. It routes work through a hierarchy of LLM-powered agents, tracks every task through a state machine, and accumulates institutional memory over time. The system answers two questions for any piece of work: **what** needs to be done (workflows) and **how** to do it (agents).

---

## Core principle

> Workflows own outcomes. Agents own execution.

Workflows define what states a task must pass through and the conditions to transition between them. Agents decide how to complete each state. These two concerns are strictly separated.

---

## Agent hierarchy

```
Human
  └── Kite Runner (KR)          — org-level orchestrator, never executes work
        └── Generalist Agent    — team lead, delegates and reviews
              └── Specialist Agent  — leaf executor, uses tools, produces output
```

**Rules:**
- Specialists are always leaf nodes. They cannot delegate.
- Generalists are always non-leaf. They never execute work directly.
- KR is the single org-level orchestrator. There is one KR.
- Only generalists or KR can initiate cross-team handoffs.
- Specialists cannot read other agents' memory. Ever.

---

## Three-tier workflow system

Workflows are human-authored markdown files. They define states, not execution steps.

| Level | Owner | Purpose |
|---|---|---|
| Org-level | KR | Route task to correct team |
| Team-level | Generalist | Assign to correct specialist, track to completion |
| Agentic-level | Specialist | Execute a specific type of task |

Workflow matching is **deterministic first** (tag index), **LLM fallback second**. If no match is found, escalate to human — never guess.

---

## Three-tier memory system (knowledge plane)

| Tier | Scope | Who can read | Who can write |
|---|---|---|---|
| Agentic memory | Private per agent | Self only | Self only |
| Team memory | Shared across team | Generalist + team specialists | Generalist only (via extraction worker) |
| Org memory | Shared across org | KR + all generalists | KR only (via extraction worker) |

Memory is backed by **Graphiti** (knowledge graph with temporal indexing).

Memory writes are triggered **only on state transitions** — not on every LLM call. A memory extraction worker reads state transition events from the event bus and writes structured facts to the appropriate tier.

Retrieval cascade: agentic → team → org. Stop at the tier where confidence is sufficient.

---

## Control plane vs knowledge plane

These are strictly separated. **This separation must never be violated.**

### Control plane (what IS happening)
- Workflow runtime (LangGraph state machine)
- Task / Case Store (Postgres)
- Event bus (Redis Streams)
- Raw event log (append-only Postgres)
- Escalation manager
- SLA monitor

### Knowledge plane (what WAS learned)
- Graphiti memory (agentic + team + org)
- Memory extraction worker
- Cascade retrieval engine

**The bridge is one-way:** the context injector reads from knowledge plane and injects into agent prompts before execution. The knowledge plane never writes back to the control plane. No exceptions.

---

## Task / Case Store

Single source of truth for all task state. Lives in Postgres.

**Core fields:**
```
task_id             UUID, immutable primary key
workflow_id         which workflow matched
workflow_version    version pinned at creation (never changes mid-task)
owner_agent_id      current responsible agent
team_id             current owning team
current_state       state machine position
version             int, increments on every transition — optimistic lock key
retry_count         attempts at current state
escalation_count    times escalated
sla_deadline        timestamp, breach triggers escalation
status              enum: open | blocked | escalated | closed
created_at / updated_at / closed_at
```

**Relational tables (separate):**
- `task_history` — append-only, one row per transition
- `task_artifacts` — references only (URLs/IDs), no raw data
- `task_blockers` — active and resolved blockers

**The `version` field is the most important field in the schema.** All duplicate-transition protection lives here. Always increment on write, always check on transition (optimistic locking).

---

## Event bus

Redis Streams. All components communicate via events — not direct calls.

**Typed event contracts:**
```
task.created
task.assigned
task.state_transition
task.blocked
task.completed
workflow.escalated
memory.write
agent.tool_call
```

Every event carries:
- `event_id` — UUID
- `idempotency_key` — `task_id:transition`
- `sequence_number` — per task
- `produced_at` — timestamp

Delivery is **at-least-once**. All consumers must be idempotent.

---

## Workflow engine

1. Loads markdown workflow files from `/workflows/` on startup and hot-reloads on file change
2. Indexes workflows by tags for deterministic matching
3. Falls back to LLM similarity match if no deterministic match
4. Escalates to human if confidence is below threshold
5. Runs LangGraph state machine for matched workflow
6. Guards transitions — checks success condition before advancing state
7. Logs every transition to audit trail

---

## LLM abstraction layer

All LLM calls go through `src/core/llm/client.py`. Agents never import provider SDKs directly.

```python
from core.llm.client import complete
from core.llm.models import ModelRole

response = await complete(role=ModelRole.REASONING, messages=[...])
```

Model strings are resolved from environment variables at runtime via **LiteLLM**. Swapping providers requires only `.env` changes — zero code changes.

**Two model roles:**
- `FAST` — workflow matching, memory extraction, intent tagging. Default: `claude-haiku-4-5-20251001`
- `REASONING` — specialist execution, generalist decisions, self-reflection. Default: `claude-sonnet-4-5`

---

## Tool layer

**OpenFang** provides the tool registry (53+ built-in tools), MCP connector, and Merkle audit trail.

Tool access is per-agent and defined in agent config JSON. Agents only receive the tools listed in their `permitted_tools` field. Nothing else.

**ZeroClaw** is the specialist agent runtime. It loads AIEOS identity configs, sandboxes execution, and intercepts all tool calls for logging.

---

## Org kernel — 10 non-negotiable invariants

These are enforced in code AND documented here. Any PR that violates one of these is wrong by definition.

```
INV-01  Task state lives only in Task Store. Agents never hold authoritative state locally.
INV-02  Only workflow runtime may transition task state. No agent writes state directly.
INV-03  All state transitions emit an append-only event. No silent transitions ever.
INV-04  Memory never mutates control plane state. Knowledge plane is read-only from control.
INV-05  No agent reads another agent's private memory. Ever. No exceptions.
INV-06  Specialists cannot initiate cross-team handoffs. Only generalists or KR.
INV-07  Workflow definitions are human-owned. Agents may suggest changes, never apply them.
INV-08  Every in-flight task is pinned to the workflow version that created it.
INV-09  All event consumers are idempotent. Duplicate events must produce no new side effects.
INV-10  All escalations are explicit events in the event bus. No implicit failure swallowing.
```

---

## V1 scope (what is and is not built yet)

### In V1
- Sequential workflows only (no parallel branches)
- FIFO queue per team (no priority levels)
- Simple agent config JSON (no full topology model)
- v1/v2 workflow versioning (no semver)
- 3 evaluation signals on task close: `completed`, `rework_count`, `false_escalation`
- Memory writes: facts only (no interpretation/confidence layer)
- ALL_SUCCESS join policy only
- Manual SLA monitoring via KR polling

### Deferred to V2
- Parallel branches + join policies
- P0–P3 priority + preemption
- Full agent topology model
- Semver workflow versioning + migration
- Full 9-metric evaluation layer
- Fact vs interpretation split in memory
- Compensation workflows
- SLA breach auto-escalation
- Explicit access control matrix
- Background Hands pattern extraction

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Package manager | uv |
| Data validation | Pydantic v2 |
| State machine | LangGraph |
| Specialist runtime | ZeroClaw + AIEOS |
| LLM routing | LiteLLM |
| Task store | Postgres 16 (asyncpg + SQLAlchemy) |
| Event bus | Redis 7 Streams (redis-py async) |
| Memory / knowledge graph | Graphiti (SQLite in dev, Neo4j in prod) |
| Tool layer | OpenFang + Composio |
| API | FastAPI |
| Testing | Pytest + pytest-asyncio |
| Logging | Loguru |
| Config | Pydantic Settings |
| Local dev | Docker + docker-compose |