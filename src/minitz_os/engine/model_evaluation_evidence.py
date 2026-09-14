"""Fail-closed import of provider-neutral external model-evaluation evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import fmean, median, pstdev
from types import MappingProxyType
from typing import NoReturn, cast
import unicodedata

from .artifact import ContentRef
from .call_ledger import ModelCall, ToolCall
from .capability import CapabilityRef
from .context_retrieval import ContextReceipt
from .model_evaluation import (
    DescriptiveStatistics,
    EvaluationContractError,
    EvaluationTask,
    EvaluationTaskSet,
    EvidenceClass,
    ModelCandidate,
    ModelEvaluationKnowledgeCandidate,
    ModelEvaluationResult,
    ModelEvaluationRun,
    ModelEvaluationSuite,
    PairwiseComparison,
    WorkloadProfile,
)
from .project import ProjectRef
from .resource import ResourceSnapshot
from .run import RunRef
from .validation import EvaluationResult, ValidationResult


_SHA256 = re.compile(r"[0-9a-f]{64}")
_SHA1 = re.compile(r"[0-9a-f]{40}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")

P4_01_L40S_FIXTURE_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "controlled_suite_results.json": "7928b7a5e23c1e8dd6b64734c1503f517b123e4910a24b4dc7c04de2ab0bc3fb",
        "controlled_suite_spec.json": "0c8af78b5f57d9ac3899af842f3867dfec05cbd9cbbd0d0769c8bdb76f70858f",
        "environment_manifest.json": "8c57ed8f96fbd2ca8f42547f5632f9584447d7859ab05f157b26a5cb1a6ec764",
        "models_manifest.json": "4826c0b36aebae3ab82e6d047b36ab111c31adfbc4c53d66d630c8fab8c580c9",
    }
)

_EXPECTED_IDENTITY_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "environment": "c735b2a34675ef4dc484595fcf1f932b057c9ab7bb8da738245fd9c1ee00bf29",
        "policy": "9c5c87c3a9b58ed4de5205a4dcfd35d35e4a39213be4e99db04bc49a72f93d95",
        "resource": "b93b6eab89138fa424aa381449068c69bf5ea8160c982d2eea1a5b99a7c5215b",
        "suite": "1aee626abb3d4c2a4f693df5bb571167f9c0eb4dc4a8f721a4ecf7e7904efe9e",
        "taskset": "25f9a3c930cdf46b7c316ae4a660f92c3850beaaab65661dae9953474fb73a46",
        "workload": "ee939a8422413256cc51be26c09f530d5b6672820fd0ad2dacab47767c00bf79",
    }
)
_EXPECTED_MODEL_IDENTITY_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "qwen2.5-0.5b-instruct": "9c4e33a12ad7d039f8403cccd221c9185db7a191c425b6c2b58fe2486491671e",
        "qwen2.5-1.5b-instruct": "f62783555bc55e310721188d3b9ccf7c0489152a412dd3c811a2c9af841c9c94",
    }
)
_EXPECTED_ENVIRONMENT_CANONICAL_SHA256 = (
    "03630dd53def46c7798a2c50561ac754a069edc1f836be1d78f0bc8067f54dbf"
)
_EXPECTED_MODELS_CANONICAL_SHA256 = (
    "5525d5e679621f9033a3e7dce78a0706467fb8e9ec3118799172aa6c7b6561f3"
)
_EXPECTED_SUITE_ID = "p4-01-controlled-paired-text-reasoning-v1"
_EXPECTED_CANDIDATES = (
    "qwen2.5-0.5b-instruct",
    "qwen2.5-1.5b-instruct",
)
_RESULTS_KEYS = {
    "cells",
    "descriptive_summaries",
    "execution",
    "identities",
    "interpretation_constraints",
    "known_confounders",
    "paired_raw_outcomes",
    "primary_variable",
    "run_finished_at",
    "run_started_at",
    "run_wall_seconds",
    "schema_version",
    "structural_validation",
    "suite_id",
}
_CELL_KEYS = {
    "cache_state",
    "candidate_id",
    "completion_tokens",
    "completion_tokens_per_second",
    "cost",
    "infrastructure_error",
    "infrastructure_status",
    "model_id",
    "model_latency_seconds",
    "model_position_in_pair",
    "output",
    "output_sha256",
    "pair_index",
    "peak_allocated_vram_bytes",
    "peak_reserved_vram_bytes",
    "prompt",
    "prompt_sha256",
    "prompt_tokens",
    "queue_seconds",
    "remote_resource_seconds",
    "rendered_prompt",
    "rendered_prompt_sha256",
    "repetition",
    "retry_count",
    "revision",
    "semantic_validation",
    "sequence_index",
    "task_id",
    "timeout_seconds",
    "tool_count",
    "transport_success",
}
_IMPORT_CONFOUNDERS: Mapping[str, str] = MappingProxyType(
    {
        "cell_identity_binding": "reference_project_and_run_identity_not_worker_native",
        "cell_timing": "reference_suite_envelope_not_worker_cell_timestamp",
        "engine_execution_capture": "historical_external_worker_import_without_native_engine_authority",
        "vram_attribution": "process_wide_with_both_models_resident",
    }
)
_EXPECTED_REPORTED_CONFOUNDERS = (
    "The task set is intentionally small and exact-answer; it does not establish broad capability or a universal winner.",
    "Both models remain resident on one GPU, so per-cell peak VRAM is process-wide and includes both loaded model weights.",
    "Generation latency excludes prompt construction/tokenization but includes synchronized autoregressive generation and cache allocation.",
    "Greedy decoding is deterministic at the policy level, while low-level GPU kernels and host scheduling can introduce timing variation.",
    "A latency over the exact timeout threshold is classified after the bounded generation call returns; it is not retried.",
    "Local in-process invocation has no network transport, queue, remote resource metering, tool use, or attributable API cost.",
    "Candidate-first order is balanced to within one pair because the design contains an odd number of pairs.",
)


class EvidenceImportError(ValueError):
    """External evaluation bytes are incomplete, inconsistent, or overclaimed."""


class EvidenceReality(str, Enum):
    REAL = "REAL"
    REFERENCE = "REFERENCE"


@dataclass(frozen=True)
class ExternalEvaluationArtifacts:
    environment_manifest: bytes
    models_manifest: bytes
    controlled_suite_spec: bytes
    controlled_suite_results: bytes

    def __post_init__(self) -> None:
        for name, payload in self.named_bytes().items():
            if not isinstance(payload, bytes) or not payload:
                raise EvidenceImportError(f"{name} must be nonempty immutable bytes")

    @classmethod
    def from_directory(cls, directory: Path) -> ExternalEvaluationArtifacts:
        if not isinstance(directory, Path):
            raise EvidenceImportError("evidence directory must be a Path")
        return cls(
            (directory / "environment_manifest.json").read_bytes(),
            (directory / "models_manifest.json").read_bytes(),
            (directory / "controlled_suite_spec.json").read_bytes(),
            (directory / "controlled_suite_results.json").read_bytes(),
        )

    def named_bytes(self) -> Mapping[str, bytes]:
        return MappingProxyType(
            {
                "controlled_suite_results.json": self.controlled_suite_results,
                "controlled_suite_spec.json": self.controlled_suite_spec,
                "environment_manifest.json": self.environment_manifest,
                "models_manifest.json": self.models_manifest,
            }
        )

    def sha256(self) -> Mapping[str, str]:
        return MappingProxyType(
            {
                name: hashlib.sha256(payload).hexdigest()
                for name, payload in sorted(self.named_bytes().items())
            }
        )


@dataclass(frozen=True, order=True)
class EvaluationCellKey:
    candidate_id: str
    task_id: str
    repetition: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.candidate_id, "candidate identity"),
            (self.task_id, "task identity"),
        ):
            if not isinstance(value, str) or _KEY.fullmatch(value) is None:
                raise EvidenceImportError(f"{label} is malformed")
        if (
            not isinstance(self.repetition, int)
            or isinstance(self.repetition, bool)
            or self.repetition < 1
        ):
            raise EvidenceImportError("repetition must be positive")


@dataclass(frozen=True)
class EvaluationCellBinding:
    """Engine identities/evidence supplied after the external run; always REFERENCE."""

    coordinate: EvaluationCellKey
    run_ref: RunRef
    started_at: str
    completed_at: str | None
    model_calls: tuple[ModelCall, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    evaluation_results: tuple[EvaluationResult, ...] = ()
    context_receipt: ContextReceipt | None = None
    resource_snapshots: tuple[ResourceSnapshot, ...] = ()
    reality: EvidenceReality = field(default=EvidenceReality.REFERENCE, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.coordinate, EvaluationCellKey) or not isinstance(
            self.run_ref, RunRef
        ):
            raise EvidenceImportError("cell binding identity is malformed")
        if not isinstance(self.started_at, str) or (
            self.completed_at is not None and not isinstance(self.completed_at, str)
        ):
            raise EvidenceImportError("cell binding timestamps are malformed")
        if not all(
            isinstance(items, tuple)
            for items in (
                self.model_calls,
                self.tool_calls,
                self.validation_results,
                self.evaluation_results,
                self.resource_snapshots,
            )
        ):
            raise EvidenceImportError("cell binding evidence must be immutable tuples")
        if not all(isinstance(item, ModelCall) for item in self.model_calls):
            raise EvidenceImportError("cell binding ModelCall evidence is malformed")
        if not all(isinstance(item, ToolCall) for item in self.tool_calls):
            raise EvidenceImportError("cell binding ToolCall evidence is malformed")
        if not all(isinstance(item, ValidationResult) for item in self.validation_results):
            raise EvidenceImportError("cell binding ValidationResult evidence is malformed")
        if not all(isinstance(item, EvaluationResult) for item in self.evaluation_results):
            raise EvidenceImportError("cell binding EvaluationResult evidence is malformed")
        if self.context_receipt is not None and not isinstance(
            self.context_receipt, ContextReceipt
        ):
            raise EvidenceImportError("cell binding ContextReceipt evidence is malformed")
        if not all(isinstance(item, ResourceSnapshot) for item in self.resource_snapshots):
            raise EvidenceImportError("cell binding ResourceSnapshot evidence is malformed")


@dataclass(frozen=True)
class CandidateEvidenceSummary:
    candidate_id: str
    implementation_name: str
    revision: str
    sample_cells: int
    semantic_pass: int
    semantic_fail: int
    semantic_pass_rate: float
    infrastructure_pass: int
    infrastructure_fail_or_timeout: int
    model_latency_mean_seconds: float
    model_latency_median_seconds: float
    model_latency_minimum_seconds: float
    model_latency_maximum_seconds: float
    completion_tokens_per_second_mean: float
    completion_tokens_per_second_median: float
    prompt_tokens_total: int
    completion_tokens_total: int
    maximum_peak_allocated_vram_bytes: int
    maximum_peak_reserved_vram_bytes: int
    cost: None = field(default=None, init=False)
    provider_queue_seconds: None = field(default=None, init=False)
    remote_resource_seconds: None = field(default=None, init=False)


@dataclass(frozen=True)
class ImportedEvaluationCell:
    coordinate: EvaluationCellKey
    run: ModelEvaluationRun
    implementation_name: str
    revision: str
    sequence_index: int
    pair_index: int
    model_position_in_pair: int
    cache_state: str
    retry_count: int
    raw_output: str
    raw_output_sha256: str
    prompt_tokens: int
    completion_tokens: int
    model_latency_seconds: float
    completion_tokens_per_second: float
    peak_allocated_vram_bytes: int
    peak_reserved_vram_bytes: int
    semantic_pass: bool
    provider_queue_seconds: None = field(default=None, init=False)
    remote_resource_seconds: None = field(default=None, init=False)
    timeout_seconds: None = field(default=None, init=False)
    cost: None = field(default=None, init=False)


@dataclass(frozen=True)
class ImportedModelEvaluationEvidence:
    evidence_reality: EvidenceReality
    identity_binding_reality: EvidenceReality
    fixture_sha256: Mapping[str, str]
    suite: ModelEvaluationSuite
    cells: tuple[ImportedEvaluationCell, ...]
    summaries: tuple[CandidateEvidenceSummary, ...]
    result: ModelEvaluationResult
    knowledge_candidate: ModelEvaluationKnowledgeCandidate
    reported_confounders: tuple[str, ...]
    significance_test_performed: bool = field(default=False, init=False)
    universal_winner_claimed: bool = field(default=False, init=False)


@dataclass(frozen=True)
class _CandidateIdentity:
    candidate_id: str
    implementation_name: str
    revision: str
    identity_sha256: str


@dataclass(frozen=True)
class _IdentityEvidence:
    candidates: Mapping[str, _CandidateIdentity]
    workload: Mapping[str, object]
    policy_sha256: str
    resource_sha256: str


@dataclass(frozen=True)
class _Cell:
    key: EvaluationCellKey
    implementation_name: str
    revision: str
    sequence_index: int
    pair_index: int
    model_position_in_pair: int
    cache_state: str
    retry_count: int
    output: str
    output_sha256: str
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
    completion_tokens_per_second: float
    peak_allocated_vram_bytes: int
    peak_reserved_vram_bytes: int
    semantic_pass: bool


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvidenceImportError("evidence is not canonical JSON data") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceImportError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise EvidenceImportError(f"non-finite JSON constant is forbidden: {value}")


def _load_document(
    payload: bytes,
    label: str,
    *,
    canonical_required: bool,
    maximum_bytes: int,
) -> dict[str, object]:
    if len(payload) > maximum_bytes:
        raise EvidenceImportError(f"{label} exceeds its byte bound")
    try:
        text = payload.decode("utf-8")
        parsed = cast(
            object,
            json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            ),
        )
    except EvidenceImportError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise EvidenceImportError(f"{label} is not strict UTF-8 JSON") from exc
    result = _object(parsed, label)
    if canonical_required and _canonical_bytes(result) != payload:
        raise EvidenceImportError(f"{label} is not exact canonical JSON")
    return result


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise EvidenceImportError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise EvidenceImportError(f"{label} must be a JSON array")
    return cast(list[object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise EvidenceImportError(f"{label} must be nonempty text")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise EvidenceImportError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, label: str, *, minimum: float = 0.0) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < minimum
    ):
        raise EvidenceImportError(f"{label} must be finite and >= {minimum}")
    return float(value)


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceImportError(f"{label} must be boolean")
    return value


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise EvidenceImportError(f"{label} must be a SHA-256 digest")
    return text


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise EvidenceImportError(
            f"{label} keys differ; missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def _expect(value: object, expected: object, label: str) -> None:
    if value != expected:
        raise EvidenceImportError(f"{label} differs from exact evidence contract")


def _close(value: float, expected: float, label: str) -> None:
    if not math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise EvidenceImportError(f"{label} differs from raw-cell recomputation")


def _timestamp(value: object, label: str) -> str:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceImportError(f"{label} is not an RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceImportError(f"{label} lacks timezone authority")
    return text


def _validate_static_documents(
    environment: dict[str, object],
    models: dict[str, object],
    spec: dict[str, object],
) -> None:
    if _digest(environment) != _EXPECTED_ENVIRONMENT_CANONICAL_SHA256:
        raise EvidenceImportError("environment manifest canonical digest differs")
    if _digest(models) != _EXPECTED_MODELS_CANONICAL_SHA256:
        raise EvidenceImportError("models manifest canonical digest differs")
    if _digest(spec) != P4_01_L40S_FIXTURE_SHA256["controlled_suite_spec.json"]:
        raise EvidenceImportError("controlled suite specification digest differs")
    _expect(spec.get("schema_version"), 1, "suite schema version")
    _expect(spec.get("suite_id"), _EXPECTED_SUITE_ID, "suite identity")
    _expect(spec.get("primary_variable"), "MODEL_IMPLEMENTATION", "primary variable")
    _expect(spec.get("repetitions"), 3, "repetition count")

    randomization = _object(spec.get("randomization"), "randomization")
    _expect(
        randomization,
        {
            "algorithm": "python_random_mt19937_v1",
            "balance_rule": "candidate-first counts differ by at most one; candidate cells adjacent within each pair",
            "pairing_unit": ["task_id", "repetition"],
            "seed": 40120260901,
        },
        "seeded randomization policy",
    )
    resource = _object(spec.get("resource"), "resource policy")
    _text(resource.get("expected_gpu_name"), "resource GPU")
    _expect(resource.get("expected_gpu_count"), 1, "resource GPU count")
    _expect(resource.get("execution"), "sequential_single_process_no_daemon", "execution")
    _expect(resource.get("keep_both_models_loaded_if_feasible"), True, "model residency")

    candidates = _array(spec.get("candidates"), "spec candidates")
    if len(candidates) != 2:
        raise EvidenceImportError("suite must contain exactly two candidates")
    observed: set[str] = set()
    for candidate_value in candidates:
        candidate = _object(candidate_value, "spec candidate")
        _expect_keys(
            candidate,
            {"candidate_id", "model_id", "revision", "snapshot_path"},
            "spec candidate",
        )
        candidate_id = _text(candidate["candidate_id"], "candidate identity")
        revision = _text(candidate["revision"], "candidate revision")
        if _SHA1.fullmatch(revision) is None:
            raise EvidenceImportError("candidate revision is not immutable SHA-1")
        snapshot = _text(candidate["snapshot_path"], "candidate snapshot")
        if not snapshot.endswith(f"/{revision}"):
            raise EvidenceImportError("candidate snapshot does not bind its revision")
        observed.add(candidate_id)
    if observed != set(_EXPECTED_CANDIDATES):
        raise EvidenceImportError("candidate set differs from exact worker evidence")

    manifest_models = _array(models.get("models"), "models manifest")
    _expect(models.get("model_count"), 2, "models manifest count")
    if len(manifest_models) != 2:
        raise EvidenceImportError("models manifest entries differ from count")
    by_model_id = {
        _text(_object(item, "models manifest entry").get("model_id"), "model id"):
        _object(item, "models manifest entry")
        for item in manifest_models
    }
    for candidate_value in candidates:
        candidate = _object(candidate_value, "spec candidate")
        manifest = by_model_id.get(_text(candidate["model_id"], "candidate model id"))
        if manifest is None:
            raise EvidenceImportError("candidate is absent from models manifest")
        _expect(manifest.get("resolved_revision_sha"), candidate["revision"], "model revision")
        _expect(manifest.get("snapshot_path"), candidate["snapshot_path"], "model snapshot")
        _expect(manifest.get("access"), "public_anonymous", "model access")


def _identity_value(
    identities: Mapping[str, object],
    name: str,
) -> dict[str, object]:
    node = _object(identities.get(name), f"{name} identity")
    _expect_keys(node, {"sha256", "value"}, f"{name} identity")
    digest = _sha(node["sha256"], f"{name} identity digest")
    value = _object(node["value"], f"{name} identity value")
    if digest != _digest(value):
        raise EvidenceImportError(f"{name} identity digest disagrees with its value")
    expected = _EXPECTED_IDENTITY_SHA256[name]
    if digest != expected:
        raise EvidenceImportError(f"{name} identity differs from exact worker evidence")
    return value


def _validate_identities(
    results: dict[str, object],
    environment: dict[str, object],
    models: dict[str, object],
    spec: dict[str, object],
) -> _IdentityEvidence:
    identities = _object(results.get("identities"), "results identities")
    _expect_keys(
        identities,
        {
            "environment",
            "models",
            "models_manifest_canonical_sha256",
            "policy",
            "resource",
            "suite",
            "taskset",
            "workload",
        },
        "results identities",
    )
    suite = _identity_value(identities, "suite")
    taskset = _identity_value(identities, "taskset")
    workload = _identity_value(identities, "workload")
    policy = _identity_value(identities, "policy")
    resource = _identity_value(identities, "resource")
    environment_identity = _identity_value(identities, "environment")

    _expect(
        suite,
        {
            "schema_version": 1,
            "spec_canonical_sha256": P4_01_L40S_FIXTURE_SHA256[
                "controlled_suite_spec.json"
            ],
            "suite_id": _EXPECTED_SUITE_ID,
        },
        "suite identity value",
    )
    _expect(
        taskset,
        {"tasks": spec["tasks"], "validation": spec["validation"]},
        "task-set identity value",
    )
    execution = _object(results.get("execution"), "execution")
    _expect(
        workload,
        {
            "actual_sequence": execution["actual_sequence"],
            "pairing_unit": ["task_id", "repetition"],
            "repetitions": 3,
            "seed": 40120260901,
        },
        "workload identity value",
    )
    _expect(
        policy,
        {
            key: spec[key]
            for key in (
                "analysis_policy",
                "cache_policy",
                "chat_context",
                "generation",
                "output_policy",
                "runtime",
            )
        },
        "shared policy identity",
    )

    _expect(
        identities["models_manifest_canonical_sha256"],
        _EXPECTED_MODELS_CANONICAL_SHA256,
        "models manifest canonical digest",
    )
    _expect(
        environment_identity.get("environment_manifest"),
        environment,
        "embedded environment manifest",
    )
    _expect(
        environment_identity.get("environment_manifest_canonical_sha256"),
        _EXPECTED_ENVIRONMENT_CANONICAL_SHA256,
        "environment manifest canonical digest",
    )

    observed_environment = _object(
        environment_identity.get("observed"), "observed environment"
    )
    observed_resource = _object(
        observed_environment.get("resource"), "observed resource"
    )
    gpu_name = _text(resource.get("gpu_name"), "resource GPU name")
    _expect(resource.get("torch_device_name"), gpu_name, "torch GPU name")
    _expect(resource.get("single_gpu"), True, "single-GPU condition")
    _expect(resource.get("sequential_execution"), True, "sequential condition")
    _expect(resource.get("daemon_started"), False, "daemon condition")
    for result_key, observed_key in (
        ("compute_capability", "compute_capability"),
        ("driver_version", "driver_version"),
        ("execution_host", "execution_host"),
        ("gpu_name", "gpu_name"),
        ("gpu_uuid", "gpu_uuid"),
        ("memory_total_mib", "memory_total_mib"),
        ("torch_device_name", "torch_device_name"),
    ):
        _expect(
            resource.get(result_key),
            observed_resource.get(observed_key),
            f"resource agreement {result_key}",
        )
    environment_gpu = _object(environment.get("gpu"), "environment GPU")
    environment_host = _object(environment.get("host"), "environment host")
    _expect(resource.get("gpu_name"), environment_gpu.get("name"), "manifest GPU")
    _expect(resource.get("gpu_uuid"), environment_gpu.get("uuid"), "manifest GPU UUID")
    _expect(
        resource.get("execution_host"),
        environment_host.get("hostname"),
        "manifest execution host",
    )

    spec_candidates = {
        _text(_object(item, "spec candidate").get("candidate_id"), "candidate identity"):
        _object(item, "spec candidate")
        for item in _array(spec.get("candidates"), "spec candidates")
    }
    manifest_candidates = {
        _text(_object(item, "models manifest entry").get("model_id"), "model id"):
        _object(item, "models manifest entry")
        for item in _array(models.get("models"), "models manifest")
    }
    model_nodes = _array(identities.get("models"), "model identities")
    if len(model_nodes) != 2:
        raise EvidenceImportError("model identity count differs")
    candidate_identities: dict[str, _CandidateIdentity] = {}
    for node_value in model_nodes:
        node = _object(node_value, "model identity")
        _expect_keys(node, {"sha256", "value"}, "model identity")
        value = _object(node["value"], "model identity value")
        digest = _sha(node["sha256"], "model identity digest")
        if digest != _digest(value):
            raise EvidenceImportError("model identity digest disagrees with its value")
        candidate_id = _text(value.get("candidate_id"), "model candidate identity")
        if digest != _EXPECTED_MODEL_IDENTITY_SHA256.get(candidate_id):
            raise EvidenceImportError("model identity differs from exact worker evidence")
        implementation_name = _text(value.get("model_id"), "model identity model id")
        revision = _text(value.get("revision"), "model identity revision")
        if _SHA1.fullmatch(revision) is None:
            raise EvidenceImportError("model identity revision is mutable or malformed")
        spec_candidate = spec_candidates.get(candidate_id)
        manifest_candidate = manifest_candidates.get(implementation_name)
        if spec_candidate is None or manifest_candidate is None:
            raise EvidenceImportError("model identity is absent from manifests")
        _expect(value.get("model_id"), spec_candidate.get("model_id"), "model id")
        _expect(value.get("revision"), spec_candidate.get("revision"), "model revision")
        _expect(
            value.get("snapshot_path"),
            spec_candidate.get("snapshot_path"),
            "snapshot path",
        )
        _expect(
            manifest_candidate.get("resolved_revision_sha"),
            revision,
            "resolved model revision",
        )
        _expect(value.get("framework"), "transformers", "model framework")
        _expect(value.get("dtype"), "float16", "model dtype")
        candidate_identities[candidate_id] = _CandidateIdentity(
            candidate_id,
            implementation_name,
            revision,
            digest,
        )
    if set(candidate_identities) != set(_EXPECTED_CANDIDATES):
        raise EvidenceImportError("model identity candidates differ")
    return _IdentityEvidence(
        MappingProxyType(dict(sorted(candidate_identities.items()))),
        MappingProxyType(dict(workload)),
        _EXPECTED_IDENTITY_SHA256["policy"],
        _EXPECTED_IDENTITY_SHA256["resource"],
    )


def _normalize_exact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().split()).casefold()


def _validate_execution(results: Mapping[str, object]) -> list[object]:
    execution = _object(results.get("execution"), "execution")
    _expect_keys(
        execution,
        {
            "actual_sequence",
            "both_models_loaded_concurrently",
            "candidate_first_pair_counts",
            "candidate_loads",
            "mode",
            "no_retry_policy",
            "sampled_cache_classification",
            "tools_available_to_models",
            "warmups",
        },
        "execution",
    )
    _expect(execution["both_models_loaded_concurrently"], True, "model residency")
    _expect(
        execution["candidate_first_pair_counts"],
        {
            "qwen2.5-0.5b-instruct": 8,
            "qwen2.5-1.5b-instruct": 7,
        },
        "balanced candidate-first counts",
    )
    _expect(execution["mode"], "sequential_single_process_no_daemon", "execution mode")
    _expect(execution["no_retry_policy"], True, "no-retry policy")
    _expect(execution["sampled_cache_classification"], "WARM", "cache state")
    _expect(execution["tools_available_to_models"], False, "tool availability")
    loads = _array(execution["candidate_loads"], "candidate loads")
    warmups = _array(execution["warmups"], "warmups")
    if len(loads) != 2 or len(warmups) != 2:
        raise EvidenceImportError("candidate loads or warmups are incomplete")
    for value in loads:
        item = _object(value, "candidate load")
        _expect_keys(
            item,
            {"candidate_id", "error", "load_seconds", "status"},
            "candidate load",
        )
        _expect(item["status"], "PASS", "candidate load status")
        _expect(item["error"], None, "candidate load error")
        _number(item["load_seconds"], "candidate load seconds")
    for value in warmups:
        item = _object(value, "candidate warmup")
        _expect_keys(
            item,
            {
                "candidate_id",
                "completion_tokens",
                "error",
                "included_in_samples",
                "latency_seconds",
                "output_sha256",
                "status",
            },
            "candidate warmup",
        )
        _expect(item["status"], "PASS", "warmup status")
        _expect(item["error"], None, "warmup error")
        _expect(item["included_in_samples"], False, "warmup sample inclusion")
        _integer(item["completion_tokens"], "warmup completion tokens")
        _number(item["latency_seconds"], "warmup latency")
        _sha(item["output_sha256"], "warmup output digest")
    return _array(execution["actual_sequence"], "actual execution sequence")


def _validate_cells(
    results: Mapping[str, object],
    spec: Mapping[str, object],
    identities: _IdentityEvidence,
    actual_sequence: list[object],
) -> tuple[_Cell, ...]:
    raw_cells = _array(results.get("cells"), "result cells")
    if len(raw_cells) != 30:
        raise EvidenceImportError("result cell count is not exactly 30")
    tasks = {
        _text(_object(item, "task").get("task_id"), "task identity"):
        _object(item, "task")
        for item in _array(spec.get("tasks"), "tasks")
    }
    expected_coordinates = {
        EvaluationCellKey(candidate_id, task_id, repetition)
        for candidate_id in _EXPECTED_CANDIDATES
        for task_id in tasks
        for repetition in range(1, 4)
    }
    cells: list[_Cell] = []
    coordinates: set[EvaluationCellKey] = set()
    rendered_by_task: dict[str, str] = {}
    prompt_tokens_by_task: dict[str, int] = {}
    projected_sequence: list[dict[str, object]] = []
    for offset, raw_value in enumerate(raw_cells, start=1):
        raw = _object(raw_value, f"cell {offset}")
        _expect_keys(raw, _CELL_KEYS, f"cell {offset}")
        candidate_id = _text(raw["candidate_id"], "cell candidate")
        task_id = _text(raw["task_id"], "cell task")
        repetition = _integer(raw["repetition"], "cell repetition", minimum=1)
        key = EvaluationCellKey(candidate_id, task_id, repetition)
        if key in coordinates:
            raise EvidenceImportError("result contains a duplicate candidate/task/repetition")
        coordinates.add(key)
        if key not in expected_coordinates:
            raise EvidenceImportError("result contains an unknown evaluation coordinate")
        candidate = identities.candidates[candidate_id]
        task = tasks[task_id]
        _expect(raw["model_id"], candidate.implementation_name, "cell model id")
        _expect(raw["revision"], candidate.revision, "cell model revision")
        prompt = _text(raw["prompt"], "cell prompt")
        _expect(prompt, task.get("prompt"), "cell task prompt")
        _expect(
            raw["prompt_sha256"],
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "cell prompt digest",
        )
        rendered = _text(raw["rendered_prompt"], "rendered prompt")
        _expect(
            raw["rendered_prompt_sha256"],
            hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "rendered prompt digest",
        )
        prior_rendered = rendered_by_task.setdefault(task_id, rendered)
        _expect(rendered, prior_rendered, "paired rendered chat context")

        output = _text(raw["output"], "raw model output")
        output_sha256 = _sha(raw["output_sha256"], "raw model output digest")
        _expect(
            output_sha256,
            hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "raw output digest agreement",
        )

        semantic = _object(raw["semantic_validation"], "semantic validation")
        _expect_keys(semantic, {"evidence", "rule", "status"}, "semantic validation")
        semantic_evidence = _object(semantic["evidence"], "semantic evidence")
        _expect_keys(
            semantic_evidence,
            {"expected", "matched", "normalized_expected", "normalized_output"},
            "semantic evidence",
        )
        expected_answer = _text(task.get("expected_answer"), "expected answer")
        _expect(semantic["rule"], task.get("validation_rule"), "validation rule")
        _expect(semantic_evidence["expected"], expected_answer, "semantic expected answer")
        normalized_expected = _normalize_exact(expected_answer)
        normalized_output = _normalize_exact(output)
        _expect(
            semantic_evidence["normalized_expected"],
            normalized_expected,
            "normalized expected answer",
        )
        _expect(
            semantic_evidence["normalized_output"],
            normalized_output,
            "normalized model output",
        )
        matched = normalized_output == normalized_expected
        _expect(semantic_evidence["matched"], matched, "semantic matched flag")
        _expect(semantic["status"], "PASS" if matched else "FAIL", "semantic status")

        _expect(raw["cache_state"], "WARM", "cell cache state")
        _expect(raw["retry_count"], 0, "cell retry count")
        _expect(raw["tool_count"], 0, "cell tool count")
        _expect(raw["transport_success"], True, "cell transport outcome")
        _expect(raw["infrastructure_status"], "PASS", "cell infrastructure outcome")
        for name in (
            "cost",
            "infrastructure_error",
            "queue_seconds",
            "remote_resource_seconds",
            "timeout_seconds",
        ):
            _expect(raw[name], None, f"cell unknown {name}")

        sequence_index = _integer(raw["sequence_index"], "sequence index", minimum=1)
        pair_index = _integer(raw["pair_index"], "pair index", minimum=1)
        model_position = _integer(
            raw["model_position_in_pair"], "model position", minimum=1
        )
        _expect(sequence_index, offset, "contiguous actual sequence")
        _expect(pair_index, (offset + 1) // 2, "adjacent pair index")
        _expect(model_position, 1 if offset % 2 else 2, "model position in pair")

        prompt_tokens = _integer(raw["prompt_tokens"], "prompt tokens")
        prior_prompt_tokens = prompt_tokens_by_task.setdefault(task_id, prompt_tokens)
        _expect(prompt_tokens, prior_prompt_tokens, "paired prompt token conditions")
        completion_tokens = _integer(raw["completion_tokens"], "completion tokens")
        latency = _number(raw["model_latency_seconds"], "model latency")
        if latency <= 0.0:
            raise EvidenceImportError("model latency must be positive")
        throughput = _number(
            raw["completion_tokens_per_second"], "completion throughput"
        )
        _close(throughput, completion_tokens / latency, "completion throughput")
        peak_allocated = _integer(
            raw["peak_allocated_vram_bytes"], "peak allocated VRAM"
        )
        peak_reserved = _integer(
            raw["peak_reserved_vram_bytes"], "peak reserved VRAM"
        )
        if peak_allocated > peak_reserved:
            raise EvidenceImportError("allocated VRAM exceeds reserved VRAM")
        cells.append(
            _Cell(
                key,
                candidate.implementation_name,
                candidate.revision,
                sequence_index,
                pair_index,
                model_position,
                "WARM",
                0,
                output,
                output_sha256,
                prompt_tokens,
                completion_tokens,
                latency,
                throughput,
                peak_allocated,
                peak_reserved,
                matched,
            )
        )
        projected_sequence.append(
            {
                "candidate_id": candidate_id,
                "model_position_in_pair": model_position,
                "pair_index": pair_index,
                "repetition": repetition,
                "sequence_index": sequence_index,
                "task_id": task_id,
            }
        )
    if coordinates != expected_coordinates:
        raise EvidenceImportError("result has missing or extra evaluation coordinates")
    _expect(projected_sequence, actual_sequence, "recorded actual sequence")
    _expect(
        identities.workload.get("actual_sequence"),
        projected_sequence,
        "workload seeded actual sequence",
    )
    for pair_offset in range(0, len(cells), 2):
        left, right = cells[pair_offset : pair_offset + 2]
        if (
            left.key.task_id != right.key.task_id
            or left.key.repetition != right.key.repetition
            or left.key.candidate_id == right.key.candidate_id
        ):
            raise EvidenceImportError("candidate cells are not exact adjacent pairs")
    return tuple(cells)


def _validate_summary_scalar(value: object, expected: float, label: str) -> float:
    observed = _number(value, label)
    _close(observed, expected, label)
    return observed


def _validate_summaries(
    results: Mapping[str, object],
    cells: tuple[_Cell, ...],
    identities: _IdentityEvidence,
) -> tuple[CandidateEvidenceSummary, ...]:
    root = _object(results.get("descriptive_summaries"), "descriptive summaries")
    if set(root) != set(_EXPECTED_CANDIDATES):
        raise EvidenceImportError("descriptive summary candidates differ")
    summaries: list[CandidateEvidenceSummary] = []
    for candidate_id in _EXPECTED_CANDIDATES:
        candidate_cells = tuple(
            item for item in cells if item.key.candidate_id == candidate_id
        )
        if len(candidate_cells) != 15:
            raise EvidenceImportError("candidate summary does not have 15 raw cells")
        summary = _object(root[candidate_id], "candidate summary")
        _expect_keys(
            summary,
            {
                "completion_tokens_per_second",
                "completion_tokens_total",
                "infrastructure_fail_or_timeout",
                "infrastructure_pass",
                "maximum_peak_allocated_vram_bytes",
                "maximum_peak_reserved_vram_bytes",
                "model_latency_seconds",
                "prompt_tokens_total",
                "sample_cells",
                "semantic_fail",
                "semantic_pass",
                "semantic_pass_rate",
            },
            "candidate summary",
        )
        latencies = [item.latency_seconds for item in candidate_cells]
        throughputs = [
            item.completion_tokens_per_second for item in candidate_cells
        ]
        semantic_pass = sum(item.semantic_pass for item in candidate_cells)
        latency_summary = _object(
            summary["model_latency_seconds"], "latency summary"
        )
        throughput_summary = _object(
            summary["completion_tokens_per_second"], "throughput summary"
        )
        _expect_keys(
            latency_summary,
            {"maximum", "mean", "median", "minimum"},
            "latency summary",
        )
        _expect_keys(throughput_summary, {"mean", "median"}, "throughput summary")
        latency_mean = _validate_summary_scalar(
            latency_summary["mean"], fmean(latencies), "latency mean"
        )
        latency_median = _validate_summary_scalar(
            latency_summary["median"], median(latencies), "latency median"
        )
        latency_minimum = _validate_summary_scalar(
            latency_summary["minimum"], min(latencies), "latency minimum"
        )
        latency_maximum = _validate_summary_scalar(
            latency_summary["maximum"], max(latencies), "latency maximum"
        )
        throughput_mean = _validate_summary_scalar(
            throughput_summary["mean"], fmean(throughputs), "throughput mean"
        )
        throughput_median = _validate_summary_scalar(
            throughput_summary["median"],
            median(throughputs),
            "throughput median",
        )
        expected_integers = {
            "completion_tokens_total": sum(
                item.completion_tokens for item in candidate_cells
            ),
            "infrastructure_fail_or_timeout": 0,
            "infrastructure_pass": 15,
            "maximum_peak_allocated_vram_bytes": max(
                item.peak_allocated_vram_bytes for item in candidate_cells
            ),
            "maximum_peak_reserved_vram_bytes": max(
                item.peak_reserved_vram_bytes for item in candidate_cells
            ),
            "prompt_tokens_total": sum(item.prompt_tokens for item in candidate_cells),
            "sample_cells": 15,
            "semantic_fail": 15 - semantic_pass,
            "semantic_pass": semantic_pass,
        }
        for name, expected in expected_integers.items():
            _expect(summary[name], expected, f"summary {name}")
        semantic_rate = _validate_summary_scalar(
            summary["semantic_pass_rate"],
            semantic_pass / 15,
            "semantic pass rate",
        )
        identity = identities.candidates[candidate_id]
        summaries.append(
            CandidateEvidenceSummary(
                candidate_id,
                identity.implementation_name,
                identity.revision,
                15,
                semantic_pass,
                15 - semantic_pass,
                semantic_rate,
                15,
                0,
                latency_mean,
                latency_median,
                latency_minimum,
                latency_maximum,
                throughput_mean,
                throughput_median,
                expected_integers["prompt_tokens_total"],
                expected_integers["completion_tokens_total"],
                expected_integers["maximum_peak_allocated_vram_bytes"],
                expected_integers["maximum_peak_reserved_vram_bytes"],
            )
        )
    return tuple(summaries)


def _validate_paired_outcomes(
    results: Mapping[str, object],
    cells: tuple[_Cell, ...],
) -> tuple[int, int, int]:
    raw_pairs = _array(results.get("paired_raw_outcomes"), "paired raw outcomes")
    if len(raw_pairs) != 15:
        raise EvidenceImportError("paired outcome count is not exactly 15")
    by_key = {item.key: item for item in cells}
    observed_coordinates: set[tuple[str, int]] = set()
    wins = losses = ties = 0
    for raw_pair in raw_pairs:
        pair = _object(raw_pair, "paired raw outcome")
        _expect_keys(pair, {"outcomes", "repetition", "task_id"}, "paired raw outcome")
        task_id = _text(pair["task_id"], "paired task")
        repetition = _integer(pair["repetition"], "paired repetition", minimum=1)
        coordinate = (task_id, repetition)
        if coordinate in observed_coordinates:
            raise EvidenceImportError("paired raw outcome is duplicated")
        observed_coordinates.add(coordinate)
        outcomes = _object(pair["outcomes"], "paired outcomes")
        if set(outcomes) != set(_EXPECTED_CANDIDATES):
            raise EvidenceImportError("paired candidate outcomes differ")
        semantic: dict[str, bool] = {}
        for candidate_id in _EXPECTED_CANDIDATES:
            cell = by_key[EvaluationCellKey(candidate_id, task_id, repetition)]
            expected = {
                "completion_tokens_per_second": cell.completion_tokens_per_second,
                "infrastructure_status": "PASS",
                "model_latency_seconds": cell.latency_seconds,
                "semantic_validation": "PASS" if cell.semantic_pass else "FAIL",
                "sequence_index": cell.sequence_index,
            }
            _expect(outcomes[candidate_id], expected, "paired raw cell outcome")
            semantic[candidate_id] = cell.semantic_pass
        left = semantic[_EXPECTED_CANDIDATES[0]]
        right = semantic[_EXPECTED_CANDIDATES[1]]
        if left and not right:
            wins += 1
        elif right and not left:
            losses += 1
        else:
            ties += 1
    expected_coordinates = {
        (item.key.task_id, item.key.repetition) for item in cells
    }
    if observed_coordinates != expected_coordinates:
        raise EvidenceImportError("paired outcomes are missing coordinates")
    return wins, losses, ties


def _validate_results_envelope(
    results: dict[str, object],
    raw_results: bytes,
    spec: Mapping[str, object],
) -> tuple[str, ...]:
    _expect_keys(results, _RESULTS_KEYS, "controlled suite results")
    _expect(results["schema_version"], 1, "results schema")
    _expect(results["suite_id"], _EXPECTED_SUITE_ID, "results suite")
    _expect(
        results["primary_variable"],
        "MODEL_IMPLEMENTATION",
        "results primary variable",
    )
    _timestamp(results["run_started_at"], "run_started_at")
    _timestamp(results["run_finished_at"], "run_finished_at")
    _number(results["run_wall_seconds"], "run wall seconds")

    interpretation = _object(
        results["interpretation_constraints"], "interpretation constraints"
    )
    _expect(
        interpretation,
        {
            "descriptive_only": True,
            "significance_test_performed": False,
            "universal_winner_claimed": False,
        },
        "interpretation constraints",
    )
    confounders = tuple(
        _text(item, "reported confounder")
        for item in _array(results["known_confounders"], "known confounders")
    )
    _expect(confounders, _EXPECTED_REPORTED_CONFOUNDERS, "known confounders")

    structural = _object(results["structural_validation"], "structural validation")
    _expect_keys(
        structural,
        {
            "checks",
            "duplicate_coordinates",
            "expected_cell_count",
            "extra_coordinates",
            "maximum_results_bytes",
            "missing_coordinates",
            "observed_cell_count",
            "results_bytes",
            "status",
        },
        "structural validation",
    )
    checks = _object(structural["checks"], "structural checks")
    expected_check_names = {
        "actual_sequence_matches_cells",
        "candidate_first_order_is_balanced",
        "cell_count_exact",
        "no_duplicate_coordinates",
        "no_extra_coordinates",
        "no_missing_coordinates",
        "results_size_bounded",
        "retry_count_is_zero",
        "sampled_cache_is_warm",
        "sequence_is_exact_and_contiguous",
        "spec_is_canonical_json",
        "tool_count_is_zero",
        "unknown_fields_are_json_null",
    }
    _expect_keys(checks, expected_check_names, "structural checks")
    if not all(
        _boolean(checks[name], f"structural check {name}") for name in checks
    ):
        raise EvidenceImportError("worker structural validation did not pass")
    _expect(structural["status"], "PASS", "structural status")
    _expect(structural["expected_cell_count"], 30, "expected cell count")
    _expect(structural["observed_cell_count"], 30, "observed cell count")
    _expect(structural["duplicate_coordinates"], [], "duplicate coordinates")
    _expect(structural["missing_coordinates"], [], "missing coordinates")
    _expect(structural["extra_coordinates"], [], "extra coordinates")
    maximum_results = _integer(
        _object(spec["output_policy"], "output policy")["maximum_results_bytes"],
        "maximum result bytes",
    )
    _expect(structural["maximum_results_bytes"], maximum_results, "result byte bound")
    _expect(structural["results_bytes"], len(raw_results), "exact result byte count")
    if len(raw_results) > maximum_results:
        raise EvidenceImportError("controlled results exceed their declared bound")
    return confounders


def _build_suite(
    project_ref: ProjectRef,
    spec: Mapping[str, object],
    identities: _IdentityEvidence,
) -> tuple[ModelEvaluationSuite, Mapping[str, EvaluationTask]]:
    capability = CapabilityRef("model.infer", "1.0.0")
    workload_content = ContentRef.from_bytes(
        _canonical_bytes(dict(identities.workload)),
        media_type="application/json",
    )
    profile = WorkloadProfile(
        project_ref,
        "p4-01-l40s-workload",
        1,
        workload_content,
        {
            "pairing": "task_id,repetition",
            "primary_variable": "MODEL_IMPLEMENTATION",
            "suite": _EXPECTED_SUITE_ID,
        },
    )
    task_items: list[EvaluationTask] = []
    task_by_id: dict[str, EvaluationTask] = {}
    for task_value in _array(spec.get("tasks"), "tasks"):
        raw = _object(task_value, "task")
        task_id = _text(raw["task_id"], "task identity")
        task = EvaluationTask(
            project_ref,
            task_id,
            1,
            ContentRef.from_bytes(
                _canonical_bytes(raw),
                media_type="application/json",
            ),
            capability,
            f"template://external-worker/{task_id}/tokenizer-chat-template",
            "text-reasoning",
            "exact-answer",
        )
        task_items.append(task)
        task_by_id[task_id] = task
    taskset_value = {"tasks": spec["tasks"], "validation": spec["validation"]}
    task_set = EvaluationTaskSet(
        project_ref,
        "p4-01-controlled-tasks",
        1,
        ContentRef.from_bytes(
            _canonical_bytes(taskset_value),
            media_type="application/json",
        ),
        tuple(task_items),
        f"selection-policy://external-worker/{_EXPECTED_IDENTITY_SHA256['taskset']}",
    )
    candidates = tuple(
        ModelCandidate(
            project_ref,
            identity.candidate_id,
            (
                "model-deployment://external-worker/"
                f"{identity.implementation_name}/{identity.revision}"
            ),
            identity.identity_sha256,
            "adapter://external-worker/tokenizer-chat-template",
            (
                "runtime://external-worker/transformers-4.53.2/"
                f"float16/{identity.revision}"
            ),
            f"sha1.{identity.revision}",
            False,
            capability,
        )
        for identity in identities.candidates.values()
    )
    policy = identities.policy_sha256
    resource = identities.resource_sha256
    try:
        suite = ModelEvaluationSuite(
            project_ref,
            _EXPECTED_SUITE_ID,
            1,
            capability,
            profile,
            task_set,
            EvidenceClass.QUASI_CONTROLLED,
            {
                "MODEL_IMPLEMENTATION": "varied",
                "cache_state": "WARM",
                "context_policy_sha256": policy,
                "generation_policy_sha256": policy,
                "resource_identity_sha256": resource,
                "runtime_policy_sha256": policy,
                "tool_count": "0",
                "validation_policy_sha256": _EXPECTED_IDENTITY_SHA256["taskset"],
                "workload_sha256": _EXPECTED_IDENTITY_SHA256["workload"],
            },
            _IMPORT_CONFOUNDERS,
            candidates,
            f"execution-policy://external-worker/{_EXPECTED_IDENTITY_SHA256['workload']}",
            f"tool-policy://external-worker/{policy}/none",
            f"context-policy://external-worker/{policy}",
            f"validation-policy://external-worker/{_EXPECTED_IDENTITY_SHA256['taskset']}",
            f"resource-policy://external-worker/{resource}",
            f"generation-policy://external-worker/{policy}",
            f"order-policy://external-worker/{_EXPECTED_IDENTITY_SHA256['workload']}",
            f"cache-policy://external-worker/{policy}/warm",
            3,
            None,
        )
    except EvaluationContractError as exc:
        raise EvidenceImportError("reference suite identity binding is invalid") from exc
    return suite, MappingProxyType(dict(task_by_id))


def _binding_map(
    project_ref: ProjectRef,
    bindings: tuple[EvaluationCellBinding, ...],
    cells: tuple[_Cell, ...],
) -> Mapping[EvaluationCellKey, EvaluationCellBinding]:
    if not isinstance(bindings, tuple) or not all(
        isinstance(item, EvaluationCellBinding) for item in bindings
    ):
        raise EvidenceImportError("cell bindings must be an immutable exact tuple")
    result: dict[EvaluationCellKey, EvaluationCellBinding] = {}
    for binding in bindings:
        if binding.coordinate in result:
            raise EvidenceImportError("cell identity binding is duplicated")
        if binding.run_ref.project_ref != project_ref:
            raise EvidenceImportError("cell identity binding crossed Project scope")
        if binding.tool_calls:
            raise EvidenceImportError("zero-tool worker evidence cannot bind ToolCalls")
        for call in binding.model_calls:
            if call.cost is not None:
                raise EvidenceImportError("unknown worker cost cannot bind a known call cost")
        result[binding.coordinate] = binding
    expected = {item.key for item in cells}
    if set(result) != expected:
        raise EvidenceImportError("cell identity bindings are missing or extra")
    return MappingProxyType(result)


def _statistics_for_cells(
    cells: tuple[_Cell, ...],
) -> tuple[DescriptiveStatistics, ...]:
    statistics: list[DescriptiveStatistics] = []
    for candidate_id in _EXPECTED_CANDIDATES:
        selected = tuple(
            item for item in cells if item.key.candidate_id == candidate_id
        )
        measured: tuple[tuple[str, list[float], str], ...] = (
            ("latency.seconds", [item.latency_seconds for item in selected], "seconds"),
            (
                "throughput.completion_tokens_per_second",
                [item.completion_tokens_per_second for item in selected],
                "tokens_per_second",
            ),
            (
                "tokens.prompt",
                [float(item.prompt_tokens) for item in selected],
                "tokens",
            ),
            (
                "tokens.completion",
                [float(item.completion_tokens) for item in selected],
                "tokens",
            ),
            (
                "vram.peak_allocated_bytes",
                [float(item.peak_allocated_vram_bytes) for item in selected],
                "bytes",
            ),
            (
                "vram.peak_reserved_bytes",
                [float(item.peak_reserved_vram_bytes) for item in selected],
                "bytes",
            ),
            (
                "reliability.semantic",
                [1.0 if item.semantic_pass else 0.0 for item in selected],
                "ratio",
            ),
            ("reliability.infrastructure", [1.0 for _ in selected], "ratio"),
        )
        for suffix, values, unit in measured:
            statistics.append(
                DescriptiveStatistics(
                    f"{candidate_id}.{suffix}",
                    len(values),
                    fmean(values),
                    pstdev(values),
                    min(values),
                    max(values),
                    unit,
                )
            )
        for suffix in (
            "cost.amount",
            "provider.queue_seconds",
            "resource.remote.seconds",
        ):
            statistics.append(
                DescriptiveStatistics(
                    f"{candidate_id}.{suffix}",
                    len(selected),
                    None,
                    None,
                    None,
                    None,
                    "unknown",
                )
            )
    return tuple(statistics)


def _build_runs(
    suite: ModelEvaluationSuite,
    task_by_id: Mapping[str, EvaluationTask],
    cells: tuple[_Cell, ...],
    bindings: Mapping[EvaluationCellKey, EvaluationCellBinding],
) -> tuple[tuple[ModelEvaluationRun, ...], tuple[ImportedEvaluationCell, ...]]:
    runs: list[ModelEvaluationRun] = []
    imported_cells: list[ImportedEvaluationCell] = []
    for cell in cells:
        binding = bindings[cell.key]
        try:
            run = ModelEvaluationRun(
                suite,
                cell.key.candidate_id,
                task_by_id[cell.key.task_id],
                cell.key.repetition,
                binding.run_ref,
                binding.model_calls,
                binding.tool_calls,
                binding.validation_results,
                binding.evaluation_results,
                binding.context_receipt,
                binding.resource_snapshots,
                "success",
                "pass" if cell.semantic_pass else "fail",
                "pass",
                "completed",
                binding.started_at,
                binding.completed_at,
                {
                    "completion_tokens": float(cell.completion_tokens),
                    "latency.seconds": cell.latency_seconds,
                    "peak_allocated_vram_bytes": float(
                        cell.peak_allocated_vram_bytes
                    ),
                    "peak_reserved_vram_bytes": float(
                        cell.peak_reserved_vram_bytes
                    ),
                    "prompt_tokens": float(cell.prompt_tokens),
                    "provider.queue_seconds": None,
                    "resource.remote_seconds": None,
                    "throughput.completion_tokens_per_second": (
                        cell.completion_tokens_per_second
                    ),
                },
                cell.prompt_tokens + cell.completion_tokens,
                None,
            )
        except (EvaluationContractError, AttributeError) as exc:
            raise EvidenceImportError(
                f"cell {cell.key} cannot bind exact Engine evidence"
            ) from exc
        runs.append(run)
        imported_cells.append(
            ImportedEvaluationCell(
                cell.key,
                run,
                cell.implementation_name,
                cell.revision,
                cell.sequence_index,
                cell.pair_index,
                cell.model_position_in_pair,
                cell.cache_state,
                cell.retry_count,
                cell.output,
                cell.output_sha256,
                cell.prompt_tokens,
                cell.completion_tokens,
                cell.latency_seconds,
                cell.completion_tokens_per_second,
                cell.peak_allocated_vram_bytes,
                cell.peak_reserved_vram_bytes,
                cell.semantic_pass,
            )
        )
    return tuple(runs), tuple(imported_cells)


def import_p4_01_l40s_evidence(
    project_ref: ProjectRef,
    artifacts: ExternalEvaluationArtifacts,
    bindings: tuple[EvaluationCellBinding, ...],
    *,
    require_real: bool = True,
) -> ImportedModelEvaluationEvidence:
    """Import exact worker evidence without upgrading historical authority."""

    if not isinstance(project_ref, ProjectRef):
        raise EvidenceImportError("import requires an exact ProjectRef")
    if not isinstance(artifacts, ExternalEvaluationArtifacts):
        raise EvidenceImportError("import requires exact external artifact bytes")
    hashes = artifacts.sha256()
    reality = (
        EvidenceReality.REAL
        if dict(hashes) == dict(P4_01_L40S_FIXTURE_SHA256)
        else EvidenceReality.REFERENCE
    )
    if require_real and reality is not EvidenceReality.REAL:
        raise EvidenceImportError("artifact bytes do not match the exact REAL worker fixture")

    environment = _load_document(
        artifacts.environment_manifest,
        "environment manifest",
        canonical_required=False,
        maximum_bytes=100_000,
    )
    models = _load_document(
        artifacts.models_manifest,
        "models manifest",
        canonical_required=False,
        maximum_bytes=100_000,
    )
    spec = _load_document(
        artifacts.controlled_suite_spec,
        "controlled suite specification",
        canonical_required=True,
        maximum_bytes=100_000,
    )
    results = _load_document(
        artifacts.controlled_suite_results,
        "controlled suite results",
        canonical_required=True,
        maximum_bytes=1_500_000,
    )
    _validate_static_documents(environment, models, spec)
    reported_confounders = _validate_results_envelope(
        results,
        artifacts.controlled_suite_results,
        spec,
    )
    identities = _validate_identities(results, environment, models, spec)
    actual_sequence = _validate_execution(results)
    cells = _validate_cells(results, spec, identities, actual_sequence)
    summaries = _validate_summaries(results, cells, identities)
    paired_wins, paired_losses, paired_ties = _validate_paired_outcomes(
        results, cells
    )
    if (paired_wins, paired_losses, paired_ties) != (0, 9, 6):
        raise EvidenceImportError("paired descriptive outcome differs from raw cells")

    suite, task_by_id = _build_suite(project_ref, spec, identities)
    binding_by_key = _binding_map(project_ref, bindings, cells)
    runs, imported_cells = _build_runs(suite, task_by_id, cells, binding_by_key)
    comparison = PairwiseComparison(
        suite,
        _EXPECTED_CANDIDATES[0],
        _EXPECTED_CANDIDATES[1],
        paired_wins,
        paired_losses,
        paired_ties,
        "DESCRIPTIVE",
        suite.resource_policy_ref,
    )
    try:
        result = ModelEvaluationResult(
            suite,
            runs,
            _statistics_for_cells(cells),
            (comparison,),
        )
        knowledge_candidate = ModelEvaluationKnowledgeCandidate(
            project_ref,
            suite.canonical_digest,
            ContentRef.from_bytes(
                artifacts.controlled_suite_results,
                media_type="application/json",
            ),
            tuple(
                f"evidence://p4-01-l40s/{name}/sha256/{digest}"
                for name, digest in sorted(hashes.items())
            ),
        )
    except EvaluationContractError as exc:
        raise EvidenceImportError("imported result contract is inconsistent") from exc
    return ImportedModelEvaluationEvidence(
        reality,
        EvidenceReality.REFERENCE,
        MappingProxyType(dict(hashes)),
        suite,
        imported_cells,
        summaries,
        result,
        knowledge_candidate,
        reported_confounders,
    )
