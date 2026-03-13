from __future__ import annotations

from pydantic import BaseModel


class FFResponse(BaseModel):
    task_id: str
    status: str
    workflow_id: str | None = None
    workflow_version: int | None = None
    summary: str | None = None
    job_id: str | None = None
