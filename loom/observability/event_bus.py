from __future__ import annotations

from loom.models import TaskEvent


class EventBus:
    def __init__(self, repositories):
        self.repositories = repositories

    def emit(self, event: TaskEvent) -> TaskEvent:
        return self.repositories.events.append(event)
