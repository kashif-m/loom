from __future__ import annotations


class WorkingMemory:
    def __init__(self):
        self.values: dict[str, dict] = {}

    def set(self, task_id: str, payload: dict) -> None:
        self.values[task_id] = payload

    def get(self, task_id: str) -> dict:
        return self.values.get(task_id, {})
