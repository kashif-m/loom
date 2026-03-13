#!/usr/bin/env bash
set -euo pipefail

if [ -f .env.local ] && [ "${1:-}" != "--force" ]; then
  echo ".env.local already exists (use --force to overwrite)"
  exit 0
fi

cat > .env.local <<'ENV'
LOOM_ENV=dev
LOOM_DATABASE_URL=sqlite:///./loom.db
LOOM_API_AUTH_ENABLED=false
LOOM_UI_AUTH_MODE=none
LOOM_INTEGRATION_PROFILE=local
LOOM_OPENCLAW_REPO_URL=https://github.com/openclaw/openclaw.git
LOOM_OPENCODE_REPO_URL=https://github.com/sst/opencode.git
LOOM_GRAPHITI_REPO_URL=https://github.com/getzep/graphiti.git
LOOM_GRAPHITI_ENABLED=false
LOOM_LITELLM_ENABLED=false
LOOM_LITELLM_BASE_URL=
LOOM_LITELLM_API_KEY=
LOOM_LITELLM_DEFAULT_MODEL=openai/gpt-4.1-mini
LOOM_OPENAI_ENABLED=false
LOOM_LANGSMITH_ENABLED=false
LOOM_OPENCLAW_ENABLED=false
LOOM_OPENCODE_ENABLED=false
LOOM_ASYNC_WORKERS_ENABLED=false
ENV

echo "wrote .env.local"
