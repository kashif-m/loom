import pytest
from fastapi import HTTPException

from loom.app.config import Settings
from loom.ui.security import require_role, resolve_user, validate_csrf


def test_resolve_user_none_mode_defaults_admin():
    user = resolve_user(Settings(ui_auth_mode="none"), authorization=None, x_loom_role=None)
    assert user.role == "admin"


def test_resolve_user_token_mode():
    settings = Settings(
        ui_auth_mode="token",
        viewer_token="viewer",
        operator_token="operator",
        admin_token="admin",
    )
    user = resolve_user(settings, authorization="Bearer operator", x_loom_role=None)
    assert user.role == "operator"


def test_require_role_blocks():
    with pytest.raises(HTTPException):
        require_role(resolve_user(Settings(ui_auth_mode="none"), None, "viewer"), "operator")


def test_csrf_validation():
    validate_csrf("a", "a")
    with pytest.raises(HTTPException):
        validate_csrf("a", "b")
