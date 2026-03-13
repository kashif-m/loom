from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(slots=True)
class AsyncJob:
    job_id: str
    task_id: str
    status: str
    created_at: str
    updated_at: str
    error: str | None = None


class AsyncWorkerService:
    def __init__(self, repositories, execution_coordinator, max_workers: int = 4):
        self.repositories = repositories
        self.execution_coordinator = execution_coordinator
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit_task(self, task_id: str) -> AsyncJob:
        task = self.repositories.tasks.get(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")

        job = AsyncJob(
            job_id=str(uuid4()),
            task_id=task_id,
            status="queued",
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.repositories.participants.upsert(
            f"job:{job.job_id}",
            {
                "job_id": job.job_id,
                "task_id": task_id,
                "status": job.status,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "error": None,
            },
            status="active",
        )

        self.executor.submit(self._run_job, job.job_id, task_id)
        return job

    def _run_job(self, job_id: str, task_id: str) -> None:
        record = self.repositories.participants.get(f"job:{job_id}")
        if not record:
            return
        row = record["data"]
        row["status"] = "running"
        row["updated_at"] = self._now()
        self.repositories.participants.upsert(f"job:{job_id}", row, status="active")

        try:
            task = self.repositories.tasks.get(task_id)
            if not task:
                raise KeyError(task_id)
            task = self.execution_coordinator.run_task(task)
            self.repositories.tasks.update(task)
            row["status"] = "completed"
            row["updated_at"] = self._now()
            self.repositories.participants.upsert(f"job:{job_id}", row, status="active")
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)
            row["updated_at"] = self._now()
            self.repositories.participants.upsert(f"job:{job_id}", row, status="retired")

    def get_job(self, job_id: str) -> dict | None:
        row = self.repositories.participants.get(f"job:{job_id}")
        return row["data"] if row else None
