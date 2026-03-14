# TASKS.md - Loom Implementation Tracker

## Completed: GUI Restructure (2026-03-13)

### Backend Changes
- [x] Added `Organization` model to `loom/models.py`
- [x] Added `OrganizationRow` table to `loom/persistence/db.py`
- [x] Added `OrganizationRepository` to `loom/persistence/repositories.py`
- [x] Added organization API endpoints (`/api/organization`) to `loom/ui/router.py`

### Frontend Changes
- [x] Complete UI restructure with 4 main screens:
  - **Organization** - Settings for org name, LiteLLM, OpenAI, OpenCode config
  - **Agents** - List view + 5-step creation wizard
  - **Workflows** - List view + split-view markdown editor with preview
  - **Tasks** - Console for intake/execution + task list
- [x] Navigation sidebar with icons
- [x] Tab-based sub-navigation per screen
- [x] Modern responsive styling

### Key Features
1. **Organization Settings**: 
   - Configure org name
   - LiteLLM: URL, API key, default model (e.g., `open-large`)
   - OpenAI: API key, model
   - OpenCode: enable toggle, command path
2. **Agent Wizard**: 5-step creation (Basic Info → Capabilities → Connectors → Policies → Review)
3. **Workflow Editor**: Markdown editor with live preview showing agent assignments
4. **Task Console**: Intake, run, retry, trace tasks with status badges

## Architecture: How Agents Work

### Agent Types
```
┌─────────────────────────────────────────────────────────────┐
│  Agent (Role)                                                │
│  ├── Capabilities (what it can do)                          │
│  │   └── connector_binding: opencode | git | gh | litellm   │
│  ├── Policies (enforcement rules)                           │
│  └── Prompt Profile (system prompt for LLM)                 │
└─────────────────────────────────────────────────────────────┘
```

### Connector Types
| Connector | Purpose | API Key Location |
|-----------|---------|------------------|
| **opencode** | Repository context, code operations | CLI-based (no key) |
| **litellm** | LLM calls via LiteLLM proxy | Organization.litellm_api_key |
| **openai** | Direct OpenAI API calls | Organization.openai_api_key |
| **git** | Git operations | SSH keys |
| **gh** | GitHub CLI operations | GitHub token |

### LLM Model Flow
```
Task → Workflow Step → Agent (Role)
                          ↓
                    ModelRouter.resolve("step_execution")
                          ↓
                    LiteLLM Provider (org.litellm_base_url)
                          ↓
                    Model: org.litellm_default_model (e.g., "open-large")
```

### Creating an OpenCode Agent
1. Go to **Organization** → Enable OpenCode
2. Go to **Agents** → Create Agent
3. In wizard step 2 (Capabilities), create/select capabilities with `connector_binding: opencode`
4. Example capabilities:
   - `repo_read` (opencode)
   - `context_build` (opencode)
5. Agent will use OpenCode CLI for these operations

### Creating an LLM Persona Agent
1. Go to **Organization** → Configure LiteLLM URL/API key/model
2. Go to **Agents** → Create Agent
3. Create capability with `connector_binding: litellm` or `none`
4. The agent's prompt profile defines its "persona"
5. LLM calls use ModelRouter → LiteLLM → configured model

## Next Steps

### High Priority
- [x] Test full end-to-end flow: Org → Agent → Workflow → Task
- [x] Add capability to select model per agent (not just service/global)
- [x] Add task streaming in the GUI console using `/tasks/{task_id}/events/stream`
- [x] Add explicit CLI auth/token mode support for remote HTTP control plane (today CLI is local DB/runtime)

### Medium Priority
- [x] Add workflow version diff viewer
- [x] Add memory/query UI for episodic memory

### Low Priority
- [x] Add export/import for configurations
- [x] Add dark mode toggle
- [x] Add keyboard shortcuts

## How to Run

```bash
# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic sqlalchemy fastapi httpx uvicorn

# Run the server
python3 -m loom.app.main --serve

# Open browser
open http://127.0.0.1:8000/ui
```

