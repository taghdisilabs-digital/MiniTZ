from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))

import minitz_taskbooster as booster


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_packet(tmp_path: Path):
    project = tmp_path / "project"
    target = project / "Config/DefaultEngine.ini"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[Renderer]\nr.Shadow.Virtual.Enable=1\n", encoding="utf-8")
    assist = {"text": "Inspect `Config/DefaultEngine.ini` and preserve the current renderer setting."}
    packet = booster.compile_packet(
        task_id="D17-02", task_state_digest="state-1",
        objective="Verify the current renderer setting.",
        acceptance=["Evidence must cite the exact current line."],
        scope_root=project, local_assist=assist,
    )
    return project, target, packet


def test_booster_result_schema_requires_all_properties_and_allows_null_symbols(tmp_path: Path):
    schema = booster.booster_result_schema()
    violations = []

    def inspect(node, path="$schema"):
        if isinstance(node, dict):
            if node.get("type") == "object" and node.get("additionalProperties") is False:
                properties = set(node["properties"])
                required = set(node.get("required", []))
                if required != properties:
                    violations.append(
                        f"{path}: missing={sorted(properties - required)}, extra={sorted(required - properties)}"
                    )
            for key, value in node.items():
                inspect(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                inspect(value, f"{path}[{index}]")

    inspect(schema)
    assert not violations, "\n".join(violations)
    for field in ("evidence_refs", "candidate_actions"):
        symbol = schema["properties"][field]["items"]["properties"]["symbol"]
        assert set(symbol["type"]) == {"string", "null"}, field

    project, target, packet = make_packet(tmp_path)
    result = {
        "booster_id": packet["booster_id"], "status": "USEFUL",
        "finding": "Virtual shadows are enabled.",
        "evidence_refs": [{
            "path": "Config/DefaultEngine.ini", "sha256": digest(target),
            "line_start": 2, "line_end": 2, "quote": "r.Shadow.Virtual.Enable=1", "symbol": None,
        }],
        "candidate_actions": [{
            "target_path": "Config/DefaultEngine.ini", "action": "Preserve setting",
            "rationale": "The current setting is enabled.", "symbol": None,
        }],
        "candidate_patch": "", "recommended_commands": [], "uncertainties": [],
    }
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert checked.accepted
    assert checked.reason == "ACCEPTED"


def test_compile_packet_is_deterministic_and_binds_exact_target(tmp_path: Path):
    project, target, first = make_packet(tmp_path)
    _, _, second = make_packet(tmp_path)
    assert first["booster_id"] == second["booster_id"]
    assert first["authority"] == "NONE"
    assert first["task_state_digest"] == "state-1"
    assert first["allowed_writes"] == []
    assert first["allowed_commands"] == []
    assert first["allowed_reads"] == [{
        "path": "Config/DefaultEngine.ini",
        "sha256": digest(target),
        "size_bytes": target.stat().st_size,
    }]


def test_extract_grounded_targets_rejects_existing_path_outside_scope(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    outside = tmp_path / "outside.txt"; outside.write_text("x")
    text = f"Inspect `{outside}` and `missing.txt`."
    assert booster.extract_grounded_targets(text, project) == ()


def test_validate_result_accepts_exact_grounded_evidence(tmp_path: Path):
    project, target, packet = make_packet(tmp_path)
    result = {
        "booster_id": packet["booster_id"], "status": "USEFUL",
        "finding": "Virtual shadows are enabled.",
        "evidence_refs": [{"path":"Config/DefaultEngine.ini","sha256":digest(target),"line_start":2,"line_end":2,"quote":"r.Shadow.Virtual.Enable=1"}],
        "candidate_actions": [], "candidate_patch": "", "recommended_commands": [], "uncertainties": [],
    }
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert checked.accepted
    assert checked.reason == "ACCEPTED"


def test_validate_result_rejects_stale_task_state(tmp_path: Path):
    project, target, packet = make_packet(tmp_path)
    result = {"booster_id":packet["booster_id"],"status":"NO_ACTION","finding":"","evidence_refs":[],"candidate_actions":[],"candidate_patch":"","recommended_commands":[],"uncertainties":[]}
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-2")
    assert not checked.accepted
    assert checked.reason == "STALE_INPUT_DIGEST"


def test_validate_result_rejects_invented_symbol(tmp_path: Path):
    project, target, packet = make_packet(tmp_path)
    result = {
        "booster_id":packet["booster_id"],"status":"USEFUL","finding":"x",
        "evidence_refs":[{"path":"Config/DefaultEngine.ini","sha256":digest(target),"line_start":1,"line_end":2,"quote":"[Renderer]\nr.Shadow.Virtual.Enable=1","symbol":"ImaginarySymbol"}],
        "candidate_actions":[],"candidate_patch":"","recommended_commands":[],"uncertainties":[]}
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert not checked.accepted
    assert checked.reason == "INVENTED_SYMBOL"


def test_validate_result_rejects_unsupported_path(tmp_path: Path):
    project, target, packet = make_packet(tmp_path)
    extra = project / "Other.txt"; extra.write_text("other")
    result = {
        "booster_id":packet["booster_id"],"status":"USEFUL","finding":"x",
        "evidence_refs":[{"path":"Other.txt","sha256":digest(extra),"line_start":1,"line_end":1,"quote":"other"}],
        "candidate_actions":[],"candidate_patch":"","recommended_commands":[],"uncertainties":[]}
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert not checked.accepted
    assert checked.reason == "UNSUPPORTED_PATH"


def test_validate_result_rejects_unapproved_command(tmp_path: Path):
    project, _target, packet = make_packet(tmp_path)
    result = {"booster_id":packet["booster_id"],"status":"NO_ACTION","finding":"","evidence_refs":[],"candidate_actions":[],"candidate_patch":"","recommended_commands":["pytest -q"],"uncertainties":[]}
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert not checked.accepted
    assert checked.reason == "FAILED_COMMAND"


def test_validate_result_rejects_patch_for_non_allowlisted_path(tmp_path: Path):
    project, target, packet = make_packet(tmp_path)
    result = {
        "booster_id":packet["booster_id"],"status":"USEFUL","finding":"x",
        "evidence_refs":[{"path":"Config/DefaultEngine.ini","sha256":digest(target),"line_start":1,"line_end":1,"quote":"[Renderer]"}],
        "candidate_actions":[{"target_path":"Config/DefaultEngine.ini","action":"candidate patch","rationale":"test"}],
        "candidate_patch":"--- a/Other.txt\n+++ b/Other.txt\n@@\n-old\n+new\n", "recommended_commands":[], "uncertainties":[]}
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert not checked.accepted
    assert checked.reason == "SCOPE_ESCAPE"


def test_failure_evidence_preserves_raw_result_digest():
    raw = '{"broken":'
    evidence = booster.failure_evidence("INVALID_JSON", raw)
    assert evidence["authority"] == "NONE"
    assert evidence["preserve_raw"] is True
    assert evidence["reason"] == "INVALID_JSON"
    assert evidence["raw_sha256"] == hashlib.sha256(raw.encode()).hexdigest()


def test_validate_result_rejects_useful_claim_without_evidence(tmp_path: Path):
    project, _target, packet = make_packet(tmp_path)
    result = {
        "booster_id":packet["booster_id"],"status":"USEFUL","finding":"unsupported claim",
        "evidence_refs":[],"candidate_actions":[],"candidate_patch":"",
        "recommended_commands":[],"uncertainties":[],
    }
    checked = booster.validate_result(packet, result, project, current_task_state_digest="state-1")
    assert not checked.accepted
    assert checked.reason == "UNSUPPORTED_CLAIM"
