from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.domainpacks.docs.loader import load_docs_pack
from loom.ingress.admin_adapter import build_admin_router
from loom.ingress.openclaw_adapter import build_router
from loom.ingress.request_models import FFRequest


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise RuntimeError(f"route not found: {method} {path}")


def test_ff_ingress_to_run(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/e2e.db", disable_scheduler=True))
    load_docs_pack(container)

    ingress = build_router(container)
    admin = build_admin_router(container)

    ff = _endpoint(ingress, "/ingress/ff", "POST")
    run = _endpoint(ingress, "/ingress/tasks/{task_id}/run", "POST")
    trace = _endpoint(admin, "/admin/tasks/{task_id}/trace", "GET")

    created = ff(FFRequest(request="enhance these docs https://example.com", domain_pack="docs"))
    assert created.status in {"workflow_selected", "awaiting_input"}

    executed = run(created.task_id)
    assert executed.status in {"completed", "blocked", "failed", "workflow_selected"}

    task_trace = trace(created.task_id)
    assert task_trace["task_id"] == created.task_id
