# UI_SPEC.md

## Philosophy

Minimal, functional, fast to ship. No charts, no animations, no complex state. The UI exists to let humans keep the system running — submit work, see what's happening, respond when the system gets stuck, and approve workflow changes. Every screen serves one of these four jobs.

Non-technical users and external stakeholders are primary consumers. Every screen must be readable without understanding the system internals. Avoid jargon: "escalation" → "needs your input", "state transition" → "progress update", "agentic memory" → "agent notes".

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js 14 (App Router) | File-based routing, server components, fast to scaffold |
| Styling | Tailwind CSS | Utility-first, no design system overhead |
| Data fetching | React Query (TanStack Query) | Polling, cache, loading states out of the box |
| Real-time | Server-Sent Events (SSE) | Simpler than WebSockets, sufficient for activity feed |
| Forms | React Hook Form + Zod | Lightweight validation |
| Icons | Lucide React | Clean, consistent |
| State | React Query only — no Redux, no Zustand | Overkill for this scope |
| API | Existing FastAPI backend | Add SSE endpoint + any missing REST routes |

---

## Pages (6 total)

### 1. Dashboard — `/`
**Purpose:** At-a-glance view of system health and pending actions.
**Primary users:** Everyone.

**Content:**
- Pending escalations banner (if any) — prominent, dismissible only by resolving
- Task summary counts: Open / Blocked / Completed today
- Recent tasks table (last 20): task ID, description snippet, status badge, current state, last updated
- Link to submit new task

**Behaviour:**
- Polls every 30 seconds
- Escalation banner is sticky — does not scroll away
- Status badges: `Open` (blue), `Blocked` (amber), `Escalated` (red), `Closed` (green)
- Clicking any task row → Task Detail page

**Non-technical language:**
- "Escalated" → show as "Needs your input" with red badge
- "current_state" → show human-readable state name from workflow definition

---

### 2. Submit Task — `/tasks/new`
**Purpose:** Human submits a new task to the system.
**Primary users:** Non-technical team members, external stakeholders.

**Content:**
- Single textarea: "Describe what needs to be done"
- Optional: priority hint (Low / Normal / Urgent) — stored as metadata, not used by V1 routing
- Submit button
- After submit: redirect to Task Detail page for the created task

**Behaviour:**
- No workflow selection — the system matches the workflow automatically
- Show a loading state after submit ("Routing your task...")
- On API error: show inline error, do not redirect

**Form validation:**
- Description: required, minimum 20 characters, maximum 2000 characters

---

### 3. Task List — `/tasks`
**Purpose:** Full filterable list of all tasks.
**Primary users:** Technical users, operators.

**Content:**
- Filter bar: Status (all / open / blocked / escalated / closed), Team, Date range
- Table columns: Task ID, Description (truncated), Team, Assigned to, Current state, Status, Created, Last updated
- Pagination (20 per page)

**Behaviour:**
- Filter state persisted in URL query params
- Clicking row → Task Detail
- "Needs your input" tasks sorted to top regardless of filter

---

### 4. Task Detail — `/tasks/[task_id]`
**Purpose:** Full task context — what happened, where it is, what's needed.
**Primary users:** Everyone.

**Content (top to bottom):**

**Header section:**
- Task ID + description
- Status badge + current state
- Assigned team + agent
- Created / updated timestamps
- SLA deadline (if set) — shows "Due in Xh" or "Overdue by Xh" in red

**Escalation panel (shown only when status = escalated):**
- Amber/red banner: "This task needs your input"
- Escalation reason (from task_blockers table)
- Context: what the agent tried, what failed
- Response textarea: "Provide additional details or instructions"
- Two buttons: "Send response" and "Reassign to different team"
- This panel is the most important UI element in the entire system

**Progress timeline:**
- Vertical timeline of all state transitions (from task_history)
- Each entry: state name, agent that completed it, timestamp, duration
- Non-technical labels: show workflow state display names, not raw state strings

**Artifacts:**
- List of outputs attached to the task (links only)
- Type icon (code, document, URL) + reference link + uploaded by + timestamp

**Blockers:**
- List of blockers: description, raised by, raised at, resolved at (or "Active")

**Technical detail (collapsed by default):**
- Raw task_id, workflow_id, workflow_version
- Retry count, escalation count
- Full JSON of latest task record
- Visible when expanded — useful for operators, hidden by default for others

---

### 5. Agent Activity Feed — `/activity`
**Purpose:** Live view of what agents are doing right now.
**Primary users:** Technical users, operators.

**Content:**
- Live event stream (SSE) from event bus
- Each event rendered as a feed item:
  - Timestamp
  - Agent name + role badge
  - Human-readable description of the event
  - Task ID (linked to Task Detail)
- Filter: by event type, by agent, by team
- Max 200 items in view — older items drop off

