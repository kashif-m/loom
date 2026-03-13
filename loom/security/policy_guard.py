from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CommandSafetyPolicy:
    allowed_prefixes: list[tuple[str, ...]] = field(
        default_factory=lambda: [
            ("git",),
            ("gh",),
            ("plantuml",),
            ("opencode",),
        ]
    )
    denied_exact: set[str] = field(
        default_factory=lambda: {
            "rm -rf /",
            "git reset --hard",
            "shutdown now",
        }
    )

    def validate(self, command: list[str]) -> None:
        joined = " ".join(command).strip()
        if joined in self.denied_exact:
            raise PermissionError(f"command denied: {joined}")

        command_tuple = tuple(command)
        for prefix in self.allowed_prefixes:
            if command_tuple[: len(prefix)] == prefix:
                return
        raise PermissionError(f"command prefix not allowed: {joined}")
