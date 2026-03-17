-- Task Store Schema for Loom MVP

-- Main tasks table
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    workflow_version INTEGER,
    owner_agent_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    current_state TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    retry_count INTEGER DEFAULT 0,
    escalation_count INTEGER DEFAULT 0,
    sla_deadline TIMESTAMP,
    status TEXT CHECK(status IN ('open', 'blocked', 'escalated', 'closed')) DEFAULT 'open',
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);

-- Task history - all state transitions
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    transitioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Task artifacts - outputs and references
CREATE TABLE IF NOT EXISTS task_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    type TEXT NOT NULL,
    reference_url TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Task blockers - issues that stop progress
CREATE TABLE IF NOT EXISTS task_blockers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    description TEXT NOT NULL,
    raised_by TEXT NOT NULL,
    raised_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Raw event log - append only
CREATE TABLE IF NOT EXISTS raw_events (
    event_id TEXT PRIMARY KEY,
    stream TEXT NOT NULL,
    payload TEXT NOT NULL, -- JSON
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Human review queue - dead tasks
CREATE TABLE IF NOT EXISTS human_review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Task evaluations
CREATE TABLE IF NOT EXISTS task_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    completed_successfully BOOLEAN NOT NULL,
    rework_count INTEGER DEFAULT 0,
    false_escalation BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_team ON tasks(team_id);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_workflow ON tasks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_history_task ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_blockers_task ON task_blockers(task_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON task_artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_events_stream ON raw_events(stream);
