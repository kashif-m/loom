from __future__ import annotations

from loom.models import Task, TaskStatus


class ExecutionCoordinator:
    def __init__(
        self,
        execution_planner,
        participant_resolver,
        policy_engine,
        step_runner,
        collaborative_step_runner,
        transition_engine,
        event_bus,
    ):
        self.execution_planner = execution_planner
        self.participant_resolver = participant_resolver
        self.policy_engine = policy_engine
        self.step_runner = step_runner
        self.collaborative_step_runner = collaborative_step_runner
        self.transition_engine = transition_engine
        self.event_bus = event_bus

    def run_task(self, task: Task, global_policy_ids: list[str] | None = None) -> Task:
        if not task.workflow_id or task.workflow_version is None:
            raise ValueError("task has no selected workflow")

        global_policy_ids = global_policy_ids or []
        ir = self.execution_planner.load_ir(task.workflow_id, task.workflow_version)
        current_step = self.execution_planner.first_step(ir)
        task.current_status = TaskStatus.running
        task.current_step_id = current_step.step_id

        step_map = {s.step_id: s for s in ir.steps}
        while task.current_status == TaskStatus.running and task.current_step_id:
            step = step_map[task.current_step_id]
            participants = self.participant_resolver.resolve(task.task_id, step)

            self.policy_engine.enforce(
                global_policy_ids,
                ir.policy_hints,
                [],
                step.policy_bindings,
                {"operation": "step_execute", "task_id": task.task_id, "step_id": step.step_id},
            )

            if len(participants) > 1:
                outcome, merged = self.collaborative_step_runner.run(task, step, participants)
            else:
                outcome, merged = self.step_runner.run(task, step, participants[0])

            task.execution_refs[step.step_id] = merged
            target = self.execution_planner.next_target(step, outcome)
            task = self.transition_engine.apply(task, target)

            if task.current_status in (TaskStatus.completed, TaskStatus.blocked, TaskStatus.failed):
                break

            if task.current_step_id not in step_map:
                task.current_status = TaskStatus.failed
                task.result_summary = f"invalid next step: {task.current_step_id}"
                break

        return task
