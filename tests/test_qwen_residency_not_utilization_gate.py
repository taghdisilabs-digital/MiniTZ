from __future__ import annotations
import json
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "ops/workstation/minitz-lib.sh"


def check_resident(models):
    body = json.dumps({"models": models})
    # curl receives its own arguments: a captured shell variable supplies only fixture bytes.
    command = 'source "$1"; fixture="$2"; curl() { printf "%s" "$fixture"; }; minitz_verify_qwen_vram'
    return subprocess.run(["bash", "-c", command, "test", str(LIBRARY), body], text=True, capture_output=True)


@pytest.mark.parametrize("mib", [38721, 40960, 44000])
def test_resident_model_is_not_rejected_by_old_fixed_vram_ceiling(mib):
    result = check_resident([{"name": "qwen3-coder-next:minitz", "size_vram": mib * 1024**2}])
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) == mib * 1024**2


@pytest.mark.parametrize("models", [[], [{"name": "other", "size_vram": 1024}],
    [{"name": "qwen3-coder-next:minitz", "size_vram": 0}],
    [{"name": "qwen3-coder-next:minitz", "size_vram": -1}],
    [{"name": "qwen3-coder-next:minitz", "size_vram": "UNKNOWN"}],
    [{"name": "qwen3-coder-next:minitz", "size_vram": True}]])
def test_missing_or_invalid_residency_is_not_reported_as_healthy(models):
    assert check_resident(models).returncode != 0
