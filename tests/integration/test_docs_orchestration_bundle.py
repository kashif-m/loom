from pathlib import Path

from loom.app.bundle_ops import apply_bundle_spec, load_bundle_spec
from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.app.chat_cli import LoomChatSession


class _DeterministicAdapter:
    def run(self, *args, **kwargs):
        return {
            "ok": True,
            "output": "deterministic-test-output",
            "model": kwargs.get("model", "test-model"),
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }


def test_docs_orchestration_bundle_apply_and_run(tmp_path: Path):
    container = Container(
        Settings(
            database_url=f"sqlite:///{tmp_path}/docs-orch.db",
            disable_scheduler=True,
            openai_enabled=True,
            openai_api_key="test-key",
        )
    )
    container.step_runner.agent_adapter = _DeterministicAdapter()
    container.execution_coordinator._connector_available = lambda connector, organization_id: True
    spec_path = Path(__file__).resolve().parents[2] / "examples" / "usecases" / "docs_orchestration" / "bundle.yaml"
    spec, base_dir = load_bundle_spec(str(spec_path))
    org_id = (spec.get("organization") or {}).get("org_id", "default")
    summary = apply_bundle_spec(container, spec, base_dir=base_dir)

    assert summary["organization"] is True
    assert summary["agents"] >= 9
    assert summary["memory_groups"] >= 2
    assert summary["memory_memberships"] >= 1
    assert summary["memory_edges"] >= 1
    assert summary["workflows"] == 5

    workflow_ids = {
        "docs.task_authoring",
        "docs.development",
        "docs.pr_review_addressal",
        "docs.review_feedback_accommodation",
        "docs.pr_promotion",
    }
    listed = {w["workflow_id"] for w in container.workflow_registry.list_all()}
    assert workflow_ids.issubset(listed)

    for workflow_id in workflow_ids:
        task = container.intake_service.intake_with_workflow(
            "run deterministic workflow execution",
            workflow_id=workflow_id,
            workflow_version=1,
            domain_pack="docs.orchestration",
            organization_id=org_id,
        )
        assert task.workflow_id == workflow_id
        task = container.execution_coordinator.run_task(task)
        container.repositories.tasks.update(task)
        assert task.current_status.value in {"completed", "blocked", "failed"}

    memory_rows = container.repositories.memory.list()
    assert len(memory_rows) > 0
    scopes = [row["data"]["scope"] for row in memory_rows]
    assert any(scope.get("organization_id") == org_id for scope in scopes)
    assert any(str(scope.get("memory_group_id", "")).startswith("private.") for scope in scopes)
    assert any(scope.get("memory_group_id") == "kr_shared" for scope in scopes)


def test_chat_cli_bundle_apply_and_select_workflow(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/docs-orch-chat.db", disable_scheduler=True))
    session = LoomChatSession(container)

    spec_path = Path(__file__).resolve().parents[2] / "examples" / "usecases" / "docs_orchestration" / "bundle.yaml"
    resp = session.handle_line(f"/bundle apply {spec_path}")
    assert resp["kind"] == "bundle"
    assert resp["summary"]["workflows"] == 5

    selected = session.handle_line("/workflows select docs.task_authoring 1")
    assert selected["kind"] == "workflows"
    assert selected["selected_workflow_id"] == "docs.task_authoring"

    result = session.handle_line("enhance docs for API retries section")
    assert result["kind"] == "task_result"
    assert result["workflow_id"] == "docs.task_authoring"


def test_docs_orchestration_bundle_apply_is_idempotent(tmp_path: Path):
    container = Container(
        Settings(
            database_url=f"sqlite:///{tmp_path}/docs-orch-idempotent.db",
            disable_scheduler=True,
        )
    )
    spec_path = Path(__file__).resolve().parents[2] / "examples" / "usecases" / "docs_orchestration" / "bundle.yaml"
    spec, base_dir = load_bundle_spec(str(spec_path))

    first = apply_bundle_spec(container, spec, base_dir=base_dir)
    second = apply_bundle_spec(container, spec, base_dir=base_dir)

    assert first["workflows"] == 5
    assert second["workflows"] == 5
