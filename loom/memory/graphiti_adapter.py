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
        self._store: dict[str, dict[str, Any]] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
            "x-workspace": self.workspace,
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.request(method, url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json() if resp.text else {}

    def upsert(self, key: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            self._store[key] = value
            return
        self._request("PUT", f"/v1/memory/{key}", {"value": value})

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return self._store.get(key)
        try:
            data = self._request("GET", f"/v1/memory/{key}")
            return data.get("value")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def list_by_scope(self, scope_prefix: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return [v for k, v in self._store.items() if k.startswith(scope_prefix)]
        data = self._request("GET", "/v1/memory/search", {"prefix": scope_prefix})
        return data.get("items", [])

    def delete(self, key: str) -> None:
        if not self.enabled:
            self._store.pop(key, None)
            return
        self._request("DELETE", f"/v1/memory/{key}")
