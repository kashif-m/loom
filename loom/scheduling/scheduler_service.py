from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from loom.models import TaskEvent
from loom.scheduling.cron_adapter import build_cron_trigger


class SchedulerService:
    def __init__(self, schedule_registry, event_bus):
        self.schedule_registry = schedule_registry
        self.event_bus = event_bus
        self.scheduler = BackgroundScheduler()

    def _run_scheduled(self, schedule):
        self.event_bus.emit(
            TaskEvent(task_id="system", event_type="schedule_triggered", payload=schedule.model_dump())
        )

    def reload(self) -> None:
        self.scheduler.remove_all_jobs()
        for schedule in self.schedule_registry.list(enabled_only=True):
            self.scheduler.add_job(
                self._run_scheduled,
                trigger=build_cron_trigger(schedule.cron),
                id=schedule.schedule_id,
                kwargs={"schedule": schedule},
                replace_existing=True,
            )

    def start(self) -> None:
        self.reload()
        if not self.scheduler.running:
            self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
