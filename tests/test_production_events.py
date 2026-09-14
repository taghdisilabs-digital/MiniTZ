from pathlib import Path
import hashlib
import json

import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/minitz_production_events.py"
spec = importlib.util.spec_from_file_location("minitz_production_events", MODULE)
assert spec and spec.loader
events = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = events
spec.loader.exec_module(events)


def test_event_journal_sequences_and_reloads(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    journal = events.ProductionEventJournal(path)
    first = journal.emit("task.started", task_id="D02-01", text="start")
    second = journal.emit("tool.started", task_id="D02-01", text="build")
    assert first["seq"] == 1
    assert second["seq"] == 2
    assert events.ProductionEventJournal(path).emit("task.continue", task_id="D02-01")["seq"] == 3


def test_codex_event_projection_keeps_dialog_and_tools_but_not_raw_reasoning():
    agent = events.project_codex_event({"type":"item.completed","item":{"type":"agent_message","text":"Working on nav readiness"}}, "D02-01")
    assert agent["type"] == "agent.message"
    assert agent["text"] == "Working on nav readiness"
    tool = events.project_codex_event({"type":"item.started","item":{"type":"command_execution","command":"python3 tests/run_d02_01.py"}}, "D02-01")
    assert tool["type"] == "tool.started"
    assert "run_d02_01.py" in tool["text"]
    reasoning = events.project_codex_event({"type":"item.completed","item":{"type":"reasoning","text":"secret chain","summary":"Checking navigation readiness"}}, "D02-01")
    assert reasoning["type"] == "agent.reasoning_summary"
    assert reasoning["text"] == "Checking navigation readiness"
    assert "secret chain" not in json.dumps(reasoning)


def test_codex_turn_usage_projection_is_bounded():
    event = events.project_codex_event({"type":"turn.completed","usage":{"input_tokens":1000,"cached_input_tokens":980,"output_tokens":20}}, "D02-01")
    assert event["type"] == "turn.completed"
    assert event["usage"]["cached_input_tokens"] == 980


def test_event_journal_rotates_without_losing_sequence(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    journal = events.ProductionEventJournal(path, max_bytes=180)
    one = journal.emit("agent.message", task_id="D02-01", text="x" * 120)
    two = journal.emit("agent.message", task_id="D02-01", text="y" * 120)
    three = journal.emit("agent.message", task_id="D02-01", text="z" * 120)
    assert [one["seq"], two["seq"], three["seq"]] == [1, 2, 3]
    assert path.with_name("events.previous.jsonl").exists()
    current = [json.loads(line) for line in path.read_text().splitlines()]
    assert current[-1]["seq"] == 3


def test_failure_ledger_mirrors_failed_retry_and_error_events(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    failures_path = tmp_path / "failures.jsonl"
    journal = events.ProductionEventJournal(events_path, failure_path=failures_path)
    journal.emit("tool.completed", task_id="D02-01", status="FAILED", text="runtime failed", tool="shell")
    journal.emit("persistence.retry", task_id="D02-01", status="RETRY", text="drive unavailable")
    journal.emit("agent.message", task_id="D02-01", status="COMPLETE", text="ok")
    rows = [json.loads(line) for line in failures_path.read_text().splitlines()]
    assert [row["failure_type"] for row in rows] == ["tool.completed", "persistence.retry"]
    assert all(row["schema"] == "minitz.failure_event/v1" for row in rows)
    assert rows[0]["task_id"] == "D02-01"
    assert rows[1]["status"] == "RETRY"


def test_failed_command_projection_keeps_bounded_diagnostic_output():
    event = events.project_codex_event({
        "type":"item.completed",
        "item":{"type":"command_execution","command":"python3 verify.py","status":"failed","exit_code":1,"aggregated_output":"ASSERT navigation failed"}
    }, "D02-01")
    assert event["type"] == "tool.completed"
    assert event["status"] == "FAILED"
    assert event["exit_code"] == 1
    assert event["detail"] == "ASSERT navigation failed"


def test_projection_links_mirrored_failure_to_event_without_collapsing_evidence(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    failures_path = tmp_path / "failures.jsonl"
    journal = events.ProductionEventJournal(events_path, failure_path=failures_path)
    emitted = journal.emit(
        "tool.completed", task_id="UNIFY-06", status="FAILED",
        text="bounded failure", tool="shell", failure_type="PROCESS_FAILED",
        session_id="session-1",
    )
    projected = list(events.project_operational_evidence(events_path, failures_path))
    assert [item["source_kind"] for item in projected] == ["EVENT", "FAILURE"]
    assert projected[0]["evidence_ref"] != projected[1]["evidence_ref"]
    assert projected[0]["journal_event_ref"] == emitted["journal_event_ref"]
    assert projected[1]["journal_event_ref"] == emitted["journal_event_ref"]
    assert projected[1]["failure_type"] == "PROCESS_FAILED"
    assert projected[0]["provenance"]["task_id"] == "UNIFY-06"
    assert projected[0]["provenance"]["session_id"] == "session-1"
    assert "run_ref" not in projected[0]["provenance"]
    assert all(item["authority"] == "NONE_DERIVED_EVIDENCE" for item in projected)
    assert emitted["record_kind"] == "EVENT"
    assert emitted["semantic_graph"] == "MiniTZ"
    assert emitted["semantic_family_ref"] == "semantic-family://minitz/event-evidence/v1"
    assert emitted["family_revision"] == 1
    assert emitted["projection_authority"] is False
    assert emitted["progression_authority"] is False
    failure = json.loads(failures_path.read_text(encoding="utf-8").splitlines()[0])
    assert failure["record_kind"] == "FAILURE"
    assert failure["failure_type"] == "PROCESS_FAILED"
    assert failure["failure_classification"] == "PROCESS_FAILED"
    assert failure["legacy_event_identity"] == emitted["journal_event_ref"]
    assert failure["semantic_family_ref"] == emitted["semantic_family_ref"]
    assert failure["family_revision"] == 1
    assert failure["projection_authority"] is False
    assert failure["progression_authority"] is False


def test_projection_preserves_invalid_legacy_failure_bytes_as_opaque_evidence(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    failures_path = tmp_path / "failures.jsonl"
    events_path.write_text('', encoding='utf-8')
    invalid = b'{"legacy":true\n'
    failures_path.write_bytes(invalid)
    projected = list(events.project_operational_evidence(events_path, failures_path))
    assert len(projected) == 1
    item = projected[0]
    assert item["source_kind"] == "FAILURE"
    assert item["parse_state"] == "OPAQUE_INVALID_JSON"
    assert item["raw_sha256"] == hashlib.sha256(invalid).hexdigest()
    assert item["journal_event_ref"] is None
    assert item["provenance"] == {}


def test_projection_preserves_failure_categories_without_normalizing_them(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    failures_path = tmp_path / "failures.jsonl"
    events_path.write_text('', encoding='utf-8')
    categories = [
        "HELPER_DEADLINE_EXCEEDED", "PROCESS_FAILED", "VALIDATION_REJECTED",
        "STALE_INPUT_DIGEST", "PROVIDER_UNAVAILABLE",
    ]
    rows = [
        {"schema": "minitz.failure_event/v1", "seq": index, "time": "2026-09-11T00:00:00+00:00",
         "failure_type": category, "event_type": "resource.taskbooster_failed",
         "status": "FAILED", "task_id": "UNIFY-06"}
        for index, category in enumerate(categories, 1)
    ]
    failures_path.write_text(
        ''.join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding='utf-8',
    )
    projected = list(events.project_operational_evidence(events_path, failures_path))
    assert [item["failure_type"] for item in projected] == categories
    assert len({item["journal_event_ref"] for item in projected}) == len(categories)
    assert all(item["event_type"] == "resource.taskbooster_failed" for item in projected)


def test_projection_identity_changes_on_material_content_not_timestamp_only(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    failures_path = tmp_path / "failures.jsonl"
    base = {"seq": 1, "time": "2026-09-11T00:00:00+00:00", "type": "agent.message", "task_id": "UNIFY-06"}
    first = dict(base, text="first")
    second = dict(base, text="second")
    events_path.write_text(
        json.dumps(first, sort_keys=True, separators=(",", ":")) + "\n"
        + json.dumps(second, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    failures_path.write_text("", encoding="utf-8")
    projected = list(events.project_operational_evidence(events_path, failures_path))
    assert projected[0]["journal_event_ref"] == projected[1]["journal_event_ref"]
    assert projected[0]["raw_sha256"] != projected[1]["raw_sha256"]
    assert projected[0]["evidence_ref"] != projected[1]["evidence_ref"]


def test_event_journal_rotation_preserves_every_raw_segment(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    journal = events.ProductionEventJournal(path, max_bytes=180)
    emitted = [
        journal.emit("agent.message", task_id="UNIFY-06", text=letter * 120)
        for letter in ("a", "b", "c", "d")
    ]
    rows = []
    for segment in sorted(tmp_path.glob("events*.jsonl")):
        rows.extend(json.loads(line) for line in segment.read_text().splitlines())
    assert sorted(row["seq"] for row in rows) == [1, 2, 3, 4]
    assert [item["seq"] for item in emitted] == [1, 2, 3, 4]
    projected = list(events.project_operational_evidence(path, tmp_path / "failures.jsonl"))
    projected_events = [item for item in projected if item["source_kind"] == "EVENT"]
    assert len(projected_events) == 4
    assert len({item["journal_event_ref"] for item in projected_events}) == 4


def test_event_journal_restart_after_rotation_recovers_sequence_from_archives(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    journal = events.ProductionEventJournal(path, max_bytes=180)
    first = journal.emit("agent.message", task_id="UNIFY-06", text="x" * 120)
    assert first["seq"] == 1
    journal._rotate_if_needed()
    assert not path.exists()
    restarted = events.ProductionEventJournal(path, max_bytes=180)
    second = restarted.emit("agent.message", task_id="UNIFY-06", text="y")
    assert second["seq"] == 2


def test_projection_normalizes_duplicate_raw_event_as_one_evidence_identity(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    failures_path = tmp_path / "failures.jsonl"
    row = {"seq": 1, "time": "2026-09-11T00:00:00+00:00", "type": "agent.message", "task_id": "UNIFY-06"}
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    events_path.write_text(encoded + encoded, encoding="utf-8")
    failures_path.write_text("", encoding="utf-8")
    projected = list(events.project_operational_evidence(events_path, failures_path))
    assert projected[0]["journal_event_ref"] == projected[1]["journal_event_ref"]
    assert projected[0]["raw_sha256"] == projected[1]["raw_sha256"]
    assert projected[0]["evidence_ref"] == projected[1]["evidence_ref"]
    assert projected[0]["source_line"] != projected[1]["source_line"]


def test_event_identity_and_authority_fields_cannot_be_overridden_by_payload(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    journal = events.ProductionEventJournal(path)
    emitted = journal.emit(
        "agent.message", task_id="UNIFY-06", text="x",
        seq=999, type="canonical.claim", lane="OTHER",
        authority="CANONICAL", journal_event_ref="event://forged",
    )
    assert emitted["seq"] == 1
    assert emitted["type"] == "agent.message"
    assert emitted["lane"] == "MiniTZ OS"
    assert emitted["authority"] == "NONE_DERIVED_EVIDENCE"
    assert emitted["journal_event_ref"] == "journal-event://minitz-production-events-v1/1"
