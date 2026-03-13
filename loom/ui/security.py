from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Header, HTTPException


ROLE_ORDER = {"viewer": 0, "operator": 1, "admin": 2}


@dataclass(slots=True)
class UIUser:
    role: str
    identity: str


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix) :].strip()


def resolve_user(settings, authorization: str | None, x_loom_role: str | None) -> UIUser:
    if settings.ui_auth_mode == "none":
        role = x_loom_role or "admin"
        if role not in ROLE_ORDER:
            role = "viewer"
        return UIUser(role=role, identity=f"local:{role}")

    token = _parse_bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="missing bearer token")

    if token == settings.admin_token:
        return UIUser(role="admin", identity="token:admin")
    if token == settings.operator_token:
        return UIUser(role="operator", identity="token:operator")
    if token == settings.viewer_token:
        return UIUser(role="viewer", identity="token:viewer")
    raise HTTPException(status_code=401, detail="invalid bearer token")


def require_role(user: UIUser, minimum: str) -> None:
    if ROLE_ORDER[user.role] < ROLE_ORDER[minimum]:
        raise HTTPException(status_code=403, detail=f"requires role {minimum}+")


def ui_user_dependency(settings):
    def _dep(
        authorization: str | None = Header(default=None),
        x_loom_role: str | None = Header(default=None),
    ) -> UIUser:
        return resolve_user(settings, authorization, x_loom_role)

    return _dep


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def validate_csrf(header_token: str | None, cookie_token: str | None) -> None:
    if not header_token or not cookie_token or header_token != cookie_token:
        raise HTTPException(status_code=403, detail="csrf token mismatch")
