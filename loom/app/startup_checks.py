from __future__ import annotations

import shutil


def check_connectors(strict: bool = False, opencode_cmd: str = "opencode") -> list[str]:
    required = ["git"]
    optional = ["gh", "plantuml", opencode_cmd]
    missing = [cmd for cmd in required if shutil.which(cmd) is None]
    if strict:
        missing.extend([cmd for cmd in optional if shutil.which(cmd) is None])
    return missing
