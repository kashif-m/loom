from __future__ import annotations

import subprocess
from pathlib import Path

from loom.security.policy_guard import CommandSafetyPolicy


class GitAdapter:
    def __init__(self, cwd: str, safety: CommandSafetyPolicy | None = None):
        self.cwd = Path(cwd)
        self.safety = safety or CommandSafetyPolicy()

    def _run(self, *args: str) -> str:
        command = ["git", *args]
        self.safety.validate(command)
        proc = subprocess.run(command, cwd=self.cwd, check=True, text=True, capture_output=True)
        return proc.stdout.strip()

    def create_branch(self, branch: str) -> str:
        return self._run("checkout", "-b", branch)

    def checkout(self, ref: str) -> str:
        return self._run("checkout", ref)

    def stage_all(self) -> str:
        return self._run("add", "-A")

    def commit(self, message: str) -> str:
        return self._run("commit", "-m", message)

    def push(self, branch: str, remote: str = "origin") -> str:
        return self._run("push", remote, branch)
