# TASKS.md - Loom Implementation Tracker

## Completed: GUI Restructure (2026-03-13)

### Backend Changes
- [x] Added `Organization` model to `loom/models.py`
- [x] Added `OrganizationRow` table to `loom/persistence/db.py`
- [x] Added `OrganizationRepository` to `loom/persistence/repositories.py`
- [x] Added organization API endpoints (`/api/organization`) to `loom/ui/router.py`

### Frontend Changes
- [x] Complete UI restructure with 4 main screens:
  - **Organization** - Settings for org name, LiteLLM, OpenAI, OpenCode config
  - **Agents** - List view + 5-step creation wizard
  - **Workflows** - List view + split-view markdown editor with preview
  - **Tasks** - Console for intake/execution + task list
- [x] Navigation sidebar with icons
- [x] Tab-based sub-navigation per screen
- [x] Modern responsive styling

### Key Features
1. **Organization Settings**: 
   - Configure org name
   - LiteLLM: URL, API key, default model (e.g., `open-large`)
   - OpenAI: API key, model
   - OpenCode: enable toggle, command path
2. **Agent Wizard**: 5-step creation (Basic Info → Capabilities → Connectors → Policies → Review)
3. **Workflow Editor**: Markdown editor with live preview showing agent assignments
4. **Task Console**: Intake, run, retry, trace tasks with status badges

## Architecture: How Agents Work

### Agent Types
```
┌─────────────────────────────────────────────────────────────┐
│  Agent (Role)                                                │
│  ├── Capabilities (what it can do)                          │
│  │   └── connector_binding: opencode | git | gh | litellm   │
│  ├── Policies (enforcement rules)                           │
│  └── Prompt Profile (system prompt for LLM)                 │
└─────────────────────────────────────────────────────────────┘
```

### Connector Types
| Connector | Purpose | API Key Location |
|-----------|---------|------------------|
| **opencode** | Repository context, code operations | CLI-based (no key) |
| **litellm** | LLM calls via LiteLLM proxy | Organization.litellm_api_key |
| **openai** | Direct OpenAI API calls | Organization.openai_api_key |
| **git** | Git operations | SSH keys |
| **gh** | GitHub CLI operations | GitHub token |

### LLM Model Flow
```
Task → Workflow Step → Agent (Role)
                          ↓
                    ModelRouter.resolve("step_execution")
                          ↓
                    LiteLLM Provider (org.litellm_base_url)
                          ↓
                    Model: org.litellm_default_model (e.g., "open-large")
```

### Creating an OpenCode Agent
1. Go to **Organization** → Enable OpenCode
2. Go to **Agents** → Create Agent
3. In wizard step 2 (Capabilities), create/select capabilities with `connector_binding: opencode`
4. Example capabilities:
   - `repo_read` (opencode)
   - `context_build` (opencode)
5. Agent will use OpenCode CLI for these operations

### Creating an LLM Persona Agent
1. Go to **Organization** → Configure LiteLLM URL/API key/model
2. Go to **Agents** → Create Agent
3. Create capability with `connector_binding: litellm` or `none`
4. The agent's prompt profile defines its "persona"
5. LLM calls use ModelRouter → LiteLLM → configured model

## Next Steps

### High Priority
- [ ] Test full end-to-end flow: Org → Agent → Workflow → Task
- [ ] Wire Organization settings to ModelRouter for LLM calls
- [ ] Add capability to select model per agent (not just global)

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

## Database Schema: organizations table

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| org_id | String(64) | "default" | Primary key |
| name | String(256) | "My Organization" | Organization name |
| litellm_base_url | String(512) | null | LiteLLM proxy URL |
| litellm_api_key | String(256) | null | LiteLLM API key |
| litellm_default_model | String(128) | "open-large" | Default model name |
| openai_api_key | String(256) | null | OpenAI API key |
| openai_model | String(128) | "gpt-4.1-mini" | OpenAI model |
| opencode_enabled | Boolean | false | OpenCode toggle |
| opencode_cmd | String(128) | "opencode" | OpenCode CLI command |
| created_at | DateTime | auto | Creation timestamp |
| updated_at | DateTime | auto | Last update timestamp |
