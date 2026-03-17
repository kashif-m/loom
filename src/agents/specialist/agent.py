"""Specialist agent for Loom MVP."""
from typing import Any

from loguru import logger

from src.agents.base.identity import load_identity
from src.agents.base.memory import retrieve_context
from src.agents.base.reflection import self_reflect
from src.core.event_bus.producer import emit
from src.core.event_bus.schemas import EventType, TaskCompletedEvent, TaskStateTransitionEvent
from src.core.llm.client import complete
from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message, Tool
from src.core.task_store.operations import TaskStore


class SpecialistAgent:
    """Specialist agent - leaf executor with tools."""

    def __init__(self, agent_id: str):
        self.config = load_identity(agent_id)
        self.task_store = TaskStore()

    async def execute(
        self,
        task_id: str,
        task_description: str,
        workflow_state: str,
        success_condition: str,
    ) -> dict[str, Any]:
        """Execute task in workflow state.

        Args:
            task_id: Task ID
            task_description: Task description
            workflow_state: Current workflow state
            success_condition: Success criteria

        Returns:
            Execution result
        """
        logger.info(f"Specialist {self.config.agent_id} executing task {task_id}")
        logger.info(f"State: {workflow_state}, Success condition: {success_condition}")

        # Retrieve relevant context from memory
        context = await retrieve_context(
            agent_id=self.config.agent_id,
            query=task_description,
            memory_scope=self.config.memory_scope,
        )

        logger.debug(f"Retrieved context: {len(context)} items")

        # Build execution prompt
        system_prompt = f"""You are {self.config.name}, a specialist agent.

Current workflow state: {workflow_state}
Success condition: {success_condition}

You have access to these tools: {', '.join(self.config.permitted_tools)}

Execute the task and provide a clear output."""

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"Task: {task_description}"),
        ]

        if context:
            context_str = "\n\n".join(context)
            messages.append(Message(role="system", content=f"Relevant context:\n{context_str}"))

        logger.info(f"Executing with {len(messages)} messages, {len(self.config.permitted_tools)} tools available")

        # Execute with tools
        try:
            # Convert permitted_tools to Tool objects if available
            tools = None
            if self.config.permitted_tools:
                tools = [
                    Tool(
                        type="function",
                        function={
                            "name": tool_name,
                            "description": f"Execute {tool_name}",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    )
                    for tool_name in self.config.permitted_tools[:3]  # Limit to 3 for MVP
                ]

            response = await complete(
                role=ModelRole.REASONING,
                messages=messages,
                tools=tools if tools else None,
            )

            logger.info(f"Execution complete. Output length: {len(response.content) if response.content else 0}")
            logger.debug(f"Execution output preview: {response.content[:300] if response.content else 'None'}...")

            if response.tool_calls:
                logger.info(f"Tool calls made: {[tc['function']['name'] for tc in response.tool_calls]}")

            # Self-reflection
            logger.info("Running self-reflection...")
            reflection_passed = await self_reflect(
                output=response.content or "",
                task_description=task_description,
                success_condition=success_condition,
            )

            logger.info(f"Self-reflection result: approved={reflection_passed}")
            
            if not reflection_passed:
                logger.warning(f"Task {task_id} failed self-reflection")
                return {
                    "success": False,
                    "reason": "Failed self-reflection",
                    "output": response.content,
                }

            # Success - attach output as artifact
            await self.task_store.attach_artifact(
                task_id=task_id,
                artifact_type="specialist_output",
                reference_url=f"data:text/plain;base64,{response.content}",
                agent_id=self.config.agent_id,
            )

            # Emit completion event
            await emit(TaskCompletedEvent(
                idempotency_key=f"{task_id}:completed",
                sequence_number=1,
                task_id=task_id,
                event_type=EventType.TASK_COMPLETED,
                outcome="success",
                agent_id=self.config.agent_id,
            ))

            logger.info(f"Task {task_id} completed successfully by specialist")

            return {
                "success": True,
                "output": response.content,
                "tool_calls": response.tool_calls,
            }

        except Exception as e:
            logger.error(f"Execution failed for task {task_id}: {e}")
            return {
                "success": False,
                "reason": str(e),
            }
