"""Fail-closed import of external P4-04 locality measurement evidence."""

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

from .project import ProjectRef
from .run import RunRef


class EvidenceImportError(ValueError):
    """External locality evidence is malformed, incomplete, or unbound."""


_SHA = re.compile(r"[0-9a-f]{64}")
_SUITE = "p4-04-real-locality-placement-evidence-v1"
_CLASSIFICATION = "CONTROLLED_LOCALITY_MEASUREMENT"
_REQUIRED_CASES = (
    "cold_vs_warm_exact_model",
    "model_residency_load_vram_latency",
    "warm_overloaded_vs_cold_idle",
    "local_vs_transferred_exact_artifact",
    "valid_vs_stale_workspace_toolchain",
    "build_render_cache_hit_miss_rebuild",
    "retention_value_pressure_congestion_fragmentation",
)
_CASE_ALIASES = (
    "cold_warm_match",
    "overload",
    "artifact_transfer",
    "stale_workspace",
    "stale_toolchain",
    "render_rebuild",
    "retention_pressure",
)
_SOURCE_INPUTS = frozenset(
    {
        "p4_01_results",
        "p4_01_spec",
        "p4_02_manifest",
        "p4_02_results",
        "p4_02_spec",
        "p4_03_manifest",
        "p4_03_post_resource",
        "p4_03_results",
        "p4_03_spec",
    }
)
_CHECKS = frozenset(
    {
        "all_required_cases_present",
        "artifact_bytes_exact",
        "artifact_local_exact",
        "artifact_transferred_exact",
        "blender_cuda_render_recorded",
        "cache_hit_faster_than_rebuild",
        "cold_warm_output_exact",
        "congestion_penalty_observed",
        "exact_model_revision_used",
        "exact_runtime_and_prompt_reused_within_model_case",
        "final_gpu_compute_processes_zero",
        "final_gpu_vram_zero",
        "final_model_render_processes_zero",
        "fragmentation_cleanup_returned_to_model_baseline",
        "fragmentation_retained_unused_observed",
        "materialization_throughput_recorded",
        "model_load_residency_vram_latency_recorded",
        "no_authoritative_routing_or_promotion_claim",
        "persistent_idle_residency_false",
        "render_cache_hit_exact",
        "retention_value_includes_pressure_congestion_fragmentation",
        "source_identities_exact",
        "stale_render_key_rebuilt",
        "stale_workspace_identity_rejected",
        "valid_workspace_identity_accepted",
        "warm_overloaded_vs_cold_idle_recorded",
    }
)
P4_04_L40S_FIXTURE_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "locality_evidence_manifest.json": "e3c17f7991caf24ae320d6ca899e098ff608e2ccce6eef3d8b75b379d9088d87",
        "locality_evidence_results.json": "978d907094c0ead0d70687ffe194d13310a7900410f2dd6d8c7d1202d169cbed",
        "locality_evidence_spec.json": "4d1a1caf3f7cac4d21fe93582a6c69a160cb1986924002bf3f1c5f6b0f1c1745",
        "post_run_resource.json": "ad302a331e445a7f3f5edbc5ef2cd4f8c6aca8e2a556c6096df86c501f2f92d9",
    }
)
_RUNNER_SHA256 = "56f2c735acc8e34a906f2925bdfab79ae2dc2d9373be09a33eb248f7060bbf79"
_RENDER_FIXTURE_SHA256 = "34b1d956f2cc211064d9d5a511615e15ca530dfb615d511310405ab60d8d9c58"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise EvidenceImportError("external locality JSON contains a duplicate key")
        result[key] = value
    return result


def _json(payload: bytes, label: str) -> dict[str, object]:
    try:
        text = payload.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_pairs)
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
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


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise EvidenceImportError(f"{label} must be finite")
    result = float(value)
    if (positive and result <= 0.0) or (not positive and result < 0.0):
        raise EvidenceImportError(f"{label} is outside its allowed range")
    return result


