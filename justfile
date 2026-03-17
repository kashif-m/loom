set shell := ["bash", "-cu"]

default:
  @just --list

# Install all dependencies
install:
  @echo "Installing Python dependencies..."
  uv sync
  @echo "Installing Node dependencies..."
  cd ui && pnpm install

# Install a specific Python package (e.g., just pip-install instructor)
pip-install package:
  uv add {{package}}

# Install a specific dev Python package (e.g., just pip-install-dev pytest)
pip-install-dev package:
  uv add --dev {{package}}

# Update all dependencies
update:
  uv sync --upgrade

# Start all services (PostgreSQL, API, UI)
start:
  @echo "Starting all services..."
  @echo "Run these in separate terminals:"
  @echo "  Terminal 1: nix run .#ext-services"
  @echo "  Terminal 2: api"
  @echo "  Terminal 3: ui-dev"

# Run database migrations
migrate:
  uv run python -c 'from src.core.task_store.operations import TaskStore; import asyncio; asyncio.run(TaskStore().init_db())'

# Start the API server
api:
  uv run uvicorn src.api.gateway:app --reload --port 8000

# Start the UI dev server
ui:
  cd ui && pnpm dev

# Run all tests
test:
  uv run pytest tests/ -v

# Run unit tests only
test-unit:
  uv run pytest tests/unit/ -v

# Run integration tests only
test-integration:
  uv run pytest tests/integration/ -v

# Run linting
lint:
  ruff check src/ && ruff format --check src/

# Auto-format code
fmt:
  ruff format src/ && ruff check --fix src/

# Run type checking
typecheck:
  pyright src/

# Run all checks (lint, typecheck, test)
check: lint typecheck test

# Clean build artifacts
clean:
  find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  find . -type f -name "*.pyc" -delete 2>/dev/null || true
  rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true
  rm -rf ui/.next ui/node_modules 2>/dev/null || true

# Tail API logs
tail-logs:
  tail -f /tmp/api.log

# Quick test of the API
test-api:
  curl -s http://localhost:8000/api/health | jq .

# Submit a test task
test-task:
  curl -s -X POST http://localhost:8000/api/tasks \
    -H "Content-Type: application/json" \
    -d '{"description":"Fix the login bug where users cannot authenticate","priority":"normal"}' | jq .
