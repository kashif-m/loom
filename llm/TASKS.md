# TASKS.md

## How to use this file

Work top to bottom. Each phase has an integration test at the end — **do not start the next phase until it passes.** Tasks within a phase can be done in any order unless marked with a dependency (→).

Estimated effort assumes ~6 focused hours per day as a solo builder.

---

## Phase 0 — Scaffolding
**Goal:** Working local environment, empty repo skeleton, invariants documented.
**Effort:** 3 days

---

### TASK-001 — Monorepo setup + Nix dev environment
Set up the project structure and Nix-based dev environment.

**Deliverables:**
- `flake.nix` — Nix flake providing: Python 3.11, uv, ruff, pyright, Node 20, pnpm, docker, docker-compose, postgresql CLI, redis-cli, jq, curl, watchman. Shell hook auto-creates venv, syncs deps, copies .env.example, defines aliases.
- `.envrc` — direnv integration (`use flake`). After `direnv allow`, entering the project directory activates the shell automatically.
- `pyproject.toml` with uv, Python 3.11+, initial dependencies: `pydantic`, `pydantic-settings`, `litellm`, `loguru`, `fastapi`, `uvicorn`, `asyncpg`, `sqlalchemy[asyncio]`, `redis`, `langgraph`, `pytest`, `pytest-asyncio`, `watchdog`, `docker`
- Directory skeleton: `src/core/`, `src/agents/`, `src/memory/`, `src/evaluation/`, `src/api/`, `workflows/`, `agents_config/`, `tests/unit/`, `tests/integration/`, `infra/`, `.data/` (gitignored)
- `src/__init__.py` in every package directory
- `.env.example` — all required env vars with comments (LLM models, DB, Redis, Graphiti, workflow engine, sandbox, logging)
- `.gitignore` — exclude `.env`, `__pycache__`, `.venv`, `.data/`, `result` (nix build output)
- `Makefile` — thin wrappers around the shell aliases defined in flake.nix: `dev`, `stop`, `migrate`, `test`, `lint`, `fmt`, `typecheck`, `api`, `ui-dev`

**Setup flow (from fresh clone):**
```bash
nix develop          # or: direnv allow (auto on cd if direnv installed)
dev                  # starts Postgres + Redis + Neo4j via docker-compose
migrate              # runs DB migrations
api                  # starts FastAPI on :8000
```

---

### TASK-002 — Docker-compose local stack
**Depends on:** TASK-001

**Deliverables:**
- `docker-compose.yml` with services: `postgres:16`, `redis:7`, `neo4j:5` (optional, for Graphiti)
- `infra/postgres/init.sql` — creates database and user
- `infra/redis/redis.conf` — enable streams, set memory limit
- Verify: `docker-compose up` starts all services cleanly
- Verify: Python can connect to Postgres and Redis from `src/`

---

### TASK-003 — Invariants and PR checklist
**Depends on:** TASK-001

**Deliverables:**
- `INVARIANTS.md` at repo root — copy all 10 invariants from ARCHITECTURE.md, one per section with a short implementation note for each
- `CODING_GUIDELINES.md` PR checklist section visible in repo
- `docs/decisions/` directory — empty, for future ADRs

---

## Phase 1 — Task Store + Event Bus
**Goal:** Tasks can be created, transitioned, and events flow through the bus into the log.
**Effort:** 5 days

**Integration test gate:** `tests/integration/test_phase1.py`
- Create a task → verify it exists in Postgres with correct fields
- Transition task state → verify version incremented, history row appended
- Emit event from bus → verify it appears in raw event log
- Emit duplicate event → verify consumer skips it (idempotency)

---

### TASK-004 — Task store schema and migrations
**Depends on:** TASK-002

Create the task store schema.

