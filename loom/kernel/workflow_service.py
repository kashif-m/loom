from __future__ import annotations


class WorkflowService:
    def __init__(self, workflow_registry, compiler_service):
        self.workflow_registry = workflow_registry
        self.compiler_service = compiler_service

    def publish(self, metadata, markdown_doc, activate=True):
        self.compiler_service.publish_from_markdown(metadata, markdown_doc, activate=activate)
