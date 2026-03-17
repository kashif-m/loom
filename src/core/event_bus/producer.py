"""Event bus producer for Loom MVP."""
import asyncio
import json
from collections.abc import Callable
from typing import Any

import aiosqlite
from loguru import logger

from src.core.event_bus.schemas import BaseEvent


class EventBus:
    """In-memory event bus with SQLite persistence for idempotency."""

    def __init__(self, db_path: str = "loom.db"):
        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._handlers: list[Callable] = []
        self._processed_ids: set[str] = set()
        self._db_path = db_path
        self._loaded_from_db = False

    async def _load_processed_ids(self) -> None:
        """Load processed event IDs from database on startup."""
        if self._loaded_from_db:
            return

        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                # Load IDs from last 24 hours (configurable)
                async with db.execute(
                    """
                    SELECT DISTINCT event_id FROM raw_events 
                    WHERE received_at > datetime('now', '-1 day')
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        self._processed_ids.add(row[0])
            
            self._loaded_from_db = True
            logger.info(f"Loaded {len(self._processed_ids)} processed event IDs from database")
        except Exception as e:
            logger.warning(f"Could not load processed IDs from DB: {e}")
            self._loaded_from_db = True  # Don't retry

    async def _persist_event(self, event: BaseEvent) -> None:
        """Persist event to raw_events table for audit trail."""
        try:
            import uuid
            # Convert event to dict and handle UUID serialization
            event_dict = event.model_dump()
            # Convert all UUIDs to strings
            def convert_uuids(obj):
                if isinstance(obj, uuid.UUID):
                    return str(obj)
                elif isinstance(obj, dict):
                    return {k: convert_uuids(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_uuids(item) for item in obj]
                return obj
            
            event_dict = convert_uuids(event_dict)
            
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO raw_events (event_id, stream, payload)
                    VALUES (?, ?, ?)
                    """,
                    (str(event.event_id), event.event_type, json.dumps(event_dict)),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to persist event {event.event_id}: {e}")

    async def emit(self, event: BaseEvent) -> None:
        """Emit event to the bus with idempotency check."""
        # Load from DB on first emit
        if not self._loaded_from_db:
            await self._load_processed_ids()

        # Check idempotency (memory + DB)
        if event.idempotency_key in self._processed_ids:
            logger.debug(f"Skipping duplicate event: {event.idempotency_key}")
            return

        # Also check DB for this specific event_id
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM raw_events WHERE event_id = ?",
                    (str(event.event_id),),
                ) as cursor:
                    if await cursor.fetchone():
                        logger.debug(f"Skipping event already in DB: {event.event_id}")
                        self._processed_ids.add(event.idempotency_key)
                        return
        except Exception:
            pass  # Continue even if DB check fails

        # Add to processed set
        self._processed_ids.add(event.idempotency_key)

        # Keep set size manageable (keep last 10000)
        if len(self._processed_ids) > 10000:
            self._processed_ids = set(list(self._processed_ids)[-5000:])

        # Persist to DB for audit trail and replay safety
        await self._persist_event(event)

        # Add to queue
        await self._queue.put(event)
        logger.info(
            f"Event emitted: {event.event_type} for task {event.task_id}"
        )

        # Notify handlers
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Handler failed for event {event.event_id}: {e}")

    def subscribe(self, handler: Callable) -> None:
        """Subscribe to events."""
        self._handlers.append(handler)

    def unsubscribe(self, handler: Callable) -> None:
        """Unsubscribe from events."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def get_event(self) -> BaseEvent:
        """Get next event from queue."""
        return await self._queue.get()

    async def replay_events(
        self, 
        stream: str | None = None, 
        since: str | None = None,
handler: Callable | None = None,
    ) -> int:
        """Replay events from raw_events table.
        
        Args:
            stream: Filter by event type/stream
            since: ISO timestamp to replay from
            handler: Optional handler to process events (default: subscribed handlers)
            
        Returns:
            Number of events replayed
        """
        count = 0
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                
                query = "SELECT * FROM raw_events WHERE 1=1"
                params = []
                
                if stream:
                    query += " AND stream = ?"
                    params.append(stream)
                if since:
                    query += " AND received_at > ?"
                    params.append(since)
                
                query += " ORDER BY received_at ASC"
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    for row in rows:
                        # Skip if already processed
                        event_id = row['event_id']
                        if event_id in self._processed_ids:
                            continue
                        
                        # Parse payload and reconstruct event
                        try:
                            payload = json.loads(row['payload'])
                            # Note: Would need event type mapping here
                            # For now just count
                            count += 1
                            
                            # Process with handler
                            target_handler = handler or self._handlers
                            if callable(target_handler):
                                await target_handler(payload)
                            else:
                                for h in target_handler:
                                    await h(payload)
                            
                            self._processed_ids.add(event_id)
                        except Exception as e:
                            logger.error(f"Failed to replay event {event_id}: {e}")
                            
            logger.info(f"Replayed {count} events")
            return count
            
        except Exception as e:
            logger.error(f"Event replay failed: {e}")
            return 0


# Global event bus instance
event_bus = EventBus()


async def emit(event: BaseEvent) -> None:
    """Emit event to the global event bus."""
    await event_bus.emit(event)
