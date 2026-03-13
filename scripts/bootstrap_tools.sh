#!/usr/bin/env bash
set -euo pipefail

TOOLS_DIR=".tools"
mkdir -p "$TOOLS_DIR"

OPENCLAW_URL="${LOOM_OPENCLAW_REPO_URL:-https://github.com/example/openclaw.git}"
OPENCODE_URL="${LOOM_OPENCODE_REPO_URL:-https://github.com/example/opencode.git}"
GRAPHITI_URL="${LOOM_GRAPHITI_REPO_URL:-https://github.com/example/graphiti.git}"

clone_if_missing() {
  local url="$1"
  local target="$2"
  if [ -d "$target/.git" ]; then
    echo "exists: $target"
    return
  fi
  git clone --depth 1 "$url" "$target" || echo "warning: failed to clone $url"
}

clone_if_missing "$OPENCLAW_URL" "$TOOLS_DIR/openclaw"
clone_if_missing "$OPENCODE_URL" "$TOOLS_DIR/opencode"
clone_if_missing "$GRAPHITI_URL" "$TOOLS_DIR/graphiti"

echo "tool bootstrap complete"
