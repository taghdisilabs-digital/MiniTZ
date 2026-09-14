"""Durable Engine evidence importer for retained REAL P3-09 renders."""

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
from minitz_os.engine.execution import NodeExecutionService
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


_SCHEMA = "minitz.p3-09.retained-real-evidence/v1"
_KPI_SCHEMA = "minitz.p3-09.prompt-kpis/v1"
_OUTPUT_SCHEMA = "minitz.p3-09.durable-engine-evidence/v1"
_KPI_NAMES = (
    "renderer_specific_kernel_fields",
    "verified_frames_lost_after_failure",
    "completed_frames_rerendered_due_only_to_restart",
    "mixed_scene_versions_in_sequence",
    "render_claimed_success_with_missing_output",
)
_FRAMES = (1, 2, 3)
_PASSES = ("beauty", "z", "normal")
_MANIFEST_PATH = "evidence/manifest.json"
_CHECKSUM_PATH = "evidence/manifest.sha256"
_OVERLAY_CHECKSUM_PATH = "evidence/overlay-files.sha256"
_MAX_PACKAGE_BYTES = 512 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
_MAX_MEMBERS = 4096
_MAX_JSON_BYTES = 32 * 1024 * 1024
_MAX_IMAGE_EDGE = 8192
_MAX_IMAGE_PIXELS = 64 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}")
_GIT_OBJECT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")


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
class _OutputEvidence:
    kind: str
    frame: int
    pass_name: str
    logical_path: str
    sha256: str
    width: int
    height: int
    channels: tuple[str, ...]
    renderer_ref: str
    runtime_ref: str

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.kind, self.frame, self.pass_name)

    @property
    def sequence_key(self) -> tuple[int, str]:
        return (self.frame, self.pass_name)


