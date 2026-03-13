from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.models import CompiledWorkflowStep, RuntimeParticipant, StepTransitions, Task


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
