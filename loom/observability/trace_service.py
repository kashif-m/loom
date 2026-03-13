from __future__ import annotations

from uuid import uuid4


class TraceService:
    def __init__(self, audit_log_service, langsmith_adapter=None):
        self.audit_log_service = audit_log_service
        self.langsmith_adapter = langsmith_adapter

    def trace_for_task(self, task_id: str) -> dict:
        events = self.audit_log_service.list_task_events(task_id)
        spans = [
            {"name": e["event_type"], "payload": e["payload"], "timestamp": e["created_at"]}
            for e in events
        ]

        emitted = []
        if self.langsmith_adapter is not None:
            for span in spans:
                emitted.append(
                    self.langsmith_adapter.emit_span(
                        trace_id=str(uuid4()),
                        name=span["name"],
                        payload={"task_id": task_id, **span["payload"]},
                    )
                )
        return {"task_id": task_id, "spans": spans, "langsmith": emitted}
