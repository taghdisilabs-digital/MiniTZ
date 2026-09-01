"""Durable engine evidence for retained REAL P3-06 Blender character outputs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import cast
from xml.etree import ElementTree

import pytest

from biella.artifact import Artifact, ArtifactService, ContentRef
from biella.capability import Capability, CapabilityRef, CapabilityRegistry
from biella.event import EventLedger
from biella.execution import NodeExecutionService
from biella.graph import GraphRef, GraphService, Node, NodeRef
from biella.object_store import FilesystemObjectStorageBackend
from biella.project import ProjectStore
from biella.run import RunService
from biella.task import TaskRevisionService
from biella.validation import (
    MetricMeasurement,
    ProjectValidationCriteria,
    ValidationCheck,
    ValidationEvidenceState,
    ValidationService,
    ValidationVerdict,
)


_KPI_NAMES = (
    "hardcoded_humanoid",
    "rig_without_exact_mesh",
    "skin_without_exact_skeleton",
    "invalid_weights",
    "stale_rig_reuse",
    "domain_kernel_changes",
)
_CATEGORY_ORDER = {
    "process": 0,
    "mesh": 1,
    "rig": 2,
    "skin": 3,
    "deformation": 4,
    "glb": 5,
    "preview": 6,
    "report": 7,
    "junit": 8,
    "manifest": 9,
}
_ROLES = {
    "process": "character.process-evidence",
    "mesh": "character.mesh",
    "rig": "character.rig",
    "skin": "character.skin",
    "deformation": "character.deformation",
    "glb": "character.export",
    "preview": "character.preview",
    "report": "character.validation-report",
    "junit": "character.junit-report",
    "manifest": "character.evidence-manifest",
}


@dataclass(frozen=True)
class _RetainedFile:
    category: str
    path: Path
    media_type: str
    payload: bytes

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def _json_value(payload: bytes, path: Path) -> object:
    try:
        return json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"retained JSON evidence is malformed: {path}: {exc}")


def _kpi_mappings(value: object) -> Iterator[Mapping[str, object]]:
    if isinstance(value, Mapping):
        if all(
            name in value
            and isinstance(value[name], (int, float))
            and not isinstance(value[name], bool)
            for name in _KPI_NAMES
        ):
            yield cast(Mapping[str, object], value)
        for child in value.values():
            yield from _kpi_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _kpi_mappings(child)


def _contains_process_record(value: object) -> bool:
    if isinstance(value, Mapping):
        keys = {str(key).lower() for key in value}
        if "command" in keys and keys.intersection(
            {"exit_code", "returncode", "status"}
        ):
            return True
        return any(_contains_process_record(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_process_record(child) for child in value)
    return False


def _junit_summary(payload: bytes, path: Path) -> dict[str, int]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        pytest.fail(f"retained JUnit evidence is malformed: {path}: {exc}")
    root_tag = root.tag.rsplit("}", 1)[-1]
    assert root_tag in {"testsuite", "testsuites"}, path
    suites = tuple(
        element
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "testsuite"
    )
    assert suites, path

    def total(attribute: str) -> int:
        return sum(int(suite.attrib.get(attribute, "0")) for suite in suites)

    summary = {
        "tests": total("tests"),
        "failures": total("failures"),
        "errors": total("errors"),
    }
    assert summary["tests"] > 0, path
    assert summary["failures"] == summary["errors"] == 0, (path, summary)
    assert not any(
        element.tag.rsplit("}", 1)[-1] in {"failure", "error"}
        for element in root.iter()
    ), path
    return summary


def _preview_media_type(path: Path, payload: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        assert payload.startswith(b"\x89PNG\r\n\x1a\n"), path
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        assert payload.startswith(b"\xff\xd8\xff"), path
        return "image/jpeg"
    if suffix == ".webp":
        assert payload.startswith(b"RIFF") and payload[8:12] == b"WEBP", path
        return "image/webp"
    raise AssertionError(f"unsupported retained preview media type: {path}")


def _process_media_type(path: Path, payload: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        _json_value(payload, path)
        return "application/json"
    if suffix == ".jsonl":
        lines = tuple(line for line in payload.splitlines() if line.strip())
        assert lines, path
        for line in lines:
            _json_value(line, path)
        return "application/x-ndjson"
    assert suffix in {".log", ".txt"}, path
    payload.decode("utf-8")
    return "text/plain"


def _discover_retained_evidence(
    root: Path,
) -> tuple[tuple[_RetainedFile, ...], Mapping[str, object], Path, dict[str, int]]:
    assert root.is_dir(), f"BIELLA_P3_06_L40S_ROOT is not a directory: {root}"
    paths = tuple(
        sorted(
            (path.resolve() for path in root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )
    assert paths, f"no retained P3-06 evidence exists under {root}"
    assert len(paths) <= 256, "retained P3-06 evidence root is unexpectedly unbounded"
    assert all(path.is_relative_to(root) for path in paths)
    assert not any(path.is_symlink() for path in root.rglob("*"))
    payloads = {path: path.read_bytes() for path in paths}
    assert all(payloads.values()), "retained P3-06 evidence contains an empty file"

    blend_paths = tuple(path for path in paths if path.suffix.lower() == ".blend")
    blend_paths_by_category = {
        "mesh": tuple(path for path in blend_paths if "mesh" in path.name.lower()),
        "rig": tuple(path for path in blend_paths if "rig" in path.name.lower()),
        "skin": tuple(path for path in blend_paths if "skin" in path.name.lower()),
        "deformation": tuple(
            path for path in blend_paths if "deform" in path.name.lower()
        ),
    }
    glb_paths = tuple(path for path in paths if path.suffix.lower() == ".glb")
    preview_paths = tuple(
        path
        for path in paths
        if "preview" in path.name.lower()
        and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    manifest_paths = tuple(path for path in paths if path.name == "manifest.json")
    assert all(blend_paths_by_category.values()), (
        "retained REAL character evidence lacks an exact mesh/rig/skin/deformation output",
        {key: tuple(path.name for path in value) for key, value in blend_paths_by_category.items()},
    )
    assert glb_paths, "retained REAL character evidence has no .glb output"
    assert preview_paths, "retained REAL character evidence has no preview image"
    assert len(manifest_paths) == 1, "retained REAL character evidence has no exact manifest"
    for path in blend_paths:
        payload = payloads[path]
        assert payload.startswith(b"BLENDER") or (
            payload.startswith(b"\x28\xb5\x2f\xfd")
            and b"BLENDER" in payload[:64]
        ), path
    for path in glb_paths:
        assert payloads[path].startswith(b"glTF") and len(payloads[path]) >= 12, path

    report_candidates: list[tuple[Path, Mapping[str, object]]] = []
    for path in paths:
        if path.suffix.lower() != ".json":
            continue
        matches = tuple(_kpi_mappings(_json_value(payloads[path], path)))
        if matches:
            assert len(matches) == 1, f"ambiguous P3-06 KPI mappings in {path}"
            report_candidates.append((path, matches[0]))
    preferred_reports = tuple(
        item
        for item in report_candidates
        if "report" in item[0].name.lower() or "validation" in item[0].name.lower()
    )
    selected_reports = preferred_reports or tuple(report_candidates)
    assert len(selected_reports) == 1, (
        "retained evidence must contain one exact JSON KPI report",
        tuple(path for path, _ in selected_reports),
    )
    report_path, observed_kpis = selected_reports[0]
    for name in _KPI_NAMES:
        value = observed_kpis[name]
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            name,
            value,
        )
        assert float(value) == 0.0, (name, value)

    junit_paths: list[Path] = []
    junit_summaries: dict[Path, dict[str, int]] = {}
    for path in paths:
        if path.suffix.lower() != ".xml":
            continue
        try:
            root_tag = ElementTree.fromstring(payloads[path]).tag.rsplit("}", 1)[-1]
        except ElementTree.ParseError:
            continue
        if root_tag in {"testsuite", "testsuites"}:
            junit_paths.append(path)
            junit_summaries[path] = _junit_summary(payloads[path], path)
    assert junit_paths, "retained REAL character evidence has no passing JUnit XML"

    reserved = {
        *blend_paths,
        *glb_paths,
        *preview_paths,
        report_path,
        *junit_paths,
        *manifest_paths,
    }
    process_paths = tuple(
        path
        for path in paths
        if path not in reserved
        and path.suffix.lower() in {".json", ".jsonl", ".log", ".txt"}
        and (
            any(token in path.name.lower() for token in ("process", "blender"))
            or (
                path.suffix.lower() == ".json"
                and _contains_process_record(_json_value(payloads[path], path))
            )
        )
    )
    assert process_paths, "retained REAL character evidence has no process record"

    retained: list[_RetainedFile] = []
    retained.extend(
        _RetainedFile("process", path, _process_media_type(path, payloads[path]), payloads[path])
        for path in process_paths
    )
    for category in ("mesh", "rig", "skin", "deformation"):
        retained.extend(
            _RetainedFile(category, path, "application/x-blender", payloads[path])
            for path in blend_paths_by_category[category]
        )
    retained.extend(
        _RetainedFile("glb", path, "model/gltf-binary", payloads[path])
        for path in glb_paths
    )
    retained.extend(
        _RetainedFile("preview", path, _preview_media_type(path, payloads[path]), payloads[path])
        for path in preview_paths
    )
    retained.append(
        _RetainedFile("report", report_path, "application/json", payloads[report_path])
    )
    retained.extend(
        _RetainedFile("junit", path, "application/xml", payloads[path])
        for path in junit_paths
    )
    retained.append(
        _RetainedFile(
            "manifest",
            manifest_paths[0],
            "application/json",
            payloads[manifest_paths[0]],
        )
    )
    retained.sort(
        key=lambda item: (_CATEGORY_ORDER[item.category], item.path.relative_to(root).as_posix())
    )
    junit_total = {
        key: sum(summary[key] for summary in junit_summaries.values())
        for key in ("tests", "failures", "errors")
    }
    return tuple(retained), observed_kpis, report_path, junit_total


def _publish_retained_file(
    evidence: _RetainedFile,
    *,
    artifacts: ArtifactService,
    objects: FilesystemObjectStorageBackend,
    access: object,
    run_attempt: object,
    task: object,
    sources: Sequence[Artifact],
) -> Artifact:
    content_ref = objects.put(
        evidence.payload,
        media_type=evidence.media_type,
        expected_digest=evidence.digest,
        expected_size=len(evidence.payload),
    )
    assert content_ref == ContentRef.from_bytes(
        evidence.payload, media_type=evidence.media_type
    )
    source_contents = tuple(
        cast(ContentRef, source.content_ref) for source in sources
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
        source_content_refs=source_contents,
        derivation_type=f"character.retained-{evidence.category}",
        metadata={
            "media_type": evidence.media_type,
            "schema_ref": f"schema://biella/p3-06/{evidence.category}/1",
        },
    )


def _manifest_target(configured: str) -> Path:
    path = Path(configured).expanduser()
    if path.is_dir() or path.suffix.lower() != ".json":
        return path / "p3-06-durable-evidence.json"
    return path


def test_retained_real_character_evidence_is_durable_engine_evidence(
    tmp_path: Path,
) -> None:
    root_value = os.environ.get("BIELLA_P3_06_L40S_ROOT")
    if root_value is None:
        pytest.skip("BIELLA_P3_06_L40S_ROOT does not identify retained REAL evidence")
    root = Path(root_value).expanduser().resolve(strict=True)
    retained, observed_kpis, report_path, junit_summary = (
        _discover_retained_evidence(root)
    )

    database = tmp_path / "p3-06-durable-evidence.sqlite3"
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    capability_ref = CapabilityRef("character.validate", "1.0.0")
    output_contract = {
        "evidence_manifest": "schema://biella/p3-06/durable-evidence/1"
    }
    CapabilityRegistry(database).register(
        Capability(
            capability_ref,
            "Validate exact retained REAL Blender character evidence",
            output_contract=output_contract,
        )
    )

    projects = ProjectStore(database)
    registration = projects.create_project(
        namespace="p3-06-durable-evidence",
        display_name="P3-06 Durable Character Evidence",
    )
    access = registration.access
    project_ref = access.project_ref
    tasks = TaskRevisionService(database)
    task = tasks.create_task(
        access,
        project_ref=project_ref,
        idempotency_key="p3-06-durable-evidence-task",
        task_type="character.durable-evidence",
        objective="Retain and validate exact REAL Blender character outputs",
        required_capabilities=(capability_ref,),
        input_refs=(),
        output_contract=output_contract,
        constraints={"validation.runtime_required": True},
        side_effect_authority="READ_ONLY",
        data_policy_ref="policy://p3-06/character-retained-evidence",
        egress_policy_ref="policy://p3-06/no-egress",
        evidence_requirements=("artifact", "content-ref", "provenance", "runtime"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={"slots": 1},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="worker://p3-06/durable-evidence/run",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "generic.character.durable-evidence",
        (capability_ref,),
        (),
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
        nodes=(node,),
        compiler_identity="compiler://p3-06/durable-evidence/v1",
        compiler_version="1.0.0",
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(access, run.run_ref)
    node_attempt = executions.lease_node(
        access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="worker://p3-06/durable-evidence/node",
        lease_seconds=1800,
        idempotency_key="p3-06-durable-evidence-node-lease",
    )
    node_execution = executions.start_node(
        access,
        node_attempt,
        idempotency_key="p3-06-durable-evidence-node-start",
    )

    artifacts = ArtifactService(database)
    published_by_category: dict[str, list[Artifact]] = {
        category: [] for category in _CATEGORY_ORDER
    }
    publication_sources = {
        "process": (),
        "mesh": ("process",),
        "rig": ("mesh",),
        "skin": ("mesh", "rig"),
        "deformation": ("skin",),
        "glb": ("deformation",),
        "preview": ("deformation",),
        "report": (
            "process",
            "mesh",
            "rig",
            "skin",
            "deformation",
            "glb",
            "preview",
        ),
        "junit": ("report",),
        "manifest": (
            "process",
            "mesh",
            "rig",
            "skin",
            "deformation",
            "glb",
            "preview",
            "report",
            "junit",
        ),
    }
    published: list[tuple[_RetainedFile, Artifact]] = []
    for evidence in retained:
        sources = tuple(
            source
            for category in publication_sources[evidence.category]
            for source in published_by_category[category]
        )
        artifact = _publish_retained_file(
            evidence,
            artifacts=artifacts,
            objects=objects,
            access=access,
            run_attempt=run_attempt,
            task=task,
            sources=sources,
        )
        published_by_category[evidence.category].append(artifact)
        published.append((evidence, artifact))

    assert projects.get_project(access, project_ref) == registration.project
    assert tasks.get_task(access, task.task_ref) == task
    reopened_run = runs.get_run(access, run.run_ref)
    assert reopened_run.task_ref == task.task_ref
    assert reopened_run.task_digest == task.canonical_digest
    assert reopened_run.current_attempt_id == run_attempt.attempt_id
    assert reopened_run.current_fence == run_attempt.fence
    assert reopened_run.status == "RUNNING"
    assert graph_ref.revision == 1
    assert graphs.get_graph(access, graph_ref) == graph
    assert graph.nodes == (node,)
    reopened_node = executions.get_node_execution(access, node.node_ref)
    assert reopened_node == node_execution
    assert reopened_node.status == "RUNNING"
    assert reopened_node.current_attempt_id == node_attempt.attempt_id
    assert reopened_node.current_fence == node_attempt.fence
    assert reopened_node.current_run_attempt_id == run_attempt.attempt_id
    assert reopened_node.current_run_fence == run_attempt.fence
    for evidence, artifact in published:
        assert artifacts.get_artifact(access, artifact.artifact_ref) == artifact
        assert artifact.content_ref is not None
        assert artifact.content_ref.digest == evidence.digest
        assert artifact.content_ref.size_bytes == len(evidence.payload)
        assert objects.read(artifact.content_ref) == evidence.payload

    validations = ValidationService(database)
    subjects = tuple(
        validations.bind_artifact_subject(
            access,
            artifact.artifact_ref,
            producer_dimensions={
                "content_ref": cast(ContentRef, artifact.content_ref).value,
            },
        )
        for _, artifact in published
    )
    kpi_checks = tuple(
        ValidationCheck(
            capability_ref,
            True,
            "project.criteria:p3-06-character-kpi",
            ("artifact", "content_ref", "provenance"),
            (),
            {"expected": 0, "kpi": name},
        )
        for name in _KPI_NAMES
    )
    plan = validations.compile_plan(
        access,
        node_attempt,
        subjects=subjects,
        project_criteria=ProjectValidationCriteria(
            project_ref,
            kpi_checks,
            "criteria://p3-06/character-durable-evidence/v1",
        ),
        idempotency_key="p3-06-durable-evidence-validation-plan",
    )
    assert validations.get_plan(access, plan.plan_ref) == plan
    report_artifact = published_by_category["report"][0]
    evidence_refs = tuple(
        [artifact.artifact_ref.value for _, artifact in published]
        + [cast(ContentRef, artifact.content_ref).value for _, artifact in published]
    )
    validator_ref = "validator://p3-06/durable-evidence/v1"
    runtime_ref = "runtime://blender/l40s-retained-evidence"
    results = []
    kpi_results = {}
    for check in plan.checks:
        kpi_name = check.parameters.get("kpi")
        metrics = ()
        if isinstance(kpi_name, str):
            assert kpi_name in _KPI_NAMES
            assert float(observed_kpis[kpi_name]) == 0.0
            metrics = (
                MetricMeasurement(
                    kpi_name,
                    0.0,
                    "count",
                    f"Exact {kpi_name} violations in the retained P3-06 report",
                    report_artifact.artifact_ref.value,
                ),
            )
        result = validations.record_result(
            access,
            node_attempt,
            plan.plan_ref,
            check_id=check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref=validator_ref,
            runtime_ref=runtime_ref,
            validator_dimensions={
                "implementation": validator_ref,
                "runtime": runtime_ref,
            },
            evidence_refs=evidence_refs,
            metrics=metrics,
            idempotency_key=f"p3-06-result-{check.check_id}",
        )
        assert validations.get_result(access, result.result_ref) == result
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
        results.append(result)
        if isinstance(kpi_name, str):
            kpi_results[kpi_name] = result
    assert set(kpi_results) == set(_KPI_NAMES)
    for name in _KPI_NAMES:
        assert len(kpi_results[name].metrics) == 1
        assert kpi_results[name].metrics[0].name == name
        assert kpi_results[name].metrics[0].value == 0.0
    aggregate = validations.aggregate(
        access,
        node_attempt,
        plan.plan_ref,
        idempotency_key="p3-06-durable-evidence-validation-aggregate",
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
        node_ref=node.node_ref,
        event_type="P3_06_DURABLE_EVIDENCE_RETAINED",
        idempotency_key="p3-06-durable-evidence-retained",
        actor_ref="worker://p3-06/durable-evidence",
        object_refs=tuple(artifact.artifact_ref for _, artifact in published),
        metadata={
            "artifact_count": len(published),
            "authority_attempt_sha256": node_attempt.record_sha256,
            "kpi_count": len(_KPI_NAMES),
            "validation_aggregate_sha256": aggregate.aggregate_sha256,
            "validation_result_count": len(results),
        },
        payload_ref=cast(ContentRef, report_artifact.content_ref),
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
        evidence_ref=report_artifact.artifact_ref,
        authority_attempt=run_attempt,
        actor_ref=run_attempt.owner_ref,
        idempotency_key="p3-06-durable-evidence-acceptance",
    )
    process_artifact = next(
        artifact
        for evidence, artifact in published
        if evidence.path.name == "process-record.json"
    )
    provenance_artifact = published_by_category["glb"][0]
    manifest_artifact = published_by_category["manifest"][0]
    completed_node = executions.finalize_node(
        access,
        node_attempt,
        outputs={"evidence_manifest": manifest_artifact.artifact_ref},
        evidence={
            "artifact": manifest_artifact.artifact_ref,
            "content-ref": cast(ContentRef, manifest_artifact.content_ref),
            "provenance": provenance_artifact.artifact_ref,
            "runtime": process_artifact.artifact_ref,
        },
        acceptance_criteria=(),
        idempotency_key="p3-06-durable-evidence-finalize",
    )
    assert completed_node.status == "SUCCEEDED"
    assert executions.get_node_execution(access, node.node_ref) == completed_node
    completed_run = runs.get_run(access, run.run_ref)
    assert completed_run.status == "SUCCEEDED"

    manifest = {
        "artifacts": [
            {
                "artifact_ref": artifact.artifact_ref.value,
                "artifact_sha256": artifact.record_sha256,
                "bytes": cast(ContentRef, artifact.content_ref).size_bytes,
                "category": evidence.category,
                "content_ref": cast(ContentRef, artifact.content_ref).value,
                "media_type": cast(ContentRef, artifact.content_ref).media_type,
                "path": evidence.path.relative_to(root).as_posix(),
                "role": artifact.role,
                "sha256": cast(ContentRef, artifact.content_ref).digest,
                "source_artifact_refs": [
                    source.value for source in artifact.source_artifact_refs
                ],
            }
            for evidence, artifact in published
        ],
        "event": {
            "record_sha256": event.record_sha256,
            "ref": event.event_ref.value,
        },
        "acceptance_event": {
            "record_sha256": acceptance_event.record_sha256,
            "ref": acceptance_event.event_ref.value,
        },
        "graph": {
            "node_attempt_fence": node_attempt.fence,
            "node_attempt_id": node_attempt.attempt_id,
            "node_attempt_sha256": node_attempt.record_sha256,
            "node_ref": node.node_ref.value,
            "node_status": completed_node.status,
            "record_sha256": graph.record_sha256,
            "ref": graph_ref.value,
        },
        "junit": junit_summary,
        "kpis": {name: 0 for name in _KPI_NAMES},
        "project_ref": project_ref.value,
        "retained_root": str(root),
        "run": {
            "attempt_fence": run_attempt.fence,
            "attempt_id": run_attempt.attempt_id,
            "attempt_sha256": run_attempt.record_sha256,
            "ref": {
                "project_ref": run.run_ref.project_ref.value,
                "run_id": run.run_ref.run_id,
            },
            "run_id": run.run_ref.run_id,
            "status": completed_run.status,
        },
        "schema_version": 1,
        "suite_id": "p3-06-durable-character-evidence-v1",
        "task": {
            "canonical_sha256": task.canonical_digest,
            "ref": {
                "project_ref": task.task_ref.project_ref.value,
                "revision": task.task_ref.revision,
                "task_id": task.task_ref.task_id,
            },
            "revision": task.task_ref.revision,
            "task_id": task.task_ref.task_id,
        },
        "validation": {
            "accepted": aggregate.accepted,
            "aggregate_sha256": aggregate.aggregate_sha256,
            "plan_ref": plan.plan_ref.value,
            "plan_sha256": plan.record_sha256,
            "result_refs": [result.result_ref.value for result in results],
            "verdict": aggregate.verdict.value,
        },
        "validation_report_path": report_path.relative_to(root).as_posix(),
    }
    output_value = os.environ.get("BIELLA_P3_06_EVIDENCE_OUT")
    if output_value:
        output_path = _manifest_target(output_value)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
