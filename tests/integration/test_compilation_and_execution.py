from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.domainpacks.docs.loader import load_docs_pack


def test_docs_workflow_compilation_and_execution(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path}/int.db"
    container = Container(Settings(database_url=db_url))
    load_docs_pack(container)

    task = container.intake_service.intake("/ff enhance these docs https://example.com repo: acme/docs")
    assert task.workflow_id is not None

    final_task = container.execution_coordinator.run_task(task)
    assert final_task.current_status.value in {"completed", "blocked"}
