"""Durable Engine evidence importer for retained REAL P3-10 simulation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import time
from typing import cast

from PIL import Image
import pytest

from minitz_os.engine.artifact import (
    Artifact,
    ArtifactScopeError,
    ArtifactService,
    ContentRef,
)
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.event import EventLedger
from minitz_os.engine.execution import NodeExecutionAuthorityError, NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphService, Node, NodeRef
from minitz_os.engine.object_store import FilesystemObjectStorageBackend
from minitz_os.engine.project import ProjectAccess, ProjectStore
from minitz_os.engine.resource import (
    FakeResourceObserver,
    QuantitySource,
    Resource,
    ResourceFitRequest,
    ResourceHealth,
    ResourceObservation,
    ResourceQuantity,
    ResourceRef,
    ResourceService,
)
from minitz_os.engine.run import ExecutionAttempt, RunService
from minitz_os.engine.scheduler import (
    ResourceClaim,
    ScheduledDispatch,
    Scheduler,
    SchedulingRequest,
)
from minitz_os.engine.task import Task, TaskRevisionService
from minitz_os.engine.validation import (
    MetricMeasurement,
    ProjectValidationCriteria,
    ValidationCheck,
    ValidationEvidenceState,
    ValidationService,
    ValidationVerdict,
)


_SCHEMA = "minitz.p3-10.retained-real-evidence/v1"
_KPI_SCHEMA = "minitz.p3-10.prompt-kpis/v1"
_OUTPUT_SCHEMA = "minitz.p3-10.durable-engine-evidence/v1"
_KPI_NAMES = (
    "simulation_cache_used_as_only_authority",
    "verified_segments_lost_after_failure",
    "incompatible_checkpoint_resumes",
    "dependent_solver_steps_parallelized_incorrectly",
    "global_GPU_requirement_for_VFX",
)
_MANIFEST_PATH = "evidence/manifest.json"
_CHECKSUM_PATH = "evidence/manifest.sha256"
_OVERLAY_CHECKSUM_PATH = "evidence/overlay-files.sha256"
_SEGMENTS = ((1, 100), (101, 200), (201, 300))
_RECORD_NAMES = {
    "cache_rebuild",
    "concurrency",
    "failure",
    "game_handoff",
    "integration",
    "process",
    "recovery",
    "render_handoff",
    "resource",
}
_MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
_MAX_MEMBERS = 8192
_MAX_JSON_BYTES = 32 * 1024 * 1024
_MAX_IMAGE_EDGE = 8192
_MAX_IMAGE_PIXELS = 64 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}")
_GIT_OBJECT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_CATEGORY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_ENGINE_ROLE = re.compile(r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+")


@dataclass(frozen=True)
class _RetainedEvidence:
    logical_path: str
    category: str
    payload: bytes
    media_type: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class _FileEvidence:
    kind: str
    logical_path: str
    sha256: str
    media_type: str
    artifact_ref: str
    content_ref: str


@dataclass(frozen=True)
class _SimulationPackage:
    retained: tuple[_RetainedEvidence, ...]
    source: Mapping[str, object]
    project_ref: str
    task_contract_sha256: str
    identity: Mapping[str, str]
    scene: _FileEvidence
    specification: _FileEvidence
    checkpoints: tuple[_FileEvidence, ...]
    bake: _FileEvidence
    preview: _FileEvidence
    records: Mapping[str, str]
    documents: Mapping[str, Mapping[str, object]]
    kpis: Mapping[str, int]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _parse_json(payload: bytes, *, source: str) -> Mapping[str, object]:
    assert len(payload) <= _MAX_JSON_BYTES, source

    def reject_nonfinite(value: str) -> object:
        raise AssertionError(f"non-finite JSON value {value!r} in {source}")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            assert key not in result, f"duplicate JSON key {key!r} in {source}"
            result[key] = value
        return result

    try:
        document: object = json.loads(
            payload,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"invalid JSON in {source}") from exc
    assert isinstance(document, Mapping), source
    return cast(Mapping[str, object], document)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    assert isinstance(value, Mapping), label
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> Sequence[object]:
    assert isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ), label
    return cast(Sequence[object], value)


def _text(value: object, label: str) -> str:
    assert isinstance(value, str) and value and len(value.encode()) <= 2048, label
    return value


def _sha(value: object, label: str) -> str:
    assert isinstance(value, str) and _HEX.fullmatch(value), label
    return value


def _ref(value: object, label: str) -> str:
    assert isinstance(value, str) and _REF.fullmatch(value), label
    return value


def _safe_relative(value: object, label: str) -> str:
    assert isinstance(value, str) and value, label
    parsed = PurePosixPath(value)
    assert not parsed.is_absolute() and ".." not in parsed.parts, label
    assert parsed.as_posix() == value
    assert all(part not in {"", "."} for part in parsed.parts), label
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    assert isinstance(value, int) and not isinstance(value, bool), label
    assert value >= minimum, label
    return value


def _media_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith((".tar.gz", ".tgz")):
        return "application/gzip"
    return {
        ".blend": "application/x-blender",
        ".json": "application/json",
        ".log": "text/plain",
        ".png": "image/png",
        ".sha256": "text/plain",
        ".txt": "text/plain",
    }.get(PurePosixPath(path).suffix.lower(), "application/octet-stream")


def _regular_package_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    mode = path.lstat().st_mode
    assert stat.S_ISREG(mode) and not path.is_symlink(), (
        "retained package must be a regular file"
    )
    return path.resolve(strict=True)


def _checksum_lines(payload: bytes, *, source: str) -> Mapping[str, str]:
    checksums: dict[str, str] = {}
    for line in payload.decode("ascii").splitlines():
        digest, separator, raw_name = line.partition(" ")
        assert separator and _HEX.fullmatch(digest), source
        name = raw_name.strip().removeprefix("*")
        _safe_relative(name, source)
        assert name not in checksums, f"duplicate checksum name: {name}"
        checksums[name] = digest
    assert checksums, source
    return checksums


def _source_identity(
    manifest: Mapping[str, object], files: Mapping[str, bytes]
) -> Mapping[str, object]:
    source = _mapping(manifest.get("source"), "source")
    commit = source.get("commit")
    tree = source.get("tree")
    assert isinstance(commit, str) and _GIT_OBJECT.fullmatch(commit), "source commit"
    assert isinstance(tree, str) and _GIT_OBJECT.fullmatch(tree), "source tree"
    assert len(commit) == len(tree), "source object formats differ"
    overlays = _sequence(source.get("overlays"), "source overlays")
    overlay_count = _integer(source.get("overlay_count"), "source overlay count")
    assert overlay_count == len(overlays), "stale source overlay count"
    normalized: dict[str, str] = {}
    for raw in overlays:
        overlay = _mapping(raw, "source overlay")
        path = _safe_relative(overlay.get("path"), "source overlay path")
        digest = _sha(overlay.get("sha256"), "source overlay digest")
        assert path not in normalized, f"duplicate source overlay: {path}"
        normalized[path] = digest
    if normalized:
        assert _OVERLAY_CHECKSUM_PATH in files, "source overlay checksums missing"
        observed = _checksum_lines(
            files[_OVERLAY_CHECKSUM_PATH], source=_OVERLAY_CHECKSUM_PATH
        )
        assert observed == normalized, "stale source overlay identity"
    expected_commit = os.environ.get("MINITZ_P3_10_EXPECTED_COMMIT")
    expected_tree = os.environ.get("MINITZ_P3_10_EXPECTED_TREE")
    if expected_commit:
        assert commit == expected_commit, "stale source commit"
    if expected_tree:
        assert tree == expected_tree, "stale source tree"
    return {
        "commit": commit,
        "tree": tree,
        "overlay_count": overlay_count,
        "overlays": tuple(
            {"path": path, "sha256": normalized[path]}
            for path in sorted(normalized)
        ),
    }


def _zero_kpis(manifest: Mapping[str, object]) -> Mapping[str, int]:
    report = _mapping(manifest.get("prompt_kpis"), "prompt_kpis")
    assert report.get("schema") == _KPI_SCHEMA
    assert report.get("all_five_zero") is True
    values = _mapping(report.get("kpis"), "prompt KPI values")
    assert set(values) == set(_KPI_NAMES), "prompt KPI names differ"
    normalized: dict[str, int] = {}
    for name in _KPI_NAMES:
        value = _integer(values[name], name)
        assert value == 0, f"non-zero prompt KPI: {name}"
        normalized[name] = value
    return normalized


def _identity(manifest: Mapping[str, object]) -> Mapping[str, str]:
    raw = _mapping(manifest.get("identity"), "simulation identity")
    fields = (
        "executor_ref",
        "generator_ref",
        "resource_ref",
        "runtime_ref",
        "scene_ref",
        "solver_ref",
        "specification_ref",
        "tool_ref",
    )
    normalized = {field: _ref(raw.get(field), field) for field in fields}
    normalized.update(
        {
            "resource_sha256": _sha(raw.get("resource_sha256"), "resource digest"),
            "scene_sha256": _sha(raw.get("scene_sha256"), "scene digest"),
            "specification_sha256": _sha(
                raw.get("specification_sha256"), "specification digest"
            ),
        }
    )
    return normalized


def _payload_index(
    manifest: Mapping[str, object],
    files: Mapping[str, bytes],
    checksums: Mapping[str, str],
) -> Mapping[str, Mapping[str, object]]:
    rows = _sequence(
        _mapping(manifest.get("payload"), "payload").get("files"), "payload files"
    )
    indexed: dict[str, Mapping[str, object]] = {}
    for raw in rows:
        row = _mapping(raw, "payload file")
        path = _safe_relative(row.get("path"), "payload path")
        assert path not in indexed, f"duplicate payload path: {path}"
        assert _sha(row.get("sha256"), "payload digest") == checksums[path]
        assert _integer(row.get("size"), "payload size") == len(files[path])
        category = _text(row.get("category"), "payload category")
        assert _CATEGORY.fullmatch(category), "payload category"
        _text(row.get("media_type"), "payload media type")
        indexed[path] = row
    assert set(indexed) == set(files) - {_MANIFEST_PATH, _CHECKSUM_PATH}, (
        "payload index is not exhaustive"
    )
    return indexed


def _file_evidence(
    raw: object,
    *,
    kind: str,
    files: Mapping[str, bytes],
    checksums: Mapping[str, str],
    payload_index: Mapping[str, Mapping[str, object]],
) -> _FileEvidence:
    record = _mapping(raw, kind)
    path = _safe_relative(record.get("path"), f"{kind} path")
    digest = _sha(record.get("sha256"), f"{kind} digest")
    assert path in files and checksums[path] == digest and files[path], kind
    row = payload_index[path]
    media_type = _text(record.get("media_type"), f"{kind} media type")
    assert row.get("media_type") == media_type
    return _FileEvidence(
        kind,
        path,
        digest,
        media_type,
        _ref(record.get("artifact_ref"), f"{kind} Artifact ref"),
        _ref(record.get("content_ref"), f"{kind} ContentRef"),
    )


def _decode_png(payload: bytes, record: Mapping[str, object], label: str) -> None:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n"), f"{label} is not PNG"
    assert len(payload) >= 24 and payload[12:16] == b"IHDR", f"{label} lacks IHDR"
    width = int.from_bytes(payload[16:20], "big")
    height = int.from_bytes(payload[20:24], "big")
    assert 0 < width <= _MAX_IMAGE_EDGE and 0 < height <= _MAX_IMAGE_EDGE
    assert width * height <= _MAX_IMAGE_PIXELS
    with Image.open(BytesIO(payload)) as probe:
        assert probe.format == "PNG", label
        probe.verify()
    validation = _mapping(record.get("decode"), f"{label} decode")
    assert validation.get("verified") is True
    assert validation.get("format") == "PNG"
    assert _integer(validation.get("width"), "preview width", minimum=1) == width
    assert _integer(validation.get("height"), "preview height", minimum=1) == height


def _segment_pairs(value: object, label: str) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for raw in _sequence(value, label):
        pair = _sequence(raw, label)
        assert len(pair) == 2
        pairs.append(
            (
                _integer(pair[0], f"{label} start", minimum=1),
                _integer(pair[1], f"{label} end", minimum=1),
            )
        )
    return tuple(pairs)


def _record_paths(
    manifest: Mapping[str, object], files: Mapping[str, bytes]
) -> Mapping[str, str]:
    raw = _mapping(manifest.get("records"), "record paths")
    assert set(raw) == _RECORD_NAMES, "record names differ"
    normalized = {
        name: _safe_relative(raw[name], f"{name} record path")
        for name in sorted(raw)
    }
    assert len(set(normalized.values())) == len(normalized)
    assert all(path in files and path.endswith(".json") for path in normalized.values())
    return normalized


def _validate_full_contract(
    manifest: Mapping[str, object],
    *,
    files: Mapping[str, bytes],
    checksums: Mapping[str, str],
    payload_index: Mapping[str, Mapping[str, object]],
    source: Mapping[str, object],
    identity: Mapping[str, str],
    project_ref: str,
    task_contract_sha256: str,
    kpis: Mapping[str, int],
) -> tuple[
    _FileEvidence,
    _FileEvidence,
    tuple[_FileEvidence, ...],
    _FileEvidence,
    _FileEvidence,
    Mapping[str, str],
    Mapping[str, Mapping[str, object]],
]:
    scene = _file_evidence(
        manifest.get("scene"),
        kind="scene",
        files=files,
        checksums=checksums,
        payload_index=payload_index,
    )
    assert scene.artifact_ref == identity["scene_ref"]
    assert scene.sha256 == identity["scene_sha256"]
    assert scene.media_type == "application/x-blender"
    assert files[scene.logical_path].startswith(b"BLENDER"), "scene is not Blender"

    specification = _file_evidence(
        manifest.get("specification"),
        kind="specification",
        files=files,
        checksums=checksums,
        payload_index=payload_index,
    )
    assert specification.artifact_ref == identity["specification_ref"]
    assert specification.sha256 == identity["specification_sha256"]
    spec = _parse_json(files[specification.logical_path], source=specification.logical_path)
    assert spec.get("schema") == "minitz.p3-10.simulation-specification/v1"
    assert spec.get("project_ref") == project_ref
    assert spec.get("task_contract_sha256") == task_contract_sha256
    assert spec.get("scene_ref") == identity["scene_ref"]
    assert spec.get("scene_sha256") == identity["scene_sha256"]
    assert spec.get("generator_ref") == identity["generator_ref"]
    assert spec.get("tool_ref") == identity["tool_ref"]
    assert spec.get("runtime_ref") == identity["runtime_ref"]
    assert spec.get("solver_ref") == identity["solver_ref"]
    assert _integer(spec.get("frame_start"), "frame start", minimum=1) == 1
    assert _integer(spec.get("frame_end"), "frame end", minimum=1) == 300
    assert spec.get("deterministic") is True

    checkpoints: list[_FileEvidence] = []
    checkpoint_rows = _sequence(manifest.get("checkpoints"), "checkpoints")
    assert len(checkpoint_rows) == 3
    for expected, raw in zip(_SEGMENTS, checkpoint_rows, strict=True):
        row = _mapping(raw, "checkpoint")
        assert (
            _integer(row.get("frame_start"), "checkpoint start", minimum=1),
            _integer(row.get("frame_end"), "checkpoint end", minimum=1),
        ) == expected
        assert row.get("status") == "VERIFIED"
        assert row.get("project_ref") == project_ref
        assert row.get("specification_sha256") == identity["specification_sha256"]
        _text(row.get("producer_attempt_id"), "checkpoint attempt")
        _integer(row.get("producer_fence"), "checkpoint fence", minimum=1)
        checkpoints.append(
            _file_evidence(
                row,
                kind=f"checkpoint-{expected[1]}",
                files=files,
                checksums=checksums,
                payload_index=payload_index,
            )
        )
    assert len({item.sha256 for item in checkpoints}) == 3

    bake_raw = _mapping(manifest.get("bake"), "bake")
    bake = _file_evidence(
        bake_raw,
        kind="bake",
        files=files,
        checksums=checksums,
        payload_index=payload_index,
    )
    assert bake_raw.get("status") == "VERIFIED" and bake_raw.get("complete") is True
    assert bake_raw.get("project_ref") == project_ref
    assert bake_raw.get("specification_sha256") == identity["specification_sha256"]
    assert tuple(_sequence(bake_raw.get("checkpoint_sha256"), "bake checkpoints")) == tuple(
        item.sha256 for item in checkpoints
    )

    preview_raw = _mapping(manifest.get("preview"), "preview")
    preview = _file_evidence(
        preview_raw,
        kind="preview",
        files=files,
        checksums=checksums,
        payload_index=payload_index,
    )
    assert preview_raw.get("status") == "VERIFIED"
    assert preview_raw.get("project_ref") == project_ref
    assert preview_raw.get("scene_ref") == identity["scene_ref"]
    assert preview_raw.get("scene_sha256") == identity["scene_sha256"]
    assert preview_raw.get("specification_sha256") == identity["specification_sha256"]
    assert preview_raw.get("bake_artifact_ref") == bake.artifact_ref
    assert preview_raw.get("bake_sha256") == bake.sha256
    assert preview_raw.get("executor_ref") == identity["executor_ref"]
    _decode_png(files[preview.logical_path], preview_raw, preview.logical_path)

    records = _record_paths(manifest, files)
    documents = {
        name: _parse_json(files[path], source=path) for name, path in records.items()
    }
    resource = documents["resource"]
    assert resource.get("schema") == "minitz.p3-10.resource-receipt/v1"
    assert resource.get("status") == "OBSERVED"
    assert resource.get("resource_ref") == identity["resource_ref"]
    assert checksums[records["resource"]] == identity["resource_sha256"]
    _ref(resource.get("provider_ref"), "resource provider")
    _ref(resource.get("host_ref"), "resource host")
    device_kind = _text(resource.get("device_kind"), "device kind")
    assert device_kind in {"cpu", "gpu"}
    _text(resource.get("device_id"), "device id")
    _text(resource.get("device_name"), "device name")
    _text(resource.get("driver_version"), "driver version")
    backend = _text(resource.get("compute_backend"), "compute backend")
    assert backend == "CPU" if device_kind == "cpu" else backend in {"CUDA", "OPTIX"}
    _integer(resource.get("memory_mib"), "resource memory", minimum=1)
    _text(resource.get("observed_at"), "resource observation time")

    process = documents["process"]
    assert process.get("schema") == "minitz.p3-10.real-process/v1"
    assert process.get("reality") == "REAL" and process.get("status") == "SUCCEEDED"
    assert process.get("exit_code") == 0
    assert process.get("source_commit") == source["commit"]
    assert process.get("source_tree") == source["tree"]
    assert process.get("resource_ref") == identity["resource_ref"]
    assert process.get("resource_sha256") == identity["resource_sha256"]
    assert "blender" in _text(process.get("executable"), "process executable").lower()
    _sha(process.get("command_sha256"), "process command digest")
    _integer(process.get("pid"), "process PID", minimum=1)
    _text(process.get("started_at"), "process start")
    _text(process.get("finished_at"), "process finish")

    failure = documents["failure"]
    assert failure.get("schema") == "minitz.p3-10.enospc-failure/v1"
    assert failure.get("status") == "FAILED"
    assert failure.get("failure_classification") == "RESOURCE_EXHAUSTED"
    reason = _text(failure.get("failure_reason"), "failure reason").lower()
    assert "enospc" in reason or "no space left" in reason
    failed_frame = _integer(failure.get("failed_frame"), "failed frame", minimum=1)
    assert 201 <= failed_frame <= 300
    assert failure.get("project_ref") == project_ref
    assert failure.get("specification_sha256") == identity["specification_sha256"]
    assert failure.get("resource_ref") == identity["resource_ref"]
    stale_attempt_id = _text(failure.get("attempt_id"), "failed attempt")
    stale_fence = _integer(failure.get("fence"), "failed fence", minimum=1)

    recovery = documents["recovery"]
    assert recovery.get("schema") == "minitz.p3-10.enospc-recovery/v1"
    assert recovery.get("status") == "RECOVERED"
    assert recovery.get("project_ref") == project_ref
    assert recovery.get("specification_sha256") == identity["specification_sha256"]
    assert recovery.get("failure_record_sha256") == checksums[records["failure"]]
    assert _segment_pairs(recovery.get("preserved_segments"), "preserved segments") == _SEGMENTS[:2]
    assert _segment_pairs(recovery.get("resumed_segments"), "resumed segments") == _SEGMENTS[2:]
    assert tuple(
        _sha(value, "preserved checkpoint digest")
        for value in _sequence(
            recovery.get("preserved_checkpoint_sha256"), "preserved checkpoint digests"
        )
    ) == tuple(item.sha256 for item in checkpoints[:2])
    assert recovery.get("resumed_checkpoint_sha256") == checkpoints[2].sha256
    assert _integer(recovery.get("resume_dispatch_start"), "resume start", minimum=1) == 201
    assert _integer(recovery.get("resume_dispatch_end"), "resume end", minimum=1) == 300
    assert recovery.get("cache_authority") == "REBUILDABLE_ONLY"
    assert recovery.get("stale_attempt_rejected") is True
    assert recovery.get("stale_attempt_id") == stale_attempt_id
    assert _integer(recovery.get("stale_fence"), "stale fence", minimum=1) == stale_fence
    recovered_attempt_id = _text(recovery.get("recovered_attempt_id"), "recovered attempt")
    assert recovered_attempt_id != stale_attempt_id
    assert _integer(recovery.get("recovered_fence"), "recovered fence", minimum=1) == stale_fence + 1
    assert _integer(recovery.get("verified_segments_lost"), "segments lost") == 0
    assert _integer(recovery.get("completed_frames_rerendered"), "frames rerendered") == 0

    concurrency = documents["concurrency"]
    assert concurrency.get("schema") == "minitz.p3-10.effect-concurrency/v1"
    assert concurrency.get("status") == "SUCCEEDED"
    assert concurrency.get("independent_overlap_observed") is True
    assert _integer(
        concurrency.get("observed_global_max_active_effects"),
        "global active effects",
        minimum=2,
    ) >= 2
    effects = _sequence(concurrency.get("effects"), "effects")
    assert len(effects) == 2
    effect_ids: set[str] = set()
    effect_specs: set[str] = set()
    for raw in effects:
        effect = _mapping(raw, "effect")
        effect_ids.add(_text(effect.get("effect_id"), "effect id"))
        effect_specs.add(_sha(effect.get("specification_sha256"), "effect spec"))
        assert _segment_pairs(effect.get("segments"), "effect segments") == _SEGMENTS
        assert _integer(
            effect.get("internal_max_active_segments"), "effect serial maximum", minimum=1
        ) == 1
        assert effect.get("dependency_order_verified") is True
    assert len(effect_ids) == 2 and len(effect_specs) == 2
    assert identity["specification_sha256"] in effect_specs

    cache = documents["cache_rebuild"]
    assert cache.get("schema") == "minitz.p3-10.cache-deletion-survival/v1"
    assert cache.get("status") == "PASSED"
    assert cache.get("cache_deleted") is True
    assert cache.get("artifact_replay_after_deletion") is True
    assert cache.get("cache_used_as_only_authority") is False
    assert tuple(_sequence(cache.get("checkpoint_sha256_before"), "cache before")) == tuple(
        item.sha256 for item in checkpoints
    )
    assert cache.get("checkpoint_sha256_after") == cache.get("checkpoint_sha256_before")
    assert cache.get("bake_sha256_before") == bake.sha256
    assert cache.get("bake_sha256_after") == bake.sha256

    render_handoff = documents["render_handoff"]
    assert render_handoff.get("schema") == "minitz.p3-10.render-handoff/v1"
    assert render_handoff.get("status") == "SUCCEEDED"
    assert render_handoff.get("project_ref") == project_ref
    assert render_handoff.get("specification_sha256") == identity["specification_sha256"]
    assert render_handoff.get("bake_artifact_ref") == bake.artifact_ref
    assert render_handoff.get("bake_sha256") == bake.sha256
    assert render_handoff.get("preview_artifact_ref") == preview.artifact_ref
    assert render_handoff.get("preview_sha256") == preview.sha256
    assert render_handoff.get("exact_identity_binding") is True

    game_handoff = documents["game_handoff"]
    assert game_handoff.get("schema") == "minitz.p3-10.game-handoff/v1"
    assert game_handoff.get("status") == "SUCCEEDED"
    assert game_handoff.get("project_ref") == project_ref
    assert game_handoff.get("scene_ref") == identity["scene_ref"]
    assert game_handoff.get("scene_sha256") == identity["scene_sha256"]
    assert game_handoff.get("specification_sha256") == identity["specification_sha256"]
    assert game_handoff.get("bake_artifact_ref") == bake.artifact_ref
    assert game_handoff.get("bake_sha256") == bake.sha256
    assert game_handoff.get("exact_identity_binding") is True
    assert game_handoff.get("forged_input_rejected") is True

    integration = documents["integration"]
    assert integration.get("schema") == "minitz.p3-10.integration-manifest/v1"
    assert integration.get("reality") == "REAL" and integration.get("status") == "SUCCEEDED"
    assert integration.get("project_ref") == project_ref
    assert integration.get("task_contract_sha256") == task_contract_sha256
    assert integration.get("source_commit") == source["commit"]
    assert integration.get("source_tree") == source["tree"]
    assert integration.get("scene_sha256") == identity["scene_sha256"]
    assert integration.get("specification_sha256") == identity["specification_sha256"]
    assert integration.get("bake_sha256") == bake.sha256
    assert integration.get("preview_sha256") == preview.sha256
    assert _mapping(integration.get("kpis"), "integration KPIs") == kpis
    assert _integer(integration.get("unresolved_failures"), "integration failures") == 0
    record_digests = _mapping(integration.get("record_sha256"), "record digests")
    expected_record_digests = {
        name: checksums[path]
        for name, path in records.items()
        if name != "integration"
    }
    expected_record_digests["integration"] = _integration_record_digest(integration)
    assert record_digests == expected_record_digests
    integration_path = records["integration"]
    assert checksums[integration_path] == hashlib.sha256(files[integration_path]).hexdigest()

    return (
        scene,
        specification,
        tuple(checkpoints),
        bake,
        preview,
        records,
        documents,
    )


def _discover_package(package_value: str | Path) -> _SimulationPackage:
    package_path = _regular_package_path(package_value)
    package_payload = package_path.read_bytes()
    assert 0 < len(package_payload) <= _MAX_PACKAGE_BYTES
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=BytesIO(package_payload), mode="r:*") as archive:
        members = archive.getmembers()
        assert 0 < len(members) <= _MAX_MEMBERS
        uncompressed = 0
        seen: set[str] = set()
        for member in members:
            parsed = PurePosixPath(member.name)
            normalized = member.name.rstrip("/")
            assert member.name and not parsed.is_absolute() and ".." not in parsed.parts, (
                "unsafe archive member"
            )
            assert normalized == parsed.as_posix(), "unsafe archive member"
            assert normalized not in seen, "duplicate archive member"
            seen.add(normalized)
            assert member.isfile() or member.isdir(), (
                "archive members must be regular files or directories"
            )
            if not member.isfile():
                continue
            assert 0 <= member.size <= _MAX_PACKAGE_BYTES
            uncompressed += member.size
            assert uncompressed <= _MAX_UNCOMPRESSED_BYTES
            stream = archive.extractfile(member)
            assert stream is not None
            payload = stream.read()
            assert len(payload) == member.size
            files[member.name] = payload

    assert _MANIFEST_PATH in files and _CHECKSUM_PATH in files
    checksums = _checksum_lines(files[_CHECKSUM_PATH], source=_CHECKSUM_PATH)
    assert set(checksums) == set(files) - {_CHECKSUM_PATH}, (
        "checksum manifest is not exhaustive"
    )
    for path, digest in checksums.items():
        assert hashlib.sha256(files[path]).hexdigest() == digest, (
            f"forged package member: {path}"
        )

    manifest = _parse_json(files[_MANIFEST_PATH], source=_MANIFEST_PATH)
    assert manifest.get("schema") == _SCHEMA
    source = _source_identity(manifest, files)
    payload_index = _payload_index(manifest, files, checksums)
    assert _integer(manifest.get("unresolved_failures"), "unresolved failures") == 0
    kpis = _zero_kpis(manifest)
    project_ref = _ref(manifest.get("project_ref"), "retained project ref")
    task_contract_sha256 = _sha(
        manifest.get("task_contract_sha256"), "Task contract digest"
    )
    identity = _identity(manifest)
    (
        scene,
        specification,
        checkpoints,
        bake,
        preview,
        records,
        documents,
    ) = _validate_full_contract(
        manifest,
        files=files,
        checksums=checksums,
        payload_index=payload_index,
        source=source,
        identity=identity,
        project_ref=project_ref,
        task_contract_sha256=task_contract_sha256,
        kpis=kpis,
    )

    retained = [
        _RetainedEvidence(
            f"retained-package/{package_path.name}",
            "package",
            package_payload,
            _media_type(package_path.name),
        ),
        _RetainedEvidence(
            _CHECKSUM_PATH,
            "checksum",
            files[_CHECKSUM_PATH],
            "text/plain",
        ),
        _RetainedEvidence(
            _MANIFEST_PATH,
            "manifest",
            files[_MANIFEST_PATH],
            "application/json",
        ),
    ]
    retained.extend(
        _RetainedEvidence(
            path,
            cast(str, payload_index[path]["category"]),
            files[path],
            cast(str, payload_index[path]["media_type"]),
        )
        for path in sorted(payload_index)
    )
    return _SimulationPackage(
        tuple(retained),
        source,
        project_ref,
        task_contract_sha256,
        identity,
        scene,
        specification,
        checkpoints,
        bake,
        preview,
        records,
        documents,
        kpis,
    )


def _quantity(value: float, source: QuantitySource) -> ResourceQuantity:
    return ResourceQuantity(
        value,
        "count",
        source,
        "resource-source://p3-10/durable-evidence/slots",
    )


def _register_resource(
    database: Path,
    access: ProjectAccess,
    retained_project_ref: str,
    external_resource_ref: str,
) -> ResourceRef:
    resource_ref = ResourceRef(
        access.project_ref,
        "res_" + hashlib.sha256(retained_project_ref.encode()).hexdigest()[:32],
    )
    resources = ResourceService(database)
    resources.register_resource(
        access,
        Resource(
            resource_ref,
            "runtime.compute",
            external_resource_ref,
            configured_capacity={"slots": _quantity(2.0, QuantitySource.CONFIGURED)},
        ),
    )
    resources.observe_resource(
        access,
        resource_ref,
        FakeResourceObserver(
            (
                ResourceObservation(
                    observed_at=_now(),
                    fresh_for_seconds=1800,
                    health=ResourceHealth.HEALTHY,
                    physical_capacity={"slots": _quantity(2.0, QuantitySource.MEASURED)},
                    effective_capacity={"slots": _quantity(2.0, QuantitySource.MEASURED)},
                    used_capacity={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                    available_capacity={"slots": _quantity(2.0, QuantitySource.MEASURED)},
                    pressure={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                ),
            )
        ),
    )
    return resource_ref


def _publish(
    evidence: _RetainedEvidence,
    *,
    artifacts: ArtifactService,
    objects: FilesystemObjectStorageBackend,
    access: ProjectAccess,
    run_attempt: ExecutionAttempt,
    task: Task,
    sources: Sequence[Artifact],
) -> Artifact:
    content_ref = objects.put(
        evidence.payload,
        media_type=evidence.media_type,
        expected_digest=evidence.sha256,
        expected_size=len(evidence.payload),
    )
    assert content_ref == ContentRef.from_bytes(
        evidence.payload, media_type=evidence.media_type
    )
    return artifacts.publish_from_run(
        access,
        producer_attempt=run_attempt,
        expected_task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        role=_engine_artifact_role(evidence.category),
        content_ref=content_ref,
        source_refs=(),
        source_artifact_refs=tuple(source.artifact_ref for source in sources),
        source_content_refs=tuple(
            cast(ContentRef, source.content_ref) for source in sources
        ),
        derivation_type=(
            "vfx.captured-real-evidence"
            if evidence.category == "package"
            else "vfx.extracted-retained-package"
        ),
        metadata={"semantic_label": evidence.logical_path},
    )


def _output_target() -> Path:
    value = os.environ.get("MINITZ_P3_10_EVIDENCE_OUT")
    return (
        Path(value).expanduser()
        if value
        else Path("/root/minitz/evidence/p3-10/P3_10_ENGINE_EVIDENCE.json")
    )


def _import_engine_evidence(
    package: _SimulationPackage,
    package_path: Path,
    tmp_path: Path,
) -> Mapping[str, object]:
    commit = cast(str, package.source["commit"])
    tree = cast(str, package.source["tree"])
    database = tmp_path / "p3-10-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("vfx.validate", "1.0.0")
    output_contract = {
        "simulation_output": "schema://minitz/p3-10/simulation-output/1",
        "evidence_manifest": "schema://minitz/p3-10/durable-evidence/1",
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate exact retained REAL simulation and ENOSPC recovery evidence",
            output_contract=output_contract,
        )
    )
    registration = ProjectStore(database).create_project(
        namespace="p3-10-durable-evidence",
        display_name="P3-10 Durable VFX Evidence",
        metadata={
            "retained_project_ref": package.project_ref,
            "source_commit": commit,
            "source_tree": tree,
        },
    )
    access = registration.access
    project_ref = access.project_ref
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=project_ref,
        idempotency_key="p3-10-durable-evidence-task",
        task_type="vfx.durable-evidence",
        objective="Retain and validate exact REAL VFX outputs and ENOSPC recovery",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={"effect_branches": 2, "segments_per_branch": 3, "named_zero_kpis": 5},
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-10/retained-evidence",
        egress_policy_ref="policy://p3-10/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={"slots": 2},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-10/durable-evidence/run",
        lease_seconds=1800,
    )

    graph_ref = GraphRef.new(project_ref)
    branch_nodes: dict[tuple[str, int], Node] = {}
    ordered_nodes: list[Node] = []
    for branch in ("primary", "independent"):
        dependencies: tuple[NodeRef, ...] = ()
        for segment_index, _ in enumerate(_SEGMENTS, start=1):
            node = Node(
                NodeRef.new(graph_ref),
                "generic.vfx.simulation-segment-evidence",
                (capability_ref,),
                dependencies,
                (),
                output_contract,
                None,
                "READ_ONLY",
                {"slots": 1},
                ("artifact", "content-ref", "provenance", "runtime"),
            )
            branch_nodes[(branch, segment_index)] = node
            ordered_nodes.append(node)
            dependencies = (node.node_ref,)
    bake_node = Node(
        NodeRef.new(graph_ref),
        "generic.vfx.bake-evidence",
        (capability_ref,),
        (branch_nodes[("primary", 3)].node_ref,),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {"slots": 1},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    preview_node = Node(
        NodeRef.new(graph_ref),
        "generic.vfx.preview-evidence",
        (capability_ref,),
        (bake_node.node_ref,),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {"slots": 1},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    integration_node = Node(
        NodeRef.new(graph_ref),
        "generic.vfx.integration-manifest",
        (capability_ref,),
        (preview_node.node_ref, branch_nodes[("independent", 3)].node_ref),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {"slots": 1},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    graphs = GraphService(database)
    graph = graphs.create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(*ordered_nodes, bake_node, preview_node, integration_node),
        compiler_identity="compiler://p3-10/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    prepared = executions.prepare_run(access, run.run_ref)
    assert {item.node_ref for item in prepared if item.status == "READY"} == {
        branch_nodes[("primary", 1)].node_ref,
        branch_nodes[("independent", 1)].node_ref,
    }

    resource_ref = _register_resource(
        database,
        access,
        package.project_ref,
        package.identity["resource_ref"],
    )
    scheduler = Scheduler(database)

    def dispatch(label: str, node: Node, *, lease_seconds: float = 1800.0) -> ScheduledDispatch:
        allocation = scheduler.reserve(
            access,
            SchedulingRequest(
                node.node_ref,
                (
                    ResourceClaim(
                        resource_ref,
                        ResourceFitRequest(required_available={"slots": 1.0}),
                        requested_capacity={"slots": 1.0},
                    ),
                ),
                side_effect_targets=(f"evidence://p3-10/{label}",),
            ),
            authority_attempt=run_attempt,
            owner_ref=f"worker://p3-10/durable-evidence/{label}",
            lease_seconds=1800,
            idempotency_key=f"p3-10-{label}-reserve",
        )
        return scheduler.dispatch(
            access,
            allocation,
            authority_attempt=run_attempt,
            lease_seconds=lease_seconds,
            idempotency_key=f"p3-10-{label}-dispatch",
        )

    artifacts = ArtifactService(database)
    published: list[tuple[_RetainedEvidence, Artifact]] = []
    package_artifact: Artifact | None = None
    for evidence in package.retained:
        sources = () if package_artifact is None else (package_artifact,)
        artifact = _publish(
            evidence,
            artifacts=artifacts,
            objects=objects,
            access=access,
            run_attempt=run_attempt,
            task=task,
            sources=sources,
        )
        if package_artifact is None:
            package_artifact = artifact
        published.append((evidence, artifact))
    assert package_artifact is not None
    by_path = {evidence.logical_path: artifact for evidence, artifact in published}
    manifest_artifact = by_path[_MANIFEST_PATH]
    process_artifact = by_path[package.records["process"]]
    integration_artifact = by_path[package.records["integration"]]
    concurrency_artifact = by_path[package.records["concurrency"]]
    checkpoint_artifacts = tuple(by_path[item.logical_path] for item in package.checkpoints)
    bake_artifact = by_path[package.bake.logical_path]
    preview_artifact = by_path[package.preview.logical_path]
    for _, artifact in published:
        assert artifacts.get_artifact(access, artifact.artifact_ref) == artifact
        assert objects.verify(cast(ContentRef, artifact.content_ref)) is True

    def finalize(dispatched: ScheduledDispatch, artifact: Artifact, label: str) -> str:
        completed = executions.finalize_node(
            access,
            dispatched.node_attempt,
            outputs={
                "simulation_output": artifact.artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": artifact.artifact_ref,
                "content-ref": cast(ContentRef, artifact.content_ref),
                "provenance": package_artifact.artifact_ref,
                "runtime": process_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key=f"p3-10-{label}-finalize",
        )
        assert completed.status == "SUCCEEDED"
        released = scheduler.release(
            access,
            dispatched.allocation,
            outcome="COMPLETED",
            idempotency_key=f"p3-10-{label}-release",
        )
        assert released.status == "RELEASED"
        return completed.status

    dispatches: dict[tuple[str, int], ScheduledDispatch] = {}
    statuses: dict[tuple[str, int], str] = {}
    for segment_index in (1, 2):
        for branch in ("primary", "independent"):
            label = f"{branch}-segment-{segment_index}"
            dispatched = dispatch(label, branch_nodes[(branch, segment_index)])
            artifact = (
                checkpoint_artifacts[segment_index - 1]
                if branch == "primary"
                else concurrency_artifact
            )
            dispatches[(branch, segment_index)] = dispatched
            statuses[(branch, segment_index)] = finalize(dispatched, artifact, label)

    failed_node = branch_nodes[("primary", 3)]
    failed_dispatch = dispatch("primary-segment-3-enospc", failed_node, lease_seconds=0.02)
    expiry = datetime.fromisoformat(failed_dispatch.node_attempt.lease_expires_at)
    time.sleep(max(0.0, (expiry - datetime.now(timezone.utc)).total_seconds()) + 0.02)
    recovered_states = executions.recover_expired_execution(access, run.run_ref)
    assert {item.node_ref for item in recovered_states if item.status == "READY"} >= {
        failed_node.node_ref
    }
    history = executions.list_node_history(access, failed_node.node_ref)
    assert any(
        item.status == "STALE"
        and item.current_attempt_id == failed_dispatch.node_attempt.attempt_id
        for item in history
    )
    scheduler.recover_expired_allocations(access, project_ref)
    with pytest.raises(NodeExecutionAuthorityError):
        executions.finalize_node(
            access,
            failed_dispatch.node_attempt,
            outputs={
                "simulation_output": checkpoint_artifacts[2].artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": checkpoint_artifacts[2].artifact_ref,
                "content-ref": cast(ContentRef, checkpoint_artifacts[2].content_ref),
                "provenance": package_artifact.artifact_ref,
                "runtime": process_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key="p3-10-stale-finalize-rejected",
        )
    recovered_dispatch = dispatch("primary-segment-3-recovery", failed_node)
    assert recovered_dispatch.node_attempt.attempt_id != failed_dispatch.node_attempt.attempt_id
    assert recovered_dispatch.node_attempt.fence == failed_dispatch.node_attempt.fence + 1
    dispatches[("primary", 3)] = recovered_dispatch
    statuses[("primary", 3)] = finalize(
        recovered_dispatch, checkpoint_artifacts[2], "primary-segment-3-recovery"
    )

    independent_dispatch = dispatch(
        "independent-segment-3", branch_nodes[("independent", 3)]
    )
    dispatches[("independent", 3)] = independent_dispatch
    statuses[("independent", 3)] = finalize(
        independent_dispatch, concurrency_artifact, "independent-segment-3"
    )
    assert {item.node_ref for item in executions.prepare_run(access, run.run_ref) if item.status == "READY"} == {
        bake_node.node_ref
    }
    bake_dispatch = dispatch("bake", bake_node)
    bake_status = finalize(bake_dispatch, bake_artifact, "bake")
    preview_dispatch = dispatch("preview", preview_node)
    preview_status = finalize(preview_dispatch, preview_artifact, "preview")
    assert {item.node_ref for item in executions.prepare_run(access, run.run_ref) if item.status == "READY"} == {
        integration_node.node_ref
    }
    integration_dispatch = dispatch("integration", integration_node)

    validations = ValidationService(database)
    subjects = tuple(
        validations.bind_artifact_subject(
            access,
            artifact.artifact_ref,
            producer_dimensions={
                "content_ref": cast(ContentRef, artifact.content_ref).value,
                "resource": package.identity["resource_ref"],
                "scene": f"scene://sha256/{package.identity['scene_sha256']}",
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
                "specification": (
                    "specification://sha256/" + package.identity["specification_sha256"]
                ),
            },
        )
        for _, artifact in published
    )
    checks = tuple(
        ValidationCheck(
            capability_ref,
            True,
            "project.criteria:p3-10-vfx-kpi",
            ("artifact", "content_ref", "provenance"),
            (),
            {"expected": 0, "kpi": name},
        )
        for name in _KPI_NAMES
    )
    plan = validations.compile_plan(
        access,
        integration_dispatch.node_attempt,
        subjects=subjects,
        project_criteria=ProjectValidationCriteria(
            project_ref,
            checks,
            "criteria://p3-10/vfx-durable-evidence/v1",
        ),
        idempotency_key="p3-10-durable-evidence-validation-plan",
    )
    evidence_refs = tuple(
        [artifact.artifact_ref.value for _, artifact in published]
        + [cast(ContentRef, artifact.content_ref).value for _, artifact in published]
    )
    results = []
    kpi_result_names: set[str] = set()
    for check in plan.checks:
        kpi_name = check.parameters.get("kpi")
        metrics: tuple[MetricMeasurement, ...] = ()
        if isinstance(kpi_name, str):
            assert package.kpis[kpi_name] == 0
            metrics = (
                MetricMeasurement(
                    _engine_metric_name(kpi_name),
                    0.0,
                    "count",
                    f"Exact {kpi_name} violations in retained P3-10 REAL evidence",
                    integration_artifact.artifact_ref.value,
                ),
            )
        result = validations.record_result(
            access,
            integration_dispatch.node_attempt,
            plan.plan_ref,
            check_id=check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://p3-10/durable-evidence/v1",
            runtime_ref=package.identity["runtime_ref"],
            validator_dimensions={
                "resource": package.identity["resource_ref"],
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
                "specification": (
                    "specification://sha256/" + package.identity["specification_sha256"]
                ),
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-10-result-{check.check_id}",
        )
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
        if isinstance(kpi_name, str):
            kpi_result_names.add(kpi_name)
        results.append(result)
    assert kpi_result_names == set(_KPI_NAMES)
    aggregate = validations.aggregate(
        access,
        integration_dispatch.node_attempt,
        plan.plan_ref,
        idempotency_key="p3-10-durable-evidence-validation-aggregate",
    )
    assert aggregate.verdict is ValidationVerdict.PASS
    assert aggregate.accepted is True
    assert aggregate.evidence_state is ValidationEvidenceState.CURRENT
    assert aggregate.missing_required_check_ids == ()

    event = EventLedger(database).append_event(
        access,
        project_ref=project_ref,
        task_ref=task.task_ref,
        run_ref=run.run_ref,
        graph_ref=graph_ref,
        node_ref=integration_node.node_ref,
        event_type="P3_10_DURABLE_VFX_EVIDENCE_RETAINED",
        idempotency_key="p3-10-durable-vfx-evidence-retained",
        actor_ref="worker://p3-10/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for _, artifact in published),
        metadata={
            "artifact_count": len(published),
            "effect_branch_count": 2,
            "failed_attempt_id": failed_dispatch.node_attempt.attempt_id,
            "kpi_count": 5,
            "recovered_attempt_id": recovered_dispatch.node_attempt.attempt_id,
            "source_commit": commit,
            "source_tree": tree,
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
        },
        payload_ref=cast(ContentRef, integration_artifact.content_ref),
        authority_attempt=run_attempt,
    )
    acceptance = executions.record_run_acceptance(
        access,
        run.run_ref,
        criterion="validation.success_rule=ALL_REQUIRED_PASS",
        evidence_ref=integration_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-10-durable-evidence-acceptance",
    )
    integration_status = finalize(
        integration_dispatch, integration_artifact, "integration"
    )
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"
    assert graphs.get_graph(access, graph_ref) == graph
    scheduler.reconcile_terminal(access, run.run_ref)

    output: Mapping[str, object] = {
        "schema": _OUTPUT_SCHEMA,
        "source": {
            "commit": commit,
            "tree": tree,
            "overlay_count": package.source["overlay_count"],
            "overlays": list(cast(Sequence[object], package.source["overlays"])),
        },
        "retained_package": {
            "artifact_ref": package_artifact.artifact_ref.value,
            "content_ref": cast(ContentRef, package_artifact.content_ref).value,
            "path": str(package_path),
            "sha256": cast(ContentRef, package_artifact.content_ref).digest,
            "status": "VERIFIED",
        },
        "engine": {
            "project_ref": project_ref.value,
            "task_ref": {
                "project_ref": task.task_ref.project_ref.value,
                "task_id": task.task_ref.task_id,
                "revision": task.task_ref.revision,
            },
            "task_sha256": task.record_sha256,
            "run_ref": {
                "project_ref": run.run_ref.project_ref.value,
                "run_id": run.run_ref.run_id,
            },
            "run_state_sha256": completed_run.state_sha256,
            "run_status": completed_run.status,
            "graph_ref": graph.graph_ref.value,
            "graph_sha256": graph.record_sha256,
        },
        "identity": dict(package.identity),
        "branches": [
            {
                "allocation_ref": dispatches[(branch, segment_index)].allocation.allocation_ref.value,
                "attempt_id": dispatches[(branch, segment_index)].node_attempt.attempt_id,
                "branch": branch,
                "frame_end": _SEGMENTS[segment_index - 1][1],
                "frame_start": _SEGMENTS[segment_index - 1][0],
                "node_ref": branch_nodes[(branch, segment_index)].node_ref.value,
                "status": statuses[(branch, segment_index)],
            }
            for branch in ("primary", "independent")
            for segment_index in (1, 2, 3)
        ],
        "recovery": {
            "failed_allocation_ref": failed_dispatch.allocation.allocation_ref.value,
            "failed_attempt_id": failed_dispatch.node_attempt.attempt_id,
            "recovered_allocation_ref": recovered_dispatch.allocation.allocation_ref.value,
            "recovered_attempt_id": recovered_dispatch.node_attempt.attempt_id,
            "stale_finalize_rejected": True,
            "preserved_segments": [list(item) for item in _SEGMENTS[:2]],
            "resumed_segments": [list(item) for item in _SEGMENTS[2:]],
        },
        "bake": {
            "artifact_ref": bake_artifact.artifact_ref.value,
            "node_ref": bake_node.node_ref.value,
            "status": bake_status,
        },
        "preview": {
            "artifact_ref": preview_artifact.artifact_ref.value,
            "node_ref": preview_node.node_ref.value,
            "status": preview_status,
        },
        "integration": {
            "artifact_ref": integration_artifact.artifact_ref.value,
            "node_ref": integration_node.node_ref.value,
            "status": integration_status,
        },
        "kpis": dict(package.kpis),
        "validation": {
            "accepted": aggregate.accepted,
            "aggregate_sha256": aggregate.aggregate_sha256,
            "plan_ref": plan.plan_ref.value,
            "result_refs": [result.result_ref.value for result in results],
            "verdict": aggregate.verdict.value,
        },
        "event": {"event_ref": event.event_ref.value, "record_sha256": event.record_sha256},
        "acceptance_event_ref": acceptance.event_ref.value,
        "unresolved_failures": 0,
    }
    assert output["kpis"] == {name: 0 for name in _KPI_NAMES}
    target = _output_target()
    assert target.resolve(strict=False) != package_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert _parse_json(target.read_bytes(), source=str(target)) == output
    return output


def _canonical(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()


def _integration_record_digest(document: Mapping[str, object]) -> str:
    unsigned = dict(document)
    unsigned.pop("record_sha256", None)
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _engine_metric_name(prompt_kpi_name: str) -> str:
    assert prompt_kpi_name in _KPI_NAMES, "unknown P3-10 prompt KPI"
    return {
        "global_GPU_requirement_for_VFX": "global_gpu_requirement_for_vfx",
    }.get(prompt_kpi_name, prompt_kpi_name)


def _engine_artifact_role(retained_category: str) -> str:
    assert _CATEGORY.fullmatch(retained_category), "retained evidence category"
    role = f"vfx.{retained_category.replace('_', '-')}"
    assert _ENGINE_ROLE.fullmatch(role), "projected Engine Artifact role"
    return role


def _minimal_manifest(*, overlay_count: int = 0) -> Mapping[str, object]:
    return {
        "schema": _SCHEMA,
        "source": {
            "commit": "a" * 40,
            "tree": "b" * 40,
            "overlay_count": overlay_count,
            "overlays": [],
        },
        "payload": {"files": []},
        "prompt_kpis": {
            "schema": _KPI_SCHEMA,
            "all_five_zero": True,
            "kpis": {name: 0 for name in _KPI_NAMES},
        },
        "unresolved_failures": 0,
    }


def test_p3_10_integration_record_digest_is_constructible_and_archive_digest_is_full_bytes() -> None:
    process_payload = _canonical({"schema": "minitz.p3-10.real-process/v1"})
    unsigned: Mapping[str, object] = {
        "schema": "minitz.p3-10.integration-manifest/v1",
        "status": "SUCCEEDED",
    }
    integration_digest = _integration_record_digest(unsigned)
    stored: Mapping[str, object] = {
        **unsigned,
        "record_sha256": {
            "integration": integration_digest,
            "process": hashlib.sha256(process_payload).hexdigest(),
        },
    }

    assert _integration_record_digest(stored) == integration_digest
    assert stored["record_sha256"] == {
        "integration": integration_digest,
        "process": hashlib.sha256(process_payload).hexdigest(),
    }
    assert hashlib.sha256(_canonical(stored)).hexdigest() != integration_digest


def test_p3_10_engine_metric_name_projection_preserves_exact_prompt_kpis() -> None:
    assert {name: _engine_metric_name(name) for name in _KPI_NAMES} == {
        "simulation_cache_used_as_only_authority": "simulation_cache_used_as_only_authority",
        "verified_segments_lost_after_failure": "verified_segments_lost_after_failure",
        "incompatible_checkpoint_resumes": "incompatible_checkpoint_resumes",
        "dependent_solver_steps_parallelized_incorrectly": "dependent_solver_steps_parallelized_incorrectly",
        "global_GPU_requirement_for_VFX": "global_gpu_requirement_for_vfx",
    }


def test_p3_10_engine_artifact_role_projects_only_invalid_category_characters() -> None:
    assert {
        category: _engine_artifact_role(category)
        for category in (
            "bake",
            "checkpoint",
            "contracts",
            "handoff",
            "inputs",
            "preview",
            "record",
            "runtime_log",
            "specification",
        )
    } == {
        "bake": "vfx.bake",
        "checkpoint": "vfx.checkpoint",
        "contracts": "vfx.contracts",
        "handoff": "vfx.handoff",
        "inputs": "vfx.inputs",
        "preview": "vfx.preview",
        "record": "vfx.record",
        "runtime_log": "vfx.runtime-log",
        "specification": "vfx.specification",
    }


def _write_test_archive(
    path: Path,
    files: Mapping[str, bytes],
    *,
    symlink: tuple[str, str] | None = None,
) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            archive.addfile(info, BytesIO(payload))
        if symlink is not None:
            name, target = symlink
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)


def test_p3_10_retained_package_rejects_unsafe_archive_boundaries(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    _write_test_archive(
        archive_path,
        {_MANIFEST_PATH: b"{}"},
        symlink=("evidence/escape", "../../outside"),
    )
    with pytest.raises(AssertionError, match="regular files"):
        _discover_package(archive_path)
    symlink_path = tmp_path / "package-link.tar.gz"
    symlink_path.symlink_to(archive_path)
    with pytest.raises(AssertionError, match="regular file"):
        _discover_package(symlink_path)


@pytest.mark.parametrize("case", ("forged", "unlisted"))
def test_p3_10_retained_package_rejects_tamper(tmp_path: Path, case: str) -> None:
    manifest_payload = _canonical(_minimal_manifest())
    checksums = f"{'0' * 64}  {_MANIFEST_PATH}\n".encode()
    files = {_MANIFEST_PATH: manifest_payload, _CHECKSUM_PATH: checksums}
    if case == "unlisted":
        digest = hashlib.sha256(manifest_payload).hexdigest()
        files[_CHECKSUM_PATH] = f"{digest}  {_MANIFEST_PATH}\n".encode()
        files["evidence/unlisted.bin"] = b"not checksummed"
    archive_path = tmp_path / f"{case}.tar.gz"
    _write_test_archive(archive_path, files)
    match = "forged package member" if case == "forged" else "not exhaustive"
    with pytest.raises(AssertionError, match=match):
        _discover_package(archive_path)


def test_p3_10_retained_package_rejects_stale_source_identity(tmp_path: Path) -> None:
    manifest_payload = _canonical(_minimal_manifest(overlay_count=1))
    archive_path = tmp_path / "stale.tar.gz"
    _write_test_archive(
        archive_path,
        {
            _MANIFEST_PATH: manifest_payload,
            _CHECKSUM_PATH: (
                f"{hashlib.sha256(manifest_payload).hexdigest()}  {_MANIFEST_PATH}\n"
            ).encode(),
        },
    )
    with pytest.raises(AssertionError, match="stale source overlay count"):
        _discover_package(archive_path)


def test_p3_10_durable_evidence_rejects_cross_project_artifact(tmp_path: Path) -> None:
    database = tmp_path / "scope.sqlite3"
    projects = ProjectStore(database)
    alpha = projects.create_project(namespace="p3-10-alpha", display_name="Alpha")
    beta = projects.create_project(namespace="p3-10-beta", display_name="Beta")
    objects = FilesystemObjectStorageBackend(tmp_path / "scope-objects")
    content = objects.put(b"p3-10", media_type="application/octet-stream")
    artifacts = ArtifactService(database)
    artifact = artifacts.create_artifact(
        alpha.access,
        project_ref=alpha.access.project_ref,
        role="vfx.retained-package",
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(content,),
        derivation_type="vfx.scope-fixture",
        metadata={},
    )
    with pytest.raises(ArtifactScopeError):
        artifacts.get_artifact(beta.access, artifact.artifact_ref)


def test_p3_10_retained_real_package_becomes_durable_engine_evidence(tmp_path: Path) -> None:
    package_value = os.environ.get("MINITZ_P3_10_RETAINED_PACKAGE")
    if not package_value:
        pytest.skip("MINITZ_P3_10_RETAINED_PACKAGE is not configured")
    package_path = Path(package_value).expanduser()
    package = _discover_package(package_path)
    imported = _import_engine_evidence(package, package_path, tmp_path)
    assert imported["schema"] == _OUTPUT_SCHEMA
    assert imported["kpis"] == {name: 0 for name in _KPI_NAMES}
    assert imported["unresolved_failures"] == 0
