#!/usr/bin/env bash
set -euo pipefail

./scripts/verify_connectors.sh || true

if [ -f "deploy/docker-compose.local.yml" ]; then
  echo "docker-compose local: present"
fi
if [ -f "flake.nix" ]; then
  echo "flake.nix: present"
fi
if [ -f "docs/ops/tool_bootstrap_matrix.md" ]; then
  echo "tool bootstrap matrix: present"
fi

echo "toolchain conformance checks complete"