**Deliverables:**
- `src/core/task_store/models.py` — Pydantic models: `Task`, `TaskHistory`, `TaskArtifact`, `TaskBlocker`
- `infra/postgres/migrations/001_task_store.sql`:
  ```sql
  tasks (task_id, workflow_id, workflow_version, owner_agent_id, team_id,
         current_state, version, retry_count, escalation_count, sla_deadline,
         status, created_at, updated_at, closed_at)
  task_history (id, task_id, from_state, to_state, agent_id, event_id, transitioned_at)
  task_artifacts (id, task_id, type, reference_url, agent_id, created_at)
  task_blockers (id, task_id, description, raised_by, raised_at, resolved_at)
  ```
- Indexes on: `task_id`, `status`, `team_id`, `owner_agent_id`
- Migration runner script or Alembic config

---

### TASK-005 — Task store operations
**Depends on:** TASK-004

Implement all 7 operations. Each must be unit tested independently.

**Deliverables:**
- `src/core/task_store/operations.py`:
  - `create_task(workflow_id, workflow_version, owner_agent_id, team_id, sla_deadline?) -> Task`
  - `transition_state(task_id, to_state, current_version, agent_id, event_id) -> Task` — raises `StaleTaskVersionError` on version mismatch
  - `record_blocker(task_id, description, raised_by) -> TaskBlocker`
  - `resolve_blocker(task_id, blocker_id) -> TaskBlocker`
  - `attach_artifact(task_id, type, reference_url, agent_id) -> TaskArtifact`
  - `escalate(task_id, reason, agent_id) -> Task` — increments escalation_count, updates owner
  - `close_task(task_id, outcome, agent_id) -> Task`
- `src/core/exceptions.py` — `StaleTaskVersionError`, and other custom exceptions
- `tests/unit/test_task_store.py` — one test per operation, including version mismatch test

---

### TASK-006 — Event bus producer and consumer
**Depends on:** TASK-002

**Deliverables:**
- `src/core/event_bus/schemas.py` — Pydantic models for all 8 event types. Every model includes `event_id: UUID`, `idempotency_key: str`, `sequence_number: int`, `produced_at: datetime`
- `src/core/event_bus/producer.py` — `async def emit(event: BaseEvent) -> None` using Redis Streams (`XADD`)
- `src/core/event_bus/consumer.py` — consumer group wrapper, `async def consume(stream, group, handler)`, includes `event_id` dedup check against a Redis SET with TTL
- `src/core/event_bus/raw_log.py` — appends every consumed event to `raw_events` Postgres table
- `infra/postgres/migrations/002_raw_event_log.sql` — `raw_events(event_id, stream, payload jsonb, received_at)`
- `tests/unit/test_event_bus.py` — emit, consume, dedup

---

### TASK-007 — Phase 1 integration test
**Depends on:** TASK-005, TASK-006

Write and pass `tests/integration/test_phase1.py`. See gate criteria above. Do not proceed to Phase 2 until this passes cleanly.

---

## Phase 2 — Workflow Engine
**Goal:** Markdown workflow files are loaded, matched against tasks, and drive a LangGraph state machine.
**Effort:** 8 days

**Integration test gate:** `tests/integration/test_phase2.py`
- Load a workflow file → verify it appears in registry with correct fields
- Match a task description with exact tags → verify deterministic match
- Match an ambiguous task → verify LLM fallback fires
- Unmatched task → verify escalation event emitted
- Drive a task through all states in a test workflow → verify history correct

---

### TASK-008 — LLM abstraction layer
**Depends on:** TASK-001

This must exist before any LLM call is written anywhere else.

**Deliverables:**
- `src/core/llm/models.py` — `ModelRole(str, Enum)`: `FAST`, `REASONING`, `LOCAL`
- `src/core/llm/schemas.py` — `Message`, `Tool`, `LLMResponse` (provider-agnostic Pydantic models)
- `src/core/llm/config.py` — `LLMConfig(BaseSettings)`: `fast_model`, `reasoning_model`, `local_model`, `fallback_model`, `max_retries`, `timeout_seconds`
- `src/core/llm/client.py`:
  - `async def complete(role, messages, tools?, temperature?) -> LLMResponse`
  - `async def complete_structured(role, messages, response_model) -> BaseModel`
  - Internal `_call_litellm()` — never called outside this file
