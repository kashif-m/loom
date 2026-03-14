from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_value(value: str | None) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OrganizationRuntimeService:
    """Manages org-level runtime state and optional local side-service processes."""

    def __init__(self, settings, repositories):
        self.settings = settings
        self.repositories = repositories
        self._lock = threading.RLock()
        self._managed: dict[tuple[str, str], subprocess.Popen] = {}
        self._managed_meta: dict[tuple[str, str], dict[str, Any]] = {}

    def _runtime_key(self, org_id: str) -> str:
        return org_id

    def _config_hash(self, org) -> str:
        material = {
            "org_id": org.org_id,
            "litellm_base_url": org.litellm_base_url or "",
            "litellm_default_model": org.litellm_default_model or "",
            "litellm_start_cmd": org.litellm_start_cmd or "",
            "litellm_api_key_hash": _hash_value(org.litellm_api_key),
            "openai_model": org.openai_model or "",
            "openai_api_key_hash": _hash_value(org.openai_api_key),
            "opencode_enabled": bool(org.opencode_enabled),
            "opencode_cmd": org.opencode_cmd or "",
            "graphiti_enabled": bool(self.settings.graphiti_enabled),
            "graphiti_base_url": self.settings.graphiti_base_url or "",
            "graphiti_start_cmd": self.settings.graphiti_start_cmd or "",
            "graphiti_api_key_hash": _hash_value(self.settings.graphiti_api_key),
        }
        text = json.dumps(material, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load_state(self, org_id: str) -> dict[str, Any]:
        row = self.repositories.organization_runtimes.get(self._runtime_key(org_id))
        if row and isinstance(row.get("data"), dict):
            return dict(row["data"])
        now = _utc_iso()
        return {
            "org_id": org_id,
            "status": "stopped",
            "restart_required": False,
            "config_hash": "",
            "services": [],
            "started_at": None,
            "updated_at": now,
            "message": "organization runtime not started yet",
        }

    def _save_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload["updated_at"] = _utc_iso()
        self.repositories.organization_runtimes.upsert(
            self._runtime_key(payload["org_id"]),
            payload,
            status="active",
        )
        return payload

    def _probe_http(self, url: str | None) -> dict[str, Any]:
        if not url:
            return {"reachable": False, "reason": "url_missing"}
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(url)
                return {"reachable": resp.status_code < 500, "status_code": resp.status_code}
        except Exception as exc:
            return {"reachable": False, "reason": str(exc)}

    def _service_scope(self, service_id: str, org_id: str) -> str:
        if service_id == "graphiti":
            return "__global__"
        return org_id

    def _service_key(self, service_id: str, org_id: str) -> tuple[str, str]:
        return (self._service_scope(service_id, org_id), service_id)

    def _build_specs(self, org) -> list[dict[str, Any]]:
        litellm_start_cmd = (org.litellm_start_cmd or self.settings.litellm_start_cmd or "").strip()
        graphiti_start_cmd = (self.settings.graphiti_start_cmd or "").strip()
        opencode_cmd = (org.opencode_cmd or self.settings.opencode_cmd or "opencode").strip()
        litellm_configured = bool(org.litellm_base_url and org.litellm_api_key)
        litellm_managed = litellm_configured and bool(litellm_start_cmd)

        litellm_spec: dict[str, Any]
        if litellm_managed:
            litellm_spec = {
                "service_id": "litellm",
                "type": "server",
                "required": True,
                "configured": True,
                "health_url": org.litellm_base_url,
                "start_command": litellm_start_cmd,
                "scope": self._service_scope("litellm", org.org_id),
            }
        else:
            litellm_spec = {
                "service_id": "litellm",
                "type": "api",
                "required": litellm_configured,
                "configured": litellm_configured,
                "scope": self._service_scope("litellm", org.org_id),
            }

        return [
            litellm_spec,
            {
                "service_id": "graphiti",
                "type": "server",
                "required": bool(self.settings.graphiti_enabled),
                "configured": bool(self.settings.graphiti_enabled and self.settings.graphiti_base_url),
                "health_url": self.settings.graphiti_base_url,
                "start_command": graphiti_start_cmd or None,
                "scope": self._service_scope("graphiti", org.org_id),
            },
            {
                "service_id": "opencode",
                "type": "command",
                "required": bool(org.opencode_enabled or self.settings.opencode_enabled),
                "configured": True,
                "command": opencode_cmd,
                "scope": self._service_scope("opencode", org.org_id),
            },
            {
                "service_id": "openai",
                "type": "api",
                "required": bool(org.openai_api_key),
                "configured": bool(org.openai_api_key),
                "scope": self._service_scope("openai", org.org_id),
            },
        ]

    def _terminate_managed(self, key: tuple[str, str]) -> bool:
        proc = self._managed.get(key)
        if not proc:
            return False
        if proc.poll() is not None:
            self._managed.pop(key, None)
            self._managed_meta.pop(key, None)
            return False
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        self._managed.pop(key, None)
        self._managed_meta.pop(key, None)
        return True

    def _start_server(self, org_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        service_id = spec["service_id"]
        key = self._service_key(service_id, org_id)
        probe = self._probe_http(spec.get("health_url"))
        if probe.get("reachable"):
            return {"started": False, "managed": False, "reason": "already_reachable"}

        proc = self._managed.get(key)
        if proc and proc.poll() is None:
            return {"started": False, "managed": True, "pid": proc.pid, "reason": "already_managed"}

        command = (spec.get("start_command") or "").strip()
        if not command:
            return {"started": False, "managed": False, "reason": "start_command_missing"}

        try:
            # Allow full command lines to support local stacks without wrappers.
            proc = subprocess.Popen(  # noqa: S603
                ["bash", "-lc", command],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            return {"started": False, "managed": False, "reason": f"spawn_failed: {exc}"}

        self._managed[key] = proc
        self._managed_meta[key] = {
            "org_id": org_id,
            "service_id": service_id,
            "command": command,
            "started_at": _utc_iso(),
        }
        return {"started": True, "managed": True, "pid": proc.pid, "reason": "spawned"}

    def _server_snapshot(self, org_id: str, spec: dict[str, Any], *, auto_start: bool) -> dict[str, Any]:
        service_id = spec["service_id"]
        key = self._service_key(service_id, org_id)
        proc = self._managed.get(key)
        if proc and proc.poll() is not None:
            self._managed.pop(key, None)
            self._managed_meta.pop(key, None)
            proc = None

        start_result: dict[str, Any] | None = None
        if auto_start and spec.get("required") and spec.get("configured"):
            start_result = self._start_server(org_id, spec)
            if start_result.get("started"):
                # Give a just-started process a brief chance to bind the port.
                time.sleep(0.35)

        probe = self._probe_http(spec.get("health_url"))
        proc = self._managed.get(key)
        managed_alive = bool(proc and proc.poll() is None)
        healthy = bool(probe.get("reachable"))
        if not spec.get("required"):
            state = "disabled"
        elif not spec.get("configured"):
            state = "missing_config"
        elif healthy and managed_alive:
            state = "running_managed"
        elif healthy:
            state = "running_external"
        elif managed_alive:
            state = "starting"
        elif start_result and start_result.get("reason") == "start_command_missing":
            state = "missing_start_command"
        else:
            state = "unreachable"

        return {
            "service_id": service_id,
            "type": "server",
            "scope": spec.get("scope"),
            "required": bool(spec.get("required")),
            "configured": bool(spec.get("configured")),
            "healthy": healthy,
            "state": state,
            "health_url": spec.get("health_url"),
            "start_command_configured": bool(spec.get("start_command")),
            "managed": managed_alive,
            "pid": proc.pid if managed_alive and proc else None,
            "probe": probe,
            "start_result": start_result,
        }

    def _command_snapshot(self, org_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        del org_id
        command = spec.get("command")
        available = bool(command and shutil.which(command))
        return {
            "service_id": spec["service_id"],
            "type": "command",
            "scope": spec.get("scope"),
            "required": bool(spec.get("required")),
            "configured": bool(spec.get("configured")),
            "healthy": available,
            "state": "available" if available else "missing_command",
            "command": command,
        }

    def _api_snapshot(self, org_id: str, spec: dict[str, Any]) -> dict[str, Any]:
        del org_id
        configured = bool(spec.get("configured"))
        return {
            "service_id": spec["service_id"],
            "type": "api",
            "scope": spec.get("scope"),
            "required": bool(spec.get("required")),
            "configured": configured,
            "healthy": configured,
            "state": "configured" if configured else "missing_config",
        }

    def _snapshot_services(self, org, *, auto_start: bool) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for spec in self._build_specs(org):
            if spec["type"] == "server":
                snapshots.append(self._server_snapshot(org.org_id, spec, auto_start=auto_start))
            elif spec["type"] == "command":
                snapshots.append(self._command_snapshot(org.org_id, spec))
            else:
                snapshots.append(self._api_snapshot(org.org_id, spec))
        return snapshots

    def _rollup_status(self, services: list[dict[str, Any]]) -> str:
        required = [s for s in services if s.get("required")]
        if not required:
            return "running"
        if any(not s.get("configured") for s in required):
            return "blocked"
        if all(s.get("healthy") for s in required):
            return "running"
        if any(s.get("healthy") for s in required):
            return "degraded"
        return "blocked"

    def status(self, org_id: str = "default") -> dict[str, Any]:
        with self._lock:
            org = self.repositories.organization.get_or_create(org_id)
            config_hash = self._config_hash(org)
            previous = self._load_state(org_id)
            services = self._snapshot_services(org, auto_start=False)
            status = self._rollup_status(services)
            restart_required = bool(
                previous.get("status") in {"running", "degraded"}
                and previous.get("config_hash")
                and previous.get("config_hash") != config_hash
            )
            payload = {
                "org_id": org_id,
                "status": status,
                "restart_required": restart_required,
                "config_hash": config_hash,
                "services": services,
                "started_at": previous.get("started_at"),
                "updated_at": _utc_iso(),
                "message": (
                    "runtime configuration changed; run organization again to apply"
                    if restart_required
                    else "organization runtime status refreshed"
                ),
            }
            return self._save_state(payload)

    def run(self, org_id: str = "default") -> dict[str, Any]:
        with self._lock:
            org = self.repositories.organization.get_or_create(org_id)
            config_hash = self._config_hash(org)
            previous = self._load_state(org_id)
            if previous.get("config_hash") and previous.get("config_hash") != config_hash:
                self.stop(org_id)
            services = self._snapshot_services(org, auto_start=True)
            status = self._rollup_status(services)
            started_at = previous.get("started_at") or _utc_iso()
            payload = {
                "org_id": org_id,
                "status": status,
                "restart_required": False,
                "config_hash": config_hash,
                "services": services,
                "started_at": started_at,
                "updated_at": _utc_iso(),
                "message": "organization runtime started",
            }
            return self._save_state(payload)

    def stop(self, org_id: str = "default") -> dict[str, Any]:
        with self._lock:
            terminated = 0
            for key, meta in list(self._managed_meta.items()):
                if meta.get("org_id") != org_id:
                    continue
                if self._terminate_managed(key):
                    terminated += 1
            previous = self._load_state(org_id)
            payload = {
                "org_id": org_id,
                "status": "stopped",
                "restart_required": False,
                "config_hash": previous.get("config_hash", ""),
                "services": [],
                "started_at": None,
                "updated_at": _utc_iso(),
                "message": f"organization runtime stopped (terminated_processes={terminated})",
            }
            return self._save_state(payload)

    def shutdown(self) -> None:
        with self._lock:
            for key in list(self._managed):
                self._terminate_managed(key)
