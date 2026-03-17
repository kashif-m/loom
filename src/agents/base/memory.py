"""Memory access layer for agents."""
from loguru import logger

from src.agents.base.identity import AgentConfig
from src.memory.graphiti.client import get_graphiti_client
from src.memory.graphiti.schemas import MemoryQuery, MemoryTier


async def retrieve_context(
    agent_id: str,
    query: str,
    memory_scope: str,
) -> list[str]:
    """Retrieve context from memory for an agent.
    
    Args:
        agent_id: Agent ID
        query: Query string
        memory_scope: Memory scope level
        
    Returns:
        List of memory content strings
    """
    from src.agents.base.identity import load_identity
    
    try:
        agent_config = load_identity(agent_id)
        context = await query_memory(agent_config, query)
        
        # Parse context into list
        if context:
            lines = context.split('\n')
            # Filter out header line and empty lines
            return [line.strip('- ') for line in lines if line.strip() and not line.startswith('Relevant')]
        return []
    except Exception as e:
        logger.warning(f"Failed to retrieve context for {agent_id}: {e}")
        return []


async def query_memory(
    agent_config: AgentConfig,
    query: str,
) -> str:
    """Query memory with cascade retrieval and access control.
    
    Implements tiered memory access:
    1. Agentic memory first (if accessible based on scope)
    2. Team memory second (if scope allows and results < threshold)
    3. Org memory third (if scope allows and results < threshold)
    
    Access control enforced at each tier.
    """
    graphiti = get_graphiti_client()

    all_memories = []

    # Stage 1: Agentic memory
    if agent_config.memory_scope in ["agentic_only", "agentic_and_team", "agentic_team_and_org"]:
        try:
            agentic_results = await graphiti.query_tier(
                MemoryQuery(
                    query=query,
                    tier=MemoryTier.AGENTIC,
                    agent_id=agent_config.agent_id,
                    limit=5,
                ),
                agent_id=agent_config.agent_id,
                authority_level=agent_config.authority_level,
            )
            all_memories.extend(agentic_results)
            logger.debug(f"Retrieved {len(agentic_results)} agentic memories")
        except Exception as e:
            logger.warning(f"Failed to query agentic memory: {e}")

    # Stage 2: Team memory (if not enough results)
    if agent_config.memory_scope in ["agentic_and_team", "agentic_team_and_org"]:
        if len(all_memories) < 3:
            try:
                team_results = await graphiti.query_tier(
                    MemoryQuery(
                        query=query,
                        tier=MemoryTier.TEAM,
                        team_id=agent_config.team_id,
                        limit=5,
                    ),
                    agent_id=agent_config.agent_id,
                    authority_level=agent_config.authority_level,
                )
                all_memories.extend(team_results)
                logger.debug(f"Retrieved {len(team_results)} team memories")
            except Exception as e:
                logger.warning(f"Failed to query team memory: {e}")

    # Stage 3: Org memory (if not enough results)
    if agent_config.memory_scope == "agentic_team_and_org":
        if len(all_memories) < 3:
            try:
                org_results = await graphiti.query_tier(
                    MemoryQuery(
                        query=query,
                        tier=MemoryTier.ORG,
                        limit=3,
                    ),
                    agent_id=agent_config.agent_id,
                    authority_level=agent_config.authority_level,
                )
                all_memories.extend(org_results)
                logger.debug(f"Retrieved {len(org_results)} org memories")
            except Exception as e:
                logger.warning(f"Failed to query org memory: {e}")

    # Assemble context
    if not all_memories:
        return ""

    context_parts = ["Relevant past experiences:"]
    for memory in all_memories[:10]:  # Max 10 memories
        context_parts.append(f"- {memory.content}")

    return "\n".join(context_parts)


def get_memory_scope_description(scope: str) -> str:
    """Get human-readable description of memory scope."""
    descriptions = {
        "agentic_only": "Can access only own memory",
        "agentic_and_team": "Can access own and team memory",
        "agentic_team_and_org": "Can access all memory tiers",
    }
    return descriptions.get(scope, "Unknown scope")
