from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import biella_production_state as state

MODULE = LOCAL_AI / "biella_task_packet.py"
spec = importlib.util.spec_from_file_location("biella_task_packet", MODULE)
assert spec and spec.loader
packets = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = packets
spec.loader.exec_module(packets)


def test_packet_contains_exact_active_contract_and_resource_rule(tmp_path: Path):
    repo = tmp_path / "repo"; (repo / "docs/project-state").mkdir(parents=True)
    active = "task:\n  id: D01-030\n  project: Biella Games\n  section: demo01\n  class: hard\n  title: Rival combat\n  status: PENDING\n"
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text(active, encoding="utf-8")
    task = state.TaskRecord("D01-030", "hard", "Rival combat", "PENDING", (), "demo01")
    section = state.SectionRecord("demo01", "Demo 01", "IN_PROGRESS", [task])
    production = state.ProductionState(Path("/repo/projects/biella-games"), "IN_PROGRESS", "demo01", "D01-030", [section])
    packet = packets.compile_task_packet(repo, production, task)
    assert "TASK: D01-030 [hard] Rival combat" in packet
    assert "04_BIELLA_ACTIVE_TASK.md" in packet
    assert active.strip() in packet
    assert "biella resource route <capability>" in packet
    assert "/usage" not in packet
    assert "quota" in packet.lower()
