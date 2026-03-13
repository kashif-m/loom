from __future__ import annotations

from typing import Any


class LangSmithAdapter:
    def __init__(self, *, enabled: bool = False, api_key: str = "", project: str = "loom"):
        self.enabled = enabled
        self.api_key = api_key
        self.project = project
        self._client = None
        if enabled:
            try:
                from langsmith import Client

                self._client = Client(api_key=api_key)
            except Exception:
                self.enabled = False

    def emit_span(self, trace_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled or self._client is None:
            return {"trace_id": trace_id, "name": name, "payload": payload, "emitted": False}
        self._client.create_run(
            id=trace_id,
            name=name,
            inputs=payload,
            project_name=self.project,
            run_type="chain",
        )
        return {"trace_id": trace_id, "name": name, "payload": payload, "emitted": True}
