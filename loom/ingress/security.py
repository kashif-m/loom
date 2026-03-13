from __future__ import annotations

from fastapi import Header, HTTPException


def require_api_key(enabled: bool, expected: str, incoming: str | None, area: str) -> None:
    if not enabled:
        return
    if not incoming or incoming != expected:
        raise HTTPException(status_code=401, detail=f"unauthorized {area} request")


def ingress_auth(enabled: bool, expected: str):
    def _check(x_api_key: str | None = Header(default=None)) -> None:
        require_api_key(enabled, expected, x_api_key, "ingress")

    return _check


def admin_auth(enabled: bool, expected: str):
    def _check(x_api_key: str | None = Header(default=None)) -> None:
        require_api_key(enabled, expected, x_api_key, "admin")

    return _check
