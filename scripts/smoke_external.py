from __future__ import annotations

from loom.app.config import load_settings, validate_settings


if __name__ == "__main__":
    s = load_settings()
    validate_settings(s)
    print("settings validated for external integrations")
