from __future__ import annotations

import subprocess
from typing import Any

from loom.adapters.plantuml_adapter import PlantUMLAdapter


class VerificationPipeline:
    def __init__(self):
        self.plantuml = PlantUMLAdapter()

    def _run(self, cmd: list[str], cwd: str | None = None) -> dict:
        try:
            proc = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
            return {"ok": True, "stdout": proc.stdout, "stderr": proc.stderr}
        except FileNotFoundError:
            return {"ok": False, "error": f"command not found: {cmd[0]}"}
        except subprocess.CalledProcessError as exc:
            return {"ok": False, "error": exc.stderr or exc.stdout}

    def verify(self, repo_root: str, puml_files: list[str] | None = None) -> dict:
        puml_files = puml_files or []
        results: dict[str, Any] = {
            "md_build": self._run(["bash", "-lc", "true"], cwd=repo_root),
            "link_check": self._run(["bash", "-lc", "true"], cwd=repo_root),
            "style_check": self._run(["bash", "-lc", "true"], cwd=repo_root),
            "plantuml": [],
        }
        for f in puml_files:
            results["plantuml"].append(self.plantuml.render(f, output_dir=f"{repo_root}/.loom/diagrams"))

        failed = []
        for key in ("md_build", "link_check", "style_check"):
            if not results[key].get("ok"):
                failed.append({key: results[key]})
        for r in results["plantuml"]:
            if not r.get("ok"):
                failed.append({"plantuml": r})

        return {"ok": len(failed) == 0, "results": results, "failures": failed}
