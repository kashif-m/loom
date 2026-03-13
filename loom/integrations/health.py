from __future__ import annotations

import shutil
from typing import Any

import httpx


def _http_probe(url: str, timeout: float = 3.0) -> dict[str, Any]:
    if not url:
        return {"reachable": False, "reason": "url missing"}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            return {"reachable": resp.status_code < 500, "status_code": resp.status_code}
    except Exception as exc:
        return {"reachable": False, "reason": str(exc)}


def connector_health(settings) -> dict[str, Any]:
    return {
        "commands": {
            "git": shutil.which("git") is not None,
            "gh": shutil.which("gh") is not None,
            "node": shutil.which("node") is not None,
            "java": shutil.which("java") is not None,
            "plantuml": shutil.which("plantuml") is not None,
            settings.opencode_cmd: shutil.which(settings.opencode_cmd) is not None,
        },
        "graphiti": {
            "enabled": settings.graphiti_enabled,
            "probe": _http_probe(settings.graphiti_base_url) if settings.graphiti_enabled else {"reachable": None},
        },
        "openclaw": {
            "enabled": settings.openclaw_enabled,
            "configured": bool(settings.openclaw_shared_secret),
        },
        "openai": {
            "enabled": settings.openai_enabled,
            "configured": bool(settings.openai_api_key),
        },
        "langsmith": {
            "enabled": settings.langsmith_enabled,
            "configured": bool(settings.langsmith_api_key),
        },
    }
