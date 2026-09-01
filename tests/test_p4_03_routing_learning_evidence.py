"""Fail-closed import tests for the REAL P4-03 L40S routing matrix."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from biella.model_evaluation_evidence import EvidenceReality
from biella.project import ProjectRef
from biella.routing_learning_evidence import (
    P4_03_L40S_FIXTURE_SHA256,
    EvidenceImportError,
    ExternalRoutingLearningArtifacts,
    RoutingEvidenceBinding,
    import_p4_03_l40s_evidence,
)
from biella.run import RunRef


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "p4_03_l40s_evidence"


def _object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def _canonical(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _artifacts() -> ExternalRoutingLearningArtifacts:
    return ExternalRoutingLearningArtifacts.from_directory(FIXTURE_DIRECTORY)


def _binding(project_ref: ProjectRef, artifacts: ExternalRoutingLearningArtifacts) -> RoutingEvidenceBinding:
    return RoutingEvidenceBinding(
        RunRef(project_ref, "run_" + hashlib.sha256(artifacts.results).hexdigest()[:32]),
        "artifact://external/p4-03-l40s/routing-matrix",
    )


def test_exact_l40s_bytes_import_as_real_bounded_routing_evidence() -> None:
    artifacts = _artifacts()
    assert {name: hashlib.sha256(payload).hexdigest() for name, payload in artifacts.named_bytes().items()} == dict(P4_03_L40S_FIXTURE_SHA256)
    project_ref = ProjectRef.new()
    imported = import_p4_03_l40s_evidence(project_ref, artifacts, _binding(project_ref, artifacts))

    assert imported.classification == "CONTROLLED_ROUTING_REPLAY_WITH_LIVE_RESOURCE_PROBES"
    assert imported.evidence_reality is EvidenceReality.REAL
    assert imported.identity_binding_reality is EvidenceReality.REFERENCE
    assert imported.case_count == 12
    assert imported.structural_checks_passed == 22
    assert imported.rejected_candidate_count == 4
    assert imported.raw_calibration_observation_count == 60
    assert imported.quality_critical_route == "m15_tool_on"
    assert imported.latency_critical_route == "m15_specialist"
    assert imported.unavailable_route == "NO_ELIGIBLE_CANDIDATE"
    assert imported.recovered_route == "m15_s1"
    assert imported.learned_failure_route == "m15_s1"
    assert imported.quality_calibration_mae == 0.0
    assert imported.latency_calibration_mae_seconds == pytest.approx(0.0016360651332888755)
    assert imported.post_run_gpu_memory_mib == 0
    assert imported.post_run_compute_processes == 0
    assert imported.post_run_model_processes == 0
    assert imported.post_run_model_loads == 0
    assert imported.post_run_persistent_residency is False
    assert imported.routing_allowed is False
    assert imported.promotion_allowed is False


@pytest.mark.parametrize("case", ("case_missing", "hard_order", "source_identity", "rejection_missing", "residency", "manifest_count"))
def test_routing_evidence_mutations_fail_closed(case: str) -> None:
    artifacts = _artifacts()
    spec = deepcopy(_object(json.loads(artifacts.spec)))
    results = deepcopy(_object(json.loads(artifacts.results)))
    manifest = deepcopy(_object(json.loads(artifacts.manifest)))
    post = deepcopy(_object(json.loads(artifacts.post_run_resource)))
    if case == "case_missing":
        _array(results["cases"]).pop()
    elif case == "hard_order":
        _array(spec["hard_constraint_order"]).reverse()
    elif case == "source_identity":
        _object(_object(results["source_inputs"])["p4_02_results"])["sha256"] = "0" * 64
    elif case == "rejection_missing":
        _array(results["rejected_candidates"]).pop()
    elif case == "residency":
        _object(post["gpu"])["memory_used_mib"] = 1
    else:
        _object(manifest["validation"])["route_cases"] = 8
    mutated = replace(artifacts, spec=_canonical(spec), results=_canonical(results), manifest=_canonical(manifest), post_run_resource=_canonical(post))
    project_ref = ProjectRef.new()
    with pytest.raises(EvidenceImportError):
        import_p4_03_l40s_evidence(project_ref, mutated, _binding(project_ref, mutated), require_exact_fixture=False)


def test_noncanonical_duplicate_key_and_cross_project_evidence_are_rejected() -> None:
    artifacts = _artifacts()
    project_ref = ProjectRef.new()
    with pytest.raises(EvidenceImportError):
        import_p4_03_l40s_evidence(project_ref, replace(artifacts, results=b" " + artifacts.results), _binding(project_ref, artifacts), require_exact_fixture=False)
    duplicate_spec = b'{"schema_version":1,' + artifacts.spec[1:]
    with pytest.raises(EvidenceImportError):
        import_p4_03_l40s_evidence(project_ref, replace(artifacts, spec=duplicate_spec), _binding(project_ref, artifacts), require_exact_fixture=False)
    foreign = ProjectRef.new()
    binding = replace(_binding(project_ref, artifacts), run_ref=RunRef(foreign, "run_" + "1" * 32))
    with pytest.raises(EvidenceImportError, match="Project"):
        import_p4_03_l40s_evidence(project_ref, artifacts, binding)
