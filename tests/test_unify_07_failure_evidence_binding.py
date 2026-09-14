from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from minitz_os.engine.failure_repair_learning import (
    FailureLearningContractError,
    FailureLearningService,
)
from minitz_os.engine.project import ProjectRef


def _failure(
    project: ProjectRef | None,
    *,
    evidence_ref: str = "journal-evidence://sha256/" + "a" * 64,
    classification: str = "PROCESS_FAILED",
) -> dict[str, object]:
    provenance: dict[str, str] = {
        "task_id": "UNIFY-07",
        "run_id": "run-42",
        "attempt_id": "attempt-1822",
    }
    if project is not None:
        provenance["project_ref"] = project.value
    return {
        "schema": "minitz.operational_evidence_projection/v1",
        "source_kind": "FAILURE",
        "evidence_ref": evidence_ref,
        "journal_event_ref": "journal-event://minitz-production-events-v1/35349",
        "failure_classification": classification,
        "status": "OUT_OF_CREDIT",
        "recorded_at": "2026-09-11T20:02:39.057872+00:00",
        "provider": "mistral",
        "model": "mistral-large",
        "provenance": provenance,
    }


def test_unified_failure_evidence_binds_exact_identity_once(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    project = ProjectRef.new()
    first = service.record_unified_failure_evidence(
        _failure(project),
        resource_context={"resource": "provider:mistral", "context": "commander.requirements"},
    )
    second = service.record_unified_failure_evidence(
        _failure(project),
        resource_context={"resource": "provider:mistral", "context": "commander.requirements"},
    )

    assert first.learning_state == "RECORDED"
    assert second == first
    assert first.failure_classification == "PROCESS_FAILED"
    assert first.evidence_ref == "journal-evidence://sha256/" + "a" * 64
    assert first.project_ref == project
    assert first.observation is not None
    assert first.evidence_ref in first.observation.raw_evidence_refs
    assert first.observation.failure_category == "PROCESS_FAILED"
    assert first.observation.environment_summary["resource"] == "provider:mistral"
    assert first.observation.environment_summary["context"] == "commander.requirements"

    with sqlite3.connect(service.database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM failure_evidence_bindings").fetchone()[0]
        observations = connection.execute("SELECT COUNT(*) FROM failure_observations").fetchone()[0]
    assert count == 1
    assert observations == 1


def test_projectless_failure_remains_evidence_without_blocking_or_fabricating_scope(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    binding = service.record_unified_failure_evidence(_failure(None))
    assert binding.learning_state == "UNAVAILABLE_SCOPE"
    assert binding.observation is None
    assert binding.project_ref is None
    assert binding.evidence_ref.endswith("a" * 64)
    with sqlite3.connect(service.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM failure_observations").fetchone()[0] == 0


def test_failure_classification_is_not_rewritten_into_provider_health(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    project = ProjectRef.new()
    binding = service.record_unified_failure_evidence(
        _failure(project, classification="DEADLINE_EXCEEDED"),
        resource_context={"resource": "provider:mistral", "provider_state": "OUT_OF_CREDIT"},
    )
    assert binding.failure_classification == "DEADLINE_EXCEEDED"
    assert binding.observation is not None
    assert binding.observation.failure_category == "DEADLINE_EXCEEDED"
    assert binding.observation.environment_summary["provider_state"] == "OUT_OF_CREDIT"


def test_conflicting_reuse_of_exact_failure_identity_is_rejected(tmp_path: Path) -> None:
    service = FailureLearningService(tmp_path / "learning.sqlite3")
    project = ProjectRef.new()
    service.record_unified_failure_evidence(_failure(project, classification="PROCESS_FAILED"))
    with pytest.raises(FailureLearningContractError):
        service.record_unified_failure_evidence(_failure(project, classification="VALIDATION_REJECTED"))


def test_live_failure_projection_feeds_learning_nonblocking(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    ops = Path(__file__).parents[1] / "ops" / "local-ai"
    monkeypatch.syspath_prepend(str(ops))
    import minitz_memory_compactor as memory_compactor  # type: ignore[import-not-found]
    import minitz_production_events as production_events  # type: ignore[import-not-found]

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    project = ProjectRef.new()
    journal = production_events.ProductionEventJournal(runtime / "events.jsonl", failure_path=runtime / "failures.jsonl")
    journal.emit(
        "commander.assist_failed",
        task_id="UNIFY-07",
        status="OUT_OF_CREDIT",
        failure_type="PROCESS_FAILED",
        text="provider route exhausted",
        project_ref=project.value,
        provider="mistral",
        model="mistral-large",
    )

    summary = memory_compactor.refresh_failure_learning_projection(runtime, current_task_id="UNIFY-07")
    assert summary["authority"] == "NONE_DERIVED_LEARNING"
    assert summary["recorded"] == 1
    assert summary["unavailable_scope"] == 0
    assert summary["rejected"] == 0
    assert (runtime / "memory" / "failure-learning.sqlite3").is_file()

    again = memory_compactor.refresh_failure_learning_projection(runtime, current_task_id="UNIFY-07")
    assert again["recorded"] == 1
    with sqlite3.connect(runtime / "memory" / "failure-learning.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM failure_evidence_bindings").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM failure_observations").fetchone()[0] == 1


def test_live_failure_learning_unavailable_scope_and_bad_rows_do_not_block(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    ops = Path(__file__).parents[1] / "ops" / "local-ai"
    monkeypatch.syspath_prepend(str(ops))
    import minitz_memory_compactor as memory_compactor

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "failures.jsonl").write_text(
        '{"seq":1,"time":"2026-09-11T20:00:00+00:00","schema":"minitz.failure_event/v1","task_id":"UNIFY-07","failure_type":"PROCESS_FAILED","status":"OUT_OF_CREDIT"}\n'
        '{broken json\n',
        encoding="utf-8",
    )
    summary = memory_compactor.refresh_failure_learning_projection(runtime, current_task_id="UNIFY-07")
    assert summary["unavailable_scope"] == 1
    assert summary["rejected"] >= 1
    assert summary["blocking"] is False
