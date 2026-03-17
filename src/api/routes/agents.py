"""Agent management routes for Loom MVP."""
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

AGENTS_CONFIG_DIR = Path("agents_config")


class AgentConfig(BaseModel):
    """Agent configuration model."""
    agent_id: str
    name: str
    authority_level: str  # kr, generalist, specialist
    team_id: str
    model_role: str  # fast, reasoning
    permitted_tools: list[str]
    memory_scope: str  # agentic_only, agentic_and_team, agentic_team_and_org
    description: str = ""
    max_retries: int = 3
    active: bool = True


class CreateAgentRequest(BaseModel):
    """Create agent request."""
    agent_id: str
    name: str
    authority_level: str
    team_id: str
    model_role: str = "reasoning"
    permitted_tools: list[str] = []
    memory_scope: str = "agentic_only"
    description: str = ""
    max_retries: int = 3


class UpdateAgentRequest(BaseModel):
    """Update agent request."""
    name: str | None = None
    team_id: str | None = None
    model_role: str | None = None
    permitted_tools: list[str] | None = None
    memory_scope: str | None = None
    description: str | None = None
    max_retries: int | None = None
    active: bool | None = None


def _load_agent_config(agent_id: str) -> dict[str, Any] | None:
    """Load agent config from JSON file."""
    config_path = AGENTS_CONFIG_DIR / f"{agent_id}.json"
    if not config_path.exists():
        return None
    
    with open(config_path) as f:
        return json.load(f)


def _save_agent_config(agent_id: str, config: dict[str, Any]) -> None:
    """Save agent config to JSON file."""
    AGENTS_CONFIG_DIR.mkdir(exist_ok=True)
    config_path = AGENTS_CONFIG_DIR / f"{agent_id}.json"
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def _list_agent_configs() -> list[dict[str, Any]]:
    """List all agent configs."""
    agents = []
    
    if not AGENTS_CONFIG_DIR.exists():
        return agents
    
    for config_file in AGENTS_CONFIG_DIR.glob("*.json"):
        try:
            with open(config_file) as f:
                config = json.load(f)
                agents.append(config)
        except Exception:
            continue
    
    return agents


@router.get("/agents")
async def list_agents():
    """List all agents."""
    agents = _list_agent_configs()
    return {"agents": agents, "total": len(agents)}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    config = _load_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return config


@router.post("/agents")
async def create_agent(request: CreateAgentRequest):
    """Create a new agent."""
    # Check if agent already exists
    config_path = AGENTS_CONFIG_DIR / f"{request.agent_id}.json"
    if config_path.exists():
        raise HTTPException(status_code=409, detail="Agent already exists")
    
    # Validate authority_level
    valid_levels = ["kr", "generalist", "specialist"]
    if request.authority_level not in valid_levels:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid authority_level. Must be one of: {valid_levels}"
        )
    
    # Validate model_role
    valid_roles = ["fast", "reasoning"]
    if request.model_role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model_role. Must be one of: {valid_roles}"
        )
    
    # Validate memory_scope
    valid_scopes = ["agentic_only", "agentic_and_team", "agentic_team_and_org"]
    if request.memory_scope not in valid_scopes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memory_scope. Must be one of: {valid_scopes}"
        )
    
    # Build config
    config = {
        "agent_id": request.agent_id,
        "name": request.name,
        "authority_level": request.authority_level,
        "team_id": request.team_id,
        "model_role": request.model_role,
        "permitted_tools": request.permitted_tools,
        "memory_scope": request.memory_scope,
        "description": request.description,
        "max_retries": request.max_retries,
        "active": True,
    }
    
    _save_agent_config(request.agent_id, config)
    
    return {"success": True, "agent_id": request.agent_id}


@router.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, request: UpdateAgentRequest):
    """Update an existing agent."""
    config = _load_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Update fields if provided
    if request.name is not None:
        config["name"] = request.name
    if request.team_id is not None:
        config["team_id"] = request.team_id
    if request.model_role is not None:
        valid_roles = ["fast", "reasoning"]
        if request.model_role not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_role. Must be one of: {valid_roles}"
            )
        config["model_role"] = request.model_role
    if request.permitted_tools is not None:
        config["permitted_tools"] = request.permitted_tools
    if request.memory_scope is not None:
        valid_scopes = ["agentic_only", "agentic_and_team", "agentic_team_and_org"]
        if request.memory_scope not in valid_scopes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid memory_scope. Must be one of: {valid_scopes}"
            )
        config["memory_scope"] = request.memory_scope
    if request.description is not None:
        config["description"] = request.description
    if request.max_retries is not None:
        config["max_retries"] = request.max_retries
    if request.active is not None:
        config["active"] = request.active
    
    _save_agent_config(agent_id, config)
    
    return {"success": True, "agent_id": agent_id}


@router.delete("/agents/{agent_id}")
async def deactivate_agent(agent_id: str):
    """Deactivate an agent (soft delete)."""
    config = _load_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Soft delete by setting active=False
    config["active"] = False
    _save_agent_config(agent_id, config)
    
    return {"success": True, "agent_id": agent_id, "status": "deactivated"}


@router.post("/agents/{agent_id}/activate")
async def activate_agent(agent_id: str):
    """Reactivate a deactivated agent."""
    config = _load_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    config["active"] = True
    _save_agent_config(agent_id, config)
    
    return {"success": True, "agent_id": agent_id, "status": "activated"}


# Teams management

