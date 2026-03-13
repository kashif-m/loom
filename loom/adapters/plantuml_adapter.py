from __future__ import annotations

import subprocess
from pathlib import Path


class PlantUMLAdapter:
    def render(self, source_file: str, output_dir: str) -> dict:
        src = Path(source_file)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                ["plantuml", "-tpng", "-o", str(out), str(src)],
                check=True,
                text=True,
                capture_output=True,
            )
            return {"ok": True, "stdout": proc.stdout, "stderr": proc.stderr}
        except FileNotFoundError:
            return {"ok": False, "error": "plantuml command not found"}
        except subprocess.CalledProcessError as exc:
            return {"ok": False, "error": exc.stderr or exc.stdout}
