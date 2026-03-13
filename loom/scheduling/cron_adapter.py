from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger


def build_cron_trigger(expr: str) -> CronTrigger:
    return CronTrigger.from_crontab(expr)
