"""LLM client for Loom MVP using LiteLLM + Instructor."""
import os
from typing import Any, TypeVar

import instructor
import litellm
from loguru import logger
from pydantic import BaseModel

from src.core.llm.models import ModelRole
from src.core.llm.schemas import Message, Tool

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """LLM client using LiteLLM proxy with Instructor for structured outputs."""

    def __init__(self):
        self.base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
        self.api_key = os.getenv("LITELLM_API_KEY", "sk-loom-master-key")
        
        # Get base model and ensure openai/ prefix
        base_model = os.getenv("MODEL", "open-large")
        if not base_model.startswith("openai/"):
            self.model = f"openai/{base_model}"
        else:
            self.model = base_model

        # Create instructor client from litellm
        # This returns a patched client that supports response_model
        self.instructor_client = instructor.from_litellm(litellm.acompletion)
        
        # Configure instructor
        self.client_kwargs = {
            "api_base": self.base_url,
            "api_key": self.api_key,
        }

        logger.info(f"LLMClient initialized with model: {self.model}")

    def _get_model_for_role(self, role: ModelRole) -> str:
        """Get model name for role.
        
        For MVP, we use the same model for all roles.
        In production, you might configure different models per role.
        """
        return self.model

    async def complete(
        self,
        role: ModelRole,
        messages: list[Message],
        tools: list[Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Complete a chat completion request (unstructured).
        
        Args:
            role: Model role (fast/reasoning)
            messages: List of messages
            tools: Optional tools for the model
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Response content as string
        """
        model = self._get_model_for_role(role)

        # Convert messages to litellm format
        litellm_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role}
            if msg.content:
                msg_dict["content"] = msg.content
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            litellm_messages.append(msg_dict)

        # Convert tools to litellm format
        litellm_tools = None
        if tools:
            litellm_tools = [tool.model_dump() for tool in tools]

        logger.debug(f"Calling {model} with {len(litellm_messages)} messages")

        try:
            # Use raw litellm for unstructured outputs
            response = await litellm.acompletion(
                model=model,
                messages=litellm_messages,
                tools=litellm_tools,
                temperature=temperature,
                max_tokens=max_tokens,
                **self.client_kwargs,
            )

            # Log response
            if response.choices:
                message = response.choices[0].message
                logger.debug(
                    f"LLM Response: model={response.model}, "
                    f"tokens={response.usage.total_tokens if response.usage else 'N/A'}"
                )
                return message.content or ""

            return ""

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def complete_structured(
        self,
        role: ModelRole,
        messages: list[Message],
        response_model: type[T],
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> T:
        """Complete with structured output using Instructor.
        
        This uses Instructor to get validated Pydantic models back.
        Automatic retries on validation failure.
        
        Args:
            role: Model role (fast/reasoning)
            messages: List of messages
            response_model: Pydantic model class for the response
            temperature: Sampling temperature
            max_retries: Maximum retries on validation failure
            
        Returns:
            Validated Pydantic model instance
        """
        model = self._get_model_for_role(role)

        # Convert messages to litellm format
        litellm_messages = []
        for msg in messages:
            msg_dict = {"role": msg.role}
            if msg.content:
                msg_dict["content"] = msg.content
            litellm_messages.append(msg_dict)

        logger.debug(
            f"Instructor structured call: model={model}, "
            f"response_model={response_model.__name__}, "
            f"retries={max_retries}"
        )

        try:
            # Use instructor client for structured outputs
            # AsyncInstructor has a chat.completions.create method
            response = await self.instructor_client.chat.completions.create(
                model=model,
                messages=litellm_messages,
                temperature=temperature,
                response_model=response_model,
                max_retries=max_retries,
                **self.client_kwargs,
            )

            logger.info(
                f"Structured response received: {response_model.__name__}"
            )
            logger.debug(f"Response: {response.model_dump_json()[:500]}...")

            return response

        except Exception as e:
            logger.error(f"Structured LLM call failed: {e}")
            raise


# Global client instance
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def complete(
    role: ModelRole,
    messages: list[Message],
    tools: list[Tool] | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str:
    """Convenience function for unstructured LLM calls."""
    client = get_llm_client()
    return await client.complete(role, messages, tools, temperature, max_tokens)


async def complete_structured(
    role: ModelRole,
    messages: list[Message],
    response_model: type[T],
    temperature: float = 0.7,
    max_retries: int = 3,
) -> T:
    """Convenience function for structured LLM calls with Instructor."""
    client = get_llm_client()
    return await client.complete_structured(
        role, messages, response_model, temperature, max_retries
    )
