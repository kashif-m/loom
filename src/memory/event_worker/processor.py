"""Memory extraction processor for Loom MVP using Instructor structured outputs."""
from typing import Any

from loguru import logger

from src.agents.base.identity import load_identity
from src.core.llm.client import complete_structured
from src.core.llm.models import ModelRole
from src.core.llm.schemas import MemoryExtractionResponse, Message
from src.core.task_store.operations import TaskStore
from src.memory.graphiti.client import get_graphiti_client
from src.memory.graphiti.schemas import MemoryNode, MemoryTier


class MemoryExtractionProcessor:
    """Extract and store memories from task events using Instructor."""

    def __init__(self, task_store: TaskStore):
        self.task_store = task_store
        self.graphiti = get_graphiti_client()

    async def process_task_completed(self, event: dict[str, Any]) -> list[MemoryNode]:
        """Process task.completed event and extract memories using Instructor.

        Args:
            event: Task completed event

        Returns:
            List of extracted memory nodes
        """
        task_id = event.get("task_id")
        agent_id = event.get("agent_id")

        # Get task details
        task = await self.task_store.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found for memory extraction")
            return []

        # Get task history
        history = await self.task_store.get_task_history(task_id)

        # Build extraction prompt
        history_text = "\n".join([
            f"- {h.from_state or 'start'} -> {h.to_state} by {h.agent_id}"
            for h in history[-10:]  # Last 10 transitions
        ])

        prompt = f"""Extract key facts and learnings from this completed task.

Task Description:
{task.description}

Workflow: {task.workflow_id}
Team: {task.team_id}
Outcome: {event.get('outcome', 'success')}

State Transitions:
{history_text}

Extract actionable facts, learnings, and any blockers encountered.
Focus on information that would help with similar tasks in the future.
"""

        messages = [
            Message(
                role="system",
                content="You extract structured memories from completed tasks. Be concise and actionable."
            ),
            Message(role="user", content=prompt),
        ]

        try:
            # Use Instructor for structured extraction
            extraction = await complete_structured(
                role=ModelRole.FAST,
                messages=messages,
                response_model=MemoryExtractionResponse,
                temperature=0.3,
                max_retries=2,
            )

            logger.info(
                f"Extracted {len(extraction.facts)} facts, "
                f"{len(extraction.entities)} entities from task {task_id}"
            )
            logger.debug(f"Summary: {extraction.summary[:150]}...")

            # Load agent config to determine tier
            agent_config = load_identity(agent_id)

            # Determine tier based on agent authority
            if agent_config.authority_level == "specialist":
                tier = MemoryTier.AGENTIC
            elif agent_config.authority_level == "generalist":
                tier = MemoryTier.TEAM
            else:  # kr
                tier = MemoryTier.ORG

            # Create memory nodes from facts
            memories = []

            for fact in extraction.facts:
                node = MemoryNode(
                    content=fact.content,
                    node_type="fact",
                    provenance={
                        "event_id": str(event.get("event_id")),
                        "task_id": task_id,
                    },
                    tier=tier,
                    agent_id=agent_id if tier == MemoryTier.AGENTIC else None,
                    team_id=task.team_id if tier in [MemoryTier.TEAM, MemoryTier.AGENTIC] else None,
                    org_id="default" if tier == MemoryTier.ORG else None,
                    importance=fact.importance,
                )

                try:
                    written = await self.graphiti.write_node(
                        node=node,
                        agent_id=agent_id,
                        authority_level=agent_config.authority_level,
                    )
                    memories.append(written)
                    logger.debug(f"Extracted memory: {written.content[:50]}...")
                except Exception as e:
                    logger.error(f"Failed to write memory: {e}")

            logger.info(f"Wrote {len(memories)} memories to Graphiti from task {task_id}")
            return memories

        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return []

    async def process_state_transition(self, event: dict[str, Any]) -> list[MemoryNode]:
        """Process state transition event using Instructor.

        For MVP, we only extract significant state transitions.
        Full extraction happens on task completion.
        """
        # Only extract from significant transitions (blocked, escalated)
        to_state = event.get("to_state")

        if to_state not in ["blocked", "escalated"]:
            return []

        # Extract learnings from difficult transitions
        task_id = event.get("task_id")
        agent_id = event.get("agent_id")

        task = await self.task_store.get_task(task_id)
        if not task:
            return []

        # Use Instructor to extract insight about the blocker
        prompt = f"""Task transitioned to {to_state} state.

Task: {task.description}
Workflow: {task.workflow_id}

Extract a brief insight about what caused this transition that would help prevent it in the future.
"""

        messages = [
            Message(role="system", content="Extract brief observations about task transitions."),
            Message(role="user", content=prompt),
        ]

        try:
            extraction = await complete_structured(
                role=ModelRole.FAST,
                messages=messages,
                response_model=MemoryExtractionResponse,
                temperature=0.3,
                max_retries=1,
            )

            # Use the summary as the observation
            content = extraction.summary or f"Task transitioned to {to_state} state"

            agent_config = load_identity(agent_id)

            if agent_config.authority_level == "specialist":
                tier = MemoryTier.AGENTIC
            elif agent_config.authority_level == "generalist":
                tier = MemoryTier.TEAM
            else:
                tier = MemoryTier.ORG

            node = MemoryNode(
                content=content,
                node_type="observation",
                provenance={
                    "event_id": str(event.get("event_id")),
                    "task_id": task_id,
                },
                tier=tier,
                agent_id=agent_id if tier == MemoryTier.AGENTIC else None,
                team_id=task.team_id if tier in [MemoryTier.TEAM, MemoryTier.AGENTIC] else None,
            )

            try:
                written = await self.graphiti.write_node(
                    node=node,
                    agent_id=agent_id,
                    authority_level=agent_config.authority_level,
                )
                logger.info(f"Wrote transition observation to Graphiti: {content[:50]}...")
                return [written]
            except Exception as e:
                logger.error(f"Failed to write transition memory: {e}")
                return []

        except Exception as e:
            logger.error(f"Transition extraction failed: {e}")
            return []
