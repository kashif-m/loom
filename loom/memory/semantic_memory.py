from __future__ import annotations


class SemanticMemory:
    def __init__(self):
        self.entries: dict[str, dict] = {}

    def upsert(self, key: str, payload: dict) -> None:
        self.entries[key] = payload

    def get(self, key: str) -> dict | None:
        return self.entries.get(key)
