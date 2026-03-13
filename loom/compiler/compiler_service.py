from __future__ import annotations

from loom.models import WorkflowDefinitionMetadata, WorkflowMarkdownDocument


class CompilerService:
    def __init__(self, workflow_registry, parser, compiler, ir_validator):
        self.workflow_registry = workflow_registry
        self.parser = parser
        self.compiler = compiler
        self.ir_validator = ir_validator

    def publish_from_markdown(
        self,
        metadata: WorkflowDefinitionMetadata,
        markdown_doc: WorkflowMarkdownDocument,
        activate: bool = True,
    ) -> None:
        self.workflow_registry.create_draft(metadata, markdown_doc)

        parsed = self.parser.parse(markdown_doc.markdown)
        compiled = self.compiler.compile(metadata.workflow_id, metadata.version, parsed)
        errors = self.ir_validator.validate(compiled)
        if errors:
            raise ValueError("invalid compiled workflow: " + "; ".join(errors))

        self.workflow_registry.publish_compiled(metadata.workflow_id, metadata.version, compiled)
        if activate:
            self.workflow_registry.activate_version(metadata.workflow_id, metadata.version)
