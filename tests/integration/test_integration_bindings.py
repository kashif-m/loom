from pathlib import Path

from loom.app.config import Settings
from loom.app.dependency_injection import Container
from loom.integrations.bootstrap_bindings import bootstrap_integration_bindings


def test_bootstrap_integration_bindings(tmp_path: Path):
    container = Container(
        Settings(
            database_url=f"sqlite:///{tmp_path}/bindings.db",
            disable_scheduler=True,
            integration_profile="local",
        )
    )
    out = bootstrap_integration_bindings(container.settings, container.repositories, force=True)
    assert out["status"] in {"bootstrapped", "existing"}
    rows = container.repositories.integration_bindings.list()
    assert len(rows) >= 1
