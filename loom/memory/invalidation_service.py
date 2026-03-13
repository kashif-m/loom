from __future__ import annotations


class InvalidationService:
    def __init__(self, memory_service):
        self.memory_service = memory_service

    def soft_invalidate(self, scope: dict) -> int:
        return self.memory_service.invalidate(scope, hard=False)

    def hard_invalidate(self, scope: dict) -> int:
        return self.memory_service.invalidate(scope, hard=True)
