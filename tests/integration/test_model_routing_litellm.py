from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import CompiledWorkflowStep, ModelDefinition, ModelProviderDefinition, Organization, RoleDefinition, RuntimeParticipant, StepTransitions, Task


def test_step_runner_uses_litellm_route(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/litellm.db",
        disable_scheduler=True,
        litellm_enabled=True,
        litellm_base_url="http://localhost:4000",
        litellm_api_key="litellm-test-key",
        litellm_default_model="openai/gpt-4.1-mini",
    )
    container = Container(settings)
    container.startup()

    captured: dict[str, str | None] = {}

    def fake_run(system_prompt, user_prompt, tools=None, *, model=None, base_url=None, api_key=None):
        del system_prompt, user_prompt, tools
        captured["model"] = model
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return {"ok": True, "output": "ok", "model": model or "mock", "usage": {}}

    container.openai_agents_adapter.run = fake_run  # type: ignore[method-assign]

    task = Task(raw_request="execute docs step")
    step = CompiledWorkflowStep(
        step_id="s1",
        title="Run step",
        owned_by="docs_ops",
        transitions=StepTransitions(on_success="completed"),
    )
    participant = RuntimeParticipant(role_id="docs_ops")

    outcome, output = container.step_runner.run(task, step, participant)
    container.shutdown()

    assert outcome == "success"
    assert output["summary"] == "ok"
    assert captured["model"] == "openai/gpt-4.1-mini"
    assert captured["base_url"] == "http://localhost:4000"
    assert captured["api_key"] == "litellm-test-key"
    assert output["model_output"]["routing"]["provider_type"] == "litellm"


def test_step_runner_prefers_org_litellm_over_bootstrap_default(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/org-litellm.db",
        disable_scheduler=True,
        litellm_enabled=True,
        litellm_base_url="http://seeded.local:4000",
        litellm_api_key="seeded-key",
        litellm_default_model="seeded/model",
    )
    container = Container(settings)
    container.startup()
    container.repositories.organization.upsert(
        Organization(
            org_id="default",
            name="Acme",
            litellm_base_url="http://org.local:4000",
            litellm_api_key="org-key",
            litellm_default_model="org/model",
        )
    )

    captured: dict[str, str | None] = {}

    def fake_run(system_prompt, user_prompt, tools=None, *, model=None, base_url=None, api_key=None):
        del system_prompt, user_prompt, tools
        captured["model"] = model
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return {"ok": True, "output": "ok", "model": model or "mock", "usage": {}}

    container.openai_agents_adapter.run = fake_run  # type: ignore[method-assign]

    task = Task(raw_request="execute step with org litellm config")
    step = CompiledWorkflowStep(
        step_id="s1",
        title="Run step",
        owned_by="docs_ops",
        transitions=StepTransitions(on_success="completed"),
    )
    participant = RuntimeParticipant(role_id="docs_ops")

    outcome, output = container.step_runner.run(task, step, participant)
    container.shutdown()

    assert outcome == "success"
    assert captured["model"] == "org/model"
    assert captured["base_url"] == "http://org.local:4000"
    assert captured["api_key"] == "org-key"
    assert output["model_output"]["routing"]["binding_source"] == "organization"


def test_step_runner_uses_org_openai_when_litellm_missing(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/org-openai.db",
        disable_scheduler=True,
    )
    container = Container(settings)
    container.startup()
    container.repositories.organization.upsert(
        Organization(
            org_id="default",
            name="Acme",
            openai_api_key="org-openai-key",
            openai_model="gpt-4.1-mini",
        )
    )

    captured: dict[str, str | None] = {}

    def fake_run(system_prompt, user_prompt, tools=None, *, model=None, base_url=None, api_key=None):
        del system_prompt, user_prompt, tools
        captured["model"] = model
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return {"ok": True, "output": "ok", "model": model or "mock", "usage": {}}

    container.openai_agents_adapter.run = fake_run  # type: ignore[method-assign]

    task = Task(raw_request="execute step with org openai config")
    step = CompiledWorkflowStep(
        step_id="s1",
        title="Run step",
        owned_by="docs_ops",
        transitions=StepTransitions(on_success="completed"),
    )
    participant = RuntimeParticipant(role_id="docs_ops")

    outcome, output = container.step_runner.run(task, step, participant)
    container.shutdown()

    assert outcome == "success"
    assert captured["model"] == "gpt-4.1-mini"
    assert captured["base_url"] is None
    assert captured["api_key"] == "org-openai-key"
    assert output["model_output"]["routing"]["provider_type"] == "openai"


