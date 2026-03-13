from __future__ import annotations

from loom.models import ScheduleDefinition


class ScheduleRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def upsert(self, schedule: ScheduleDefinition) -> None:
        self.repositories.schedules.upsert(
            schedule.schedule_id,
            schedule.model_dump(),
            status="active" if schedule.enabled else "retired",
        )

    def get(self, schedule_id: str) -> ScheduleDefinition | None:
        row = self.repositories.schedules.get(schedule_id)
        return ScheduleDefinition(**row["data"]) if row else None

    def delete(self, schedule_id: str) -> None:
        self.repositories.schedules.delete(schedule_id)

    def list(self, enabled_only: bool = False) -> list[ScheduleDefinition]:
        rows = self.repositories.schedules.list(status="active" if enabled_only else None)
        return [ScheduleDefinition(**row["data"]) for row in rows]
