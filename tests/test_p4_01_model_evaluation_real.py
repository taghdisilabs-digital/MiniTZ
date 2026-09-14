"""Focused REAL NVIDIA L40S model-evaluation evidence import tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from minitz_os.engine.model_evaluation import EvidenceClass
from minitz_os.engine.model_evaluation_evidence import (
    P4_01_L40S_FIXTURE_SHA256,
    CandidateEvidenceSummary,
    EvaluationCellBinding,
    EvaluationCellKey,
    EvidenceImportError,
    EvidenceReality,
    ExternalEvaluationArtifacts,
    import_p4_01_l40s_evidence,
)
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.run import RunRef


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "p4_01_l40s_evidence"


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _integer(value: object) -> int:
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _artifacts() -> ExternalEvaluationArtifacts:
    return ExternalEvaluationArtifacts.from_directory(FIXTURE_DIRECTORY)


def _bindings(
    artifacts: ExternalEvaluationArtifacts,
    project_ref: ProjectRef,
) -> tuple[EvaluationCellBinding, ...]:
    results = _object(cast(object, json.loads(artifacts.controlled_suite_results)))
    run_ref = RunRef(
        project_ref,
        "run_" + hashlib.sha256(artifacts.controlled_suite_results).hexdigest()[:32],
    )
    started_at = _text(results["run_started_at"])
    completed_at = _text(results["run_finished_at"])
    bindings: list[EvaluationCellBinding] = []
    for raw_cell in _array(results["cells"]):
        cell = _object(raw_cell)
        bindings.append(
            EvaluationCellBinding(
                coordinate=EvaluationCellKey(
                    _text(cell["candidate_id"]),
                    _text(cell["task_id"]),
                    _integer(cell["repetition"]),
                ),
                run_ref=run_ref,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
    return tuple(bindings)


def _summary_by_candidate(
    summaries: tuple[CandidateEvidenceSummary, ...],
) -> dict[str, CandidateEvidenceSummary]:
    return {item.candidate_id: item for item in summaries}


def test_exact_worker_bytes_import_as_real_quasi_controlled_evidence() -> None:
    artifacts = _artifacts()
    observed_hashes = {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in artifacts.named_bytes().items()
    }
    assert observed_hashes == dict(P4_01_L40S_FIXTURE_SHA256)

    project_ref = ProjectRef.new()
    imported = import_p4_01_l40s_evidence(
        project_ref,
        artifacts,
        _bindings(artifacts, project_ref),
    )

    assert imported.evidence_reality is EvidenceReality.REAL
    assert imported.identity_binding_reality is EvidenceReality.REFERENCE
    assert imported.suite.evidence_class is EvidenceClass.QUASI_CONTROLLED
    assert imported.suite.confounders == {
        "cell_identity_binding": "reference_project_and_run_identity_not_worker_native",
        "cell_timing": "reference_suite_envelope_not_worker_cell_timestamp",
        "engine_execution_capture": "historical_external_worker_import_without_native_engine_authority",
        "vram_attribution": "process_wide_with_both_models_resident",
    }
    assert len(imported.cells) == len(imported.result.runs) == 30
    assert len({item.coordinate for item in imported.cells}) == 30
    assert [item.sequence_index for item in imported.cells] == list(range(1, 31))
    assert all(item.cache_state == "WARM" and item.retry_count == 0 for item in imported.cells)
    assert all(item.provider_queue_seconds is None for item in imported.cells)
    assert all(item.remote_resource_seconds is None for item in imported.cells)
    assert all(item.timeout_seconds is None and item.cost is None for item in imported.cells)
    assert all(item.run.cost is None for item in imported.cells)
    assert all(not item.run.tool_calls for item in imported.cells)
    assert all(not item.run.resource_snapshots for item in imported.cells)

    first = imported.cells[0]
    assert hashlib.sha256(first.raw_output.encode("utf-8")).hexdigest() == first.raw_output_sha256
    assert first.run.token_count == first.prompt_tokens + first.completion_tokens
    assert first.run.resource_metrics["latency.seconds"] == first.model_latency_seconds
    assert first.run.resource_metrics["provider.queue_seconds"] is None
    assert first.run.resource_metrics["resource.remote_seconds"] is None

    summaries = _summary_by_candidate(imported.summaries)
    small = summaries["qwen2.5-0.5b-instruct"]
    large = summaries["qwen2.5-1.5b-instruct"]
    assert small.revision == "7ae557604adf67be50417f59c2c2f167def9a775"
    assert large.revision == "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
    assert (small.semantic_pass, small.sample_cells) == (3, 15)
    assert (large.semantic_pass, large.sample_cells) == (12, 15)
    assert small.model_latency_mean_seconds == pytest.approx(0.14227793353331133)
    assert small.model_latency_median_seconds == pytest.approx(0.07308083699990675)
    assert large.model_latency_mean_seconds == pytest.approx(0.049920118066665964)
    assert large.model_latency_median_seconds == pytest.approx(0.04410559699999794)

    comparison = imported.result.pairwise_comparisons[0]
    assert (comparison.paired_wins, comparison.paired_losses, comparison.paired_ties) == (0, 9, 6)
    assert comparison.conclusion == "DESCRIPTIVE"
    assert comparison.winner is None
    assert comparison.resource_confounder_ref == imported.suite.resource_policy_ref
    assert imported.significance_test_performed is False
    assert imported.universal_winner_claimed is False
    assert imported.knowledge_candidate.promotion_allowed is False
    assert imported.knowledge_candidate.routing_allowed is False


@pytest.mark.parametrize(
    "case",
    ("tampered_output", "missing_cell", "duplicate_cell", "fabricated_cost", "resource_mislabel"),
)
def test_reference_mutations_fail_closed_at_the_evidence_boundary(case: str) -> None:
    artifacts = _artifacts()
    root = deepcopy(_object(cast(object, json.loads(artifacts.controlled_suite_results))))
    cells = _array(root["cells"])
    if case == "tampered_output":
        _object(cells[0])["output"] = "tampered"
    elif case == "missing_cell":
        cells.pop()
    elif case == "duplicate_cell":
        cells.append(deepcopy(cells[0]))
    elif case == "fabricated_cost":
        _object(cells[0])["cost"] = 0.0
    else:
        identities = _object(root["identities"])
        resource_identity = _object(identities["resource"])
        resource_value = _object(resource_identity["value"])
        resource_value["gpu_name"] = "NVIDIA A100"
        resource_identity["sha256"] = hashlib.sha256(_canonical(resource_value)).hexdigest()

    mutated = replace(artifacts, controlled_suite_results=_canonical(root))
    project_ref = ProjectRef.new()
    with pytest.raises(EvidenceImportError):
        import_p4_01_l40s_evidence(
            project_ref,
            mutated,
            _bindings(mutated, project_ref),
            require_real=False,
        )


def test_noncanonical_and_duplicate_key_json_are_rejected() -> None:
    artifacts = _artifacts()
    project_ref = ProjectRef.new()
    noncanonical = replace(
        artifacts,
        controlled_suite_results=b" " + artifacts.controlled_suite_results,
    )
    with pytest.raises(EvidenceImportError):
        import_p4_01_l40s_evidence(
            project_ref,
            noncanonical,
            _bindings(noncanonical, project_ref),
            require_real=False,
        )

    duplicate_key_spec = (
        b'{"schema_version":1,' + artifacts.controlled_suite_spec[1:]
    )
    duplicate = replace(artifacts, controlled_suite_spec=duplicate_key_spec)
    with pytest.raises(EvidenceImportError):
        import_p4_01_l40s_evidence(
            project_ref,
            duplicate,
            _bindings(duplicate, project_ref),
            require_real=False,
        )


def test_cross_project_identity_binding_is_rejected() -> None:
    artifacts = _artifacts()
    project_ref = ProjectRef.new()
    bindings = list(_bindings(artifacts, project_ref))
    foreign = ProjectRef.new()
    bindings[0] = replace(
        bindings[0],
        run_ref=RunRef(foreign, bindings[0].run_ref.run_id),
    )
    with pytest.raises(EvidenceImportError, match="Project"):
        import_p4_01_l40s_evidence(project_ref, artifacts, tuple(bindings))
