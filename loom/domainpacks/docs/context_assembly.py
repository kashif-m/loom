from __future__ import annotations

from loom.adapters.opencode_adapter import OpenCodeAdapter
from loom.models import MemoryType


class DocsContextAssembler:
    def __init__(self, repo_root: str, memory_service, *, opencode_enabled: bool = False, opencode_cmd: str = "opencode"):
        self.opencode = OpenCodeAdapter(repo_root, cmd=opencode_cmd, enabled=opencode_enabled)
        self.memory_service = memory_service
        self._cache: dict[str, dict] = {}

    def assemble(self, task_id: str, pr_metadata: dict, scope: dict) -> dict:
        if task_id in self._cache:
            return self._cache[task_id]

        context = {
            "repository": self.opencode.collect_context(),
            "pr": pr_metadata,
            "memory": self.memory_service.retrieve(
                scope, memory_type=scope.get("memory_type", MemoryType.episodic)
            ),
        }
        self._cache[task_id] = context
        return context
