"""Shared application state for Loom API."""
from src.agents.kite_runner.agent import KiteRunner
from src.core.task_store.operations import TaskStore


class AppState:
    """Application state."""
    task_store: TaskStore | None = None
    kite_runner: KiteRunner | None = None


# Global state instance
app_state = AppState()
