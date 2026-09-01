"""Fail-closed import of the REAL P4-02 NVIDIA L40S strategy matrix."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import NoReturn, cast
import unicodedata

from .artifact import ContentRef
from .capability import CapabilityRef
from .model_evaluation import (
    EvidenceClass,
    EvaluationTask,
    EvaluationTaskSet,
    ModelCandidate,
    WorkloadProfile,
)
from .model_evaluation_evidence import EvidenceReality
from .project import ProjectRef
from .run import RunRef
from .strategy_evaluation import (
    ExecutionStrategy,
    MatrixKind,
    PromptArtifact,
    SkillArtifact,
    StrategyDimension,
    StrategyEvaluationExperiment,
    StrategyEvaluationKnowledgeCandidate,
    StrategyEvaluationResult,
    StrategyEvaluationRun,
    StrategyMetricSet,
    StrategyPattern,
    build_strategy_evaluation_result,
)


P4_02_L40S_FIXTURE_SHA256: Mapping[str, str] = MappingProxyType(
    {
        "post_run_resource.json": "9669aa3ac8925afc0c17eeb30fd957dc9f62a1425111b542a83b71399ac7c33c",
        "strategy_evaluation_manifest.json": "4c68e6a753262492e9414504d0f4886b608faf5879fbc0c41464a1032e2551ad",
        "strategy_evaluation_results.json": "c231296e8b413726ccd8d65c53fb7d5db0d68be8f48599abdfbb578af4db06f5",
        "strategy_evaluation_spec.json": "5e06acd465fa846efc42c7c5c235667bfc70e099b0f501100d01a7f20d5515ba",
    }
)


class EvidenceImportError(ValueError):
    """External strategy evidence failed identity, integrity, or scope checks."""


@dataclass(frozen=True)
class ExternalStrategyEvaluationArtifacts:
    spec: bytes
    results: bytes
    manifest: bytes
    post_run_resource: bytes

    def __post_init__(self) -> None:
        if any(not isinstance(value, bytes) or not value for value in self.named_bytes().values()):
            raise EvidenceImportError("strategy evidence artifacts must contain bytes")

    @classmethod
    def from_directory(cls, directory: Path) -> ExternalStrategyEvaluationArtifacts:
        return cls(
            (directory / "strategy_evaluation_spec.json").read_bytes(),
            (directory / "strategy_evaluation_results.json").read_bytes(),
            (directory / "strategy_evaluation_manifest.json").read_bytes(),
            (directory / "post_run_resource.json").read_bytes(),
        )

    def named_bytes(self) -> Mapping[str, bytes]:
        return MappingProxyType(
            {
                "post_run_resource.json": self.post_run_resource,
                "strategy_evaluation_manifest.json": self.manifest,
                "strategy_evaluation_results.json": self.results,
                "strategy_evaluation_spec.json": self.spec,
            }
        )

    def sha256(self) -> Mapping[str, str]:
        return MappingProxyType(
            {name: hashlib.sha256(payload).hexdigest() for name, payload in self.named_bytes().items()}
        )


@dataclass(frozen=True)
class StrategyEvidenceBinding:
    run_ref: RunRef
    source_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_ref, RunRef):
            raise EvidenceImportError("strategy evidence RunRef is required")
        if not isinstance(self.source_ref, str) or not self.source_ref.startswith("artifact://"):
            raise EvidenceImportError("strategy evidence source must be an exact Artifact ref")


@dataclass(frozen=True)
class ImportedRawStrategyCell:
    cell_id: str
    variant_id: str
    model_id: str
    strategy_id: str
    task_id: str
    repetition: int
    final_output: str
    final_output_sha256: str
    semantic_pass: bool
    infrastructure_pass: bool
    model_calls: int
    tool_calls: int
    model_latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    graph_depth: int
    graph_width: int
    graph_revisions: int
    graph_repairs: int
    peak_allocated_vram_bytes: int
    peak_reserved_vram_bytes: int
    invocation_refs: tuple[str, ...]
    tool_call_refs: tuple[str, ...]
    identity_sha256: Mapping[str, str]


@dataclass(frozen=True)
class VariantEvidenceSummary:
    variant_id: str
    cells: int
    semantic_pass: int
    semantic_fail: int
    infrastructure_pass: int
    logical_model_calls: int
    physical_model_invocations: int
    tool_calls: int
    prompt_tokens: int
    completion_tokens: int
    unique_invocation_latency_seconds: float
    maximum_peak_allocated_vram_bytes: int
    maximum_peak_reserved_vram_bytes: int
    graph_maximum_depth: int
    graph_maximum_width: int
    graph_revisions: int
    graph_repairs: int


@dataclass(frozen=True)
class ImportedStrategyMatrixEvidence:
    matrix_id: str
    source_variants: tuple[str, ...]
    experiment: StrategyEvaluationExperiment
    result: StrategyEvaluationResult
    raw_cell_ids: tuple[str, ...]


@dataclass(frozen=True)
class ImportedStrategyEvaluationEvidence:
    artifacts: ExternalStrategyEvaluationArtifacts
    binding: StrategyEvidenceBinding
    evidence_reality: EvidenceReality
    identity_binding_reality: EvidenceReality
    raw_cells: tuple[ImportedRawStrategyCell, ...]
    matrices: tuple[ImportedStrategyMatrixEvidence, ...]
    variant_summaries: Mapping[str, VariantEvidenceSummary]
    knowledge_candidates: tuple[StrategyEvaluationKnowledgeCandidate, ...]
    known_confounders: tuple[str, ...]
    infrastructure_pass: int
    semantic_pass: int
    semantic_fail: int
    model_invocations: int
    tool_calls: int
    post_run_gpu_memory_mib: int
    post_run_model_processes: int
    post_run_persistent_residency: bool
    significance_test_performed: bool
    universal_winner_claimed: bool


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
        raise EvidenceImportError("strategy evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _reject_duplicate(value: str) -> NoReturn:
    raise EvidenceImportError(f"duplicate JSON key: {value}")


def _load_document(payload: bytes, label: str) -> dict[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                _reject_duplicate(key)
            result[key] = value
        return result

    try:
        decoded = payload.decode("utf-8")
        value = json.loads(decoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceImportError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceImportError(f"{label} root must be an object")
    result = cast(dict[str, object], value)
    if _canonical_bytes(result) != payload:
        raise EvidenceImportError(f"{label} is not canonical JSON")
    return result


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise EvidenceImportError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise EvidenceImportError(f"{label} must be an array")
    return cast(list[object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise EvidenceImportError(f"{label} must be non-empty text")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise EvidenceImportError(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise EvidenceImportError(f"{label} must be finite")
    result = float(value)
    if result < minimum:
        raise EvidenceImportError(f"{label} is below its minimum")
    return result


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceImportError(f"{label} must be boolean")
    return value


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise EvidenceImportError(f"{label} must be SHA-256")
    return text


def _timestamp(value: object, label: str) -> str:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceImportError(f"{label} is not a timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceImportError(f"{label} must be timezone-aware")
    return text.replace("Z", "+00:00")


def _expect(value: object, expected: object, label: str) -> None:
    if value != expected:
        raise EvidenceImportError(f"{label} differs from the exact evidence contract")


def _close(value: float, expected: float, label: str) -> None:
    if not math.isclose(value, expected, rel_tol=1e-10, abs_tol=1e-12):
        raise EvidenceImportError(f"{label} is inconsistent")


def _normalize_exact(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def _validate_identity_tree(value: object, label: str) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_identity_tree(item, f"{label}[{index}]")
        return
    if not isinstance(value, dict):
        return
    item = cast(dict[str, object], value)
    if "value" in item or "sha256" in item:
        if set(item) != {"sha256", "value"}:
            raise EvidenceImportError(f"{label} identity envelope is malformed")
        observed = _sha(item["sha256"], f"{label}.sha256")
        if observed != _digest(item["value"]):
            raise EvidenceImportError(f"{label} identity digest differs")
        _validate_identity_tree(item["value"], f"{label}.value")
        return
    for key, child in item.items():
        _validate_identity_tree(child, f"{label}.{key}")


def _identity_record(value: object, label: str) -> tuple[dict[str, object], str]:
    envelope = _object(value, label)
    if set(envelope) != {"sha256", "value"}:
        raise EvidenceImportError(f"{label} identity envelope is malformed")
    payload = _object(envelope["value"], f"{label}.value")
    digest = _sha(envelope["sha256"], f"{label}.sha256")
    if digest != _digest(payload):
        raise EvidenceImportError(f"{label} identity digest differs")
    return payload, digest


def _validate_static(
    spec: Mapping[str, object],
    results: Mapping[str, object],
    manifest: Mapping[str, object],
    post: Mapping[str, object],
    artifacts: ExternalStrategyEvaluationArtifacts,
) -> None:
    for value, label in ((spec, "spec"), (results, "results"), (manifest, "manifest"), (post, "post-run resource")):
        _expect(value.get("schema_version"), 1, f"{label} schema")
    suite = "p4-02-controlled-strategy-evaluation-v1"
    _expect(spec.get("suite_id"), suite, "spec suite")
    _expect(results.get("suite_id"), suite, "results suite")
    _expect(manifest.get("suite_id"), suite, "manifest suite")
    _expect(spec.get("classification"), "CONTROLLED", "spec classification")
    _expect(results.get("classification"), "CONTROLLED", "results classification")
    _expect(results.get("spec_canonical_sha256"), hashlib.sha256(artifacts.spec).hexdigest(), "spec binding")
    output = _object(spec.get("output_policy"), "output policy")
    for key in (
        "canonical_json",
        "descriptive_only",
        "forbid_significance_claims",
        "forbid_universal_winner",
        "preserve_failed_and_worse_outcomes",
        "preserve_raw_outputs",
    ):
        _expect(output.get(key), True, f"output policy {key}")
    _expect(output.get("retry_count"), 0, "retry count")
    interpretation = _object(results.get("interpretation_constraints"), "interpretation constraints")
    _expect(interpretation.get("descriptive_only"), True, "descriptive-only constraint")
    _expect(interpretation.get("failed_and_worse_outcomes_preserved"), True, "failure preservation")
    _expect(interpretation.get("significance_test_performed"), False, "significance constraint")
    _expect(interpretation.get("universal_winner_claimed"), False, "winner constraint")
    structural = _object(results.get("structural_validation"), "structural validation")
    _expect(structural.get("status"), "PASS", "structural status")
    _expect(structural.get("expected_cells"), 120, "expected cell count")
    _expect(structural.get("observed_cells"), 120, "observed cell count")
    checks = _object(structural.get("checks"), "structural checks")
    if not checks or any(value is not True for value in checks.values()):
        raise EvidenceImportError("not every structural check passed")
    _expect(manifest.get("run_exit_code"), 0, "worker exit code")
    validation = _object(manifest.get("validation"), "manifest validation")
    expected_validation = {
        "expected_cells": 120,
        "observed_cells": 120,
        "infrastructure_pass": 120,
        "semantic_pass": 69,
        "semantic_fail": 51,
        "model_invocations": 138,
        "tool_calls": 15,
        "structural": "PASS",
    }
    for key, expected in expected_validation.items():
        _expect(validation.get(key), expected, f"manifest validation {key}")
    required = set(_array(validation.get("required_matrices"), "required matrices"))
    _expect(
        required,
        {
            "same_model_s1_s2",
            "tool_policy",
            "context_policy",
            "parallel_vs_serial",
            "specialist_vs_generalist",
            "model_strategy_factorial",
        },
        "required matrix set",
    )
    artifact_rows = _array(manifest.get("artifacts"), "manifest artifacts")
    by_name: dict[str, dict[str, object]] = {}
    for row_value in artifact_rows:
        row = _object(row_value, "manifest artifact")
        name = Path(_text(row.get("path"), "manifest artifact path")).name
        by_name[name] = row
    for name, payload in artifacts.named_bytes().items():
        if name == "strategy_evaluation_manifest.json":
            continue
        matched_row = by_name.get(name)
        if matched_row is None:
            raise EvidenceImportError(f"manifest omitted {name}")
        _expect(matched_row.get("bytes"), len(payload), f"{name} size")
        _expect(matched_row.get("sha256"), hashlib.sha256(payload).hexdigest(), f"{name} digest")
    post_binding = _object(manifest.get("post_run_resource"), "manifest post-run resource")
    _expect(post_binding.get("artifact_sha256"), hashlib.sha256(artifacts.post_run_resource).hexdigest(), "post-run digest")
    _expect(post_binding.get("gpu_memory_used_mib"), 0, "post-run GPU memory")
    _expect(post_binding.get("compute_process_count"), 0, "post-run compute processes")
    _expect(post_binding.get("model_runtime_process_count"), 0, "post-run model processes")
    _expect(post_binding.get("persistent_model_or_agent_residency"), False, "post-run residency")
    gpu = _object(post.get("gpu"), "post-run GPU")
    _expect(gpu.get("name"), "NVIDIA L40S", "post-run GPU name")
    _expect(gpu.get("memory_total_mib"), 46068, "post-run GPU memory total")
    _expect(gpu.get("memory_used_mib"), 0, "post-run GPU memory used")
    _expect(gpu.get("utilization_gpu_percent"), 0, "post-run GPU utilization")
    _expect(post.get("compute_process_count"), 0, "post-run compute process count")
    _expect(post.get("model_runtime_process_count"), 0, "post-run model process count")
    _expect(post.get("persistent_model_or_agent_residency"), False, "post-run residency flag")


def _validate_invocations(
    results: Mapping[str, object],
    model_identity: Mapping[str, tuple[dict[str, object], str]],
) -> Mapping[str, dict[str, object]]:
    rows = _array(results.get("model_invocations"), "model invocations")
    if len(rows) != 138:
        raise EvidenceImportError("model invocation count differs")
    invocations: dict[str, dict[str, object]] = {}
    for row_value in rows:
        row = _object(row_value, "model invocation")
        invocation_id = _text(row.get("invocation_id"), "model invocation id")
        if invocation_id in invocations:
            raise EvidenceImportError("model invocation id is duplicated")
        candidate = _text(row.get("candidate_id"), "model invocation candidate")
        identity = model_identity.get(candidate)
        if identity is None:
            raise EvidenceImportError("model invocation candidate is unknown")
        model_value, _ = identity
        _expect(row.get("model_id"), model_value.get("model_id"), "model invocation model")
        _expect(row.get("revision"), model_value.get("revision"), "model invocation revision")
        _expect(row.get("status"), "PASS", "model invocation status")
        _expect(row.get("error"), None, "model invocation error")
        items = _array(row.get("items"), "model invocation items")
        batch_size = _integer(row.get("batch_size"), "model batch size", minimum=1)
        if len(items) != batch_size:
            raise EvidenceImportError("model invocation batch size differs")
        for index, item_value in enumerate(items):
            item = _object(item_value, "model invocation item")
            _expect(item.get("index"), index, "model invocation item index")
            raw = _text(item.get("raw_output"), "model raw output")
            _expect(item.get("raw_output_sha256"), hashlib.sha256(raw.encode()).hexdigest(), "model raw output digest")
            rendered = _text(item.get("rendered_prompt"), "rendered prompt")
            _expect(item.get("rendered_prompt_sha256"), hashlib.sha256(rendered.encode()).hexdigest(), "rendered prompt digest")
            _integer(item.get("prompt_tokens"), "prompt tokens")
            _integer(item.get("completion_tokens"), "completion tokens")
        _number(row.get("latency_seconds"), "model invocation latency")
        _integer(row.get("peak_allocated_vram_bytes"), "allocated VRAM")
        _integer(row.get("peak_reserved_vram_bytes"), "reserved VRAM")
        invocations[invocation_id] = row
    return MappingProxyType(invocations)


def _validate_tool_calls(results: Mapping[str, object]) -> Mapping[str, dict[str, object]]:
    rows = _array(results.get("tool_calls"), "tool calls")
    if len(rows) != 15:
        raise EvidenceImportError("tool call count differs")
    calls: dict[str, dict[str, object]] = {}
    for row_value in rows:
        row = _object(row_value, "tool call")
        call_id = _text(row.get("tool_call_id"), "tool call id")
        if call_id in calls:
            raise EvidenceImportError("tool call id is duplicated")
        _expect(row.get("status"), "PASS", "tool call status")
        _expect(row.get("error"), None, "tool call error")
        _expect(row.get("side_effects"), False, "tool side effects")
        output = _text(row.get("output"), "tool output")
        _expect(row.get("output_sha256"), hashlib.sha256(output.encode()).hexdigest(), "tool output digest")
        _number(row.get("latency_seconds"), "tool latency")
        calls[call_id] = row
    return MappingProxyType(calls)


def _identity_maps(identities: Mapping[str, object]) -> tuple[
    Mapping[str, tuple[dict[str, object], str]],
    Mapping[str, Mapping[str, str]],
]:
    models: dict[str, tuple[dict[str, object], str]] = {}
    for value in _array(identities.get("models"), "model identities"):
        payload, digest = _identity_record(value, "model identity")
        candidate = _text(payload.get("candidate_id"), "model candidate")
        if candidate in models:
            raise EvidenceImportError("model identity is duplicated")
        models[candidate] = (payload, digest)
    categories: dict[str, Mapping[str, str]] = {}
    for category in (
        "contexts",
        "decompositions",
        "parallel_profiles",
        "specialist_profiles",
        "strategies",
        "tools",
    ):
        values = _object(identities.get(category), f"{category} identities")
        category_map: dict[str, str] = {}
        for key, value in values.items():
            _, digest = _identity_record(value, f"{category}.{key}")
            category_map[key] = digest
        categories[category] = MappingProxyType(category_map)
    for category in ("runtime", "validation", "output", "environment", "prompts", "taskset"):
        _, digest = _identity_record(identities.get(category), f"{category} identity")
        categories[category] = MappingProxyType({category: digest})
    return MappingProxyType(models), MappingProxyType(categories)


def _validate_cells(
    spec: Mapping[str, object],
    results: Mapping[str, object],
    invocations: Mapping[str, dict[str, object]],
    tool_calls: Mapping[str, dict[str, object]],
    model_identity: Mapping[str, tuple[dict[str, object], str]],
    identity_categories: Mapping[str, Mapping[str, str]],
) -> tuple[tuple[ImportedRawStrategyCell, ...], Mapping[str, dict[str, object]]]:
    variants = {
        _text(_object(value, "variant").get("variant_id"), "variant id"): _object(value, "variant")
        for value in _array(spec.get("variants"), "variants")
    }
    tasks = {
        _text(_object(value, "task").get("task_id"), "task id"): _object(value, "task")
        for value in _array(spec.get("tasks"), "tasks")
    }
    repetitions = _integer(spec.get("repetitions"), "repetitions", minimum=1)
    expected = {
        (variant_id, task_id, repetition)
        for variant_id in variants
        for task_id in tasks
        for repetition in range(1, repetitions + 1)
    }
    cells = _array(results.get("cells"), "cells")
    if len(cells) != len(expected) or len(cells) != 120:
        raise EvidenceImportError("strategy cell count differs")
    observed: set[tuple[str, str, int]] = set()
    by_id: dict[str, dict[str, object]] = {}
    sequence_indexes: set[int] = set()
    referenced_invocations: set[str] = set()
    referenced_tools: set[str] = set()
    imported: list[ImportedRawStrategyCell] = []
    runtime_digest = identity_categories["runtime"]["runtime"]
    validation_digest = identity_categories["validation"]["validation"]
    output_digest = identity_categories["output"]["output"]
    for value in cells:
        cell = _object(value, "strategy cell")
        cell_id = _text(cell.get("cell_id"), "cell id")
        if cell_id in by_id:
            raise EvidenceImportError("strategy cell id is duplicated")
        variant_id = _text(cell.get("variant_id"), "cell variant")
        task_id = _text(cell.get("task_id"), "cell task")
        repetition = _integer(cell.get("repetition"), "cell repetition", minimum=1)
        coordinate = (variant_id, task_id, repetition)
        if coordinate in observed:
            raise EvidenceImportError("strategy cell coordinate is duplicated")
        observed.add(coordinate)
        variant = variants.get(variant_id)
        task = tasks.get(task_id)
        if variant is None or task is None:
            raise EvidenceImportError("strategy cell variant/task is unknown")
        _expect(cell_id, f"{variant_id}::{task_id}::r{repetition}", "cell id")
        for field, variant_field in (
            ("model", "model"),
            ("strategy", "strategy"),
            ("context_policy", "context"),
            ("execution_profile", "execution"),
            ("specialization", "specialization"),
            ("tool_policy", "tool_policy"),
        ):
            _expect(cell.get(field), variant.get(variant_field), f"cell {field}")
        _expect(cell.get("task_prompt"), task.get("prompt"), "cell task prompt")
        _expect(cell.get("expected_answer"), task.get("expected_answer"), "cell expected answer")
        model_id = _text(cell.get("model"), "cell model")
        strategy_id = _text(cell.get("strategy"), "cell strategy")
        context_id = _text(cell.get("context_policy"), "cell context")
        execution_id = _text(cell.get("execution_profile"), "cell execution profile")
        specialist_id = _text(cell.get("specialization"), "cell specialist")
        tool_id = _text(cell.get("tool_policy"), "cell tool policy")
        identities = _object(cell.get("identity_sha256"), "cell identities")
        expected_identity_keys = {
            "context",
            "decomposition",
            "model",
            "output",
            "parallel",
            "prompt",
            "runtime",
            "specialist",
            "strategy",
            "tool",
            "validation",
        }
        if set(identities) != expected_identity_keys:
            raise EvidenceImportError("cell identity classes differ")
        for identity_value in identities.values():
            _sha(identity_value, "cell identity")
        model_record = model_identity.get(model_id)
        if model_record is None:
            raise EvidenceImportError("cell model identity is unknown")
        expected_identities = {
            "context": identity_categories["contexts"][context_id],
            "decomposition": identity_categories["decompositions"][strategy_id],
            "model": model_record[1],
            "output": output_digest,
            "parallel": identity_categories["parallel_profiles"][execution_id],
            "runtime": runtime_digest,
            "specialist": identity_categories["specialist_profiles"][specialist_id],
            "strategy": identity_categories["strategies"][strategy_id],
            "tool": identity_categories["tools"][tool_id],
            "validation": validation_digest,
        }
        for key, expected_digest in expected_identities.items():
            _expect(identities.get(key), expected_digest, f"cell {key} identity")
        invocation_refs = _array(cell.get("invocation_refs"), "cell invocation refs")
        model_call_count = _integer(cell.get("model_calls"), "cell ModelCalls")
        if len(invocation_refs) != model_call_count:
            raise EvidenceImportError("cell ModelCall count differs from invocation refs")
        resolved_items: list[dict[str, object]] = []
        resolved_invocations: list[dict[str, object]] = []
        invocation_ids: list[str] = []
        for raw_ref in invocation_refs:
            invocation_ref = _object(raw_ref, "invocation ref")
            invocation_id = _text(invocation_ref.get("invocation_id"), "invocation ref id")
            invocation = invocations.get(invocation_id)
            if invocation is None:
                raise EvidenceImportError("cell invocation ref is unresolved")
            index = _integer(invocation_ref.get("item_index"), "invocation item index")
            items = _array(invocation.get("items"), "invocation items")
            if index >= len(items):
                raise EvidenceImportError("invocation item index is out of range")
            _expect(invocation.get("candidate_id"), model_id, "cell invocation model")
            resolved_items.append(_object(items[index], "invocation item"))
            resolved_invocations.append(invocation)
            invocation_ids.append(invocation_id)
            referenced_invocations.add(invocation_id)
        if not resolved_items:
            raise EvidenceImportError("strategy cell has no ModelCall evidence")
        final_output = _text(cell.get("final_output"), "cell final output")
        _expect(resolved_items[-1].get("raw_output"), final_output, "cell final output binding")
        draft_output = cell.get("draft_output")
        if model_call_count == 2:
            _expect(draft_output, resolved_items[0].get("raw_output"), "cell draft output binding")
        elif draft_output is not None:
            raise EvidenceImportError("single-call cell unexpectedly has draft output")
        prompt_tokens = sum(_integer(item.get("prompt_tokens"), "invocation prompt tokens") for item in resolved_items)
        completion_tokens = sum(_integer(item.get("completion_tokens"), "invocation completion tokens") for item in resolved_items)
        _expect(cell.get("prompt_tokens"), prompt_tokens, "cell prompt tokens")
        _expect(cell.get("completion_tokens"), completion_tokens, "cell completion tokens")
        latency = sum(_number(item.get("latency_seconds"), "invocation latency") for item in resolved_invocations)
        cell_latency = _number(cell.get("model_latency_seconds"), "cell model latency")
        _close(cell_latency, latency, "cell model latency")
        tool_ref_values = _array(cell.get("tool_call_refs"), "cell tool refs")
        tool_count = _integer(cell.get("tool_calls"), "cell ToolCalls")
        if len(tool_ref_values) != tool_count:
            raise EvidenceImportError("cell ToolCall count differs from refs")
        resolved_tools: list[dict[str, object]] = []
        resolved_tool_ids: list[str] = []
        for raw_tool_ref in tool_ref_values:
            tool_ref = _text(raw_tool_ref, "tool call ref")
            tool = tool_calls.get(tool_ref)
            if tool is None or tool.get("cell_key") != cell_id:
                raise EvidenceImportError("cell ToolCall ref is unresolved or misbound")
            referenced_tools.add(tool_ref)
            resolved_tools.append(tool)
            resolved_tool_ids.append(tool_ref)
        semantic = _object(cell.get("semantic_validation"), "cell semantic validation")
        _expect(semantic.get("rule_id"), task.get("validation_rule"), "cell validation rule")
        evidence = _object(semantic.get("evidence"), "cell semantic evidence")
        expected_answer = _text(task.get("expected_answer"), "task expected answer")
        normalized_expected = _normalize_exact(expected_answer)
        normalized_output = _normalize_exact(final_output)
        matched = normalized_expected == normalized_output
        _expect(evidence.get("expected"), expected_answer, "semantic expected evidence")
        _expect(evidence.get("normalized_expected"), normalized_expected, "semantic normalized expected")
        _expect(evidence.get("normalized_output"), normalized_output, "semantic normalized output")
        _expect(evidence.get("matched"), matched, "semantic matched evidence")
        _expect(semantic.get("status"), "PASS" if matched else "FAIL", "semantic status")
        _expect(cell.get("infrastructure_status"), "PASS", "cell infrastructure status")
        _expect(cell.get("infrastructure_error"), None, "cell infrastructure error")
        graph = _object(cell.get("graph_equivalent"), "cell graph metrics")
        depth = _integer(graph.get("depth"), "graph depth", minimum=1)
        width = _integer(graph.get("width"), "graph width", minimum=1)
        revisions = _integer(graph.get("revisions"), "graph revisions")
        repairs = _integer(graph.get("repairs"), "graph repairs")
        sequence_index = _integer(cell.get("execution_sequence_index"), "cell sequence index", minimum=1)
        if sequence_index in sequence_indexes:
            raise EvidenceImportError("cell sequence index is duplicated")
        sequence_indexes.add(sequence_index)
        peak_allocated = max(_integer(item.get("peak_allocated_vram_bytes"), "cell allocated VRAM") for item in resolved_invocations)
        peak_reserved = max(_integer(item.get("peak_reserved_vram_bytes"), "cell reserved VRAM") for item in resolved_invocations)
        imported.append(
            ImportedRawStrategyCell(
                cell_id,
                variant_id,
                model_id,
                strategy_id,
                task_id,
                repetition,
                final_output,
                hashlib.sha256(final_output.encode()).hexdigest(),
                matched,
                True,
                model_call_count,
                tool_count,
                cell_latency,
                prompt_tokens,
                completion_tokens,
                depth,
                width,
                revisions,
                repairs,
                peak_allocated,
                peak_reserved,
                tuple(invocation_ids),
                tuple(resolved_tool_ids),
                MappingProxyType({key: _sha(value, "cell identity") for key, value in identities.items()}),
            )
        )
        by_id[cell_id] = cell
    if observed != expected or sequence_indexes != set(range(1, len(cells) + 1)):
        raise EvidenceImportError("strategy cell coverage/order differs")
    if referenced_invocations != set(invocations) or referenced_tools != set(tool_calls):
        raise EvidenceImportError("worker invocation/tool evidence is orphaned or missing")
    return tuple(sorted(imported, key=lambda item: item.cell_id)), MappingProxyType(by_id)


def _validate_summaries(
    results: Mapping[str, object],
    cells: Sequence[ImportedRawStrategyCell],
    raw_cells: Mapping[str, dict[str, object]],
    invocations: Mapping[str, dict[str, object]],
) -> Mapping[str, VariantEvidenceSummary]:
    source = _object(results.get("variant_summaries"), "variant summaries")
    by_variant: dict[str, list[ImportedRawStrategyCell]] = {}
    for cell in cells:
        by_variant.setdefault(cell.variant_id, []).append(cell)
    summaries: dict[str, VariantEvidenceSummary] = {}
    for variant_id, variant_cells in sorted(by_variant.items()):
        raw = _object(source.get(variant_id), f"summary {variant_id}")
        refs: set[str] = set()
        for cell in variant_cells:
            for value in _array(raw_cells[cell.cell_id].get("invocation_refs"), "summary invocation refs"):
                refs.add(_text(_object(value, "summary invocation ref").get("invocation_id"), "summary invocation id"))
        invocation_rows = [invocations[value] for value in refs]
        semantic_pass = sum(item.semantic_pass for item in variant_cells)
        prompt_tokens = sum(item.prompt_tokens for item in variant_cells)
        completion_tokens = sum(item.completion_tokens for item in variant_cells)
        logical_calls = sum(item.model_calls for item in variant_cells)
        tool_count = sum(item.tool_calls for item in variant_cells)
        unique_latency = sum(_number(item.get("latency_seconds"), "summary invocation latency") for item in invocation_rows)
        expected_values: Mapping[str, object] = {
            "cells": len(variant_cells),
            "semantic_pass": semantic_pass,
            "semantic_fail": len(variant_cells) - semantic_pass,
            "infrastructure_pass": len(variant_cells),
            "infrastructure_fail_or_timeout": 0,
            "logical_model_calls": logical_calls,
            "physical_model_invocations": len(refs),
            "tool_calls": tool_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        for key, expected in expected_values.items():
            _expect(raw.get(key), expected, f"{variant_id} summary {key}")
        _close(_number(raw.get("unique_invocation_latency_seconds"), "summary latency"), unique_latency, f"{variant_id} unique latency")
        peak_allocated = max(_integer(item.get("peak_allocated_vram_bytes"), "summary allocated VRAM") for item in invocation_rows)
        peak_reserved = max(_integer(item.get("peak_reserved_vram_bytes"), "summary reserved VRAM") for item in invocation_rows)
        _expect(raw.get("maximum_peak_allocated_vram_bytes"), peak_allocated, "summary allocated VRAM")
        _expect(raw.get("maximum_peak_reserved_vram_bytes"), peak_reserved, "summary reserved VRAM")
        graph = _object(raw.get("graph_equivalent"), "summary graph")
        graph_depth = max(item.graph_depth for item in variant_cells)
        graph_width = max(item.graph_width for item in variant_cells)
        graph_revisions = sum(item.graph_revisions for item in variant_cells)
        graph_repairs = sum(item.graph_repairs for item in variant_cells)
        _expect(graph.get("maximum_depth"), graph_depth, "summary graph depth")
        _expect(graph.get("maximum_width"), graph_width, "summary graph width")
        _expect(graph.get("revisions"), graph_revisions, "summary graph revisions")
        _expect(graph.get("repairs"), graph_repairs, "summary graph repairs")
        summaries[variant_id] = VariantEvidenceSummary(
            variant_id,
            len(variant_cells),
            semantic_pass,
            len(variant_cells) - semantic_pass,
            len(variant_cells),
            logical_calls,
            len(refs),
            tool_count,
            prompt_tokens,
            completion_tokens,
            unique_latency,
            peak_allocated,
            peak_reserved,
            graph_depth,
            graph_width,
            graph_revisions,
            graph_repairs,
        )
    if set(source) != set(summaries):
        raise EvidenceImportError("variant summary set differs")
    return MappingProxyType(summaries)


def _base_contracts(
    project_ref: ProjectRef,
    spec: Mapping[str, object],
    model_identity: Mapping[str, tuple[dict[str, object], str]],
    identity_categories: Mapping[str, Mapping[str, str]],
) -> tuple[
    CapabilityRef,
    WorkloadProfile,
    EvaluationTaskSet,
    Mapping[str, EvaluationTask],
    Mapping[str, ModelCandidate],
]:
    capability = CapabilityRef("strategy.evaluate", "1.0.0")
    tasks: dict[str, EvaluationTask] = {}
    task_values = _array(spec.get("tasks"), "spec tasks")
    for value in task_values:
        task = _object(value, "spec task")
        task_id = _text(task.get("task_id"), "spec task id")
        tasks[task_id] = EvaluationTask(
            project_ref,
            task_id,
            1,
            ContentRef.from_bytes(_canonical_bytes(task), media_type="application/json"),
            capability,
            f"template://p4-02/{task_id}/v1",
            "reasoning",
            "bounded",
        )
    task_set = EvaluationTaskSet(
        project_ref,
        "p4-02-l40s-taskset",
        1,
        ContentRef.from_bytes(_canonical_bytes(task_values), media_type="application/json"),
        tuple(tasks.values()),
        "selection-policy://p4-02/exact-all/v1",
    )
    profile = WorkloadProfile(
        project_ref,
        "p4-02-l40s",
        1,
        ContentRef.from_bytes(_canonical_bytes({"tasks": sorted(tasks)}), media_type="application/json"),
        {"domain": "bounded-reasoning", "output": "exact-answer"},
    )
    runtime_digest = identity_categories["runtime"]["runtime"]
    models: dict[str, ModelCandidate] = {}
    for candidate_id, (raw, digest) in model_identity.items():
        revision = _text(raw.get("revision"), "model revision")
        model_id = _text(raw.get("model_id"), "model id")
        models[candidate_id] = ModelCandidate(
            project_ref,
            candidate_id,
            f"model-deployment://huggingface/{model_id}@{revision}",
            digest,
            "adapter://p4-02/local-transformers",
            f"runtime://p4-02/{runtime_digest}",
            f"hf-{revision}",
            False,
            capability,
        )
    return capability, profile, task_set, MappingProxyType(tasks), MappingProxyType(models)


def _strategy_for_variant(
    project_ref: ProjectRef,
    variant: Mapping[str, object],
    strategy_id: str,
    identities: Mapping[str, object],
    identity_categories: Mapping[str, Mapping[str, str]],
) -> ExecutionStrategy:
    raw_strategy_id = _text(variant.get("strategy"), "variant strategy")
    strategy_payload, strategy_digest = _identity_record(
        _object(identities.get("strategies"), "strategy identities").get(raw_strategy_id),
        f"strategy {raw_strategy_id}",
    )
    skill = SkillArtifact(
        project_ref,
        f"{raw_strategy_id}.skill",
        1,
        ContentRef.from_bytes(_canonical_bytes(strategy_payload), media_type="application/json"),
        {"workload": "p4-02-l40s"},
    )
    prompts = _object(strategy_payload.get("system_prompts"), "strategy system prompts")
    prompt = PromptArtifact(
        project_ref,
        f"{raw_strategy_id}.prompt",
        1,
        ContentRef.from_bytes(_canonical_bytes(prompts), media_type="application/json"),
        {"workload": "p4-02-l40s"},
    )
    context_id = _text(variant.get("context"), "variant context")
    tool_id = _text(variant.get("tool_policy"), "variant tool policy")
    parallel_id = _text(variant.get("execution"), "variant execution")
    specialist_id = _text(variant.get("specialization"), "variant specialist")
    decomposition_digest = identity_categories["decompositions"][raw_strategy_id]
    patterns: tuple[StrategyPattern, ...] = (StrategyPattern.DIRECT,)
    if raw_strategy_id == "s2_draft_verify_v1":
        patterns = (StrategyPattern.DIRECT, StrategyPattern.VALIDATOR_ON_DEMAND)
    validation_ref = f"validation-policy://p4-02/{identity_categories['validation']['validation']}"
    return ExecutionStrategy(
        project_ref,
        strategy_id,
        1,
        patterns,
        {"workload": "p4-02-l40s"},
        (skill,),
        (prompt,),
        f"decomposition-policy://p4-02/{decomposition_digest}",
        f"tool-policy://p4-02/{identity_categories['tools'][tool_id]}",
        f"context-policy://p4-02/{identity_categories['contexts'][context_id]}",
        f"model-call-policy://p4-02/{strategy_digest}",
        f"loop-stop-policy://p4-02/{strategy_digest}",
        f"parallel-policy://p4-02/{identity_categories['parallel_profiles'][parallel_id]}",
        f"specialist-policy://p4-02/{identity_categories['specialist_profiles'][specialist_id]}",
        (validation_ref,),
        "failure-policy://p4-02/preserve-all/v1",
        f"output-policy://p4-02/{identity_categories['output']['output']}",
    )


_MATRIX_DIMENSION: Mapping[str, tuple[StrategyDimension, ...]] = MappingProxyType(
    {
        "same_model_s1_s2": (StrategyDimension.FULL_STRATEGY,),
        "tool_policy": (StrategyDimension.TOOL_POLICY,),
        "context_policy": (StrategyDimension.CONTEXT_POLICY,),
        "parallel_vs_serial": (StrategyDimension.PARALLELIZATION,),
        "specialist_vs_generalist": (StrategyDimension.SPECIALIST,),
        "model_strategy_factorial": (StrategyDimension.FULL_STRATEGY,),
    }
)


def _build_matrices(
    project_ref: ProjectRef,
    spec: Mapping[str, object],
    results: Mapping[str, object],
    binding: StrategyEvidenceBinding,
    raw_cells: Mapping[str, dict[str, object]],
    invocations: Mapping[str, dict[str, object]],
    tool_calls: Mapping[str, dict[str, object]],
    identities: Mapping[str, object],
    identity_categories: Mapping[str, Mapping[str, str]],
    capability: CapabilityRef,
    profile: WorkloadProfile,
    task_set: EvaluationTaskSet,
    tasks: Mapping[str, EvaluationTask],
    models: Mapping[str, ModelCandidate],
) -> tuple[ImportedStrategyMatrixEvidence, ...]:
    variants = {
        _text(_object(value, "variant").get("variant_id"), "variant id"): _object(value, "variant")
        for value in _array(spec.get("variants"), "variants")
    }
    result_matrices = {
        _text(_object(value, "result matrix").get("matrix_id"), "matrix id"): _object(value, "result matrix")
        for value in _array(results.get("matrices"), "result matrices")
    }
    spec_matrices = _array(spec.get("matrices"), "spec matrices")
    known_confounders = {
        "cell_timing": "suite_envelope_timestamp_for_external_worker_cells",
        "engine_execution_capture": "external_worker_import_without_native_engine_node_authority",
        "graph_identity_binding": "reference_project_run_and_graph_metrics_not_native_graph_records",
        "taskset_scope": "small_exact_answer_taskset",
        "vram_attribution": "process_wide_with_both_model_snapshots_resident",
    }
    matrices: list[ImportedStrategyMatrixEvidence] = []
    seen_baseline_uses: set[str] = set()
    for matrix_value in spec_matrices:
        matrix = _object(matrix_value, "spec matrix")
        matrix_id = _text(matrix.get("matrix_id"), "matrix id")
        dimensions = _MATRIX_DIMENSION.get(matrix_id)
        if dimensions is None:
            raise EvidenceImportError("unexpected strategy matrix")
        conditions = tuple(_text(value, "matrix condition") for value in _array(matrix.get("conditions"), "matrix conditions"))
        if len(set(conditions)) != len(conditions) or any(value not in variants for value in conditions):
            raise EvidenceImportError("matrix conditions are missing or duplicated")
        factorial = matrix_id == "model_strategy_factorial"
        selected_models = tuple(
            models[value]
            for value in sorted({_text(variants[condition].get("model"), "condition model") for condition in conditions})
        )
        strategy_by_condition: dict[str, ExecutionStrategy] = {}
        canonical_strategies: dict[str, ExecutionStrategy] = {}
        for condition in conditions:
            raw_strategy_id = _text(variants[condition].get("strategy"), "condition strategy")
            canonical_id = raw_strategy_id if factorial else condition
            strategy = canonical_strategies.get(canonical_id)
            if strategy is None:
                strategy = _strategy_for_variant(
                    project_ref,
                    variants[condition],
                    canonical_id,
                    identities,
                    identity_categories,
                )
                canonical_strategies[canonical_id] = strategy
            else:
                candidate = _strategy_for_variant(
                    project_ref,
                    variants[condition],
                    canonical_id,
                    identities,
                    identity_categories,
                )
                if candidate.canonical_digest != strategy.canonical_digest:
                    raise EvidenceImportError("factorial strategy changed across model cells")
            strategy_by_condition[condition] = strategy
        confounders = dict(known_confounders)
        if matrix_id == "parallel_vs_serial":
            confounders["parallel_batching"] = "padded_single_gpu_batch_vs_independent_serial_calls"
        if matrix_id == "tool_policy":
            confounders["tool_inputs"] = "fixed_deterministic_structured_task_facts"
        experiment = StrategyEvaluationExperiment(
            project_ref,
            matrix_id,
            1,
            capability,
            profile,
            task_set,
            EvidenceClass.QUASI_CONTROLLED,
            MatrixKind.FACTORIAL if factorial else MatrixKind.SAME_MODEL,
            {
                "EXECUTION_STRATEGY": "varied",
                "MODEL_IMPLEMENTATION": "varied" if factorial else "fixed",
                "OUTPUT": "fixed",
                "RESOURCE": "fixed",
                "TASK_SET": "fixed",
                "VALIDATION": "fixed",
            },
            dimensions,
            confounders,
            selected_models,
            tuple(canonical_strategies.values()),
            (f"validation-policy://p4-02/{identity_categories['validation']['validation']}",),
            f"resource-policy://p4-02/{identity_categories['environment']['environment']}",
            f"order-policy://p4-02/{_digest(spec.get('randomization'))}",
            f"cache-policy://p4-02/{identity_categories['runtime']['runtime']}",
            "READ_ONLY",
            3,
        )
        runs: list[StrategyEvaluationRun] = []
        source_ids: list[str] = []
        for condition in conditions:
            strategy = strategy_by_condition[condition]
            selected = sorted(
                (value for value in raw_cells.values() if value.get("variant_id") == condition),
                key=lambda value: (_text(value.get("task_id"), "raw task"), _integer(value.get("repetition"), "raw repetition")),
            )
            if len(selected) != 15:
                raise EvidenceImportError("matrix condition does not contain 15 raw cells")
            for cell in selected:
                cell_id = _text(cell.get("cell_id"), "matrix cell id")
                source_ids.append(cell_id)
                semantic = _object(cell.get("semantic_validation"), "matrix semantic validation")
                semantic_pass = semantic.get("status") == "PASS"
                invocation_refs = _array(cell.get("invocation_refs"), "matrix invocation refs")
                invocation_rows = [
                    invocations[_text(_object(value, "matrix invocation ref").get("invocation_id"), "matrix invocation id")]
                    for value in invocation_refs
                ]
                tool_ref_values = [_text(value, "matrix tool ref") for value in _array(cell.get("tool_call_refs"), "matrix tool refs")]
                tool_rows = [tool_calls[value] for value in tool_ref_values]
                graph = _object(cell.get("graph_equivalent"), "matrix graph metrics")
                model_call_count = _integer(cell.get("model_calls"), "matrix ModelCalls")
                tool_call_count = _integer(cell.get("tool_calls"), "matrix ToolCalls")
                prompt_tokens = _integer(cell.get("prompt_tokens"), "matrix prompt tokens")
                completion_tokens = _integer(cell.get("completion_tokens"), "matrix completion tokens")
                model_latency = _number(cell.get("model_latency_seconds"), "matrix model latency")
                tool_latency = sum(_number(value.get("latency_seconds"), "matrix tool latency") for value in tool_rows)
                peak_allocated = max(_integer(value.get("peak_allocated_vram_bytes"), "matrix allocated VRAM") for value in invocation_rows)
                peak_reserved = max(_integer(value.get("peak_reserved_vram_bytes"), "matrix reserved VRAM") for value in invocation_rows)
                model_id = _text(cell.get("model"), "matrix model")
                task_id = _text(cell.get("task_id"), "matrix task")
                completed_reuse = int(condition in seen_baseline_uses)
                metrics = StrategyMetricSet(
                    semantic_pass,
                    1.0 if semantic_pass else 0.0,
                    model_latency + tool_latency,
                    model_call_count,
                    prompt_tokens,
                    completion_tokens,
                    prompt_tokens,
                    model_latency,
                    None,
                    tool_call_count,
                    0,
                    0,
                    0,
                    tool_latency,
                    0,
                    sum(len(_text(value.get("output"), "matrix tool output").encode()) for value in tool_rows),
                    max(1, model_call_count + tool_call_count),
                    _integer(graph.get("depth"), "matrix graph depth", minimum=1),
                    _integer(graph.get("width"), "matrix graph width", minimum=1),
                    _integer(graph.get("revisions"), "matrix graph revisions"),
                    0,
                    _integer(graph.get("repairs"), "matrix graph repairs"),
                    0,
                    completed_reuse,
                    {
                        "gpu.vram_peak_allocated_bytes": float(peak_allocated),
                        "gpu.vram_peak_reserved_bytes": float(peak_reserved),
                        "model.physical_invocation_refs": float(len(invocation_rows)),
                    },
                )
                runs.append(
                    StrategyEvaluationRun(
                        experiment,
                        model_id,
                        strategy.strategy_id,
                        strategy.canonical_digest,
                        tasks[task_id],
                        _integer(cell.get("repetition"), "matrix repetition", minimum=1),
                        binding.run_ref,
                        metrics,
                        "passed",
                        "passed" if semantic_pass else "failed",
                        "passed",
                        "completed",
                        _timestamp(results.get("run_started_at"), "run started"),
                        _timestamp(results.get("run_finished_at"), "run finished"),
                        (
                            binding.source_ref,
                            f"artifact://external/p4-02-l40s/cell/{cell_id}",
                        ),
                    )
                )
            seen_baseline_uses.add(condition)
        result = build_strategy_evaluation_result(experiment, runs)
        result_matrix = result_matrices.get(matrix_id)
        if result_matrix is None:
            raise EvidenceImportError("results omitted a required matrix")
        _expect(result_matrix.get("conditions"), list(conditions), "matrix condition order")
        paired = result_matrix.get("paired_descriptive")
        if paired is not None and not factorial:
            raw_pair = _object(paired, "paired descriptive result")
            comparison = result.pairwise_comparisons[0]
            _expect(raw_pair.get("treatment_win"), comparison.paired_losses, "treatment wins")
            _expect(raw_pair.get("treatment_loss"), comparison.paired_wins, "treatment losses")
            _expect(raw_pair.get("tie"), comparison.paired_ties, "treatment ties")
        matrices.append(
            ImportedStrategyMatrixEvidence(
                matrix_id,
                conditions,
                experiment,
                result,
                tuple(sorted(source_ids)),
            )
        )
    if set(result_matrices) != {item.matrix_id for item in matrices}:
        raise EvidenceImportError("result matrix set differs from spec")
    return tuple(sorted(matrices, key=lambda item: item.matrix_id))


def import_p4_02_l40s_evidence(
    project_ref: ProjectRef,
    artifacts: ExternalStrategyEvaluationArtifacts,
    binding: StrategyEvidenceBinding,
    *,
    require_real: bool = True,
) -> ImportedStrategyEvaluationEvidence:
    """Validate exact worker bytes, then bind them as QUASI_CONTROLLED evidence."""

    if not isinstance(project_ref, ProjectRef) or not isinstance(artifacts, ExternalStrategyEvaluationArtifacts):
        raise EvidenceImportError("strategy evidence Project/artifacts are malformed")
    if not isinstance(binding, StrategyEvidenceBinding) or binding.run_ref.project_ref != project_ref:
        raise EvidenceImportError("strategy evidence binding crossed Project scope")
    observed_hashes = artifacts.sha256()
    exact_real = dict(observed_hashes) == dict(P4_02_L40S_FIXTURE_SHA256)
    if require_real and not exact_real:
        raise EvidenceImportError("strategy evidence bytes differ from the verified REAL fixture")
    spec = _load_document(artifacts.spec, "strategy spec")
    results = _load_document(artifacts.results, "strategy results")
    manifest = _load_document(artifacts.manifest, "strategy manifest")
    post = _load_document(artifacts.post_run_resource, "post-run resource")
    _validate_static(spec, results, manifest, post, artifacts)
    identities = _object(results.get("identities"), "identities")
    _validate_identity_tree(identities, "identities")
    model_identity, identity_categories = _identity_maps(identities)
    invocations = _validate_invocations(results, model_identity)
    tools = _validate_tool_calls(results)
    raw_cells, raw_by_id = _validate_cells(
        spec,
        results,
        invocations,
        tools,
        model_identity,
        identity_categories,
    )
    summaries = _validate_summaries(results, raw_cells, raw_by_id, invocations)
    capability, profile, task_set, tasks, models = _base_contracts(
        project_ref,
        spec,
        model_identity,
        identity_categories,
    )
    matrices = _build_matrices(
        project_ref,
        spec,
        results,
        binding,
        raw_by_id,
        invocations,
        tools,
        identities,
        identity_categories,
        capability,
        profile,
        task_set,
        tasks,
        models,
    )
    result_content_refs = {
        item.matrix_id: ContentRef.from_bytes(
            _canonical_bytes(item.result.payload()),
            media_type="application/vnd.biella.strategy-evaluation-result+json",
        )
        for item in matrices
    }
    knowledge = tuple(
        StrategyEvaluationKnowledgeCandidate(
            project_ref,
            item.experiment.canonical_digest,
            result_content_refs[item.matrix_id],
            (
                binding.source_ref,
                f"artifact://external/p4-02-l40s/matrix/{item.matrix_id}",
            ),
        )
        for item in matrices
    )
    known_confounders = tuple(
        _text(value, "known confounder")
        for value in _array(results.get("known_confounders"), "known confounders")
    )
    return ImportedStrategyEvaluationEvidence(
        artifacts,
        binding,
        EvidenceReality.REAL if exact_real else EvidenceReality.REFERENCE,
        EvidenceReality.REFERENCE,
        raw_cells,
        matrices,
        summaries,
        knowledge,
        known_confounders,
        sum(item.infrastructure_pass for item in raw_cells),
        sum(item.semantic_pass for item in raw_cells),
        sum(not item.semantic_pass for item in raw_cells),
        len(invocations),
        len(tools),
        _integer(_object(post.get("gpu"), "post GPU").get("memory_used_mib"), "post GPU memory"),
        _integer(post.get("model_runtime_process_count"), "post model processes"),
        _boolean(post.get("persistent_model_or_agent_residency"), "post residency"),
        False,
        False,
    )


__all__ = [
    "EvidenceImportError",
    "ExternalStrategyEvaluationArtifacts",
    "ImportedRawStrategyCell",
    "ImportedStrategyEvaluationEvidence",
    "ImportedStrategyMatrixEvidence",
    "P4_02_L40S_FIXTURE_SHA256",
    "StrategyEvidenceBinding",
    "VariantEvidenceSummary",
    "import_p4_02_l40s_evidence",
]
