from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
MODULE = LOCAL_AI / "biella_production_runner.py"
spec = importlib.util.spec_from_file_location("minitz_commander_evidence_runner", MODULE)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class _FakeStdin:
    def write(self, _value: str) -> None:
        return None

    def close(self) -> None:
        return None


class _FakeProcess:
    _next_pid = 61000

    def __init__(self, *, stdout_handle: Any, stdout_payload: str) -> None:
        type(self)._next_pid += 1
        self.pid = type(self)._next_pid
        self.stdin = _FakeStdin()
        self._returncode = 0
        stdout_handle.write(stdout_payload)
        stdout_handle.flush()

    def poll(self) -> int:
        return self._returncode


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Any]:
    repo = tmp_path / "repo"
    (repo / "ops/workstation").mkdir(parents=True)
    (repo / "ops/workstation/provider-registry.json").write_text(json.dumps({
        "schema": "biella.provider_registry/v1",
        "providers": {"groq": {"required_env": ["GROQ_API_KEY"], "default_model": "qwen"}},
        "routes": {"llm.fast": ["groq"]},
    }), encoding="utf-8")
    project = repo / "projects/game"
    project.mkdir(parents=True)
    runtime = tmp_path / "runtime"
    (runtime / "memory").mkdir(parents=True)
    capsule = runtime / "task-memory/T.json"
    capsule.parent.mkdir(parents=True)
    capsule.write_text(json.dumps({"task_id": "T", "title": "Task", "summary": "Current"}), encoding="utf-8")
    projection = runtime / "memory/current-task.json"
    projection.write_text(json.dumps({"task_id": "T", "failures": [], "source_refs": []}), encoding="utf-8")
    task = runner.state.TaskRecord("T", "hard", "Task", "PENDING")
    return repo, project, runtime, capsule, projection, task


def test_commander_raw_capture_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    source = tmp_path / "lane.stdout.json"
    source.write_bytes(b"first provider output\n")
    first = runner._commander_output_evidence(source, prefix="raw_result")
    source.write_bytes(b"second provider output\n")
    second = runner._commander_output_evidence(source, prefix="raw_result")

    first_path = Path(first["raw_result_path"])
    second_path = Path(second["raw_result_path"])
    assert first_path != second_path
    assert first_path.read_bytes() == b"first provider output\n"
    assert second_path.read_bytes() == b"second provider output\n"
    assert first["raw_result_sha256"] == hashlib.sha256(first_path.read_bytes()).hexdigest()
    assert second["raw_result_sha256"] == hashlib.sha256(second_path.read_bytes()).hexdigest()


def test_invalid_commander_output_keeps_raw_evidence_and_failure_link(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo, project, runtime, capsule, projection, task = _fixture(tmp_path)
    monkeypatch.setattr(runner.commander, "eligible_external_providers", lambda *_a, **_k: ("groq",))
    monkeypatch.setattr(runner.commander, "build_resource_command", lambda provider, **_k: ["commander", provider])
    envelope = json.dumps({"provider": "groq", "model": "qwen", "text": "not-json"})

    def popen(_command: Any, *, stdout: Any, **_kwargs: Any) -> _FakeProcess:
        return _FakeProcess(stdout_handle=stdout, stdout_payload=envelope)

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    journal = runner.production_events.ProductionEventJournal(
        runtime / "events.jsonl", failure_path=runtime / "failures.jsonl"
    )
    inflight: dict[str, Any] = {}
    runner._launch_commander_assists(
        repo, project, runtime, task, "a" * 64, capsule, projection, inflight, journal
    )
    handle = next(iter(inflight.values()))
    runner._collect_commander_assists(runtime, inflight, journal)

    assert inflight == {}
    assert not handle.accepted_path.exists()
    rejected = json.loads(handle.rejected_path.read_text(encoding="utf-8"))
    raw_path = Path(rejected["raw_result_path"])
    assert rejected["authority"] == "NONE"
    assert rejected["progression_authority"] is False
    assert rejected["status"] == "NEEDS_MODIFICATION"
    assert rejected["failure_type"] == "INVALID_RESULT"
    assert rejected["raw_result_capture_path"] == str(handle.stdout_path)
    assert raw_path.read_bytes() == handle.stdout_path.read_bytes()
    assert rejected["raw_result_sha256"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert rejected["raw_result_bytes"] == len(raw_path.read_bytes())
    assert rejected["evidence_ref"] == str(raw_path)
    assert task.status == "PENDING"

    event_rows = [json.loads(line) for line in (runtime / "events.jsonl").read_text().splitlines()]
    failed = next(row for row in event_rows if row["type"] == "commander.assist_failed")
    assert failed["task_id"] == "T"
    assert failed["failure_type"] == "INVALID_RESULT"
    assert failed["raw_result_path"] == str(raw_path)
    assert failed["raw_result_sha256"] == rejected["raw_result_sha256"]
    assert failed["evidence_ref"] == str(raw_path)
    failure_rows = [json.loads(line) for line in (runtime / "failures.jsonl").read_text().splitlines()]
    mirrored = next(row for row in failure_rows if row["origin_event_ref"] == failed["journal_event_ref"])
    assert mirrored["failure_type"] == "INVALID_RESULT"
    assert mirrored["raw_result_path"] == str(raw_path)
    assert mirrored["raw_result_sha256"] == rejected["raw_result_sha256"]
    assert mirrored["evidence_ref"] == str(raw_path)
