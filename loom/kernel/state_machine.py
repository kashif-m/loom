from __future__ import annotations

from loom.models import TaskStatus


class TaskStateMachine:
    ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.created: {TaskStatus.triaging, TaskStatus.archived},
        TaskStatus.triaging: {TaskStatus.workflow_selected, TaskStatus.awaiting_input, TaskStatus.blocked},
        TaskStatus.workflow_selected: {TaskStatus.running, TaskStatus.blocked},
        TaskStatus.running: {
            TaskStatus.running,
            TaskStatus.awaiting_input,
            TaskStatus.blocked,
            TaskStatus.failed,
            TaskStatus.completed,
        },
        TaskStatus.awaiting_input: {TaskStatus.triaging, TaskStatus.archived, TaskStatus.failed},
        TaskStatus.blocked: {TaskStatus.triaging, TaskStatus.failed, TaskStatus.archived},
        TaskStatus.failed: {TaskStatus.archived},
        TaskStatus.completed: {TaskStatus.archived},
        TaskStatus.archived: set(),
    }

    def can_transition(self, current: TaskStatus, target: TaskStatus) -> bool:
        return target in self.ALLOWED[current]

    def transition(self, current: TaskStatus, target: TaskStatus) -> TaskStatus:
        if not self.can_transition(current, target):
            raise ValueError(f"invalid transition: {current.value} -> {target.value}")
        return target