class Team(BaseModel):
    """Team model."""
    team_id: str
    name: str
    description: str = ""
    generalist_agent_id: str | None = None
    specialist_agent_ids: list[str] = []


class CreateTeamRequest(BaseModel):
    """Create team request."""
    team_id: str
    name: str
    description: str = ""
    generalist_agent_id: str | None = None


class UpdateTeamRequest(BaseModel):
    """Update team request."""
    name: str | None = None
    description: str | None = None
    generalist_agent_id: str | None = None


# In-memory team store (could be moved to DB in future)
_teams: dict[str, dict[str, Any]] = {}


def _load_teams() -> None:
    """Load teams from disk if exists."""
    global _teams
    teams_file = AGENTS_CONFIG_DIR / "_teams.json"
    if teams_file.exists():
        with open(teams_file) as f:
            _teams = json.load(f)


def _save_teams() -> None:
    """Save teams to disk."""
    AGENTS_CONFIG_DIR.mkdir(exist_ok=True)
    teams_file = AGENTS_CONFIG_DIR / "_teams.json"
    with open(teams_file, 'w') as f:
        json.dump(_teams, f, indent=2)


# Load teams on module import
_load_teams()


@router.get("/teams")
async def list_teams():
    """List all teams."""
    teams_list = list(_teams.values())
    
    # Enrich with agent counts
    for team in teams_list:
        team["specialist_count"] = len(team.get("specialist_agent_ids", []))
    
    return {"teams": teams_list, "total": len(teams_list)}


@router.get("/teams/{team_id}")
async def get_team(team_id: str):
    """Get team details."""
    if team_id not in _teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = _teams[team_id].copy()
    
    # Enrich with agent details
    team["agents"] = []
    for agent_id in team.get("specialist_agent_ids", []):
        config = _load_agent_config(agent_id)
        if config:
            team["agents"].append({
                "agent_id": config["agent_id"],
                "name": config["name"],
                "authority_level": config["authority_level"],
                "active": config.get("active", True),
            })
    
    if team.get("generalist_agent_id"):
        config = _load_agent_config(team["generalist_agent_id"])
        if config:
            team["generalist"] = {
                "agent_id": config["agent_id"],
                "name": config["name"],
                "active": config.get("active", True),
            }
    
    return team


@router.post("/teams")
async def create_team(request: CreateTeamRequest):
    """Create a new team."""
    if request.team_id in _teams:
        raise HTTPException(status_code=409, detail="Team already exists")
    
    # Validate generalist if provided
    if request.generalist_agent_id:
        config = _load_agent_config(request.generalist_agent_id)
        if not config:
            raise HTTPException(status_code=400, detail="Generalist agent not found")
        if config["authority_level"] != "generalist":
            raise HTTPException(
                status_code=400, 
                detail="Agent must be a generalist to lead a team"
            )
    
    team = {
        "team_id": request.team_id,
        "name": request.name,
        "description": request.description,
        "generalist_agent_id": request.generalist_agent_id,
        "specialist_agent_ids": [],
    }
    
    _teams[request.team_id] = team
    _save_teams()
    
    return {"success": True, "team_id": request.team_id}


@router.patch("/teams/{team_id}")
async def update_team(team_id: str, request: UpdateTeamRequest):
    """Update a team."""
    if team_id not in _teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = _teams[team_id]
    
    if request.name is not None:
        team["name"] = request.name
    if request.description is not None:
        team["description"] = request.description
    if request.generalist_agent_id is not None:
        if request.generalist_agent_id:
            config = _load_agent_config(request.generalist_agent_id)
            if not config:
                raise HTTPException(status_code=400, detail="Generalist agent not found")
            if config["authority_level"] != "generalist":
                raise HTTPException(
                    status_code=400,
                    detail="Agent must be a generalist to lead a team"
                )
        team["generalist_agent_id"] = request.generalist_agent_id
    
    _save_teams()
    
    return {"success": True, "team_id": team_id}


@router.delete("/teams/{team_id}")
async def delete_team(team_id: str):
    """Delete a team."""
    if team_id not in _teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    del _teams[team_id]
    _save_teams()
    
    return {"success": True, "team_id": team_id}


@router.post("/teams/{team_id}/agents/{agent_id}")
async def add_agent_to_team(team_id: str, agent_id: str):
    """Add a specialist agent to a team."""
    if team_id not in _teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    config = _load_agent_config(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if config["authority_level"] != "specialist":
        raise HTTPException(
            status_code=400,
            detail="Only specialist agents can be added to teams"
        )
    
    team = _teams[team_id]
    if agent_id not in team["specialist_agent_ids"]:
        team["specialist_agent_ids"].append(agent_id)
        
        # Update agent's team_id
        config["team_id"] = team_id
        _save_agent_config(agent_id, config)
        
        _save_teams()
    
    return {"success": True, "team_id": team_id, "agent_id": agent_id}


@router.delete("/teams/{team_id}/agents/{agent_id}")
async def remove_agent_from_team(team_id: str, agent_id: str):
    """Remove a specialist agent from a team."""
    if team_id not in _teams:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = _teams[team_id]
    if agent_id in team["specialist_agent_ids"]:
        team["specialist_agent_ids"].remove(agent_id)
        
        # Update agent's team_id to empty
        config = _load_agent_config(agent_id)
        if config:
            config["team_id"] = ""
            _save_agent_config(agent_id, config)
        
        _save_teams()
    
    return {"success": True, "team_id": team_id, "agent_id": agent_id}
