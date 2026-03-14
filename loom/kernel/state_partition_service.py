from __future__ import annotations

from typing import Any


class StatePartitionService:
    def __init__(self, repositories):
        self.repositories = repositories

    def write(
        self,
        *,
        partition_id: str,
        key: str,
        actor_role: str,
        payload: dict[str, Any],
    ) -> None:
        repo_key = f"{partition_id}:{key}"
        data = {
            "partition_id": partition_id,
            "key": key,
            "actor_role": actor_role,
            "payload": payload,
        }
        self.repositories.state_partitions.upsert(repo_key, data, status="active")

    def list(self, partition_id: str | None = None, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.repositories.state_partitions.list()
        items = [row["data"] for row in rows]
        if partition_id:
            items = [item for item in items if item.get("partition_id") == partition_id]
        return items[:limit]

    def get(self, partition_id: str, key: str) -> dict[str, Any] | None:
        row = self.repositories.state_partitions.get(f"{partition_id}:{key}")
        return row["data"] if row else None
