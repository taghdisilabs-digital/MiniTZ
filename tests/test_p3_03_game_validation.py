"""P3-03 generic package validation and kernel-neutrality invariants."""

from __future__ import annotations

import ast
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest
from biella import (
    Artifact,
    ArtifactService,
    FilesystemObjectStorageBackend,
    GraphRef,
    GraphService,
    Node,
    NodeExecutionService,
    NodeRef,
    ProductionPackRegistry,
    ProjectAccess,
    ProjectStore,
    ProjectValidationCriteria,
    RunService,
    TaskRevisionService,
    ValidationCheck,
    ValidationContractError,
    ValidationEvidenceState,
    ValidationService,
    ValidationVerdict,
    game_production_pack,
)


_ROOT = Path(__file__).resolve().parents[1]
_VALIDATED_ROLES = {
    "game.build.output",
    "game.capture.output",
    "game.engine.detection",
    "game.export.output",
    "game.import.output",
    "game.package.output",
    "game.profile.report",
    "game.project.inspection",
    "game.runtime.observation",
    "game.test.result",
    "game.validation.result",
}


def test_t01_p3_03_sources_have_no_test_escape_hatches() -> None:
    affected = (
        _ROOT / "src/biella/game_engine.py",
        _ROOT / "src/biella/game_pack.py",
        *sorted((_ROOT / "tests").glob("test_p3_03_*.py")),
        *sorted(
            path
            for path in (_ROOT / "tests/fixtures/p3_03_game_project").rglob("*")
            if path.is_file()
        ),
    )
    forbidden_tokens = (
        "pytest.mark." + "skip",
        "pytest.mark." + "xfail",
        "pytest." + "skip" + "(",
        "pytest." + "xfail" + "(",
        "pytest.importor" + "skip",
        "unittest." + "skip",
        "Not" + "Implemented",
        "TO" + "DO",
        "FIX" + "ME",
        "place" + "holder",
    )

    assert affected
    for path in affected:
        source = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{path.relative_to(_ROOT)} contains {token}"


def test_t02_active_runtime_and_universal_kernel_remain_game_neutral() -> None:
    active_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((_ROOT / "src/biella").rglob("*.py"))
        if path.name != "migration.py"
    )
    assert "Quarantine" + "Ref" not in active_runtime

    kernel_paths = tuple(
        _ROOT / "src/biella" / name
        for name in (
            "task.py",
            "run.py",
            "graph.py",
            "project.py",
            "scheduler.py",
            "resource.py",
            "production_pack.py",
        )
    )
    vendor_pattern = re.compile(r"\b(?:godot|unity|unreal)\b", re.IGNORECASE)
    forbidden_domain_types = (
        "GameEngineAdapter",
        "GameEngineOperation",
        "GameProjectIdentity",
        "GameAssetInput",
    )
    for path in kernel_paths:
        source = path.read_text(encoding="utf-8")
        assert vendor_pattern.search(source) is None, path
        assert not any(token in source for token in forbidden_domain_types), path
        class_names = {
            node.name
            for node in ast.walk(ast.parse(source, filename=str(path)))
            if isinstance(node, ast.ClassDef)
        }
        assert not any(name.startswith("Game") for name in class_names), path


def _zip_entry(name: str, payload: bytes) -> tuple[ZipInfo, bytes]:
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = ZIP_STORED
    entry.external_attr = 0o100644 << 16
    return entry, payload


def _artifact(
    artifacts: ArtifactService,
    objects: FilesystemObjectStorageBackend,
    access: ProjectAccess,
    *,
    role: str,
    payload: bytes,
    media_type: str,
    sources: tuple[Artifact, ...],
) -> Artifact:
    content_ref = objects.put(payload, media_type=media_type)
    created = artifacts.create_artifact(
        access,
        project_ref=access.project_ref,
        role=role,
        content_ref=content_ref,
        source_refs=(),
        source_artifact_refs=tuple(item.artifact_ref for item in sources),
        source_content_refs=tuple(
            item.content_ref for item in sources if item.content_ref is not None
        ),
        derivation_type=f"game.validation.fixture.{role}",
        metadata={
            "schema_ref": f"schema://biella/{role.replace('.', '-')}/1",
            "schema_version": "1.0.0",
            "semantic_label": f"p3-03-{role.replace('.', '-')}",
        },
    )
    objects.verify(content_ref)
    assert objects.read(content_ref) == payload
    return created