- `tests/unit/test_llm_client.py` — mock litellm, verify role resolves to correct model string

---

### TASK-009 — Workflow file parser and validator
**Depends on:** TASK-008

**Deliverables:**
- `src/core/workflow_engine/schemas.py` — `WorkflowDefinition` Pydantic model with all required fields: `id`, `version`, `level`, `trigger`, `tags`, `states`, `success_condition`, `escalate_if`
- `src/core/workflow_engine/parser.py` — reads markdown files, extracts YAML frontmatter, validates against schema, returns `WorkflowDefinition`
- Parser rejects invalid files with a clear log message — does not crash the service
- `tests/unit/test_parser.py` — valid file, missing field, invalid level, duplicate id

---

### TASK-010 — Workflow registry and hot reload
**Depends on:** TASK-009

**Deliverables:**
- `src/core/workflow_engine/registry.py` — in-memory store, indexed by `id`, by `level`, and by `tags` (inverted index for deterministic matching)
- `src/core/workflow_engine/hot_reload.py` — uses `watchdog` to watch `/workflows/` directory, re-parses and re-registers on file change, logs reload events
- Registry exposes: `register(workflow)`, `get_by_id(id)`, `search_by_tags(tags) -> list[WorkflowDefinition]`, `all_by_level(level) -> list[WorkflowDefinition]`

---

### TASK-011 — Workflow matcher
**Depends on:** TASK-010, TASK-008

Two-stage matching: deterministic first, LLM fallback second.

**Deliverables:**
- `src/core/workflow_engine/matcher.py`:
  - Stage 1: extract tags from task description (simple keyword extraction, no LLM), look up in registry tag index, return match if found
  - Stage 2: embed task description via `complete(FAST, ...)` with a structured prompt, rank against all workflow triggers by similarity, return best match if above threshold (default: 0.75)
  - Stage 3: return `None` if below threshold — caller handles escalation
- Config: `MATCH_CONFIDENCE_THRESHOLD` env var (default 0.75)
- Every match attempt is logged with which stage matched and confidence score
- `tests/unit/test_matcher.py` — exact tag match, LLM fallback match, no match

---

### TASK-012 — State machine runtime
**Depends on:** TASK-011, TASK-005, TASK-006

**Deliverables:**
- `src/core/workflow_engine/runtime.py` — LangGraph-based state machine:
  - Builds a graph from `WorkflowDefinition.states` (linear transitions in V1)
  - Each node calls the appropriate agent to complete the state
  - Transition guard: calls `complete(FAST, ...)` to evaluate whether success condition is met before advancing
  - On guard pass: calls `transition_state()` in task store, emits `task.state_transition` event
  - On guard fail: increments retry, checks `escalate_if` condition, emits `workflow.escalated` if met
  - On final state: calls `close_task()`, emits `task.completed`
- `tests/unit/test_runtime.py` — mock agent calls, verify state transitions, verify escalation on max retries

---

### TASK-013 — Phase 2 integration test
**Depends on:** TASK-012

Write and pass `tests/integration/test_phase2.py`. See gate criteria above.

---

## Phase 3 — Agent Layer
**Goal:** Full orchestration loop working end to end. Human task in, result back.
**Effort:** 12 days

**Integration test gate:** `tests/integration/test_phase3.py`
- Submit task via API → KR matches workflow → creates task → delegates to generalist
- Generalist matches team workflow → assigns to specialist
- Specialist executes → returns result → generalist reviews → notifies KR
- KR closes task → human notified
- Verify task history shows all state transitions

---

### TASK-014 — Agent identity loader
**Depends on:** TASK-008

