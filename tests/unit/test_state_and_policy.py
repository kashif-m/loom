import pytest

from loom.kernel.policy_engine import PolicyEngine
from loom.kernel.state_machine import TaskStateMachine
from loom.models import PolicyDefinition, PolicyEnforcement, TaskStatus


class _PolicyRegistry:
    def __init__(self):
        self._p = {
            "no_direct_merge": PolicyDefinition(
                policy_id="no_direct_merge",
                description="x",
                enforcement=PolicyEnforcement.block,
                rules={"deny_operation": "merge"},
            )
        }

    def resolve_effective(self, a, b, c, d):
        _ = (a, b, c)
        return [self._p[x] for x in d if x in self._p]


def test_state_machine_valid_and_invalid_transitions():
    sm = TaskStateMachine()
    assert sm.transition(TaskStatus.created, TaskStatus.triaging) == TaskStatus.triaging
    with pytest.raises(ValueError):
        sm.transition(TaskStatus.created, TaskStatus.completed)


def test_policy_engine_blocks_merge():
    pe = PolicyEngine(_PolicyRegistry())
    with pytest.raises(PermissionError):
        pe.enforce([], [], [], ["no_direct_merge"], {"operation": "merge"})
