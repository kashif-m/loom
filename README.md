# Loom

Loom is a workflow-first multi-agent orchestration kernel with a local-first GUI control plane.

## What you can do now

- Open GUI at `/ui` and CRUD:
  - workflows + versions + lifecycle actions
  - agents/roles
  - capabilities
  - policies
  - prompt profiles
  - model providers (LiteLLM), model catalog, and service-to-model bindings
  - schedules
  - tasks/runs/traces/events
  - memory scope queries/invalidation
  - incidents and topology
- Bootstrap Docs Pack and publish custom workflows.
- Run local stack with SQLite by default.

## Local start (recommended)

```bash
# run from repo root
# ensure `just` is installed (nix shell below includes it)
pip install -e '.[dev,integrations]'
just bootstrap
just run
```

Open:

- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/health`

## Nix start

```bash
nix develop
# .venv is auto-created/activated by flake shellHook
pip install -e '.[dev,integrations]'
just bootstrap
just run
```

## Docker start

```bash
docker build -t loom .
docker run --rm -p 8000:8000 \
  -e LOOM_DATABASE_URL='sqlite:////app/data/loom.db' \
  -e LOOM_ENV='dev' \
  -e LOOM_UI_AUTH_MODE='none' \
  loom
```

## Docker compose local stack

Minimal profile:

```bash
docker compose -f deploy/docker-compose.local.yml --profile minimal up --build
```

Full local integration profile (with mock side services):

```bash
docker compose -f deploy/docker-compose.local.yml --profile full up --build
```

## GUI auth and CSRF

- Local convenience mode: `LOOM_UI_AUTH_MODE=none`.
- Production-style mode: `LOOM_UI_AUTH_MODE=token` with tokens:
  - `LOOM_VIEWER_TOKEN`
  - `LOOM_OPERATOR_TOKEN`
  - `LOOM_ADMIN_TOKEN`
- In token mode, mutating `/api/*` calls require CSRF token from `/api/auth/csrf`.

## LiteLLM model routing (per service)

Loom now supports LiteLLM-first model routing through GUI/API CRUD:

- `model-providers` (`provider_type=litellm`)
- `models` (provider-scoped model entries)
- `service-models` (bind service like `step_execution` to a model)

Optional env bootstrap:

- `LOOM_LITELLM_ENABLED=true`
- `LOOM_LITELLM_BASE_URL=http://localhost:4000`
- `LOOM_LITELLM_API_KEY=...`
- `LOOM_LITELLM_DEFAULT_MODEL=openai/gpt-4.1-mini`

When enabled, Loom auto-seeds a default LiteLLM provider/model/binding for `step_execution`.

## External integrations supported

- Graphiti (HTTP adapter + fallback)
- OpenClaw (signed ingress path)
- OpenAI execution adapter
- LangSmith trace adapter
- OpenCode context adapter

Enable each via env vars in `loom/app/config.py`.

## Useful scripts

- `./scripts/init_env_local.sh`
- `./scripts/init_env_local.sh --force` (regenerate `.env.local`)
- `./scripts/bootstrap_local_stack.sh`
- `./scripts/verify_connectors.sh`
- `./scripts/bootstrap_tools.sh`
- `./scripts/load_docs_pack.py`
- `./scripts/publish_workflow.py`

## CLI control plane

Loom now includes a built-in control plane CLI through `loom ctl`:

```bash
# Organization
loom ctl organization list
loom ctl organization show --org-id default
loom ctl organization set --org-id docs_team --name "Acme Docs" \
  --litellm-base-url "http://localhost:4000" \
  --litellm-api-key "..." \
  --litellm-default-model "openai/gpt-4.1-mini"
# Optional only if you self-host LiteLLM locally:
# loom ctl organization set --org-id docs_team --litellm-start-cmd "docker compose up -d litellm"
loom ctl organization run --org-id docs_team
loom ctl organization runtime-status --org-id docs_team
loom ctl organization stop --org-id docs_team

# Agents
loom ctl agent create \
  --role-id docs_agent \
  --title "Docs Agent" \
  --domain-pack custom \
  --capability-ids repo_read \
  --ensure-capability "repo_read:Read repository context:opencode"
loom ctl agent list

# Workflows
loom ctl workflow validate \
  --workflow-id custom_flow \
  --version 1 \
  --markdown-file examples/custom_agentic_workflow.md
loom ctl workflow publish \
  --workflow-id custom_flow \
  --version 1 \
  --title "Custom Flow" \
  --domain-pack custom \
  --intent-group custom_local \
  --markdown-file examples/custom_agentic_workflow.md \
  --activate

# Tasks
loom ctl task intake --request "run custom local workflow" --domain-pack custom --run --trace
loom ctl task list
# Deterministic intake (pin exact workflow/version)
loom ctl task intake \
  --organization-id docs_team \
  --request "update docs for payouts API" \
  --domain-pack docs \
  --workflow-id docs_maintenance \
  --workflow-version 1 \
  --run --trace
# Fan-out intake for multi-object requests (one task per object)
loom ctl task intake \
  --organization-id docs_team \
  --request "enhance docs https://example.com/a and https://example.com/b" \
  --domain-pack docs \
  --workflow-id docs_maintenance \
  --workflow-version 1 \
  --fanout \
  --run
# Fan-in summary for a fan-out group
loom ctl task fanin --fanout-group <fanout_group_id>
# State partition inspection
loom ctl state list --partition-id task_workflow
# Artifact inspection (API): /api/artifacts/{packages|grounding_references|pr_contexts|audit_results|repo_target_mappings}
```

One-command starter scaffold:

```bash
loom ctl scaffold starter \
  --org-name "My Organization" \
  --domain-pack custom \
  --agent-id starter_agent \
  --workflow-id starter_workflow \
  --request "run custom local workflow"
```

Declarative deterministic setup with YAML spec:

```bash
loom ctl bundle apply --spec-file examples/docs_org_bundle.yaml
loom ctl bundle export --organization-id default --output-file exported_bundle.yaml
```

Docs orchestration use-case bundle:

```bash
loom ctl bundle apply --spec-file examples/usecases/docs_orchestration/bundle.yaml
```

You can then run pinned workflow execution:

```bash
loom ctl task intake \
  --request "enhance docs for retries section" \
  --domain-pack docs \
  --workflow-id docs_maintenance \
  --workflow-version 1 \
  --run --trace
```

Remote HTTP control plane mode (token/header auth):

```bash
loom ctl remote --base-url http://127.0.0.1:8000 --auth-mode token --token <operator_token> auth-check
loom ctl remote --base-url http://127.0.0.1:8000 --auth-mode token --token <operator_token> organization show --org-id default
loom ctl remote --base-url http://127.0.0.1:8000 --auth-mode token --token <operator_token> task intake \
  --organization-id default --domain-pack docs --request "enhance docs"
```

## Interactive Chat CLI

You can use a slash-command chat shell:

```bash
loom chat
```

Supported slash commands:

- `/organization` list/view/create/update/select/run/runtime/status/stop
- `/agents` list/select/create
- `/workflows` list/select/create/versions/diff/validate-file/publish-file
- `/models` list/providers/bindings/add-provider/add-model/bind/resolve
- `/bundle` apply/export declarative bundle specs
- `/integrations` status/health/bindings
- `/tasks` list/intake/run/trace/events/fanin
- `/memory` groups/group-create/memberships/member-add/resolve/query/invalidate
- `/artifacts` list/upsert-file/upsert-yaml
- `/state` inspect state partitions
- `/domain` set active domain pack
- `/status` show current selections
- `/help`
- `/exit`

Any normal message (non-slash) is treated as a task request and executed through Loom.
If multiple task objects are detected (for example multiple doc URLs), chat mode fans out into one task per object.

## UI ergonomics

- Agent wizard supports optional per-agent preferred model selection.
- Workflow tab includes version diff viewer.
- Tasks tab includes memory query/invalidate controls (org-scoped).
- Tasks tab includes task event streaming from `/api/tasks/{task_id}/events/stream`.
- Organization tab includes `Run Organization`, runtime status chips, and `Stop Organization`.
- Organization runtime is config-driven: agent/workflow changes are stateless and hot; restart is only required for runtime config changes.
- Theme toggle supports light/dark mode.
- Keyboard shortcuts:
  - `Ctrl+1/2/3/4`: switch main views
  - `Ctrl+Enter`: intake task (Tasks view)
  - `Ctrl+Shift+R`: refresh auth + data
  - `?`: show shortcuts

## Memory topology and isolation

- Graphiti memory routing is org-scoped (`organization_id` workspace separation).
- Runtime writes episodic memory automatically per step and consolidates semantic memory on workflow completion.
- Shared memory is explicit via memory groups and memberships; role-private scopes are created automatically.
- UI APIs:
  - `GET/POST /api/memory/groups`
  - `GET/POST /api/memory/memberships`
  - `GET/POST /api/memory/edges`
  - `GET /api/memory/scopes/resolve`

## Organization runtime APIs

- `GET /api/organization/runtime?org_id=<org>`
- `POST /api/organization/runtime/run` with payload `{ "org_id": "<org>" }`
- `POST /api/organization/runtime/stop` with payload `{ "org_id": "<org>" }`

## Docs

- GUI IA/API contracts: `docs/architecture/gui_ia_api_contracts.md`
- Tool bootstrap matrix: `docs/ops/tool_bootstrap_matrix.md`
- Local troubleshooting: `docs/runbooks/local-troubleshooting.md`
- Local golden path: `docs/ops/local-golden-path.md`
- Task backlog: [TASKS.md](./TASKS.md)
