import json
from pathlib import Path

from loom.app.control_plane_cli import run_control_plane_cli


def _read_json(capsys):
    out = capsys.readouterr().out.strip()
    assert out
    return json.loads(out)


def test_control_plane_cli_core_flow(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/ctl.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    markdown_file = tmp_path / "wf.md"
    markdown_file.write_text(
        """## Title
CLI Workflow
## Purpose
Exercise CLI operations.
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Execute custom
- id: execute_custom
- owned_by: cli_agent
- required_capabilities: cli_cap
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
""",
        encoding="utf-8",
    )

    run_control_plane_cli(
        [
            "organization",
            "set",
            "--name",
            "CLI Org",
            "--litellm-base-url",
            "http://org.local:4000",
            "--litellm-api-key",
            "litellm-key",
            "--litellm-default-model",
            "openai/gpt-4.1-mini",
        ]
    )
    org_payload = _read_json(capsys)
    assert org_payload["ok"] is True
    assert org_payload["organization"]["name"] == "CLI Org"

    run_control_plane_cli(
        [
            "agent",
            "create",
            "--role-id",
            "cli_agent",
            "--title",
            "CLI Agent",
            "--domain-pack",
            "custom",
            "--capability-ids",
            "cli_cap",
            "--ensure-capability",
            "cli_cap:CLI capability:none",
        ]
    )
    agent_payload = _read_json(capsys)
    assert agent_payload["ok"] is True
    assert agent_payload["role"]["role_id"] == "cli_agent"

    run_control_plane_cli(
        [
            "workflow",
            "publish",
            "--workflow-id",
            "cli_workflow",
            "--version",
            "1",
            "--title",
            "CLI Workflow",
            "--domain-pack",
            "custom",
            "--intent-group",
            "custom_local",
            "--markdown-file",
            str(markdown_file),
            "--activate",
        ]
    )
    workflow_payload = _read_json(capsys)
    assert workflow_payload["ok"] is True
    assert workflow_payload["activated"] is True

    run_control_plane_cli(
        [
            "task",
            "intake",
            "--request",
            "do something unrelated",
            "--domain-pack",
            "custom",
            "--workflow-id",
            "cli_workflow",
            "--workflow-version",
            "1",
            "--run",
            "--trace",
        ]
    )
    task_payload = _read_json(capsys)
    assert task_payload["task"]["workflow_id"] == "cli_workflow"
    assert task_payload["task"]["current_status"] in {"completed", "blocked", "failed", "workflow_selected"}
    assert task_payload["trace"]["task_id"] == task_payload["task"]["task_id"]


def test_control_plane_cli_scaffold_starter(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/scaffold.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    run_control_plane_cli(
        [
            "scaffold",
            "starter",
            "--org-name",
            "Scaffold Org",
            "--domain-pack",
            "custom",
            "--agent-id",
            "starter_agent",
            "--workflow-id",
            "starter_workflow",
            "--request",
            "run custom local workflow",
        ]
    )
    payload = _read_json(capsys)
    assert payload["ok"] is True
    assert payload["organization"]["name"] == "Scaffold Org"
    assert payload["agent_id"] == "starter_agent"
    assert payload["workflow_id"] == "starter_workflow"
    assert payload["task"]["workflow_id"] == "starter_workflow"


def test_control_plane_cli_bundle_apply(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/bundle.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    markdown_file = tmp_path / "docs_flow.md"
    markdown_file.write_text(
        """## Title
Bundle Flow
## Purpose
Bundle apply workflow
## Trigger
task_authoring
## Required Inputs
- topic
## Steps
1. Gather
- id: gather
- owned_by: docs_maintainer
- required_capabilities: docs_context
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
""",
        encoding="utf-8",
    )

    spec_file = tmp_path / "bundle.yaml"
    spec_file.write_text(
        f"""organization:
  name: "Bundle Org"
capabilities:
  - capability_id: docs_context
    description: docs context
    connector_binding: none
    status: active
agents:
  - role_id: docs_maintainer
    title: Docs Maintainer
    domain_pack: docs
    capability_ids: [docs_context]
    policy_ids: []
    memory_visibility: [docs]
    status: active
workflows:
  - workflow_id: docs_maintenance
    version: 1
    title: Docs Maintenance
    domain_pack: docs
    intent_group: task_authoring
    activate: true
    markdown_file: {markdown_file.name}
""",
        encoding="utf-8",
    )

    run_control_plane_cli(["bundle", "apply", "--spec-file", str(spec_file)])
    payload = _read_json(capsys)
    assert payload["ok"] is True
    assert payload["summary"]["organization"] is True
    assert payload["summary"]["workflows"] == 1

    run_control_plane_cli(
        [
            "task",
            "intake",
            "--request",
            "unrelated request text",
            "--domain-pack",
            "docs",
            "--workflow-id",
            "docs_maintenance",
            "--workflow-version",
            "1",
            "--run",
        ]
    )
    task_payload = _read_json(capsys)
    assert task_payload["task"]["workflow_id"] == "docs_maintenance"


def test_control_plane_cli_task_fanout(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/fanout-cli.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    run_control_plane_cli(
        [
            "scaffold",
            "starter",
            "--domain-pack",
            "custom",
            "--agent-id",
            "fanout_agent",
            "--workflow-id",
            "fanout_workflow",
        ]
    )
    _ = _read_json(capsys)

    run_control_plane_cli(
        [
            "task",
            "intake",
            "--request",
            "enhance docs https://example.com/a and https://example.com/b",
            "--domain-pack",
            "custom",
            "--workflow-id",
            "fanout_workflow",
            "--workflow-version",
            "1",
            "--fanout",
        ]
    )
    payload = _read_json(capsys)
    assert "tasks" in payload
    assert len(payload["tasks"]) == 2
    fanout_group = payload["tasks"][0]["linked_entities"]["fanout_group"]

    run_control_plane_cli(
        [
            "task",
            "fanin",
            "--fanout-group",
            fanout_group,
        ]
    )
    summary = _read_json(capsys)
    assert summary["count"] == 2


def test_control_plane_cli_supports_multi_org_task_scoping(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/org-scope-cli.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    run_control_plane_cli(
        [
            "organization",
            "set",
            "--org-id",
            "docs_team",
            "--name",
            "Docs Team",
        ]
    )
    payload = _read_json(capsys)
    assert payload["organization"]["org_id"] == "docs_team"

    run_control_plane_cli(["organization", "list"])
    orgs = _read_json(capsys)
    assert any(org["org_id"] == "docs_team" for org in orgs)

    run_control_plane_cli(
        [
            "scaffold",
            "starter",
            "--organization-id",
            "docs_team",
            "--domain-pack",
            "custom",
            "--agent-id",
            "docs_team_agent",
            "--workflow-id",
            "docs_team_workflow",
        ]
    )
    _ = _read_json(capsys)

    run_control_plane_cli(
        [
            "task",
            "intake",
            "--organization-id",
            "docs_team",
            "--request",
            "do docs update",
            "--domain-pack",
            "custom",
            "--workflow-id",
            "docs_team_workflow",
            "--workflow-version",
            "1",
        ]
    )
    task_payload = _read_json(capsys)
    assert task_payload["task"]["organization_id"] == "docs_team"


def test_control_plane_cli_organization_runtime_commands(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/org-runtime-cli.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    run_control_plane_cli(
        [
            "organization",
            "set",
            "--org-id",
            "runtime_org",
            "--name",
            "Runtime Org",
        ]
    )
    _ = _read_json(capsys)

    run_control_plane_cli(["organization", "run", "--org-id", "runtime_org"])
    started = _read_json(capsys)
    assert started["org_id"] == "runtime_org"
    assert started["status"] in {"running", "degraded", "blocked"}

    run_control_plane_cli(["organization", "runtime-status", "--org-id", "runtime_org"])
    status = _read_json(capsys)
    assert status["org_id"] == "runtime_org"
    assert "services" in status

    run_control_plane_cli(["organization", "stop", "--org-id", "runtime_org"])
    stopped = _read_json(capsys)
    assert stopped["status"] == "stopped"


def test_control_plane_cli_bundle_export(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("LOOM_DATABASE_URL", f"sqlite:///{tmp_path}/bundle-export.db")
    monkeypatch.setenv("LOOM_DISABLE_SCHEDULER", "true")

    run_control_plane_cli(
        [
            "organization",
            "set",
            "--org-id",
            "export_org",
            "--name",
            "Export Org",
        ]
    )
    _ = _read_json(capsys)

    run_control_plane_cli(
        [
            "scaffold",
            "starter",
            "--organization-id",
            "export_org",
            "--domain-pack",
            "custom",
            "--agent-id",
            "export_agent",
            "--workflow-id",
            "export_flow",
        ]
    )
    _ = _read_json(capsys)

    output_file = tmp_path / "export.yaml"
    run_control_plane_cli(
        [
            "bundle",
            "export",
            "--organization-id",
            "export_org",
            "--domain-pack",
            "custom",
            "--output-file",
            str(output_file),
        ]
    )
    payload = _read_json(capsys)
    assert payload["ok"] is True
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "organization:" in content
    assert "export_agent" in content


def test_control_plane_cli_remote_auth_headers(monkeypatch, capsys):
    monkeypatch.setenv("LOOM_OPERATOR_TOKEN", "token-123")

    import loom.app.control_plane_cli as cli

    captured = {}

    def fake_remote_request(args, method, path, **kwargs):
        captured["auth_mode"] = args.auth_mode
        captured["token"] = args.token
        captured["method"] = method
        captured["path"] = path
        return {"ok": True, "identity": "remote-user"}

    monkeypatch.setattr(cli, "_remote_request", fake_remote_request)

    run_control_plane_cli(
        [
            "remote",
            "--base-url",
            "http://localhost:8000",
            "--auth-mode",
            "token",
            "auth-check",
        ]
    )
    payload = _read_json(capsys)
    assert payload["ok"] is True
    assert captured["auth_mode"] == "token"
    assert captured["method"] == "GET"
    assert captured["path"] == "/api/auth/me"
