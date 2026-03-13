from __future__ import annotations


class EpisodicMemory:
    def __init__(self):
        self.entries: list[dict] = []

    def add(self, payload: dict) -> None:
        self.entries.append(payload)

    def list(self) -> list[dict]:
        return list(self.entries)
