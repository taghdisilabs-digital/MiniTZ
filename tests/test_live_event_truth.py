from pathlib import Path
import json
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
from ops.control_gateway.minitz_live_projection import LiveProjection

@pytest.mark.parametrize("command", [
    "/bin/bash -lc \"git diff --name-only 6e9e3b4 HEAD -- .; sed -n '1,200p' Build/Presentation/D03-01-pso-increment.json; cat Build/Presentation/D03-01-audio-final-readback.json; sed -n '1,160p' Build/Cinematics/D06-01-acceptance.md; sed -n '1,100p' tests/verify_d01_043.py\"",
    "/bin/bash -lc \"sed -n '1,95p' Build/Presentation/D03-01-automatic-pso-increment.json; rg -n 'def verify' tests/verify_d02_01.py\"",
    "rg -n 'render capture validation.json pytest' Source",
])
def test_reading_old_proof_is_not_running_old_validation(command):
    projected = LiveProjection.sanitize_event({"task_id":"D07-01", "type":"tool.completed", "tool":"shell", "status":"COMPLETED", "exit_code":0, "text":command})
    assert projected["category"] == "TOOL"
    assert projected["operation_kind"] == "READ"
    assert projected["text"].startswith("D07-01")
    assert "Validation completed" not in projected["text"]

@pytest.mark.parametrize("command,category", [
    ("python3 tests/run_d07_01_qualification.py", "TEST"),
    ("sed -n '1,30p' Build/Presentation/D03-01-pso-increment.json; python3 -m pytest tests/test_one.py", "TEST"),
    ("/bin/bash -lc '/opt/unreal/UE_5.8.2/Engine/Build/BatchFiles/Linux/Build.sh MiniTZGamesEditor Linux Development'", "BUILD"),
    ("git status --short && git commit -m 'validated source'", "COMMIT"),
])
def test_real_actions_keep_their_category(command, category):
    event = {"task_id":"D07-01", "type":"tool.started", "tool":"shell", "text":command}
    assert LiveProjection.sanitize_event(event)["category"] == category

