from __future__ import annotations

from typing import Any

import httpx


class GraphitiAdapter:
    """Graphiti adapter with production HTTP mode and local fallback mode."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        base_url: str = "",
        api_key: str = "",
        workspace: str = "default",
        timeout_seconds: float = 10.0,
    ):
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.workspace = workspace
        self.timeout_seconds = timeout_seconds
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    def _workspace(self, workspace: str | None = None) -> str:
        return workspace or self.workspace

    def _headers(self, *, workspace: str | None = None) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
            "x-workspace": self._workspace(workspace),
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        workspace: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.request(method, url, headers=self._headers(workspace=workspace), json=payload)
            resp.raise_for_status()
            return resp.json() if resp.text else {}

    def upsert(self, key: str, value: dict[str, Any], *, workspace: str | None = None) -> None:
        effective_workspace = self._workspace(workspace)
        if not self.enabled:
            self._store.setdefault(effective_workspace, {})[key] = value
            return
        self._request("PUT", f"/v1/memory/{key}", {"value": value}, workspace=effective_workspace)

    def get(self, key: str, *, workspace: str | None = None) -> dict[str, Any] | None:
        effective_workspace = self._workspace(workspace)
        if not self.enabled:
            return self._store.get(effective_workspace, {}).get(key)
        try:
            data = self._request("GET", f"/v1/memory/{key}", workspace=effective_workspace)
            return data.get("value")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def list_by_scope(self, scope_prefix: str, *, workspace: str | None = None) -> list[dict[str, Any]]:
        effective_workspace = self._workspace(workspace)
        if not self.enabled:
            rows = self._store.get(effective_workspace, {})
            return [v for k, v in rows.items() if k.startswith(scope_prefix)]
        data = self._request("GET", "/v1/memory/search", {"prefix": scope_prefix}, workspace=effective_workspace)
        return data.get("items", [])

    def list_keys_by_scope(self, scope_prefix: str, *, workspace: str | None = None) -> list[str]:
        effective_workspace = self._workspace(workspace)
        if not self.enabled:
            rows = self._store.get(effective_workspace, {})
            return [k for k in rows if k.startswith(scope_prefix)]
        data = self._request("GET", "/v1/memory/search", {"prefix": scope_prefix}, workspace=effective_workspace)
        keys: list[str] = []
        for item in data.get("items", []):
            if isinstance(item, dict):
                key = item.get("key") or item.get("id")
                if key:
                    keys.append(str(key))
        return keys

    def delete(self, key: str, *, workspace: str | None = None) -> None:
        effective_workspace = self._workspace(workspace)
        if not self.enabled:
            self._store.setdefault(effective_workspace, {}).pop(key, None)
            return
        self._request("DELETE", f"/v1/memory/{key}", workspace=effective_workspace)