def test_step_runner_respects_task_organization_id_for_model_routing(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/org-explicit-route.db",
        disable_scheduler=True,
    )
    container = Container(settings)
    container.startup()
    container.repositories.organization.upsert(
        Organization(
            org_id="org_a",
            name="Org A",
            openai_api_key="org-a-key",
            openai_model="gpt-4.1-mini",
        )
    )
    container.repositories.organization.upsert(
        Organization(
            org_id="org_b",
            name="Org B",
            openai_api_key="org-b-key",
            openai_model="gpt-4.1-mini",
        )
    )

    captured: dict[str, str | None] = {}

    def fake_run(system_prompt, user_prompt, tools=None, *, model=None, base_url=None, api_key=None):
        del system_prompt, user_prompt, tools, model, base_url
        captured["api_key"] = api_key
        return {"ok": True, "output": "ok", "model": "mock", "usage": {}}

    container.openai_agents_adapter.run = fake_run  # type: ignore[method-assign]

    task = Task(raw_request="run task in org b", organization_id="org_b")
    step = CompiledWorkflowStep(
        step_id="s1",
        title="Run step",
        owned_by="docs_ops",
        transitions=StepTransitions(on_success="completed"),
    )
    participant = RuntimeParticipant(role_id="docs_ops")

    outcome, output = container.step_runner.run(task, step, participant)
    container.shutdown()

    assert outcome == "success"
    assert captured["api_key"] == "org-b-key"
    assert output["model_output"]["routing"]["binding_source"] == "organization"


def test_step_runner_prefers_role_model_binding_over_org_and_service_defaults(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/role-model-route.db",
        disable_scheduler=True,
        litellm_enabled=True,
        litellm_base_url="http://service.default:4000",
        litellm_api_key="service-key",
        litellm_default_model="service/model",
    )
    container = Container(settings)
    container.startup()
    container.repositories.organization.upsert(
        Organization(
            org_id="default",
            name="Acme",
            litellm_base_url="http://org.default:4000",
            litellm_api_key="org-key",
            litellm_default_model="org/model",
        )
    )

    container.model_provider_registry.upsert(
        ModelProviderDefinition(
            provider_id="custom_provider",
            provider_type="litellm",
            base_url="http://role.model:4000",
            api_key="role-key",
            status="active",
        )
    )
    container.model_registry.upsert(
        ModelDefinition(
            model_id="role_model",
            provider_id="custom_provider",
            model_name="role/model",
            status="active",
        )
    )
    container.role_registry.upsert(
        RoleDefinition(
            role_id="docs_ops",
            title="Docs Ops",
            domain_pack="docs",
            capability_ids=[],
            policy_ids=[],
            memory_visibility=[],
            preferred_model_id="role_model",
            status="active",
        )
    )

    captured: dict[str, str | None] = {}

    def fake_run(system_prompt, user_prompt, tools=None, *, model=None, base_url=None, api_key=None):
        del system_prompt, user_prompt, tools
        captured["model"] = model
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return {"ok": True, "output": "ok", "model": model or "mock", "usage": {}}

    container.openai_agents_adapter.run = fake_run  # type: ignore[method-assign]

    task = Task(raw_request="role specific route")
    step = CompiledWorkflowStep(
        step_id="s1",
        title="Run step",
        owned_by="docs_ops",
        transitions=StepTransitions(on_success="completed"),
    )
    participant = RuntimeParticipant(role_id="docs_ops")

    outcome, output = container.step_runner.run(task, step, participant)
    container.shutdown()

    assert outcome == "success"
    assert captured["model"] == "role/model"
    assert captured["base_url"] == "http://role.model:4000"
    assert captured["api_key"] == "role-key"
    assert output["model_output"]["routing"]["binding_source"] == "role"
