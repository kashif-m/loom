from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    app_name: str = "loom"
    env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "sqlite:///./loom.db"
    log_level: str = "INFO"
    strict_connectors: bool = False
    disable_scheduler: bool = False

    # Integration toggles
    graphiti_enabled: bool = False
    graphiti_base_url: str = ""
    graphiti_api_key: str = ""
    graphiti_workspace: str = "default"

    opencode_enabled: bool = False
    opencode_cmd: str = "opencode"

    openclaw_enabled: bool = False
    openclaw_shared_secret: str = ""

    openai_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    litellm_enabled: bool = False
    litellm_base_url: str = ""
    litellm_api_key: str = ""
    litellm_default_model: str = "openai/gpt-4.1-mini"
    litellm_start_cmd: str = ""
    graphiti_start_cmd: str = ""

    langsmith_enabled: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "loom"

    # Security
    api_auth_enabled: bool = False
    ingress_api_key: str = ""
    admin_api_key: str = ""
    ui_auth_mode: str = "none"  # none | token
    viewer_token: str = ""
    operator_token: str = ""
    admin_token: str = ""

    # Runtime
    async_workers_enabled: bool = False
    max_worker_threads: int = 4
    integration_profile: str = "local"  # local | staging | prod

    # Optional bootstrap sources for external tools
    openclaw_repo_url: str = "https://github.com/example/openclaw.git"
    opencode_repo_url: str = "https://github.com/example/opencode.git"
    graphiti_repo_url: str = "https://github.com/example/graphiti.git"


def _getenv_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("LOOM_APP_NAME", "loom"),
        env=os.getenv("LOOM_ENV", "dev"),
        host=os.getenv("LOOM_HOST", "0.0.0.0"),
        port=int(os.getenv("LOOM_PORT", "8000")),
        database_url=os.getenv("LOOM_DATABASE_URL", "sqlite:///./loom.db"),
        log_level=os.getenv("LOOM_LOG_LEVEL", "INFO"),
        strict_connectors=_getenv_bool("LOOM_STRICT_CONNECTORS"),
        disable_scheduler=_getenv_bool("LOOM_DISABLE_SCHEDULER"),
        graphiti_enabled=_getenv_bool("LOOM_GRAPHITI_ENABLED"),
        graphiti_base_url=os.getenv("LOOM_GRAPHITI_BASE_URL", ""),
        graphiti_api_key=os.getenv("LOOM_GRAPHITI_API_KEY", ""),
        graphiti_workspace=os.getenv("LOOM_GRAPHITI_WORKSPACE", "default"),
        opencode_enabled=_getenv_bool("LOOM_OPENCODE_ENABLED"),
        opencode_cmd=os.getenv("LOOM_OPENCODE_CMD", "opencode"),
        openclaw_enabled=_getenv_bool("LOOM_OPENCLAW_ENABLED"),
        openclaw_shared_secret=os.getenv("LOOM_OPENCLAW_SHARED_SECRET", ""),
        openai_enabled=_getenv_bool("LOOM_OPENAI_ENABLED"),
        openai_api_key=os.getenv("LOOM_OPENAI_API_KEY", ""),
        openai_model=os.getenv("LOOM_OPENAI_MODEL", "gpt-4.1-mini"),
        litellm_enabled=_getenv_bool("LOOM_LITELLM_ENABLED"),
        litellm_base_url=os.getenv("LOOM_LITELLM_BASE_URL", ""),
        litellm_api_key=os.getenv("LOOM_LITELLM_API_KEY", ""),
        litellm_default_model=os.getenv("LOOM_LITELLM_DEFAULT_MODEL", "openai/gpt-4.1-mini"),
        litellm_start_cmd=os.getenv("LOOM_LITELLM_START_CMD", ""),
        graphiti_start_cmd=os.getenv("LOOM_GRAPHITI_START_CMD", ""),
        langsmith_enabled=_getenv_bool("LOOM_LANGSMITH_ENABLED"),
        langsmith_api_key=os.getenv("LOOM_LANGSMITH_API_KEY", ""),
        langsmith_project=os.getenv("LOOM_LANGSMITH_PROJECT", "loom"),
        api_auth_enabled=_getenv_bool("LOOM_API_AUTH_ENABLED"),
        ingress_api_key=os.getenv("LOOM_INGRESS_API_KEY", ""),
        admin_api_key=os.getenv("LOOM_ADMIN_API_KEY", ""),
        ui_auth_mode=os.getenv("LOOM_UI_AUTH_MODE", "none"),
        viewer_token=os.getenv("LOOM_VIEWER_TOKEN", ""),
        operator_token=os.getenv("LOOM_OPERATOR_TOKEN", ""),
        admin_token=os.getenv("LOOM_ADMIN_TOKEN", ""),
        async_workers_enabled=_getenv_bool("LOOM_ASYNC_WORKERS_ENABLED"),
        max_worker_threads=int(os.getenv("LOOM_MAX_WORKER_THREADS", "4")),
        integration_profile=os.getenv("LOOM_INTEGRATION_PROFILE", "local"),
        openclaw_repo_url=os.getenv("LOOM_OPENCLAW_REPO_URL", "https://github.com/example/openclaw.git"),
        opencode_repo_url=os.getenv("LOOM_OPENCODE_REPO_URL", "https://github.com/example/opencode.git"),
        graphiti_repo_url=os.getenv("LOOM_GRAPHITI_REPO_URL", "https://github.com/example/graphiti.git"),
    )


