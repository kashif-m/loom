"""Events routes."""
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from src.api.state import app_state
from src.core.event_bus.producer import event_bus
from src.core.event_bus.schemas import EventType

router = APIRouter()


# Event type to human-readable mapping
EVENT_LABELS = {
    EventType.TASK_CREATED: "New task submitted",
    EventType.TASK_ASSIGNED: "Task assigned",
    EventType.TASK_STATE_TRANSITION: "Progress update",
    EventType.TASK_BLOCKED: "Task stuck",
    EventType.TASK_COMPLETED: "Task completed",
    EventType.WORKFLOW_ESCALATED: "Needs your input",
    EventType.AGENT_TOOL_CALL: "Tool used",
}


def format_event(event) -> dict:
    """Format event for SSE."""
    label = EVENT_LABELS.get(event.event_type, event.event_type.value)

    return {
        "id": str(event.event_id),
        "event": "task_event",
        "data": json.dumps({
            "timestamp": datetime.now().isoformat(),
            "type": event.event_type.value,
            "label": label,
            "task_id": event.task_id,
            "agent_id": getattr(event, "agent_id", None),
            "details": event.model_dump(exclude={"event_id", "event_type", "task_id"}),
        }),
    }


@router.get("/events/stream")
async def events_stream():
    """SSE endpoint for real-time events."""

    async def event_generator():
        """Generate events."""
        # Send initial connection event
        yield {
            "event": "connected",
            "data": json.dumps({"message": "Connected to event stream"}),
        }

        # Subscribe to event bus
        events_queue = asyncio.Queue()

        async def handler(event):
            """Event handler."""
            # Filter out memory.write events (too noisy)
            if event.event_type != EventType.MEMORY_WRITE:
                await events_queue.put(event)

        event_bus.subscribe(handler)

        try:
            while True:
                # Wait for event with timeout (keepalive)
                try:
                    event = await asyncio.wait_for(
                        events_queue.get(),
                        timeout=15.0,
                    )
                    yield format_event(event)
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "keepalive",
                        "data": json.dumps({"timestamp": datetime.now().isoformat()}),
                    }
        finally:
            event_bus.unsubscribe(handler)

    return EventSourceResponse(event_generator())
