from loom.memory.memory_service import InMemoryMemoryService
from loom.models import MemoryType, TaskEvent


class _EventBus:
    def __init__(self):
        self.events = []

    def emit(self, event: TaskEvent):
        self.events.append(event)


class _Repo:
    class _Mem:
        def __init__(self):
            self.rows = {}

        def upsert(self, key, data, status="active", version=1):
            _ = (status, version)
            self.rows[key] = data

    def __init__(self):
        self.memory = self._Mem()


def test_memory_write_retrieve_and_invalidate():
    svc = InMemoryMemoryService(_Repo(), _EventBus())
    scope = {
        "organization_id": "org_a",
        "domain_pack": "docs",
        "workflow_id": "wf",
        "workflow_version": 1,
        "role": "docs_ops",
    }
    svc.write(scope, MemoryType.episodic, {"id": "e1", "task_id": "t1", "summary": "hello"})
    rows = svc.retrieve(scope, MemoryType.episodic)
    assert len(rows) == 1
    other_org_rows = svc.retrieve(
        {
            "organization_id": "org_b",
            "domain_pack": "docs",
            "workflow_id": "wf",
            "workflow_version": 1,
            "role": "docs_ops",
        },
        MemoryType.episodic,
    )
    assert other_org_rows == []
    changed = svc.invalidate(scope, hard=False)
    assert changed == 1