def _integer(value: object, label: str, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise EvidenceImportError(f"{label} must be an integer")
    if (positive and value <= 0) or (not positive and value < 0):
        raise EvidenceImportError(f"{label} is outside its allowed range")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceImportError(message)


@dataclass(frozen=True, init=False)
class ExternalLocalityArtifacts:
    """Exact external bytes, named by the canonical four-file contract."""

    spec: bytes
    results: bytes
    manifest: bytes
    post_run_resource: bytes

    def __init__(self, **named_bytes: bytes) -> None:
        expected = set(P4_04_L40S_FIXTURE_SHA256)
        if set(named_bytes) != expected:
            raise EvidenceImportError("external locality artifact set is incomplete or contains extras")
        for name, payload in named_bytes.items():
            if not isinstance(payload, bytes) or not payload:
                raise EvidenceImportError(f"external locality artifact {name} requires non-empty exact bytes")
        object.__setattr__(self, "spec", named_bytes["locality_evidence_spec.json"])
        object.__setattr__(self, "results", named_bytes["locality_evidence_results.json"])
        object.__setattr__(self, "manifest", named_bytes["locality_evidence_manifest.json"])
        object.__setattr__(self, "post_run_resource", named_bytes["post_run_resource.json"])

    @classmethod
    def from_directory(cls, directory: str | Path) -> "ExternalLocalityArtifacts":
        root = Path(directory)
        try:
            return cls(**{name: (root / name).read_bytes() for name in P4_04_L40S_FIXTURE_SHA256})
        except OSError as exc:
            raise EvidenceImportError("external locality artifact set is incomplete") from exc

    def named_bytes(self) -> Mapping[str, bytes]:
        return MappingProxyType(
            {
                "locality_evidence_manifest.json": self.manifest,
                "locality_evidence_results.json": self.results,
                "locality_evidence_spec.json": self.spec,
                "post_run_resource.json": self.post_run_resource,
            }
        )


@dataclass(frozen=True)
class LocalityEvidenceBinding:
    project_ref: ProjectRef
    run_ref: RunRef

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.run_ref, RunRef):
            raise EvidenceImportError("locality evidence binding identity is malformed")
        if self.run_ref.project_ref != self.project_ref:
            raise EvidenceImportError("locality evidence binding crossed Project scope")


