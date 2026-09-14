"""Durable Engine evidence importer for retained REAL P3-11 images."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
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
from minitz_os.engine.run import ExecutionAttempt, RunService
from minitz_os.engine.task import Task, TaskRevisionService
from minitz_os.engine.validation import (
    MetricMeasurement,
    ProjectValidationCriteria,
    ValidationCheck,
    ValidationEvidenceState,
    ValidationService,
    ValidationVerdict,
)


_SCHEMA = "minitz.p3-11.retained-real-evidence/v1"
_KPI_SCHEMA = "minitz.p3-11.prompt-kpis/v1"
_OUTPUT_SCHEMA = "minitz.p3-11.durable-engine-evidence/v1"
_KPI_NAMES = (
    "corrupt_image_accepted",
    "source_image_destructively_mutated",
    "project_visual_style_globalized",
    "texture_channel_convention_implicit",
    "color_space_silently_changed",
    "provider_specific_image_kernel_architecture",
)
_OUTPUT_KINDS = (
    "crop",
    "resize",
    "jpeg_convert",
    "mask",
    "composite",
    "thumbnail",
    "enhance",
    "color_convert",
    "data_texture",
    "channel_pack",
)
_MANIFEST_PATH = "evidence/manifest.json"
_CHECKSUM_PATH = "evidence/manifest.sha256"
_OVERLAY_CHECKSUM_PATH = "evidence/overlay-files.sha256"
_RECORD_NAMES = {
    "concurrency",
    "integration",
    "material_binding",
    "process",
    "producer",
    "resource",
}
_MAX_PACKAGE_BYTES = 512 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
_MAX_MEMBERS = 4096
_MAX_JSON_BYTES = 32 * 1024 * 1024
_MAX_IMAGE_EDGE = 8192
_MAX_IMAGE_PIXELS = 64 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}")
_GIT_OBJECT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_CATEGORY = re.compile(r"[a-z][a-z0-9.-]{0,63}")
_ENGINE_ROLE = re.compile(r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+")
_PROJECT_REF = "project://minitz/p3-11/retained"
_TASK_SHA = "1" * 64
_SOURCE_COMMIT = "2" * 40
_SOURCE_TREE = "3" * 40


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
class _ImageEvidence:
    kind: str
    logical_path: str
    sha256: str
    media_type: str
    artifact_ref: str
    content_ref: str
    width: int
    height: int
    mode: str


@dataclass(frozen=True)
class _ImagePackage:
    retained: tuple[_RetainedEvidence, ...]
    source: Mapping[str, object]
    project_ref: str
    task_contract_sha256: str
    identity: Mapping[str, object]
    source_image: _ImageEvidence
    specification_path: str
    specification_sha256: str
    outputs: tuple[_ImageEvidence, ...]
    records: Mapping[str, str]
    documents: Mapping[str, Mapping[str, object]]
    kpis: Mapping[str, int]


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


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    assert isinstance(value, int) and not isinstance(value, bool), label
    assert value >= minimum, label
    return value


def _safe_relative(value: object, label: str) -> str:
    assert isinstance(value, str) and value, label
    parsed = PurePosixPath(value)
    assert not parsed.is_absolute() and ".." not in parsed.parts, label
    assert parsed.as_posix() == value
    assert all(part not in {"", "."} for part in parsed.parts), label
    return value


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
    raw = _mapping(manifest.get("source"), "source")
    commit = raw.get("commit")
    tree = raw.get("tree")
    assert isinstance(commit, str) and _GIT_OBJECT.fullmatch(commit), "source commit"
    assert isinstance(tree, str) and _GIT_OBJECT.fullmatch(tree), "source tree"
    assert len(commit) == len(tree), "source object formats differ"
    overlays = _sequence(raw.get("overlays"), "source overlays")
    overlay_count = _integer(raw.get("overlay_count"), "source overlay count")
    assert overlay_count == len(overlays), "stale source overlay count"
    normalized: dict[str, str] = {}
    for value in overlays:
        overlay = _mapping(value, "source overlay")
        path = _safe_relative(overlay.get("path"), "source overlay path")
        digest = _sha(overlay.get("sha256"), "source overlay digest")
        assert path not in normalized, f"duplicate source overlay: {path}"
        normalized[path] = digest
    if normalized:
        assert _OVERLAY_CHECKSUM_PATH in files, "source overlay checksums missing"
        assert _checksum_lines(
            files[_OVERLAY_CHECKSUM_PATH], source=_OVERLAY_CHECKSUM_PATH
        ) == normalized, "stale source overlay identity"
    expected_commit = os.environ.get("MINITZ_P3_11_EXPECTED_COMMIT")
    expected_tree = os.environ.get("MINITZ_P3_11_EXPECTED_TREE")
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


def _payload_index(
    manifest: Mapping[str, object],
    files: Mapping[str, bytes],
    checksums: Mapping[str, str],
) -> Mapping[str, Mapping[str, object]]:
    rows = _sequence(
        _mapping(manifest.get("payload"), "payload").get("files"), "payload files"
    )
    indexed: dict[str, Mapping[str, object]] = {}
    for value in rows:
        row = _mapping(value, "payload file")
        path = _safe_relative(row.get("path"), "payload path")
        assert path in files and path in checksums, path
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


def _decode_image(
    payload: bytes,
    record: Mapping[str, object],
    *,
    media_type: str,
    label: str,
) -> tuple[int, int, str]:
    if media_type == "image/png":
        assert payload.startswith(b"\x89PNG\r\n\x1a\n"), f"{label} is not PNG"
        expected_format = "PNG"
    else:
        assert media_type == "image/jpeg", f"{label} media type"
        assert payload.startswith(b"\xff\xd8\xff"), f"{label} is not JPEG"
        expected_format = "JPEG"
    with Image.open(BytesIO(payload)) as probe:
        assert probe.format == expected_format, label
        probe.verify()
    with Image.open(BytesIO(payload)) as decoded:
        decoded.load()
        width, height = decoded.size
        mode = decoded.mode
    assert 0 < width <= _MAX_IMAGE_EDGE and 0 < height <= _MAX_IMAGE_EDGE
    assert width * height <= _MAX_IMAGE_PIXELS
    declared = _mapping(record.get("decode"), f"{label} decode")
    assert declared.get("verified") is True
    assert declared.get("format") == expected_format
    assert _integer(declared.get("width"), f"{label} width", minimum=1) == width
    assert _integer(declared.get("height"), f"{label} height", minimum=1) == height
    assert _text(declared.get("mode"), f"{label} mode") == mode
    return width, height, mode


def _image_evidence(
    raw: object,
    *,
    files: Mapping[str, bytes],
    checksums: Mapping[str, str],
    payload_index: Mapping[str, Mapping[str, object]],
) -> _ImageEvidence:
    record = _mapping(raw, "image evidence")
    kind = _text(record.get("kind"), "image kind")
    path = _safe_relative(record.get("path"), f"{kind} path")
    digest = _sha(record.get("sha256"), f"{kind} digest")
    assert path in files and checksums[path] == digest and files[path], kind
    row = payload_index[path]
    media_type = _text(record.get("media_type"), f"{kind} media type")
    assert row.get("media_type") == media_type
    width, height, mode = _decode_image(
        files[path], record, media_type=media_type, label=path
    )
    return _ImageEvidence(
        kind,
        path,
        digest,
        media_type,
        _ref(record.get("artifact_ref"), f"{kind} Artifact ref"),
        _ref(record.get("content_ref"), f"{kind} ContentRef"),
        width,
        height,
        mode,
    )


def _zero_kpis(manifest: Mapping[str, object]) -> Mapping[str, int]:
    report = _mapping(manifest.get("prompt_kpis"), "prompt_kpis")
    assert report.get("schema") == _KPI_SCHEMA
    assert report.get("all_six_zero") is True
    values = _mapping(report.get("kpis"), "prompt KPI values")
    assert set(values) == set(_KPI_NAMES), "prompt KPI names differ"
    normalized: dict[str, int] = {}
    for name in _KPI_NAMES:
        value = _integer(values[name], name)
        assert value == 0, f"non-zero prompt KPI: {name}"
        normalized[name] = value
    return normalized


def _integration_record_digest(document: Mapping[str, object]) -> str:
    unsigned = dict(document)
    unsigned.pop("record_sha256", None)
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _discover_package(package_value: str | Path) -> _ImagePackage:
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
    for member_path, digest in checksums.items():
        assert hashlib.sha256(files[member_path]).hexdigest() == digest, (
            f"forged package member: {member_path}"
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
    identity_raw = _mapping(manifest.get("identity"), "identity")
    identity: dict[str, object] = {
        "runtime_ref": _ref(identity_raw.get("runtime_ref"), "runtime ref"),
        "executor_ref": _ref(identity_raw.get("executor_ref"), "executor ref"),
        "resource_ref": _ref(identity_raw.get("resource_ref"), "resource ref"),
        "source_artifact_ref": _ref(
            identity_raw.get("source_artifact_ref"), "source Artifact ref"
        ),
        "source_content_ref": _ref(
            identity_raw.get("source_content_ref"), "source ContentRef"
        ),
        "source_sha256": _sha(identity_raw.get("source_sha256"), "source digest"),
        "specification_artifact_ref": _ref(
            identity_raw.get("specification_artifact_ref"), "specification Artifact ref"
        ),
        "specification_sha256": _sha(
            identity_raw.get("specification_sha256"), "specification digest"
        ),
        "producer_attempt_id": _text(
            identity_raw.get("producer_attempt_id"), "producer attempt"
        ),
        "producer_fence": _integer(
            identity_raw.get("producer_fence"), "producer fence", minimum=1
        ),
    }
    source_record = _mapping(manifest.get("source_image"), "source image")
    source_image = _image_evidence(
        source_record,
        files=files,
        checksums=checksums,
        payload_index=payload_index,
    )
    assert source_image.kind == "source"
    assert source_image.artifact_ref == identity["source_artifact_ref"]
    assert source_image.content_ref == identity["source_content_ref"]
    assert source_image.sha256 == identity["source_sha256"]

    specification_record = _mapping(manifest.get("specification"), "specification")
    specification_path = _safe_relative(
        specification_record.get("path"), "specification path"
    )
    specification_sha256 = _sha(
        specification_record.get("sha256"), "specification digest"
    )
    assert specification_path in files and checksums[specification_path] == specification_sha256
    assert specification_record.get("media_type") == "application/json"
    assert specification_record.get("artifact_ref") == identity["specification_artifact_ref"]
    assert specification_sha256 == identity["specification_sha256"]
    specification = _parse_json(
        files[specification_path], source=specification_path
    )
    assert specification.get("schema") == "minitz.p3-11.image-specification/v1"
    assert specification.get("project_ref") == project_ref
    assert specification.get("task_contract_sha256") == task_contract_sha256
    assert specification.get("source_artifact_ref") == source_image.artifact_ref
    assert specification.get("source_content_ref") == source_image.content_ref
    assert specification.get("source_sha256") == source_image.sha256
    assert tuple(_sequence(specification.get("output_kinds"), "output kinds")) == _OUTPUT_KINDS
    assert specification.get("deterministic") is True
    assert specification.get("provider_neutral") is True
    assert specification.get("source_mutation_forbidden") is True
    assert specification.get("color_space_policy") == "EXPLICIT"
    assert specification.get("texture_channel_policy") == "EXPLICIT"

    outputs: list[_ImageEvidence] = []
    for value in _sequence(manifest.get("outputs"), "outputs"):
        record = _mapping(value, "output")
        output = _image_evidence(
            record,
            files=files,
            checksums=checksums,
            payload_index=payload_index,
        )
        assert record.get("project_ref") == project_ref
        assert record.get("task_contract_sha256") == task_contract_sha256
        assert record.get("specification_sha256") == specification_sha256
        assert record.get("source_artifact_ref") == source_image.artifact_ref
        assert record.get("source_content_ref") == source_image.content_ref
        assert record.get("source_sha256") == source_image.sha256
        assert record.get("producer_attempt_id") == identity["producer_attempt_id"]
        assert record.get("producer_fence") == identity["producer_fence"]
        expected_color_space = (
            "DATA" if output.kind in {"data_texture", "channel_pack"} else "sRGB"
        )
        assert record.get("color_space") == expected_color_space
        if output.kind == "jpeg_convert":
            assert output.media_type == "image/jpeg"
        else:
            assert output.media_type == "image/png"
        if output.kind == "mask":
            assert output.mode == "L"
        outputs.append(output)
    assert tuple(item.kind for item in outputs) == _OUTPUT_KINDS
    assert len({item.logical_path for item in outputs}) == len(_OUTPUT_KINDS)
    assert len({item.artifact_ref for item in outputs}) == len(_OUTPUT_KINDS)
    assert len({item.content_ref for item in outputs}) == len(_OUTPUT_KINDS)

    records_raw = _mapping(manifest.get("records"), "record paths")
    assert set(records_raw) == _RECORD_NAMES, "record names differ"
    records = {
        name: _safe_relative(records_raw[name], f"{name} record path")
        for name in sorted(records_raw)
    }
    assert len(set(records.values())) == len(records)
    assert all(path in files and path.endswith(".json") for path in records.values())
    documents = {
        name: _parse_json(files[path], source=path) for name, path in records.items()
    }
    resource = documents["resource"]
    assert resource.get("schema") == "minitz.p3-11.resource-receipt/v1"
    assert resource.get("status") == "OBSERVED"
    assert resource.get("resource_ref") == identity["resource_ref"]
    assert resource.get("runtime_ref") == identity["runtime_ref"]
    assert resource.get("executor_ref") == identity["executor_ref"]
    _ref(resource.get("provider_ref"), "provider ref")
    _text(resource.get("observed_at"), "resource observation")

    producer = documents["producer"]
    assert producer.get("schema") == "minitz.p3-11.producer-fence/v1"
    assert producer.get("status") == "FENCED"
    assert producer.get("project_ref") == project_ref
    assert producer.get("task_contract_sha256") == task_contract_sha256
    assert producer.get("attempt_id") == identity["producer_attempt_id"]
    assert producer.get("fence") == identity["producer_fence"]
    assert producer.get("stale_write_rejected") is True
    stale_attempt = _text(producer.get("stale_attempt_id"), "stale attempt")
    assert stale_attempt != identity["producer_attempt_id"]
    stale_fence = _integer(producer.get("stale_fence"), "stale fence", minimum=1)
    assert stale_fence < cast(int, identity["producer_fence"])

    process = documents["process"]
    assert process.get("schema") == "minitz.p3-11.real-process/v1"
    assert process.get("reality") == "REAL" and process.get("status") == "SUCCEEDED"
    assert process.get("exit_code") == 0
    assert process.get("source_commit") == source["commit"]
    assert process.get("source_tree") == source["tree"]
    assert process.get("runtime_ref") == identity["runtime_ref"]
    assert process.get("executor_ref") == identity["executor_ref"]
    assert process.get("resource_ref") == identity["resource_ref"]
    _text(process.get("started_at"), "process start")
    _text(process.get("finished_at"), "process finish")

    concurrency = documents["concurrency"]
    assert concurrency.get("schema") == "minitz.p3-11.image-concurrency/v1"
    assert concurrency.get("status") == "SUCCEEDED"
    assert concurrency.get("overlap_observed") is True
    assert _integer(
        concurrency.get("max_active_operations"), "active operations", minimum=2
    ) >= 2
    independent = tuple(
        _text(value, "independent output")
        for value in _sequence(
            concurrency.get("independent_output_kinds"), "independent outputs"
        )
    )
    assert len(independent) >= 2 and set(independent) <= set(_OUTPUT_KINDS)
    assert concurrency.get("producer_attempt_id") == identity["producer_attempt_id"]
    assert concurrency.get("producer_fence") == identity["producer_fence"]

    by_kind = {item.kind: item for item in outputs}
    material = documents["material_binding"]
    assert material.get("schema") == "minitz.p3-11.material-binding/v1"
    assert material.get("status") == "SUCCEEDED"
    assert material.get("project_ref") == project_ref
    assert material.get("specification_sha256") == specification_sha256
    for prefix, kind in (
        ("base_color", "color_convert"),
        ("data_texture", "data_texture"),
        ("channel_pack", "channel_pack"),
    ):
        assert material.get(f"{prefix}_artifact_ref") == by_kind[kind].artifact_ref
        assert material.get(f"{prefix}_sha256") == by_kind[kind].sha256
    assert material.get("color_space_explicit") is True
    assert material.get("channel_packing_explicit") is True

    integration = documents["integration"]
    assert integration.get("schema") == "minitz.p3-11.integration-manifest/v1"
    assert integration.get("reality") == "REAL" and integration.get("status") == "SUCCEEDED"
    assert integration.get("project_ref") == project_ref
    assert integration.get("task_contract_sha256") == task_contract_sha256
    assert integration.get("source_commit") == source["commit"]
    assert integration.get("source_tree") == source["tree"]
    assert integration.get("source_sha256") == source_image.sha256
    assert integration.get("specification_sha256") == specification_sha256
    assert _mapping(integration.get("outputs"), "integration outputs") == {
        item.kind: item.sha256 for item in outputs
    }
    assert _mapping(integration.get("kpis"), "integration KPIs") == kpis
    assert _integer(integration.get("unresolved_failures"), "integration failures") == 0
    record_sha256 = _mapping(integration.get("record_sha256"), "record digests")
    expected_record_sha256 = {
        name: checksums[path]
        for name, path in records.items()
        if name != "integration"
    }
    expected_record_sha256["integration"] = _integration_record_digest(integration)
    assert record_sha256 == expected_record_sha256
    integration_path = records["integration"]
    assert checksums[integration_path] == hashlib.sha256(files[integration_path]).hexdigest()

    retained = [
        _RetainedEvidence(
            f"retained-package/{package_path.name}",
            "package",
            package_payload,
            "application/gzip",
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
            member_path,
            cast(str, payload_index[member_path]["category"]),
            files[member_path],
            cast(str, payload_index[member_path]["media_type"]),
        )
        for member_path in sorted(payload_index)
    )
    return _ImagePackage(
        tuple(retained),
        source,
        project_ref,
        task_contract_sha256,
        identity,
        source_image,
        specification_path,
        specification_sha256,
        tuple(outputs),
        records,
        documents,
        kpis,
    )


def _import_engine_evidence(
    package: _ImagePackage,
    package_path: Path,
    tmp_path: Path,
    *,
    output_target: Path | None,
) -> Mapping[str, object]:
    commit = cast(str, package.source["commit"])
    tree = cast(str, package.source["tree"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "p3-11-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("image.validate", "1.0.0")
    output_contract = {
        "image_output": "schema://minitz/p3-11/image-output/1",
        "evidence_manifest": "schema://minitz/p3-11/durable-evidence/1",
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate exact retained REAL P3-11 image evidence",
            output_contract=output_contract,
        )
    )
    registration = ProjectStore(database).create_project(
        namespace="p3-11-durable-evidence",
        display_name="P3-11 Durable Image Evidence",
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
        idempotency_key="p3-11-durable-evidence-task",
        task_type="image.durable-evidence",
        objective="Retain and validate exact REAL P3-11 image outputs",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={"expected_outputs": len(_OUTPUT_KINDS), "named_zero_kpis": 6},
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-11/retained-evidence",
        egress_policy_ref="policy://p3-11/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-11/durable-evidence/run",
        lease_seconds=1800,
    )

    graph_ref = GraphRef.new(project_ref)
    output_nodes = {
        kind: Node(
            NodeRef.new(graph_ref),
            "generic.image.output-evidence",
            (capability_ref,),
            (),
            (),
            output_contract,
            None,
            "READ_ONLY",
            {},
            ("artifact", "content-ref", "provenance", "runtime"),
        )
        for kind in _OUTPUT_KINDS
    }
    integration_node = Node(
        NodeRef.new(graph_ref),
        "generic.image.integration-manifest",
        (capability_ref,),
        tuple(node.node_ref for node in output_nodes.values()),
        (),
        output_contract,
        None,
        "READ_ONLY",
        {},
        ("artifact", "content-ref", "provenance", "runtime"),
    )
    graphs = GraphService(database)
    graph = graphs.create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(*output_nodes.values(), integration_node),
        compiler_identity="compiler://p3-11/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    prepared = executions.prepare_run(access, run.run_ref)
    assert {item.node_ref for item in prepared if item.status == "READY"} == {
        node.node_ref for node in output_nodes.values()
    }

    artifacts = ArtifactService(database)
    published: list[tuple[_RetainedEvidence, Artifact]] = []
    package_artifact: Artifact | None = None
    for evidence in package.retained:
        content_ref = objects.put(
            evidence.payload,
            media_type=evidence.media_type,
            expected_digest=evidence.sha256,
            expected_size=len(evidence.payload),
        )
        assert content_ref == ContentRef.from_bytes(
            evidence.payload, media_type=evidence.media_type
        )
        role = f"image.{evidence.category}"
        assert _ENGINE_ROLE.fullmatch(role), "Engine Artifact role"
        sources: tuple[Artifact, ...] = () if package_artifact is None else (package_artifact,)
        artifact = artifacts.publish_from_run(
            access,
            producer_attempt=run_attempt,
            expected_task_ref=task.task_ref,
            expected_task_digest=task.canonical_digest,
            role=role,
            content_ref=content_ref,
            source_refs=(),
            source_artifact_refs=tuple(item.artifact_ref for item in sources),
            source_content_refs=tuple(
                cast(ContentRef, item.content_ref) for item in sources
            ),
            derivation_type=(
                "image.captured-real-evidence"
                if evidence.category == "package"
                else "image.extracted-retained-package"
            ),
            metadata={"semantic_label": evidence.logical_path},
        )
        if package_artifact is None:
            package_artifact = artifact
        published.append((evidence, artifact))
    assert package_artifact is not None
    by_path = {evidence.logical_path: artifact for evidence, artifact in published}
    manifest_artifact = by_path[_MANIFEST_PATH]
    process_artifact = by_path[package.records["process"]]
    integration_artifact = by_path[package.records["integration"]]
    output_artifacts = {
        item.kind: by_path[item.logical_path] for item in package.outputs
    }
    for _, artifact in published:
        assert artifacts.get_artifact(access, artifact.artifact_ref) == artifact
        assert objects.verify(cast(ContentRef, artifact.content_ref)) is True

    node_attempts = {}
    node_statuses: dict[str, str] = {}
    for kind, node in output_nodes.items():
        attempt = executions.lease_node(
            access,
            node.node_ref,
            authority_attempt=run_attempt,
            owner_ref=f"worker://p3-11/durable-evidence/{kind}",
            lease_seconds=1800,
            idempotency_key=f"p3-11-{kind}-lease",
        )
        started = executions.start_node(
            access,
            attempt,
            idempotency_key=f"p3-11-{kind}-start",
        )
        assert started.status == "RUNNING"
        artifact = output_artifacts[kind]
        completed = executions.finalize_node(
            access,
            attempt,
            outputs={
                "image_output": artifact.artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": artifact.artifact_ref,
                "content-ref": cast(ContentRef, artifact.content_ref),
                "provenance": package_artifact.artifact_ref,
                "runtime": process_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key=f"p3-11-{kind}-finalize",
        )
        assert completed.status == "SUCCEEDED"
        node_attempts[kind] = attempt
        node_statuses[kind] = completed.status
    assert {item.node_ref for item in executions.prepare_run(access, run.run_ref) if item.status == "READY"} == {
        integration_node.node_ref
    }
    integration_attempt = executions.lease_node(
        access,
        integration_node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="worker://p3-11/durable-evidence/integration",
        lease_seconds=1800,
        idempotency_key="p3-11-integration-lease",
    )
    started_integration = executions.start_node(
        access,
        integration_attempt,
        idempotency_key="p3-11-integration-start",
    )
    assert started_integration.status == "RUNNING"

    validations = ValidationService(database)
    subjects = tuple(
        validations.bind_artifact_subject(
            access,
            artifact.artifact_ref,
            producer_dimensions={
                "content_ref": cast(ContentRef, artifact.content_ref).value,
                "producer_attempt": (
                    f"attempt://{cast(str, package.identity['producer_attempt_id'])}"
                ),
                "producer_fence": f"fence://{package.identity['producer_fence']}",
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
            "project.criteria:p3-11-image-kpi",
            ("artifact", "content_ref", "provenance"),
            (),
            {"expected": 0, "kpi": name},
        )
        for name in _KPI_NAMES
    )
    plan = validations.compile_plan(
        access,
        integration_attempt,
        subjects=subjects,
        project_criteria=ProjectValidationCriteria(
            project_ref,
            checks,
            "criteria://p3-11/image-durable-evidence/v1",
        ),
        idempotency_key="p3-11-durable-evidence-validation-plan",
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
                    kpi_name,
                    0.0,
                    "count",
                    f"Exact {kpi_name} violations in retained P3-11 REAL evidence",
                    integration_artifact.artifact_ref.value,
                ),
            )
        result = validations.record_result(
            access,
            integration_attempt,
            plan.plan_ref,
            check_id=check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://p3-11/durable-evidence/v1",
            runtime_ref=cast(str, package.identity["runtime_ref"]),
            validator_dimensions={
                "producer_attempt": (
                    f"attempt://{cast(str, package.identity['producer_attempt_id'])}"
                ),
                "producer_fence": f"fence://{package.identity['producer_fence']}",
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-11-result-{check.check_id}",
        )
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
        if isinstance(kpi_name, str):
            kpi_result_names.add(kpi_name)
        results.append(result)
    assert kpi_result_names == set(_KPI_NAMES)
    aggregate = validations.aggregate(
        access,
        integration_attempt,
        plan.plan_ref,
        idempotency_key="p3-11-durable-evidence-validation-aggregate",
    )
    assert aggregate.verdict is ValidationVerdict.PASS
    assert aggregate.accepted is True
    assert aggregate.evidence_state is ValidationEvidenceState.CURRENT
    assert aggregate.missing_required_check_ids == ()

    evidence_event = EventLedger(database).append_event(
        access,
        project_ref=project_ref,
        task_ref=task.task_ref,
        run_ref=run.run_ref,
        graph_ref=graph_ref,
        node_ref=integration_node.node_ref,
        event_type="P3_11_DURABLE_IMAGE_EVIDENCE_RETAINED",
        idempotency_key="p3-11-durable-image-evidence-retained",
        actor_ref="worker://p3-11/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for _, artifact in published),
        metadata={
            "artifact_count": len(published),
            "kpi_count": 6,
            "output_count": len(package.outputs),
            "producer_attempt_id": cast(str, package.identity["producer_attempt_id"]),
            "producer_fence": cast(str, package.identity["producer_fence"]),
            "source_commit": commit,
            "source_tree": tree,
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
        },
        payload_ref=cast(ContentRef, integration_artifact.content_ref),
        authority_attempt=run_attempt,
    )
    acceptance_event = executions.record_run_acceptance(
        access,
        run.run_ref,
        criterion="validation.success_rule=ALL_REQUIRED_PASS",
        evidence_ref=integration_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-11-durable-evidence-acceptance",
    )
    completed_integration = executions.finalize_node(
        access,
        integration_attempt,
        outputs={
            "image_output": integration_artifact.artifact_ref,
            "evidence_manifest": manifest_artifact.artifact_ref,
        },
        evidence={
            "artifact": integration_artifact.artifact_ref,
            "content-ref": cast(ContentRef, integration_artifact.content_ref),
            "provenance": package_artifact.artifact_ref,
            "runtime": process_artifact.artifact_ref,
        },
        acceptance_criteria=(),
        idempotency_key="p3-11-integration-finalize",
    )
    assert completed_integration.status == "SUCCEEDED"
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"
    assert graphs.get_graph(access, graph_ref) == graph
    events = EventLedger(database)
    assert events.get_event(access, evidence_event.event_ref) == evidence_event
    assert events.get_event(access, acceptance_event.event_ref) == acceptance_event

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
            "graph_ref": graph.graph_ref.value,
            "graph_sha256": graph.record_sha256,
        },
        "engine_status": completed_run.status,
        "outputs": [
            {
                "artifact_ref": output_artifacts[kind].artifact_ref.value,
                "attempt_id": node_attempts[kind].attempt_id,
                "content_ref": cast(ContentRef, output_artifacts[kind].content_ref).value,
                "kind": kind,
                "node_ref": output_nodes[kind].node_ref.value,
                "status": node_statuses[kind],
            }
            for kind in _OUTPUT_KINDS
        ],
        "integration": {
            "artifact_ref": integration_artifact.artifact_ref.value,
            "node_ref": integration_node.node_ref.value,
            "status": completed_integration.status,
        },
        "kpis": dict(package.kpis),
        "validation": {
            "accepted": aggregate.accepted,
            "aggregate_sha256": aggregate.aggregate_sha256,
            "plan_ref": plan.plan_ref.value,
            "result_refs": [result.result_ref.value for result in results],
            "verdict": aggregate.verdict.value,
        },
        "events": {
            "acceptance": acceptance_event.event_ref.value,
            "evidence": evidence_event.event_ref.value,
        },
        "unresolved_failures": 0,
    }
    if output_target is not None:
        assert output_target.resolve(strict=False) != package_path
        output_target.parent.mkdir(parents=True, exist_ok=True)
        output_target.write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assert _parse_json(output_target.read_bytes(), source=str(output_target)) == output
    return output


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _image_payload(
    *,
    image_format: str,
    mode: str,
    size: tuple[int, int],
    color: float | tuple[float, ...] | str | None,
) -> bytes:
    stream = BytesIO()
    Image.new(mode, size, color).save(stream, format=image_format)
    return stream.getvalue()


def _artifact_ref(label: str) -> str:
    suffix = hashlib.sha256(label.encode()).hexdigest()[:32]
    return f"artifact://retained/{suffix}/1"


def _file_record(
    *,
    kind: str,
    path: str,
    payload: bytes,
    media_type: str,
    artifact_ref: str,
) -> Mapping[str, object]:
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "kind": kind,
        "path": path,
        "sha256": digest,
        "media_type": media_type,
        "artifact_ref": artifact_ref,
        "content_ref": f"content://sha256/{digest}?size={len(payload)}",
    }


def _decode_record(payload: bytes) -> Mapping[str, object]:
    with Image.open(BytesIO(payload)) as image:
        image.load()
        return {
            "verified": True,
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
        }


def _build_valid_archive(
    path: Path,
    *,
    corrupt_image: bool = False,
    forged_member: bool = False,
) -> None:
    files: dict[str, bytes] = {}
    source_payload = _image_payload(
        image_format="PNG",
        mode="RGBA",
        size=(8, 8),
        color=(24, 48, 72, 255),
    )
    source = dict(
        _file_record(
            kind="source",
            path="evidence/images/source.png",
            payload=source_payload,
            media_type="image/png",
            artifact_ref=_artifact_ref("source"),
        )
    )
    source["decode"] = _decode_record(source_payload)
    files[str(source["path"])] = source_payload

    specification_document: Mapping[str, object] = {
        "schema": "minitz.p3-11.image-specification/v1",
        "project_ref": _PROJECT_REF,
        "task_contract_sha256": _TASK_SHA,
        "source_artifact_ref": source["artifact_ref"],
        "source_content_ref": source["content_ref"],
        "source_sha256": source["sha256"],
        "output_kinds": list(_OUTPUT_KINDS),
        "deterministic": True,
        "provider_neutral": True,
        "source_mutation_forbidden": True,
        "color_space_policy": "EXPLICIT",
        "texture_channel_policy": "EXPLICIT",
    }
    specification_payload = _canonical(specification_document)
    specification = _file_record(
        kind="specification",
        path="evidence/specification.json",
        payload=specification_payload,
        media_type="application/json",
        artifact_ref=_artifact_ref("specification"),
    )
    files[str(specification["path"])] = specification_payload

    output_payloads: dict[str, bytes] = {}
    outputs: list[Mapping[str, object]] = []
    for index, kind in enumerate(_OUTPUT_KINDS):
        is_jpeg = kind == "jpeg_convert"
        mode = "L" if kind == "mask" else "RGB"
        image_format = "JPEG" if is_jpeg else "PNG"
        extension = "jpg" if is_jpeg else "png"
        color: float | tuple[float, ...] = (
            255 if mode == "L" else (20 + index, 40 + index, 60 + index)
        )
        payload = _image_payload(
            image_format=image_format,
            mode=mode,
            size=(4 + index, 5 + index),
            color=color,
        )
        if corrupt_image and kind == "crop":
            payload = b"not-a-decodable-png"
        output_payloads[kind] = payload
        record = dict(
            _file_record(
                kind=kind,
                path=f"evidence/images/{kind}.{extension}",
                payload=payload,
                media_type="image/jpeg" if is_jpeg else "image/png",
                artifact_ref=_artifact_ref(kind),
            )
        )
        record.update(
            {
                "project_ref": _PROJECT_REF,
                "task_contract_sha256": _TASK_SHA,
                "specification_sha256": specification["sha256"],
                "source_artifact_ref": source["artifact_ref"],
                "source_content_ref": source["content_ref"],
                "source_sha256": source["sha256"],
                "producer_attempt_id": "natt_" + "4" * 32,
                "producer_fence": 2,
                "color_space": "DATA" if kind in {"data_texture", "channel_pack"} else "sRGB",
                "decode": (
                    {
                        "verified": True,
                        "format": "PNG",
                        "width": 4,
                        "height": 5,
                        "mode": "RGB",
                    }
                    if corrupt_image and kind == "crop"
                    else _decode_record(payload)
                ),
            }
        )
        outputs.append(record)
        files[str(record["path"])] = payload

    record_paths = {
        "concurrency": "evidence/records/concurrency.json",
        "integration": "evidence/records/integration.json",
        "material_binding": "evidence/records/material-binding.json",
        "process": "evidence/records/process.json",
        "producer": "evidence/records/producer.json",
        "resource": "evidence/records/resource.json",
    }
    resource_document: Mapping[str, object] = {
        "schema": "minitz.p3-11.resource-receipt/v1",
        "status": "OBSERVED",
        "resource_ref": "resource://local/cpu/p3-11",
        "provider_ref": "provider://local",
        "runtime_ref": "runtime://pillow/12.1.1",
        "executor_ref": "executor://p3-11/collector",
        "observed_at": "2026-09-01T00:00:00Z",
    }
    producer_document: Mapping[str, object] = {
        "schema": "minitz.p3-11.producer-fence/v1",
        "status": "FENCED",
        "project_ref": _PROJECT_REF,
        "task_contract_sha256": _TASK_SHA,
        "attempt_id": "natt_" + "4" * 32,
        "fence": 2,
        "stale_attempt_id": "natt_" + "5" * 32,
        "stale_fence": 1,
        "stale_write_rejected": True,
    }
    process_document: Mapping[str, object] = {
        "schema": "minitz.p3-11.real-process/v1",
        "reality": "REAL",
        "status": "SUCCEEDED",
        "exit_code": 0,
        "source_commit": _SOURCE_COMMIT,
        "source_tree": _SOURCE_TREE,
        "runtime_ref": resource_document["runtime_ref"],
        "executor_ref": resource_document["executor_ref"],
        "resource_ref": resource_document["resource_ref"],
        "started_at": "2026-09-01T00:00:00Z",
        "finished_at": "2026-09-01T00:01:00Z",
    }
    concurrency_document: Mapping[str, object] = {
        "schema": "minitz.p3-11.image-concurrency/v1",
        "status": "SUCCEEDED",
        "independent_output_kinds": ["data_texture", "channel_pack"],
        "overlap_observed": True,
        "max_active_operations": 2,
        "producer_attempt_id": producer_document["attempt_id"],
        "producer_fence": producer_document["fence"],
    }
    by_kind = {str(record["kind"]): record for record in outputs}
    material_document: Mapping[str, object] = {
        "schema": "minitz.p3-11.material-binding/v1",
        "status": "SUCCEEDED",
        "project_ref": _PROJECT_REF,
        "specification_sha256": specification["sha256"],
        "base_color_artifact_ref": by_kind["color_convert"]["artifact_ref"],
        "base_color_sha256": by_kind["color_convert"]["sha256"],
        "data_texture_artifact_ref": by_kind["data_texture"]["artifact_ref"],
        "data_texture_sha256": by_kind["data_texture"]["sha256"],
        "channel_pack_artifact_ref": by_kind["channel_pack"]["artifact_ref"],
        "channel_pack_sha256": by_kind["channel_pack"]["sha256"],
        "color_space_explicit": True,
        "channel_packing_explicit": True,
    }
    record_documents: dict[str, Mapping[str, object]] = {
        "concurrency": concurrency_document,
        "material_binding": material_document,
        "process": process_document,
        "producer": producer_document,
        "resource": resource_document,
    }
    for name, document in record_documents.items():
        files[record_paths[name]] = _canonical(document)

    integration_unsigned: Mapping[str, object] = {
        "schema": "minitz.p3-11.integration-manifest/v1",
        "reality": "REAL",
        "status": "SUCCEEDED",
        "project_ref": _PROJECT_REF,
        "task_contract_sha256": _TASK_SHA,
        "source_commit": _SOURCE_COMMIT,
        "source_tree": _SOURCE_TREE,
        "source_sha256": source["sha256"],
        "specification_sha256": specification["sha256"],
        "outputs": {str(record["kind"]): record["sha256"] for record in outputs},
        "kpis": {name: 0 for name in _KPI_NAMES},
        "unresolved_failures": 0,
    }
    integration_digest = hashlib.sha256(_canonical(integration_unsigned)).hexdigest()
    record_sha256 = {
        name: hashlib.sha256(files[record_paths[name]]).hexdigest()
        for name in record_documents
    }
    record_sha256["integration"] = integration_digest
    integration_document = {
        **integration_unsigned,
        "record_sha256": record_sha256,
    }
    files[record_paths["integration"]] = _canonical(integration_document)

    payload_rows = [
        {
            "path": member_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "category": (
                "image-output"
                if member_path.startswith("evidence/images/") and member_path != source["path"]
                else "image-source"
                if member_path == source["path"]
                else "specification"
                if member_path == specification["path"]
                else "record"
            ),
            "media_type": (
                "image/jpeg"
                if member_path.endswith(".jpg")
                else "image/png"
                if member_path.endswith(".png")
                else "application/json"
            ),
        }
        for member_path, payload in sorted(files.items())
    ]
    manifest: Mapping[str, object] = {
        "schema": _SCHEMA,
        "source": {
            "commit": _SOURCE_COMMIT,
            "tree": _SOURCE_TREE,
            "overlay_count": 0,
            "overlays": [],
        },
        "project_ref": _PROJECT_REF,
        "task_contract_sha256": _TASK_SHA,
        "identity": {
            "runtime_ref": resource_document["runtime_ref"],
            "executor_ref": resource_document["executor_ref"],
            "resource_ref": resource_document["resource_ref"],
            "source_artifact_ref": source["artifact_ref"],
            "source_content_ref": source["content_ref"],
            "source_sha256": source["sha256"],
            "specification_artifact_ref": specification["artifact_ref"],
            "specification_sha256": specification["sha256"],
            "producer_attempt_id": producer_document["attempt_id"],
            "producer_fence": producer_document["fence"],
        },
        "source_image": source,
        "specification": specification,
        "outputs": outputs,
        "records": record_paths,
        "payload": {"files": payload_rows},
        "prompt_kpis": {
            "schema": _KPI_SCHEMA,
            "all_six_zero": True,
            "kpis": {name: 0 for name in _KPI_NAMES},
        },
        "unresolved_failures": 0,
    }
    files[_MANIFEST_PATH] = _canonical(manifest)
    checksums = {
        member_path: hashlib.sha256(payload).hexdigest()
        for member_path, payload in files.items()
    }
    checksum_payload = "".join(
        f"{digest}  {member_path}\n"
        for member_path, digest in sorted(checksums.items())
    ).encode()
    files[_CHECKSUM_PATH] = checksum_payload
    if forged_member:
        files[str(source["path"])] = source_payload + b"forged"

    with tarfile.open(path, mode="w:gz") as archive:
        for member_path, payload in sorted(files.items()):
            info = tarfile.TarInfo(member_path)
            info.size = len(payload)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, BytesIO(payload))


def _write_unsafe_archive(path: Path) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        info = tarfile.TarInfo(_MANIFEST_PATH)
        info.size = 2
        archive.addfile(info, BytesIO(b"{}"))
        link = tarfile.TarInfo("evidence/escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive.addfile(link)


def test_p3_11_valid_retained_archive_becomes_durable_engine_evidence(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "valid.tar.gz"
    _build_valid_archive(archive_path)
    package = _discover_package(archive_path)
    imported = _import_engine_evidence(
        package,
        archive_path,
        tmp_path / "engine",
        output_target=None,
    )
    assert imported["schema"] == _OUTPUT_SCHEMA
    assert imported["kpis"] == {name: 0 for name in _KPI_NAMES}
    assert imported["unresolved_failures"] == 0
    assert imported["engine_status"] == "SUCCEEDED"
    validation = cast(Mapping[str, object], imported["validation"])
    assert validation["accepted"] is True
    assert validation["verdict"] == "PASS"
    assert set(cast(Mapping[str, object], imported["events"])) == {
        "acceptance",
        "evidence",
    }


@pytest.mark.parametrize("failure", ("forged", "corrupt"))
def test_p3_11_retained_archive_rejects_forged_or_corrupt_image(
    tmp_path: Path,
    failure: str,
) -> None:
    archive_path = tmp_path / f"{failure}.tar.gz"
    _build_valid_archive(
        archive_path,
        corrupt_image=failure == "corrupt",
        forged_member=failure == "forged",
    )
    match = "forged package member" if failure == "forged" else "not PNG"
    with pytest.raises(AssertionError, match=match):
        _discover_package(archive_path)


def test_p3_11_retained_archive_rejects_unsafe_members(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    _write_unsafe_archive(archive_path)
    with pytest.raises(AssertionError, match="regular files"):
        _discover_package(archive_path)


def test_p3_11_engine_artifacts_remain_project_scoped(tmp_path: Path) -> None:
    database = tmp_path / "scope.sqlite3"
    projects = ProjectStore(database)
    alpha = projects.create_project(namespace="p3-11-alpha", display_name="Alpha")
    beta = projects.create_project(namespace="p3-11-beta", display_name="Beta")
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    content = objects.put(b"p3-11", media_type="application/octet-stream")
    artifact = ArtifactService(database).create_artifact(
        alpha.access,
        project_ref=alpha.access.project_ref,
        role="image.retained-package",
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(content,),
        derivation_type="image.scope-fixture",
        metadata={},
    )
    with pytest.raises(ArtifactScopeError):
        ArtifactService(database).get_artifact(beta.access, artifact.artifact_ref)


def test_p3_11_final_retained_package_import(tmp_path: Path) -> None:
    package_value = os.environ.get("MINITZ_P3_11_RETAINED_PACKAGE")
    if not package_value:
        pytest.skip("MINITZ_P3_11_RETAINED_PACKAGE is not configured")
    package_path = Path(package_value).expanduser()
    package = _discover_package(package_path)
    output_value = os.environ.get("MINITZ_P3_11_EVIDENCE_OUT")
    output_target = (
        Path(output_value).expanduser()
        if output_value
        else Path("/root/minitz/evidence/p3-11/P3_11_ENGINE_EVIDENCE.json")
    )
    imported = _import_engine_evidence(
        package,
        package_path,
        tmp_path,
        output_target=output_target,
    )
    assert imported["schema"] == _OUTPUT_SCHEMA
    assert imported["unresolved_failures"] == 0
