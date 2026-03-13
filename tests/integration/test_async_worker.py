from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.domainpacks.docs.loader import load_docs_pack


def test_async_worker_submit_and_status(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/async.db",
        disable_scheduler=True,
        async_workers_enabled=True,
    )
    container = Container(settings)
    load_docs_pack(container)

    task = container.intake_service.intake("enhance docs https://example.com", domain_pack="docs")
    job = container.async_worker.submit_task(task.task_id)
    status = container.async_worker.get_job(job.job_id)
    assert status is not None
    assert status["status"] in {"queued", "running", "completed", "failed"}
