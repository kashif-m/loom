"""LLM models for Loom MVP."""
from enum import Enum


class ModelRole(str, Enum):
    """Model role enum."""
    FAST = "fast"
    REASONING = "reasoning"
    LOCAL = "local"