**Deliverables:**
- `src/agents/base/identity.py` — `AgentConfig` Pydantic model, `load_identity(agent_id) -> AgentConfig` reads from `/agents_config/{agent_id}.json`
- `agents_config/` — JSON files for: `kite_runner.json`, `engineering_generalist.json`, `frontend_specialist.json`
- Validate `authority_level` (must be `kr | generalist | specialist`)
- Validate `model_role` (must be `fast | reasoning`)
- Validate `memory_scope` (must be `agentic_only | agentic_and_team | agentic_team_and_org`)
- `tests/unit/test_identity.py`

---

### TASK-015 — Specialist agent
**Depends on:** TASK-014, TASK-012

**Deliverables:**
- `src/agents/specialist/agent.py`:
  - Loads identity config
  - Queries own agentic memory (stub for now — memory layer is Phase 4)
  - Assembles system prompt from identity + task context + memory context
  - Calls `complete(ModelRole.REASONING, ...)` in a tool-use loop via LangGraph
  - Emits `agent.tool_call` event for every tool call
  - Self-reflection loop: after completing, calls `complete(FAST, ...)` to verify output meets the state's success condition. If not, retries up to `max_retries`
  - Returns structured result to generalist
- `src/agents/specialist/tools.py` — OpenFang tool registry bridge, enforces `permitted_tools` from identity config
- `src/agents/base/reflection.py` — reusable self-reflection prompt + evaluation logic
- `tests/unit/test_specialist.py` — mock LLM + tools, verify tool loop, verify reflection

---

### TASK-016 — Generalist agent
**Depends on:** TASK-015

**Deliverables:**
- `src/agents/generalist/agent.py`:
  - Receives delegated task from KR
  - Matches team-level workflow via `matcher.py`
  - Assigns task state to available specialist (FIFO from team config — hardcoded list of specialists in V1)
  - Calls specialist, awaits result
  - Output review: calls `complete(FAST, ...)` to evaluate specialist output against success condition
  - On approval: calls `transition_state()`, emits event, reports to KR
  - On rejection: increments retry, reassigns to specialist
  - On max retries: calls `escalate()`, emits `workflow.escalated`
- `src/agents/generalist/join_gate.py` — ALL_SUCCESS gate (sequential in V1 — just awaits single specialist result and checks success)
- `tests/unit/test_generalist.py`

---

### TASK-017 — Kite Runner
**Depends on:** TASK-016

**Deliverables:**
- `src/agents/kite_runner/agent.py`:
  - Receives task from API gateway
  - Matches org-level workflow via `matcher.py`
  - On match: calls `create_task()`, delegates to correct generalist (hardcoded team→generalist map in V1)
  - On no match: emits `workflow.escalated`, notifies human via notification stub
  - Notification stub: `notify_human(task_id, message)` — logs to stdout + writes to a `notifications` Postgres table (no real notification in V1)
- `src/agents/kite_runner/polling.py` — background task, runs every 5 minutes, queries tasks with `status=open` older than threshold, emits `workflow.escalated` if stuck
- `tests/unit/test_kite_runner.py`

---

### TASK-018 — API gateway
**Depends on:** TASK-017

**Deliverables:**
- `src/api/gateway.py` — FastAPI app
- `src/api/routes/tasks.py`:
  - `POST /tasks` — accepts `{description: str}`, passes to KR, returns `{task_id, status}`
  - `GET /tasks/{task_id}` — returns full task record + history
  - `GET /tasks` — list tasks, filter by `status`, `team_id`
- `src/api/routes/health.py` — `GET /health` returns Postgres + Redis connectivity status
- `tests/unit/test_api.py`

---

### TASK-019 — Phase 3 integration test
**Depends on:** TASK-018

Write and pass `tests/integration/test_phase3.py`. This is the first full end-to-end loop. Budget 2 days — prompt tuning and integration debugging will be needed. Do not move to Phase 4 until this passes.

---

## Phase 4 — Memory Layer
**Goal:** Completed tasks write structured facts to Graphiti. New tasks retrieve relevant context.
**Effort:** 10 days

