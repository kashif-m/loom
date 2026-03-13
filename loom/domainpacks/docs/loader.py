from __future__ import annotations

from pathlib import Path

import yaml

from loom.models import (
    CapabilityDefinition,
    DomainPackManifest,
    PromptProfile,
    RoleDefinition,
    WorkflowDefinitionMetadata,
    WorkflowMarkdownDocument,
)


def load_docs_pack(container, base_dir: str | None = None) -> None:
    root = Path(base_dir or Path(__file__).resolve().parent)

    manifest_data = yaml.safe_load((root / "pack_manifest.yaml").read_text(encoding="utf-8"))
    container.domain_pack_registry.upsert(DomainPackManifest(**manifest_data))
    container.domain_pack_registry.activate("docs")

    roles_data = yaml.safe_load((root / "roles" / "roles.yaml").read_text(encoding="utf-8"))
    for role in roles_data["roles"]:
        container.role_registry.upsert(RoleDefinition(**role))

    capabilities_data = yaml.safe_load((root / "capabilities" / "capabilities.yaml").read_text(encoding="utf-8"))
    for cap in capabilities_data["capabilities"]:
        container.capability_registry.upsert(CapabilityDefinition(**cap))

    policies_data = yaml.safe_load((root / "policies" / "policies.yaml").read_text(encoding="utf-8"))
    for policy in policies_data["policies"]:
        from loom.models import PolicyDefinition

        container.policy_registry.upsert(PolicyDefinition(**policy))

    prompts_data = yaml.safe_load((root / "prompts" / "profiles.yaml").read_text(encoding="utf-8"))
    for prompt in prompts_data["prompts"]:
        container.prompt_registry.upsert(PromptProfile(**prompt))

    workflow_map = {
        "task_authoring.md": ("docs_task_authoring", "task_authoring", "Docs Task Authoring"),
        "development.md": ("docs_development", "development", "Docs Development"),
        "pr_review_addressal.md": (
            "docs_pr_review_addressal",
            "pr_review_addressal",
            "PR Review Addressal",
        ),
        "pr_promotion.md": ("docs_pr_promotion", "pr_promotion", "PR Promotion"),
    }

    for fname, (wf_id, intent, title) in workflow_map.items():
        markdown = (root / "workflows" / fname).read_text(encoding="utf-8")
        metadata = WorkflowDefinitionMetadata(
            workflow_id=wf_id,
            version=1,
            title=title,
            domain_pack="docs",
            intent_group=intent,
        )
        doc = WorkflowMarkdownDocument(workflow_id=wf_id, version=1, markdown=markdown)
        container.compiler_service.publish_from_markdown(metadata, doc, activate=True)
