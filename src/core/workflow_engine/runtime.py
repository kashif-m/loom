"""Workflow runtime for Loom MVP using LangGraph."""
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from src.core.event_bus.producer import emit
from src.core.event_bus.schemas import (
    EventType,
    TaskBlockedEvent,
    TaskCompletedEvent,
    TaskStateTransitionEvent,
    WorkflowEscalatedEvent,
)
from src.core.llm.client import complete
from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message
from src.core.task_store.operations import TaskStore
from src.core.workflow_engine.schemas import WorkflowDefinition


class WorkflowRuntime:
    """Workflow runtime for executing workflows."""

    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

    def build_graph(self, workflow: WorkflowDefinition) -> StateGraph:
        """Build LangGraph state machine from workflow definition."""

        # Define state type
        class WorkflowState(dict):
            """Workflow execution state."""
            pass

        graph = StateGraph(WorkflowState)

        # Add nodes for each state
        for state in workflow.states:
            async def state_node(state_data: WorkflowState, state_name: str = state) -> WorkflowState:
                """Execute a workflow state."""
                task_id = state_data.get("task_id")
                agent_id = state_data.get("agent_id")

                logger.info(f"Executing state '{state_name}' for task {task_id}")

                # In real implementation, this would call the agent
                # For now, we just mark it as complete
                state_data["current_state"] = state_name
                state_data["state_complete"] = True

                return state_data

            graph.add_node(state, lambda x, s=state: state_node(x, s))

        # Add edges between states
        for i in range(len(workflow.states) - 1):
            current = workflow.states[i]
            next_state = workflow.states[i + 1]

            async def should_transition(state_data: WorkflowState) -> str:
                """Determine if we should transition to next state."""
                if state_data.get("state_complete"):
                    return next_state
                return END

            graph.add_conditional_edges(
                current,
                should_transition,
                {next_state: next_state, END: END}
            )

        # Set entry point
        graph.set_entry_point(workflow.states[0])

        return graph.compile()

    async def execute_state(
        self,
        task_id: str,
        workflow: WorkflowDefinition,
        state: str,
        agent_id: str,
    ) -> bool:
        """Execute a single workflow state.

        Returns True if state completed successfully, False otherwise.
        """
        logger.info(f"Executing state '{state}' for task {task_id}")

        # Get task
        task = await self.task_store.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        # Check success condition
        messages = [
            Message(
                role="system",
                content=f"You are evaluating if a task state is complete. "
                       f"Workflow: {workflow.id}, State: {state}\n"
                       f"Success condition: {workflow.success_condition}"
            ),
            Message(
                role="user",
                content=f"Task description: {task.description}\n\n"
                       f"Current state: {state}\n\n"
                       f"Has this state been successfully completed? "
                       f"Respond with ONLY 'yes' or 'no'."
            ),
        ]

        try:
            response = await complete(
                role=ModelRole.FAST,
                messages=messages,
                temperature=0.3,
            )

            is_complete = response.content and "yes" in response.content.lower()

            if is_complete:
                # Find next state
                current_idx = workflow.states.index(state)
                if current_idx < len(workflow.states) - 1:
                    next_state = workflow.states[current_idx + 1]

                    # Transition
                    await self.transition_state(
                        task_id=task_id,
                        from_state=state,
                        to_state=next_state,
                        agent_id=agent_id,
                    )
                else:
                    # Final state - complete task
                    await self.complete_task(task_id, agent_id)

                return True
            else:
                # Check escalation condition
                if task.retry_count >= 3:  # TODO: Get from config
                    await self.escalate_task(task_id, workflow.escalate_if, agent_id)
                else:
                    # Increment retry
                    await self.task_store.transition_state(
                        task_id=task_id,
                        to_state=state,
                        current_version=task.version,
                        agent_id=agent_id,
                        event_id=str(task.task_id),  # TODO: Generate proper event ID
                    )

                return False

        except Exception as e:
            logger.error(f"State execution failed: {e}")
            return False

    async def transition_state(
        self,
        task_id: str,
        from_state: str,
        to_state: str,
        agent_id: str,
    ) -> None:
        """Transition task to new state."""
        task = await self.task_store.get_task(task_id)
        if not task:
            return

        # Update task
        await self.task_store.transition_state(
            task_id=task_id,
            to_state=to_state,
            current_version=task.version,
            agent_id=agent_id,
            event_id=f"{task_id}:{from_state}:{to_state}",
        )

        # Emit event
        await emit(TaskStateTransitionEvent(
            idempotency_key=f"{task_id}:{from_state}:{to_state}",
            sequence_number=task.version,
            task_id=task_id,
            event_type=EventType.TASK_STATE_TRANSITION,
            from_state=from_state,
            to_state=to_state,
            agent_id=agent_id,
        ))

        logger.info(f"Task {task_id} transitioned: {from_state} -> {to_state}")

    async def complete_task(self, task_id: str, agent_id: str) -> None:
        """Mark task as complete."""
        task = await self.task_store.get_task(task_id)
        if not task:
            return

        await self.task_store.close_task(
            task_id=task_id,
            outcome="success",
            agent_id=agent_id,
        )

        # Emit event
        await emit(TaskCompletedEvent(
            idempotency_key=f"{task_id}:completed",
            sequence_number=task.version + 1,
            task_id=task_id,
            event_type=EventType.TASK_COMPLETED,
            outcome="success",
            agent_id=agent_id,
        ))

        logger.info(f"Task {task_id} completed")

    async def escalate_task(self, task_id: str, reason: str, agent_id: str) -> None:
        """Escalate task to human."""
        task = await self.task_store.get_task(task_id)
        if not task:
            return

        await self.task_store.escalate(
            task_id=task_id,
            reason=reason,
            agent_id=agent_id,
        )

        # Emit event
        await emit(WorkflowEscalatedEvent(
            idempotency_key=f"{task_id}:escalated",
            sequence_number=task.version + 1,
            task_id=task_id,
            event_type=EventType.WORKFLOW_ESCALATED,
            reason=reason,
            agent_id=agent_id,
        ))

        logger.info(f"Task {task_id} escalated: {reason}")

    async def block_task(self, task_id: str, description: str, agent_id: str) -> None:
        """Block task with a blocker."""
        task = await self.task_store.get_task(task_id)
        if not task:
            return

        await self.task_store.record_blocker(
            task_id=task_id,
            description=description,
            raised_by=agent_id,
        )

        # Emit event
        await emit(TaskBlockedEvent(
            idempotency_key=f"{task_id}:blocked",
            sequence_number=task.version,
            task_id=task_id,
            event_type=EventType.TASK_BLOCKED,
            blocker_description=description,
            agent_id=agent_id,
        ))

        logger.info(f"Task {task_id} blocked: {description}")
