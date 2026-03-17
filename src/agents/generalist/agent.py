"""Generalist agent for Loom MVP using PydanticAI for specialist execution."""
from typing import Any

from loguru import logger

from src.agents.base.identity import load_identity
from src.agents.base.reflection import self_reflect
from src.agents.pydantic_ai import TaskExecutionAgent
from src.core.event_bus.producer import emit
from src.core.event_bus.schemas import EventType, WorkflowEscalatedEvent
from src.core.llm.client import complete
from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message
from src.core.task_store.operations import TaskStore
from src.core.workflow_engine.matcher import match_workflow
from src.core.workflow_engine.registry import get_registry
from src.core.workflow_engine.schemas import WorkflowDefinition, WorkflowLevel, WorkflowStatus


class GeneralistAgent:
    """Generalist agent - team lead that delegates to PydanticAI specialists."""

    def __init__(self, agent_id: str, task_store: TaskStore):
        self.config = load_identity(agent_id)
        self.task_store = task_store
        self.specialists: list[str] = []
        
        # Auto-discover specialists from same team
        self._discover_specialists()

    def _discover_specialists(self) -> None:
        """Discover specialists in the same team."""
        import json
        from pathlib import Path
        
        agents_config_dir = Path("agents_config")
        if not agents_config_dir.exists():
            return
        
        for config_file in agents_config_dir.glob("*.json"):
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    # Check if this is a specialist in the same team
                    if (
                        config.get("authority_level") == "specialist" and
                        config.get("team_id") == self.config.team_id and
                        config.get("active", True) is True
                    ):
                        self.specialists.append(config["agent_id"])
                        logger.info(f"Auto-registered specialist: {config['agent_id']}")
            except Exception:
                continue
        
        if self.specialists:
            logger.info(f"Generalist {self.config.agent_id} loaded {len(self.specialists)} specialists")
        else:
            logger.warning(f"Generalist {self.config.agent_id} found no specialists in team {self.config.team_id}")

    def register_specialist(self, specialist_id: str) -> None:
        """Register a specialist agent."""
        self.specialists.append(specialist_id)
        logger.info(f"Generalist {self.config.agent_id} registered specialist: {specialist_id}")

    async def handle_task(
        self,
        task_id: str,
        task_description: str,
    ) -> dict[str, Any]:
        """Handle a task delegated by KR using PydanticAI specialists.

        Args:
            task_id: Task ID
            task_description: Task description

        Returns:
            Result
        """
        logger.info(f"Generalist {self.config.agent_id} handling task {task_id}")

        # Match team workflow
        match_result = await match_workflow(task_description, level="team")

        if not match_result:
            logger.warning(f"No workflow match for task {task_id}")
            await self._escalate(task_id, "No matching team workflow found")
            return {"success": False, "reason": "No workflow match"}

        workflow = match_result.workflow
        logger.info(f"Matched workflow: {workflow.id}")

        # Assign to first state
        first_state = workflow.states[0]

        # Get task
        task = await self.task_store.get_task(task_id)
        if not task:
            return {"success": False, "reason": "Task not found"}

        # Assign to specialist
        if not self.specialists:
            logger.error("No specialists available")
            await self._escalate(task_id, "No specialists available")
            return {"success": False, "reason": "No specialists"}

        specialist_id = self.specialists[0]  # Simple FIFO in MVP
        logger.info(f"Assigning task {task_id} to specialist {specialist_id}")

        # Execute with PydanticAI specialist
        specialist = TaskExecutionAgent(specialist_id)

        result = await specialist.run(
            task_id=task_id,
            task_description=task_description,
            workflow_state=first_state,
            success_condition=workflow.success_condition,
        )

        # Review specialist output
        if result["success"]:
            is_approved = await self._review_output(
                task_description,
                result["output"],
                workflow.success_condition,
            )

            if is_approved:
                logger.info(f"Task {task_id} approved by generalist")
                return result
            else:
                logger.warning(f"Task {task_id} rejected by generalist")
                # Retry with same specialist (up to max retries)
                task = await self.task_store.get_task(task_id)
                if task and task.retry_count < 3:
                    return await self.handle_task(task_id, task_description)
                else:
                    await self._escalate(task_id, "Max retries exceeded")
                    return {"success": False, "reason": "Max retries"}
        else:
            logger.error(f"Specialist failed task {task_id}")
            await self._escalate(task_id, result.get("reason", "Specialist failed"))
            return result

    async def _review_output(
        self,
        task_description: str,
        output: str,
        success_condition: str,
    ) -> bool:
        """Review specialist output using Instructor."""
        from src.core.llm.schemas import SelfReflectionResponse
        from src.core.llm.client import complete_structured
        
        messages = [
            Message(
                role="system",
                content="You are reviewing work done by a specialist. Evaluate if it meets the success criteria."
            ),
            Message(
                role="user",
                content=f"Task: {task_description}\n\n"
                       f"Success condition: {success_condition}\n\n"
                       f"Output:\n{output[:2000]}\n\n"
                       f"Does this meet the success criteria?"
            ),
        ]

        try:
            response = await complete_structured(
                role=ModelRole.FAST,
                messages=messages,
                response_model=SelfReflectionResponse,
                temperature=0.3,
            )
            
            logger.info(f"Review result: approved={response.approved}, score={response.score}")
            return response.approved
            
        except Exception as e:
            logger.error(f"Review failed: {e}")
            # Fail-safe: approve if review fails
            return True

    async def _escalate(self, task_id: str, reason: str) -> None:
        """Escalate task to human."""
        await self.task_store.escalate(
            task_id=task_id,
            reason=reason,
            agent_id=self.config.agent_id,
        )

        task = await self.task_store.get_task(task_id)
        if task:
            await emit(WorkflowEscalatedEvent(
                idempotency_key=f"{task_id}:escalated",
                sequence_number=task.version,
                task_id=task_id,
                event_type=EventType.WORKFLOW_ESCALATED,
                reason=reason,
                agent_id=self.config.agent_id,
            ))

        logger.info(f"Task {task_id} escalated: {reason}")
