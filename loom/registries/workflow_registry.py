from __future__ import annotations

from loom.models import CompiledWorkflowIR, WorkflowDefinitionMetadata, WorkflowMarkdownDocument


class WorkflowRegistry:
    def __init__(self, repositories):
        self.repositories = repositories

    def create_draft(self, metadata: WorkflowDefinitionMetadata, markdown_doc: WorkflowMarkdownDocument) -> None:
        existing = self.repositories.workflows.get_version(metadata.workflow_id, metadata.version)
        if existing:
            existing_metadata = self._canonical_metadata(existing.get("metadata") or {})
            new_metadata = self._canonical_metadata(metadata.model_dump(mode="json"))
            existing_markdown = existing.get("markdown") or ""
            if existing_metadata != new_metadata or existing_markdown != markdown_doc.markdown:
                raise ValueError(
                    "workflow versions are immutable once published. "
                    f"Create a new version for {metadata.workflow_id}."
                )
            return
        self.repositories.workflows.create_version(
            metadata.workflow_id,
            metadata.version,
            metadata.model_dump(mode="json"),
            markdown_doc.markdown,
            status="draft",
        )

    @staticmethod
    def _canonical_metadata(payload: dict) -> dict:
        # Ignore mutable/runtime-managed metadata fields (for idempotent republish
        # of the same workflow version) while keeping semantic identity strict.
        return {
            "workflow_id": payload.get("workflow_id"),
            "version": payload.get("version"),
            "title": payload.get("title"),
            "domain_pack": payload.get("domain_pack"),
            "intent_group": payload.get("intent_group"),
            "selection_hints": payload.get("selection_hints") or [],
        }

    def publish_compiled(self, workflow_id: str, version: int, compiled_ir: CompiledWorkflowIR) -> None:
        self.repositories.workflows.update_version(
            workflow_id,
            version,
            compiled_ir=compiled_ir.model_dump(mode="json"),
        )

    def activate_version(self, workflow_id: str, version: int) -> None:
        for v in self.repositories.workflows.list_versions(workflow_id):
            if v["status"] == "active":
                self.repositories.workflows.update_version(workflow_id, v["version"], status="deprecated")
        self.repositories.workflows.update_version(workflow_id, version, status="active")

    def deprecate_version(self, workflow_id: str, version: int) -> None:
        self.repositories.workflows.update_version(workflow_id, version, status="deprecated")

    def archive_version(self, workflow_id: str, version: int) -> None:
        self.repositories.workflows.update_version(workflow_id, version, status="archived")

    def get_active(self, workflow_id: str) -> dict | None:
        return self.repositories.workflows.get_active_version(workflow_id)

    def get_version(self, workflow_id: str, version: int) -> dict | None:
        return self.repositories.workflows.get_version(workflow_id, version)

    def list_active(self) -> list[dict]:
        return self.repositories.workflows.list_active()

    def list_all(self) -> list[dict]:
        return self.repositories.workflows.list_all()

    def list_versions(self, workflow_id: str) -> list[dict]:
        return self.repositories.workflows.list_versions(workflow_id)

    def rollback(self, workflow_id: str, target_version: int) -> None:
        target = self.get_version(workflow_id, target_version)
        if not target:
            raise KeyError(f"workflow version not found: {workflow_id}:{target_version}")
        self.activate_version(workflow_id, target_version)
