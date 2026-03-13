# GUI IA and API Contracts

## Information Architecture

1. Authentication and Security
- identity and role
- CSRF token status

2. Workflow Lifecycle
- list workflows and versions
- validate, publish, activate, deprecate, archive, rollback
- markdown and IR diff

3. Agent Builder
- compose role + capabilities + policies + prompt profile
- compatibility checks against compiled workflow steps

4. Entity CRUD
- roles, capabilities, policies, prompts, domain packs, schedules

5. Run Console
- intake, run, retry, mark blocked/failed
- task trace and event stream

6. Memory and Topology
- scoped memory query/invalidate
- live topology view

7. Audit and Incidents
- filtered audit events
- incident creation/list/export

8. Integrations and Bootstrap
- connector status and health
- integration binding profile visibility

## API Envelope

- Reads return entity payloads directly for low overhead local mode.
- Mutations return `{ ok: true }` or resource payload.
- Errors return standard FastAPI `detail` object with status codes.

## Role Matrix

- `viewer`: read-only endpoints
- `operator`: CRUD and task execution
- `admin`: archive/rollback and other high-risk operations

## CSRF Policy

- `ui_auth_mode=token`: mutating `/api/*` routes require matching cookie/header CSRF token.
- `ui_auth_mode=none`: CSRF checks skipped for local convenience.
