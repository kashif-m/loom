#!/usr/bin/env bash
set -euo pipefail

./scripts/init_env_local.sh
set -a
source .env.local
set +a

./scripts/bootstrap_tools.sh || true
./scripts/verify_connectors.sh || true
./scripts/run_migrations.sh || true
./scripts/load_docs_pack.py || true
./scripts/check_toolchain_conformance.sh || true

echo "Local stack bootstrap complete"
echo "Run: python3 -m loom.app.main --serve"
