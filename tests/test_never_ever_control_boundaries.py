from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(LOCAL_AI))


def _load(name: str):
    path = LOCAL_AI / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_never_ever_policy_is_explicit():
    policy = (ROOT / "ops/workstation/AGENTS.md").read_text()
    assert "NEVER_EVER_WINDOWS_CONTROL_WITHOUT_EXPLICIT_OWNER_NAMING" in policy
    assert "NEVER_EVER_BOOST_CANONICAL_STATE_WRITE" in policy
    assert "NEVER_EVER_FULL_BURST" not in policy
    assert "OWNER_ONLY_PRODUCTION_STOP" in policy
    assert "LOCAL_GPU_FULL_CAPABILITY" in policy
    assert "SINGLE_CANONICAL_WRITER" in policy


def test_commander_local_parallelism_is_not_hard_capped_to_one(monkeypatch):
    runner = _load("minitz_production_runner")
    monkeypatch.setenv("MINITZ_LOCAL_QWEN_PARALLEL", "2")
    assert runner._local_qwen_parallelism() == 2



@pytest.mark.parametrize("module_name,writer_name", [
    ("minitz_boost_fabric", "_atomic_json"),
    ("minitz_booster_sync", "_atomic_json"),
    ("minitz_commander_fabric", "atomic_json"),
])
@pytest.mark.parametrize("name", [
    "TASK_PROGRAM.json", "runtime.json", "current-task.json",
    "compacted-memory.json", "failure-learning.sqlite3", "minitz-publication.json",
])
def test_boost_commander_writers_reject_canonical_state_paths(tmp_path: Path, module_name: str, writer_name: str, name: str):
    module = _load(module_name)
    writer = getattr(module, writer_name)
    with pytest.raises(ValueError, match="canonical control state"):
        writer(tmp_path / name, {"x": 1})


def test_windows_browser_control_origins_are_absent():
    forbidden = [
        ROOT / "ops/workstation/minitz-browser-cloud.py",
        ROOT / "ops/workstation/windows-browser-bridge.ps1",
        ROOT / "ops/workstation/windows-browser-cloud-targets.json",
        ROOT / "ops/local-ai/minitz_boost_browser_agent.py",
        ROOT / "ops/local-ai/minitz-boost-browser-agent.service",
    ]
    assert not [str(path) for path in forbidden if path.exists()]
    registry = (ROOT / "ops/workstation/provider-registry.json").read_text()
    installer = (ROOT / "ops/workstation/install-minitz-workstation.sh").read_text()
    ai_installer = (ROOT / "ops/local-ai/install-minitz-ai.sh").read_text()
    for needle in ("windows-browser-cloud", "minitz-browser-cloud", "MiniTZBrowserBridge"):
        assert needle not in registry + installer + ai_installer
