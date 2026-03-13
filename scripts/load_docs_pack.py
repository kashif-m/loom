#!/usr/bin/env python3
from __future__ import annotations

from loom.app.config import load_settings, validate_settings
from loom.app.dependency_injection import Container
from loom.domainpacks.docs.loader import load_docs_pack


def main() -> None:
    settings = load_settings()
    validate_settings(settings)
    container = Container(settings)
    load_docs_pack(container)
    print("Docs pack loaded into", settings.database_url)


if __name__ == "__main__":
    main()
