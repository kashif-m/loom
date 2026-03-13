from pathlib import Path

from loom.adapters.mermaid_adapter import MermaidAdapter
from loom.adapters.plantuml_adapter import PlantUMLAdapter


def test_mermaid_adapter_writes_file(tmp_path: Path):
    adapter = MermaidAdapter()
    out = adapter.write("flowchart LR\nA-->B", str(tmp_path / "topology.mmd"))
    assert Path(out).exists()


def test_plantuml_adapter_handles_missing_binary(tmp_path: Path):
    adapter = PlantUMLAdapter()
    src = tmp_path / "x.puml"
    src.write_text("@startuml\nAlice->Bob: hi\n@enduml", encoding="utf-8")
    result = adapter.render(str(src), str(tmp_path))
    assert "ok" in result
