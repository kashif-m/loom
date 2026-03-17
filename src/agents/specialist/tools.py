"""Tool integration for specialist agents using OpenFang."""
import os
from typing import Any

import httpx
from loguru import logger

from src.exceptions import OpenFangConnectionError


class OpenFangClient:
    """Client for OpenFang tool registry."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv("OPENFANG_URL", "http://localhost:8001")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools."""
        try:
            response = await self.client.get("/tools")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list tools: {e}")
            raise OpenFangConnectionError(f"OpenFang unreachable: {e}")

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool via OpenFang.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        try:
            logger.info(f"Executing tool: {tool_name}")

            response = await self.client.post(
                f"/tools/{tool_name}/execute",
                json=tool_input,
            )
            response.raise_for_status()

            result = response.json()
            logger.debug(f"Tool {tool_name} executed successfully")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "error": True,
                "message": str(e),
            }

    async def get_tool_schema(self, tool_name: str) -> dict[str, Any] | None:
        """Get tool schema for LLM."""
        try:
            response = await self.client.get(f"/tools/{tool_name}")
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.HTTPError:
            return None


# Global client instance
_openfang_client: OpenFangClient | None = None


def get_openfang_client() -> OpenFangClient:
    """Get or create global OpenFang client."""
    global _openfang_client
    if _openfang_client is None:
        _openfang_client = OpenFangClient()
    return _openfang_client


def tool_to_openai_format(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenFang tool to OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
        }
    }