**Integration test gate:** `tests/integration/test_phase4.py`
- Complete a task → verify memory extraction worker fires → facts written to Graphiti agentic tier
- Run a second identical task → verify specialist receives context from memory
- Verify generalist reads team memory, not agentic memory
- Verify KR reads org memory only

---

### TASK-020 — Graphiti setup
**Depends on:** TASK-002

**Deliverables:**
- `src/memory/graphiti/client.py` — Graphiti connection, using SQLite backend in dev
- `src/memory/graphiti/schemas.py` — `MemoryNode` Pydantic model: `content`, `type` (fact), `provenance` (source event_id + task_id), `created_at`, `tier` (agentic|team|org)
- `src/memory/graphiti/writer.py` — `write_to_tier(node, tier, agent_id)` — enforces access rules (see ARCHITECTURE.md), raises `MemoryAccessDeniedError` if violated
- `tests/unit/test_graphiti_client.py` — write, read, access denial

---

### TASK-021 — Memory extraction worker
**Depends on:** TASK-020, TASK-006

**Deliverables:**
- `src/memory/event_worker/worker.py` — Redis Streams consumer, subscribes to `task.state_transition` and `task.completed` events only (ignores all others)
- `src/memory/event_worker/processor.py`:
  - Calls `complete(FAST, ...)` with a structured extraction prompt
  - Extracts: task description, what was attempted, blockers encountered, outcome, key learnings
  - Writes facts to correct memory tier based on the emitting agent's `authority_level`
  - Checks `event_id` before writing — skips if already processed (idempotent)
- Extraction prompt template — returns structured JSON: `{facts: [{content, type, provenance}]}`
- `tests/unit/test_extraction_worker.py` — mock LLM, verify correct tier written, verify idempotency

---

### TASK-022 — Cascade retrieval and context injection
**Depends on:** TASK-021

**Deliverables:**
- `src/memory/graphiti/retrieval.py` — `query_tier(query, tier, agent_id) -> list[MemoryNode]`
- `src/agents/base/memory.py`:
  - `query_memory(agent_id, memory_scope, query) -> str` — cascade: query agentic first, add team if scope allows and confidence low, add org if scope allows and confidence still low
  - Returns assembled context string ready to inject into system prompt
  - Confidence heuristic for V1: if agentic tier returns 0 results, try next tier
- Wire into `specialist/agent.py` and `generalist/agent.py` — replace memory stubs from Phase 3
- `tests/unit/test_memory_retrieval.py` — cascade order, scope enforcement, empty tier fallthrough

---

### TASK-023 — Phase 4 integration test
**Depends on:** TASK-022

Write and pass `tests/integration/test_phase4.py`. Budget time for qualitative evaluation — run real tasks and manually check what context is retrieved. The test suite validates structural correctness; you validate quality by reading the output.

---

## Phase 5 — Hardening
**Goal:** The system is reliable under failure conditions.
**Effort:** 10 days

**Integration test gate:** `tests/integration/test_phase5.py`
- Emit duplicate event → no duplicate state transition
- Specialist fails 3 times → task escalated to human
- SLA exceeded → KR detects and escalates
- Dead task (max retries) → lands in human review queue
- Replay event stream → no duplicate memory writes

---

### TASK-024 — Idempotency hardening
**Depends on:** TASK-019

Audit every consumer and harden.

**Deliverables:**
- Review all event consumers — add `event_id` dedup check to any that are missing it
- Add version mismatch test to `test_task_store.py` — concurrent transition attempt must fail gracefully
- Replay test: manually replay 10 events through the bus, verify task store and memory are unchanged
- `tests/integration/test_phase5.py` (idempotency section)

---

### TASK-025 — Retry and escalation logic
**Depends on:** TASK-017

