from __future__ import annotations

import json
import subprocess

from loom.security.policy_guard import CommandSafetyPolicy


class GhAdapter:
    def __init__(self, safety: CommandSafetyPolicy | None = None):
        self.safety = safety or CommandSafetyPolicy()

    def _run(self, *args: str) -> str:
        command = ["gh", *args]
        self.safety.validate(command)
        proc = subprocess.run(command, check=True, text=True, capture_output=True)
        return proc.stdout.strip()

    def pr_create(self, title: str, body: str, base: str, head: str) -> str:
        return self._run("pr", "create", "--title", title, "--body", body, "--base", base, "--head", head)

    def pr_read(self, number: int) -> dict:
        out = self._run("pr", "view", str(number), "--json", "number,title,body,state")
        return json.loads(out)

    def pr_comments(self, number: int) -> list[dict]:
        out = self._run("api", f"repos/:owner/:repo/issues/{number}/comments")
        return json.loads(out)

    def pr_review_comments(self, number: int) -> list[dict]:
        out = self._run("api", f"repos/:owner/:repo/pulls/{number}/comments")
        return json.loads(out)

    def pr_merge(self, number: int, method: str = "squash") -> str:
        return self._run("pr", "merge", str(number), f"--{method}")