def test_t03_real_package_artifact_and_registered_game_roles_aggregate(
    tmp_path: Path,
) -> None:
    database = tmp_path / "p3-03-game-validation.sqlite3"
    registration = ProjectStore(database).create_project(
        namespace="p3-03-game-validation",
        display_name="P3-03 Game Validation",
    )
    access = registration.access
    pack = ProductionPackRegistry(database).register(
        game_production_pack(),
        idempotency_key="p3-03-register-game-validation-pack",
    )
    validator_prefix = "validation-check://artifact-role/"
    registrations_by_role = {}
    for item in pack.validators:
        assert item.validator_ref.startswith(validator_prefix)
        assert item.validator_ref.endswith("/v1")
        role = item.validator_ref.removeprefix(validator_prefix).removesuffix("/v1")
        registrations_by_role[role] = item
    assert set(registrations_by_role) == _VALIDATED_ROLES

    capabilities = tuple(
        sorted(item.capability_ref for item in pack.capability_definitions)
    )
    task = TaskRevisionService(database).create_task(
        access,
        project_ref=access.project_ref,
        idempotency_key="p3-03-game-validation-task",
        task_type="game.validation",
        objective="Validate exact game role and package provenance",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={},
        constraints={},
        side_effect_authority="PROJECT_WRITE",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=(),
        acceptance_criteria=(),
        resource_hints={},
    )
    runs = RunService(database)
    run = runs.create_run(access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        access,
        run.run_ref,
        owner_ref="controller://p3-03-game-validation",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(access.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "VALIDATE",
        capabilities,
        (),
        (),
        {},
        None,
        "PROJECT_WRITE",
        {},
        (),
    )
    GraphService(database).create_graph(
        access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(access, run.run_ref)
    attempt = executions.lease_node(
        access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="executor://p3-03-game-validation",
        lease_seconds=1800,
        idempotency_key="p3-03-game-validation-lease",
    )
    executions.start_node(
        access,
        attempt,
        idempotency_key="p3-03-game-validation-start",
    )

    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    artifacts = ArtifactService(database)
    candidate = _artifact(
        artifacts,
        objects,
        access,
        role="workspace.snapshot",
        payload=b'{"candidate":"p3-03-validation-fixture","classification":"REFERENCE"}\n',
        media_type="application/json",
        sources=(),
    )
    produced: dict[str, Artifact] = {}
    for role in (
        "game.engine.detection",
        "game.project.inspection",
        "game.import.output",
    ):
        produced[role] = _artifact(
            artifacts,
            objects,
            access,
            role=role,
            payload=json.dumps(
                {"classification": "REFERENCE", "role": role},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            media_type="application/json",
            sources=(candidate,),
        )
    build = _artifact(
        artifacts,
        objects,
        access,
        role="game.build.output",
        payload=b"GDPC-p3-03-reference-build-bytes\n",
        media_type="application/octet-stream",
        sources=(candidate, produced["game.import.output"]),
    )
    produced[build.role] = build
    for role in (
        "game.runtime.observation",
        "game.test.result",
        "game.profile.report",
        "game.capture.output",
    ):
        produced[role] = _artifact(
            artifacts,
            objects,
            access,
            role=role,
            payload=json.dumps(
                {"classification": "REFERENCE", "role": role},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            media_type="application/json",
            sources=(candidate, build),
        )
    export_payload = b"GDPC-p3-03-reference-export-bytes\n"
    exported = _artifact(
        artifacts,
        objects,
        access,
        role="game.export.output",
        payload=export_payload,
        media_type="application/octet-stream",
        sources=(candidate, build),
    )
    produced[exported.role] = exported

    package_manifest = {
        "classification": "REFERENCE",
        "format": "zip",
        "source_artifact_ref": exported.artifact_ref.value,
    }
    package_buffer = BytesIO()
    with ZipFile(package_buffer, mode="w") as archive:
        archive.writestr(
            *_zip_entry(
                "manifest.json",
                json.dumps(
                    package_manifest,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
        )
        archive.writestr(*_zip_entry("game/biella-game.pck", export_payload))
    package = _artifact(
        artifacts,
        objects,
        access,
        role="game.package.output",
        payload=package_buffer.getvalue(),
        media_type="application/zip",
        sources=(candidate, build, exported),
    )
    produced[package.role] = package
    assert package.content_ref is not None
    with ZipFile(BytesIO(objects.read(package.content_ref))) as archive:
        assert archive.namelist() == ["manifest.json", "game/biella-game.pck"]
        assert json.loads(archive.read("manifest.json")) == package_manifest
        assert archive.read("game/biella-game.pck") == export_payload

    service = ValidationService(database)
    first_roles = _VALIDATED_ROLES - {"game.validation.result"}
    criteria = ProjectValidationCriteria(
        access.project_ref,
        tuple(
            ValidationCheck(
                registrations_by_role[role].capability_ref,
                True,
                registrations_by_role[role].registration_ref,
                ("artifact",),
                parameters={
                    "artifact_role": role,
                    "source_artifact_ref": candidate.artifact_ref.value,
                },
            )
            for role in sorted(first_roles)
        ),
        "config://sha256/" + "a" * 64,
    )
    plan = service.compile_plan(
        access,
        attempt,
        subjects=tuple(
            service.bind_artifact_subject(access, item.artifact_ref)
            for item in (candidate, *tuple(produced[role] for role in sorted(first_roles)))
        ),
        project_criteria=criteria,
        idempotency_key="p3-03-game-role-validation-plan",
    )
    checks_by_role = {
        item.parameters["artifact_role"]: item
        for item in plan.checks
        if "artifact_role" in item.parameters
    }
    assert set(checks_by_role) == first_roles
    with pytest.raises(ValidationContractError, match="role"):
        service.record_result(
            access,
            attempt,
            plan.plan_ref,
            check_id=checks_by_role["game.package.output"].check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref=registrations_by_role[
                "game.package.output"
            ].validator_ref,
            runtime_ref="runtime://validation/deterministic-cpu",
            evidence_refs=(exported.artifact_ref.value,),
            idempotency_key="p3-03-reject-export-as-package",
        )
    for role in sorted(first_roles):
        result = service.record_result(
            access,
            attempt,
            plan.plan_ref,
            check_id=checks_by_role[role].check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref=registrations_by_role[role].validator_ref,
            runtime_ref="runtime://validation/deterministic-cpu",
            evidence_refs=(produced[role].artifact_ref.value,),
            idempotency_key=f"p3-03-validate-{role.replace('.', '-')}",
        )
        assert result.verdict is ValidationVerdict.PASS
        assert result.evidence_state is ValidationEvidenceState.CURRENT
    first_aggregate = service.aggregate(
        access,
        attempt,
        plan.plan_ref,
        idempotency_key="p3-03-game-role-validation-aggregate",
    )
    assert first_aggregate.verdict is ValidationVerdict.PASS
    assert first_aggregate.accepted
    assert not first_aggregate.missing_required_check_ids

    validation_payload = json.dumps(
        first_aggregate.payload(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    validation_artifact = _artifact(
        artifacts,
        objects,
        access,
        role="game.validation.result",
        payload=validation_payload,
        media_type="application/json",
        sources=(candidate, package),
    )
    validation_registration = registrations_by_role["game.validation.result"]
    validation_criteria = ProjectValidationCriteria(
        access.project_ref,
        (
            ValidationCheck(
                validation_registration.capability_ref,
                True,
                validation_registration.registration_ref,
                ("artifact",),
                parameters={
                    "artifact_role": "game.validation.result",
                    "source_artifact_ref": candidate.artifact_ref.value,
                },
            ),
        ),
        "config://sha256/" + "b" * 64,
    )
    validation_plan = service.compile_plan(
        access,
        attempt,
        subjects=(
            service.bind_artifact_subject(access, candidate.artifact_ref),
            service.bind_artifact_subject(access, validation_artifact.artifact_ref),
        ),
        project_criteria=validation_criteria,
        idempotency_key="p3-03-validation-artifact-plan",
    )
    validation_check = next(
        item
        for item in validation_plan.checks
        if item.parameters.get("artifact_role") == "game.validation.result"
    )
    service.record_result(
        access,
        attempt,
        validation_plan.plan_ref,
        check_id=validation_check.check_id,
        verdict=ValidationVerdict.PASS,
        validator_kind="DETERMINISTIC",
        implementation_ref=validation_registration.validator_ref,
        runtime_ref="runtime://validation/deterministic-cpu",
        evidence_refs=(validation_artifact.artifact_ref.value,),
        idempotency_key="p3-03-validate-aggregate-artifact",
    )
    final_aggregate = service.aggregate(
        access,
        attempt,
        validation_plan.plan_ref,
        idempotency_key="p3-03-validation-artifact-aggregate",
    )
    assert final_aggregate.verdict is ValidationVerdict.PASS
    assert final_aggregate.accepted
    assert not final_aggregate.missing_required_check_ids
    assert validation_artifact.content_ref is not None
    assert json.loads(objects.read(validation_artifact.content_ref)) == (
        first_aggregate.payload()
    )
