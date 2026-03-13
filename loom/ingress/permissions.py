from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CallerContext:
    role: str


def ensure_admin(caller: CallerContext) -> None:
    if caller.role != "admin":
        raise PermissionError("admin role required")
