# UI_REDESIGN_PROMPT.md
# Feed this entire file to opencode before starting any UI task.

---

## Role

You are implementing the frontend for **Loom** — a virtual organisation orchestration system. The backend is fully built. Your job is to make the UI production-quality: clear, fast, and usable by both technical operators and non-technical team members.

Read `ARCHITECTURE.md`, `CODING_GUIDELINES.md`, and `UI_SPEC.md` before touching any file.

---

## Design principles

**1. Hierarchy over decoration.**
Every screen has one primary action and one primary piece of information. Everything else is secondary. Never let decoration compete with content.

**2. Status is always visible.**
A user should be able to understand the health of the system in under 3 seconds from any page. Escalations (tasks that need human input) must always be the most visually prominent thing on screen when they exist.

**3. Non-technical language everywhere.**
Apply the language map from `UI_SPEC.md` without exception. Never render raw field names, enum values, or system internals in the UI. "Needs your input" not "escalated". "Attempts" not "retry_count". "Process template" not "workflow_id".

**4. The escalation panel is the most important UI element in the system.**
If an agent gets stuck and escalates, a human must be able to understand what happened and respond clearly. This screen gets the most design care of anything in the UI.

**5. Minimal but complete.**
No charts, no animations, no decorative elements. Clean whitespace, consistent spacing, readable typography. The UI should feel like a well-designed internal tool, not a marketing page.

---

## Design system

### Colours
- **Brand / primary action:** `#92610A` (amber-800) — used for the logo, primary buttons, active nav states
- **Background:** `#F5F3EE` (warm off-white) — page background
- **Surface:** `#FFFFFF` — cards, panels, inputs
- **Border:** `#E5E1D8` — subtle warm gray
- **Text primary:** `#1A1714` — near-black
- **Text secondary:** `#6B6560` — muted warm gray
- **Text tertiary:** `#9E9890` — hints, timestamps

**Status colours (semantic — do not use for decoration):**
- Open: `#1D4ED8` / `#EFF6FF` (blue)
- Blocked / Needs input: `#D97706` / `#FFFBEB` (amber)
- Escalated / Urgent: `#DC2626` / `#FEF2F2` (red)
- Completed: `#16A34A` / `#F0FDF4` (green)
- Draft: `#6B7280` / `#F9FAFB` (gray)

### Typography
- Font: System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`)
- Page title: 24px, weight 600
- Section heading: 16px, weight 600
- Body: 14px, weight 400, line-height 1.6
- Label / caption: 12px, weight 500, uppercase tracking for column headers only
- Monospace (task IDs, raw values): 12px, `font-mono`

### Spacing
- Base unit: 4px
- Component padding: 16px (cards), 12px (table cells), 8px (badges)
- Section gap: 24px
- Page padding: 32px horizontal, 24px vertical

### Components (define once, use everywhere)
- `StatusBadge` — pill with semantic colour, 12px text, 4px radius
- `TaskRow` — table row with hover state, entire row is clickable
- `Timeline` — vertical list with connector line, timestamps right-aligned
- `EscalationPanel` — amber-bordered panel, prominent on Task Detail
- `FeedItem` — single activity event with agent badge and task link
- `PageHeader` — title + subtitle + optional action button
- `EmptyState` — centered icon + heading + subtext, no border
- `SectionCard` — white card with `border: 1px solid #E5E1D8`, `border-radius: 8px`

---

## Screen-by-screen design spec

### Dashboard (`/`)

**Layout:** Full-width page. Three stat cards in a row. Escalation banner above everything when escalations exist. Recent tasks table below.

**Escalation banner:**
- Only visible when `status = escalated` tasks exist
- Full-width, `background: #FEF2F2`, `border-bottom: 2px solid #DC2626`
- Text: "{N} task(s) need your input" with a "Review now →" link
- This banner must appear ABOVE the page header, spanning the full viewport width
- It is never dismissible — it disappears only when all escalations are resolved

**Stat cards:**
- Three equal-width cards in a row
- Each: icon (coloured), label (text-secondary, 12px), large number (28px, weight 600)
- Open Tasks: blue clock icon
- Blocked: amber warning icon  
- Completed Today: green checkmark icon
- Cards have no hover state — they are display only

**Recent Tasks table:**
- Columns: Task (description truncated to 60 chars + task ID in mono below), Team, Assigned to, Status, Current state, Last updated (relative time)
- No checkbox column in V1
- Entire row is clickable → Task Detail
- Rows with `status = escalated` get a subtle `background: #FFFBEB` tint
- "No tasks yet" empty state with document icon (already implemented — keep it)
- Table lives inside a SectionCard
- Add a "View all tasks →" link at bottom right of the card

**Polling:** Every 30 seconds. Show a subtle "Last updated X seconds ago" text near the table header — not a spinner.

