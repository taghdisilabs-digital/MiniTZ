from __future__ import annotations

import json
import os
from pathlib import Path

from minitz_os.__main__ import main
from minitz_os.operator import Doctor, OperatorSurface


ROOT = Path(__file__).resolve().parents[1]
TASK_PROGRAM = Path(
    os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/state/task-program/TASK_PROGRAM.json")
)


def test_surface_has_one_discoverable_route_for_every_normal_user_area(tmp_path: Path) -> None:
    snapshot = OperatorSurface(ROOT, tmp_path, TASK_PROGRAM).snapshot()

    assert snapshot["schema"] == "minitz.operator-surface/v1"
    assert snapshot["discoverable_command"] == "minitz dashboard"
    assert {section["key"] for section in snapshot["sections"]} == {
        "tasks",
        "resources",
        "files",
        "apps",
        "browser/computer",
        "memory",
        "health",
        "updates",
        "recovery",
        "evidence",
    }
    assert all(section["title"] and section["description"] and section["command"] for section in snapshot["sections"])
    assert snapshot["evidence"]["evidence_ref"] == "evidence://minitz/operator-surface/v1"
    assert len(snapshot["surface_sha256"]) == 64


def test_doctor_reports_actionable_missing_dependencies_without_false_ready(tmp_path: Path) -> None:
    report = Doctor(ROOT, tmp_path, TASK_PROGRAM).report().as_dict()
    checks = {check["title"]: check for check in report["checks"]}

    assert checks["Canonical source"]["availability"] == "Ready"
    assert checks["Task authority"]["availability"] == "Ready"
    assert checks["Runtime qualification"]["reason_code"] == "QUALIFICATION_MISSING"
    assert checks["Runtime qualification"]["action"]
    assert checks["Capability resources"]["reason_code"] == "CAPABILITY_RESOURCES_UNOBSERVED"
    assert report["overall_availability"] != "Ready"


def test_doctor_redacts_qualification_payloads_and_reads_state_only(tmp_path: Path) -> None:
    qualification = tmp_path / "qualification"
    qualification.mkdir()
    (qualification / "sandbox-foundation.json").write_text(
        json.dumps({"state": "NEEDS_ATTENTION", "detail": "sk-proj-raw-secret-value-should-not-appear"}),
        encoding="utf-8",
    )

    report = Doctor(ROOT, tmp_path, TASK_PROGRAM).report().as_dict()
    encoded = json.dumps(report, sort_keys=True)

    assert "QUALIFICATION_STATE_UNKNOWN" in encoded
    assert "sk-proj-raw-secret-value-should-not-appear" not in encoded
    assert "detail" not in encoded


def test_cli_dashboard_and_doctor_are_discoverable(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setenv("MINITZ_SOURCE_ROOT", str(ROOT))
    monkeypatch.setenv("MINITZ_STATE_ROOT", str(tmp_path))
    monkeypatch.setenv("MINITZ_TASK_PROGRAM_PATH", str(TASK_PROGRAM))

    assert main([]) == 0
    dashboard = capsys.readouterr().out
    assert "What do you want to do?" in dashboard
    assert "Browser and computer" in dashboard
    assert "minitz doctor" in dashboard

    assert main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == "minitz.doctor/v1"
    assert report["checks"]


def test_operator_observation_does_not_mutate_task_program(tmp_path: Path) -> None:
    before = TASK_PROGRAM.read_bytes()
    OperatorSurface(ROOT, tmp_path, TASK_PROGRAM).snapshot()
    assert TASK_PROGRAM.read_bytes() == before
