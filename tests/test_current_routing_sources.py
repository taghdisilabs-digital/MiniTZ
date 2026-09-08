from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import biella_codex_routing as routing


def test_installed_unit_source_uses_existing_task_class_router(monkeypatch):
    for key in ("BIELLA_CODEX_FORCE_MODEL", "BIELLA_CODEX_FORCE_REASONING", "BIELLA_CODEX_PREFER_MODEL", "BIELLA_CODEX_PREFER_REASONING"):
        monkeypatch.delenv(key, raising=False)
    unit = (ROOT / "ops/local-ai/biella-codex-production.service").read_text()
    for line in unit.splitlines():
        if line.startswith("Environment=BIELLA_CODEX_"):
            key, value = line[len("Environment="):].split("=", 1)
            monkeypatch.setenv(key, value)
    catalog = {"gpt-6-astra": {"high", "xhigh", "max", "ultra"}, "gpt-5.6-luna": {"medium", "high", "max"}, "gpt-reserve": {"max"}}
    now = datetime.now(timezone.utc)
    for task_class, expected in (("simple", ("gpt-5.6-luna", "medium")), ("medium", ("gpt-5.6-luna", "high")), ("creation", ("gpt-5.6-luna", "max")), ("hard", ("gpt-6-astra", "ultra")), ("hard_creation", ("gpt-6-astra", "ultra")), ("deep_memory", ("gpt-6-astra", "ultra"))):
        result = routing.select_route(task_class, catalog, {}, now)
        assert (result.model, result.reasoning) == expected


def test_obsolete_unreferenced_current_pointer_is_removed():
    assert not (ROOT / "docs/project-state/BIELLA_CURRENT_LOCAL_AI_RUNTIME_POINTER_2026-09-04.md").exists()


def test_sync_policy_does_not_reopen_completed_foundation():
    text = (ROOT / "docs/project-state/BIELLA_DURABLE_SOURCE_AND_SYNC_RULES.md").read_text()
    assert "Re-establish P0-01" not in text
    assert "five" in text.lower()


def test_drive_index_does_not_dispatch_old_tasks():
    text = (ROOT / "docs/project-state/BIELLA_DRIVE_LIVE_MANIFEST.md").read_text()
    assert "Current observed numbered boundary remains" not in text
    assert "Current active prompt:" not in text
    assert "not authorized before P3-05" not in text
    assert "1x35z0cZ-t3SM3Ma6mX5O4AMfFKnDcolv" in text


def test_dependent_historical_files_are_preserved_without_runtime_authority():
    base = ROOT / "docs/project-state"
    for name in ("BIELLA_LOCAL_AI_RUNTIME_DECISION_2026-09-04.md", "BIELLA_LOCAL_AI_RUNTIME_MANIFEST_2026-09-04.yaml"):
        text = (base / name).read_text()
        assert "HISTORICAL_EVIDENCE_ONLY" in text
        assert "07_BIELLA_PRODUCTION_SYSTEM.md" in text
    text = (base / "BIELLA_PROJECT_CONTEXT_SNAPSHOT_2026-08-26.md").read_text()
    assert "Execute only P0-01 and stop" not in text
    assert "SUPERSEDED_NON_AUTHORITY" in text