@dataclass(frozen=True)
class _RenderPackage:
    retained: tuple[_RetainedEvidence, ...]
    source: Mapping[str, object]
    identity: Mapping[str, object]
    project_ref: str
    task_contract_sha256: str
    outputs: tuple[_OutputEvidence, ...]
    recovery: Mapping[str, object]
    kpis: Mapping[str, int]
    paths: Mapping[str, str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _parse_json(payload: bytes, *, source: str) -> Mapping[str, object]:
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
    assert isinstance(value, str) and value and len(value.encode()) <= 1024, label
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


def _identity(manifest: Mapping[str, object]) -> Mapping[str, object]:
    raw = _mapping(manifest.get("identity"), "render identity")
    normalized: dict[str, object] = {
        "scene_ref": _ref(raw.get("scene_ref"), "scene ref"),
        "scene_sha256": _sha(raw.get("scene_sha256"), "scene digest"),
        "camera_ref": _ref(raw.get("camera_ref"), "camera ref"),
        "camera_sha256": _sha(raw.get("camera_sha256"), "camera digest"),
        "preview_config_ref": _ref(
            raw.get("preview_config_ref"), "preview config ref"
        ),
        "preview_config_sha256": _sha(
            raw.get("preview_config_sha256"), "preview config digest"
        ),
        "final_config_ref": _ref(raw.get("final_config_ref"), "final config ref"),
        "final_config_sha256": _sha(
            raw.get("final_config_sha256"), "final config digest"
        ),
        "renderer_a_ref": _ref(raw.get("renderer_a_ref"), "renderer A ref"),
        "renderer_b_ref": _ref(raw.get("renderer_b_ref"), "renderer B ref"),
        "runtime_a_ref": _ref(raw.get("runtime_a_ref"), "runtime A ref"),
        "runtime_b_ref": _ref(raw.get("runtime_b_ref"), "runtime B ref"),
        "executor_ref": _ref(raw.get("executor_ref"), "executor ref"),
    }
    assert normalized["preview_config_ref"] != normalized["final_config_ref"]
    assert normalized["preview_config_sha256"] != normalized["final_config_sha256"]
    assert normalized["renderer_a_ref"] != normalized["renderer_b_ref"]
    device = _mapping(raw.get("device"), "device identity")
    normalized_device: dict[str, object] = {
        "device_ref": _ref(device.get("device_ref"), "device ref"),
        "device_id": _text(device.get("device_id"), "device id"),
        "device_kind": _text(device.get("device_kind"), "device kind"),
        "device_name": _text(device.get("device_name"), "device name"),
        "device_uuid": _text(device.get("device_uuid"), "device UUID"),
        "driver_version": _text(device.get("driver_version"), "driver version"),
        "compute_backend": _text(
            device.get("compute_backend"), "compute backend"
        ),
        "memory_mib": _integer(device.get("memory_mib"), "device memory", minimum=1),
    }
    device_kind = cast(str, normalized_device["device_kind"])
    device_ref = cast(str, normalized_device["device_ref"])
    device_id = cast(str, normalized_device["device_id"])
    device_name = cast(str, normalized_device["device_name"])
    device_uuid = cast(str, normalized_device["device_uuid"])
    compute_backend = cast(str, normalized_device["compute_backend"])
    assert device_kind in {"cpu", "gpu"}
    if device_kind == "gpu":
        assert device_uuid.startswith("GPU-")
        assert compute_backend in {"CUDA", "OPTIX"}
    else:
        identity_match = re.fullmatch(r"CPU-([0-9a-f]{64})", device_uuid)
        assert identity_match is not None, "CPU identity must be stable SHA-256"
        cpu_identity = identity_match.group(1)
        assert device_ref == f"device://cpu/sha256/{cpu_identity}"
        assert device_id == f"cpu:sha256:{cpu_identity}"
        assert compute_backend == "CPU"
        assert device_name == device_name.strip() and re.search(
            r"[A-Za-z0-9]", device_name
        )
        assert not {"GPU", "CUDA", "OPTIX"} & set(device_name.upper().split())
    device_sha256 = _sha(raw.get("device_sha256"), "device identity digest")
    assert device_sha256 == hashlib.sha256(_canonical(normalized_device)).hexdigest()
    normalized["device"] = normalized_device
    normalized["device_sha256"] = device_sha256
    return normalized


def _decode_png(
    payload: bytes, record: Mapping[str, object], label: str
) -> tuple[int, int, tuple[str, ...]]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n"), f"{label} is not PNG"
    assert len(payload) >= 24 and payload[12:16] == b"IHDR", f"{label} lacks IHDR"
    header_width = int.from_bytes(payload[16:20], "big")
    header_height = int.from_bytes(payload[20:24], "big")
    assert 0 < header_width <= _MAX_IMAGE_EDGE
    assert 0 < header_height <= _MAX_IMAGE_EDGE
    assert header_width * header_height <= _MAX_IMAGE_PIXELS
    with Image.open(BytesIO(payload)) as probe:
        assert probe.format == "PNG", label
        probe.verify()
    with Image.open(BytesIO(payload)) as decoded:
        decoded.load()
        width, height = decoded.size
        channels = tuple(decoded.getbands())
    assert (width, height) == (header_width, header_height)
    validation = _mapping(record.get("decode"), f"{label} decode")
    assert validation.get("verified") is True
    assert validation.get("format") == "PNG"
    assert _integer(validation.get("width"), f"{label} width", minimum=1) == width
    assert _integer(validation.get("height"), f"{label} height", minimum=1) == height
    expected_channels = tuple(
        _text(item, f"{label} channel")
        for item in _sequence(validation.get("channels"), f"{label} channels")
    )
    assert expected_channels and len(set(expected_channels)) == len(expected_channels)
    assert expected_channels == channels, f"{label} channels differ"
    return width, height, channels


def _output(
    raw: object,
    *,
    files: Mapping[str, bytes],
    checksums: Mapping[str, str],
    identity: Mapping[str, object],
    project_ref: str,
    task_contract_sha256: str,
) -> _OutputEvidence:
    record = _mapping(raw, "render output")
    kind = _text(record.get("kind"), "render output kind")
    frame = _integer(record.get("frame"), "render frame", minimum=1)
    pass_name = _text(record.get("pass"), "render pass")
    path = _safe_relative(record.get("path"), "render output path")
    digest = _sha(record.get("sha256"), "render output digest")
    assert path in files and checksums[path] == digest
    assert record.get("project_ref") == project_ref
    assert record.get("task_contract_sha256") == task_contract_sha256
    for field in ("scene_ref", "scene_sha256", "camera_ref", "camera_sha256"):
        assert record.get(field) == identity[field], (path, field)
    assert record.get("executor_ref") == identity["executor_ref"]
    assert record.get("device_sha256") == identity["device_sha256"]
    if kind == "preview":
        assert record.get("config_ref") == identity["preview_config_ref"]
        assert record.get("config_sha256") == identity["preview_config_sha256"]
        assert record.get("renderer_ref") == identity["renderer_b_ref"]
        assert record.get("runtime_ref") == identity["runtime_b_ref"]
    else:
        assert kind == "final"
        assert record.get("config_ref") == identity["final_config_ref"]
        assert record.get("config_sha256") == identity["final_config_sha256"]
        assert record.get("renderer_ref") == identity["renderer_a_ref"]
        assert record.get("runtime_ref") == identity["runtime_a_ref"]
    width, height, channels = _decode_png(files[path], record, path)
    if pass_name in {"beauty", "normal"}:
        assert {"R", "G", "B"} <= set(channels), path
    return _OutputEvidence(
        kind,
        frame,
        pass_name,
        path,
        digest,
        width,
        height,
        channels,
        cast(str, record["renderer_ref"]),
        cast(str, record["runtime_ref"]),
    )


def _record_paths(
    manifest: Mapping[str, object], files: Mapping[str, bytes]
) -> Mapping[str, str]:
    records = _mapping(manifest.get("records"), "record paths")
    assert set(records) == {"failure", "integration", "process", "sequence"}
    normalized = {
        name: _safe_relative(records[name], f"{name} record path")
        for name in sorted(records)
    }
    assert len(set(normalized.values())) == len(normalized)
    assert all(path in files and path.endswith(".json") for path in normalized.values())
    return normalized


def _validate_sequence(
    document: Mapping[str, object],
    outputs: Sequence[_OutputEvidence],
    identity: Mapping[str, object],
    project_ref: str,
    task_contract_sha256: str,
) -> None:
    assert document.get("schema") == "minitz.p3-09.render-sequence/v1"
    assert document.get("status") == "SUCCEEDED"
    assert document.get("project_ref") == project_ref
    assert document.get("task_contract_sha256") == task_contract_sha256
    for field in ("scene_ref", "scene_sha256", "camera_ref", "camera_sha256"):
        assert document.get(field) == identity[field]
    assert document.get("config_ref") == identity["final_config_ref"]
    assert document.get("config_sha256") == identity["final_config_sha256"]
    assert tuple(_sequence(document.get("frames"), "sequence frames")) == _FRAMES
    assert tuple(_sequence(document.get("passes"), "sequence passes")) == _PASSES
    completed: dict[tuple[int, str], tuple[str, str]] = {}
    for raw in _sequence(document.get("completed_outputs"), "completed outputs"):
        item = _mapping(raw, "completed output")
        key = (
            _integer(item.get("frame"), "completed frame", minimum=1),
            _text(item.get("pass"), "completed pass"),
        )
        assert key not in completed
        completed[key] = (
            _safe_relative(item.get("path"), "completed output path"),
            _sha(item.get("sha256"), "completed output digest"),
        )
    final_outputs = {item.sequence_key: item for item in outputs if item.kind == "final"}
    assert set(completed) == set(final_outputs)
    assert all(
        completed[key] == (item.logical_path, item.sha256)
        for key, item in final_outputs.items()
    )
    assert tuple(_sequence(document.get("failed_outputs"), "failed outputs")) == ()
    assert _integer(document.get("unresolved_failures"), "sequence failures") == 0


def _validate_recovery(
    recovery: Mapping[str, object],
    failure: Mapping[str, object],
    outputs: Sequence[_OutputEvidence],
) -> Mapping[str, object]:
    assert recovery.get("schema") == "minitz.p3-09.render-recovery/v1"
    assert recovery.get("status") == "RECOVERED"
    assert recovery.get("failure_mode") == "INJECTED_WORKER_LOSS"
    assert recovery.get("resume_compatible_only") is True
    assert recovery.get("prior_artifacts_unchanged") is True
    failed = _mapping(recovery.get("failed_output"), "failed output")
    failed_key = (
        _integer(failed.get("frame"), "failed frame", minimum=1),
        _text(failed.get("pass"), "failed pass"),
    )
    final_outputs = {item.sequence_key: item for item in outputs if item.kind == "final"}
    assert failed_key in final_outputs
    preserved: set[tuple[int, str]] = set()
    for raw in _sequence(recovery.get("preserved_outputs"), "preserved outputs"):
        item = _mapping(raw, "preserved output")
        key = (
            _integer(item.get("frame"), "preserved frame", minimum=1),
            _text(item.get("pass"), "preserved pass"),
        )
        assert key in final_outputs and key not in preserved and key != failed_key
        output = final_outputs[key]
        before_ref = _ref(item.get("before_artifact_ref"), "before artifact ref")
        after_ref = _ref(item.get("after_artifact_ref"), "after artifact ref")
        assert before_ref == after_ref
        before_sha = _sha(item.get("before_sha256"), "before artifact digest")
        after_sha = _sha(item.get("after_sha256"), "after artifact digest")
        assert before_sha == after_sha == output.sha256
        preserved.add(key)
    assert preserved == set(final_outputs) - {failed_key}
    resumed: set[tuple[int, str]] = set()
    for raw in _sequence(recovery.get("resume_executed_outputs"), "resume outputs"):
        item = _mapping(raw, "resume output")
        resumed.add(
            (
                _integer(item.get("frame"), "resume frame", minimum=1),
                _text(item.get("pass"), "resume pass"),
            )
        )
    assert resumed == {failed_key}, "resume executed more than the missing output"
    assert failure.get("schema") == "minitz.p3-09.worker-loss/v1"
    assert failure.get("injected") is True
    assert failure.get("status") == "WORKER_LOST"
    assert failure.get("output_published") is False
    assert failure.get("frame") == failed_key[0]
    assert failure.get("pass") == failed_key[1]
    assert _integer(failure.get("unresolved_failures"), "worker loss failures") == 0
    return {
        "failed_frame": failed_key[0],
        "failed_pass": failed_key[1],
        "preserved_count": len(preserved),
        "resume_executed_count": len(resumed),
    }


def _discover_package(package_value: str | Path) -> _RenderPackage:
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
    payload_rows = _sequence(
        _mapping(manifest.get("payload"), "payload").get("files"), "payload files"
    )
    indexed: dict[str, Mapping[str, object]] = {}
    for raw in payload_rows:
        row = _mapping(raw, "payload file")
        path = _safe_relative(row.get("path"), "payload path")
        assert path not in indexed
        indexed[path] = row
    assert set(indexed) == set(files) - {_MANIFEST_PATH, _CHECKSUM_PATH}
    for path, row in indexed.items():
        assert _sha(row.get("sha256"), "payload digest") == checksums[path]
        assert _integer(row.get("size"), "payload size") == len(files[path])

    assert _integer(manifest.get("unresolved_failures"), "unresolved failures") == 0
    kpis = _zero_kpis(manifest)
    project_ref = _ref(manifest.get("project_ref"), "retained project ref")
    task_contract_sha256 = _sha(
        manifest.get("task_contract_sha256"), "Task contract digest"
    )
    identity = _identity(manifest)
    outputs = tuple(
        _output(
            raw,
            files=files,
            checksums=checksums,
            identity=identity,
            project_ref=project_ref,
            task_contract_sha256=task_contract_sha256,
        )
        for raw in _sequence(manifest.get("outputs"), "render outputs")
    )
    expected_keys = {("preview", 1, "beauty")} | {
        ("final", frame, pass_name) for frame in _FRAMES for pass_name in _PASSES
    }
    assert {item.key for item in outputs} == expected_keys
    assert len(outputs) == len(expected_keys)
    final_sizes = {(item.width, item.height) for item in outputs if item.kind == "final"}
    assert len(final_sizes) == 1, "production dimensions differ"
    preview = next(item for item in outputs if item.kind == "preview")
    final_width, final_height = next(iter(final_sizes))
    assert preview.width <= final_width and preview.height <= final_height

    paths = _record_paths(manifest, files)
    documents = {
        name: _parse_json(files[path], source=path) for name, path in paths.items()
    }
    process = documents["process"]
    assert process.get("schema") == "minitz.p3-09.real-process/v1"
    assert process.get("reality") == "REAL"
    assert process.get("status") == "SUCCEEDED"
    assert process.get("exit_code") == 0
    assert process.get("source_commit") == source["commit"]
    assert process.get("source_tree") == source["tree"]
    assert process.get("device_sha256") == identity["device_sha256"]
    assert set(_sequence(process.get("renderer_refs"), "process renderers")) == {
        identity["renderer_a_ref"],
        identity["renderer_b_ref"],
    }
    assert _integer(process.get("unresolved_failures"), "process failures") == 0
    _validate_sequence(
        documents["sequence"], outputs, identity, project_ref, task_contract_sha256
    )
    recovery_raw = _mapping(manifest.get("recovery"), "recovery")
    assert recovery_raw.get("failure_record_path") == paths["failure"]
    recovery = _validate_recovery(recovery_raw, documents["failure"], outputs)

    replacement = _mapping(manifest.get("renderer_replacement"), "renderer replacement")
    assert replacement.get("task_contract_sha256") == task_contract_sha256
    assert replacement.get("task_unchanged") is True
    assert replacement.get("semantic_capability") == "render.frame"
    assert replacement.get("renderer_a_ref") == identity["renderer_a_ref"]
    assert replacement.get("renderer_b_ref") == identity["renderer_b_ref"]
    assert {item.renderer_ref for item in outputs} == {
        identity["renderer_a_ref"],
        identity["renderer_b_ref"],
    }

    integration = documents["integration"]
    assert integration.get("schema") == "minitz.p3-09.integration-manifest/v1"
    assert integration.get("status") == "SUCCEEDED"
    assert integration.get("project_ref") == project_ref
    assert integration.get("task_contract_sha256") == task_contract_sha256
    assert integration.get("renderer_a_ref") == identity["renderer_a_ref"]
    assert integration.get("renderer_b_ref") == identity["renderer_b_ref"]
    assert integration.get("task_unchanged") is True
    assert tuple(_sequence(integration.get("kernel_renderer_fields"), "kernel fields")) == ()
    assert integration.get("sequence_manifest_sha256") == checksums[paths["sequence"]]
    assert _mapping(integration.get("kpis"), "integration KPIs") == kpis
    assert _integer(integration.get("unresolved_failures"), "integration failures") == 0

    selected: dict[str, str] = {
        _CHECKSUM_PATH: "checksum",
        _MANIFEST_PATH: "manifest",
        **{path: name for name, path in paths.items()},
        **{item.logical_path: item.kind for item in outputs},
    }
    if _OVERLAY_CHECKSUM_PATH in files:
        selected[_OVERLAY_CHECKSUM_PATH] = "checksum"
    retained = [
        _RetainedEvidence(
            f"retained-package/{package_path.name}",
            "package",
            package_payload,
            _media_type(package_path.name),
        )
    ]
    retained.extend(
        _RetainedEvidence(path, selected[path], files[path], _media_type(path))
        for path in sorted(selected)
    )
    return _RenderPackage(
        tuple(retained),
        source,
        identity,
        project_ref,
        task_contract_sha256,
        outputs,
        recovery,
        kpis,
        paths,
    )


def _quantity(value: float, source: QuantitySource) -> ResourceQuantity:
    return ResourceQuantity(
        value,
        "count",
        source,
        "resource-source://p3-09/durable-evidence/slots",
    )


def _register_resource(
    database: Path,
    access: ProjectAccess,
    project_ref_value: str,
    device_ref: str,
) -> ResourceRef:
    resource_ref = ResourceRef(
        access.project_ref,
        "res_" + hashlib.sha256(project_ref_value.encode()).hexdigest()[:32],
    )
    resources = ResourceService(database)
    resources.register_resource(
        access,
        Resource(
            resource_ref,
            "runtime.gpu",
            device_ref,
            configured_capacity={
                "slots": _quantity(12.0, QuantitySource.CONFIGURED)
            },
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
                    physical_capacity={
                        "slots": _quantity(12.0, QuantitySource.MEASURED)
                    },
                    effective_capacity={
                        "slots": _quantity(12.0, QuantitySource.MEASURED)
                    },
                    used_capacity={
                        "slots": _quantity(0.0, QuantitySource.MEASURED)
                    },
                    available_capacity={
                        "slots": _quantity(12.0, QuantitySource.MEASURED)
                    },
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
        role=f"render.{evidence.category}",
        content_ref=content_ref,
        source_refs=(),
        source_artifact_refs=tuple(source.artifact_ref for source in sources),
        source_content_refs=tuple(
            cast(ContentRef, source.content_ref) for source in sources
        ),
        derivation_type=(
            "render.captured-real-evidence"
            if evidence.category == "package"
            else "render.extracted-retained-package"
        ),
        metadata={"semantic_label": evidence.logical_path},
    )


def _output_target() -> Path | None:
    value = os.environ.get("MINITZ_P3_09_EVIDENCE_OUT")
    return Path(value).expanduser() if value else None


def _import_engine_evidence(
    package: _RenderPackage,
    package_path: Path,
    tmp_path: Path,
) -> Mapping[str, object]:
    commit = cast(str, package.source["commit"])
    tree = cast(str, package.source["tree"])
    database = tmp_path / "p3-09-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("render.validate", "1.0.0")
    output_contract = {
        "render_output": "schema://minitz/p3-09/render-output/1",
        "evidence_manifest": "schema://minitz/p3-09/durable-evidence/1",
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate exact retained REAL rendering evidence",
            output_contract=output_contract,
        )
    )
    registration = ProjectStore(database).create_project(
        namespace="p3-09-durable-evidence",
        display_name="P3-09 Durable Rendering Evidence",
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
        idempotency_key="p3-09-durable-evidence-task",
        task_type="render.durable-evidence",
        objective="Retain and validate exact REAL render outputs and recovery",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={"expected_frame_pass_outputs": 9, "named_zero_kpis": 5},
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-09/retained-evidence",
        egress_policy_ref="policy://p3-09/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={"slots": 12},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-09/durable-evidence/run",
        lease_seconds=1800,
    )

    graph_ref = GraphRef.new(project_ref)
    preview_node = Node(
        NodeRef.new(graph_ref),
        "generic.render.preview-evidence",
        (capability_ref,),
        (),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {"slots": 1},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    frame_nodes = {
        (frame, pass_name): Node(
            NodeRef.new(graph_ref),
            "generic.render.frame-pass-evidence",
            (capability_ref,),
            (),
            (),
            output_contract,
            None,
            "READ_ONLY",
            {"slots": 1},
            ("artifact", "content-ref", "provenance", "runtime"),
        )
        for frame in _FRAMES
        for pass_name in _PASSES
    }
    recovery_node = Node(
        NodeRef.new(graph_ref),
        "generic.render.recovery-evidence",
        (capability_ref,),
        tuple(node.node_ref for node in frame_nodes.values()),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {"slots": 1},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    integration_node = Node(
        NodeRef.new(graph_ref),
        "generic.render.integration-manifest",
        (capability_ref,),
        (preview_node.node_ref, recovery_node.node_ref),
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
        nodes=(preview_node, *frame_nodes.values(), recovery_node, integration_node),
        compiler_identity="compiler://p3-09/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    prepared = executions.prepare_run(access, run.run_ref)
    ready = {item.node_ref for item in prepared if item.status == "READY"}
    assert ready == {preview_node.node_ref, *(node.node_ref for node in frame_nodes.values())}

    device = _mapping(package.identity["device"], "device identity")
    resource_ref = _register_resource(
        database,
        access,
        package.project_ref,
        cast(str, device["device_ref"]),
    )
    scheduler = Scheduler(database)

    def dispatch(
        label: str, node: Node, *, lease_seconds: float = 1800.0
    ) -> ScheduledDispatch:
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
                side_effect_targets=(f"evidence://p3-09/{label}",),
            ),
            authority_attempt=run_attempt,
            owner_ref=f"worker://p3-09/durable-evidence/{label}",
            lease_seconds=1800,
            idempotency_key=f"p3-09-{label}-reserve",
        )
        return scheduler.dispatch(
            access,
            allocation,
            authority_attempt=run_attempt,
            lease_seconds=lease_seconds,
            idempotency_key=f"p3-09-{label}-dispatch",
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
    process_artifact = by_path[package.paths["process"]]
    sequence_artifact = by_path[package.paths["sequence"]]
    failure_artifact = by_path[package.paths["failure"]]
    integration_artifact = by_path[package.paths["integration"]]
    output_artifacts = {
        item.key: by_path[item.logical_path] for item in package.outputs
    }
    assert len({item.artifact_ref for item in output_artifacts.values()}) == 10
    for _, artifact in published:
        assert artifacts.get_artifact(access, artifact.artifact_ref) == artifact
        assert objects.verify(cast(ContentRef, artifact.content_ref)) is True

    def finalize(
        dispatched: ScheduledDispatch,
        artifact: Artifact,
        label: str,
    ) -> str:
        completed = executions.finalize_node(
            access,
            dispatched.node_attempt,
            outputs={
                "render_output": artifact.artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": artifact.artifact_ref,
                "content-ref": cast(ContentRef, artifact.content_ref),
                "provenance": package_artifact.artifact_ref,
                "runtime": process_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key=f"p3-09-{label}-finalize",
        )
        assert completed.status == "SUCCEEDED"
        return completed.status

    preview_dispatch = dispatch("preview", preview_node)
    preview_status = finalize(
        preview_dispatch, output_artifacts[("preview", 1, "beauty")], "preview"
    )
    failed_key = (
        cast(int, package.recovery["failed_frame"]),
        cast(str, package.recovery["failed_pass"]),
    )
    frame_dispatches: dict[tuple[int, str], ScheduledDispatch] = {}
    frame_statuses: dict[tuple[int, str], str] = {}
    preserved_before: dict[tuple[int, str], Artifact] = {}
    for key, node in frame_nodes.items():
        if key == failed_key:
            continue
        label = f"frame-{key[0]}-{key[1]}"
        dispatched = dispatch(label, node)
        frame_dispatches[key] = dispatched
        artifact = output_artifacts[("final", key[0], key[1])]
        preserved_before[key] = artifact
        frame_statuses[key] = finalize(dispatched, artifact, label)

    initial_failed = dispatch(
        f"frame-{failed_key[0]}-{failed_key[1]}-lost",
        frame_nodes[failed_key],
        lease_seconds=0.02,
    )
    expiry = datetime.fromisoformat(initial_failed.node_attempt.lease_expires_at)
    time.sleep(max(0.0, (expiry - datetime.now(timezone.utc)).total_seconds()) + 0.02)
    recovered_states = executions.recover_expired_execution(access, run.run_ref)
    recovered_by_ref = {item.node_ref: item for item in recovered_states}
    assert recovered_by_ref[frame_nodes[failed_key].node_ref].status == "READY"
    history = executions.list_node_history(access, frame_nodes[failed_key].node_ref)
    assert any(
        item.status == "STALE"
        and item.current_attempt_id == initial_failed.node_attempt.attempt_id
        for item in history
    )
    expired_allocations = scheduler.recover_expired_allocations(access, project_ref)
    assert tuple(item.allocation_ref for item in expired_allocations) == (
        initial_failed.allocation.allocation_ref,
    )
    assert expired_allocations[0].status == "EXPIRED"
    recovered_dispatch = dispatch(
        f"frame-{failed_key[0]}-{failed_key[1]}-recovery",
        frame_nodes[failed_key],
    )
    assert recovered_dispatch.node_attempt.attempt_id != initial_failed.node_attempt.attempt_id
    assert recovered_dispatch.node_attempt.fence == initial_failed.node_attempt.fence + 1
    frame_dispatches[failed_key] = recovered_dispatch
    recovered_artifact = output_artifacts[("final", failed_key[0], failed_key[1])]
    frame_statuses[failed_key] = finalize(
        recovered_dispatch,
        recovered_artifact,
        f"frame-{failed_key[0]}-{failed_key[1]}-recovery",
    )
    for key, before in preserved_before.items():
        assert artifacts.get_artifact(access, before.artifact_ref) == before
        assert output_artifacts[("final", key[0], key[1])] == before

    after_frames = executions.prepare_run(access, run.run_ref)
    assert {item.node_ref for item in after_frames if item.status == "READY"} == {
        recovery_node.node_ref
    }
    recovery_dispatch = dispatch("recovery-manifest", recovery_node)
    recovery_status = finalize(
        recovery_dispatch, failure_artifact, "recovery-manifest"
    )
    after_recovery = executions.prepare_run(access, run.run_ref)
    assert {item.node_ref for item in after_recovery if item.status == "READY"} == {
        integration_node.node_ref
    }
    integration_dispatch = dispatch("integration-manifest", integration_node)

    validations = ValidationService(database)
    subjects = tuple(
        validations.bind_artifact_subject(
            access,
            artifact.artifact_ref,
            producer_dimensions={
                "camera": cast(str, package.identity["camera_ref"]),
                "content_ref": cast(ContentRef, artifact.content_ref).value,
                "device": (
                    "device://sha256/"
                    + cast(str, package.identity["device_sha256"])
                ),
                "renderer_a": cast(str, package.identity["renderer_a_ref"]),
                "renderer_b": cast(str, package.identity["renderer_b_ref"]),
                "scene": (
                    "scene://sha256/"
                    + cast(str, package.identity["scene_sha256"])
                ),
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
            },
        )
        for _, artifact in published
    )
    checks = tuple(
        ValidationCheck(
            capability_ref,
            True,
            "project.criteria:p3-09-render-kpi",
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
            "criteria://p3-09/render-durable-evidence/v1",
        ),
        idempotency_key="p3-09-durable-evidence-validation-plan",
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
            assert kpi_name in _KPI_NAMES and package.kpis[kpi_name] == 0
            metrics = (
                MetricMeasurement(
                    kpi_name,
                    0.0,
                    "count",
                    f"Exact {kpi_name} violations in retained P3-09 REAL evidence",
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
            implementation_ref="validator://p3-09/durable-evidence/v1",
            runtime_ref=cast(str, package.identity["runtime_a_ref"]),
            validator_dimensions={
                "device": (
                    "device://sha256/"
                    + cast(str, package.identity["device_sha256"])
                ),
                "renderer_a": cast(str, package.identity["renderer_a_ref"]),
                "renderer_b": cast(str, package.identity["renderer_b_ref"]),
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-09-result-{check.check_id}",
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
        idempotency_key="p3-09-durable-evidence-validation-aggregate",
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
        event_type="P3_09_DURABLE_RENDER_EVIDENCE_RETAINED",
        idempotency_key="p3-09-durable-render-evidence-retained",
        actor_ref="worker://p3-09/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for _, artifact in published),
        metadata={
            "artifact_count": len(published),
            "failed_attempt_id": initial_failed.node_attempt.attempt_id,
            "frame_pass_node_count": 9,
            "kpi_count": 5,
            "recovered_attempt_id": recovered_dispatch.node_attempt.attempt_id,
            "source_commit": commit,
            "source_tree": tree,
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
        },
        payload_ref=cast(ContentRef, integration_artifact.content_ref),
        authority_attempt=run_attempt,
    )
    events = EventLedger(database)
    assert events.get_event(access, event.event_ref) == event
    acceptance = executions.record_run_acceptance(
        access,
        run.run_ref,
        criterion="validation.success_rule=ALL_REQUIRED_PASS",
        evidence_ref=integration_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-09-durable-evidence-acceptance",
    )
    integration_status = finalize(
        integration_dispatch, integration_artifact, "integration-manifest"
    )
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"
    assert graphs.get_graph(access, graph_ref) == graph
    released = scheduler.reconcile_terminal(access, run.run_ref)
    assert len(released) == 12
    assert all(item.status == "RELEASED" for item in released)

    manifest: Mapping[str, object] = {
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
        "identity": {
            "camera_ref": package.identity["camera_ref"],
            "device_sha256": package.identity["device_sha256"],
            "final_config_ref": package.identity["final_config_ref"],
            "preview_config_ref": package.identity["preview_config_ref"],
            "renderer_a_ref": package.identity["renderer_a_ref"],
            "renderer_b_ref": package.identity["renderer_b_ref"],
            "scene_ref": package.identity["scene_ref"],
        },
        "outputs": [
            {
                "allocation_ref": frame_dispatches[item.sequence_key].allocation.allocation_ref.value,
                "artifact_ref": output_artifacts[item.key].artifact_ref.value,
                "attempt_id": frame_dispatches[item.sequence_key].node_attempt.attempt_id,
                "frame": item.frame,
                "node_ref": frame_nodes[item.sequence_key].node_ref.value,
                "pass": item.pass_name,
                "sha256": item.sha256,
                "status": frame_statuses[item.sequence_key],
            }
            for item in package.outputs
            if item.kind == "final"
        ],
        "preview": {
            "allocation_ref": preview_dispatch.allocation.allocation_ref.value,
            "artifact_ref": output_artifacts[("preview", 1, "beauty")].artifact_ref.value,
            "attempt_id": preview_dispatch.node_attempt.attempt_id,
            "node_ref": preview_node.node_ref.value,
            "status": preview_status,
        },
        "recovery": {
            "failed_allocation_ref": initial_failed.allocation.allocation_ref.value,
            "failed_attempt_id": initial_failed.node_attempt.attempt_id,
            "failure_mode": "INJECTED_WORKER_LOSS",
            "prior_artifacts_unchanged": True,
            "recovered_allocation_ref": recovered_dispatch.allocation.allocation_ref.value,
            "recovered_attempt_id": recovered_dispatch.node_attempt.attempt_id,
            "recovery_node_ref": recovery_node.node_ref.value,
            "recovery_status": recovery_status,
            "resume_executed_count": package.recovery["resume_executed_count"],
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
        "event": {
            "event_ref": event.event_ref.value,
            "record_sha256": event.record_sha256,
        },
        "acceptance_event_ref": acceptance.event_ref.value,
        "unresolved_failures": 0,
    }
    assert manifest["kpis"] == {name: 0 for name in _KPI_NAMES}
    target = _output_target()
    if target is not None:
        assert target.resolve(strict=False) != package_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assert _parse_json(target.read_bytes(), source=str(target)) == manifest
    return manifest


def test_p3_09_retained_real_package_becomes_durable_engine_evidence(
    tmp_path: Path,
) -> None:
    package_value = os.environ.get("MINITZ_P3_09_RETAINED_PACKAGE")
    if not package_value:
        pytest.skip("MINITZ_P3_09_RETAINED_PACKAGE is not configured")
    package_path = _regular_package_path(package_value)
    package = _discover_package(package_path)
    imported = _import_engine_evidence(package, package_path, tmp_path)
    assert imported["schema"] == _OUTPUT_SCHEMA
    assert imported["kpis"] == {name: 0 for name in _KPI_NAMES}
    assert imported["unresolved_failures"] == 0


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


def test_p3_09_retained_package_rejects_unsafe_archive_boundaries(
    tmp_path: Path,
) -> None:
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
def test_p3_09_retained_package_rejects_tamper(
    tmp_path: Path,
    case: str,
) -> None:
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


def test_p3_09_retained_package_rejects_stale_source_identity(
    tmp_path: Path,
) -> None:
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


def test_p3_09_durable_evidence_rejects_cross_project_artifact(
    tmp_path: Path,
) -> None:
    database = tmp_path / "scope.sqlite3"
    projects = ProjectStore(database)
    alpha = projects.create_project(namespace="p3-09-alpha", display_name="Alpha")
    beta = projects.create_project(namespace="p3-09-beta", display_name="Beta")
    objects = FilesystemObjectStorageBackend(tmp_path / "scope-objects")
    content = objects.put(b"p3-09", media_type="application/octet-stream")
    artifacts = ArtifactService(database)
    artifact = artifacts.create_artifact(
        alpha.access,
        project_ref=alpha.access.project_ref,
        role="render.retained-package",
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(content,),
        derivation_type="render.scope-fixture",
        metadata={},
    )
    with pytest.raises(ArtifactScopeError):
        artifacts.get_artifact(beta.access, artifact.artifact_ref)


def test_p3_09_manifest_accepts_exact_cpu_device_identity() -> None:
    cpu_identity = "4d4e08a1f7e5547fdb9d9e368e7b9703c03aeeea0ee28a557b69df12eced6045"
    device: Mapping[str, object] = {
        "device_ref": f"device://cpu/sha256/{cpu_identity}",
        "device_id": f"cpu:sha256:{cpu_identity}",
        "device_kind": "cpu",
        "device_name": "AMD EPYC 7R32 48-Core Processor",
        "device_uuid": f"CPU-{cpu_identity}",
        "driver_version": "linux-kernel-7.0.0-1011-aws",
        "compute_backend": "CPU",
        "memory_mib": 196608,
    }
    normalized = _identity(
        {
            "identity": {
                "scene_ref": "artifact://scene/controller/v1",
                "scene_sha256": "1" * 64,
                "camera_ref": "camera://controller/main/v1",
                "camera_sha256": "2" * 64,
                "preview_config_ref": "config://render/preview/v1",
                "preview_config_sha256": "3" * 64,
                "final_config_ref": "config://render/final/v1",
                "final_config_sha256": "4" * 64,
                "renderer_a_ref": "renderer://blender/cpu-a/v1",
                "renderer_b_ref": "renderer://blender/cpu-b/v1",
                "runtime_a_ref": "runtime://controller/cpu-a/v1",
                "runtime_b_ref": "runtime://controller/cpu-b/v1",
                "executor_ref": "executor://controller/cpu/v1",
                "device": device,
                "device_sha256": (
                    "8bbcf8ce61e15d6fe3dce00481dbd623"
                    "91f96cde138d150cc8bda0b7b06e344f"
                ),
            }
        }
    )
    assert normalized["device"] == device
    assert normalized["device_sha256"] == (
        "8bbcf8ce61e15d6fe3dce00481dbd623"
        "91f96cde138d150cc8bda0b7b06e344f"
    )
