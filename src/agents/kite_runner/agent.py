"""Kite Runner agent for Loom MVP."""
from datetime import datetime, timezone, timedelta
from typing import Any

from loguru import logger

from src.agents.base.identity import load_identity
from src.agents.generalist.agent import GeneralistAgent
from src.core.event_bus.producer import emit
from src.core.event_bus.schemas import EventType, TaskCreatedEvent, WorkflowEscalatedEvent
from src.core.task_store.models import TaskStatus
from src.core.task_store.operations import TaskStore
from src.core.workflow_engine.matcher import match_workflow
from src.core.workflow_engine.schemas import WorkflowLevel


class KiteRunner:
    """Kite Runner - org-level orchestrator."""

    def __init__(self, task_store: TaskStore):
        self.config = load_identity("kite_runner")
        self.task_store = task_store
        self.teams: dict[str, str] = {}  # team_id -> generalist_agent_id

    def register_team(self, team_id: str, generalist_id: str) -> None:
        """Register a team with its generalist."""
        self.teams[team_id] = generalist_id
        logger.info(f"KR registered team {team_id} with generalist {generalist_id}")

    async def submit_task(self, description: str) -> dict[str, Any]:
        """Submit a new task to the system.

        Args:
            description: Task description

        Returns:
            Task creation result
        """
        logger.info(f"KR received task: {description[:50]}...")

        # Match org workflow
        match_result = await match_workflow(description, level="org")

        if not match_result:
            logger.warning("No org workflow match")
            return {
                "success": False,
                "reason": "No matching workflow found",
            }

        workflow = match_result.workflow
        logger.info(f"Matched org workflow: {workflow.id}")
        
        # Log LLM match details
        logger.info(f"Workflow match: type={match_result.match_type}, confidence={match_result.confidence}")

        # Determine target team from workflow
        # For MVP, we handle org-level workflows specially
        if workflow.level.value == "org":
            # For org workflows, use the first registered team
            # In production, you'd have logic to pick the right team
            if not self.teams:
                logger.error("No teams registered")
                return {
                    "success": False,
                    "reason": "No teams available",
                }
            team_id = list(self.teams.keys())[0]  # Use first registered team
            logger.info(f"Routing org workflow to team: {team_id}")
        else:
            # For team/agentic workflows, extract from ID
            team_id = workflow.id.split("/")[0] if "/" in workflow.id else "default"

        if team_id not in self.teams:
            logger.error(f"Team {team_id} not registered")
            return {
                "success": False,
                "reason": f"Team {team_id} not available",
            }

        generalist_id = self.teams[team_id]

        # Create task
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=24)  # Default 24h SLA

        task = await self.task_store.create_task(
            workflow_id=workflow.id,
            workflow_version=int(workflow.version.replace("v", "")),
            owner_agent_id=generalist_id,
            team_id=team_id,
            description=description,
            sla_deadline=sla_deadline,
        )

        # Emit task created event
        await emit(TaskCreatedEvent(
            idempotency_key=f"{task.task_id}:created",
            sequence_number=1,
            task_id=task.task_id,
            event_type=EventType.TASK_CREATED,
            description=description,
            workflow_id=workflow.id,
            team_id=team_id,
        ))

        logger.info(f"Task {task.task_id} created and assigned to {generalist_id}")

        # Delegate to generalist
        generalist = GeneralistAgent(generalist_id, self.task_store)

        # In real implementation, this would be async/queued
        # For MVP, we execute directly
        result = await generalist.handle_task(task.task_id, description)

        return {
            "success": result.get("success", False),
            "task_id": task.task_id,
            "result": result,
        }

    async def check_sla_breaches(self) -> list[str]:
        """Check for SLA breaches and escalate.

        Returns:
            List of escalated task IDs
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        # Get all open tasks past SLA
        open_tasks = await self.task_store.list_tasks(status=TaskStatus.OPEN)

        breached_tasks = []
        for task in open_tasks:
            if task.sla_deadline and task.sla_deadline < now:
                logger.warning(f"Task {task.task_id} breached SLA")

                await self.task_store.escalate(
                    task_id=task.task_id,
                    reason=f"SLA deadline breached: {task.sla_deadline}",
                    agent_id=self.config.agent_id,
                )

                await emit(WorkflowEscalatedEvent(
                    idempotency_key=f"{task.task_id}:sla_breach",
                    sequence_number=task.version,
                    task_id=task.task_id,
                    event_type=EventType.WORKFLOW_ESCALATED,
                    reason="SLA deadline breached",
                    agent_id=self.config.agent_id,
                ))

                breached_tasks.append(task.task_id)

        return breached_tasks

    async def respond_to_escalation(
        self,
        task_id: str,
        response: str,
    ) -> dict[str, Any]:
        """Handle human response to escalation.

        Args:
            task_id: Task ID
            response: Human response

        Returns:
            Result
        """
        from src.core.task_store.models import TaskStatus
        from src.core.event_bus.producer import emit
        from src.core.event_bus.schemas import (
            EventType,
            TaskStateTransitionEvent,
            WorkflowEscalatedEvent,
        )
        import uuid

        logger.info(f"KR processing human response for task {task_id}")

        task = await self.task_store.get_task(task_id)
        if not task:
            return {"success": False, "reason": "Task not found"}

        if task.status != TaskStatus.ESCALATED:
            return {"success": False, "reason": "Task not escalated"}

        # Get active blockers
        blockers = await self.task_store.get_task_blockers(task_id)
        active_blockers = [b for b in blockers if b.resolved_at is None]

        # Resolve all active blockers with human response
        for blocker in active_blockers:
            if blocker.id is not None:
                await self.task_store.resolve_blocker(task_id, blocker.id)
                logger.info(f"Resolved blocker {blocker.id} with human response")

        # Record human response as an artifact
        await self.task_store.attach_artifact(
            task_id=task_id,
            artifact_type="human_response",
            reference_url=f"data:text/plain;base64,{response}",  # Store inline
            agent_id=self.config.agent_id,
        )

        # Re-trigger workflow: transition from escalated back to previous state
        # or move to next state based on response
        current_version = task.version
        
        # Transition back to 'in_progress' or continue from current state
        # For simplicity, we'll resume from current state
        await self.task_store.transition_state(
            task_id=task_id,
            to_state=task.current_state,  # Stay in current state but reactivate
            current_version=current_version,
            agent_id=self.config.agent_id,
            event_id=str(uuid.uuid4()),
        )

        # Emit state transition event to trigger workflow continuation
        await emit(TaskStateTransitionEvent(
            idempotency_key=f"{task_id}:human_response_resume",
            sequence_number=task.version + 1,
            task_id=task_id,
            event_type=EventType.TASK_STATE_TRANSITION,
            from_state="escalated",
            to_state=task.current_state,
            agent_id=self.config.agent_id,
        ))

        logger.info(f"Task {task_id} resumed from escalation with human response")

        return {
            "success": True, 
            "task_id": task_id,
            "message": "Escalation resolved, workflow resumed",
        }
