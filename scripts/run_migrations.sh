#!/usr/bin/env bash
set -euo pipefail

export LOOM_DATABASE_URL="${LOOM_DATABASE_URL:-sqlite:///./loom.db}"

if command -v alembic >/dev/null 2>&1; then
  if ! python3 -c "import alembic, sqlalchemy" >/dev/null 2>&1; then
    echo "alembic/python deps not ready; skipping migrations for now"
    exit 0
  fi

  needs_stamp="$(
    python3 - <<'PY'
import os
import sqlite3

url = os.environ.get("LOOM_DATABASE_URL", "")
if not url.startswith("sqlite:///"):
    print("no")
    raise SystemExit(0)

path = url[len("sqlite:///") :]
if not path or path == ":memory:":
    print("no")
    raise SystemExit(0)

if not os.path.exists(path):
    print("no")
    raise SystemExit(0)

conn = sqlite3.connect(path)
try:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
finally:
    conn.close()

tables = {r[0] for r in rows}
if "tasks" in tables and "alembic_version" not in tables:
    print("yes")
else:
    print("no")
PY
  )"

  if [ "$needs_stamp" = "yes" ]; then
    echo "Detected existing SQLite schema without alembic version; stamping head"
    alembic stamp head
  fi

  err_log="$(mktemp)"
  if ! alembic upgrade head 2>"$err_log"; then
    if grep -Eiq "already exists|duplicatetable" "$err_log"; then
      echo "Detected existing tables during migration; stamping and retrying"
      alembic stamp head
      alembic upgrade head
    else
      echo "alembic upgrade failed:"
      cat "$err_log"
      rm -f "$err_log"
      exit 1
    fi
  fi
  rm -f "$err_log"
else
  echo "alembic not found; skipping"
fi