---

### Task List (`/tasks`)

**Layout:** PageHeader with title + "New Task" button. Filter bar. Table.

**Filter bar:**
- Status multiselect (pill toggles, not a dropdown): All | Open | Blocked | Needs input | Completed
- Team select dropdown
- Date range: "Today", "Last 7 days", "Last 30 days", "All time"
- Filters are reflected in URL query params
- Active filter pills shown below the filter bar when non-default filters are applied, each with an × to remove

**Table:**
- Same columns as Dashboard recent tasks, but add: Created date, Retry count
- Sortable columns: Created, Last updated, Status (click header to toggle asc/desc)
- "Needs your input" tasks always sort to top regardless of other sort
- Pagination: 20 rows per page, simple prev/next with page number
- Row hover: `background: #FAFAF8`

---

### Submit Task (`/tasks/new`)

**Layout:** Narrow centered form (max-width 640px), PageHeader.

**Form:**
- Large textarea for task description, min-height 120px, placeholder: "Describe what needs to be done in as much detail as possible..."
- Character count shown below textarea (e.g. "142 / 2000")
- Priority hint: three pill toggles — Low, Normal (default selected), Urgent
- Urgency note: small text under priority, "Urgent tasks are still routed through the same workflow — this is a hint only"
- Submit button: full-width, primary amber, "Submit task →"
- Loading state: button becomes "Routing your task..." with a spinner, disabled

**After submit:**
- Redirect to Task Detail page for the new task
- Task Detail shows a "Just submitted" indicator for 10 seconds

**Validation:**
- Inline error below textarea if < 20 chars on submit attempt
- No other validation in V1

---

### Task Detail (`/tasks/[task_id]`)

This is the most important page. Design it with the most care.

**Layout:** Two-column on desktop (main content left 65%, sidebar right 35%). Single column on mobile (not a V1 requirement but structure should support it).

**Left column (main content):**

*Header section:*
- Task description as the page heading (h1, 20px, weight 600)
- Task ID in monospace below the heading, text-secondary
- Status badge + current state (human-readable) side by side
- Row: Team • Assigned to • Created X days ago • Last updated X mins ago

*Escalation panel (conditional — highest visual priority):*
- Only shown when `status = escalated` or `status = blocked`
- Full-width amber panel: `background: #FFFBEB`, `border: 1.5px solid #D97706`, `border-radius: 8px`, padding 16px
- Header row: amber warning icon + "This task needs your input" (16px, weight 600)
- Blocker description below (the reason it escalated)
- "What was tried" section — collapsible, shows last 3 task history entries
- Divider
- Textarea: "Provide additional details or instructions" (required, min 20 chars)
- Two buttons side by side: "Send response" (primary amber) and "Reassign to different team" (secondary/outline)
- On "Send response" submit: optimistic update — panel disappears, timeline updates, success toast

*Progress timeline:*
- Section heading: "Progress"
- Vertical timeline, newest at top
- Each entry: coloured dot (colour matches status), state name (human-readable, weight 500), agent name in text-secondary, relative timestamp right-aligned, duration badge (e.g. "took 4m") in gray pill
- Current state entry has a pulsing dot indicator if status = open
- Completed entries have a checkmark dot

**Right column (sidebar):**

*SLA card:*
- Only shown if SLA deadline is set
- "Due" label + deadline datetime
- If overdue: red background, "Overdue by Xh" in red
- If within 2 hours: amber background, "Due in Xh" in amber
- Otherwise: normal

*Artifacts card:*
- "Outputs" heading
- List of attached artifacts: type icon + clickable reference link + agent + relative timestamp
- "No outputs yet" empty state in gray

*Blockers card:*
- "Blockers" heading
- Active blockers: amber bullet, description, raised by, raised at
- Resolved blockers: gray strikethrough, resolved at timestamp
- Collapsed by default if all resolved

*Technical details card (collapsed by default):*
- Gray "Technical details" heading with chevron
- Expands to show: raw task_id, workflow_id, version, retry_count, escalation_count
- For operators only — hidden by default from non-technical users

**Polling:** Every 15 seconds while `status = open`. Stop when `status = closed`.

---

### Activity Feed (`/activity`)

**Layout:** PageHeader. Filter bar. Live feed list.

**Header bar:**
- "Activity Feed" heading
- Right side: connection status indicator (green dot "Live" / amber dot "Reconnecting" / red dot "Disconnected")
- "Pause" toggle button — freezes rendering without disconnecting SSE

**Filter bar:**
- Event type pills: All | Task events | Agent actions | Escalations | Completions
- Agent filter: text input with autocomplete from seen agent names
- These filters apply client-side to the buffered events

