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
pip install -e '.[dev,integrations]'
make bootstrap
make run
```

Open:

- `http://127.0.0.1:8000/ui`
- `http://127.0.0.1:8000/health`

## Nix start

```bash
nix develop
pip install -e '.[dev,integrations]'
make bootstrap
make run
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
- `./scripts/bootstrap_local_stack.sh`
- `./scripts/verify_connectors.sh`
- `./scripts/bootstrap_tools.sh`
- `./scripts/load_docs_pack.py`
- `./scripts/publish_workflow.py`

## Docs

- GUI IA/API contracts: `docs/architecture/gui_ia_api_contracts.md`
- Tool bootstrap matrix: `docs/ops/tool_bootstrap_matrix.md`
- Local troubleshooting: `docs/runbooks/local-troubleshooting.md`
- Local golden path: `docs/ops/local-golden-path.md`
- Task backlog: [TASKS.md](./TASKS.md)
