"""Focused REAL NVIDIA L40S strategy-evaluation evidence import tests."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from minitz_os.engine.model_evaluation import EvidenceClass
from minitz_os.engine.model_evaluation_evidence import EvidenceReality
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.run import RunRef
from minitz_os.engine.strategy_evaluation import StrategyEffectKind
from minitz_os.engine.strategy_evaluation_evidence import (
    P4_02_L40S_FIXTURE_SHA256,
    EvidenceImportError,
    ExternalStrategyEvaluationArtifacts,
    StrategyEvidenceBinding,
    import_p4_02_l40s_evidence,
)


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "p4_02_l40s_evidence"


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _artifacts() -> ExternalStrategyEvaluationArtifacts:
    return ExternalStrategyEvaluationArtifacts.from_directory(FIXTURE_DIRECTORY)


def _binding(project_ref: ProjectRef, artifacts: ExternalStrategyEvaluationArtifacts) -> StrategyEvidenceBinding:
    return StrategyEvidenceBinding(
        RunRef(project_ref, "run_" + hashlib.sha256(artifacts.results).hexdigest()[:32]),
        "artifact://external/p4-02-l40s/controlled-suite",
    )


def test_exact_worker_bytes_import_as_real_quasi_controlled_strategy_evidence() -> None:
    artifacts = _artifacts()
    assert {
        name: hashlib.sha256(payload).hexdigest()
        for name, payload in artifacts.named_bytes().items()
    } == dict(P4_02_L40S_FIXTURE_SHA256)

    project_ref = ProjectRef.new()
    imported = import_p4_02_l40s_evidence(
        project_ref,
        artifacts,
        _binding(project_ref, artifacts),
    )

    assert imported.evidence_reality is EvidenceReality.REAL
    assert imported.identity_binding_reality is EvidenceReality.REFERENCE
    assert len(imported.raw_cells) == 120
    assert len({item.cell_id for item in imported.raw_cells}) == 120
    assert len(imported.matrices) == 6
    assert sum(len(item.result.runs) for item in imported.matrices) == 210
    assert all(item.experiment.evidence_class is EvidenceClass.QUASI_CONTROLLED for item in imported.matrices)
    assert all(item.result.universal_winner_claimed is False for item in imported.matrices)
    assert all(item.result.mandatory_agent_hierarchy_created is False for item in imported.matrices)
    assert all(item.promotion_allowed is False and item.routing_allowed is False for item in imported.knowledge_candidates)
    assert imported.infrastructure_pass == 120
    assert (imported.semantic_pass, imported.semantic_fail) == (69, 51)
    assert imported.model_invocations == 138
    assert imported.tool_calls == 15
    assert imported.post_run_gpu_memory_mib == 0
    assert imported.post_run_model_processes == 0
    assert imported.post_run_persistent_residency is False
    assert sum(len(item.invocation_refs) for item in imported.raw_cells) == 150
    assert sum(len(item.tool_call_refs) for item in imported.raw_cells) == 15
    assert all(item.identity_sha256 for item in imported.raw_cells)

    matrices = {item.matrix_id: item for item in imported.matrices}
    same = matrices["same_model_s1_s2"].result
    same_comparison = same.pairwise_comparisons[0]
    assert (same_comparison.paired_wins, same_comparison.paired_losses, same_comparison.paired_ties) == (9, 0, 6)
    assert {item.effect_kind for item in same.effects} == {StrategyEffectKind.STRATEGY}

    tool_comparison = matrices["tool_policy"].result.pairwise_comparisons[0]
    assert (tool_comparison.paired_wins, tool_comparison.paired_losses, tool_comparison.paired_ties) == (0, 3, 12)

    factorial = matrices["model_strategy_factorial"].result
    assert {item.effect_kind for item in factorial.effects} == {
        StrategyEffectKind.MODEL,
        StrategyEffectKind.STRATEGY,
        StrategyEffectKind.INTERACTION,
    }
    summaries = imported.variant_summaries
    assert (summaries["m15_parallel"].physical_model_invocations, summaries["m15_s1"].physical_model_invocations) == (3, 15)
    assert summaries["m15_parallel"].unique_invocation_latency_seconds == pytest.approx(0.33251176800013127)
    assert summaries["m15_s1"].unique_invocation_latency_seconds == pytest.approx(0.7398038410005938)
    assert summaries["m15_tool_on"].semantic_pass == 15


@pytest.mark.parametrize(
    "case",
    ("tampered_output", "missing_cell", "identity_mismatch", "residency_not_released", "count_mismatch"),
)
def test_real_evidence_mutations_fail_closed_at_import_boundary(case: str) -> None:
    artifacts = _artifacts()
    results = deepcopy(_object(cast(object, json.loads(artifacts.results))))
    manifest = deepcopy(_object(cast(object, json.loads(artifacts.manifest))))
    post = deepcopy(_object(cast(object, json.loads(artifacts.post_run_resource))))
    if case == "tampered_output":
        _object(_array(results["cells"])[0])["final_output"] = "tampered"
    elif case == "missing_cell":
        _array(results["cells"]).pop()
    elif case == "identity_mismatch":
        identity = _object(_object(_array(results["cells"])[0])["identity_sha256"])
        identity["model"] = "0" * 64
    elif case == "residency_not_released":
        _object(post["gpu"])["memory_used_mib"] = 1
    else:
        _object(manifest["validation"])["observed_cells"] = 119

    mutated = replace(
        artifacts,
        results=_canonical(results),
        manifest=_canonical(manifest),
        post_run_resource=_canonical(post),
    )
    project_ref = ProjectRef.new()
    with pytest.raises(EvidenceImportError):
        import_p4_02_l40s_evidence(
            project_ref,
            mutated,
            _binding(project_ref, mutated),
            require_real=False,
        )


def test_noncanonical_and_duplicate_key_strategy_json_are_rejected() -> None:
    artifacts = _artifacts()
    project_ref = ProjectRef.new()
    noncanonical = replace(artifacts, results=b" " + artifacts.results)
    with pytest.raises(EvidenceImportError):
        import_p4_02_l40s_evidence(
            project_ref,
            noncanonical,
            _binding(project_ref, noncanonical),
            require_real=False,
        )

    duplicate_spec = b'{"schema_version":1,' + artifacts.spec[1:]
    duplicate = replace(artifacts, spec=duplicate_spec)
    with pytest.raises(EvidenceImportError):
        import_p4_02_l40s_evidence(
            project_ref,
            duplicate,
            _binding(project_ref, duplicate),
            require_real=False,
        )


def test_cross_project_strategy_binding_is_rejected() -> None:
    artifacts = _artifacts()
    project_ref = ProjectRef.new()
    foreign = ProjectRef.new()
    binding = replace(_binding(project_ref, artifacts), run_ref=RunRef(foreign, "run_" + "1" * 32))
    with pytest.raises(EvidenceImportError, match="Project"):
        import_p4_02_l40s_evidence(project_ref, artifacts, binding)
