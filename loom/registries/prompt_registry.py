from __future__ import annotations

from loom.models import PromptProfile


class PromptRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, profile: PromptProfile) -> None:
        key = f"{profile.profile_id}:{profile.version}"
        self.repositories.prompts.upsert(key, profile.model_dump(), status=profile.status.value, version=profile.version)

    def get(self, profile_id: str, version: int) -> PromptProfile | None:
        row = self.repositories.prompts.get(f"{profile_id}:{version}")
        return PromptProfile(**row["data"]) if row else None

    def list(self, status: str | None = None) -> list[PromptProfile]:
        return [PromptProfile(**row["data"]) for row in self.repositories.prompts.list(status=status)]
