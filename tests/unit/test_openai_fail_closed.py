from loom.adapters.openai_agents_adapter import OpenAIAgentsAdapter


def test_openai_adapter_fails_closed_when_sdk_missing():
    adapter = OpenAIAgentsAdapter(enabled=False, api_key="", model="gpt-4.1-mini")
    adapter._openai_cls = None
    result = adapter.run(system_prompt="sys", user_prompt="hello", tools=[])
    assert result["ok"] is False
    assert result["error_code"] == "MODEL_SDK_MISSING"
    assert result["output"] == ""


def test_openai_adapter_fails_closed_when_api_key_missing():
    adapter = OpenAIAgentsAdapter(enabled=False, api_key="", model="gpt-4.1-mini")
    adapter._openai_cls = object
    result = adapter.run(system_prompt="sys", user_prompt="hello", tools=[])
    assert result["ok"] is False
    assert result["error_code"] == "MODEL_API_KEY_MISSING"
    assert result["output"] == ""
