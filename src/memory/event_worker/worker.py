"""Memory event worker for Loom MVP."""
import asyncio
from typing import Any

from loguru import logger

from src.core.event_bus.producer import event_bus
from src.core.event_bus.schemas import EventType
from src.core.task_store.operations import TaskStore
from src.memory.event_worker.processor import MemoryExtractionProcessor


class MemoryEventWorker:
    """Worker that processes events and extracts memories."""

    def __init__(self, task_store: TaskStore):
        self.task_store = task_store
        self.processor = MemoryExtractionProcessor(task_store)
        self._processed_ids: set[str] = set()
        self._running = False

    async def start(self) -> None:
        """Start the memory worker."""
        self._running = True
        logger.info("Memory event worker started")

        # Subscribe to events
        event_bus.subscribe(self._handle_event)

    async def stop(self) -> None:
        """Stop the memory worker."""
        self._running = False
        event_bus.unsubscribe(self._handle_event)
        logger.info("Memory event worker stopped")

    async def _handle_event(self, event: Any) -> None:
        """Handle incoming event."""
        if not self._running:
            return

        # Check idempotency
        event_id = str(event.event_id)
        if event_id in self._processed_ids:
            return

        self._processed_ids.add(event_id)

        # Keep set size manageable
        if len(self._processed_ids) > 10000:
            self._processed_ids = set(list(self._processed_ids)[-5000:])

        # Process based on event type
        if event.event_type == EventType.TASK_COMPLETED:
            await self._process_task_completed(event)
        elif event.event_type == EventType.TASK_STATE_TRANSITION:
            await self._process_state_transition(event)

    async def _process_task_completed(self, event: Any) -> None:
        """Process task completed event."""
        try:
            memories = await self.processor.process_task_completed(event.model_dump())
            logger.info(f"Extracted {len(memories)} memories from completed task")
        except Exception as e:
            logger.error(f"Failed to process task completion: {e}")

    async def _process_state_transition(self, event: Any) -> None:
        """Process state transition event."""
        try:
            memories = await self.processor.process_state_transition(event.model_dump())
            if memories:
                logger.info(f"Extracted {len(memories)} memories from state transition")
        except Exception as e:
            logger.error(f"Failed to process state transition: {e}")


# Global worker instance
_memory_worker: MemoryEventWorker | None = None


def get_memory_worker(task_store: TaskStore) -> MemoryEventWorker:
    """Get or create global memory worker."""
    global _memory_worker
    if _memory_worker is None:
        _memory_worker = MemoryEventWorker(task_store)
    return _memory_worker
