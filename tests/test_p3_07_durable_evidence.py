"""Durable engine evidence for a retained REAL P3-07 animation package."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import cast
from xml.etree import ElementTree

import pytest

from minitz_os.engine.artifact import Artifact, ArtifactService, ContentRef
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.event import EventLedger
from minitz_os.engine.execution import NodeExecutionService
from minitz_os.engine.graph import GraphRef, GraphService, Node, NodeRef
from minitz_os.engine.object_store import FilesystemObjectStorageBackend
from minitz_os.engine.project import ProjectStore
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
from minitz_os.engine.run import RunService
from minitz_os.engine.scheduler import ResourceClaim, ScheduledDispatch, Scheduler, SchedulingRequest
from minitz_os.engine.task import TaskRevisionService
from minitz_os.engine.validation import (
    MetricMeasurement,
    ProjectValidationCriteria,
    ValidationCheck,
    ValidationEvidenceState,
    ValidationService,
    ValidationVerdict,
)


_KPI_NAMES = (
    "animation_without_exact_skeleton_identity",
    "implicit_unrecorded_bone_mapping",
    "nonfinite_values_accepted",
    "project_root_motion_policy_globalized",
    "stale_validation_reused_after_skeleton_change",
)
_REQUIRED_CASES = {
    "tests.test_p3_07_animation_pack::test_animation_pack_registers_core_optional_paths_roles_validators_and_recipe",
    "tests.test_p3_07_animation_pack::test_animation_contracts_bind_exact_character_rigs_mapping_and_policies",
    "tests.test_p3_07_three_d_animation_real::test_real_animation_actions_retarget_bake_preview_export_and_reopen",
    "tests.test_p3_07_three_d_animation_real::test_animation_specs_reject_nonfinite_transforms",
    "tests.test_p3_07_three_d_animation_real::test_independent_animation_worker_failure_recovers_without_erasing_peer",
}
_CONCURRENCY_CASE = (
    "tests.test_p3_07_three_d_animation_real::"
    "test_independent_animation_worker_failure_recovers_without_erasing_peer"
)
_MAX_PACKAGE_BYTES = 512 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
_MAX_SELECTED_MEMBERS = 40
_CATEGORY_ORDER = {
    "package": 0,
    "process": 1,
    "editable": 2,
    "glb": 3,
    "preview": 4,
    "report": 5,
    "junit": 6,
    "manifest": 7,
}
_ROLES = {
    "package": "animation.retained-package",
    "process": "animation.process-evidence",
    "editable": "animation.editable-source",
    "glb": "animation.export",
    "preview": "animation.preview",
    "report": "animation.validation-report",
    "junit": "animation.junit-report",
    "manifest": "animation.source-manifest",
}
_HEX_40 = re.compile(r"[0-9a-f]{40}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")


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
    report_documents: Mapping[str, Mapping[str, object]]
    junit: Mapping[str, object]
    test_summary: Mapping[str, object]
    kpis: Mapping[str, int]
    kpi_basis: Mapping[str, tuple[str, ...]]
    action_identity: Mapping[str, object]
    reopen_identity: Mapping[str, object]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _quantity(value: float, source: QuantitySource) -> ResourceQuantity:
    return ResourceQuantity(
        value,
        "count",
        source,
        "resource-source://p3-07/durable-evidence/slots",
    )


def _parse_json(payload: bytes, *, source: str) -> Mapping[str, object]:
    def reject_nonfinite(value: str) -> object:
        raise AssertionError(f"Non-finite JSON value {value!r} in {source}")

    document = json.loads(payload, parse_constant=reject_nonfinite)
    assert isinstance(document, Mapping), source
    return cast(Mapping[str, object], document)


def _media_type(name: str) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    return {
        ".blend": "application/x-blender",
        ".glb": "model/gltf-binary",
        ".json": "application/json",
        ".log": "text/plain",
        ".png": "image/png",
        ".txt": "text/plain",
        ".xml": "application/xml",
    }.get(suffix, "application/octet-stream")


def _is_process_record(value: object) -> bool:
    if isinstance(value, Mapping):
        if value.get("schema") == "minitz.p3-07.final-real-process/v2":
            processes = value.get("processes")
            return (
                isinstance(processes, Sequence)
                and not isinstance(processes, (str, bytes, bytearray))
                and bool(processes)
                and all(
                    isinstance(process, Mapping)
                    and isinstance(process.get("name"), str)
                    and bool(process.get("name"))
                    and isinstance(process.get("command"), str)
                    and bool(process.get("command"))
                    and process.get("exit_code") == 0
                    and isinstance(process.get("junit"), str)
                    and isinstance(process.get("log"), str)
                    for process in processes
                )
            )
        status = value.get("status")
        exit_code = value.get("exit_code")
        failure = value.get("failure")
        has_identity = any(
            key in value
            for key in ("execution_id", "pid", "process_group_id", "process_identity")
        )
        if status == "SUCCEEDED" and exit_code == 0 and failure is None and has_identity:
            return True
        return any(_is_process_record(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_is_process_record(item) for item in value)
    return False


def _kpi_mappings(value: object) -> tuple[Mapping[str, object], ...]:
    found: list[Mapping[str, object]] = []
    if isinstance(value, Mapping):
        if all(name in value for name in _KPI_NAMES):
            found.append(cast(Mapping[str, object], value))
        for item in value.values():
            found.extend(_kpi_mappings(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_kpi_mappings(item))
    return tuple(found)


def _numeric_values_for_key(value: object, fragment: str) -> tuple[float, ...]:
    values: list[float] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if (
                fragment in str(key).lower()
                and isinstance(item, (int, float))
                and not isinstance(item, bool)
                and math.isfinite(float(item))
            ):
                values.append(float(item))
            values.extend(_numeric_values_for_key(item, fragment))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            values.extend(_numeric_values_for_key(item, fragment))
    return tuple(values)


def _junit_summary(payload: bytes) -> Mapping[str, object]:
    root = ElementTree.fromstring(payload)
    cases: list[str] = []
    failures = 0
    errors = 0
    skipped = 0
    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname")
        name = testcase.attrib.get("name")
        assert classname and name
        cases.append(f"{classname}::{name}")
        failures += len(testcase.findall("failure"))
        errors += len(testcase.findall("error"))
        skipped += len(testcase.findall("skipped"))
    summary: Mapping[str, object] = {
        "cases": sorted(cases),
        "errors": errors,
        "failures": failures,
        "skipped": skipped,
        "tests": len(cases),
    }
    assert _REQUIRED_CASES <= set(cast(Sequence[str], summary["cases"]))
    assert cast(int, summary["tests"]) >= 5
    assert summary["errors"] == summary["failures"] == summary["skipped"] == 0
    return summary


def _derive_action_identity(
    validation: Mapping[str, object], reopen: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    inspection = validation.get("inspection")
    assert isinstance(inspection, Mapping)
    animation = inspection.get("animation")
    assert isinstance(animation, Mapping)
    actions = animation.get("actions")
    assert isinstance(actions, Sequence) and not isinstance(actions, (str, bytes))
    actions_by_name: dict[str, object] = {}
    for item in actions:
        assert isinstance(item, Mapping)
        name = item.get("name", item.get("clip_id"))
        assert isinstance(name, str) and name
        actions_by_name[name] = dict(item)
    assert set(actions_by_name) == {"turn-baked", "walk"}
    assert animation.get("action_count") == 2
    for item in actions_by_name.values():
        assert 72.0 in _numeric_values_for_key(item, "keyframe")
        assert 36.0 in _numeric_values_for_key(item, "fcurve")

    reopen_inspection = reopen.get("inspection")
    assert isinstance(reopen_inspection, Mapping)
    reopen_animation = reopen_inspection.get("animation")
    assert isinstance(reopen_animation, Mapping)
    reopen_actions = reopen_animation.get("actions")
    assert isinstance(reopen_actions, Sequence) and not isinstance(
        reopen_actions, (str, bytes)
    )
    reopen_actions_by_name: dict[str, object] = {}
    for item in reopen_actions:
        assert isinstance(item, Mapping)
        name = item.get("name", item.get("clip_id"))
        assert isinstance(name, str) and name
        reopen_actions_by_name[name] = dict(item)
    reopen_names = sorted(reopen_actions_by_name)
    reopen_identity: Mapping[str, object] = {
        "action_count": reopen_animation.get("action_count"),
        "action_names": reopen_names,
        "actions": reopen_actions_by_name,
        "exact_action_identity_supported": bool(reopen_names),
        "source_format": reopen_inspection.get("source_format"),
    }
    assert reopen_identity["source_format"] == "GLTF"
    if reopen_names:
        assert set(reopen_names) == {"turn-baked", "walk"}
        stable_fields = (
            "baked",
            "clip_id",
            "clip_sha256",
            "end_frame",
            "loop_error",
            "loop_tolerance",
            "retarget_sha256",
            "root_motion_policy",
            "source_fcurve_count",
            "source_keyframe_count",
            "source_skeleton_sha256",
            "start_frame",
            "target_skeleton_sha256",
        )
        for name in reopen_names:
            before = cast(Mapping[str, object], actions_by_name[name])
            after = cast(Mapping[str, object], reopen_actions_by_name[name])
            for field in stable_fields:
                if field in before or field in after:
                    assert before.get(field) == after.get(field), (name, field)
    else:
        assert reopen_identity["action_count"] == 0
    return actions_by_name, reopen_identity


def _derive_zero_kpis(
    manifest: Mapping[str, object],
    reports: Mapping[str, Mapping[str, object]],
    junit: Mapping[str, object],
    validation_path: str,
) -> tuple[Mapping[str, int], Mapping[str, tuple[str, ...]]]:
    validation = reports[validation_path]
    assert validation.get("valid") is True
    checks = validation.get("checks")
    assert isinstance(checks, Mapping) and checks
    assert all(value is True for value in checks.values())
    identity = validation.get("character_identity")
    assert isinstance(identity, Mapping)
    skeleton_sha256 = identity.get("skeleton_sha256")
    assert isinstance(skeleton_sha256, str) and _HEX_64.fullmatch(skeleton_sha256)
    inspection_subject = validation.get("inspection_subject")
    assert isinstance(inspection_subject, Mapping)
    subject_sha256 = inspection_subject.get("sha256")
    assert isinstance(subject_sha256, str) and _HEX_64.fullmatch(subject_sha256)
    request_sha256 = validation.get("request_sha256")
    assert isinstance(request_sha256, str) and _HEX_64.fullmatch(request_sha256)

    serialized_reports = json.dumps(reports, sort_keys=True, separators=(",", ":")).lower()
    assert "mapping" in serialized_reports
    assert "root_motion" in serialized_reports
    assert "retarget" in serialized_reports
    assert "bake" in serialized_reports
    cases = set(cast(Sequence[str], junit["cases"]))
    assert _CONCURRENCY_CASE in cases
    assert any("reject_nonfinite" in case for case in cases)

    if manifest.get("schema") == "minitz.p3-07.final-real-evidence/v2":
        prompt_kpis = manifest.get("prompt_kpis")
        assert isinstance(prompt_kpis, Mapping)
        assert prompt_kpis.get("schema") == "minitz.p3-07.prompt-kpis/v3"
        assert prompt_kpis.get("all_five_zero") is True
        prompt_values = prompt_kpis.get("kpis")
        assert isinstance(prompt_values, Mapping)
        assert set(prompt_values) == set(_KPI_NAMES)
        assert all(prompt_values[name] == 0 for name in _KPI_NAMES)

    authoritative = _kpi_mappings(manifest)
    for report in reports.values():
        authoritative += _kpi_mappings(report)
    if authoritative:
        first_mapping = authoritative[0]
        observed: dict[str, int] = {}
        for name in _KPI_NAMES:
            value = first_mapping[name]
            assert isinstance(value, int) and not isinstance(value, bool)
            observed[name] = value
        for mapping in authoritative:
            comparison: dict[str, int] = {}
            for name in _KPI_NAMES:
                value = mapping[name]
                assert isinstance(value, int) and not isinstance(value, bool)
                comparison[name] = value
            assert comparison == observed
    else:
        observed = {name: 0 for name in _KPI_NAMES}
    assert set(observed) == set(_KPI_NAMES)
    assert all(value == 0 for value in observed.values())

    contract_case = (
        "tests.test_p3_07_animation_pack::"
        "test_animation_contracts_bind_exact_character_rigs_mapping_and_policies"
    )
    real_case = (
        "tests.test_p3_07_three_d_animation_real::"
        "test_real_animation_actions_retarget_bake_preview_export_and_reopen"
    )
    nonfinite_case = (
        "tests.test_p3_07_three_d_animation_real::"
        "test_animation_specs_reject_nonfinite_transforms"
    )
    basis = {
        "animation_without_exact_skeleton_identity": (
            validation_path,
            f"skeleton_sha256:{skeleton_sha256}",
            real_case,
        ),
        "implicit_unrecorded_bone_mapping": (
            validation_path,
            contract_case,
            real_case,
        ),
        "nonfinite_values_accepted": (nonfinite_case, "strict-json-nonfinite-rejection"),
        "project_root_motion_policy_globalized": (
            validation_path,
            contract_case,
            real_case,
        ),
        "stale_validation_reused_after_skeleton_change": (
            validation_path,
            f"request_sha256:{request_sha256}",
            f"inspection_subject_sha256:{subject_sha256}",
            f"skeleton_sha256:{skeleton_sha256}",
        ),
    }
    return observed, basis


def _discover_package(package_path: Path) -> _PackageEvidence:
    package_payload = package_path.read_bytes()
    assert 0 < len(package_payload) <= _MAX_PACKAGE_BYTES
    cache: dict[str, bytes] = {}
    selected: dict[str, _RetainedEvidence] = {}
    report_documents: dict[str, Mapping[str, object]] = {}

    with tarfile.open(fileobj=BytesIO(package_payload), mode="r:*") as archive:
        members: dict[str, tarfile.TarInfo] = {}
        uncompressed_bytes = 0
        for archive_member_info in archive.getmembers():
            path = PurePosixPath(archive_member_info.name)
            assert archive_member_info.name and not path.is_absolute()
            assert ".." not in path.parts
            if archive_member_info.issym():
                target = PurePosixPath(archive_member_info.linkname)
                assert archive_member_info.linkname and not target.is_absolute()
                resolved_parts: list[str] = []
                for part in (path.parent / target).parts:
                    if part in ("", "."):
                        continue
                    if part == "..":
                        assert resolved_parts, (
                            archive_member_info.name,
                            archive_member_info.linkname,
                        )
                        resolved_parts.pop()
                    else:
                        resolved_parts.append(part)
                assert resolved_parts
            else:
                assert archive_member_info.isfile() or archive_member_info.isdir()
            assert archive_member_info.name not in members
            members[archive_member_info.name] = archive_member_info
            if archive_member_info.isfile():
                assert 0 <= archive_member_info.size <= _MAX_PACKAGE_BYTES
                uncompressed_bytes += archive_member_info.size
        assert uncompressed_bytes <= _MAX_UNCOMPRESSED_BYTES

        def read(name: str) -> bytes:
            if name not in cache:
                selected_member = members.get(name)
                assert selected_member is not None and selected_member.isfile(), name
                stream = archive.extractfile(selected_member)
                assert stream is not None
                payload = stream.read()
                assert len(payload) == selected_member.size
                cache[name] = payload
            return cache[name]

        manifest_path = "evidence/manifest.json"
        manifest_payload = read(manifest_path)
        manifest = _parse_json(manifest_payload, source=manifest_path)
        schema = manifest.get("schema")
        assert schema in {
            "minitz.p3-07.l40s-baseline-evidence/v1",
            "minitz.p3-07.final-real-evidence/v2",
        }
        is_v2 = schema == "minitz.p3-07.final-real-evidence/v2"
        checksum_lines = read("evidence/manifest.sha256").decode("ascii").splitlines()
        checksums: dict[str, str] = {}
        for line in checksum_lines:
            digest, name = line.split(maxsplit=1)
            name = name.removeprefix("*")
            assert len(digest) == 64
            assert all(character in "0123456789abcdef" for character in digest)
            assert name not in checksums
            member = members.get(name)
            assert member is not None and member.isfile(), name
            assert hashlib.sha256(read(name)).hexdigest() == digest
            checksums[name] = digest
        assert checksums[manifest_path] == hashlib.sha256(manifest_payload).hexdigest()

        payload_section = manifest.get("payload")
        assert isinstance(payload_section, Mapping)
        payload_rows = payload_section.get("files")
        assert isinstance(payload_rows, Sequence) and not isinstance(
            payload_rows, (str, bytes)
        )
        indexed_rows: dict[str, Mapping[str, object]] = {}
        for row in payload_rows:
            assert isinstance(row, Mapping)
            row_name = row.get("path")
            row_digest = row.get("sha256")
            v1_size = row.get("bytes")
            v2_size = row.get("size")
            if v1_size is not None and v2_size is not None:
                assert v1_size == v2_size
            size = v2_size if v2_size is not None else v1_size
            assert isinstance(row_name, str) and row_name not in indexed_rows
            assert isinstance(row_digest, str) and _HEX_64.fullmatch(row_digest)
            assert isinstance(size, int) and size >= 0
            indexed_rows[row_name] = {
                "path": row_name,
                "sha256": row_digest,
                "size": size,
            }

        def add(name: str, category: str) -> None:
            payload = read(name)
            if name not in {manifest_path, "evidence/manifest.sha256"}:
                row = indexed_rows.get(name)
                assert row is not None, name
                assert row["size"] == len(payload)
                assert row["sha256"] == hashlib.sha256(payload).hexdigest()
            evidence = _RetainedEvidence(name, category, payload, _media_type(name))
            prior = selected.setdefault(name, evidence)
            assert prior == evidence

        def unique_suffix(suffix: str) -> str:
            matches = [
                name
                for name, member in members.items()
                if member.isfile()
                and name.endswith("/" + suffix)
                and "/.minitz-three-d-stage-" not in name
            ]
            full_matches = [name for name in matches if name.startswith("full-tmp/")]
            if is_v2:
                assert len(full_matches) == 1, (suffix, full_matches)
                return full_matches[0]
            assert len(matches) == 1, (suffix, matches)
            return matches[0]

        process_candidates = (
            "evidence/commands.txt",
            "evidence/manifest.sha256",
            "evidence/environment.txt",
            "evidence/nvidia-processes-after.txt",
            "evidence/nvidia-smi-q.txt",
            "evidence/pytest.exit-code",
            "evidence/pytest.log",
            "evidence/blender-processes-post.txt",
            "evidence/full-exit-code",
            "evidence/full-pytest.log",
            "evidence/gpu-post-state.csv",
            "evidence/gpu-processes-post.csv",
            "evidence/overlay-files.sha256",
            "evidence/process-record.json",
            "evidence/tool-versions.txt",
        )
        for name in process_candidates:
            candidate_member = members.get(name)
            if candidate_member is not None and candidate_member.isfile():
                add(name, "process")
        if is_v2:
            direct_process_path = "evidence/process-record.json"
            assert direct_process_path in selected
            direct_process = _parse_json(
                read(direct_process_path), source=direct_process_path
            )
            assert _is_process_record(direct_process)
            direct_processes = direct_process.get("processes")
            assert isinstance(direct_processes, Sequence) and not isinstance(
                direct_processes, (str, bytes)
            )
            commands_text = read("evidence/commands.txt").decode("utf-8")
            for process in direct_processes:
                assert isinstance(process, Mapping)
                command = process.get("command")
                junit_ref = process.get("junit")
                log_ref = process.get("log")
                assert isinstance(command, str) and command in commands_text
                assert isinstance(junit_ref, str) and junit_ref in checksums
                assert isinstance(log_ref, str) and log_ref in checksums
                read(junit_ref)
                read(log_ref)

        for suffix in (
            "turn-retargeted.blend",
            "turn-baked.blend",
            "peer-success.blend",
            "peer-recover.blend",
        ):
            add(unique_suffix(suffix), "editable")
        add(unique_suffix("animation.glb"), "glb")
        add(unique_suffix("animation-preview.png"), "preview")

        validation_path = unique_suffix("animation-validation.json")
        reopen_path = unique_suffix("animation-reopen.json")
        for name in (validation_path, reopen_path):
            add(name, "report")
            report_documents[name] = _parse_json(read(name), source=name)
        for name in (
            "evidence/prompt-kpi-report.json",
            "evidence/test-summary.json",
        ):
            report_member = members.get(name)
            if report_member is not None and report_member.isfile():
                add(name, "report")
                report_documents[name] = _parse_json(read(name), source=name)

        operation_reports: list[tuple[str, str, Mapping[str, object]]] = []
        for name in sorted(members):
            if (
                "/.minitz-three-d-" not in name
                or "/.minitz-three-d-stage-" in name
                or not name.endswith(".json")
                or (is_v2 and not name.startswith("full-tmp/"))
            ):
                continue
            document = _parse_json(read(name), source=name)
            operation = document.get("operation")
            if isinstance(operation, str):
                operation_reports.append((operation.lower(), name, document))

        picked_reports: set[str] = set()
        for desired in ("retarget", "bake", "export", "animate", "preview", "inspect"):
            match = next(
                (
                    (name, document)
                    for operation, name, document in operation_reports
                    if desired in operation and name not in picked_reports
                ),
                None,
            )
            if match is not None:
                name, document = match
                picked_reports.add(name)
                add(name, "report")
                report_documents[name] = document
        for peer_name in ("peer-success.blend", "peer-recover.blend"):
            match = next(
                (
                    (name, document)
                    for _, name, document in operation_reports
                    if document.get("output_path") == peer_name
                ),
                None,
            )
            assert match is not None, peer_name
            name, document = match
            picked_reports.add(name)
            add(name, "report")
            report_documents[name] = document

        process_reports = 0
        process_report_target = 0 if is_v2 else 3
        if not is_v2:
            for name in sorted(members):
                if not name.startswith("retained/json/") or not name.endswith(".json"):
                    continue
                document = _parse_json(read(name), source=name)
                if _is_process_record(document):
                    add(name, "process")
                    process_reports += 1
                    if process_reports == process_report_target:
                        break
        assert process_reports == process_report_target

        junit_path = "evidence/full-junit.xml" if is_v2 else "evidence/junit.xml"
        add(junit_path, "junit")
        junit = _junit_summary(read(junit_path))
        if is_v2:
            add("evidence/focused-junit.xml", "junit")
        add(manifest_path, "manifest")

    source = manifest.get("source")
    assert isinstance(source, Mapping)
    commit = source.get("base_commit") if is_v2 else source.get("commit")
    tree = source.get("base_tree") if is_v2 else source.get("tree")
    assert isinstance(commit, str) and _HEX_40.fullmatch(commit)
    assert isinstance(tree, str) and _HEX_40.fullmatch(tree)
    overlays: list[Mapping[str, object]] = []
    if is_v2:
        raw_overlays = source.get("overlays")
        assert isinstance(raw_overlays, Sequence) and not isinstance(
            raw_overlays, (str, bytes)
        )
        seen_overlay_paths: set[str] = set()
        for raw_overlay in raw_overlays:
            assert isinstance(raw_overlay, Mapping)
            overlay_path = raw_overlay.get("path")
            overlay_sha256 = raw_overlay.get("sha256")
            assert isinstance(overlay_path, str) and overlay_path not in seen_overlay_paths
            parsed_overlay_path = PurePosixPath(overlay_path)
            assert not parsed_overlay_path.is_absolute()
            assert ".." not in parsed_overlay_path.parts
            assert isinstance(overlay_sha256, str) and _HEX_64.fullmatch(
                overlay_sha256
            )
            seen_overlay_paths.add(overlay_path)
            overlays.append(dict(raw_overlay))
        assert source.get("overlay_count") == len(overlays) == 7
        excluded_recipe_sha256 = source.get("excluded_production_recipe_sha256")
        assert isinstance(excluded_recipe_sha256, str) and _HEX_64.fullmatch(
            excluded_recipe_sha256
        )
        overlay_checksums: dict[str, str] = {}
        for line in cache["evidence/overlay-files.sha256"].decode("ascii").splitlines():
            digest, name = line.split(maxsplit=1)
            assert _HEX_64.fullmatch(digest)
            assert name not in overlay_checksums
            overlay_checksums[name] = digest
        assert overlay_checksums == {
            cast(str, overlay["path"]): cast(str, overlay["sha256"])
            for overlay in overlays
        }
    else:
        assert source.get("transfer") == "git archive exact commit"

    command_text = cache["evidence/commands.txt"].decode("utf-8")
    raw_commands = manifest.get("commands")
    if raw_commands is None:
        parsed_commands: list[str] = []
        for line in command_text.splitlines():
            label, separator, command = line.partition(": ")
            assert separator and label in {"focused", "full", "package"}
            assert command
            parsed_commands.append(command)
        commands: Sequence[str] = tuple(parsed_commands)
    else:
        assert isinstance(raw_commands, Sequence) and not isinstance(
            raw_commands, (str, bytes)
        )
        assert all(isinstance(command, str) for command in raw_commands)
        commands = cast(Sequence[str], raw_commands)
        for command in commands:
            assert command in command_text
    assert len(commands) >= 3
    if not is_v2:
        assert commit in command_text
    assert "tests/test_p3_07_animation_pack.py" in command_text
    assert "tests/test_p3_07_three_d_animation_real.py" in command_text

    if is_v2:
        focused_summary = manifest.get("focused")
        full_summary = manifest.get("full")
        assert isinstance(focused_summary, Mapping)
        assert isinstance(full_summary, Mapping)
        test_summary = report_documents["evidence/test-summary.json"]
        assert test_summary == {
            "focused": focused_summary,
            "full": full_summary,
        }
        assert focused_summary.get("tests") == 1
        assert full_summary.get("tests") == junit["tests"] == 10
        for summary in (focused_summary, full_summary):
            assert summary.get("failures") == 0
            assert summary.get("errors") == 0
            assert summary.get("skipped") == 0
            summary_cases = summary.get("cases")
            assert isinstance(summary_cases, Sequence) and not isinstance(
                summary_cases, (str, bytes)
            )
            assert len(summary_cases) == summary.get("tests")
            assert all(
                isinstance(case, Mapping)
                and case.get("failed") is False
                and case.get("errored") is False
                and case.get("skipped") is False
                for case in summary_cases
            )
        full_cases = full_summary.get("cases")
        assert isinstance(full_cases, Sequence) and not isinstance(
            full_cases, (str, bytes)
        )
        full_case_ids: set[str] = set()
        for case in full_cases:
            assert isinstance(case, Mapping)
            classname = case.get("classname")
            case_name = case.get("name")
            assert isinstance(classname, str) and isinstance(case_name, str)
            full_case_ids.add(f"{classname}::{case_name}")
        assert full_case_ids == set(cast(Sequence[str], junit["cases"]))
        assert cache["evidence/full-exit-code"].strip() == b"0"
        prompt_report = report_documents["evidence/prompt-kpi-report.json"]
        assert prompt_report == manifest.get("prompt_kpis")
    else:
        pytest_summary = manifest.get("pytest")
        assert isinstance(pytest_summary, Mapping)
        assert pytest_summary.get("tests") == junit["tests"] == 5
        assert pytest_summary.get("failures") == junit["failures"] == 0
        assert pytest_summary.get("errors") == junit["errors"] == 0
        assert pytest_summary.get("skipped") == junit["skipped"] == 0
        assert pytest_summary.get("exit_code") == 0
        assert cache["evidence/pytest.exit-code"].strip() == b"0"
        test_summary = {"full": dict(pytest_summary)}

    normalized_source = dict(source)
    normalized_source.update({"commit": commit, "tree": tree})
    normalized_manifest = dict(manifest)
    normalized_manifest.update(
        {
            "commands": tuple(commands),
            "source": normalized_source,
            "test_summary": test_summary,
        }
    )

    validation = report_documents[validation_path]
    reopen = report_documents[reopen_path]
    action_identity, reopen_identity = _derive_action_identity(validation, reopen)
    kpis, kpi_basis = _derive_zero_kpis(
        normalized_manifest, report_documents, junit, validation_path
    )

    retained = [
        _RetainedEvidence(
            package_path.name,
            "package",
            package_payload,
            "application/gzip",
            archive_member=False,
        )
    ]
    retained.extend(
        sorted(
            selected.values(),
            key=lambda item: (_CATEGORY_ORDER[item.category], item.logical_path),
        )
    )
    assert len(retained) <= _MAX_SELECTED_MEMBERS
    assert {item.category for item in retained} == set(_CATEGORY_ORDER)
    return _PackageEvidence(
        tuple(retained),
        normalized_manifest,
        report_documents,
        junit,
        test_summary,
        kpis,
        kpi_basis,
        action_identity,
        reopen_identity,
    )


def _publish(
    evidence: _RetainedEvidence,
    *,
    artifacts: ArtifactService,
    objects: FilesystemObjectStorageBackend,
    access: object,
    run_attempt: object,
    task: object,
    sources: Sequence[Artifact],
    commit: str,
    tree: str,
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
    source_contents: dict[tuple[str, str, int], ContentRef] = {}
    for source in sources:
        source_content = cast(ContentRef, source.content_ref)
        source_contents.setdefault(
            (
                source_content.algorithm,
                source_content.digest,
                source_content.size_bytes,
            ),
            source_content,
        )
    return artifacts.publish_from_run(
        access,  # type: ignore[arg-type]
        producer_attempt=run_attempt,  # type: ignore[arg-type]
        expected_task_ref=task.task_ref,  # type: ignore[attr-defined]
        expected_task_digest=task.canonical_digest,  # type: ignore[attr-defined]
        role=_ROLES[evidence.category],
        content_ref=content_ref,
        source_refs=(),
        source_artifact_refs=tuple(source.artifact_ref for source in sources),
        source_content_refs=tuple(source_contents.values()),
        derivation_type=(
            "animation.captured-real-evidence"
            if evidence.category == "package"
            else "animation.extracted-retained-package"
        ),
        metadata={},
    )


def _output_target() -> Path | None:
    value = os.environ.get("MINITZ_P3_07_EVIDENCE_OUT")
    return Path(value).expanduser() if value else None


def test_p3_07_retained_package_becomes_durable_engine_evidence(
    tmp_path: Path,
) -> None:
    package_value = os.environ.get("MINITZ_P3_07_RETAINED_PACKAGE")
    if not package_value:
        pytest.skip("MINITZ_P3_07_RETAINED_PACKAGE is not configured")
    package_path = Path(package_value).expanduser().resolve(strict=True)
    assert package_path.is_file()
    package = _discover_package(package_path)

    source = package.manifest["source"]
    assert isinstance(source, Mapping)
    commit = cast(str, source["commit"])
    tree = cast(str, source["tree"])
    commands = package.manifest["commands"]
    assert isinstance(commands, Sequence) and not isinstance(commands, (str, bytes))

    database = tmp_path / "p3-07-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("animation.validate", "1.0.0")
    output_contract = {
        "clip_evidence": "schema://minitz/p3-07/durable-clip-evidence/1",
        "evidence_manifest": "schema://minitz/p3-07/durable-evidence/1",
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate exact retained REAL Blender animation evidence",
            output_contract=output_contract,
        )
    )

    projects = ProjectStore(database)
    registration = projects.create_project(
        namespace="p3-07-durable-evidence",
        display_name="P3-07 Durable Animation Evidence",
        metadata={"source_commit": commit, "source_tree": tree},
    )
    access = registration.access
    project_ref = access.project_ref
    tasks = TaskRevisionService(database)
    task = tasks.create_task(
        access,
        project_ref=project_ref,
        idempotency_key="p3-07-durable-evidence-task",
        task_type="animation.durable-evidence",
        objective="Retain and validate exact REAL Blender animation outputs",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={"independent_clip_nodes": 2, "named_zero_kpis": 5},
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-07/retained-evidence",
        egress_policy_ref="policy://p3-07/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={"slots": 2},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-07/durable-evidence/run",
        lease_seconds=1800,
    )

    graph_ref = GraphRef.new(project_ref)
    clip_nodes = tuple(
        Node(
            NodeRef.new(graph_ref),
            f"generic.animation.{clip_name}-evidence",
            (capability_ref,),
            (),
            (),
            output_contract,
            None,
            "READ_ONLY",
            {"slots": 1},
            ("artifact", "content-ref", "provenance", "runtime"),
        )
        for clip_name in ("peer-success", "peer-recover")
    )
    graphs = GraphService(database)
    graph = graphs.create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=clip_nodes,
        compiler_identity="compiler://p3-07/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    assert graph.graph_ref.revision == 1
    assert graphs.get_graph(access, graph_ref) == graph
    assert len({node.node_ref for node in graph.nodes}) == 2
    assert all(node.dependencies == () for node in graph.nodes)

    executions = NodeExecutionService(database)
    prepared = executions.prepare_run(access, run.run_ref)
    assert {execution.node_ref for execution in prepared} == {
        node.node_ref for node in clip_nodes
    }

    resource_ref = ResourceRef(
        project_ref,
        "res_"
        + hashlib.sha256(f"p3-07:{project_ref.value}".encode()).hexdigest()[:32],
    )
    resources = ResourceService(database)
    resources.register_resource(
        access,
        Resource(
            resource_ref,
            "runtime.host",
            "locality://p3-07/durable-evidence/shared",
            configured_capacity={
                "slots": _quantity(2.0, QuantitySource.CONFIGURED)
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
                        "slots": _quantity(2.0, QuantitySource.MEASURED)
                    },
                    effective_capacity={
                        "slots": _quantity(2.0, QuantitySource.MEASURED)
                    },
                    used_capacity={
                        "slots": _quantity(0.0, QuantitySource.MEASURED)
                    },
                    available_capacity={
                        "slots": _quantity(2.0, QuantitySource.MEASURED)
                    },
                    pressure={
                        "slots": _quantity(0.0, QuantitySource.MEASURED)
                    },
                ),
                ),
            ),
        )
    scheduler = Scheduler(database)
    dispatches: list[ScheduledDispatch] = []
    for clip_name, node in zip(("peer-success", "peer-recover"), clip_nodes):
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
                side_effect_targets=(f"evidence://p3-07/clips/{clip_name}",),
            ),
            authority_attempt=run_attempt,
            owner_ref=f"worker://p3-07/durable-evidence/{clip_name}",
            lease_seconds=1800,
            idempotency_key=f"p3-07-{clip_name}-reserve",
        )
        dispatch = scheduler.dispatch(
            access,
            allocation,
            authority_attempt=run_attempt,
            lease_seconds=1800,
            idempotency_key=f"p3-07-{clip_name}-dispatch",
        )
        started = executions.get_node_execution(access, node.node_ref)
        assert started.status == "RUNNING"
        assert started.current_attempt_id == dispatch.node_attempt.attempt_id
        assert started.current_fence == dispatch.node_attempt.fence
        assert dispatch.allocation.status == "DISPATCHED"
        dispatches.append(dispatch)
    assert dispatches[0].allocation.allocation_ref != dispatches[1].allocation.allocation_ref
    assert dispatches[0].node_attempt.node_ref != dispatches[1].node_attempt.node_ref
    assert dispatches[0].node_attempt.attempt_id != dispatches[1].node_attempt.attempt_id
    assert dispatches[0].node_attempt.record_sha256 != dispatches[1].node_attempt.record_sha256
    assert dispatches[0].allocation.side_effect_targets != dispatches[1].allocation.side_effect_targets

    artifacts = ArtifactService(database)
    published_by_category: dict[str, list[Artifact]] = {
        category: [] for category in _CATEGORY_ORDER
    }
    publication_sources = {
        "package": (),
        "process": ("package",),
        "editable": ("package", "process"),
        "glb": ("editable",),
        "preview": ("editable",),
        "report": ("package", "process", "editable", "glb", "preview"),
        "junit": ("process", "report"),
        "manifest": (
            "package",
            "process",
            "editable",
            "glb",
            "preview",
            "report",
            "junit",
        ),
    }
    published: list[tuple[_RetainedEvidence, Artifact]] = []
    for evidence in package.retained:
        sources = tuple(
            artifact
            for category in publication_sources[evidence.category]
            for artifact in published_by_category[category]
        )
        artifact = _publish(
            evidence,
            artifacts=artifacts,
            objects=objects,
            access=access,
            run_attempt=run_attempt,
            task=task,
            sources=sources,
            commit=commit,
            tree=tree,
        )
        published_by_category[evidence.category].append(artifact)
        published.append((evidence, artifact))

    assert projects.get_project(access, project_ref) == registration.project
    assert tasks.get_task(access, task.task_ref) == task
    package_artifact = published_by_category["package"][0]
    manifest_artifact = published_by_category["manifest"][0]
    validation_artifact = next(
        artifact
        for evidence, artifact in published
        if evidence.logical_path.endswith("/animation-validation.json")
    )
    glb_artifact = published_by_category["glb"][0]
    process_artifact = next(
        (
            artifact
            for evidence, artifact in published
            if evidence.logical_path == "evidence/process-record.json"
        ),
        None,
    )
    if process_artifact is None:
        process_artifact = next(
            artifact
            for evidence, artifact in published
            if evidence.category == "process"
            and evidence.logical_path.startswith("retained/json/")
        )
    peer_artifacts = {
        clip_name: next(
            artifact
            for evidence, artifact in published
            if evidence.logical_path.endswith(f"/{clip_name}.blend")
        )
        for clip_name in ("peer-success", "peer-recover")
    }

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
            "project.criteria:p3-07-animation-kpi",
            ("artifact", "content_ref", "provenance"),
            (),
            {"expected": 0, "kpi": name},
        )
        for name in _KPI_NAMES
    )
    validation_attempt = dispatches[0].node_attempt
    plan = validations.compile_plan(
        access,
        validation_attempt,
        subjects=subjects,
        project_criteria=ProjectValidationCriteria(
            project_ref,
            checks,
            "criteria://p3-07/animation-durable-evidence/v1",
        ),
        idempotency_key="p3-07-durable-evidence-validation-plan",
    )
    assert validations.get_plan(access, plan.plan_ref) == plan
    evidence_refs = tuple(
        [artifact.artifact_ref.value for _, artifact in published]
        + [cast(ContentRef, artifact.content_ref).value for _, artifact in published]
    )
    results = []
    kpi_results = {}
    for check in plan.checks:
        kpi_name = check.parameters.get("kpi")
        metrics: tuple[MetricMeasurement, ...] = ()
        if isinstance(kpi_name, str):
            assert kpi_name in _KPI_NAMES
            assert package.kpis[kpi_name] == 0
            metrics = (
                MetricMeasurement(
                    kpi_name,
                    0.0,
                    "count",
                    f"Exact {kpi_name} violations in retained P3-07 REAL evidence",
                    validation_artifact.artifact_ref.value,
                ),
            )
        result = validations.record_result(
            access,
            validation_attempt,
            plan.plan_ref,
            check_id=check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://p3-07/durable-evidence/v1",
            runtime_ref="runtime://blender/l40s-retained-evidence",
            validator_dimensions={
                "implementation": "validator://p3-07/durable-evidence/v1",
                "runtime": "runtime://blender/l40s-retained-evidence",
                "source_commit": f"source://git/commit/{commit}",
                "source_tree": f"source://git/tree/{tree}",
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-07-result-{check.check_id}",
        )
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
        results.append(result)
        if isinstance(kpi_name, str):
            assert len(result.metrics) == 1
            assert result.metrics[0].name == kpi_name
            assert result.metrics[0].value == 0.0
            kpi_results[kpi_name] = result
        else:
            assert result.metrics == ()
    assert set(kpi_results) == set(_KPI_NAMES)
    aggregate = validations.aggregate(
        access,
        validation_attempt,
        plan.plan_ref,
        idempotency_key="p3-07-durable-evidence-validation-aggregate",
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
        node_ref=clip_nodes[0].node_ref,
        event_type="P3_07_DURABLE_EVIDENCE_RETAINED",
        idempotency_key="p3-07-durable-evidence-retained",
        actor_ref="worker://p3-07/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for _, artifact in published),
        metadata={
            "artifact_count": len(published),
            "independent_node_count": len(clip_nodes),
            "kpi_count": len(_KPI_NAMES),
            "source_commit": commit,
            "source_tree": tree,
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
        },
        payload_ref=cast(ContentRef, manifest_artifact.content_ref),
        authority_attempt=run_attempt,
    )
    assert events.get_event(access, event.event_ref) == event
    assert set(event.object_refs) == {
        artifact.artifact_ref.value for _, artifact in published
    }
    acceptance_event = executions.record_run_acceptance(
        access,
        run.run_ref,
        criterion="validation.success_rule=ALL_REQUIRED_PASS",
        evidence_ref=validation_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-07-durable-evidence-acceptance",
    )

    success_content = cast(ContentRef, peer_artifacts["peer-success"].content_ref)
    success_before_recovery = objects.read(success_content)
    completed_nodes = []
    for clip_name, node, dispatch in zip(
        ("peer-success", "peer-recover"), clip_nodes, dispatches
    ):
        completed = executions.finalize_node(
            access,
            dispatch.node_attempt,
            outputs={
                "clip_evidence": peer_artifacts[clip_name].artifact_ref,
                "evidence_manifest": manifest_artifact.artifact_ref,
            },
            evidence={
                "artifact": peer_artifacts[clip_name].artifact_ref,
                "content-ref": cast(ContentRef, peer_artifacts[clip_name].content_ref),
                "provenance": glb_artifact.artifact_ref,
                "runtime": process_artifact.artifact_ref,
            },
            acceptance_criteria=(),
            idempotency_key=f"p3-07-{clip_name}-finalize",
        )
        assert completed.status == "SUCCEEDED"
        assert executions.get_node_execution(access, node.node_ref) == completed
        completed_nodes.append(completed)
        if clip_name == "peer-success":
            assert objects.read(success_content) == success_before_recovery

    success_after_recovery = objects.read(success_content)
    assert success_after_recovery == success_before_recovery
    assert hashlib.sha256(success_after_recovery).hexdigest() == success_content.digest
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"
    assert graphs.get_graph(access, graph_ref) == graph
    released = scheduler.reconcile_terminal(access, run.run_ref)
    assert {allocation.allocation_ref for allocation in released} == {
        dispatch.allocation.allocation_ref for dispatch in dispatches
    }
    assert all(allocation.status == "RELEASED" for allocation in released)
    released_by_ref = {allocation.allocation_ref: allocation for allocation in released}

    output_manifest = {
        "schema": "minitz.p3-07.durable-engine-evidence/v1",
        "source": {
            "base_commit": source.get("base_commit", commit),
            "base_tree": source.get("base_tree", tree),
            "commands": list(commands),
            "commit": commit,
            "excluded_production_recipe_sha256": source.get(
                "excluded_production_recipe_sha256"
            ),
            "overlay_count": source.get("overlay_count", 0),
            "overlays": list(cast(Sequence[object], source.get("overlays", ()))),
            "tree": tree,
        },
        "retained_package": {
            "artifact_ref": package_artifact.artifact_ref.value,
            "artifact_sha256": package_artifact.record_sha256,
            "bytes": cast(ContentRef, package_artifact.content_ref).size_bytes,
            "content_ref": cast(ContentRef, package_artifact.content_ref).value,
            "path": str(package_path),
            "sha256": cast(ContentRef, package_artifact.content_ref).digest,
        },
        "project": {
            "project_ref": project_ref.value,
            "task_ref": {
                "project_ref": task.task_ref.project_ref.value,
                "revision": task.task_ref.revision,
                "task_id": task.task_ref.task_id,
            },
            "task_sha256": task.record_sha256,
        },
        "run": {
            "acceptance_event_ref": acceptance_event.event_ref.value,
            "attempt_id": run_attempt.attempt_id,
            "attempt_sha256": run_attempt.record_sha256,
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
            "revision": graph_ref.revision,
            "semantic_digest": graph.semantic_digest,
        },
        "nodes": [
            {
                "allocation_ref": dispatch.allocation.allocation_ref.value,
                "allocation_sha256": released_by_ref[
                    dispatch.allocation.allocation_ref
                ].state_sha256,
                "allocation_status": released_by_ref[
                    dispatch.allocation.allocation_ref
                ].status,
                "attempt_fence": dispatch.node_attempt.fence,
                "attempt_id": dispatch.node_attempt.attempt_id,
                "attempt_sha256": dispatch.node_attempt.record_sha256,
                "clip": clip_name,
                "clip_artifact_ref": peer_artifacts[clip_name].artifact_ref.value,
                "clip_sha256": cast(
                    ContentRef, peer_artifacts[clip_name].content_ref
                ).digest,
                "node_ref": node.node_ref.value,
                "node_state_sha256": completed.state_sha256,
                "side_effect_targets": list(dispatch.allocation.side_effect_targets),
                "status": completed.status,
            }
            for clip_name, node, dispatch, completed in zip(
                ("peer-success", "peer-recover"),
                clip_nodes,
                dispatches,
                completed_nodes,
            )
        ],
        "concurrency": {
            "distinct_allocation_refs": True,
            "distinct_attempt_ids": True,
            "distinct_node_refs": True,
            "failure_isolation_junit_case": _CONCURRENCY_CASE,
            "peer_success_reread_after_recovery_sha256": hashlib.sha256(
                success_after_recovery
            ).hexdigest(),
            "shared_object_store": True,
            "shared_project_store": True,
        },
        "junit": dict(package.junit),
        "test_summary": dict(package.test_summary),
        "action_identity": dict(package.action_identity),
        "reopen_identity": dict(package.reopen_identity),
        "kpis": dict(package.kpis),
        "kpi_basis": {
            name: list(package.kpi_basis[name]) for name in _KPI_NAMES
        },
        "validation": {
            "accepted": aggregate.accepted,
            "aggregate_sha256": aggregate.aggregate_sha256,
            "evidence_state": aggregate.evidence_state.value,
            "plan_ref": plan.plan_ref.value,
            "plan_sha256": plan.record_sha256,
            "result_refs": [result.result_ref.value for result in results],
            "result_sha256s": [result.record_sha256 for result in results],
            "verdict": aggregate.verdict.value,
        },
        "event": {
            "event_ref": event.event_ref.value,
            "record_sha256": event.record_sha256,
            "type": event.event_type,
        },
        "artifacts": [
            {
                "archive_member": evidence.archive_member,
                "artifact_ref": artifact.artifact_ref.value,
                "artifact_sha256": artifact.record_sha256,
                "bytes": cast(ContentRef, artifact.content_ref).size_bytes,
                "category": evidence.category,
                "content_ref": cast(ContentRef, artifact.content_ref).value,
                "media_type": cast(ContentRef, artifact.content_ref).media_type,
                "path": evidence.logical_path,
                "role": artifact.role,
                "sha256": cast(ContentRef, artifact.content_ref).digest,
                "source_artifact_refs": [
                    source_ref.value for source_ref in artifact.source_artifact_refs
                ],
            }
            for evidence, artifact in published
        ],
    }
    assert output_manifest["kpis"] == {name: 0 for name in _KPI_NAMES}
    target = _output_target()
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = (
            json.dumps(output_manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        target.write_bytes(encoded)
        assert _parse_json(target.read_bytes(), source=str(target)) == output_manifest
