import pytest

from loom.app.config import Settings, validate_settings


def test_validate_external_settings_requires_keys():
    with pytest.raises(ValueError):
        validate_settings(Settings(graphiti_enabled=True))

    with pytest.raises(ValueError):
        validate_settings(Settings(openai_enabled=True))

    with pytest.raises(ValueError):
        validate_settings(Settings(litellm_enabled=True))

    with pytest.raises(ValueError):
        validate_settings(Settings(langsmith_enabled=True))

    with pytest.raises(ValueError):
        validate_settings(Settings(api_auth_enabled=True))
