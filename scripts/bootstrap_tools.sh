#!/usr/bin/env bash
set -euo pipefail

TOOLS_DIR=".tools"
mkdir -p "$TOOLS_DIR"

export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true

OPENCLAW_URL="${LOOM_OPENCLAW_REPO_URL:-https://github.com/openclaw/openclaw.git}"
OPENCODE_URL="${LOOM_OPENCODE_REPO_URL:-https://github.com/sst/opencode.git}"
GRAPHITI_URL="${LOOM_GRAPHITI_REPO_URL:-https://github.com/getzep/graphiti.git}"

clone_if_missing() {
  local name="$1"
  local url="$2"
  local target="$3"
  if [ -d "$target/.git" ]; then
    echo "exists: $target"
    return
  fi
  if [ -z "$url" ]; then
    echo "skip $name: repo URL not set"
    return
  fi
  if ! git ls-remote --heads "$url" >/dev/null 2>&1; then
    echo "warning: cannot access $name repo via HTTPS: $url"
    return
  fi
  if ! git -c credential.helper= clone --depth 1 "$url" "$target"; then
    echo "warning: failed to clone $name from $url"
  fi
}

clone_if_missing "openclaw" "$OPENCLAW_URL" "$TOOLS_DIR/openclaw"
clone_if_missing "opencode" "$OPENCODE_URL" "$TOOLS_DIR/opencode"
clone_if_missing "graphiti" "$GRAPHITI_URL" "$TOOLS_DIR/graphiti"

echo "tool bootstrap complete"
