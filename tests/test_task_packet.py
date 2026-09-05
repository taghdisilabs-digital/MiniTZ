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
    assert "auto feeder owns github/drive publication and canonical state transition" in packet.lower()


def test_resume_packet_is_compact_delta_not_full_contract(tmp_path: Path):
    task = state.TaskRecord("D02-01", "hard_creation", "Open-world streaming and continuity", "PENDING", (), "post_d01")
    capsule = tmp_path / "D02-01.json"
    packet = packets.compile_resume_packet(task, capsule)
    assert "RESUME_EXISTING_TASK_SESSION" in packet
    assert "D02-01" in packet
    assert str(capsule) in packet
    assert "--- ACTIVE CONTRACT ---" not in packet
    assert len(packet.encode()) < 1800


def test_task_memory_capsule_is_bounded_and_project_aware(tmp_path: Path):
    repo = tmp_path / "repo"
    project = repo / "projects/biella-games"
    project.mkdir(parents=True)
    (repo / ".git").mkdir()
    task = state.TaskRecord("D02-01", "hard_creation", "Open-world streaming and continuity", "PENDING", (), "post_d01")
    capsule = packets.build_task_memory_capsule(
        task,
        project,
        session_id="session-d02",
        summary="world streaming implementation partially validated",
        evidence=["build pass", "runtime failed at nav readiness"],
        dirty_paths=["Source/BiellaGames/Private/BiellaWorldContinuity.cpp", "tests/run_d02_01.py"],
    )
    assert capsule["task_id"] == "D02-01"
    assert capsule["project_root"] == str(project)
    assert capsule["session_id"] == "session-d02"
    assert capsule["dirty_paths"] == ["Source/BiellaGames/Private/BiellaWorldContinuity.cpp", "tests/run_d02_01.py"]
    assert len(__import__("json").dumps(capsule).encode()) < 8192


def test_task_packet_autonomously_provides_routine_needs(tmp_path: Path):
    repo = tmp_path / "repo"; (repo / "docs/project-state").mkdir(parents=True)
    active = "task:\n  id: D02-01\n  project: Biella Games\n  section: post_d01\n  class: hard_creation\n  title: Streaming\n  status: PENDING\n"
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text(active, encoding="utf-8")
    task = state.TaskRecord("D02-01", "hard_creation", "Streaming", "PENDING", (), "post_d01")
    production = state.ProductionState(Path("/repo/projects/biella-games"), "IN_PROGRESS", "post_d01", "D02-01", [state.SectionRecord("post_d01", "Continuation", "IN_PROGRESS", [task])])
    packet = packets.compile_task_packet(repo, production, task).lower()
    assert "resolve routine task needs autonomously" in packet
    assert "install/configure task-scoped dependencies" in packet
    assert "do not stop for confirmation" in packet
    assert "return continue" in packet
    assert "owner_decision" not in packet
    assert "external_dependency" not in packet


def test_resume_packet_keeps_autonomy_without_reinjecting_full_contract(tmp_path: Path):
    task = state.TaskRecord("D02-01", "hard_creation", "Streaming", "PENDING", (), "post_d01")
    packet = packets.compile_resume_packet(task, tmp_path / "D02-01.json").lower()
    assert "resolve routine task needs autonomously" in packet
    assert "do not stop for confirmation" in packet
    assert "active contract" in packet
    assert "return continue" in packet


def test_section_planner_never_creates_approval_gate_tasks():
    task = state.TaskRecord("D02-01", "hard_creation", "Streaming", "PENDING", (), "post_d01")
    production = state.ProductionState(Path("/repo/projects/biella-games"), "IN_PROGRESS", "post_d01", "D02-01", [state.SectionRecord("post_d01", "Continuation", "IN_PROGRESS", [task])])
    packet = packets.compile_section_packet(production, production.sections[0], audit=True).lower()
    assert "do not create approval" in packet
    assert "owner-decision" in packet
    assert "executable missing work" in packet
