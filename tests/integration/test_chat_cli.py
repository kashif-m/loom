from pathlib import Path

from loom.app.chat_cli import LoomChatSession
from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import ModelDefinition, ModelProviderDefinition


def test_chat_cli_slash_commands_and_task_execution(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat.db", disable_scheduler=True))
    session = LoomChatSession(container)

    org = session.handle_line('/organization create docs "Docs Org" litellm_base_url=http://localhost:4000')
    assert org["kind"] == "organization"
    assert org["organization"]["org_id"] == "docs"
    assert org["organization"]["name"] == "Docs Org"

    created_agent = session.handle_line(
        '/agents create docs_maintainer "Docs Maintainer" '
        "domain_pack=custom capabilities=docs_context connector=none"
    )
    assert created_agent["kind"] == "agents"
    assert created_agent["created"]["role_id"] == "docs_maintainer"

    created_workflow = session.handle_line(
        '/workflows create docs_flow "Docs Flow" '
        "owned_by=docs_maintainer domain_pack=custom "
        "intent_group=custom_local required_capabilities=docs_context"
    )
    assert created_workflow["kind"] == "workflows"
    assert created_workflow["created"]["workflow_id"] == "docs_flow"

    selected = session.handle_line("/workflows select docs_flow")
    assert selected["selected_workflow_id"] == "docs_flow"

    result = session.handle_line("please update the docs structure for payouts")
    assert result["kind"] == "task_result"
    assert result["workflow_id"] == "docs_flow"
    assert result["task"]["organization_id"] == "docs"
    assert result["status"] in {"completed", "blocked", "failed", "workflow_selected"}


def test_chat_cli_greeting_and_help(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-help.db", disable_scheduler=True))
    session = LoomChatSession(container)

    greeting = session.handle_line("hello")
    assert greeting["kind"] == "chat"
    assert "workflow-bound orchestration" in greeting["message"]

    help_msg = session.handle_line("/help")
    assert help_msg["kind"] == "help"
    assert "/organization" in help_msg["message"]


def test_chat_cli_auto_fanout_for_multi_urls(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-fanout.db", disable_scheduler=True))
    session = LoomChatSession(container)

    session.handle_line('/agents create docs_agent "Docs Agent" domain_pack=custom capabilities=docs_cap connector=none')
    session.handle_line(
        '/workflows create docs_flow "Docs Flow" owned_by=docs_agent '
        "domain_pack=custom intent_group=custom_local required_capabilities=docs_cap"
    )
    session.handle_line("/workflows select docs_flow")

    result = session.handle_line(
        "enhance docs https://example.com/one and https://example.com/two with deterministic flow"
    )
    assert result["kind"] == "task_batch_result"
    assert result["fanout_count"] == 2


def test_chat_cli_organization_list_select_and_task_scoping(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-orgs.db", disable_scheduler=True))
    session = LoomChatSession(container)

    created = session.handle_line('/organization create docs_docs "Docs Docs"')
    assert created["kind"] == "organization"
    assert created["organization"]["org_id"] == "docs_docs"

    _ = session.handle_line('/organization create docs_ops "Docs Ops"')
    listed = session.handle_line("/organization list")
    assert listed["kind"] == "organization_list"
    org_ids = {item["org_id"] for item in listed["items"]}
    assert {"docs_docs", "docs_ops"}.issubset(org_ids)

    selected = session.handle_line("/organization select docs_ops")
    assert selected["kind"] == "organization"
    assert "docs_ops" in selected["message"]

    session.handle_line('/agents create org_agent "Org Agent" domain_pack=custom capabilities=org_cap connector=none')
    session.handle_line(
        '/workflows create org_flow "Org Flow" owned_by=org_agent '
        "domain_pack=custom intent_group=custom_local required_capabilities=org_cap"
    )
    session.handle_line("/workflows select org_flow")

    result = session.handle_line("update docs quickly")
    assert result["kind"] == "task_result"
    assert result["task"]["organization_id"] == "docs_ops"


def test_chat_cli_organization_runtime_commands(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-org-runtime.db", disable_scheduler=True))
    session = LoomChatSession(container)

    created = session.handle_line('/organization create docs "Docs Org"')
    assert created["kind"] == "organization"
    assert created["organization"]["org_id"] == "docs"

    started = session.handle_line("/organization run docs")
    assert started["kind"] == "organization_runtime"
    assert started["runtime"]["org_id"] == "docs"
    assert started["runtime"]["status"] in {"running", "degraded", "blocked"}

    status = session.handle_line("/organization status docs")
    assert status["kind"] == "organization_runtime"
    assert "services" in status["runtime"]

    stopped = session.handle_line("/organization stop docs")
    assert stopped["kind"] == "organization_runtime"
    assert stopped["runtime"]["status"] == "stopped"


def test_chat_cli_bundle_export_and_agent_model_id(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-export.db", disable_scheduler=True))
    session = LoomChatSession(container)

    container.model_provider_registry.upsert(
        ModelProviderDefinition(
            provider_id="chat_provider",
            provider_type="litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
            status="active",
        )
    )
    container.model_registry.upsert(
        ModelDefinition(
            model_id="chat_model",
            provider_id="chat_provider",
            model_name="openai/gpt-4.1-mini",
            status="active",
        )
    )

    created = session.handle_line(
        '/agents create model_agent "Model Agent" domain_pack=custom capabilities=docs_cap model_id=chat_model'
    )
    assert created["kind"] == "agents"
    assert created["created"]["preferred_model_id"] == "chat_model"

    exported = session.handle_line("/bundle export domain_pack=custom")
    assert exported["kind"] == "bundle_export"
    assert "agents:" in exported["yaml"]


def test_chat_cli_models_and_workflow_file_operations(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-models-wf.db", disable_scheduler=True))
    session = LoomChatSession(container)

    provider = session.handle_line("/models add-provider chat_litellm http://localhost:4000 test-key")
    assert provider["kind"] == "models"
    assert provider["provider"]["provider_id"] == "chat_litellm"

    model = session.handle_line("/models add-model chat_fast chat_litellm openai/gpt-4.1-mini max_tokens=2048")
    assert model["kind"] == "models"
    assert model["model"]["model_id"] == "chat_fast"

    binding = session.handle_line("/models bind step_execution chat_fast")
    assert binding["kind"] == "models"
    assert binding["binding"]["service_id"] == "step_execution"

    resolved = session.handle_line("/models resolve step_execution")
    assert resolved["kind"] == "models"
    assert resolved["resolved"]["model_id"] == "chat_fast"

    session.handle_line(
        '/agents create wf_owner "Workflow Owner" domain_pack=custom capabilities=docs_cap connector=none'
    )
    created = session.handle_line(
        '/workflows create wf_file "Workflow File" owned_by=wf_owner domain_pack=custom '
        "intent_group=custom_local required_capabilities=docs_cap"
    )
    assert created["kind"] == "workflows"
    assert created["created"]["version"] == 1

    wf2_path = tmp_path / "wf-v2.md"
    wf2_path.write_text(
        "## Title\nWorkflow File V2\n"
        "## Purpose\nWorkflow published from file.\n"
        "## Trigger\ncustom_local\n"
        "## Required Inputs\n- request\n"
        "## Steps\n"
        "1. Execute docs\n"
        "- id: execute\n"
        "- owned_by: wf_owner\n"
        "- required_capabilities: docs_cap\n"
        "- on_success: completed\n"
        "## Completion Criteria\ncompleted\n"
        "## Blocked Conditions\nmissing context\n"
        "## Failure Conditions\nexecution error\n"
        "## Rules\n- follow workflow\n- keep deterministic\n",
        encoding="utf-8",
    )
    published = session.handle_line(
        f'/workflows publish-file wf_file 2 "Workflow File V2" custom_local {wf2_path} domain_pack=custom activate=true'
    )
    assert published["kind"] == "workflows"
    assert published["published"]["version"] == 2

    diff = session.handle_line("/workflows diff wf_file 1 2")
    assert diff["kind"] == "workflows"
    assert "added" in diff["diff"]

    validated = session.handle_line(f"/workflows validate-file wf_file 3 {wf2_path}")
    assert validated["kind"] == "workflows"
    assert validated["validation"]["ok"] is True


def test_chat_cli_tasks_memory_integrations_and_artifacts(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/chat-ops.db", disable_scheduler=True))
    session = LoomChatSession(container)

    session.handle_line(
        '/organization create docs "Docs Org" litellm_base_url=http://localhost:4000 litellm_api_key=test-key'
    )
    session.handle_line('/agents create docs_owner "Docs Owner" domain_pack=custom capabilities=docs_cap connector=none')
    session.handle_line(
        '/workflows create docs_flow "Docs Flow" owned_by=docs_owner domain_pack=custom '
        "intent_group=custom_local required_capabilities=docs_cap"
    )
    session.handle_line("/workflows select docs_flow")
    group = session.handle_line('/memory group-create kr_shared "KR Shared" visibility=shared')
    assert group["kind"] == "memory"
    assert group["group"]["group_id"] == "kr_shared"

    member = session.handle_line("/memory member-add kr_shared docs_owner access=read_write")
    assert member["kind"] == "memory"
    assert member["membership"]["group_id"] == "kr_shared"

    resolved_scopes = session.handle_line("/memory resolve docs_owner workflow_id=docs_flow workflow_version=1")
    assert resolved_scopes["kind"] == "memory"
    assert any(scope["memory_group_id"] == "kr_shared" for scope in resolved_scopes["scopes"]["write"])

    intake = session.handle_line('/tasks intake "refresh docs section" run=true trace=true')
    assert intake["kind"] == "tasks"
    assert "task" in intake
    task_id = intake["task"]["task_id"]

    events = session.handle_line(f"/tasks events {task_id} limit=50")
    assert events["kind"] == "tasks"
    assert isinstance(events["events"], list)

    trace = session.handle_line(f"/tasks trace {task_id}")
    assert trace["kind"] == "tasks"
    assert trace["trace"]["task_id"] == task_id

    rerun = session.handle_line(f"/tasks run {task_id} trace=true")
    assert rerun["kind"] == "tasks"
    assert rerun["task"]["task_id"] == task_id
    assert "trace" in rerun

    memory_query = session.handle_line(
        "/memory query domain_pack=custom workflow_id=docs_flow workflow_version=1 role=any memory_type=episodic"
    )
    assert memory_query["kind"] == "memory"
    assert "items" in memory_query

    memory_invalidate = session.handle_line(
        "/memory invalidate domain_pack=custom workflow_id=docs_flow workflow_version=1 role=any hard=false"
    )
    assert memory_invalidate["kind"] == "memory"
    assert memory_invalidate["ok"] is True

    integrations = session.handle_line("/integrations status")
    assert integrations["kind"] == "integrations"
    assert integrations["status"]["organization"]["org_id"] == "docs"

    health = session.handle_line("/integrations health")
    assert health["kind"] == "integrations"
    assert "commands" in health["health"]

    package_path = tmp_path / "package.yaml"
    package_path.write_text(
        "title: Docs Package\nworkflow_id: docs_flow\nworkflow_version: 1\ncontent: hello\n",
        encoding="utf-8",
    )
    artifact_upsert = session.handle_line(f"/artifacts upsert-file packages {package_path}")
    assert artifact_upsert["kind"] == "artifacts"
    assert artifact_upsert["artifact_type"] == "packages"

    artifact_list = session.handle_line("/artifacts list packages organization_id=docs")
    assert artifact_list["kind"] == "artifacts"
    assert len(artifact_list["items"]) >= 1
