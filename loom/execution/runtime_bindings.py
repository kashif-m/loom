from __future__ import annotations


class RuntimeBindings:
    def __init__(self, adapters: dict[str, object] | None = None):
        self.adapters = adapters or {}

    def bind(self, capability_id: str):
        return self.adapters.get(capability_id)
