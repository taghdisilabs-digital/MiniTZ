from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import minitz_codex_routing as routing


def test_installed_unit_source_uses_existing_task_class_router(monkeypatch):
    for key in ("MINITZ_CODEX_FORCE_MODEL", "MINITZ_CODEX_FORCE_REASONING", "MINITZ_CODEX_PREFER_MODEL", "MINITZ_CODEX_PREFER_REASONING"):
        monkeypatch.delenv(key, raising=False)
    unit = (ROOT / "ops/local-ai/minitz-production.service").read_text()
    for line in unit.splitlines():
        if line.startswith("Environment=MINITZ_CODEX_"):
            key, value = line[len("Environment="):].split("=", 1)
            monkeypatch.setenv(key, value)
    catalog = {"gpt-6-astra": {"high", "xhigh", "max", "ultra"}, "gpt-5.6-luna": {"medium", "high", "max"}, "gpt-reserve": {"max"}}
    now = datetime.now(timezone.utc)
    for task_class in ("simple", "medium", "creation", "hard", "hard_creation", "deep_memory"):
        result = routing.select_route(task_class, catalog, {}, now)
        assert (result.model, result.reasoning) == ("gpt-6-astra", "ultra")
        assert result.model != "gpt-5.6-luna"


def test_obsolete_unreferenced_current_pointer_is_removed():
    assert not (ROOT / "docs/project-state/MINITZ_CURRENT_LOCAL_AI_RUNTIME_POINTER_2026-09-04.md").exists()


def test_sync_policy_does_not_reopen_completed_foundation():
    text = (ROOT / "docs/project-state/MINITZ_DURABLE_SOURCE_AND_SYNC_RULES.md").read_text()
    assert "Re-establish P0-01" not in text
    assert "five" in text.lower()


def test_drive_index_does_not_dispatch_old_tasks():
    text = (ROOT / "docs/project-state/MINITZ_DRIVE_LIVE_MANIFEST.md").read_text()
    assert "Current observed numbered boundary remains" not in text
    assert "Current active prompt:" not in text
    assert "not authorized before P3-05" not in text
    assert "1x35z0cZ-t3SM3Ma6mX5O4AMfFKnDcolv" in text


def test_dependent_historical_files_are_preserved_without_runtime_authority():
    base = ROOT / "docs/project-state"
    for name in ("MINITZ_LOCAL_AI_RUNTIME_DECISION_2026-09-04.md", "MINITZ_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml"):
        text = (base / name).read_text()
        assert "HISTORICAL_EVIDENCE_ONLY" in text
        assert "07_MINITZ_PRODUCTION_SYSTEM.md" in text
    text = (base / "MINITZ_PROJECT_CONTEXT_SNAPSHOT_2026-08-26.md").read_text()
    assert "Execute only P0-01 and stop" not in text
    assert "SUPERSEDED_NON_AUTHORITY" in text
