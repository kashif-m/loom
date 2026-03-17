"""Evaluation signals for Loom MVP."""
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from src.core.event_bus.producer import event_bus
from src.core.event_bus.schemas import EventType, TaskCompletedEvent
from src.core.task_store.models import TaskEvaluation, TaskStatus
from src.core.task_store.operations import TaskStore


class EvaluationService:
    """Service for computing evaluation signals."""

    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

    async def on_task_completed(self, event: TaskCompletedEvent) -> TaskEvaluation:
        """Compute evaluation signals when task completes.

        Signals:
        - completed_successfully: reached final state without escalation
        - rework_count: count of retries across all states
        - false_escalation: escalation occurred but resolved without human input within 30 min
        """
        task_id = event.task_id

        # Get task
        task = await self.task_store.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found for evaluation")
            return None

        # Get task history
        history = await self.task_store.get_task_history(task_id)

        # Compute signals
        completed_successfully = task.status == TaskStatus.CLOSED and task.escalation_count == 0

        # Count rework (retries)
        rework_count = task.retry_count

        # Check for false escalation
        false_escalation = await self._check_false_escalation(task_id)

        # Create evaluation
        evaluation = TaskEvaluation(
            task_id=task_id,
            completed_successfully=completed_successfully,
            rework_count=rework_count,
            false_escalation=false_escalation,
        )

        # Store evaluation
        await self.task_store.record_evaluation(evaluation)

        logger.info(
            f"Task {task_id} evaluation: success={completed_successfully}, "
            f"rework={rework_count}, false_esc={false_escalation}"
        )

        return evaluation

    async def _check_false_escalation(self, task_id: str) -> bool:
        """Check if escalation was resolved quickly without human input.

        An escalation is considered "false" if:
        - Task was escalated
        - Task was resolved within 30 minutes of escalation
        - No human response was provided (task closed directly)
        """
        # Get task history
        history = await self.task_store.get_task_history(task_id)

        # Find escalation event
        escalation_time = None
        resolution_time = None

        for h in history:
            if h.to_state == "escalated":
                escalation_time = h.transitioned_at
            if h.to_state in ["completed", "closed", "done"]:
                resolution_time = h.transitioned_at

        if not escalation_time or not resolution_time:
            return False

        # Check if resolved within 30 minutes
        time_diff = resolution_time - escalation_time
        if time_diff <= timedelta(minutes=30):
            return True

        return False

    async def get_task_metrics(self, task_id: str) -> dict[str, Any]:
        """Get all metrics for a task."""
        task = await self.task_store.get_task(task_id)
        if not task:
            return {}

        history = await self.task_store.get_task_history(task_id)

        # Calculate duration
        if task.closed_at and task.created_at:
            duration = task.closed_at - task.created_at
            duration_minutes = duration.total_seconds() / 60
        else:
            duration_minutes = None

        # Count state transitions
        state_transitions = len(history)

        # Count unique states visited
        unique_states = set()
        for h in history:
            if h.from_state:
                unique_states.add(h.from_state)
            unique_states.add(h.to_state)

        return {
            "task_id": task_id,
            "status": task.status.value,
            "duration_minutes": duration_minutes,
            "state_transitions": state_transitions,
            "unique_states_visited": len(unique_states),
            "retry_count": task.retry_count,
            "escalation_count": task.escalation_count,
            "completed_successfully": task.status == TaskStatus.CLOSED and task.escalation_count == 0,
        }

    async def get_team_metrics(self, team_id: str, days: int = 7) -> dict[str, Any]:
        """Get aggregated metrics for a team."""
        # Get all tasks for team in time window
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Query all tasks (we'll filter in memory for MVP)
        all_tasks = await self.task_store.list_tasks(team_id=team_id, limit=1000)
        team_tasks = [t for t in all_tasks if t.created_at >= since]

        if not team_tasks:
            return {
                "team_id": team_id,
                "period_days": days,
                "total_tasks": 0,
            }

        # Calculate metrics
        completed = sum(1 for t in team_tasks if t.status == TaskStatus.CLOSED)
        escalated = sum(1 for t in team_tasks if t.escalation_count > 0)
        avg_retries = sum(t.retry_count for t in team_tasks) / len(team_tasks)

        return {
            "team_id": team_id,
            "period_days": days,
            "total_tasks": len(team_tasks),
            "completed": completed,
            "escalated": escalated,
            "completion_rate": completed / len(team_tasks) if team_tasks else 0,
            "escalation_rate": escalated / len(team_tasks) if team_tasks else 0,
            "average_retries": avg_retries,
        }


def setup_evaluation_listeners(task_store: TaskStore) -> None:
    """Set up event listeners for evaluation."""
    service = EvaluationService(task_store)

    async def handle_task_completed(event):
        if event.event_type == EventType.TASK_COMPLETED:
            await service.on_task_completed(event)

    event_bus.subscribe(handle_task_completed)
    logger.info("Evaluation listeners set up")
