"""PydanticAI agent definitions for Loom MVP.

This module provides a simplified agent interface.
For now, we use the existing specialist agent implementation
since PydanticAI's LiteLLM integration requires additional setup.
"""
from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.agents.base.identity import AgentConfig, load_identity
from src.agents.base.reflection import self_reflect
from src.agents.base.memory import retrieve_context
from src.core.llm.client import complete
from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message
from src.core.task_store.operations import TaskStore


@dataclass
class AgentContext:
    """Context passed to agent execution."""
    agent_config: AgentConfig
    task_store: TaskStore
    task_id: str
    workflow_state: str


class TaskExecutionAgent:
    """Task execution agent using standard LLM client.
    
    This is a bridge implementation. The full PydanticAI integration
    would require proper model configuration. For now, we use the
    existing reliable implementation with Instructor for structured outputs.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.config = load_identity(agent_id)
        self.task_store = TaskStore()

    async def run(
        self,
        task_id: str,
        task_description: str,
        workflow_state: str,
        success_condition: str,
    ) -> dict[str, Any]:
        """Execute task using LLM with tool calling simulation.

        Args:
            task_id: Task ID
            task_description: Task description
            workflow_state: Current workflow state
            success_condition: Success criteria

        Returns:
            Execution result
        """
        logger.info(f"TaskExecutionAgent {self.agent_id} running task {task_id}")

        # Retrieve context
        context = await retrieve_context(
            agent_id=self.agent_id,
            query=task_description,
            memory_scope=self.config.memory_scope,
        )

        # Build system prompt
        system_prompt = f"""You are {self.config.name}, a specialist agent.

Current workflow state: {workflow_state}
Success condition: {success_condition}

Available tools: {', '.join(self.config.permitted_tools)}

You can use these tools by describing what you want to do:
- file_read: Read a file (specify the path)
- file_write: Write to a file (specify path and content)
- code_search: Search the codebase (specify query)
- task_query: Query task information
- git_status: Check git status
- notify: Send a notification

Execute the task and provide a clear output of what was accomplished."""

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"Task: {task_description}"),
        ]

        if context:
            messages.append(Message(
                role="system", 
                content=f"Relevant context:\n{chr(10).join(context[:5])}"
            ))

        try:
            # Execute with LLM
            response = await complete(
                role=ModelRole.REASONING,
                messages=messages,
            )

            output = response

            logger.info(f"Execution complete. Output length: {len(output) if output else 0}")

            # Self-reflection
            reflection = await self_reflect(
                output=output or "",
                task_description=task_description,
                success_condition=success_condition,
            )

            if not reflection:
                return {
                    "success": False,
                    "reason": "Self-reflection failed",
                    "output": output,
                }

            return {
                "success": reflection.get("approved", False),
                "output": output,
                "reason": reflection.get("reasoning") if not reflection.get("approved") else None,
                "agent_id": self.agent_id,
            }

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "success": False,
                "reason": str(e),
                "agent_id": self.agent_id,
            }


# Backwards compatibility alias
SpecialistAgent = TaskExecutionAgent
