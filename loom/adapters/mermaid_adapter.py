from __future__ import annotations

from pathlib import Path


class MermaidAdapter:
    def write(self, mermaid_text: str, output_file: str) -> str:
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mermaid_text, encoding="utf-8")
        return str(path)
