from __future__ import annotations


class ConsolidationService:
    def __init__(self, memory_service):
        self.memory_service = memory_service

    def run(self, scope: dict) -> dict:
        return self.memory_service.consolidate(scope)
