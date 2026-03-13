from __future__ import annotations

from typing import Any

from loom.models import MemoryType, TaskEvent
from loom.memory.graphiti_adapter import GraphitiAdapter


class InMemoryMemoryService:
    def __init__(
        self,
        repositories,
        event_bus,
        *,
        graphiti_enabled: bool = False,
        graphiti_base_url: str = "",
        graphiti_api_key: str = "",
        graphiti_workspace: str = "default",
    ):
        self.repositories = repositories
        self.event_bus = event_bus
        self.graphiti = GraphitiAdapter(
            enabled=graphiti_enabled,
            base_url=graphiti_base_url,
            api_key=graphiti_api_key,
            workspace=graphiti_workspace,
        )

    def _scope_key(self, scope: dict[str, Any], memory_type: MemoryType | str) -> str:
        mem_type = MemoryType(memory_type) if isinstance(memory_type, str) else memory_type
        return ":".join(
            [
                scope.get("domain_pack", "global"),
                scope.get("workflow_id", "none"),
                str(scope.get("workflow_version", "0")),
                scope.get("role", "any"),
                mem_type.value,
            ]
        )

    def write(self, scope: dict[str, Any], memory_type: MemoryType | str, payload: dict[str, Any]) -> None:
        mem_type = MemoryType(memory_type) if isinstance(memory_type, str) else memory_type
        key = self._scope_key(scope, memory_type) + ":" + payload.get("id", "entry")
        self.graphiti.upsert(key, payload)
        self.repositories.memory.upsert(key, {"scope": scope, "type": mem_type.value, "payload": payload})
        self.event_bus.emit(TaskEvent(task_id=payload.get("task_id", "system"), event_type="memory_write", payload={"key": key}))

    def retrieve(
        self, scope: dict[str, Any], memory_type: MemoryType | str, active_only: bool = True
    ) -> list[dict[str, Any]]:
        prefix = self._scope_key(scope, memory_type)
        rows = self.graphiti.list_by_scope(prefix)
        if active_only:
            rows = [r for r in rows if not r.get("deprecated", False)]
        return rows

    def consolidate(self, scope: dict[str, Any]) -> dict[str, Any]:
        episodic = self.retrieve(scope, MemoryType.episodic, active_only=True)
        summary = {
            "id": "semantic-summary",
            "task_id": "system",
            "insights": [e.get("summary", "") for e in episodic if e.get("summary")],
            "count": len(episodic),
            "provenance": [e.get("id") for e in episodic],
        }
        self.write(scope, MemoryType.semantic, summary)
        return summary

    def invalidate(self, scope: dict[str, Any], hard: bool = False) -> int:
        prefix = self._scope_key(scope, MemoryType.episodic)
        rows = self.graphiti.list_by_scope(prefix)
        changed = 0
        for row in rows:
            row["deprecated"] = True
            changed += 1
        if hard:
            for key in [k for k in self.graphiti._store.keys() if k.startswith(prefix)]:
                self.graphiti.delete(key)
        return changed
