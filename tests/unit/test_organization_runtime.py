from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import Organization


def test_organization_runtime_detects_config_drift_and_restart_need(tmp_path: Path):
    container = Container(
        Settings(
            database_url=f"sqlite:///{tmp_path}/runtime.db",
            disable_scheduler=True,
        )
    )
    org = container.repositories.organization.upsert(
        Organization(
            org_id="docs",
            name="Docs",
            openai_api_key="openai-key",
            openai_model="gpt-4.1-mini",
        )
    )
    assert org.org_id == "docs"

    first = container.organization_runtime_service.run("docs")
    assert first["status"] == "running"
    openai_row = next(item for item in first["services"] if item["service_id"] == "openai")
    assert openai_row["state"] == "configured"

    org.openai_model = "gpt-4.1"
    container.repositories.organization.upsert(org)
    drift = container.organization_runtime_service.status("docs")
    assert drift["restart_required"] is True


def test_organization_runtime_can_start_and_stop_litellm_sidecar(tmp_path: Path):
    container = Container(
        Settings(
            database_url=f"sqlite:///{tmp_path}/runtime-sidecar.db",
            disable_scheduler=True,
        )
    )
    org = container.repositories.organization.upsert(
        Organization(
            org_id="docs",
            name="Docs",
            litellm_base_url="http://127.0.0.1:19091",
            litellm_api_key="test-key",
            litellm_start_cmd="echo start-litellm",
        )
    )
    assert org.litellm_start_cmd

    service = container.organization_runtime_service

    class _DummyProc:
        pid = 4242

        def __init__(self):
            self.alive = True

        def poll(self):
            return None if self.alive else 0

        def terminate(self):
            self.alive = False

        def wait(self, timeout=None):
            del timeout
            return 0

        def kill(self):
            self.alive = False

    def _fake_probe(_url):
        key = service._service_key("litellm", "docs")
        proc = service._managed.get(key)
        return {"reachable": bool(proc and proc.poll() is None), "status_code": 200}

    def _fake_start(org_id: str, spec: dict):
        key = service._service_key(spec["service_id"], org_id)
        proc = _DummyProc()
        service._managed[key] = proc
        service._managed_meta[key] = {"org_id": org_id, "service_id": spec["service_id"]}
        return {"started": True, "managed": True, "pid": proc.pid, "reason": "spawned"}

    service._probe_http = _fake_probe
    service._start_server = _fake_start

    started = container.organization_runtime_service.run("docs")
    litellm_row = next(item for item in started["services"] if item["service_id"] == "litellm")
    assert litellm_row["state"] == "running_managed"

    stopped = container.organization_runtime_service.stop("docs")
    assert stopped["status"] == "stopped"
