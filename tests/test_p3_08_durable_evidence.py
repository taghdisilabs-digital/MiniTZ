"""Durable Engine evidence for a retained REAL P3-08 environment package."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import time
from typing import cast
from xml.etree import ElementTree

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


_SCHEMA = "minitz.p3-08.final-real-evidence/v1"
_KPI_SCHEMA = "minitz.p3-08.prompt-kpis/v1"
_KPI_NAMES = (
    "environment_style_globalized",
    "untracked_placed_asset_sources",
    "engine_specific_world_structure_in_kernel",
    "global_environment_budget",
    "stale_environment_integration_accepted",
)
_BRANCH_NAMES = ("terrain", "structure", "vegetation", "material")
_MANIFEST_PATH = "evidence/manifest.json"
_CHECKSUM_PATH = "evidence/manifest.sha256"
_OVERLAY_CHECKSUM_PATH = "evidence/overlay-files.sha256"
_MAX_PACKAGE_BYTES = 512 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
_MAX_MEMBERS = 4096
_MAX_JSON_BYTES = 32 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}")
_GIT_OBJECT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_CATEGORY_ORDER = {
    "package": 0,
    "process": 1,
    "editable": 2,
    "export": 3,
    "preview": 4,
    "report": 5,
    "game": 6,
    "junit": 7,
    "integration": 8,
    "manifest": 9,
}
_ROLES = {
    "package": "environment.retained-package",
    "process": "environment.process-evidence",
    "editable": "environment.editable-source",
    "export": "environment.export",
    "preview": "environment.preview",
    "report": "environment.validation-report",
    "game": "environment.game-output",
    "junit": "environment.junit-report",
    "integration": "environment.integration-manifest",
    "manifest": "environment.source-manifest",
}


@dataclass(frozen=True)
class _RetainedEvidence:
    logical_path: str
    category: str
    payload: bytes
    media_type: str
    archive_member: bool = True

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class _PackageEvidence:
    retained: tuple[_RetainedEvidence, ...]
    manifest: Mapping[str, object]
    source: Mapping[str, object]
    kpis: Mapping[str, int]
    junit: Mapping[str, object]
    environment_report: Mapping[str, object]
    export_report: Mapping[str, object]
    reopen_report: Mapping[str, object]
    integration_manifest: Mapping[str, object]
    game_output: Mapping[str, object] | None
    paths: Mapping[str, str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _quantity(value: float, source: QuantitySource) -> ResourceQuantity:
    return ResourceQuantity(
        value,
        "count",
        source,
        "resource-source://p3-08/durable-evidence/slots",
    )


def _parse_json(payload: bytes, *, source: str) -> Mapping[str, object]:
    def reject_nonfinite(value: str) -> object:
        raise AssertionError(f"Non-finite JSON value {value!r} in {source}")

    document = json.loads(payload, parse_constant=reject_nonfinite)
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
    assert parsed.as_posix() == value and all(part not in {"", "."} for part in parsed.parts)
    return value


def _media_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "application/gzip"
    return {
        ".blend": "application/x-blender",
        ".glb": "model/gltf-binary",
        ".json": "application/json",
        ".log": "text/plain",
        ".png": "image/png",
        ".txt": "text/plain",
        ".xml": "application/xml",
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
    overlay_count = source.get("overlay_count")
    assert isinstance(overlay_count, int) and not isinstance(overlay_count, bool)
    assert overlay_count == len(overlays), "stale source overlay count"
    normalized: dict[str, str] = {}
    for raw in overlays:
        overlay = _mapping(raw, "source overlay")
        path = _safe_relative(overlay.get("path"), "source overlay path")
        digest = _sha(overlay.get("sha256"), "source overlay digest")
        assert path not in normalized, f"duplicate source overlay: {path}"
        normalized[path] = digest
    if normalized:
        assert _OVERLAY_CHECKSUM_PATH in files, "source overlay checksum manifest missing"
        observed = _checksum_lines(
            files[_OVERLAY_CHECKSUM_PATH], source=_OVERLAY_CHECKSUM_PATH
        )
        assert observed == normalized, "stale source overlay identity"
    return {
        "commit": commit,
        "tree": tree,
        "overlay_count": overlay_count,
        "overlays": tuple(
            {"path": path, "sha256": normalized[path]} for path in sorted(normalized)
        ),
    }


def _zero_kpis(manifest: Mapping[str, object]) -> Mapping[str, int]:
    prompt = _mapping(manifest.get("prompt_kpis"), "prompt_kpis")
    assert prompt.get("schema") == _KPI_SCHEMA
    assert prompt.get("all_five_zero") is True
    values = _mapping(prompt.get("kpis"), "prompt KPI values")
    assert set(values) == set(_KPI_NAMES), "prompt KPI names differ"
    normalized: dict[str, int] = {}
    for name in _KPI_NAMES:
        value = values[name]
        assert isinstance(value, int) and not isinstance(value, bool) and value == 0
        normalized[name] = value
    return normalized


def _junit_summary(payload: bytes) -> Mapping[str, object]:
    root = ElementTree.fromstring(payload)
    cases: list[str] = []
    failures = errors = skipped = 0
    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname")
        name = testcase.attrib.get("name")
        assert classname and name
        cases.append(f"{classname}::{name}")
        failures += len(testcase.findall("failure"))
        errors += len(testcase.findall("error"))
        skipped += len(testcase.findall("skipped"))
    assert cases
    assert failures == errors == skipped == 0, "retained qualification is unresolved"
    joined = "\n".join(cases)
    for module in (
        "test_p3_08_environment_pack",
        "test_p3_08_three_d_environment_real",
    ):
        assert module in joined, f"required P3-08 qualification missing: {module}"
    return {
        "cases": tuple(sorted(cases)),
        "errors": errors,
        "failures": failures,
        "skipped": skipped,
        "tests": len(cases),
    }


def _successful_process_record(document: Mapping[str, object]) -> bool:
    processes = document.get("processes")
    if isinstance(processes, Sequence) and not isinstance(
        processes, (str, bytes, bytearray)
    ):
        return bool(processes) and all(
            isinstance(item, Mapping)
            and item.get("exit_code") == 0
            and item.get("failure") in {None, ""}
            for item in processes
        )
    return (
        document.get("status") == "SUCCEEDED"
        and document.get("exit_code") == 0
        and document.get("failure") in {None, ""}
    )


def _one_document(
    documents: Mapping[str, Mapping[str, object]],
    predicate: Callable[[Mapping[str, object]], bool],
    label: str,
) -> tuple[str, Mapping[str, object]]:
    matches = [(path, document) for path, document in documents.items() if predicate(document)]
    assert len(matches) == 1, (label, tuple(path for path, _ in matches))
    return matches[0]


def _member_for_digest(
    checksums: Mapping[str, str], digest: str, suffix: str, label: str
) -> str:
    candidates = [
        path
        for path, observed in checksums.items()
        if observed == digest and path.lower().endswith(suffix.lower())
    ]
    full = [path for path in candidates if path.startswith("full-tmp/")]
    selected = full if full else candidates
    assert len(selected) == 1, (label, tuple(selected))
    return selected[0]


def _output_digest(report: Mapping[str, object], label: str) -> str:
    output = _mapping(report.get("output"), f"{label} output")
    return _sha(output.get("sha256"), f"{label} output digest")


def _integration_document(document: Mapping[str, object]) -> bool:
    required = {
        "collision_ref",
        "content_sha256",
        "material_ref",
        "navigation_ref",
        "partition_ref",
        "placed_assets",
        "specification",
        "terrain",
    }
    return required <= set(document)


def _validate_integration_manifest(
    integration: Mapping[str, object],
    environment_report: Mapping[str, object],
    editable_sha256: str,
) -> None:
    assert _sha(integration.get("content_sha256"), "integration content") == editable_sha256
    project_ref = integration.get("project_ref")
    assert isinstance(project_ref, str) and project_ref
    specification = _mapping(integration.get("specification"), "environment specification")
    assert specification.get("project_ref") == project_ref
    assert _sha(specification.get("content_sha256"), "specification content") == editable_sha256
    source_ref = _ref(specification.get("source_ref"), "specification source")
    library_refs = _sequence(specification.get("asset_library_refs"), "asset library refs")
    assert library_refs and all(_REF.fullmatch(cast(str, item)) for item in library_refs)

    terrain = _mapping(integration.get("terrain"), "terrain")
    assert terrain.get("project_ref") == project_ref
    _ref(terrain.get("generator_ref"), "terrain generator")
    version = terrain.get("generator_version")
    assert isinstance(version, str) and _VERSION.fullmatch(version)
    config = _mapping(terrain.get("config"), "terrain config")
    assert config and all(isinstance(key, str) and key for key in config)
    seed = terrain.get("seed")
    assert isinstance(seed, int) and not isinstance(seed, bool) and seed >= 0
    assert terrain.get("terrain_ref") == source_ref
    assert _sha(terrain.get("content_sha256"), "terrain content") == editable_sha256

    identity = _mapping(environment_report.get("environment_identity"), "environment identity")
    assert identity.get("seed") == seed
    _sha(identity.get("layout_sha256"), "environment layout")
    reported_assets = _sequence(identity.get("placed_assets"), "reported placed assets")
    placed_assets = _sequence(integration.get("placed_assets"), "integration placed assets")
    assert placed_assets and len(placed_assets) == len(reported_assets)
    observed_by_id = {
        cast(str, _mapping(item, "reported asset").get("asset_id")): _mapping(
            item, "reported asset"
        )
        for item in reported_assets
    }
    assert len(observed_by_id) == len(reported_assets)
    placed_sources: set[str] = set()
    for raw in placed_assets:
        asset = _mapping(raw, "integration placed asset")
        assert asset.get("project_ref") == project_ref
        asset_id = asset.get("asset_id")
        assert isinstance(asset_id, str) and asset_id in observed_by_id
        observed = observed_by_id[asset_id]
        asset_ref = _ref(asset.get("source_ref"), "placed asset source")
        asset_sha = _sha(asset.get("content_sha256"), "placed asset content")
        placed_sources.add(asset_ref)
        transform = _sequence(asset.get("transform"), "placed asset transform")
        assert len(transform) == 16 and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in transform
        )
        _ref(asset.get("material_ref"), "placed asset material")
        assert observed.get("artifact_ref") == asset_ref
        assert observed.get("content_sha256") == asset_sha
        for field in ("material_ref", "parent_ref", "partition_id", "transform", "variant"):
            assert observed.get(field) == asset.get(field), (asset_id, field)
    assert set(cast(Sequence[str], library_refs)) == placed_sources
    for field in (
        "structure_ref",
        "prop_ref",
        "vegetation_ref",
        "material_ref",
        "collision_ref",
        "navigation_ref",
        "partition_ref",
        "tool_ref",
        "runtime_ref",
        "derivation_ref",
    ):
        _ref(integration.get(field), f"integration {field}")


def _game_output(
    manifest: Mapping[str, object],
    checksums: Mapping[str, str],
) -> Mapping[str, object] | None:
    raw = manifest.get("game_output")
    if raw is None:
        return None
    game = _mapping(raw, "game_output")
    assert game.get("reality") == "REAL", "supplied game output is not REAL"
    path = _safe_relative(game.get("path"), "game output path")
    assert path in checksums
    assert _sha(game.get("sha256"), "game output digest") == checksums[path]
    return dict(game)


def _discover_package(package_value: str | Path) -> _PackageEvidence:
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
            member_path = PurePosixPath(member.name)
            assert member.name and not member_path.is_absolute() and ".." not in member_path.parts, (
                "unsafe archive member"
            )
            assert member.name.rstrip("/") == member_path.as_posix()
            assert member.name not in seen, "duplicate archive member"
            seen.add(member.name)
            assert member.isfile() or member.isdir(), "archive members must be regular files"
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
    assert set(checksums) == set(files) - {_CHECKSUM_PATH}, "checksum manifest is not exhaustive"
    for checksum_path, digest in checksums.items():
        assert hashlib.sha256(files[checksum_path]).hexdigest() == digest, (
            f"forged package member: {checksum_path}"
        )

    manifest = _parse_json(files[_MANIFEST_PATH], source=_MANIFEST_PATH)
    assert manifest.get("schema") == _SCHEMA
    payload_rows = _sequence(_mapping(manifest.get("payload"), "payload").get("files"), "payload files")
    indexed: dict[str, Mapping[str, object]] = {}
    for raw in payload_rows:
        row = _mapping(raw, "payload file")
        payload_path = _safe_relative(row.get("path"), "payload path")
        assert payload_path not in indexed
        indexed[payload_path] = row
    assert set(indexed) == set(files) - {_MANIFEST_PATH, _CHECKSUM_PATH}
    for payload_path, row in indexed.items():
        assert _sha(row.get("sha256"), "payload digest") == checksums[payload_path]
        size = row.get("size")
        assert isinstance(size, int) and not isinstance(size, bool) and size == len(files[payload_path])

    source = _source_identity(manifest, files)
    kpis = _zero_kpis(manifest)
    unresolved = manifest.get("unresolved_failures")
    assert isinstance(unresolved, int) and not isinstance(unresolved, bool) and unresolved == 0

    documents: dict[str, Mapping[str, object]] = {}
    for document_path, payload in files.items():
        if document_path.endswith(".json") and len(payload) <= _MAX_JSON_BYTES:
            documents[document_path] = _parse_json(payload, source=document_path)
    environment_path, environment_report = _one_document(
        documents,
        lambda item: item.get("operation") == "environment"
        and isinstance(item.get("environment_identity"), Mapping)
        and isinstance(item.get("output"), Mapping),
        "REAL Blender environment report",
    )
    runtime = _mapping(environment_report.get("runtime"), "Blender runtime")
    assert any("blender" in str(value).lower() for value in runtime.values()), (
        "environment report lacks REAL Blender runtime identity"
    )
    editable_sha = _output_digest(environment_report, "environment")
    editable_path = _member_for_digest(checksums, editable_sha, ".blend", "editable environment")

    export_path, export_report = _one_document(
        documents,
        lambda item: item.get("operation") in {"convert", "export"}
        and str(item.get("output_path", "")).lower().endswith(".glb")
        and isinstance(item.get("output"), Mapping),
        "environment export report",
    )
    export_sha = _output_digest(export_report, "environment export")
    glb_path = _member_for_digest(checksums, export_sha, ".glb", "environment GLB")

    reopen_path, reopen_report = _one_document(
        documents,
        lambda item: isinstance(item.get("inspection"), Mapping)
        and cast(Mapping[str, object], item["inspection"]).get("source_format") == "GLTF"
        and isinstance(item.get("inspection_subject"), Mapping)
        and cast(Mapping[str, object], item["inspection_subject"]).get("sha256")
        == export_sha,
        "environment GLB reopen report",
    )
    integration_path, integration = _one_document(
        documents, _integration_document, "environment integration manifest"
    )
    _validate_integration_manifest(integration, environment_report, editable_sha)

    preview_candidates = [
        path
        for path, payload in files.items()
        if path.lower().endswith(".png") and payload.startswith(b"\x89PNG\r\n\x1a\n")
    ]
    full_previews = [path for path in preview_candidates if path.startswith("full-tmp/")]
    previews = full_previews if full_previews else preview_candidates
    assert len(previews) == 1, ("environment preview", tuple(previews))
    preview_path = previews[0]

    junit_candidates = [
        path
        for path, payload in files.items()
        if path.lower().endswith(".xml") and b"<testcase" in payload
    ]
    full_junit = [path for path in junit_candidates if path.endswith("full-junit.xml")]
    junit_paths = full_junit if full_junit else junit_candidates
    assert len(junit_paths) == 1, ("JUnit report", tuple(junit_paths))
    junit_path = junit_paths[0]
    junit = _junit_summary(files[junit_path])

    process_paths = [
        path for path, document in documents.items() if _successful_process_record(document)
    ]
    assert process_paths, "successful REAL process evidence is absent"
    game = _game_output(manifest, checksums)
    if game is not None:
        assert "test_p3_08_game_bridge_real" in "\n".join(
            cast(Sequence[str], junit["cases"])
        )

    selected_categories = {
        _CHECKSUM_PATH: "process",
        _MANIFEST_PATH: "manifest",
        environment_path: "report",
        export_path: "report",
        reopen_path: "report",
        integration_path: "integration",
        editable_path: "editable",
        glb_path: "export",
        preview_path: "preview",
        junit_path: "junit",
        **{path: "process" for path in process_paths},
    }
    if _OVERLAY_CHECKSUM_PATH in files:
        selected_categories[_OVERLAY_CHECKSUM_PATH] = "process"
    prompt_report_path = "evidence/prompt-kpi-report.json"
    if prompt_report_path in files:
        assert documents[prompt_report_path] == manifest["prompt_kpis"]
        selected_categories[prompt_report_path] = "report"
    if game is not None:
        selected_categories[cast(str, game["path"])] = "game"

    retained = [
        _RetainedEvidence(
            f"retained-package/{package_path.name}",
            "package",
            package_payload,
            _media_type(package_path.name),
            archive_member=False,
        )
    ]
    retained.extend(
        _RetainedEvidence(path, category, files[path], _media_type(path))
        for path, category in sorted(
            selected_categories.items(),
            key=lambda item: (_CATEGORY_ORDER[item[1]], item[0]),
        )
    )
    paths = {
        "editable": editable_path,
        "environment_report": environment_path,
        "export": glb_path,
        "export_report": export_path,
        "integration": integration_path,
        "junit": junit_path,
        "manifest": _MANIFEST_PATH,
        "preview": preview_path,
        "process": sorted(process_paths)[0],
        "reopen_report": reopen_path,
    }
    return _PackageEvidence(
        tuple(retained),
        manifest,
        source,
        kpis,
        junit,
        environment_report,
        export_report,
        reopen_report,
        integration,
        game,
        paths,
    )


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
        role=_ROLES[evidence.category],
        content_ref=content_ref,
        source_refs=(),
        source_artifact_refs=tuple(source.artifact_ref for source in sources),
        source_content_refs=tuple(
            cast(ContentRef, source.content_ref) for source in sources
        ),
        derivation_type=(
            "environment.captured-real-evidence"
            if evidence.category == "package"
            else "environment.extracted-retained-package"
        ),
        metadata={"semantic_label": evidence.logical_path},
    )


def _output_target() -> Path | None:
    value = os.environ.get("MINITZ_P3_08_EVIDENCE_OUT")
    return Path(value).expanduser() if value else None


def _register_resource(
    database: Path, access: ProjectAccess, resource_ref: ResourceRef
) -> None:
    resources = ResourceService(database)
    resources.register_resource(
        access,
        Resource(
            resource_ref,
            "runtime.host",
            "locality://p3-08/durable-evidence/shared",
            configured_capacity={"slots": _quantity(6.0, QuantitySource.CONFIGURED)},
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
                    physical_capacity={"slots": _quantity(6.0, QuantitySource.MEASURED)},
                    effective_capacity={"slots": _quantity(6.0, QuantitySource.MEASURED)},
                    used_capacity={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                    available_capacity={"slots": _quantity(6.0, QuantitySource.MEASURED)},
                    pressure={"slots": _quantity(0.0, QuantitySource.MEASURED)},
                ),
            )
        ),
    )


def test_p3_08_retained_package_becomes_durable_engine_evidence(
    tmp_path: Path,
) -> None:
    package_value = os.environ.get("MINITZ_P3_08_RETAINED_PACKAGE")
    if not package_value:
        pytest.skip("MINITZ_P3_08_RETAINED_PACKAGE is not configured")
    package_path = _regular_package_path(package_value)
    package = _discover_package(package_path)
    commit = cast(str, package.source["commit"])
    tree = cast(str, package.source["tree"])

    database = tmp_path / "p3-08-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("environment.validate", "1.0.0")
    output_contract = {
        "branch_evidence": "schema://minitz/p3-08/durable-branch-evidence/1",
        "evidence_manifest": "schema://minitz/p3-08/durable-evidence/1",
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate exact retained REAL Blender environment evidence",
            output_contract=output_contract,
        )
    )
    projects = ProjectStore(database)
    registration = projects.create_project(
        namespace="p3-08-durable-evidence",
        display_name="P3-08 Durable Environment Evidence",
        metadata={"source_commit": commit, "source_tree": tree},
    )
    access = registration.access
    project_ref = access.project_ref
    tasks = TaskRevisionService(database)
    task = tasks.create_task(
        access,
        project_ref=project_ref,
        idempotency_key="p3-08-durable-evidence-task",
        task_type="environment.durable-evidence",
        objective="Retain and validate exact REAL Blender environment outputs",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={"independent_branch_nodes": 4, "named_zero_kpis": 5},
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-08/retained-evidence",
        egress_policy_ref="policy://p3-08/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={"slots": 6},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-08/durable-evidence/run",
        lease_seconds=1800,
    )

    graph_ref = GraphRef.new(project_ref)
    branch_nodes = {
        name: Node(
            NodeRef.new(graph_ref),
            f"generic.environment.{name}-evidence",
            (capability_ref,),
            (),
            (),
            output_contract,
            None,
            "READ_ONLY",
            {"slots": 1},
            ("artifact", "content-ref", "provenance", "runtime"),
        )
        for name in _BRANCH_NAMES
    }
    integration_node = Node(
        NodeRef.new(graph_ref),
        "generic.environment.integration-evidence",
        (capability_ref,),
        tuple(node.node_ref for node in branch_nodes.values()),
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
        nodes=(*branch_nodes.values(), integration_node),
        compiler_identity="compiler://p3-08/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    assert graph.graph_ref.revision == 1
    assert graphs.get_graph(access, graph_ref) == graph
    assert integration_node.dependencies == tuple(
        sorted(
            (node.node_ref for node in branch_nodes.values()),
            key=lambda item: item.node_id,
        )
    )

    executions = NodeExecutionService(database)
    prepared = executions.prepare_run(access, run.run_ref)
    by_ref = {item.node_ref: item for item in prepared}
    assert all(by_ref[node.node_ref].status == "READY" for node in branch_nodes.values())
    assert by_ref[integration_node.node_ref].status in {"CREATED", "QUEUED"}

    resource_ref = ResourceRef(
        project_ref,
        "res_" + hashlib.sha256(f"p3-08:{project_ref.value}".encode()).hexdigest()[:32],
    )
    _register_resource(database, access, resource_ref)
    scheduler = Scheduler(database)

    def dispatch(label: str, node: Node, lease_seconds: float = 1800.0) -> ScheduledDispatch:
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
                side_effect_targets=(f"evidence://p3-08/{label}",),
            ),
            authority_attempt=run_attempt,
            owner_ref=f"worker://p3-08/durable-evidence/{label}",
            lease_seconds=1800,
            idempotency_key=f"p3-08-{label}-reserve",
        )
        return scheduler.dispatch(
            access,
            allocation,
            authority_attempt=run_attempt,
            lease_seconds=lease_seconds,
            idempotency_key=f"p3-08-{label}-dispatch",
        )

    branch_dispatches = {
        name: dispatch(name, branch_nodes[name])
        for name in ("terrain", "structure", "vegetation")
    }
    failed_material = dispatch("material-initial", branch_nodes["material"], 30.0)
    time.sleep(30.1)
    recovered_states = executions.recover_expired_execution(access, run.run_ref)
    recovered_by_ref = {item.node_ref: item for item in recovered_states}
    assert recovered_by_ref[branch_nodes["material"].node_ref].status == "READY"
    assert all(
        recovered_by_ref[branch_nodes[name].node_ref].status == "RUNNING"
        for name in ("terrain", "structure", "vegetation")
    )
    material_history = executions.list_node_history(
        access, branch_nodes["material"].node_ref
    )
    assert any(
        state.status == "STALE"
        and state.current_attempt_id == failed_material.node_attempt.attempt_id
        for state in material_history
    )
    recovered_allocations = scheduler.recover_expired_allocations(access, project_ref)
    assert tuple(item.allocation_ref for item in recovered_allocations) == (
        failed_material.allocation.allocation_ref,
    )
    assert recovered_allocations[0].status == "EXPIRED"
    recovered_material = dispatch("material-recovery", branch_nodes["material"])
    branch_dispatches["material"] = recovered_material
    assert recovered_material.node_attempt.attempt_id != failed_material.node_attempt.attempt_id
    assert recovered_material.node_attempt.fence == failed_material.node_attempt.fence + 1
    assert len(
        {item.node_attempt.attempt_id for item in branch_dispatches.values()}
    ) == 4
    assert len(
        {item.allocation.allocation_ref for item in branch_dispatches.values()}
    ) == 4

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
            assert evidence.category == "package"
            package_artifact = artifact
        published.append((evidence, artifact))
    assert package_artifact is not None
    artifacts_by_path = {
        evidence.logical_path: artifact for evidence, artifact in published
    }
    manifest_artifact = artifacts_by_path[package.paths["manifest"]]
    integration_artifact = artifacts_by_path[package.paths["integration"]]
    process_artifact = artifacts_by_path[package.paths["process"]]
    branch_artifacts = {
        "terrain": integration_artifact,
        "structure": artifacts_by_path[package.paths["editable"]],
        "vegetation": artifacts_by_path[package.paths["preview"]],
        "material": artifacts_by_path[package.paths["environment_report"]],
    }
    assert len({item.artifact_ref for item in branch_artifacts.values()}) == 4
    for _, artifact in published:
        assert artifacts.get_artifact(access, artifact.artifact_ref) == artifact
        assert objects.verify(cast(ContentRef, artifact.content_ref)) is True

    completed_branches = {}
    for name in _BRANCH_NAMES:
        branch_artifact = branch_artifacts[name]
        dispatch_record = branch_dispatches[name]
        completed = executions.finalize_node(
            access,
            dispatch_record.node_attempt,
            outputs={
                "branch_evidence": branch_artifact.artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": branch_artifact.artifact_ref,
                "content-ref": cast(ContentRef, branch_artifact.content_ref),
                "provenance": package_artifact.artifact_ref,
                "runtime": process_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key=f"p3-08-{name}-finalize",
        )
        assert completed.status == "SUCCEEDED"
        completed_branches[name] = completed

    after_branches = executions.prepare_run(access, run.run_ref)
    assert {
        item.node_ref for item in after_branches if item.status == "READY"
    } == {integration_node.node_ref}
    integration_dispatch = dispatch("integration", integration_node)

    validations = ValidationService(database)
    subjects = tuple(
        validations.bind_artifact_subject(
            access,
            artifact.artifact_ref,
            producer_dimensions={
                "content_ref": cast(ContentRef, artifact.content_ref).value,
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
            "project.criteria:p3-08-environment-kpi",
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
            "criteria://p3-08/environment-durable-evidence/v1",
        ),
        idempotency_key="p3-08-durable-evidence-validation-plan",
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
                    f"Exact {kpi_name} violations in retained P3-08 REAL evidence",
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
            implementation_ref="validator://p3-08/durable-evidence/v1",
            runtime_ref="runtime://blender/retained-real-environment",
            validator_dimensions={
                "implementation": "validator://p3-08/durable-evidence/v1",
                "runtime": "runtime://blender/retained-real-environment",
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-08-result-{check.check_id}",
        )
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
        if isinstance(kpi_name, str):
            assert result.metrics[0].name == kpi_name
            assert result.metrics[0].value == 0.0
            kpi_result_names.add(kpi_name)
        results.append(result)
    assert kpi_result_names == set(_KPI_NAMES)
    aggregate = validations.aggregate(
        access,
        integration_dispatch.node_attempt,
        plan.plan_ref,
        idempotency_key="p3-08-durable-evidence-validation-aggregate",
    )
    assert aggregate.verdict is ValidationVerdict.PASS
    assert aggregate.accepted is True
    assert aggregate.evidence_state is ValidationEvidenceState.CURRENT
    assert aggregate.missing_required_check_ids == ()

    events = EventLedger(database)
    event = events.append_event(
        access,
        project_ref=project_ref,
        task_ref=task.task_ref,
        run_ref=run.run_ref,
        graph_ref=graph_ref,
        node_ref=integration_node.node_ref,
        event_type="P3_08_DURABLE_EVIDENCE_RETAINED",
        idempotency_key="p3-08-durable-evidence-retained",
        actor_ref="worker://p3-08/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for _, artifact in published),
        metadata={
            "artifact_count": len(published),
            "branch_count": 4,
            "kpi_count": 5,
            "recovered_attempt_id": recovered_material.node_attempt.attempt_id,
            "source_commit": commit,
            "source_tree": tree,
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
        },
        payload_ref=cast(ContentRef, manifest_artifact.content_ref),
        authority_attempt=run_attempt,
    )
    assert events.get_event(access, event.event_ref) == event
    acceptance = executions.record_run_acceptance(
        access,
        run.run_ref,
        criterion="validation.success_rule=ALL_REQUIRED_PASS",
        evidence_ref=integration_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-08-durable-evidence-acceptance",
    )
    integration_completed = executions.finalize_node(
        access,
        integration_dispatch.node_attempt,
        outputs={
            "branch_evidence": integration_artifact.artifact_ref,
            "evidence_manifest": manifest_artifact.artifact_ref,
        },
        evidence={
            "artifact": integration_artifact.artifact_ref,
            "content-ref": cast(ContentRef, integration_artifact.content_ref),
            "provenance": artifacts_by_path[package.paths["export"]].artifact_ref,
            "runtime": process_artifact.artifact_ref,
        },
        acceptance_criteria=(),
        idempotency_key="p3-08-integration-finalize",
    )
    assert integration_completed.status == "SUCCEEDED"
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"
    assert graphs.get_graph(access, graph_ref) == graph
    released = scheduler.reconcile_terminal(access, run.run_ref)
    assert len(released) == 5
    assert all(item.status == "RELEASED" for item in released)
    terminal_allocations = (*recovered_allocations, *released)
    assert len(terminal_allocations) == 6
    assert len({item.allocation_ref for item in terminal_allocations}) == 6

    output_manifest = {
        "schema": "minitz.p3-08.durable-engine-evidence/v1",
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
        },
        "project": {
            "project_ref": project_ref.value,
            "task_ref": {
                "project_ref": task.task_ref.project_ref.value,
                "task_id": task.task_ref.task_id,
                "revision": task.task_ref.revision,
            },
            "task_sha256": task.record_sha256,
        },
        "run": {
            "acceptance_event_ref": acceptance.event_ref.value,
            "run_ref": {
                "project_ref": run.run_ref.project_ref.value,
                "run_id": run.run_ref.run_id,
            },
            "state_sha256": completed_run.state_sha256,
            "status": completed_run.status,
        },
        "graph": {
            "graph_ref": graph_ref.value,
            "record_sha256": graph.record_sha256,
            "semantic_digest": graph.semantic_digest,
        },
        "branches": [
            {
                "allocation_ref": branch_dispatches[name].allocation.allocation_ref.value,
                "artifact_ref": branch_artifacts[name].artifact_ref.value,
                "attempt_id": branch_dispatches[name].node_attempt.attempt_id,
                "name": name,
                "node_ref": branch_nodes[name].node_ref.value,
                "status": completed_branches[name].status,
            }
            for name in _BRANCH_NAMES
        ],
        "recovery": {
            "failed_allocation_ref": failed_material.allocation.allocation_ref.value,
            "failed_allocation_status": recovered_allocations[0].status,
            "failed_attempt_id": failed_material.node_attempt.attempt_id,
            "failed_attempt_outcome": "STALE",
            "failure_mode": "LEASE_EXPIRED_WORKER_LOSS",
            "peer_branches_preserved": True,
            "recovered_allocation_ref": recovered_material.allocation.allocation_ref.value,
            "recovered_attempt_id": recovered_material.node_attempt.attempt_id,
        },
        "integration": {
            "artifact_ref": integration_artifact.artifact_ref.value,
            "node_ref": integration_node.node_ref.value,
            "status": integration_completed.status,
        },
        "kpis": dict(package.kpis),
        "game_output": (
            {"classification": "NOT_SUPPLIED"}
            if package.game_output is None
            else dict(package.game_output)
        ),
        "qualification": {
            "junit_errors": package.junit["errors"],
            "junit_failures": package.junit["failures"],
            "junit_skipped": package.junit["skipped"],
            "junit_tests": package.junit["tests"],
            "unresolved_failures": 0,
        },
        "validation": {
            "accepted": aggregate.accepted,
            "aggregate_sha256": aggregate.aggregate_sha256,
            "plan_ref": plan.plan_ref.value,
            "result_refs": [result.result_ref.value for result in results],
            "verdict": aggregate.verdict.value,
        },
        "event": {"event_ref": event.event_ref.value, "record_sha256": event.record_sha256},
        "artifacts": [
            {
                "artifact_ref": artifact.artifact_ref.value,
                "category": evidence.category,
                "path": evidence.logical_path,
                "sha256": cast(ContentRef, artifact.content_ref).digest,
            }
            for evidence, artifact in published
        ],
    }
    assert output_manifest["kpis"] == {name: 0 for name in _KPI_NAMES}
    target = _output_target()
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(output_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        assert _parse_json(target.read_bytes(), source=str(target)) == output_manifest


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


def test_p3_08_retained_package_rejects_unsafe_regular_file_boundary(
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


def test_p3_08_retained_package_rejects_forged_named_checksum(
    tmp_path: Path,
) -> None:
    manifest_payload = json.dumps(
        _minimal_manifest(), sort_keys=True, separators=(",", ":")
    ).encode()
    archive_path = tmp_path / "forged.tar.gz"
    _write_test_archive(
        archive_path,
        {
            _MANIFEST_PATH: manifest_payload,
            _CHECKSUM_PATH: f"{'0' * 64}  {_MANIFEST_PATH}\n".encode(),
        },
    )
    with pytest.raises(AssertionError, match="forged package member"):
        _discover_package(archive_path)


def test_p3_08_retained_package_rejects_stale_source_overlay_identity(
    tmp_path: Path,
) -> None:
    manifest_payload = json.dumps(
        _minimal_manifest(overlay_count=1), sort_keys=True, separators=(",", ":")
    ).encode()
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


def test_p3_08_durable_evidence_rejects_cross_project_artifact(
    tmp_path: Path,
) -> None:
    database = tmp_path / "scope.sqlite3"
    projects = ProjectStore(database)
    alpha = projects.create_project(namespace="p3-08-alpha", display_name="Alpha")
    beta = projects.create_project(namespace="p3-08-beta", display_name="Beta")
    objects = FilesystemObjectStorageBackend(tmp_path / "scope-objects")
    content = objects.put(b"p3-08", media_type="application/octet-stream")
    artifacts = ArtifactService(database)
    artifact = artifacts.create_artifact(
        alpha.access,
        project_ref=alpha.access.project_ref,
        role="environment.retained-package",
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(content,),
        derivation_type="environment.scope-fixture",
        metadata={},
    )
    with pytest.raises(ArtifactScopeError):
        artifacts.get_artifact(beta.access, artifact.artifact_ref)
