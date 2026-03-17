"""Workflow file parser for Loom MVP."""
import re
from pathlib import Path

import yaml
from loguru import logger

from src.core.workflow_engine.schemas import WorkflowDefinition, WorkflowLevel, WorkflowStatus


class WorkflowParser:
    """Parser for workflow markdown files."""

    @staticmethod
    def parse_file(file_path: Path) -> WorkflowDefinition | None:
        """Parse a workflow markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            WorkflowDefinition or None if parsing fails
        """
        try:
            content = file_path.read_text()
            return WorkflowParser.parse_content(content, str(file_path))
        except Exception as e:
            logger.error(f"Failed to parse workflow file {file_path}: {e}")
            return None

    @staticmethod
    def parse_content(content: str, source_file: str | None = None) -> WorkflowDefinition | None:
        """Parse workflow content.

        Args:
            content: Markdown content
            source_file: Optional source file path

        Returns:
            WorkflowDefinition or None if parsing fails
        """
        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not frontmatter_match:
            logger.error("No YAML frontmatter found in workflow file")
            return None

        try:
            frontmatter = yaml.safe_load(frontmatter_match.group(1))
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML frontmatter: {e}")
            return None

        # Validate required fields
        required_fields = ["id", "version", "level", "trigger", "tags", "states", "success_condition", "escalate_if"]
        for field in required_fields:
            if field not in frontmatter:
                logger.error(f"Missing required field '{field}' in workflow")
                return None

        # Validate level
        level_str = frontmatter["level"]
        try:
            level = WorkflowLevel(level_str)
        except ValueError:
            logger.error(f"Invalid workflow level: {level_str}")
            return None

        # Validate status if present, default to ACTIVE
        status_str = frontmatter.get("status", "active")
        try:
            status = WorkflowStatus(status_str)
        except ValueError:
            logger.error(f"Invalid workflow status: {status_str}")
            status = WorkflowStatus.ACTIVE

        return WorkflowDefinition(
            id=frontmatter["id"],
            version=str(frontmatter["version"]),
            level=level,
            trigger=frontmatter["trigger"],
            tags=frontmatter["tags"],
            states=frontmatter["states"],
            success_condition=frontmatter["success_condition"],
            escalate_if=frontmatter["escalate_if"],
            status=status,
            source_file=source_file,
        )


# Global parser instance
_parser: WorkflowParser | None = None


def get_parser() -> WorkflowParser:
    """Get or create global parser."""
    global _parser
    if _parser is None:
        _parser = WorkflowParser()
    return _parser
