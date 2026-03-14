from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.ui.router import build_ui_router
from loom.ui.security import UIUser


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise RuntimeError(f"route not found: {method} {path}")


def test_ui_api_crud_and_task_flow(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui.db", disable_scheduler=True))
    router = build_ui_router(container)

    publish = _endpoint(router, "/api/workflows/publish", "POST")
    list_workflows = _endpoint(router, "/api/workflows", "GET")
    intake = _endpoint(router, "/api/tasks/intake", "POST")
    bootstrap = _endpoint(router, "/api/bootstrap/docs-pack", "POST")
    upsert_model_provider = _endpoint(router, "/api/model-providers", "POST")
    upsert_model = _endpoint(router, "/api/models", "POST")
    upsert_service_model = _endpoint(router, "/api/service-models", "POST")
    resolve_service_model = _endpoint(router, "/api/service-models/resolve/{service_id}", "GET")
    admin = UIUser(role="admin", identity="test-admin")
    bootstrap(user=admin)

    markdown = """
## Title
Custom Flow
## Purpose
Custom
## Trigger
custom
## Required Inputs
- topic
## Steps
1. Do thing
- id: do_thing
- owned_by: docs_ops
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
"""

    from loom.ui.router import PublishWorkflowRequest, IntakeRequest

    publish(
        PublishWorkflowRequest(
            workflow_id="wf_custom",
            version=1,
            title="Custom",
            domain_pack="custom",
            intent_group="custom_local",
            markdown=markdown,
            activate=True,
        ),
        user=admin,
    )
    workflows = list_workflows(user=admin)
    assert any(w["workflow_id"] == "wf_custom" for w in workflows)

    task_resp = intake(IntakeRequest(request="run custom local workflow", domain_pack="custom"), user=admin)
    assert task_resp["task"]["task_id"]

    from loom.models import ModelDefinition, ModelProviderDefinition, ServiceModelBinding

    upsert_model_provider(
        ModelProviderDefinition(
            provider_id="litellm_local",
            provider_type="litellm",
            base_url="http://localhost:4000",
            api_key="test-key",
            status="active",
        ),
        user=admin,
    )
    upsert_model(
        ModelDefinition(
            model_id="docs_fast",
            provider_id="litellm_local",
            model_name="openai/gpt-4.1-mini",
            status="active",
        ),
        user=admin,
    )
    upsert_service_model(
        ServiceModelBinding(
            service_id="step_execution",
            model_id="docs_fast",
            status="active",
        ),
        user=admin,
    )
    resolved = resolve_service_model("step_execution", user=admin)
    assert resolved["provider_type"] == "litellm"


def test_integrations_status_includes_commands_and_org_overrides(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-status.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    get_status = _endpoint(router, "/api/integrations/status", "GET")
    update_org = _endpoint(router, "/api/organization", "POST")

    from loom.ui.router import OrganizationRequest

    update_org(
        OrganizationRequest(
            name="Acme",
            litellm_base_url="http://org.local:4000",
            litellm_api_key="org-key",
            litellm_default_model="org-model",
            opencode_enabled=True,
            opencode_cmd="opencode",
        ),
        user=admin,
    )

    status = get_status(user=admin)
    assert "commands" in status
    assert status["connectors"] == status["commands"]
    assert "opencode" in status["commands"]
    assert status["organization"]["name"] == "Acme"
    assert status["litellm"]["configured"] is True
    assert status["model_routing"]["step_execution"]["binding_source"] == "organization"


def test_ui_task_intake_accepts_explicit_workflow_pin(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-pin.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    publish = _endpoint(router, "/api/workflows/publish", "POST")
    intake = _endpoint(router, "/api/tasks/intake", "POST")

    from loom.ui.router import IntakeRequest, PublishWorkflowRequest

    markdown = """
## Title
Pinned Flow
## Purpose
Pinned
## Trigger
custom_local
## Required Inputs
- topic
## Steps
1. Do thing
- id: do_thing
- owned_by: docs_ops
- on_success: completed
## Completion Criteria
done
## Blocked Conditions
none
## Failure Conditions
none
## Rules
- none
"""

    # docs_ops is required by markdown compiler validation
    from loom.domainpacks.docs.loader import load_docs_pack

    load_docs_pack(container)
    publish(
        PublishWorkflowRequest(
            workflow_id="wf_pin",
            version=1,
            title="Pinned Flow",
            domain_pack="custom",
            intent_group="custom_local",
            markdown=markdown,
            activate=True,
        ),
        user=admin,
    )

    task_resp = intake(
        IntakeRequest(
            request="this request does not need to match classifier",
            domain_pack="custom",
            workflow_id="wf_pin",
            workflow_version=1,
        ),
        user=admin,
    )
    assert task_resp["task"]["workflow_id"] == "wf_pin"
    assert task_resp["task"]["workflow_version"] == 1


def test_ui_bundle_apply_with_inline_markdown(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-bundle.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    apply_bundle = _endpoint(router, "/api/bundle/apply", "POST")
    list_workflows = _endpoint(router, "/api/workflows", "GET")

    from loom.ui.router import BundleApplyRequest

    bundle_yaml = """
organization:
  name: Bundle UI Org
capabilities:
  - capability_id: ui_cap
    description: ui capability
    connector_binding: none
    status: active
agents:
  - role_id: ui_agent
    title: UI Agent
    domain_pack: custom
    capability_ids: [ui_cap]
    policy_ids: []
    memory_visibility: [custom]
    status: active
workflows:
  - workflow_id: ui_bundle_flow
    version: 1
    title: UI Bundle Flow
    domain_pack: custom
    intent_group: custom_local
    activate: true
    markdown: |
      ## Title
      UI Bundle Flow
      ## Purpose
      Validate UI bundle apply.
      ## Trigger
      custom_local
      ## Required Inputs
      - topic
      ## Steps
      1. Execute
      - id: execute
      - owned_by: ui_agent
      - required_capabilities: ui_cap
      - on_success: completed
      ## Completion Criteria
      done
      ## Blocked Conditions
      none
      ## Failure Conditions
      none
      ## Rules
      - none
"""

    resp = apply_bundle(BundleApplyRequest(bundle_yaml=bundle_yaml), user=admin)
    assert resp["ok"] is True
    assert resp["summary"]["agents"] == 1
    assert resp["summary"]["workflows"] == 1

    workflows = list_workflows(user=admin)
    assert any(w["workflow_id"] == "ui_bundle_flow" for w in workflows)


def test_ui_task_intake_fanout_returns_multiple_tasks(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-fanout.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    apply_bundle = _endpoint(router, "/api/bundle/apply", "POST")
    intake = _endpoint(router, "/api/tasks/intake", "POST")

    from loom.ui.router import BundleApplyRequest, IntakeRequest

    bundle_yaml = """
capabilities:
  - capability_id: ui_fanout_cap
    description: ui fanout capability
    connector_binding: none
    status: active
agents:
  - role_id: ui_fanout_agent
    title: UI Fanout Agent
    domain_pack: custom
    capability_ids: [ui_fanout_cap]
    policy_ids: []
    memory_visibility: [custom]
    status: active
workflows:
  - workflow_id: ui_fanout_flow
    version: 1
    title: UI Fanout Flow
    domain_pack: custom
    intent_group: custom_local
    activate: true
    markdown: |
      ## Title
      UI Fanout Flow
      ## Purpose
      fanout
      ## Trigger
      custom_local
      ## Required Inputs
      - topic
      ## Steps
      1. Execute
      - id: execute
      - owned_by: ui_fanout_agent
      - required_capabilities: ui_fanout_cap
      - on_success: completed
      ## Completion Criteria
      done
      ## Blocked Conditions
      none
      ## Failure Conditions
      none
      ## Rules
      - none
"""
    apply_bundle(BundleApplyRequest(bundle_yaml=bundle_yaml), user=admin)

    resp = intake(
        IntakeRequest(
            request="enhance docs https://example.com/one and https://example.com/two",
            domain_pack="custom",
            workflow_id="ui_fanout_flow",
            workflow_version=1,
            fanout=True,
        ),
        user=admin,
    )
    assert "tasks" in resp
    assert len(resp["tasks"]) == 2
    fanout_group = resp["tasks"][0]["linked_entities"]["fanout_group"]
    fanin = _endpoint(router, "/api/tasks/fanout/{fanout_group}/summary", "GET")
    summary = fanin(fanout_group, user=admin)
    assert summary["count"] == 2


def test_ui_api_organizations_and_org_scoped_intake(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-orgs.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    update_org = _endpoint(router, "/api/organization", "POST")
    list_orgs = _endpoint(router, "/api/organizations", "GET")
    get_org = _endpoint(router, "/api/organization", "GET")
    intake = _endpoint(router, "/api/tasks/intake", "POST")

    from loom.ui.router import IntakeRequest, OrganizationRequest

    update_org(
        OrganizationRequest(
            org_id="docs_team",
            name="Docs Team",
            openai_api_key="docs-team-openai-key",
            openai_model="gpt-4.1-mini",
        ),
        user=admin,
    )

    orgs = list_orgs(user=admin)
    assert any(org["org_id"] == "docs_team" for org in orgs)

    fetched = get_org(org_id="docs_team", user=admin)
    assert fetched["name"] == "Docs Team"

    task_resp = intake(
        IntakeRequest(
            request="run docs task",
            domain_pack="docs",
            organization_id="docs_team",
        ),
        user=admin,
    )
    assert task_resp["task"]["organization_id"] == "docs_team"


def test_ui_api_artifact_upsert_and_list_with_org_filter(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-artifacts.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    upsert_artifact = _endpoint(router, "/api/artifacts/{artifact_type}", "POST")
    list_artifacts = _endpoint(router, "/api/artifacts/{artifact_type}", "GET")

    from loom.ui.router import ArtifactUpsertRequest

    upsert_resp = upsert_artifact(
        "packages",
        ArtifactUpsertRequest(
            payload={
                "organization_id": "docs_team",
                "title": "Docs Package",
                "workflow_id": "docs.task_authoring",
                "workflow_version": 1,
                "content": "package body",
                "status": "active",
            }
        ),
        user=admin,
    )
    assert upsert_resp["ok"] is True

    filtered = list_artifacts("packages", organization_id="docs_team", user=admin)
    assert len(filtered) == 1
    assert filtered[0]["organization_id"] == "docs_team"


def test_ui_bundle_export_and_role_preferred_model(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-export-role.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    from loom.models import ModelDefinition, ModelProviderDefinition
    from loom.ui.router import AgentBuilderRequest

    upsert_provider = _endpoint(router, "/api/model-providers", "POST")
    upsert_model = _endpoint(router, "/api/models", "POST")
    create_agent = _endpoint(router, "/api/agents/builder", "POST")
    export_bundle = _endpoint(router, "/api/bundle/export", "GET")

    upsert_provider(
        ModelProviderDefinition(
            provider_id="litellm_role_provider",
            provider_type="litellm",
            base_url="http://role.local:4000",
            api_key="role-key",
            status="active",
        ),
        user=admin,
    )
    upsert_model(
        ModelDefinition(
            model_id="role_docs_model",
            provider_id="litellm_role_provider",
            model_name="openai/gpt-4.1-mini",
            status="active",
        ),
        user=admin,
    )

    from loom.models import PromptProfile, RoleDefinition

    create_agent(
        AgentBuilderRequest(
            role=RoleDefinition(
                role_id="role_model_agent",
                title="Role Model Agent",
                domain_pack="custom",
                capability_ids=[],
                policy_ids=[],
                memory_visibility=[],
                preferred_model_id="role_docs_model",
                status="active",
            ),
            capabilities=[],
            policies=[],
            prompt_profile=PromptProfile(
                profile_id="role_model_agent_prompt",
                version=1,
                domain_pack="custom",
                system_prompt="role model agent",
                status="active",
            ),
        ),
        user=admin,
    )

    payload = export_bundle(org_id="default", domain_pack="custom", user=admin)
    assert "role_model_agent" in payload.body.decode("utf-8")
    assert "preferred_model_id: role_docs_model" in payload.body.decode("utf-8")


def test_ui_memory_topology_group_membership_and_scope_resolution(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-memory-topology.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    from loom.models import MemoryGroupDefinition, MemoryGroupMembership, RoleDefinition

    upsert_role = _endpoint(router, "/api/roles", "POST")
    upsert_memory_group = _endpoint(router, "/api/memory/groups", "POST")
    list_memory_groups = _endpoint(router, "/api/memory/groups", "GET")
    upsert_membership = _endpoint(router, "/api/memory/memberships", "POST")
    list_memberships = _endpoint(router, "/api/memory/memberships", "GET")
    resolve_scopes = _endpoint(router, "/api/memory/scopes/resolve", "GET")

    upsert_role(
        RoleDefinition(
            role_id="memory_writer",
            title="Memory Writer",
            domain_pack="custom",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            status="active",
        ),
        user=admin,
    )

    upsert_memory_group(
        MemoryGroupDefinition(
            group_id="team_shared",
            organization_id="docs_team",
            title="Team Shared",
            visibility="shared",
            owner_role_id="memory_writer",
            status="active",
        ),
        user=admin,
    )
    groups = list_memory_groups(org_id="docs_team", user=admin)
    assert any(group["group_id"] == "team_shared" for group in groups)

    upsert_membership(
        MemoryGroupMembership(
            organization_id="docs_team",
            group_id="team_shared",
            role_id="memory_writer",
            access="read_write",
            status="active",
        ),
        user=admin,
    )
    memberships = list_memberships(org_id="docs_team", group_id="team_shared", user=admin)
    assert len(memberships) == 1
    assert memberships[0]["role_id"] == "memory_writer"

    scopes = resolve_scopes(
        org_id="docs_team",
        role_id="memory_writer",
        domain_pack="custom",
        workflow_id="wf_custom",
        workflow_version=1,
        user=admin,
    )
    read_groups = {scope["memory_group_id"] for scope in scopes["read"]}
    write_groups = {scope["memory_group_id"] for scope in scopes["write"]}
    assert "team_shared" in read_groups
    assert "team_shared" in write_groups
    assert "private.memory_writer" in write_groups


def test_ui_organization_runtime_run_status_stop(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-runtime.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    from loom.ui.router import OrganizationRuntimeRequest

    runtime_status = _endpoint(router, "/api/organization/runtime", "GET")
    runtime_run = _endpoint(router, "/api/organization/runtime/run", "POST")
    runtime_stop = _endpoint(router, "/api/organization/runtime/stop", "POST")

    first = runtime_status(org_id="default", user=admin)
    assert first["org_id"] == "default"
    assert "status" in first

    running = runtime_run(OrganizationRuntimeRequest(org_id="default"), user=admin)
    assert running["org_id"] == "default"
    assert running["status"] in {"running", "degraded", "blocked"}

    after = runtime_status(org_id="default", user=admin)
    assert after["org_id"] == "default"
    assert "services" in after

    stopped = runtime_stop(OrganizationRuntimeRequest(org_id="default"), user=admin)
    assert stopped["status"] == "stopped"


def test_ui_memory_topology_graph_endpoint(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-topology-graph.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    from loom.models import MemoryGroupDefinition, MemoryGroupMembership, MemoryRoleEdge, RoleDefinition

    upsert_role = _endpoint(router, "/api/roles", "POST")
    upsert_group = _endpoint(router, "/api/memory/groups", "POST")
    upsert_membership = _endpoint(router, "/api/memory/memberships", "POST")
    upsert_edge = _endpoint(router, "/api/memory/edges", "POST")
    graph = _endpoint(router, "/api/memory/topology/graph", "GET")

    for role_id in ("kr", "writer"):
        upsert_role(
            RoleDefinition(
                role_id=role_id,
                title=role_id.upper(),
                domain_pack="custom",
                capability_ids=[],
                policy_ids=[],
                memory_visibility=[],
                status="active",
            ),
            user=admin,
        )

    upsert_group(
        MemoryGroupDefinition(
            group_id="kr_shared",
            organization_id="default",
            title="KR Shared",
            description="shared memory",
            visibility="shared",
            owner_role_id="kr",
            status="active",
        ),
        user=admin,
    )
    upsert_membership(
        MemoryGroupMembership(
            organization_id="default",
            group_id="kr_shared",
            role_id="writer",
            access="read_write",
            status="active",
        ),
        user=admin,
    )
    upsert_edge(
        MemoryRoleEdge(
            organization_id="default",
            parent_role_id="kr",
            child_role_id="writer",
            shared_group_id="kr_shared",
            status="active",
        ),
        user=admin,
    )

    topology = graph(org_id="default", user=admin)
    assert topology["organization_id"] == "default"
    assert any(node["id"] == "role:kr" for node in topology["nodes"])
    assert any(node["id"] == "group:kr_shared" for node in topology["nodes"])
    assert any(edge["kind"] == "membership" for edge in topology["edges"])
    assert topology["validation"]["ok"] is True


def test_ui_designer_draft_generate_and_apply_bundle(tmp_path: Path):
    container = Container(Settings(database_url=f"sqlite:///{tmp_path}/ui-designer.db", disable_scheduler=True))
    router = build_ui_router(container)
    admin = UIUser(role="admin", identity="test-admin")

    get_draft = _endpoint(router, "/api/designer/draft", "GET")
    put_draft = _endpoint(router, "/api/designer/draft", "PUT")
    validate_draft = _endpoint(router, "/api/designer/validate", "POST")
    generate_bundle = _endpoint(router, "/api/designer/bundle/generate", "POST")
    apply_bundle = _endpoint(router, "/api/designer/bundle/apply", "POST")
    list_workflows = _endpoint(router, "/api/workflows", "GET")

    from loom.ui.router import DesignerBundleApplyRequest, DesignerDraftRequest

    initial = get_draft(org_id="default", user=admin)
    assert initial["org_id"] == "default"

    draft = {
        "organization": {"org_id": "default", "name": "Designer Org"},
        "roles": [
            {
                "role_id": "designer_owner",
                "title": "Designer Owner",
                "domain_pack": "custom",
                "capability_ids": [],
                "policy_ids": [],
                "memory_visibility": ["custom"],
                "x": 40,
                "y": 40,
            }
        ],
        "memory_topology": {
            "groups": [],
            "memberships": [],
            "edges": [],
        },
        "workflows": [
            {
                "workflow_id": "designer.flow",
                "version": 1,
                "title": "Designer Flow",
                "domain_pack": "custom",
                "intent_group": "custom_local",
                "activate": True,
                "purpose": "Run designer flow",
                "required_inputs": ["request"],
                "completion_criteria": "done",
                "blocked_conditions": "none",
                "failure_conditions": "none",
                "rules": ["none"],
                "steps": [
                    {
                        "step_id": "execute",
                        "title": "Execute",
                        "owned_by": "designer_owner",
                        "participants": [],
                        "required_capabilities": [],
                        "on_success": "completed",
                        "on_blocked": "blocked",
                        "on_failure": "failed",
                        "state_partition": None,
                    }
                ],
            }
        ],
    }
    stored = put_draft(DesignerDraftRequest(draft=draft), org_id="default", user=admin)
    assert stored["version"] >= 2

    validation = validate_draft(DesignerDraftRequest(draft=draft), org_id="default", user=admin)
    assert validation["ok"] is True

    generated = generate_bundle(DesignerBundleApplyRequest(draft=draft), org_id="default", user=admin)
    assert generated["ok"] is True
    assert "designer.flow" in generated["bundle_yaml"]

    applied = apply_bundle(DesignerBundleApplyRequest(draft=draft), org_id="default", user=admin)
    assert applied["ok"] is True
    assert applied["summary"]["workflows"] == 1

    workflows = list_workflows(user=admin)
    assert any(item["workflow_id"] == "designer.flow" for item in workflows)
