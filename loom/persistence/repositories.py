from __future__ import annotations

from typing import Any

from sqlalchemy import and_, desc, select

from loom.models import Organization, Task, TaskEvent, TaskStatus
from loom.persistence.db import EventLogRow, OrganizationRow, RegistryRow, ScheduleRunRow, TaskRow, WorkflowVersionRow


class TaskRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def create(self, task: Task) -> Task:
        with self._session_factory() as session:
            row = TaskRow(
                task_id=task.task_id,
                organization_id=task.organization_id,
                raw_request=task.raw_request,
                normalized_request=task.normalized_request,
                workflow_id=task.workflow_id,
                workflow_version=task.workflow_version,
                domain_pack=task.domain_pack,
                status=task.current_status.value,
                current_step_id=task.current_step_id,
                linked_entities=task.linked_entities,
                execution_refs=task.execution_refs,
                result_summary=task.result_summary,
            )
            session.add(row)
            session.commit()
        return task

    def get(self, task_id: str) -> Task | None:
        with self._session_factory() as session:
            row = session.get(TaskRow, task_id)
            if not row:
                return None
            return Task(
                task_id=row.task_id,
                organization_id=row.organization_id,
                raw_request=row.raw_request,
                normalized_request=row.normalized_request,
                workflow_id=row.workflow_id,
                workflow_version=row.workflow_version,
                domain_pack=row.domain_pack,
                current_status=TaskStatus(row.status),
                current_step_id=row.current_step_id,
                linked_entities=row.linked_entities,
                execution_refs=row.execution_refs,
                result_summary=row.result_summary,
            )

    def update(self, task: Task) -> Task:
        with self._session_factory() as session:
            row = session.get(TaskRow, task.task_id)
            if not row:
                raise KeyError(f"task not found: {task.task_id}")
            row.normalized_request = task.normalized_request
            row.organization_id = task.organization_id
            row.workflow_id = task.workflow_id
            row.workflow_version = task.workflow_version
            row.domain_pack = task.domain_pack
            row.status = task.current_status.value
            row.current_step_id = task.current_step_id
            row.linked_entities = task.linked_entities
            row.execution_refs = task.execution_refs
            row.result_summary = task.result_summary
            session.commit()
        return task

    def list(self, organization_id: str | None = None) -> list[Task]:
        with self._session_factory() as session:
            stmt = select(TaskRow)
            if organization_id:
                stmt = stmt.where(TaskRow.organization_id == organization_id)
            rows = session.execute(stmt.order_by(desc(TaskRow.created_at))).scalars().all()
            return [
                Task(
                    task_id=row.task_id,
                    organization_id=row.organization_id,
                    raw_request=row.raw_request,
                    normalized_request=row.normalized_request,
                    workflow_id=row.workflow_id,
                    workflow_version=row.workflow_version,
                    domain_pack=row.domain_pack,
                    current_status=TaskStatus(row.status),
                    current_step_id=row.current_step_id,
                    linked_entities=row.linked_entities,
                    execution_refs=row.execution_refs,
                    result_summary=row.result_summary,
                )
                for row in rows
            ]


class WorkflowRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def create_version(
        self,
        workflow_id: str,
        version: int,
        metadata: dict[str, Any],
        markdown: str,
        status: str = "draft",
        compiled_ir: dict[str, Any] | None = None,
    ) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(WorkflowVersionRow).where(
                    and_(WorkflowVersionRow.workflow_id == workflow_id, WorkflowVersionRow.version == version)
                )
            ).scalar_one_or_none()
            if existing:
                existing.metadata_json = metadata
                existing.markdown = markdown
                existing.compiled_ir = compiled_ir
                existing.status = status
            else:
                row = WorkflowVersionRow(
                    workflow_id=workflow_id,
                    version=version,
                    metadata_json=metadata,
                    markdown=markdown,
                    compiled_ir=compiled_ir,
                    status=status,
                )
                session.add(row)
            session.commit()

    def update_version(
        self,
        workflow_id: str,
        version: int,
        *,
        metadata: dict[str, Any] | None = None,
        markdown: str | None = None,
        compiled_ir: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            stmt = select(WorkflowVersionRow).where(
                and_(WorkflowVersionRow.workflow_id == workflow_id, WorkflowVersionRow.version == version)
            )
            row = session.execute(stmt).scalars().first()
            if not row:
                raise KeyError(f"workflow version not found: {workflow_id}:{version}")
            if metadata is not None:
                row.metadata_json = metadata
            if markdown is not None:
                row.markdown = markdown
            if compiled_ir is not None:
                row.compiled_ir = compiled_ir
            if status is not None:
                row.status = status
            session.commit()

    def get_version(self, workflow_id: str, version: int) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = select(WorkflowVersionRow).where(
                and_(WorkflowVersionRow.workflow_id == workflow_id, WorkflowVersionRow.version == version)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if not row:
                return None
            return {
                "workflow_id": row.workflow_id,
                "version": row.version,
                "metadata": row.metadata_json,
                "markdown": row.markdown,
                "compiled_ir": row.compiled_ir,
                "status": row.status,
            }

    def list_versions(self, workflow_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.execute(
                select(WorkflowVersionRow)
                .where(WorkflowVersionRow.workflow_id == workflow_id)
                .order_by(desc(WorkflowVersionRow.version))
            ).scalars().all()
            return [
                {
                    "workflow_id": row.workflow_id,
                    "version": row.version,
                    "metadata": row.metadata_json,
                    "markdown": row.markdown,
                    "compiled_ir": row.compiled_ir,
                    "status": row.status,
                }
                for row in rows
            ]

    def get_active_version(self, workflow_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = (
                select(WorkflowVersionRow)
                .where(
                    and_(
                        WorkflowVersionRow.workflow_id == workflow_id,
                        WorkflowVersionRow.status == "active",
                    )
                )
                .order_by(desc(WorkflowVersionRow.version))
            )
            row = session.execute(stmt).scalars().first()
            if not row:
                return None
            return {
                "workflow_id": row.workflow_id,
                "version": row.version,
                "metadata": row.metadata_json,
                "markdown": row.markdown,
                "compiled_ir": row.compiled_ir,
                "status": row.status,
            }

    def list_active(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.execute(select(WorkflowVersionRow).where(WorkflowVersionRow.status == "active")).scalars().all()
            return [
                {
                    "workflow_id": row.workflow_id,
                    "version": row.version,
                    "metadata": row.metadata_json,
                    "markdown": row.markdown,
                    "compiled_ir": row.compiled_ir,
                    "status": row.status,
                }
                for row in rows
            ]

    def list_all(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.execute(
                select(WorkflowVersionRow).order_by(WorkflowVersionRow.workflow_id, desc(WorkflowVersionRow.version))
            ).scalars().all()
            return [
                {
                    "workflow_id": row.workflow_id,
                    "version": row.version,
                    "metadata": row.metadata_json,
                    "markdown": row.markdown,
                    "compiled_ir": row.compiled_ir,
                    "status": row.status,
                }
                for row in rows
            ]


class GenericRegistryRepository:
    def __init__(self, session_factory, registry_type: str):
        self._session_factory = session_factory
        self.registry_type = registry_type

    def upsert(self, key: str, data: dict[str, Any], status: str = "active", version: int = 1) -> None:
        with self._session_factory() as session:
            stmt = select(RegistryRow).where(
                and_(RegistryRow.registry_type == self.registry_type, RegistryRow.key == key)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row:
                row.data = data
                row.status = status
                row.version = version
            else:
                session.add(
                    RegistryRow(
                        registry_type=self.registry_type,
                        key=key,
                        data=data,
                        status=status,
                        version=version,
                    )
                )
            session.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = select(RegistryRow).where(
                and_(RegistryRow.registry_type == self.registry_type, RegistryRow.key == key)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if not row:
                return None
            return {"key": row.key, "data": row.data, "status": row.status, "version": row.version}

    def delete(self, key: str) -> None:
        with self._session_factory() as session:
            stmt = select(RegistryRow).where(
                and_(RegistryRow.registry_type == self.registry_type, RegistryRow.key == key)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row:
                session.delete(row)
            session.commit()

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = select(RegistryRow).where(RegistryRow.registry_type == self.registry_type)
            if status:
                stmt = stmt.where(RegistryRow.status == status)
            rows = session.execute(stmt).scalars().all()
            return [{"key": row.key, "data": row.data, "status": row.status, "version": row.version} for row in rows]


class EventRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def append(self, event: TaskEvent) -> TaskEvent:
        with self._session_factory() as session:
            session.add(
                EventLogRow(
                    event_id=event.event_id,
                    task_id=event.task_id,
                    event_type=event.event_type,
                    payload=event.payload,
                )
            )
            session.commit()
        return event

    def list_for_task(self, task_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.execute(
                select(EventLogRow)
                .where(EventLogRow.task_id == task_id)
                .order_by(EventLogRow.created_at)
            ).scalars().all()
            return [
                {
                    "event_id": row.event_id,
                    "task_id": row.task_id,
                    "event_type": row.event_type,
                    "payload": row.payload,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]

    def list(
        self,
        *,
        task_id: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = select(EventLogRow)
            if task_id:
                stmt = stmt.where(EventLogRow.task_id == task_id)
            if event_type:
                stmt = stmt.where(EventLogRow.event_type == event_type)
            rows = session.execute(
                stmt.order_by(desc(EventLogRow.created_at)).offset(offset).limit(limit)
            ).scalars().all()
            return [
                {
                    "event_id": row.event_id,
                    "task_id": row.task_id,
                    "event_type": row.event_type,
                    "payload": row.payload,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]


class ScheduleRunRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def create(self, schedule_id: str, success: bool, payload: dict[str, Any]) -> None:
        with self._session_factory() as session:
            session.add(ScheduleRunRow(schedule_id=schedule_id, success=success, payload=payload))
            session.commit()


class OrganizationRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def get(self, org_id: str = "default") -> Organization | None:
        with self._session_factory() as session:
            row = session.get(OrganizationRow, org_id)
            if not row:
                return None
            return Organization(
                org_id=row.org_id,
                name=row.name,
                litellm_base_url=row.litellm_base_url,
                litellm_api_key=row.litellm_api_key,
                litellm_default_model=row.litellm_default_model,
                litellm_start_cmd=row.litellm_start_cmd,
                openai_api_key=row.openai_api_key,
                openai_model=row.openai_model,
                opencode_enabled=row.opencode_enabled,
                opencode_cmd=row.opencode_cmd,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def upsert(self, org: Organization) -> Organization:
        with self._session_factory() as session:
            row = session.get(OrganizationRow, org.org_id)
            if row:
                row.name = org.name
                row.litellm_base_url = org.litellm_base_url
                row.litellm_api_key = org.litellm_api_key
                row.litellm_default_model = org.litellm_default_model
                row.litellm_start_cmd = org.litellm_start_cmd
                row.openai_api_key = org.openai_api_key
                row.openai_model = org.openai_model
                row.opencode_enabled = org.opencode_enabled
                row.opencode_cmd = org.opencode_cmd
            else:
                session.add(
                    OrganizationRow(
                        org_id=org.org_id,
                        name=org.name,
                        litellm_base_url=org.litellm_base_url,
                        litellm_api_key=org.litellm_api_key,
                        litellm_default_model=org.litellm_default_model,
                        litellm_start_cmd=org.litellm_start_cmd,
                        openai_api_key=org.openai_api_key,
                        openai_model=org.openai_model,
                        opencode_enabled=org.opencode_enabled,
                        opencode_cmd=org.opencode_cmd,
                    )
                )
            session.commit()
        return org

    def get_or_create(self, org_id: str = "default") -> Organization:
        org = self.get(org_id)
        if org:
            return org
        return self.upsert(Organization(org_id=org_id, name="My Organization"))

    def list(self) -> list[Organization]:
        with self._session_factory() as session:
            rows = session.execute(select(OrganizationRow).order_by(OrganizationRow.org_id)).scalars().all()
            return [
                Organization(
                    org_id=row.org_id,
                    name=row.name,
                    litellm_base_url=row.litellm_base_url,
                    litellm_api_key=row.litellm_api_key,
                    litellm_default_model=row.litellm_default_model,
                    litellm_start_cmd=row.litellm_start_cmd,
                    openai_api_key=row.openai_api_key,
                    openai_model=row.openai_model,
                    opencode_enabled=row.opencode_enabled,
                    opencode_cmd=row.opencode_cmd,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]


class Repositories:
    def __init__(self, session_factory):
        self.organization = OrganizationRepository(session_factory)
        self.tasks = TaskRepository(session_factory)
        self.workflows = WorkflowRepository(session_factory)
        self.roles = GenericRegistryRepository(session_factory, "roles")
        self.capabilities = GenericRegistryRepository(session_factory, "capabilities")
        self.prompts = GenericRegistryRepository(session_factory, "prompts")
        self.policies = GenericRegistryRepository(session_factory, "policies")
        self.model_providers = GenericRegistryRepository(session_factory, "model_providers")
        self.models = GenericRegistryRepository(session_factory, "models")
        self.service_models = GenericRegistryRepository(session_factory, "service_models")
        self.domain_packs = GenericRegistryRepository(session_factory, "domain_packs")
        self.schedules = GenericRegistryRepository(session_factory, "schedules")
        self.participants = GenericRegistryRepository(session_factory, "participants")
        self.memory = GenericRegistryRepository(session_factory, "memory")
        self.memory_groups = GenericRegistryRepository(session_factory, "memory_groups")
        self.memory_memberships = GenericRegistryRepository(session_factory, "memory_memberships")
        self.memory_edges = GenericRegistryRepository(session_factory, "memory_edges")
        self.state_partitions = GenericRegistryRepository(session_factory, "state_partitions")
        self.packages = GenericRegistryRepository(session_factory, "packages")
        self.grounding_references = GenericRegistryRepository(session_factory, "grounding_references")
        self.pr_contexts = GenericRegistryRepository(session_factory, "pr_contexts")
        self.audit_results = GenericRegistryRepository(session_factory, "audit_results")
        self.repo_target_mappings = GenericRegistryRepository(session_factory, "repo_target_mappings")
        self.integration_bindings = GenericRegistryRepository(session_factory, "integration_bindings")
        self.organization_runtimes = GenericRegistryRepository(session_factory, "organization_runtimes")
        self.designer_drafts = GenericRegistryRepository(session_factory, "designer_drafts")
        self.incidents = GenericRegistryRepository(session_factory, "incidents")
        self.events = EventRepository(session_factory)
        self.schedule_runs = ScheduleRunRepository(session_factory)
