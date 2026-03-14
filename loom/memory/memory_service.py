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

    def _organization_id(self, scope: dict[str, Any]) -> str:
        return str(scope.get("organization_id", "default"))

    def _scope_key(self, scope: dict[str, Any], memory_type: MemoryType | str) -> str:
        mem_type = MemoryType(memory_type) if isinstance(memory_type, str) else memory_type
        scope_id = scope.get("scope_id") or scope.get("role", "any")
        return ":".join(
            [
                self._organization_id(scope),
                scope.get("domain_pack", "global"),
                scope.get("workflow_id", "none"),
                str(scope.get("workflow_version", "0")),
                str(scope_id),
                mem_type.value,
            ]
        )

    def write(self, scope: dict[str, Any], memory_type: MemoryType | str, payload: dict[str, Any]) -> None:
        mem_type = MemoryType(memory_type) if isinstance(memory_type, str) else memory_type
        organization_id = self._organization_id(scope)
        key = self._scope_key(scope, memory_type) + ":" + payload.get("id", "entry")
        self.graphiti.upsert(key, payload, workspace=organization_id)
        self.repositories.memory.upsert(key, {"scope": scope, "type": mem_type.value, "payload": payload})
        self.event_bus.emit(
            TaskEvent(
                task_id=payload.get("task_id", "system"),
                event_type="memory_write",
                payload={"key": key, "organization_id": organization_id},
            )
        )

    def retrieve(
        self, scope: dict[str, Any], memory_type: MemoryType | str, active_only: bool = True
    ) -> list[dict[str, Any]]:
        organization_id = self._organization_id(scope)
        prefix = self._scope_key(scope, memory_type)
        rows = self.graphiti.list_by_scope(prefix, workspace=organization_id)
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
        organization_id = self._organization_id(scope)
        prefix = self._scope_key(scope, MemoryType.episodic)
        rows = self.graphiti.list_by_scope(prefix, workspace=organization_id)
        changed = 0
        for row in rows:
            row["deprecated"] = True
            changed += 1
        if hard:
            for key in self.graphiti.list_keys_by_scope(prefix, workspace=organization_id):
                self.graphiti.delete(key, workspace=organization_id)
        return changed
