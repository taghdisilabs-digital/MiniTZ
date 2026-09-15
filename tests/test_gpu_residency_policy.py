from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "ops/workstation/minitz-gpu-residency.json"
RESIDENCY = ROOT / "ops/workstation/minitz-qwen-residency.sh"
SERVICE = ROOT / "ops/workstation/minitz-qwen-residency.service"
OLLAMA_SERVICE = ROOT / "ops/workstation/minitz-ollama.service"
LIB = ROOT / "ops/workstation/minitz-lib.sh"
MODE_SELECTOR = ROOT / "ops/workstation/minitz-qwen-mode.sh"


def test_gpu_policy_is_observation_not_execution_gate():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["schema"] == "minitz.gpu_residency_policy/v1"
    assert policy["gpu"]["resource"] == "NVIDIA L40S"
    assert policy["gpu"]["observed_total_vram_mib"] == 46068
    text = POLICY.read_text(encoding="utf-8")
    for forbidden in ("required_free_vram_mib", "max_combined_resident_vram_mib", "max_vram_mib", "combined_resident_vram_mib_must_not_exceed", "logic_and_visual_may_not_be_co_resident"):
        assert forbidden not in text
    assert policy["admission"]["authority"] == "RESOURCE_RUNTIME"
    assert policy["admission"]["minitz_admission_gate"] is False


def test_logic_resource_retains_observed_identity_without_fixed_gpu_profile():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    logic = next(slot for slot in policy["slots"] if slot["slot_id"] == "logic")
    assert logic["model"] == "qwen3-coder-next:minitz"
    assert logic["observed_vram_mib"] == 38721
    assert {"code.generate", "code.compare", "reason.calculate", "logic.analyze"}.issubset(logic["capabilities"])
    assert "gpu_blocks" not in logic
    assert "max_vram_mib" not in logic


def test_qwen_residency_never_unloads_or_reprofiles_healthy_model():
    script = RESIDENCY.read_text(encoding="utf-8")
    for forbidden in ("unload_model", "model_profile_matches", "model_vram_matches", "MIN_VRAM", "MAX_VRAM", "num_gpu", "keep_alive\":0"):
        assert forbidden not in script
    assert "/api/tags" in script and "/api/ps" in script
    assert '"keep_alive":-1' in script


def test_qwen_library_warmup_does_not_force_gpu_layers():
    lib = LIB.read_text(encoding="utf-8")
    assert "MINITZ_QWEN_NUM_GPU" not in lib
    assert "num_gpu" not in lib
    assert "keep_alive':-1" in lib or '"keep_alive":-1' in lib


def test_old_qwen_profile_selector_is_removed_and_service_has_no_profile_env_hook():
    assert not MODE_SELECTOR.exists()
    service = SERVICE.read_text(encoding="utf-8")
    assert "qwen-residency.env" not in service
    assert "OLLAMA_NUM_PARALLEL=" not in service
    assert "OLLAMA_NUM_PARALLEL=" not in OLLAMA_SERVICE.read_text(encoding="utf-8")


def test_qwen_residency_watcher_recovery_interval_is_fast():
    service = SERVICE.read_text(encoding="utf-8")
    assert 'MINITZ_QWEN_RESIDENCY_INTERVAL_SECONDS=5' in service