def _redacted_env_keys() -> dict[str, str]:
    keys = [
        "LOOM_GRAPHITI_API_KEY",
        "LOOM_OPENAI_API_KEY",
        "LOOM_LITELLM_API_KEY",
        "LOOM_LANGSMITH_API_KEY",
        "LOOM_INGRESS_API_KEY",
        "LOOM_ADMIN_API_KEY",
        "LOOM_OPENCLAW_SHARED_SECRET",
        "LOOM_VIEWER_TOKEN",
        "LOOM_OPERATOR_TOKEN",
        "LOOM_ADMIN_TOKEN",
    ]
    return {k: "***" for k in keys if os.getenv(k)}


def validate_settings(settings: Settings) -> None:
    if settings.port < 1 or settings.port > 65535:
        raise ValueError("LOOM_PORT must be between 1 and 65535")
    if not (settings.database_url.startswith("sqlite") or settings.database_url.startswith("postgresql")):
        raise ValueError("LOOM_DATABASE_URL must be sqlite:// or postgresql://")

    if settings.graphiti_enabled and (not settings.graphiti_base_url or not settings.graphiti_api_key):
        raise ValueError("Graphiti enabled but LOOM_GRAPHITI_BASE_URL/LOOM_GRAPHITI_API_KEY missing")
    if settings.openclaw_enabled and not settings.openclaw_shared_secret:
        raise ValueError("OpenClaw enabled but LOOM_OPENCLAW_SHARED_SECRET missing")
    if settings.openai_enabled and not settings.openai_api_key:
        raise ValueError("OpenAI enabled but LOOM_OPENAI_API_KEY missing")
    if settings.litellm_enabled and (not settings.litellm_base_url or not settings.litellm_api_key):
        raise ValueError("LiteLLM enabled but LOOM_LITELLM_BASE_URL/LOOM_LITELLM_API_KEY missing")
    if settings.langsmith_enabled and not settings.langsmith_api_key:
        raise ValueError("LangSmith enabled but LOOM_LANGSMITH_API_KEY missing")
    if settings.api_auth_enabled and (not settings.ingress_api_key or not settings.admin_api_key):
        raise ValueError("API auth enabled but LOOM_INGRESS_API_KEY/LOOM_ADMIN_API_KEY missing")
    if settings.ui_auth_mode not in {"none", "token"}:
        raise ValueError("LOOM_UI_AUTH_MODE must be one of: none, token")
    if settings.ui_auth_mode == "token":
        if not settings.admin_token:
            raise ValueError("token UI auth requires LOOM_ADMIN_TOKEN")
        if not settings.operator_token:
            raise ValueError("token UI auth requires LOOM_OPERATOR_TOKEN")
        if not settings.viewer_token:
            raise ValueError("token UI auth requires LOOM_VIEWER_TOKEN")
    if settings.integration_profile not in {"local", "staging", "prod"}:
        raise ValueError("LOOM_INTEGRATION_PROFILE must be one of: local, staging, prod")


def sanitized_runtime_config(settings: Settings) -> dict[str, object]:
    payload = {
        "app_name": settings.app_name,
        "env": settings.env,
        "database_url": settings.database_url,
        "graphiti_enabled": settings.graphiti_enabled,
        "openai_enabled": settings.openai_enabled,
        "litellm_base_url": settings.litellm_base_url,
        "litellm_default_model": settings.litellm_default_model,
        "litellm_enabled": settings.litellm_enabled,
        "litellm_start_cmd_configured": bool(settings.litellm_start_cmd),
        "graphiti_start_cmd_configured": bool(settings.graphiti_start_cmd),
        "langsmith_enabled": settings.langsmith_enabled,
        "openclaw_enabled": settings.openclaw_enabled,
        "api_auth_enabled": settings.api_auth_enabled,
        "ui_auth_mode": settings.ui_auth_mode,
        "async_workers_enabled": settings.async_workers_enabled,
        "max_worker_threads": settings.max_worker_threads,
        "integration_profile": settings.integration_profile,
    }
    payload.update(_redacted_env_keys())
    return payload