## API Endpoints Added

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/organization` | GET | Get organization settings |
| `/api/organization` | POST | Update organization settings |

## Database Schema: organizations table

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| org_id | String(64) | "default" | Primary key |
| name | String(256) | "My Organization" | Organization name |
| litellm_base_url | String(512) | null | LiteLLM proxy URL |
| litellm_api_key | String(256) | null | LiteLLM API key |
| litellm_default_model | String(128) | "open-large" | Default model name |
| openai_api_key | String(256) | null | OpenAI API key |
| openai_model | String(128) | "gpt-4.1-mini" | OpenAI model |
| opencode_enabled | Boolean | false | OpenCode toggle |
| opencode_cmd | String(128) | "opencode" | OpenCode CLI command |
| created_at | DateTime | auto | Creation timestamp |
| updated_at | DateTime | auto | Last update timestamp |

## Completed: Runtime + CLI Bridge (2026-03-13)

### Backend/runtime
- [x] Model routing now reads Organization settings at execution time.
- [x] `step_execution` can resolve from organization-configured LiteLLM or OpenAI.
- [x] Organization settings can override bootstrap default LiteLLM route safely.

### UI/API contract
- [x] `/api/integrations/status` now returns a stable `commands` map.
- [x] `connectors` remains as a backward-compatible alias to `commands`.
- [x] Integration status now exposes organization-aware effective config signals.

### CLI control plane
- [x] Added `loom ctl organization` (`show`, `set`)
- [x] Added `loom ctl agent` (`list`, `create`)
- [x] Added `loom ctl workflow` (`list`, `validate`, `publish`)
- [x] Added `loom ctl task` (`intake`, `run`, `list`, `trace`)
- [x] Added `loom ctl scaffold starter` to create org + agent + workflow (+ optional task run)

### Test coverage
- [x] Added integration tests for CLI core flow.
- [x] Added integration tests for scaffold starter flow.
- [x] Added integration tests for organization-aware integration status.
- [x] Added integration tests for organization-aware model routing.

## Completed: Deterministic Ops Hardening (2026-03-13)

- [x] Added explicit workflow pinning for task intake in API/UI/CLI (`workflow_id`, `workflow_version`).
- [x] Added stricter workflow validation: owner role must be active and satisfy required capabilities.
- [x] Added declarative bundle apply (`loom ctl bundle apply --spec-file ...`) for idempotent setup.
- [x] Added example documentation organization spec at `examples/docs_org_bundle.yaml`.

## Completed: TUI-Native Docs Orchestration Bootstrap (2026-03-13)

- [x] Added reusable bundle operations module for generic spec apply (`loom/app/bundle_ops.py`).
- [x] Added chat slash command `/bundle apply <spec-file>` to load full packs from TUI shell.
- [x] Added GUI API endpoint `/api/bundle/apply` to apply YAML bundles directly from UI.
- [x] Added UI bundle textarea + apply action for no-code control plane setup.
- [x] Added full `docs.orchestration` example bundle with 9 roles, 48 capabilities, 10 policies, 5 workflows.
- [x] Added integration tests for docs orchestration bundle apply and execution path.

## Completed: Advanced Workflow Enforcement (2026-03-13)

- [x] Added fan-out intake (`intake_many`) with one-task-per-object splitting for multi-URL / multi-PR requests.
- [x] Added UI/API/CLI fan-out support for deterministic multi-object execution.
- [x] Added subworkflow dispatch support via workflow step attributes (`subworkflow_id`, `subworkflow_version`).
- [x] Added state-partition ownership enforcement in policy engine (`state_partition` + `owner_roles`).
- [x] Added execution coordinator safety handling for policy/runtime errors to fail task deterministically.
- [x] Added tests for fan-out splitting, subworkflow dispatch, and ownership-policy blocking.

## Completed: Determinism Hardening (2026-03-13)

- [x] Added immutable workflow version guard (same `workflow_id:version` cannot be modified once published).
- [x] Allowed idempotent republish when metadata/markdown are unchanged.
- [x] Added fan-in summary APIs/CLI/chat for fan-out groups.
- [x] Added first-class state partition service with list/get inspection surfaces.

## Completed: Multi-Organization and Artifact Surfaces (2026-03-13)

- [x] Added organization-aware task context (`Task.organization_id`) across intake and execution.
- [x] Added compatibility migration for existing SQLite DBs to backfill `tasks.organization_id`.
- [x] Added `/api/organizations` and org-aware `/api/organization`, `/api/integrations/status`, `/api/tasks`.
- [x] Added GUI org selector/create flow; task intake and integration checks now use selected org context.
- [x] Upgraded chat slash command `/organization` to `list/view/select/create/update` (multi-org ready).
- [x] Added CLI org listing and org-scoped task intake/scaffold (`--organization-id`).
- [x] Added first-class artifact API endpoints:
  - `GET /api/artifacts/{artifact_type}`
  - `POST /api/artifacts/{artifact_type}`
- [x] Added org-scoped filtering support for artifacts and tasks.
- [x] Added integration/e2e tests for org scoping and artifact APIs.

## Completed: Backlog Closure Sprint (2026-03-13)

Pending items were converted into implementation tasks and completed sequentially:

1. [x] Per-agent model selection:
   - Added `RoleDefinition.preferred_model_id`
   - Added role-priority model routing in `ModelRouter`
   - Wired role-aware routing in `StepRunner`
   - Added UI support in Agent creation wizard
2. [x] GUI task streaming:
   - Added stream controls in Tasks Console
   - Wired EventSource against `/api/tasks/{task_id}/events/stream`
3. [x] Remote CLI auth/token mode:
   - Added `loom ctl remote ...` with explicit `--auth-mode token|header`
   - Added CSRF-aware token-mode remote mutations
4. [x] Workflow diff viewer UI:
   - Added UI controls and rendering for `/api/workflows/{workflow_id}/diff/{from}/{to}`
5. [x] Memory query/invalidate UI:
   - Added Tasks Console memory tools against `/api/memory/query` and `/api/memory/invalidate`
6. [x] Export/import configuration completion:
   - Added `export_bundle_spec(...)`
   - Added `/api/bundle/export`
   - Added `loom ctl bundle export`
   - Added chat `/bundle export`
7. [x] Dark mode:
   - Added theme variables and runtime theme toggle
8. [x] Keyboard shortcuts:
   - Added `Ctrl+1/2/3/4`, `Ctrl+Enter`, `Ctrl+Shift+R`, `?`
9. [x] Regression coverage and validation:
   - Added/updated integration/e2e tests for new features
   - Full suite passing: `57 passed`

## Completed: TUI Parity Closure Sprint (2026-03-13)

TUI gap checklist to ensure chat shell can fully manage deterministic agentic workflows:

1. [x] Add model routing slash commands in chat TUI (`/models ...`).
2. [x] Add workflow file operations in chat TUI (`/workflows versions|diff|validate-file|publish-file`).
3. [x] Add task lifecycle operations in chat TUI (`/tasks intake|run|trace|events`).
4. [x] Add memory operations in chat TUI (`/memory query|invalidate`).
5. [x] Add integration inspection commands in chat TUI (`/integrations status|health|bindings`).
6. [x] Add artifact management commands in chat TUI (`/artifacts list|upsert-*`).
7. [x] Add integration tests covering all new TUI command families.
8. [x] Run full test suite and close all regressions.
9. [x] Update README slash-command docs for new TUI capabilities.

## Completed: Strict Graphiti Isolation + Memory Topology E2E (2026-03-14)

1. [x] Added first-class memory topology models:
   - `MemoryGroupDefinition`
   - `MemoryGroupMembership`
   - `MemoryRoleEdge`
2. [x] Added memory topology registries:
   - `MemoryGroupRegistry`
   - `MemoryMembershipRegistry`
   - `MemoryEdgeRegistry`
3. [x] Added `MemoryTopologyService` with:
   - explicit shared-group resolution
   - automatic role-private group/membership creation
   - strict org-scoped scope resolution
4. [x] Upgraded Graphiti adapter + memory service:
   - per-call workspace routing
   - org-prefixed memory keys
   - cross-org isolation by scope/workspace
5. [x] Wired automatic runtime memory lifecycle:
   - per-step episodic writes from `StepRunner`
   - scoped memory reads injected into step context
   - workflow-completion semantic consolidation in `ExecutionCoordinator`
6. [x] Fixed subworkflow org context propagation:
   - child task now inherits `organization_id`
7. [x] Extended bundle import/export for memory topology:
   - `memory_groups`
   - `memory_memberships`
   - `memory_edges`
8. [x] Upgraded docs orchestration bundle with default shared groups:
   - `kr_shared`
   - `development_shared`
9. [x] Added UI/API memory topology surfaces:
   - list/upsert groups, memberships, edges
   - resolve effective scopes
10. [x] Extended chat TUI memory command family:
   - group + membership management
   - scope resolution
   - org-scoped query/invalidate
11. [x] Added tests for memory topology/isolation/runtime behavior:
   - unit + integration + e2e coverage
12. [x] Full regression validation complete:
   - `62 passed`

## Completed: Organization Runtime + Stateless Ops + UI Upgrade (2026-03-14)

1. [x] Added org runtime manager:
   - new `OrganizationRuntimeService`
   - idempotent `run/status/stop`
   - service snapshots for LiteLLM/Graphiti/OpenCode/OpenAI
2. [x] Added runtime config drift detection:
   - hashes org runtime-relevant config
   - marks `restart_required` only when runtime config changes
   - keeps agent/workflow edits stateless (no restart needed)
3. [x] Added optional side-service boot hooks:
   - `litellm_start_cmd` per organization
   - `LOOM_LITELLM_START_CMD` / `LOOM_GRAPHITI_START_CMD` settings fallback
4. [x] Added new API surfaces:
   - `GET /api/organization/runtime`
   - `POST /api/organization/runtime/run`
   - `POST /api/organization/runtime/stop`
5. [x] Added TUI slash command runtime controls:
   - `/organization run`
   - `/organization runtime|status`
   - `/organization stop`
6. [x] Added control-plane CLI runtime commands:
   - `loom ctl organization run`
   - `loom ctl organization runtime-status`
   - `loom ctl organization stop`
7. [x] Improved UI organization experience:
   - runtime control card (run/refresh/stop)
   - runtime service status chips
   - LiteLLM start command field in org config
8. [x] Added regression coverage:
   - unit tests for runtime behavior and restart semantics
   - integration tests for chat CLI + control-plane runtime commands
   - e2e tests for UI runtime endpoints
9. [x] Full regression validation complete:
   - `67 passed`
