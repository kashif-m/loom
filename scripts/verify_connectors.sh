#!/usr/bin/env bash
set -euo pipefail

required=(git)
optional=(gh node java plantuml opencode)

for cmd in "${required[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "missing required connector: $cmd"
    exit 1
  fi
done

for cmd in "${optional[@]}"; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "ok optional connector: $cmd"
  else
    echo "missing optional connector: $cmd"
  fi
done
