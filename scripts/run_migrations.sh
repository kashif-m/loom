#!/usr/bin/env bash
set -euo pipefail

export LOOM_DATABASE_URL="${LOOM_DATABASE_URL:-sqlite:///./loom.db}"

if command -v alembic >/dev/null 2>&1; then
  alembic upgrade head || true
else
  echo "alembic not found; skipping"
fi
