"""Agent identity loader for Loom MVP."""
import json
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field, validator


class AgentConfig(BaseModel):
    """Agent configuration."""
    agent_id: str
    name: str
    authority_level: str  # kr, generalist, specialist
    team_id: str
    model_role: str  # fast, reasoning
    permitted_tools: list[str]
    memory_scope: str  # agentic_only, agentic_and_team, agentic_team_and_org
    openfang_config: dict | None = None

    @validator("authority_level")
    def validate_authority(cls, v):
        if v not in ["kr", "generalist", "specialist"]:
            raise ValueError(f"Invalid authority_level: {v}")
        return v

    @validator("model_role")
    def validate_model_role(cls, v):
        if v not in ["fast", "reasoning"]:
            raise ValueError(f"Invalid model_role: {v}")
        return v

    @validator("memory_scope")
    def validate_memory_scope(cls, v):
        if v not in ["agentic_only", "agentic_and_team", "agentic_team_and_org"]:
            raise ValueError(f"Invalid memory_scope: {v}")
        return v


def load_identity(agent_id: str) -> AgentConfig:
    """Load agent identity from JSON file.

    Args:
        agent_id: Agent ID

    Returns:
        AgentConfig

    Raises:
        FileNotFoundError: If agent config not found
    """
    config_path = Path(f"agents_config/{agent_id}.json")

    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")

    with open(config_path) as f:
        data = json.load(f)

    config = AgentConfig(**data)
    logger.debug(f"Loaded agent config: {config.agent_id}")
    return config


def list_agents() -> list[str]:
    """List all available agent IDs."""
    config_dir = Path("agents_config")
    if not config_dir.exists():
        return []

    return [
        f.stem for f in config_dir.glob("*.json")
        if f.stem != "__init__"
    ]
