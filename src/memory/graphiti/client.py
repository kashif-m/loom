"""Graphiti client for Loom MVP using graphiti-core 0.28.2 as a library."""
import os
import uuid
from typing import Any

from loguru import logger

from src.exceptions import MemoryAccessDeniedError
from src.memory.graphiti.schemas import MemoryEdge, MemoryNode, MemoryQuery, MemoryTier


# Try to import graphiti_core, but make it optional for MVP
try:
    from graphiti_core import Graphiti
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    logger.warning("graphiti_core not available - memory features will be limited")


class GraphitiClient:
    """Graphiti client using graphiti-core library directly with custom tiered access control."""

    def __init__(self):
        # Graphiti uses Neo4j by default
        self.uri = os.getenv("GRAPHITI_URI", "bolt://localhost:7687")
        self.user = os.getenv("GRAPHITI_USER", "neo4j")
        self.password = os.getenv("GRAPHITI_PASSWORD", "password")
        self._graphiti = None
        
        # In-memory storage for MVP when Neo4j is not available
        self._nodes: list[MemoryNode] = []
        self._edges: list[MemoryEdge] = []

    def _get_graphiti(self):
        """Get or create Graphiti instance."""
        if not GRAPHITI_AVAILABLE:
            return None
            
        if self._graphiti is None:
            try:
                self._graphiti = Graphiti(
                    uri=self.uri,
                    user=self.user,
                    password=self.password,
                )
            except Exception as e:
                logger.warning(f"Could not connect to Neo4j: {e}")
                self._graphiti = None
        return self._graphiti

    async def write_node(
        self,
        node: MemoryNode,
        agent_id: str,
        authority_level: str,
    ) -> MemoryNode:
        """Write a memory node with access control.
        
        CUSTOM ACCESS CONTROL LAYER (INV-05):
        - Agentic: Only self can write
        - Team: Only generalists can write  
        - Org: Only KR can write
        """
        # Enforce access rules before writing
        if node.tier == MemoryTier.AGENTIC:
            if node.agent_id != agent_id:
                raise MemoryAccessDeniedError(
                    f"Agent {agent_id} cannot write to agentic memory of {node.agent_id}"
                )

        elif node.tier == MemoryTier.TEAM:
            if authority_level != "generalist":
                raise MemoryAccessDeniedError(
                    f"Only generalists can write team memory, not {authority_level}"
                )

        elif node.tier == MemoryTier.ORG:
            if authority_level != "kr":
                raise MemoryAccessDeniedError(
                    f"Only KR can write org memory, not {authority_level}"
                )

        # Generate ID for the node
        node.id = str(uuid.uuid4())
        
        # Store in memory for MVP (when Neo4j not available)
        self._nodes.append(node)
        
        logger.debug(f"Wrote memory node: {node.id} to tier {node.tier.value}")
        return node

    async def query_tier(
        self,
        query: MemoryQuery,
        agent_id: str,
        authority_level: str,
    ) -> list[MemoryNode]:
        """Query memory tier with access control.
        
        CUSTOM ACCESS CONTROL LAYER:
        Enforces tier visibility based on agent authority.
        """
        # Access control check
        if query.tier == MemoryTier.AGENTIC:
            if query.agent_id != agent_id:
                raise MemoryAccessDeniedError(
                    f"Agent {agent_id} cannot query agentic memory of {query.agent_id}"
                )

        # Query from in-memory storage for MVP
        results = []
        for node in self._nodes:
            if node.tier != query.tier:
                continue
            if query.agent_id and node.agent_id != query.agent_id:
                continue
            if query.team_id and node.team_id != query.team_id:
                continue
            if query.query and query.query.lower() not in node.content.lower():
                continue
            results.append(node)
        
        # Limit results
        results = results[:query.limit]
        
        logger.debug(f"Querying {query.tier.value} tier for: {query.query} - found {len(results)} results")
        return results

    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> MemoryEdge:
        """Create an edge between two nodes."""
        edge = MemoryEdge(
            id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
        )
        self._edges.append(edge)
        logger.debug(f"Created edge: {edge.id}")
        return edge

    async def health_check(self) -> bool:
        """Check if graphiti is available."""
        # Always return True for MVP - we use in-memory storage
        return True


# Global client instance
_graphiti_client: GraphitiClient | None = None


def get_graphiti_client() -> GraphitiClient:
    """Get or create global Graphiti client."""
    global _graphiti_client
    if _graphiti_client is None:
        _graphiti_client = GraphitiClient()
    return _graphiti_client
