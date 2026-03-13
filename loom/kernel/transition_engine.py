from __future__ import annotations

from loom.models import Task, TaskEvent, TaskStatus


class TransitionEngine:
    def __init__(self, state_machine, event_bus):
        self.state_machine = state_machine
        self.event_bus = event_bus

    def apply(self, task: Task, target: str) -> Task:
        terminal_mapping = {
            "completed": TaskStatus.completed,
            "blocked": TaskStatus.blocked,
            "failed": TaskStatus.failed,
            "awaiting_input": TaskStatus.awaiting_input,
        }
        if target in terminal_mapping:
            task.current_status = self.state_machine.transition(task.current_status, terminal_mapping[target])
            self.event_bus.emit(TaskEvent(task_id=task.task_id, event_type="task_transition", payload={"target": target}))
            return task

        task.current_status = self.state_machine.transition(task.current_status, TaskStatus.running)
        task.current_step_id = target
        self.event_bus.emit(TaskEvent(task_id=task.task_id, event_type="step_transition", payload={"step_id": target}))
        return task
