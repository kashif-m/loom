#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from loom.app.config import load_settings, validate_settings
from loom.app.dependency_injection import Container
from loom.models import WorkflowDefinitionMetadata, WorkflowMarkdownDocument


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a workflow markdown file into Loom")
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--version", required=True, type=int)
    parser.add_argument("--title", required=True)
    parser.add_argument("--domain-pack", default="custom")
    parser.add_argument("--intent-group", required=True)
    parser.add_argument("--markdown-file", required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    markdown_path = Path(args.markdown_file)
    if not markdown_path.exists():
        raise SystemExit(f"markdown file not found: {markdown_path}")

    settings = load_settings()
    validate_settings(settings)
    container = Container(settings)

    metadata = WorkflowDefinitionMetadata(
        workflow_id=args.workflow_id,
        version=args.version,
        title=args.title,
        domain_pack=args.domain_pack,
        intent_group=args.intent_group,
    )
    doc = WorkflowMarkdownDocument(
        workflow_id=args.workflow_id,
        version=args.version,
        markdown=markdown_path.read_text(encoding="utf-8"),
    )

    container.compiler_service.publish_from_markdown(metadata, doc, activate=args.activate)
    print(
        "published",
        {
            "workflow_id": args.workflow_id,
            "version": args.version,
            "activate": args.activate,
            "database_url": settings.database_url,
        },
    )


if __name__ == "__main__":
    main()
