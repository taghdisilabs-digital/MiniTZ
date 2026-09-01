"""Fail-closed import of external P4-03 routing-learning evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import cast

from .model_evaluation_evidence import EvidenceReality
from .project import ProjectRef
from .run import RunRef


class EvidenceImportError(ValueError):
    """External routing evidence is malformed, incomplete, or unbound."""


_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1024}")
_SHA = re.compile(r"[0-9a-f]{64}")
_SUITE = "p4-03-provider-neutral-routing-evidence-v1"
_CLASSIFICATION = "CONTROLLED_ROUTING_REPLAY_WITH_LIVE_RESOURCE_PROBES"
_REQUIRED_CASES = (
    "quality_critical",
    "latency_critical",
    "gpu_available",
    "gpu_unavailable",
    "gpu_recovered",
    "cold_start_unknown_evidence",
    "stale_evidence",
    "model_revision_mismatch",
    "predicted_vs_observed_calibration",
    "safe_shadow_exploration",
    "unsafe_exploration_rejected",
    "learned_state_failure_fallback",
)
_HARD_ORDER = (
    "CAPABILITY_MATCH",
    "TASK_SIDE_EFFECT_SAFETY",
    "RESOURCE_AVAILABILITY",
    "EVIDENCE_PRESENT",
    "EVIDENCE_FRESH",
    "MODEL_REVISION_MATCH",
    "RELIABILITY_FLOOR",
    "QUALITY_FLOOR",
    "LATENCY_CEILING",
)
_CHECKS = frozenset(
    {
        "all_required_cases_present",
        "bounded_shadow_exploration_task_safe_only",
        "capability_identity_unchanged",
        "cold_start_unknown_evidence_rejected",
        "failed_and_rejected_candidates_preserved",
        "final_compute_processes_zero",
        "final_gpu_memory_zero",
        "final_model_runtime_processes_zero",
        "gpu_available_observed_live",
        "gpu_recovery_observed_live",
        "gpu_unavailable_observed_process_scoped",
        "hard_constraints_precede_learning",
        "latency_critical_selects_lower_latency_eligible",
        "learned_state_failure_uses_deterministic_baseline",
        "no_chain_of_thought_recorded",
        "no_persistent_model_or_agent",
        "predicted_vs_observed_calibration_recorded",
        "quality_critical_selects_highest_quality_eligible",
        "raw_observations_preserved",
        "revision_mismatch_rejected",
        "source_identities_exact",
        "stale_evidence_rejected",
    }
)
P4_03_L40S_FIXTURE_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "post_run_resource.json": "7e767a9a0f4c30c8e0c4772d1fd252fcda13a0564c5ee2e433f461a3b8af2db1",
        "routing_evidence_manifest.json": "73c067dc3576188c38a4de5fe51b91285bb8af7068aee787e552f9c60faf3623",
        "routing_evidence_results.json": "9b592360af07be9e627f19c0e425c175ab5edef1cb9a803679d9ffc00a2d00ac",
        "routing_evidence_spec.json": "e0a4ccd1a471dd3ff5c0ed1a817d15a8baedcf1434e6c7a5aa960c8208ae2009",
    }
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise EvidenceImportError("external routing JSON contains a duplicate key")
        result[key] = value
    return result


def _json(payload: bytes, label: str) -> dict[str, object]:
    try:
        text = payload.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_pairs)
        canonical = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, EvidenceImportError):
            raise
        raise EvidenceImportError(f"{label} is not canonical UTF-8 JSON") from exc
    if not isinstance(value, dict) or payload not in {canonical, canonical + b"\n"}:
        raise EvidenceImportError(f"{label} is not an exact canonical object")
    return cast(dict[str, object], value)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise EvidenceImportError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise EvidenceImportError(f"{label} must be an array")
    return cast(list[object], value)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceImportError(message)


@dataclass(frozen=True)
class ExternalRoutingLearningArtifacts:
    spec: bytes
    results: bytes
    manifest: bytes
    post_run_resource: bytes

    def __post_init__(self) -> None:
        if any(not isinstance(value, bytes) or not value for value in self.named_bytes().values()):
            raise EvidenceImportError("external routing artifacts require non-empty exact bytes")

    @classmethod
    def from_directory(cls, directory: str | Path) -> "ExternalRoutingLearningArtifacts":
        root = Path(directory)
        try:
            return cls(
                (root / "routing_evidence_spec.json").read_bytes(),
                (root / "routing_evidence_results.json").read_bytes(),
                (root / "routing_evidence_manifest.json").read_bytes(),
                (root / "post_run_resource.json").read_bytes(),
            )
        except OSError as exc:
            raise EvidenceImportError("external routing artifact set is incomplete") from exc

    def named_bytes(self) -> Mapping[str, bytes]:
        return MappingProxyType(
            {
                "post_run_resource.json": self.post_run_resource,
                "routing_evidence_manifest.json": self.manifest,
                "routing_evidence_results.json": self.results,
                "routing_evidence_spec.json": self.spec,
            }
        )


@dataclass(frozen=True)
class RoutingEvidenceBinding:
    run_ref: RunRef
    artifact_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_ref, RunRef):
            raise EvidenceImportError("routing evidence Run identity is malformed")
        if not isinstance(self.artifact_ref, str) or _REF.fullmatch(self.artifact_ref) is None:
            raise EvidenceImportError("routing evidence Artifact identity is malformed")


@dataclass(frozen=True)
class ImportedRoutingLearningEvidence:
    project_ref: ProjectRef
    binding: RoutingEvidenceBinding
    artifact_sha256: Mapping[str, str]
    classification: str
    case_ids: tuple[str, ...]
    structural_checks: Mapping[str, bool]
    rejected_candidate_count: int
    raw_calibration_observation_count: int
    quality_critical_route: str
    latency_critical_route: str
    unavailable_route: str
    recovered_route: str
    learned_failure_route: str
    quality_calibration_mae: float
    latency_calibration_mae_seconds: float
    post_run_gpu_memory_mib: int
    post_run_compute_processes: int
    post_run_model_processes: int
    post_run_model_loads: int
    post_run_persistent_residency: bool
    evidence_reality: EvidenceReality = EvidenceReality.REAL
    identity_binding_reality: EvidenceReality = EvidenceReality.REFERENCE
    routing_allowed: bool = False
    promotion_allowed: bool = False
    evidence_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_sha256", MappingProxyType(dict(sorted(self.artifact_sha256.items()))))
        object.__setattr__(self, "structural_checks", MappingProxyType(dict(sorted(self.structural_checks.items()))))
        object.__setattr__(self, "evidence_sha256", hashlib.sha256(json.dumps({"artifacts": dict(self.artifact_sha256), "binding": self.binding.artifact_ref, "cases": list(self.case_ids), "project": self.project_ref.value}, separators=(",", ":"), sort_keys=True).encode()).hexdigest())

    @property
    def case_count(self) -> int:
        return len(self.case_ids)

    @property
    def structural_checks_passed(self) -> int:
        return sum(self.structural_checks.values())


def import_p4_03_l40s_evidence(
    project_ref: ProjectRef,
    artifacts: ExternalRoutingLearningArtifacts,
    binding: RoutingEvidenceBinding,
    *,
    require_exact_fixture: bool = True,
) -> ImportedRoutingLearningEvidence:
    """Bind exact external bytes as descriptive, non-routing Project evidence."""
    if not isinstance(project_ref, ProjectRef) or not isinstance(artifacts, ExternalRoutingLearningArtifacts) or not isinstance(binding, RoutingEvidenceBinding):
        raise EvidenceImportError("routing evidence import identities are malformed")
    if binding.run_ref.project_ref != project_ref:
        raise EvidenceImportError("routing evidence binding crossed Project scope")
    hashes = {name: _sha(payload) for name, payload in artifacts.named_bytes().items()}
    expected_run = "run_" + hashes["routing_evidence_results.json"][:32]
    _require(binding.run_ref.run_id == expected_run, "routing evidence Run binding differs from result bytes")
    if require_exact_fixture:
        _require(hashes == dict(P4_03_L40S_FIXTURE_SHA256), "routing evidence bytes differ from the qualified L40S fixture")

    spec = _json(artifacts.spec, "routing specification")
    results = _json(artifacts.results, "routing results")
    manifest = _json(artifacts.manifest, "routing manifest")
    post = _json(artifacts.post_run_resource, "routing post-run resource")
    for value, label in ((spec, "specification"), (results, "results"), (manifest, "manifest"), (post, "post-run resource")):
        _require(value.get("schema_version") == 1, f"routing {label} schema is unsupported")
    _require(spec.get("suite_id") == _SUITE == results.get("suite_id") == manifest.get("suite_id"), "routing suite identities differ")
    _require(spec.get("classification") == _CLASSIFICATION == results.get("classification") == manifest.get("classification"), "routing evidence classification differs")
    _require(tuple(_array(spec.get("required_cases"), "required cases")) == _REQUIRED_CASES, "required routing cases differ")
    _require(tuple(_array(spec.get("hard_constraint_order"), "hard constraint order")) == _HARD_ORDER, "hard routing constraint order changed")
    output_policy = _object(spec.get("output_policy"), "output policy")
    _require(output_policy.get("record_chain_of_thought") is False and output_policy.get("preserve_failed_and_rejected_candidates") is True and output_policy.get("preserve_raw_observations") is True, "routing output evidence policy changed")
    provider = _object(spec.get("provider_neutral_contract"), "provider-neutral contract")
    _require(provider.get("capability_mutation_forbidden") is True and provider.get("provider_specific_branching_forbidden") is True, "provider-neutral routing contract changed")
    _require(results.get("spec_canonical_sha256") == hashes["routing_evidence_spec.json"], "routing result specification binding differs")

    manifest_artifacts = _array(manifest.get("artifacts"), "manifest artifacts")
    manifest_by_name = {Path(cast(str, _object(item, "manifest artifact").get("path"))).name: _object(item, "manifest artifact") for item in manifest_artifacts}
    for name in ("routing_evidence_spec.json", "routing_evidence_results.json", "post_run_resource.json"):
        entry = manifest_by_name.get(name)
        _require(entry is not None and entry.get("sha256") == hashes[name] and entry.get("bytes") == len(artifacts.named_bytes()[name]), f"manifest binding for {name} differs")

    source_inputs = _object(results.get("source_inputs"), "source inputs")
    _require(source_inputs == _object(manifest.get("source_inputs"), "manifest source inputs"), "result and manifest source identities differ")
    _require(set(source_inputs) == {"p4_01_results", "p4_01_spec", "p4_02_manifest", "p4_02_results", "p4_02_spec"}, "source identity set differs")
    for name, source_value in source_inputs.items():
        identity = _object(source_value, f"source identity {name}")
        sha = identity.get("sha256")
        _require(identity.get("identity_status") == "PASS" and isinstance(sha, str) and _SHA.fullmatch(sha) is not None and sha == identity.get("expected_sha256"), f"source identity {name} is not exact")

    validation = _object(results.get("structural_validation"), "structural validation")
    checks = _object(validation.get("checks"), "structural checks")
    _require(validation.get("status") == "PASS" and set(checks) == _CHECKS and all(value is True for value in checks.values()), "routing structural validation did not pass exactly")
    _require(validation.get("required_case_count") == 12 and validation.get("observed_case_count") == 12 and validation.get("rejected_candidate_count") == 4 and validation.get("route_case_count") == 9, "routing structural counts differ")
    manifest_validation = _object(manifest.get("validation"), "manifest validation")
    _require(manifest_validation.get("status") == "PASS" and _object(manifest_validation.get("checks"), "manifest checks") == checks and manifest_validation.get("route_cases") == 9, "manifest validation differs from results")

    cases = tuple(_object(item, "routing case") for item in _array(results.get("cases"), "routing cases"))
    case_map = {cast(str, item.get("case_id")): item for item in cases}
    _require(len(case_map) == len(cases) == 12 and set(case_map) == set(_REQUIRED_CASES), "routing case evidence is missing or duplicated")
    expected_routes: Mapping[str, tuple[object, object]] = {
        "quality_critical": ("LEARNED_ROUTER", "m15_tool_on"),
        "latency_critical": ("LEARNED_ROUTER", "m15_specialist"),
        "gpu_available": ("LEARNED_ROUTER", "m15_s1"),
        "gpu_unavailable": ("NO_ELIGIBLE_CANDIDATE", None),
        "gpu_recovered": ("LEARNED_ROUTER", "m15_s1"),
        "cold_start_unknown_evidence": ("NO_ELIGIBLE_CANDIDATE", None),
        "stale_evidence": ("NO_ELIGIBLE_CANDIDATE", None),
        "model_revision_mismatch": ("NO_ELIGIBLE_CANDIDATE", None),
        "learned_state_failure_fallback": ("DETERMINISTIC_BASELINE_FALLBACK", "m15_s1"),
    }
    for case_id, (mode, selected) in expected_routes.items():
        case = case_map[case_id]
        _require(case.get("route_mode") == mode and case.get("selected_candidate_id") == selected, f"routing outcome {case_id} differs")
        trace = _array(case.get("trace"), f"routing trace {case_id}")
        _require(bool(trace) and _object(trace[0], "routing trace stage").get("stage") == "HARD_CONSTRAINTS_COMPLETE", f"hard constraints did not precede {case_id}")
    _require(case_map["learned_state_failure_fallback"].get("learned_state_status") == "FAILED", "learned-state failure fallback is absent")
    safe = case_map["safe_shadow_exploration"]
    unsafe = case_map["unsafe_exploration_rejected"]
    _require(safe.get("status") == "ENABLED" and safe.get("mode") == "SHADOW_REPLAY" and safe.get("authoritative_effect") is False and safe.get("live_model_invocations") == 0, "safe shadow exploration evidence differs")
    _require(unsafe.get("status") == "REJECTED" and unsafe.get("authoritative_effect") is False and unsafe.get("reason") == "TASK_SIDE_EFFECT_CLASS_NOT_EXPLORATION_SAFE", "unsafe exploration was not rejected")
    calibration_case = case_map["predicted_vs_observed_calibration"]
    aggregate = _object(calibration_case.get("aggregate"), "calibration aggregate")
    quality_mae = aggregate.get("quality_mae")
    latency_mae = aggregate.get("latency_mae_seconds")
    _require(calibration_case.get("status") == "PASS" and isinstance(quality_mae, (int, float)) and isinstance(latency_mae, (int, float)) and math.isfinite(float(quality_mae)) and math.isfinite(float(latency_mae)), "calibration aggregate is malformed")

    rejections = tuple(_object(item, "rejected candidate") for item in _array(results.get("rejected_candidates"), "rejected candidates"))
    _require(len(rejections) == 4 and {item.get("case_id") for item in rejections} == {"gpu_unavailable", "cold_start_unknown_evidence", "stale_evidence", "model_revision_mismatch"} and all(_array(item.get("rejected_by"), "rejection reasons") for item in rejections), "rejected candidate evidence differs")
    raw_calibration = tuple(_object(item, "raw calibration observation") for item in _array(results.get("raw_calibration_observations"), "raw calibration observations"))
    _require(len(raw_calibration) == 60 and all(item.get("infrastructure_status") == "PASS" and item.get("semantic_status") in {"PASS", "FAIL"} and isinstance(item.get("latency_seconds"), (int, float)) for item in raw_calibration), "raw calibration evidence is incomplete")
    capability = _object(results.get("capability_identity"), "capability identity")
    _require(capability.get("mutation") is False and capability.get("before_sha256") == capability.get("after_sha256"), "routing evidence mutated Capability identity")

    observations = {_object(item, "resource observation").get("observation_id"): _object(item, "resource observation") for item in _array(results.get("resource_observations"), "resource observations")}
    _require(set(observations) == {"gpu_start", "cuda_available", "cuda_process_scoped_unavailable", "cuda_recovered", "gpu_final"} and all(item.get("exit_code") == 0 for item in observations.values()), "live Resource observation set differs")
    available = _object(observations["cuda_available"].get("parsed"), "available CUDA observation")
    unavailable = _object(observations["cuda_process_scoped_unavailable"].get("parsed"), "unavailable CUDA observation")
    recovered = _object(observations["cuda_recovered"].get("parsed"), "recovered CUDA observation")
    _require(available.get("available") is True and available.get("device_count") == 1 and unavailable.get("available") is False and unavailable.get("device_count") == 0 and recovered.get("available") is True and recovered.get("device_count") == 1, "GPU availability/recovery observations differ")

    gpu = _object(post.get("gpu"), "post-run GPU")
    runtime = _object(spec.get("runtime"), "runtime identity")
    expected_device_name = runtime.get("expected_gpu_name")
    _require(isinstance(expected_device_name, str) and bool(expected_device_name) and gpu.get("name") == expected_device_name and gpu.get("memory_used_mib") == 0 and post.get("compute_process_count") == 0 and post.get("model_runtime_process_count") == 0 and post.get("model_loads_for_this_suite") == 0 and post.get("persistent_model_or_agent_residency") is False, "post-run accelerator residency was not released")
    summary = _object(manifest.get("result_summary"), "result summary")
    _require(summary.get("quality_critical_route") == "m15_tool_on" and summary.get("latency_critical_route") == "m15_specialist" and summary.get("unavailable_route") == "NO_ELIGIBLE_CANDIDATE" and summary.get("recovered_route") == "m15_s1" and summary.get("learned_failure_route") == "m15_s1", "manifest routing result summary differs")

    return ImportedRoutingLearningEvidence(
        project_ref,
        binding,
        hashes,
        _CLASSIFICATION,
        tuple(cast(str, item.get("case_id")) for item in cases),
        cast(Mapping[str, bool], checks),
        len(rejections),
        len(raw_calibration),
        cast(str, summary["quality_critical_route"]),
        cast(str, summary["latency_critical_route"]),
        cast(str, summary["unavailable_route"]),
        cast(str, summary["recovered_route"]),
        cast(str, summary["learned_failure_route"]),
        float(cast(int | float, quality_mae)),
        float(cast(int | float, latency_mae)),
        cast(int, gpu["memory_used_mib"]),
        cast(int, post["compute_process_count"]),
        cast(int, post["model_runtime_process_count"]),
        cast(int, post["model_loads_for_this_suite"]),
        cast(bool, post["persistent_model_or_agent_residency"]),
    )


__all__ = [
    "P4_03_L40S_FIXTURE_SHA256",
    "EvidenceImportError",
    "ExternalRoutingLearningArtifacts",
    "ImportedRoutingLearningEvidence",
    "RoutingEvidenceBinding",
    "import_p4_03_l40s_evidence",
]
