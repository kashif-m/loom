from __future__ import annotations

from loom.models import ScheduleDefinition


def default_maintenance_schedules() -> list[ScheduleDefinition]:
    return [
        ScheduleDefinition(
            schedule_id="nightly_memory_consolidation",
            cron="0 2 * * *",
            action_type="maintenance",
            target="memory_consolidation",
            payload={"scope": "docs"},
            enabled=True,
        ),
        ScheduleDefinition(
            schedule_id="stale_pr_scan",
            cron="0 3 * * *",
            action_type="maintenance",
            target="stale_pr_scan",
            payload={},
            enabled=False,
        ),
        ScheduleDefinition(
            schedule_id="docs_freshness_scan",
            cron="0 4 * * *",
            action_type="maintenance",
            target="docs_freshness_scan",
            payload={},
            enabled=False,
        ),
        ScheduleDefinition(
            schedule_id="topology_regeneration",
            cron="*/30 * * * *",
            action_type="maintenance",
            target="topology_regeneration",
            payload={},
            enabled=True,
        ),
    ]
