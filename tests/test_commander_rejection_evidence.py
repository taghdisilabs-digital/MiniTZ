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
MODULE = LOCAL_AI / "minitz_production_runner.py"
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
        "schema": "minitz.provider_registry/v1",
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
    monkeypatch.setattr(runner, "_commander_external_provider_pool", lambda *_a, **_k: ("groq",))
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
    assert not any(row["type"] in {"commander.assist_failed", "commander.assist_rejected"} for row in event_rows)
    assert not (runtime / "failures.jsonl").exists() or not (runtime / "failures.jsonl").read_text().strip()


def test_legacy_commander_rejections_get_append_only_evidence_links(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    root = runtime / "memory/commander-fabric"
    root.mkdir(parents=True)
    records = (
        (
            "5cdce92d4f6a04e7d128527a645503fe1342e498878054153b959f1cbfa0a5ca",
            "2026-09-11T03:52:25.333012+00:00",
            "2026-09-11T03:52:25.333559+00:00",
            "ACTIVE",
            "Unterminated string starting at: line 7 column 5 (char 1729)",
            30506,
            b'{"provider":"groq","model":"qwen","text":"{\\"broken\\":"}',
        ),
        (
            "abefb38feff9715f12f029eb6c470679cf4ce2cf3d7b293ee17b3db69f8ba2d5",
            "2026-09-11T09:11:58.141586+00:00",
            "2026-09-11T09:11:58.142286+00:00",
            "OUT_OF_CREDIT",
            "Unterminated string starting at: line 18 column 1 (char 1512)",
            31344,
            b'{"provider":"groq","model":"qwen","text":"{\\"broken\\":"}',
        ),
    )
    events: list[str] = []
    failures: list[str] = []
    original_rejections: dict[Path, bytes] = {}
    original_stdout: dict[Path, bytes] = {}
    for key, created_at, event_time, status, detail, seq, stdout in records:
        rejection_path = root / f"{key}.rejected.json"
        stdout_path = root / f"{key}.stdout.json"
        rejection = {
            "authority": "NONE",
            "cache_key": key,
            "created_at": created_at,
            "detail": detail,
            "lane_id": "CMD-01",
            "progression_authority": False,
            "projection_digest": "p" * 64,
            "provider": "groq",
            "role": "requirements",
            "schema": "minitz.commander_rejection/v1",
            "status": status,
            "task_id": "UNIFY-04",
            "task_state_digest": "t" * 64,
        }
        rejection_bytes = (json.dumps(rejection, sort_keys=True) + "\n").encode()
        rejection_path.write_bytes(rejection_bytes)
        stdout_path.write_bytes(stdout)
        original_rejections[rejection_path] = rejection_bytes
        original_stdout[stdout_path] = stdout
        event = {
            "authority": "NONE",
            "lane": "MiniTZ OS",
            "lane_id": "CMD-01",
            "provider": "groq",
            "role": "requirements",
            "seq": seq,
            "status": status,
            "task_id": "UNIFY-04",
            "text": detail,
            "time": event_time,
            "type": "commander.assist_failed",
        }
        events.append(json.dumps(event, sort_keys=True, separators=(",", ":")))
        failure = {
            "event_type": "commander.assist_failed",
            "failure_type": "commander.assist_failed",
            "lane": "MiniTZ OS",
            "provider": "groq",
            "schema": "minitz.failure_event/v1",
            "seq": seq,
            "status": status,
            "task_id": "UNIFY-04",
            "text": detail,
            "time": event_time,
        }
        failures.append(json.dumps(failure, sort_keys=True, separators=(",", ":")))
    (runtime / "events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")
    (runtime / "failures.jsonl").write_text("\n".join(failures) + "\n", encoding="utf-8")
    journal = runner.production_events.ProductionEventJournal(
        runtime / "events.jsonl", failure_path=runtime / "failures.jsonl"
    )

    linked = runner.reconcile_commander_rejection_evidence(runtime, journal)
    assert len(linked) == 2
    for rejection_path, rejection_bytes in original_rejections.items():
        assert rejection_path.read_bytes() == rejection_bytes
    for stdout_path, stdout in original_stdout.items():
        assert stdout_path.read_bytes() == stdout

    event_rows = [json.loads(line) for line in (runtime / "events.jsonl").read_text().splitlines()]
    link_rows = [row for row in event_rows if row["type"] == "commander.assist_evidence_linked"]
    assert len(link_rows) == 2
    for row in link_rows:
        raw_path = Path(row["raw_result_path"])
        assert raw_path.read_bytes() == next(
            stdout for path, stdout in original_stdout.items()
            if path.name.startswith(str(row["cache_key"]))
        )
        assert row["raw_result_capture_path"].endswith(f"{row['cache_key']}.stdout.json")
        assert row["raw_result_sha256"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()
        assert row["failure_type"] == "INVALID_RESULT"
        assert row["legacy_failure_type"] == "commander.assist_failed"
        assert row["source_event_ref"].startswith("journal-event://")
        assert row["source_failure_ref"].startswith("journal-failure://")
        assert row["progression_authority"] is False
        sidecar = Path(row["evidence_link_ref"])
        assert sidecar.is_file()
        assert json.loads(sidecar.read_text())["raw_result_sha256"] == row["raw_result_sha256"]

    failure_rows = [json.loads(line) for line in (runtime / "failures.jsonl").read_text().splitlines()]
    assert len(failure_rows) == 2
    assert all(row["event_type"] == "commander.assist_failed" for row in failure_rows)

    projection = list(runner.production_events.project_operational_evidence(
        runtime / "events.jsonl", runtime / "failures.jsonl"
    ))
    projected_links = [item for item in projection if item.get("event_type") == "commander.assist_evidence_linked"]
    assert len(projected_links) == 2
    assert all(item.get("linked_evidence_ref") for item in projected_links)
    assert all(item.get("source_event_ref", "").startswith("journal-event://") for item in projected_links)

    before_second_pass = (runtime / "events.jsonl").read_bytes()
    assert runner.reconcile_commander_rejection_evidence(runtime, journal) == tuple(linked)
    assert (runtime / "events.jsonl").read_bytes() == before_second_pass
