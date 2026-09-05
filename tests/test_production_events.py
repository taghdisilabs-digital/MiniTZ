from pathlib import Path
import json

import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops/local-ai/biella_production_events.py"
spec = importlib.util.spec_from_file_location("biella_production_events", MODULE)
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
