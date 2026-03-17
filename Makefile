.PHONY: dev migrate test test-unit test-integration lint fmt typecheck api ui-dev

dev:
	@echo "SQLite database ready at ./loom.db"

migrate:
	uv run python -m src.core.task_store.migrations

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

lint:
	ruff check src/ && ruff format --check src/

fmt:
	ruff format src/ && ruff check --fix src/

typecheck:
	pyright src/

api:
	uv run uvicorn src.api.gateway:app --reload --port 8000

ui-dev:
	cd ui && pnpm dev
