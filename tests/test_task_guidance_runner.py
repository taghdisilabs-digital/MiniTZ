from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import minitz_production_runner as runner
import minitz_production_state as state


def guide(task_id: str = "T-GUIDE") -> dict:
    return {
        "schema": "minitz.task_guidance_projection/v1",
        "authority": "NONE",
        "progression_authority": False,
        "task_id": task_id,
        "task_revision": 3,
        "task_record_sha256": "a" * 64,
        "title": "Guided task",
        "objective": {"desired_state": "Use task guidance"},
        "acceptance": ["guidance consumed"],
        "required_evidence": ["exact evidence"],
        "negative_controls": ["NO_PARALLEL_AUTHORITY"],
        "execution_guidance": {"procedure": ["Reuse exact current evidence"]},
        "capability_context": {
            "required": ["cap.required"],
            "candidates": ["cap.candidate"],
            "promotion": "VALIDATED_CANDIDATE_ONLY",
            "system_promotion_authority": False,
        },
    }


def test_main_coder_prompt_embeds_digest_bound_task_guidance(tmp_path: Path, monkeypatch):
    task = state.TaskRecord("T-GUIDE", "hard", "Guided task", "PENDING", (), "minitz")
    production = state.ProductionState(
        tmp_path, "IN_PROGRESS", "minitz", task.id,
        [state.SectionRecord("minitz", "MiniTZ", "IN_PROGRESS", [task])],
        run_id="minitz-task-program", priority_policy="MINITZ_TASK_PROGRAM",
    )
    capsule = tmp_path / "capsule.json"; capsule.write_text("{}\n")
    monkeypatch.setattr(runner, "_task_guidance_for", lambda _task_id: guide())
    monkeypatch.setattr(runner, "_minitz_owner_direction", lambda _root: "")
    monkeypatch.setattr(runner, "_minitz_owner_wake_context", lambda *_a: "")
    monkeypatch.setattr(runner, "_task_working_directory", lambda *_a: tmp_path)
    monkeypatch.setattr(runner.main_coder, "shared_policy_paths", lambda *_a: ())
    monkeypatch.setattr(runner, "_task_has_shared_continuity", lambda *_a: False)
    monkeypatch.setattr(runner.packets, "compile_task_packet", lambda *_a: "PACKET\n")
    monkeypatch.setattr(runner.execution_map, "task_context", lambda *_a: "")
    monkeypatch.setattr(runner.execution_style, "proven_execution_style_prompt", lambda: "")

    prompt = runner._task_prompt(tmp_path, production, task, runner.initial_runtime(), capsule)

    assert "MINITZ_TASK_GUIDANCE" in prompt
    assert "cap.required" in prompt
    assert "cap.candidate" in prompt
    assert "VALIDATED_CANDIDATE_ONLY" in prompt
    assert "cannot advance, complete, or become capability authority" in prompt


def test_local_assist_consumes_task_guidance(tmp_path: Path, monkeypatch):
    projection = tmp_path / "memory/current-task.json"
    projection.parent.mkdir(parents=True)
    projection.write_text(json.dumps({
        "task_id": "T-GUIDE", "task_memory": {"task_class": "hard", "title": "Guided task"},
        "failures": [], "capabilities": {}, "verified_actions": [],
    }))
    calls = []
    def fake_run(argv, **kwargs):
        calls.append(argv)
        payload = {
            "provider": "ollama-qwen", "model": "qwen3-coder-next:minitz",
            "text": "Likely failure cause if any: NONE", "usage": {},
        }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(payload) + "\n", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    path = runner._ensure_local_resource_assist(
        tmp_path, "T-GUIDE", projection, guidance_document=guide(),
    )
    assert path is not None
    prompt = calls[0][calls[0].index("--prompt") + 1]
    assert "task_guidance" in prompt
    assert "cap.required" in prompt
    assert "cap.candidate" in prompt
    assert "VALIDATED_CANDIDATE_ONLY" in prompt