**Event → human-readable labels:**
```
task.created          → "New task submitted: {description snippet}"
task.assigned         → "{agent} picked up task {task_id}"
task.state_transition → "{agent} completed '{from_state}' → moved to '{to_state}'"
task.blocked          → "{agent} hit a blocker on task {task_id}: {description}"
task.completed        → "Task {task_id} completed successfully"
workflow.escalated    → "Task {task_id} escalated — needs human input"
agent.tool_call       → "{agent} used {tool_name} on task {task_id}"
```

**Behaviour:**
- SSE connection with auto-reconnect on disconnect
- New events appear at top (newest first)
- "Pause feed" toggle — freezes the view without disconnecting
- Each feed item links to the relevant task

**Backend requirement:**
- New FastAPI SSE endpoint: `GET /events/stream`
- Reads from Redis Streams, converts to SSE format
- Filters out `memory.write` events (too noisy for the UI)

---

### 6. Workflow Definitions — `/workflows`
**Purpose:** View, approve, and manage workflow files.
**Primary users:** Technical users, operators.

**This is not a workflow editor.** Workflows are edited as markdown files in the repo. This page is for visibility and approval gating — not authoring.

**Content:**

**Workflow list view (`/workflows`):**
- Table: workflow ID, name, level (org/team/agentic), version, status (active/draft/deprecated), last modified
- Filter by level, status
- Clicking row → Workflow Detail

**Workflow detail view (`/workflows/[workflow_id]`):**
- Workflow metadata: id, version, level, status, trigger, tags
- State list: ordered states with descriptions
- Success condition + escalation conditions
- Raw markdown (read-only, syntax highlighted)
- If status = `draft`: "Approve and activate" button — changes status to `active` in the workflow registry
- If status = `active`: "Deprecate" button — changes status to `deprecated`
- Version history: list of prior versions (v1, v2...) with link to each

**Approval flow:**
- New workflow files start as `draft` when added to the repo
- Hot reload detects the file, registers it as draft
- Operator sees it in the UI, reviews, clicks "Approve and activate"
- API call: `PATCH /workflows/{workflow_id}/status` with `{status: "active"}`
- Only active workflows are used by the matcher

**What this page does NOT have:**
- A markdown editor (edit files in your repo / IDE)
- Drag-and-drop state builder
- Visual workflow canvas

---

## API additions required

The existing FastAPI backend needs these additions to support the UI:

```
GET  /tasks                          — filtered task list (already planned)
GET  /tasks/{task_id}                — task detail (already planned)
POST /tasks                          — submit task (already planned)
GET  /health                         — health check (already planned)

NEW:
GET  /events/stream                  — SSE stream of live events
POST /tasks/{task_id}/respond        — human responds to escalation
POST /tasks/{task_id}/reassign       — reassign escalated task to different team
GET  /workflows                      — list all workflow definitions
GET  /workflows/{workflow_id}        — get workflow definition + version history
PATCH /workflows/{workflow_id}/status — approve (active) or deprecate workflow
```

---

## Notification model (V1 — minimal)

No email, no Slack, no push notifications in V1. Notifications are:

1. **In-app banner** — Dashboard shows escalation banner when any task is in `escalated` status
2. **Browser tab title** — changes to `(N) Needs input — OrgOS` when escalations are pending
3. **Notification log** — `GET /notifications` returns list of unread notifications, each with `task_id`, `message`, `created_at`, `read_at`

Real notification delivery (email/Slack) is a V2 feature.

---

## Routing summary

```
/                          Dashboard
/tasks                     Task list
/tasks/new                 Submit task
/tasks/[task_id]           Task detail + escalation response
/activity                  Live agent activity feed
/workflows                 Workflow list
/workflows/[workflow_id]   Workflow detail + approve/deprecate
```

---

## Non-technical language map

The UI must never show raw system internals to non-technical users. Apply these substitutions everywhere:

| System term | UI label |
|---|---|
| escalated | Needs your input |
| state_transition | Progress update |
| agentic_memory | Agent notes |
| workflow_id | Process template |
| owner_agent_id | Assigned to |
| kite_runner | Coordinator |
| generalist | Team lead |
| specialist | Agent |
| retry_count | Attempts |
| escalation_count | Times escalated |
| task.blocked | Stuck |
| task.completed | Done |

Operators and technical users can see raw values in the collapsed "Technical detail" section on Task Detail.

---

## Component library (minimal)

Build only these reusable components. Nothing else.

```
StatusBadge         — renders status as coloured pill
TaskRow             — single row in task table
Timeline            — vertical event timeline
EscalationPanel     — the human-response panel on Task Detail
FeedItem            — single item in activity feed
WorkflowCard        — single row in workflow table
PageHeader          — consistent page title + breadcrumb
EmptyState          — "nothing here yet" placeholder
LoadingSpinner      — inline loading indicator
ErrorMessage        — inline error display
```

---

## V2 UI backlog

Do not build these in V1:

- Email / Slack notification delivery
- Memory explorer (browse what agents have learned)
- Evaluation metrics dashboard (charts, trends)
- Visual workflow canvas / editor
- Role-based access control (all users see everything in V1)
- Dark mode
- Mobile-optimised layout (desktop-first in V1)
- Bulk task actions
- Task search (use browser ctrl+F on task list for V1)