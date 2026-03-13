from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "local": {
        "graphiti": {"mode": "fallback", "enabled": False},
        "openclaw": {"mode": "disabled", "enabled": False},
        "openai": {"mode": "mock_or_real", "enabled": False},
        "langsmith": {"mode": "disabled", "enabled": False},
        "opencode": {"mode": "filesystem_or_cli", "enabled": False},
    },
    "staging": {
        "graphiti": {"mode": "http", "enabled": True},
        "openclaw": {"mode": "signed", "enabled": True},
        "openai": {"mode": "real", "enabled": True},
        "langsmith": {"mode": "real", "enabled": True},
        "opencode": {"mode": "cli", "enabled": True},
    },
    "prod": {
        "graphiti": {"mode": "http", "enabled": True},
        "openclaw": {"mode": "signed", "enabled": True},
        "openai": {"mode": "real", "enabled": True},
        "langsmith": {"mode": "real", "enabled": True},
        "opencode": {"mode": "cli", "enabled": True},
    },
}


def bootstrap_integration_bindings(settings, repositories, *, force: bool = False) -> dict[str, Any]:
    profile = settings.integration_profile
    bindings = PROFILES[profile]

    existing = repositories.integration_bindings.list()
    if existing and not force:
        return {"profile": profile, "status": "existing", "count": len(existing)}

    for key, value in bindings.items():
        repositories.integration_bindings.upsert(key, value, status="active")

    # conflict detection for explicit config mismatches
    if settings.graphiti_enabled and not settings.graphiti_base_url:
        raise ValueError("graphiti enabled without base URL")
    if settings.openclaw_enabled and not settings.openclaw_shared_secret:
        raise ValueError("openclaw enabled without shared secret")

    return {"profile": profile, "status": "bootstrapped", "count": len(bindings)}