**Feed:**
- Newest events at top
- Max 200 items in DOM — older items removed
- Each feed item:
  - Relative timestamp (left, text-tertiary, 12px, min-width 60px)
  - Agent badge: agent name in a coloured pill (colour consistent per agent role — amber for KR, blue for generalist, purple for specialist)
  - Event description in human-readable text (apply language map)
  - Task ID as a clickable link in monospace

**Event colour coding:**
- `task.completed` → green left border on feed item
- `workflow.escalated` → red left border
- `task.blocked` → amber left border
- All others → no border

**Empty / disconnected states:**
- Not yet connected: "Connecting to activity feed..."
- No events yet: "No activity yet. Submit a task to get started."
- Disconnected: red banner "Feed disconnected — attempting to reconnect"

---

### Workflows (`/workflows`)

**Layout:** PageHeader. Table.

**Table:**
- Columns: Name, Level (org/team/agentic badge), Version, Status badge, Trigger (truncated), Last modified
- Draft workflows: amber left border on row, "Pending approval" text in status column
- Clicking row → Workflow Detail

**Workflow Detail (`/workflows/[workflow_id]`):**

*Header:*
- Workflow name as heading
- Level badge + Version + Status badge
- "Trigger: ..." in text-secondary

*Approval banner (if status = draft):*
- Full-width amber banner: "This workflow is pending approval and will not be used until activated"
- "Approve and activate" button (primary)

*Deprecation notice (if status = deprecated):*
- Gray banner: "This workflow is deprecated. In-flight tasks will complete but no new tasks will use it."

*Content sections:*
- Tags: rendered as gray pills
- States: numbered ordered list, each state on its own row with a subtle connector
- Success condition: green-tinted block
- Escalation conditions: amber-tinted block
- Raw markdown: collapsible, syntax-highlighted code block (read-only)

*Version history:*
- Simple table: Version, Status, Activated at, Deprecated at
- Current version highlighted

---

## Navigation

Current nav (Dashboard, Tasks, Activity, Workflows) is correct. Keep it.

**Additions:**
- Escalation count badge on the nav itself — red number badge on "Tasks" nav item when escalations exist. This persists across all pages so the human always knows something needs their attention.
- Active page indicator: amber underline on active nav item (already implemented — keep it)
- "New Task" button in top right — already implemented, keep it

---

## Toast notifications

Add a minimal toast notification system for:
- Task submitted successfully → "Task submitted — routing now"
- Escalation response sent → "Response sent — task resumed"
- Workflow approved → "Workflow activated"
- Workflow deprecated → "Workflow deprecated"
- Any API error → "Something went wrong — please try again"

Toasts appear bottom-right, auto-dismiss after 4 seconds, max 3 visible at once.

---

## What NOT to build

Do not add any of these in this sprint:
- Charts or graphs of any kind
- Dark mode
- Animations or transitions (beyond CSS hover states)
- Role-based access control
- Mobile layout optimisation
- Bulk task actions
- Task search
- User profiles or settings pages
- Notification preferences

---

## API contract assumptions

These backend endpoints exist and return the following shapes.
Do not change the API — adapt the UI to what's there.

```
GET  /health
GET  /tasks?status=&team_id=&page=&per_page=
GET  /tasks/{task_id}
POST /tasks  { description, priority_hint }
POST /tasks/{task_id}/respond  { message }
POST /tasks/{task_id}/reassign  { team_id }
GET  /workflows
GET  /workflows/{workflow_id}
PATCH /workflows/{workflow_id}/status  { status }
GET  /events/stream  (SSE)
GET  /notifications
```

If a field is missing from the API response, render an empty state gracefully — never crash.

---

## Task list

Complete tasks in order. Each task is independently shippable.

### UI-001 — Design system foundation
Establish the design tokens and base components before touching any page.

Deliverables:
- `ui/lib/design-tokens.ts` — export all colours, spacing, typography values as typed constants. Single source of truth — no hardcoded hex values anywhere else in the UI.
- Update `tailwind.config.js` — extend theme with Loom colour palette, custom font sizes, spacing scale.
- Rebuild these base components to match the design spec above: `StatusBadge`, `SectionCard`, `PageHeader`, `EmptyState`, `LoadingSpinner`, `ErrorMessage`
- Add `Toast` component + `useToast` hook — bottom-right, auto-dismiss 4s, max 3 visible
- No page changes in this task — foundation only

Acceptance: All base components render correctly in isolation. No hardcoded colours anywhere.

---

### UI-002 — Navigation improvements
Depends on: UI-001

Deliverables:
- Escalation count badge on the "Tasks" nav item — red pill with count, fetched from `GET /tasks?status=escalated`, polls every 30s
- Badge disappears when count = 0
- "Last updated" subtle timestamp near the dashboard table (not a spinner)
- Ensure active nav state (amber underline) works correctly on all 5 routes

