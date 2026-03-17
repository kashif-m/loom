"""Workflow registry for Loom MVP."""
from pathlib import Path

from loguru import logger

from src.core.workflow_engine.parser import get_parser
from src.core.workflow_engine.schemas import WorkflowDefinition, WorkflowLevel, WorkflowStatus


class WorkflowRegistry:
    """In-memory workflow registry with tag indexing."""

    def __init__(self):
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._by_level: dict[WorkflowLevel, list[WorkflowDefinition]] = {
            WorkflowLevel.ORG: [],
            WorkflowLevel.TEAM: [],
            WorkflowLevel.AGENTIC: [],
        }
        self._by_tags: dict[str, list[WorkflowDefinition]] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow."""
        key = f"{workflow.id}:{workflow.version}"

        # Remove old version if exists
        if key in self._workflows:
            old = self._workflows[key]
            self._by_level[old.level].remove(old)
            for tag in old.tags:
                if tag in self._by_tags and old in self._by_tags[tag]:
                    self._by_tags[tag].remove(old)

        # Add new workflow
        self._workflows[key] = workflow
        self._by_level[workflow.level].append(workflow)

        # Index by tags
        for tag in workflow.tags:
            if tag not in self._by_tags:
                self._by_tags[tag] = []
            if workflow not in self._by_tags[tag]:
                self._by_tags[tag].append(workflow)

        logger.info(f"Registered workflow: {key} (status: {workflow.status.value})")

    def get_by_id(self, workflow_id: str, version: str | None = None) -> WorkflowDefinition | None:
        """Get workflow by ID and optional version."""
        if version:
            key = f"{workflow_id}:{version}"
            return self._workflows.get(key)

        # Get latest version
        matching = [
            w for w in self._workflows.values()
            if w.id == workflow_id
        ]
        if not matching:
            return None

        # Sort by version and return latest
        # Simple string sort works for v1, v2, etc.
        return sorted(matching, key=lambda w: w.version, reverse=True)[0]

    def get_by_level(self, level: WorkflowLevel) -> list[WorkflowDefinition]:
        """Get all workflows for a level."""
        return self._by_level[level].copy()

    def search_by_tags(self, tags: list[str]) -> list[WorkflowDefinition]:
        """Search workflows by tags (union - ANY tag match)."""
        if not tags:
            return []

        # Collect all workflows that match ANY tag (union)
        matching_workflows: dict[str, WorkflowDefinition] = {}
        
        for tag in tags:
            workflows = self._by_tags.get(tag, [])
            for wf in workflows:
                if wf.status == WorkflowStatus.ACTIVE and wf.id not in matching_workflows:
                    matching_workflows[wf.id] = wf

        return list(matching_workflows.values())

    def get_all(self) -> list[WorkflowDefinition]:
        """Get all workflows."""
        return list(self._workflows.values())

    def set_status(self, workflow_id: str, version: str, status: WorkflowStatus) -> bool:
        """Set workflow status."""
        key = f"{workflow_id}:{version}"
        if key not in self._workflows:
            return False

        self._workflows[key].status = status
        logger.info(f"Set workflow {key} status to {status.value}")
        return True

    def load_from_directory(self, directory: Path) -> int:
        """Load all workflows from a directory."""
        count = 0
        parser = get_parser()

        for md_file in directory.rglob("*.md"):
            workflow = parser.parse_file(md_file)
            if workflow:
                self.register(workflow)
                count += 1

        logger.info(f"Loaded {count} workflows from {directory}")
        return count


# Global registry instance
_registry: WorkflowRegistry | None = None


def get_registry() -> WorkflowRegistry:
    """Get or create global registry."""
    global _registry
    if _registry is None:
        _registry = WorkflowRegistry()
    return _registry
