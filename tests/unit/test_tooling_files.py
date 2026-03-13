from pathlib import Path


def test_bootstrap_and_compose_files_exist():
    root = Path(__file__).resolve().parents[2]
    assert (root / "scripts" / "bootstrap_local_stack.sh").exists()
    assert (root / "scripts" / "bootstrap_tools.sh").exists()
    assert (root / "deploy" / "docker-compose.local.yml").exists()
    assert (root / "docs" / "ops" / "tool_bootstrap_matrix.md").exists()