Acceptance: Badge appears when escalated tasks exist. Disappears when resolved.

---

### UI-003 — Dashboard redesign
Depends on: UI-001, UI-002

Deliverables:
- Full-width escalation banner above everything — red background, count, "Review now →" link — only when escalations exist
- Stat cards redesigned to match spec (icon + label + large number)
- Recent tasks table: add task ID in mono below description, add relative timestamps, escalated rows get amber tint
- "View all tasks →" link at bottom right of table card
- "Last updated X seconds ago" below table header
- 30-second polling

Acceptance: Escalation banner appears and disappears correctly. Table rows link to correct task detail pages.

---

### UI-004 — Task list page redesign
Depends on: UI-001

Deliverables:
- Filter bar with pill toggles for status (not a dropdown)
- Active filter pills with × removal
- URL query param persistence for all filters
- "Needs your input" tasks always at top regardless of sort
- Sortable columns (Created, Last updated, Status)
- Pagination (20/page, prev/next)
- Row hover state

Acceptance: Filtering by status works. URL reflects active filters. Refreshing page preserves filter state.

---

### UI-005 — Task detail page — core layout
Depends on: UI-001

Deliverables:
- Two-column layout (65/35 split)
- Left: header section with all task metadata, progress timeline
- Right: SLA card, artifacts card, blockers card, technical details (collapsed)
- Timeline: coloured dots, agent names, relative timestamps, duration pills
- Current state dot pulses if task is open
- 15-second polling while open, stops when closed
- Human-readable state names and agent labels (apply language map)

Acceptance: Task detail page renders all sections. Timeline shows correct history. Technical details card is collapsed by default.

---

### UI-006 — Escalation panel
Depends on: UI-005

This is the highest-priority UI element in the system. Build it with the most care.

Deliverables:
- Escalation panel renders only when `status = escalated` or `status = blocked`
- Amber border panel with warning icon, blocker description, collapsible "what was tried" section
- Response textarea with validation (required, min 20 chars)
- "Send response" and "Reassign" buttons
- Send response: `POST /tasks/{task_id}/respond`, optimistic update, success toast, panel hides on success
- Reassign: opens an inline team selector, calls `POST /tasks/{task_id}/reassign`, success toast
- Error state: inline error if API call fails, panel stays open

Acceptance: Full escalation flow works end-to-end. Submitting a response causes the panel to disappear and the timeline to update.

---

### UI-007 — Submit task page redesign
Depends on: UI-001

Deliverables:
- Narrow centered layout (max-width 640px)
- Character count below textarea
- Priority hint as pill toggles (Low / Normal / Urgent) with Normal pre-selected
- Urgency note below priority
- Full-width submit button with loading state
- Redirect to task detail on success
- "Just submitted" indicator on task detail for 10 seconds after redirect
- Inline validation error for < 20 chars

Acceptance: Form submits correctly. Loading state shows. Redirect works. Character count updates live.

---

### UI-008 — Activity feed redesign
Depends on: UI-001

Deliverables:
- Connection status indicator (Live / Reconnecting / Disconnected)
- Pause toggle — freezes rendering, queues new items, shows "N new events" badge when paused
- Agent role badges with consistent colours per role (amber=KR, blue=generalist, purple=specialist)
- Left border colour coding per event type
- Client-side filters (event type pills, agent name input)
- Auto-reconnect with exponential backoff
- Max 200 items in DOM
- All events use human-readable language map

Acceptance: Feed connects on page load. Pause/resume works. Filters apply correctly client-side. Disconnection shows correct banner.

---

### UI-009 — Workflows pages redesign
Depends on: UI-001

Deliverables:
- Workflow list: draft workflows with amber left border, correct status badges
- Workflow detail: approval banner for drafts, deprecation notice for deprecated
- Tags as gray pills
- States as numbered ordered list with connectors
- Success condition in green-tinted block
- Escalation conditions in amber-tinted block
- Raw markdown collapsible
- Version history table
- Approve and deprecate actions with confirmation on deprecate

Acceptance: Approve flow changes status and removes banner. Deprecate shows confirmation before acting.

---

### UI-010 — Polish and consistency pass
Depends on: UI-001 through UI-009

Final pass before calling V1 UI complete.

Deliverables:
- Audit every page for hardcoded colours — replace with design tokens
- Audit every page for raw field names — apply language map
- Verify toast notifications appear on all success and error states
- Verify empty states on every page render correctly
- Verify all relative timestamps update correctly (should re-render every minute)
- Verify 30s polling on dashboard and 15s polling on task detail work correctly
- Verify escalation badge in nav updates when tasks are escalated and resolved
- Manual test checklist from TASK-038 in TASKS.md — run every item

Acceptance: All 8 checklist items from TASK-038 pass.
EOF