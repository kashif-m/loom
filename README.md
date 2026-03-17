# Loom MVP

A workflow-first multi-agent orchestration system with a 3-tier hierarchy: Kite Runner (org) → Generalist (team) → Specialist (execution).

## What You Can Do Now

- **Submit tasks** via web UI — system automatically matches workflows
- **Track task progress** through states with live timeline
- **Respond to escalations** when agents get stuck
- **View workflow definitions** and approve/deprecate them
- **Monitor live activity** via SSE event stream
- **Manage agents** via JSON config files

## Architecture

```
Human
  └── Kite Runner (KR)          — org-level orchestrator
        └── Generalist Agent    — team lead, delegates work
              └── Specialist    — leaf executor with tools
```

## Quick Start

### Prerequisites

- Nix with flakes enabled
- LiteLLM proxy running on :4000 (optional, for LLM calls)

### Start Services

```bash
# Enter dev shell
nix develop

# Start PostgreSQL
nix run .#ext-services
```

### Start Backend

```bash
# In another terminal, from project root
nix develop
migrate  # Initialize database (first time only)
api      # Starts FastAPI on :8000
```

### Start Frontend

```bash
# In another terminal
nix develop
ui-dev   # Starts Next.js on :3000
```

### Open UI

Navigate to: http://localhost:3000

## What's Implemented (V1)

### Backend
- ✅ Task store with SQLite (Postgres ready)
- ✅ Event bus (in-memory, Redis-ready)
- ✅ Workflow engine with LangGraph state machine
- ✅ Markdown workflow parser with hot reload
- ✅ Two-stage workflow matching (tags → LLM fallback)
- ✅ 3-tier agent hierarchy
- ✅ Memory layer with Graphiti client
- ✅ LLM abstraction via LiteLLM
- ✅ Evaluation signals

### Frontend (6 Pages)
- ✅ Dashboard — summary, recent tasks, escalations
- ✅ Tasks List — filterable with pagination
- ✅ Task Detail — timeline, escalation panel, artifacts
- ✅ New Task — submission form
- ✅ Activity Feed — live SSE event stream
- ✅ Workflows — list, approve, deprecate

### Configuration
- Agent configs: `agents_config/*.json`
- Workflow files: `workflows/**/*.md`

## Project Structure

```
├── src/                    # Backend (FastAPI + agents)
│   ├── api/               # REST API routes
│   ├── core/              # Task store, event bus, workflows, LLM
│   ├── agents/            # KR, Generalist, Specialist
│   ├── memory/            # Graphiti client, extraction worker
│   └── evaluation/        # Task evaluation signals
├── ui/                    # Next.js 14 frontend
│   ├── app/              # Pages (dashboard, tasks, workflows, activity)
│   └── components/       # Reusable UI components
├── agents_config/         # Agent identity configs (JSON)
├── workflows/             # Workflow definitions (Markdown + YAML)
├── infra/                 # Database migrations
├── llm/                   # Architecture docs, tasks, UI spec
└── context/               # Implementation plans, diagrams
```

## Development Commands

```bash
# Inside nix develop shell:
api          # Start FastAPI dev server (:8000)
ui-dev       # Start Next.js dev server (:3000)
migrate      # Initialize database
lint         # Check code style (ruff)
fmt          # Auto-format code
services     # Start PostgreSQL via services-flake
```

## What's NOT Implemented (V2)

- Agent management UI (currently JSON-only)
- Redis Streams event bus (using in-memory)
- Neo4j for Graphiti (using SQLite)
- Parallel workflow branches
- Priority queues (P0-P3)
- Real notifications (email/Slack)
- Full RBAC
- Visual workflow editor

## Documentation

- Architecture: `llm/ARCHITECTURE.md`
- UI Specification: `llm/UI_SPEC.md`
- Task List: `llm/TASKS.md`
- Coding Guidelines: `llm/CODING_GUIDELINES.md`

## License

MIT
