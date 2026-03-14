from __future__ import annotations

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class OrganizationRow(Base):
    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), default="My Organization")
    litellm_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    litellm_api_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    litellm_default_model: Mapped[str] = mapped_column(String(128), default="open-large")
    litellm_start_cmd: Mapped[str | None] = mapped_column(String(512), nullable=True)
    openai_api_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    openai_model: Mapped[str] = mapped_column(String(128), default="gpt-4.1-mini")
    opencode_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    opencode_cmd: Mapped[str] = mapped_column(String(128), default="opencode")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskRow(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    raw_request: Mapped[str] = mapped_column(Text)
    normalized_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_pack: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    current_step_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    linked_entities: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_refs: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowVersionRow(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    markdown: Mapped[str] = mapped_column(Text)
    compiled_ir: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)


class RegistryRow(Base):
    __tablename__ = "registry_rows"
    __table_args__ = (
        UniqueConstraint("registry_type", "key", name="uq_registry_type_key"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registry_type: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True)


class EventLogRow(Base):
    __tablename__ = "event_logs"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleRunRow(Base):
    __tablename__ = "schedule_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[str] = mapped_column(String(128), index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


def init_db(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(
        database_url,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    # Lightweight compatibility migration for existing local SQLite DBs.
    # New installs already get this column via `TaskRow`.
    if database_url.startswith("sqlite"):
        with engine.begin() as conn:
            org_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(organizations)")).fetchall()
            }
            if "litellm_start_cmd" not in org_columns:
                conn.execute(text("ALTER TABLE organizations ADD COLUMN litellm_start_cmd VARCHAR(512)"))
            columns = {
                row[1]  # PRAGMA table_info(tasks) -> (cid, name, type, notnull, dflt_value, pk)
                for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
            }
            if "organization_id" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN organization_id VARCHAR(64) DEFAULT 'default'"))
                conn.execute(text("UPDATE tasks SET organization_id='default' WHERE organization_id IS NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_organization_id ON tasks (organization_id)"))
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory
