from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite

from src.core.task_store.models import (
    HumanReviewQueue,
    RawEvent,
    Task,
    TaskArtifact,
    TaskBlocker,
    TaskEvaluation,
    TaskHistory,
    TaskStatus,
)
from src.exceptions import StaleTaskVersionError


class TaskStore:
    """Task store for managing tasks and related entities."""

    def __init__(self, db_path: str = "loom.db"):
        self.db_path = db_path

    @asynccontextmanager
    async def _get_db(self):
        """Get database connection as async context manager."""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()

    async def init_db(self) -> None:
        """Initialize database with schema."""
        async with self._get_db() as db:
            with open("infra/sqlite/migrations/001_task_store.sql") as f:
                await db.executescript(f.read())
            await db.commit()

    # Task operations

    async def create_task(
        self,
        workflow_id: str | None,
        workflow_version: int | None,
        owner_agent_id: str,
        team_id: str,
        description: str,
        sla_deadline: datetime | None = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            owner_agent_id=owner_agent_id,
            team_id=team_id,
            current_state="received",
            description=description,
            sla_deadline=sla_deadline,
        )

        async with self._get_db() as db:
            await db.execute(
                """
                INSERT INTO tasks (
                    task_id, workflow_id, workflow_version, owner_agent_id, team_id,
                    current_state, version, retry_count, escalation_count, sla_deadline,
                    status, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.workflow_id,
                    task.workflow_version,
                    task.owner_agent_id,
                    task.team_id,
                    task.current_state,
                    task.version,
                    task.retry_count,
                    task.escalation_count,
                    task.sla_deadline,
                    task.status.value,
                    task.description,
                    task.created_at,
                    task.updated_at,
                ),
            )
            await db.commit()

        return task

    async def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        async with self._get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = await cursor.fetchone()
            if row:
                return Task(**dict(row))
            return None

    async def transition_state(
        self,
        task_id: str,
        to_state: str,
        current_version: int,
        agent_id: str,
        event_id: str,
    ) -> Task:
        """Transition task to new state with optimistic locking."""
        async with self._get_db() as db:
            # Check current version
            cursor = await db.execute(
                "SELECT version FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = await cursor.fetchone()

            if not row:
                raise ValueError(f"Task {task_id} not found")

            if row["version"] != current_version:
                raise StaleTaskVersionError(
                    f"Version mismatch: expected {current_version}, got {row['version']}"
                )

            # Get current state for history
            cursor = await db.execute(
                "SELECT current_state FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            from_state = (await cursor.fetchone())["current_state"]

            # Update task
            new_version = current_version + 1
            now = datetime.now(timezone.utc)

            await db.execute(
                """
                UPDATE tasks
                SET current_state = ?, version = ?, updated_at = ?
                WHERE task_id = ? AND version = ?
                """,
                (to_state, new_version, now, task_id, current_version),
            )

            # Record history
            await db.execute(
                """
                INSERT INTO task_history (task_id, from_state, to_state, agent_id, event_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, from_state, to_state, agent_id, event_id),
            )

            await db.commit()

        return await self.get_task(task_id)

    async def record_blocker(
        self,
        task_id: str,
        description: str,
        raised_by: str,
    ) -> TaskBlocker:
        """Record a new blocker for a task."""
        blocker = TaskBlocker(
            task_id=task_id,
            description=description,
            raised_by=raised_by,
        )

        async with self._get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO task_blockers (task_id, description, raised_by)
                VALUES (?, ?, ?)
                """,
                (blocker.task_id, blocker.description, blocker.raised_by),
            )
            await db.commit()
            blocker.id = cursor.lastrowid

        return blocker

    async def resolve_blocker(
        self,
        task_id: str,
        blocker_id: int,
    ) -> TaskBlocker:
        """Resolve a blocker."""
        now = datetime.now(timezone.utc)

        async with self._get_db() as db:
            await db.execute(
                """
                UPDATE task_blockers
                SET resolved_at = ?
                WHERE id = ? AND task_id = ?
                """,
                (now, blocker_id, task_id),
            )
            await db.commit()

            cursor = await db.execute(
                "SELECT * FROM task_blockers WHERE id = ?",
                (blocker_id,)
            )
            row = await cursor.fetchone()
            return TaskBlocker(**dict(row))

    async def attach_artifact(
        self,
        task_id: str,
        artifact_type: str,
        reference_url: str,
        agent_id: str,
    ) -> TaskArtifact:
        """Attach an artifact to a task."""
        artifact = TaskArtifact(
            task_id=task_id,
            artifact_type=artifact_type,
            reference_url=reference_url,
            agent_id=agent_id,
        )

        async with self._get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO task_artifacts (task_id, type, reference_url, agent_id)
                VALUES (?, ?, ?, ?)
                """,
                (artifact.task_id, artifact.artifact_type, artifact.reference_url, artifact.agent_id),
            )
            await db.commit()
            artifact.id = cursor.lastrowid

        return artifact

    async def escalate(
        self,
        task_id: str,
        reason: str,
        agent_id: str,
    ) -> Task:
        """Escalate a task."""
        now = datetime.now(timezone.utc)

        async with self._get_db() as db:
            await db.execute(
                """
                UPDATE tasks
                SET escalation_count = escalation_count + 1,
                    status = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (TaskStatus.ESCALATED.value, now, task_id),
            )
            await db.commit()

        return await self.get_task(task_id)

    async def close_task(
        self,
        task_id: str,
        outcome: str,
        agent_id: str,
    ) -> Task:
        """Close a task."""
        now = datetime.now(timezone.utc)

        async with self._get_db() as db:
            await db.execute(
                """
                UPDATE tasks
                SET status = ?,
                    closed_at = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (TaskStatus.CLOSED.value, now, now, task_id),
            )
            await db.commit()

        return await self.get_task(task_id)

    # Query operations

    async def get_task_history(self, task_id: str) -> list[TaskHistory]:
        """Get task history."""
        async with self._get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM task_history WHERE task_id = ? ORDER BY transitioned_at DESC",
                (task_id,)
            )
            rows = await cursor.fetchall()
            return [TaskHistory(**dict(row)) for row in rows]

    async def get_task_blockers(self, task_id: str, active_only: bool = False) -> list[TaskBlocker]:
        """Get task blockers."""
        async with self._get_db() as db:
            if active_only:
                cursor = await db.execute(
                    "SELECT * FROM task_blockers WHERE task_id = ? AND resolved_at IS NULL",
                    (task_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM task_blockers WHERE task_id = ?",
                    (task_id,)
                )
            rows = await cursor.fetchall()
            return [TaskBlocker(**dict(row)) for row in rows]

    async def get_task_artifacts(self, task_id: str) -> list[TaskArtifact]:
        """Get task artifacts."""
        async with self._get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM task_artifacts WHERE task_id = ?",
                (task_id,)
            )
            rows = await cursor.fetchall()
            return [TaskArtifact(**dict(row)) for row in rows]

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        team_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filters."""
        async with self._get_db() as db:
            query = "SELECT * FROM tasks WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if team_id:
                query += " AND team_id = ?"
                params.append(team_id)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [Task(**dict(row)) for row in rows]

    async def add_to_human_review(self, task_id: str, reason: str) -> HumanReviewQueue:
        """Add task to human review queue."""
        entry = HumanReviewQueue(task_id=task_id, reason=reason)

        async with self._get_db() as db:
            cursor = await db.execute(
                "INSERT INTO human_review_queue (task_id, reason) VALUES (?, ?)",
                (entry.task_id, entry.reason),
            )
            await db.commit()
            entry.id = cursor.lastrowid

        return entry

    async def record_evaluation(self, evaluation: TaskEvaluation) -> TaskEvaluation:
        """Record task evaluation."""
        async with self._get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO task_evaluations
                (task_id, completed_successfully, rework_count, false_escalation)
                VALUES (?, ?, ?, ?)
                """,
                (
                    evaluation.task_id,
                    evaluation.completed_successfully,
                    evaluation.rework_count,
                    evaluation.false_escalation,
                ),
            )
            await db.commit()
            evaluation.id = cursor.lastrowid

        return evaluation

    async def log_event(self, event: RawEvent) -> None:
        """Log event to raw event log."""
        import json

        async with self._get_db() as db:
            await db.execute(
                "INSERT INTO raw_events (event_id, stream, payload) VALUES (?, ?, ?)",
                (event.event_id, event.stream, json.dumps(event.payload)),
            )
            await db.commit()
