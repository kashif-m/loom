from __future__ import annotations

import argparse

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from loom.app.config import load_settings, sanitized_runtime_config, validate_settings
from loom.app.dependency_injection import Container
from loom.app.security_middleware import install_security_headers
from loom.app.startup_checks import check_connectors
from loom.ingress.openclaw_adapter import build_router
from loom.ingress.admin_adapter import build_admin_router
from loom.ui.router import build_ui_router, mount_ui


def build_app() -> FastAPI:
    settings = load_settings()
    validate_settings(settings)
    container = Container(settings)

    app = FastAPI(title="Loom")
    app.state.container = container
    install_security_headers(app)

    @app.on_event("startup")
    def on_startup() -> None:
        missing = check_connectors(
            strict=settings.strict_connectors,
            opencode_cmd=settings.opencode_cmd,
        )
        if missing:
            raise RuntimeError(f"missing required connector commands: {', '.join(missing)}")
        container.startup()

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        container.shutdown()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "env": settings.env}

    @app.get("/runtime-config")
    def runtime_config() -> dict[str, object]:
        return sanitized_runtime_config(settings)

    @app.get("/", include_in_schema=False)
    def root_redirect():
        return RedirectResponse(url="/ui")

    app.include_router(build_router(container))
    app.include_router(build_admin_router(container))
    app.include_router(build_ui_router(container))
    mount_ui(app)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Loom")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    validate_settings(settings)

    if args.health:
        print("ok")
        return

    if args.serve:
        uvicorn.run("loom.app.main:build_app", host=settings.host, port=settings.port, factory=True)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
