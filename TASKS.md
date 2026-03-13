# TASKS.md - Loom Implementation Tracker

## Completed: GUI Restructure (2026-03-13)

### Backend Changes
- [x] Added `Organization` model to `loom/models.py`
- [x] Added `OrganizationRow` table to `loom/persistence/db.py`
- [x] Added `OrganizationRepository` to `loom/persistence/repositories.py`
- [x] Added organization API endpoints (`/api/organization`) to `loom/ui/router.py`

### Frontend Changes
- [x] Complete UI restructure with 4 main screens:
  - **Organization** - Settings for org name and LiteLLM config
  - **Agents** - List view + 5-step creation wizard
  - **Workflows** - List view + split-view markdown editor with preview
  - **Tasks** - Console for intake/execution + task list
- [x] Navigation sidebar with icons
- [x] Tab-based sub-navigation per screen
- [x] Modern responsive styling

### Key Features
1. **Organization Settings**: Configure org name, LiteLLM URL, API key
2. **Agent Wizard**: 5-step creation (Basic Info → Capabilities → Connectors → Policies → Review)
3. **Workflow Editor**: Markdown editor with live preview showing agent assignments
4. **Task Console**: Intake, run, retry, trace tasks with status badges

## Next Steps

### High Priority
- [ ] Test full end-to-end flow: Org → Agent → Workflow → Task
- [ ] Add workflow step visual builder (drag-drop)
- [ ] Add agent capability compatibility matrix

### Medium Priority
- [ ] Add real-time task execution streaming
- [ ] Add workflow version diff viewer
- [ ] Add memory/query UI for episodic memory

### Low Priority
- [ ] Add export/import for configurations
- [ ] Add dark mode toggle
- [ ] Add keyboard shortcuts

## How to Run

```bash
# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate
pip install pydantic sqlalchemy fastapi httpx uvicorn

# Run the server
python3 -m loom.app.main --serve

# Open browser
open http://127.0.0.1:8000/ui
```

## API Endpoints Added

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/organization` | GET | Get organization settings |
| `/api/organization` | POST | Update organization settings |

## Database Schema Added

### organizations table
| Column | Type | Description |
|--------|------|-------------|
| org_id | String(64) | Primary key (default: "default") |
| name | String(256) | Organization name |
| litellm_base_url | String(512) | LiteLLM base URL |
| litellm_api_key | String(256) | LiteLLM API key |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |
