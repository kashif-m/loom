from __future__ import annotations


class AuditLogService:
    def __init__(self, repositories):
        self.repositories = repositories

    def list_task_events(self, task_id: str) -> list[dict]:
        return self.repositories.events.list_for_task(task_id)

    def list_events(
        self,
        *,
        task_id: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        return self.repositories.events.list(
            task_id=task_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
