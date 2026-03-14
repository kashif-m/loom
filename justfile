set shell := ["bash", "-cu"]

default:
  @just --list

bootstrap:
  ./scripts/bootstrap_local_stack.sh

run:
  python3 -m loom.app.main --serve

gui:
  python3 -m loom.app.main --serve

tui:
  python3 -m loom.app.main chat

test:
  python3 -m pytest -q

lint:
  python3 -m ruff check .

typecheck:
  python3 -m mypy loom

check: lint typecheck test