@dataclass(frozen=True)
class ImportedLocalityEvidence:
    project_ref: ProjectRef | None
    binding: LocalityEvidenceBinding | None
    artifact_sha256: Mapping[str, str]
    classification: str
    case_ids: tuple[str, ...]
    cases: tuple[str, ...]
    structural_check_results: Mapping[str, bool]
    cold_latency_seconds: float
    warm_latency_seconds: float
    warm_overloaded_latency_seconds: float
    load_seconds: float
    residency_allocated_bytes: int
    artifact_bytes: int
    artifact_content_sha256: str
    local_materialization_seconds: float
    transferred_materialization_seconds: float
    cache_miss_seconds: float
    cache_hit_seconds: float
    stale_rebuild_seconds: float
    fragmentation_retained_unused_bytes: int
    congestion_penalty_seconds: float
    post_run_gpu_memory_mib: int
    post_run_processes: int
    post_run_residency: bool
    reality: str = "REAL"
    identity_binding: str = "REFERENCE"
    routing_allowed: bool = False
    promotion_allowed: bool = False
    correctness_authority_allowed: bool = False
    evidence_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_sha256", MappingProxyType(dict(sorted(self.artifact_sha256.items()))))
        object.__setattr__(
            self,
            "structural_check_results",
            MappingProxyType(dict(sorted(self.structural_check_results.items()))),
        )
        binding_payload: object
        if self.binding is None:
            binding_payload = None
        else:
            binding_payload = {
                "project": self.binding.project_ref.value,
                "run": self.binding.run_ref.run_id,
            }
        object.__setattr__(
            self,
            "evidence_sha256",
            hashlib.sha256(
                json.dumps(
                    {
                        "artifacts": dict(self.artifact_sha256),
                        "binding": binding_payload,
                        "cases": list(self.case_ids),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
        )

    @property
    def structural_checks(self) -> int:
        return sum(self.structural_check_results.values())


def import_p4_04_l40s_evidence(**values: object) -> ImportedLocalityEvidence:
    """Import exact measurement bytes as descriptive, non-routing evidence."""
    binding_value = values.pop("binding", None)
    if binding_value is not None and not isinstance(binding_value, LocalityEvidenceBinding):
        raise EvidenceImportError("locality evidence binding is malformed")
    binding = binding_value
    exact_value = values.pop("require_exact_fixture", True)
    if not isinstance(exact_value, bool):
        raise EvidenceImportError("exact-fixture requirement must be boolean")
    require_exact_fixture = exact_value
    named_bytes: dict[str, bytes] = {}
    for name, payload in values.items():
        if not isinstance(payload, bytes):
            raise EvidenceImportError(f"external locality artifact {name} must contain exact bytes")
        named_bytes[name] = payload
    artifacts = ExternalLocalityArtifacts(**named_bytes)
    hashes = {name: _sha(payload) for name, payload in artifacts.named_bytes().items()}
    if require_exact_fixture:
        _require(hashes == dict(P4_04_L40S_FIXTURE_SHA256), "locality evidence bytes differ from the qualified fixture")
    if binding is not None:
        expected_run = "run_" + hashes["locality_evidence_results.json"][:32]
        _require(binding.run_ref.run_id == expected_run, "locality evidence Run binding differs from result bytes")

    spec = _json(artifacts.spec, "locality specification")
    results = _json(artifacts.results, "locality results")
    manifest = _json(artifacts.manifest, "locality manifest")
    post = _json(artifacts.post_run_resource, "locality post-run resource")
    for document, label in ((spec, "specification"), (results, "results"), (manifest, "manifest"), (post, "post-run resource")):
        _require(document.get("schema_version") == 1, f"locality {label} schema is unsupported")
    _require(spec.get("suite_id") == _SUITE == results.get("suite_id") == manifest.get("suite_id"), "locality suite identities differ")
    _require(spec.get("classification") == _CLASSIFICATION == results.get("classification") == manifest.get("classification"), "locality classifications differ")
    _require(tuple(_array(spec.get("required_cases"), "required locality cases")) == _REQUIRED_CASES, "required locality cases differ")
    _require(results.get("spec_canonical_sha256") == hashes["locality_evidence_spec.json"], "locality result specification binding differs")

    output_policy = _object(spec.get("output_policy"), "locality output policy")
    interpretation = _object(spec.get("interpretation_policy"), "locality interpretation policy")
    cleanup = _object(spec.get("cleanup_policy"), "locality cleanup policy")
    _require(output_policy.get("canonical_json") is True and output_policy.get("raw_observations") is True and output_policy.get("record_chain_of_thought") is False and output_policy.get("sidecar_sha256") is True, "locality output policy changed")
    _require(interpretation.get("descriptive_only") is True and interpretation.get("authoritative_routing_claims") is False and interpretation.get("promotion_claims") is False and interpretation.get("universal_locality_claims") is False, "locality evidence asserted authority")
    _require(cleanup.get("gpu_compute_processes_final") == 0 and cleanup.get("model_processes_final") == 0 and cleanup.get("persistent_idle_residency") is False and cleanup.get("release_model_vram") is True, "locality cleanup contract changed")

    source_inputs = _object(results.get("source_inputs"), "locality source inputs")
    _require(source_inputs == _object(manifest.get("source_inputs"), "manifest source inputs"), "result and manifest source identities differ")
    _require(set(source_inputs) == _SOURCE_INPUTS, "locality source identity set differs")
    for name, source_value in source_inputs.items():
        identity = _object(source_value, f"source identity {name}")
        digest = identity.get("sha256")
        _require(identity.get("identity_status") == "PASS" and isinstance(digest, str) and _SHA.fullmatch(digest) is not None and digest == identity.get("expected_sha256"), f"source identity {name} is not exact")

    manifest_artifacts = tuple(_object(item, "manifest artifact") for item in _array(manifest.get("artifacts"), "manifest artifacts"))
    manifest_by_name = {Path(cast(str, item.get("path"))).name: item for item in manifest_artifacts}
    expected_manifest_hashes = {
        "locality_evidence_results.json": hashes["locality_evidence_results.json"],
        "locality_evidence_spec.json": hashes["locality_evidence_spec.json"],
        "post_run_resource.json": hashes["post_run_resource.json"],
        "render_fixture.py": _RENDER_FIXTURE_SHA256,
        "run_locality_evidence.py": _RUNNER_SHA256,
    }
    for name, digest in expected_manifest_hashes.items():
        entry = manifest_by_name.get(name)
        _require(entry is not None and entry.get("sha256") == digest and _integer(entry.get("bytes"), f"manifest bytes for {name}", positive=True) > 0, f"manifest binding for {name} differs")

    validation = _object(results.get("structural_validation"), "locality structural validation")
    checks = _object(validation.get("checks"), "locality structural checks")
    _require(validation.get("status") == "PASS" and set(checks) == _CHECKS and all(value is True for value in checks.values()), "locality structural validation did not pass exactly")
    _require(validation.get("required_case_count") == 7 and validation.get("observed_case_count") == 7, "locality structural case counts differ")
    manifest_validation = _object(manifest.get("validation"), "manifest validation")
    _require(manifest.get("run_exit_code") == 0 and manifest_validation.get("status") == "PASS" and manifest_validation.get("case_count") == 7 and _object(manifest_validation.get("checks"), "manifest structural checks") == checks and tuple(_array(manifest_validation.get("required_cases"), "manifest required cases")) == _REQUIRED_CASES and tuple(_array(manifest_validation.get("observed_cases"), "manifest observed cases")) == _REQUIRED_CASES, "manifest validation differs from results")

    cases = tuple(_object(item, "locality case") for item in _array(results.get("cases"), "locality cases"))
    case_map = {cast(str, item.get("case_id")): item for item in cases}
    _require(len(case_map) == len(cases) == 7 and tuple(case_map) == _REQUIRED_CASES and all(item.get("status") == "PASS" for item in cases), "locality cases are missing, duplicated, reordered, or failed")

    cold_warm = case_map["cold_vs_warm_exact_model"]
    cold = _object(cold_warm.get("cold"), "cold inference")
    warm = _object(cold_warm.get("warm"), "warm inference")
    cold_seconds = _number(cold.get("latency_seconds"), "cold latency", positive=True)
    warm_seconds = _number(warm.get("latency_seconds"), "warm latency", positive=True)
    cold_output_sha = cold.get("output_sha256")
    _require(cold_warm.get("exact_output_equivalence") is True and cold.get("output") == warm.get("output") and isinstance(cold_output_sha, str) and _SHA.fullmatch(cold_output_sha) is not None and warm.get("output_sha256") == cold_output_sha and warm_seconds < cold_seconds, "cold and warm exact-output evidence differs")
    implementation_identity = _object(cold_warm.get("model_identity"), "implementation identity")
    experiment = _object(spec.get("model_experiment"), "implementation experiment")
    _require(implementation_identity.get("revision") == experiment.get("revision") and implementation_identity.get("model_id") == experiment.get("model_id"), "exact implementation revision differs")

    residency = case_map["model_residency_load_vram_latency"]
    load = _object(residency.get("load"), "load observation")
    residency_value = _object(residency.get("residency"), "residency observation")
    latencies = _object(residency.get("latencies_seconds"), "residency latencies")
    load_seconds = _number(load.get("combined_load_seconds"), "combined load", positive=True)
    allocated_bytes = _integer(residency_value.get("allocated_bytes"), "resident allocated bytes", positive=True)
    overloaded_seconds = _number(latencies.get("warm_overloaded"), "warm overloaded latency", positive=True)
    _require(residency_value.get("persistent_after_suite") is False and latencies.get("cold") == cold.get("latency_seconds") and latencies.get("warm") == warm.get("latency_seconds"), "residency latency identity differs")

    overload = case_map["warm_overloaded_vs_cold_idle"]
    cold_idle = _object(overload.get("cold_idle"), "cold-idle observation")
    warm_overloaded = _object(overload.get("warm_overloaded"), "warm-overloaded observation")
    comparison = _object(overload.get("descriptive_comparison"), "overload comparison")
    _require(overload.get("exact_output_equivalence") is True and cold_idle.get("inference_latency_seconds") == cold.get("latency_seconds") and warm_overloaded.get("inference_latency_seconds") == overloaded_seconds and _number(comparison.get("overloaded_minus_cold_inference_seconds"), "overload penalty", positive=True) > 0.0, "warm-overloaded versus cold-idle evidence differs")

    transfer_case = case_map["local_vs_transferred_exact_artifact"]
    content_ref = _object(transfer_case.get("content_ref"), "transferred content identity")
    local = _object(transfer_case.get("local_materialization"), "local materialization")
    transferred = _object(transfer_case.get("transferred_materialization"), "transferred materialization")
    artifact_bytes = _integer(transfer_case.get("bytes"), "Artifact bytes", positive=True)
    artifact_digest = content_ref.get("digest")
    local_seconds = _number(local.get("seconds"), "local materialization", positive=True)
    transferred_seconds = _number(transferred.get("end_to_end_seconds"), "transferred materialization", positive=True)
    _require(content_ref.get("algorithm") == "sha256" and isinstance(artifact_digest, str) and _SHA.fullmatch(artifact_digest) is not None and local.get("exact") is True and transferred.get("exact") is True and local.get("sha256") == artifact_digest == transferred.get("sha256") == transferred.get("source_sha256") == transferred.get("destination_sha256") and transferred.get("artifact_bytes") == artifact_bytes == transferred.get("destination_bytes") and transferred_seconds > local_seconds and _number(local.get("throughput_bytes_per_second"), "local throughput", positive=True) > 0.0 and _number(transferred.get("payload_throughput_bytes_per_second"), "transfer throughput", positive=True) > 0.0, "local and transferred Artifact evidence differs")

    workspace = case_map["valid_vs_stale_workspace_toolchain"]
    valid = _object(workspace.get("valid_candidate"), "valid Workspace identity")
    stale = _object(workspace.get("stale_candidate"), "stale Workspace identity")
    required_fields = tuple(_array(workspace.get("required_fields"), "Workspace identity fields"))
    workspace_policy = _object(spec.get("workspace_toolchain_policy"), "Workspace policy")
    valid_digest = valid.get("identity_sha256")
    stale_digest = stale.get("identity_sha256")
    stale_mismatches = set(_array(stale.get("mismatches"), "stale Workspace mismatches"))
    _require(required_fields == tuple(_array(workspace_policy.get("required_identity_fields"), "required Workspace policy fields")) and workspace_policy.get("stale_or_mismatched_action") == "REJECT" and valid.get("status") == "VALID" and valid.get("mismatches") == [] and valid_digest == workspace.get("expected_identity_sha256") and isinstance(valid_digest, str) and _SHA.fullmatch(valid_digest) is not None and stale.get("status") == "STALE_REJECTED" and isinstance(stale_digest, str) and _SHA.fullmatch(stale_digest) is not None and stale_digest != valid_digest and stale_mismatches == {"blender_version", "model_revision"}, "Workspace or toolchain compatibility evidence differs")

    render = case_map["build_render_cache_hit_miss_rebuild"]
    miss = _object(render.get("cache_miss"), "render cache miss")
    hit = _object(render.get("cache_hit"), "render cache hit")
    rebuild = _object(render.get("stale_input_rebuild"), "stale render rebuild")
    miss_seconds = _number(miss.get("wall_seconds"), "render cache miss", positive=True)
    hit_seconds = _number(hit.get("seconds"), "render cache hit", positive=True)
    rebuild_seconds = _number(render.get("rebuild_cost_seconds"), "stale render rebuild", positive=True)
    _require(miss.get("cache_status") == "MISS_REBUILT" and rebuild.get("cache_status") == "MISS_REBUILT" and hit.get("exact") is True and hit.get("source_sha256") == hit.get("materialized_sha256") == miss.get("image_sha256") and miss.get("cache_key") == hit.get("cache_key") and rebuild.get("cache_key") != hit.get("cache_key") and rebuild.get("wall_seconds") == render.get("rebuild_cost_seconds") and hit_seconds < rebuild_seconds and hit_seconds < miss_seconds, "render cache hit, miss, or stale rebuild evidence differs")

    retention_case = case_map["retention_value_pressure_congestion_fragmentation"]
    retention = _object(results.get("retention_measurement"), "retention measurement")
    _require(retention == _object(retention_case.get("measured_value_and_costs"), "case retention measurement") and retention_case.get("interpretation") == "DESCRIPTIVE_BOUNDED_MEASUREMENT_NO_PLACEMENT_OR_PROMOTION_CLAIM", "retention evidence asserted authority or diverged")
    retained_fragmentation = _integer(_object(retention.get("fragmentation_negative_effect"), "fragmentation evidence").get("retained_unused_bytes_at_gap"), "fragmentation retained-unused bytes", positive=True)
    congestion_penalty = _number(_object(retention.get("pressure_congestion_negative_effect"), "congestion evidence").get("latency_penalty_seconds"), "congestion penalty", positive=True)
    _require(_number(_object(retention.get("model"), "retained implementation evidence").get("warm_idle_time_saved_vs_cold_seconds"), "warm retained benefit", positive=True) > 0.0 and _number(_object(retention.get("artifact"), "retained Artifact evidence").get("transfer_penalty_seconds"), "Artifact transfer benefit", positive=True) > 0.0 and _number(_object(retention.get("render_cache"), "render retention evidence").get("rebuild_cost_vs_hit_seconds"), "render rebuild benefit", positive=True) > 0.0, "retention benefit evidence is incomplete")

    result_constraints = _object(results.get("interpretation_constraints"), "result interpretation constraints")
    _require(result_constraints == interpretation and len(_array(results.get("known_confounders"), "known confounders")) >= 1 and len(_object(results.get("raw_observations"), "raw locality observations")) >= 1, "locality interpretation or raw evidence is incomplete")

    gpu = _object(post.get("gpu"), "post-run accelerator")
    compute_count = _integer(post.get("compute_process_count"), "post-run compute processes")
    runtime_count = _integer(post.get("model_or_render_process_count"), "post-run implementation processes")
    post_gpu_memory = _integer(gpu.get("memory_used_mib"), "post-run accelerator memory")
    _require(post_gpu_memory == 0 and compute_count == 0 and runtime_count == 0 and post.get("compute_processes") == [] and post.get("model_or_render_processes") == [] and post.get("model_process_exited") is True and post.get("persistent_idle_residency") is False and post.get("model_loads_for_suite") == 1 and _integer(gpu.get("memory_total_mib"), "accelerator capacity", positive=True) > 0, "post-run residency was not released")
    manifest_post = _object(manifest.get("post_run_resource"), "manifest post-run Resource")
    _require(manifest_post.get("artifact_sha256") == hashes["post_run_resource.json"] and manifest_post.get("gpu_memory_used_mib") == 0 and manifest_post.get("compute_process_count") == 0 and manifest_post.get("model_or_render_process_count") == 0 and manifest_post.get("persistent_idle_residency") is False, "manifest post-run Resource binding differs")

    measured = _object(manifest.get("measured_results"), "manifest measured results")
    _require(measured.get("cold_latency_seconds") == cold.get("latency_seconds") and measured.get("warm_latency_seconds") == warm.get("latency_seconds") and measured.get("warm_overloaded_latency_seconds") == overloaded_seconds and measured.get("model_load_seconds") == load_seconds and measured.get("model_residency_allocated_bytes") == allocated_bytes and measured.get("artifact_bytes") == artifact_bytes and measured.get("local_materialization_seconds") == local_seconds and measured.get("transferred_materialization_seconds") == transferred_seconds and measured.get("cache_miss_render_seconds") == miss_seconds and measured.get("cache_hit_seconds") == hit_seconds and measured.get("stale_rebuild_seconds") == rebuild_seconds and measured.get("fragmentation_retained_unused_bytes") == retained_fragmentation, "manifest measured results differ from raw cases")

    return ImportedLocalityEvidence(
        None if binding is None else binding.project_ref,
        binding,
        hashes,
        _CLASSIFICATION,
        _REQUIRED_CASES,
        _REQUIRED_CASES + _CASE_ALIASES,
        cast(Mapping[str, bool], checks),
        cold_seconds,
        warm_seconds,
        overloaded_seconds,
        load_seconds,
        allocated_bytes,
        artifact_bytes,
        cast(str, artifact_digest),
        local_seconds,
        transferred_seconds,
        miss_seconds,
        hit_seconds,
        rebuild_seconds,
        retained_fragmentation,
        congestion_penalty,
        post_gpu_memory,
        compute_count + runtime_count,
        cast(bool, post["persistent_idle_residency"]),
    )


__all__ = [
    "P4_04_L40S_FIXTURE_SHA256",
    "EvidenceImportError",
    "ExternalLocalityArtifacts",
    "ImportedLocalityEvidence",
    "LocalityEvidenceBinding",
    "import_p4_04_l40s_evidence",
]