**Deliverables:**
- Enforce `max_retries` per state in workflow runtime — read from workflow definition or fall back to global config (`MAX_RETRIES_PER_STATE`, default: 3)
- `escalate_if` condition evaluated after each retry by `complete(FAST, ...)` against the condition string from workflow file
- Dead task handler: when `escalation_count` exceeds `MAX_ESCALATIONS` (default: 3), set `status=blocked`, write to `human_review_queue` Postgres table, notify human
- `infra/postgres/migrations/003_human_review_queue.sql`
- `tests/unit/test_escalation.py`

---

### TASK-026 — SLA polling
**Depends on:** TASK-017

**Deliverables:**
- `src/agents/kite_runner/polling.py` (extend from TASK-017):
  - Query tasks where `sla_deadline < now()` and `status = open`
  - Emit `workflow.escalated` event for each breached task
  - Log breach with `task_id`, `sla_deadline`, `current_state`
- Config: `SLA_POLL_INTERVAL_SECONDS` (default: 300)
- `tests/unit/test_sla_polling.py`

---

### TASK-027 — Basic evaluation signals
**Depends on:** TASK-019

**Deliverables:**
- `src/evaluation/signals.py`:
  - Triggered on `task.completed` event
  - Computes 3 signals:
    - `completed_successfully: bool` — was final state reached without escalation?
    - `rework_count: int` — count of retries across all states (from task_history)
    - `false_escalation: bool` — escalation occurred but task resolved without human input within 30 min
  - Writes evaluation record to `task_evaluations` Postgres table
- `infra/postgres/migrations/004_task_evaluations.sql`
- `tests/unit/test_evaluation.py`

---

### TASK-028 — Smoke test suite
**Depends on:** TASK-024, TASK-025, TASK-026, TASK-027

Write the full unhappy path smoke tests.

**Deliverables:**
- `tests/integration/test_phase5.py` covering:
  1. Happy path end-to-end (regression from Phase 3 gate)
  2. Specialist retry → eventual success
  3. Specialist max retries → task escalated to human
  4. Cross-team handoff mid-execution (generalist A → generalist B → back)
  5. SLA breach → KR detects → human notified
- All 5 scenarios pass before V1 is considered complete

---

## V1 complete milestone

When `tests/integration/test_phase5.py` passes cleanly, V1 is done.

At this point you have:
- A working orchestration loop (human → KR → generalist → specialist → result)
- Reliable task state tracking with optimistic locking
- Event-driven architecture with idempotent consumers
- Structured memory that accumulates across tasks
- Human escalation paths for every failure mode
- Basic evaluation signals for systematic improvement

**Show it to someone. Get feedback. Let that feedback drive V2 priorities.**

---

## V2 backlog (do not build yet)

Add to this list as pain points emerge in V1.

- [ ] Parallel workflow branches + join policies
- [ ] P0–P3 task priority + preemption
- [ ] Full agent topology model
- [ ] Semver workflow versioning + in-flight migration
- [ ] Full 9-metric evaluation layer
- [ ] Fact vs interpretation split in memory + confidence scoring
- [ ] Compensation workflows for parallel branch failures
- [ ] Auto SLA breach escalation (currently polling-based)
- [ ] Explicit access control matrix (multi-tenant)
- [ ] Background Hands pattern extraction → workflow suggestions
- [ ] Neo4j migration for Graphiti (when SQLite gets slow)
- [ ] Real notification delivery (email/Slack — currently logs only)

---

## Phase 6 — UI
**Goal:** Minimal functional web UI. Non-technical users can submit tasks, track progress, respond to escalations, view live activity, and approve workflows.
**Effort:** 8 days

**Gate:** All 6 pages render correctly, escalation response updates task in backend, SSE feed streams live events, workflow approval changes status in registry.

---

### TASK-029 — Next.js project scaffold
**Depends on:** TASK-018 (API gateway complete)

