from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "ops/workstation/minitz-gpu-residency.json"
RESIDENCY = ROOT / "ops/workstation/biella-qwen-residency.sh"
LIB = ROOT / "ops/workstation/biella-lib.sh"
MODE_SELECTOR = ROOT / "ops/workstation/minitz-qwen-mode.sh"


def test_gpu_policy_reserves_two_gib_and_two_semantic_model_slots():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["schema"] == "minitz.gpu_residency_policy/v1"
    assert policy["gpu"]["observed_total_vram_mib"] == 46068
    assert policy["gpu"]["required_free_vram_mib"] == 2048
    assert policy["max_resident_model_slots"] == 2
    assert policy["start_enabled"] is False
    assert {slot["slot_id"] for slot in policy["slots"]} == {"logic", "visual"}


def test_logic_slot_uses_42_of_48_qwen_blocks_for_code_reasoning_and_comparison():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    logic = next(slot for slot in policy["slots"] if slot["slot_id"] == "logic")
    assert logic["model"] == "qwen3-coder-next:biella"
    assert logic["gpu_blocks"] == 42
    assert logic["total_model_blocks"] == 48
    assert logic["estimated_vram_mib"] == 42821
    assert logic["max_vram_mib"] == 43008
    assert logic["observed_total_gpu_used_mib"] == 43341
    assert {"code.generate", "code.compare", "reason.calculate", "logic.analyze"}.issubset(logic["capabilities"])


def test_visual_slot_is_budgeted_but_not_falsely_bound_to_uninstalled_weights():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    visual = next(slot for slot in policy["slots"] if slot["slot_id"] == "visual")
    assert visual["state"] == "UNBOUND_NEEDS_QUALIFICATION"
    assert visual["model"] is None
    assert visual["target_vram_mib"] == 8192
    assert visual["max_vram_mib"] == 8192
    assert visual["capabilities"] == ["image.generate", "visual.create"]
    logic = next(slot for slot in policy["slots"] if slot["slot_id"] == "logic")
    assert visual["co_resident_with_logic"] is False
    assert policy["admission"]["logic_and_visual_may_not_be_co_resident"] is True
    observed_free = policy["gpu"]["observed_total_vram_mib"] - logic["observed_total_gpu_used_mib"]
    assert observed_free >= policy["gpu"]["required_free_vram_mib"]


def test_qwen_future_residency_uses_42_blocks_without_starting_services():
    script = RESIDENCY.read_text(encoding="utf-8")
    lib = LIB.read_text(encoding="utf-8")
    assert 'BIELLA_QWEN_NUM_GPU:-42' in script
    assert "readonly BIELLA_QWEN_NUM_GPU=42" in lib
    assert "43008 * 1024 * 1024" in lib


def test_qwen_residency_enforces_selected_profile_and_exposes_26_42_selector():
    script = RESIDENCY.read_text(encoding="utf-8")
    assert "model_profile_matches" in script
    assert "unload_model" in script
    assert 'EnvironmentFile=-/etc/minitz/qwen-residency.env' in (ROOT / "ops/workstation/biella-qwen-residency.service").read_text(encoding="utf-8")
    selector = MODE_SELECTOR.read_text(encoding="utf-8")
    assert "/etc/minitz/qwen-residency.env" in selector
    assert '26|42)' in selector
    assert "BIELLA_QWEN_NUM_GPU" in selector
