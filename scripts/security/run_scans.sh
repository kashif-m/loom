#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install pip-audit bandit >/dev/null
pip-audit || true
bandit -r loom -q