**Deliverables:**
- `ui/` directory at monorepo root (sibling to `src/`)
- Next.js 14 with App Router, TypeScript, Tailwind CSS
- `ui/package.json` — dependencies: `@tanstack/react-query`, `react-hook-form`, `zod`, `lucide-react`, `eventsource-parser`
- `ui/lib/api.ts` — typed API client wrapping all backend endpoints
- `ui/lib/types.ts` — TypeScript types mirroring Pydantic models from backend
- `ui/.env.local.example` — `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Proxy config in `next.config.js` — `/api/*` proxied to FastAPI in dev
- Reusable components: `StatusBadge`, `LoadingSpinner`, `ErrorMessage`, `EmptyState`, `PageHeader`
- `docker-compose.yml` updated — add `ui` service on port 3000

---

### TASK-030 — Dashboard page (`/`)
**Depends on:** TASK-029

**Deliverables:**
- Escalation banner: queries `GET /tasks?status=escalated`, shows count + link if any pending. Sticky at top. Red background. Never dismissible without resolving.
- Task summary counts: 3 stat cards — Open, Blocked, Completed today. Poll every 30s via React Query.
- Recent tasks table (last 20): columns — ID (truncated), Description, Team, Status badge, Current state, Last updated. Clicking row navigates to `/tasks/[task_id]`.
- "Submit new task" button → `/tasks/new`
- Apply non-technical language map from UI_SPEC.md to all labels

---

### TASK-031 — Submit task page (`/tasks/new`)
**Depends on:** TASK-029

**Deliverables:**
- Single form: description textarea (required, 20–2000 chars), priority hint select (Low/Normal/Urgent)
- Submit calls `POST /tasks`, shows loading state ("Routing your task...")
- On success: redirect to `/tasks/[task_id]`
- On error: inline error message, no redirect, form stays filled
- Zod validation schema on client side matching backend requirements

---

### TASK-032 — Task list page (`/tasks`)
**Depends on:** TASK-029

**Deliverables:**
- Filter bar: Status multiselect, Team select, Date range (from/to). State persisted in URL query params.
- Table with all columns from UI_SPEC.md. Paginated at 20/page.
- "Needs your input" tasks sorted to top regardless of active filter.
- Empty state component for no results.
- Each row links to task detail.

---

### TASK-033 — Task detail page (`/tasks/[task_id]`)
**Depends on:** TASK-031, TASK-032

This is the most important page. Build it carefully.

**Deliverables:**

- **Header:** Task ID, description, status badge, current state (human-readable), team, assigned agent, created/updated timestamps, SLA indicator (green "Due in Xh" or red "Overdue by Xh").

- **Escalation panel** (visible only when `status = escalated`):
  - Amber banner with "This task needs your input"
  - Blocker description (from task_blockers)
  - Context: what was tried (from task_history)
  - Textarea: "Provide additional details or instructions" (required)
  - "Send response" button → `POST /tasks/{task_id}/respond`
  - "Reassign to different team" button → opens team selector → `POST /tasks/{task_id}/reassign`
  - On submit: optimistic update, then refetch task

- **Progress timeline:** Vertical timeline from task_history. Each item: state name (human-readable), agent name, timestamp, duration since previous state. Most recent at top.

- **Artifacts section:** List of attached artifacts. Type icon + clickable reference link + agent + timestamp. "No outputs yet" empty state.

- **Blockers section:** Active blockers (no resolved_at) shown first in amber. Resolved blockers in gray with strikethrough.

- **Technical detail (collapsed):** Raw JSON of task record. Visible only when expanded. Label: "Technical details" with chevron toggle.

- Poll every 15 seconds while task is open. Stop polling when status = closed.

---

### TASK-034 — Agent activity feed (`/activity`)
**Depends on:** TASK-029

**Backend prerequisite:** Add `GET /events/stream` SSE endpoint to FastAPI before building this page. Reads from Redis Streams, converts to SSE, filters out `memory.write` events.

**Deliverables:**
- SSE connection using `EventSource` API with auto-reconnect (exponential backoff, max 30s)
- Feed renders newest events at top, max 200 items (older items removed from DOM)
- Each feed item: timestamp (relative — "2m ago"), agent name + role badge, human-readable event description, task ID as link to task detail
- Apply event → human-readable label map from UI_SPEC.md
- Filter bar: event type multiselect, agent name input, team select
- "Pause feed" toggle — freezes rendering, SSE still connected, queues new items
- "Live" / "Paused" indicator badge
- Connection status indicator: green dot (connected), amber (reconnecting), red (failed)
- `GET /events/stream` SSE backend endpoint in `src/api/routes/events.py`

---

### TASK-035 — Workflow definitions pages (`/workflows`, `/workflows/[workflow_id]`)
**Depends on:** TASK-029

**Backend prerequisite:** Add workflow API routes before building this page:
- `GET /workflows` — list from registry
- `GET /workflows/{workflow_id}` — detail + version history
- `PATCH /workflows/{workflow_id}/status` — approve or deprecate

**Deliverables:**

- **List page (`/workflows`):**
  - Table: workflow ID, display name, level badge (org/team/agentic), version, status badge (draft/active/deprecated), last modified
  - Filter by level, status
  - Draft workflows highlighted with amber left border — "waiting for approval"
  - Empty state

- **Detail page (`/workflows/[workflow_id]`):**
  - Metadata section: id, version, level, status, trigger text, tags as pills
  - States list: ordered, numbered, each state on its own row
  - Success condition + escalation conditions in distinct visual blocks
  - Raw markdown rendered as syntax-highlighted code block (read-only)
  - If `status = draft`: amber banner "This workflow is pending approval" + "Approve and activate" button
  - If `status = active`: "Deprecate" button (with confirmation modal — "Are you sure?")
  - Version history: table of prior versions, each with status and link
  - On approve/deprecate: optimistic update + refetch

---

### TASK-036 — SSE backend endpoint
**Depends on:** TASK-018

This is a backend task but is prerequisite for TASK-034.

**Deliverables:**
- `src/api/routes/events.py` — `GET /events/stream` SSE endpoint using FastAPI's `StreamingResponse`
- Reads from Redis Streams consumer group
- Converts each event to SSE format: `data: {json}\n\n`
- Filters out `memory.write` events before sending
- Converts raw event field names to UI-friendly labels (use language map from UI_SPEC.md)
- Heartbeat every 15 seconds to keep connection alive
- `tests/unit/test_events_sse.py`

---

### TASK-037 — Backend escalation response endpoints
**Depends on:** TASK-018, TASK-025

**Deliverables:**
- `POST /tasks/{task_id}/respond` — accepts `{message: str}`, writes message to task as blocker resolution context, calls `resolve_blocker()`, re-triggers workflow from current state
- `POST /tasks/{task_id}/reassign` — accepts `{team_id: str}`, calls `escalate()` with new team, updates task owner
- Both endpoints emit appropriate events to event bus
- `tests/unit/test_escalation_endpoints.py`

---

### TASK-038 — Phase 6 UI integration test
**Depends on:** TASK-036, TASK-037, TASK-033, TASK-034, TASK-035

**Deliverables:**
- Manual test checklist (not automated — UI testing is expensive):
  - [ ] Submit task via form → task appears in dashboard within 30s
  - [ ] Task progresses through states → timeline updates on detail page
  - [ ] Task escalates → banner appears on dashboard, escalation panel on detail page
  - [ ] Human responds to escalation → task resumes, banner disappears
  - [ ] Activity feed shows live events as task progresses
  - [ ] New workflow file added to repo → appears as draft in UI
  - [ ] Approve workflow → status changes to active in UI
  - [ ] All pages load without errors for a non-technical user mental model test

---

## V2 UI backlog

- Email / Slack notification delivery
- Memory explorer (browse what agents have learned)
- Evaluation metrics dashboard
- Visual workflow canvas / editor
- Role-based access control
- Mobile-optimised layout
- Bulk task actions
- Full-text task search