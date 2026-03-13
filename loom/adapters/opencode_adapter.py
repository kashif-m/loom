from __future__ import annotations

import json
import subprocess
from pathlib import Path


class OpenCodeAdapter:
    def __init__(self, root: str, cmd: str = "opencode", enabled: bool = False):
        self.root = Path(root)
        self.cmd = cmd
        self.enabled = enabled

    def collect_context(self, include_extensions: tuple[str, ...] = (".md", ".mdx", ".py", ".yaml")) -> dict:
        if self.enabled:
            try:
                proc = subprocess.run(
                    [self.cmd, "context", "--format", "json", str(self.root)],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                data = json.loads(proc.stdout)
                return {
                    "root": str(self.root),
                    "files": data.get("files", [])[:1000],
                    "source": "opencode",
                }
            except Exception:
                pass

        files = []
        for p in self.root.rglob("*"):
            if p.is_file() and p.suffix in include_extensions:
                files.append(str(p.relative_to(self.root)))
        return {"root": str(self.root), "files": files[:500], "source": "filesystem-fallback"}
