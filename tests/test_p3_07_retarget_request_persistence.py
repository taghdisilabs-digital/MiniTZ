"""P3-07 durable, versioned retarget-request publication contract."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import sqlite3

import pytest

from biella import (
    AnimationClip,
    Artifact,
    ArtifactRef,
    ArtifactService,
    BoneMapping,
    CharacterRigRef,
    FilesystemObjectStorageBackend,
    ProjectAccess,
    ProjectStore,
    ReferenceThreeDToolAdapter,
    RetargetMapping,
    RetargetRequest,
)
from biella.animation_pack import AnimationContractError


_POLICIES = {"mapping", "coordinate", "scale", "root_motion", "export"}


@dataclass(frozen=True)
class _Fixture:
    database: Path
    access: ProjectAccess
    objects: FilesystemObjectStorageBackend
    artifacts: ArtifactService
    adapter: ReferenceThreeDToolAdapter
    request: RetargetRequest
    source_artifacts: tuple[Artifact, ...]


def _fixture(tmp_path: Path) -> _Fixture:
    database = tmp_path / "retarget-request.sqlite3"
    registration = ProjectStore(database).create_project(
        namespace="p3-07-retarget-request",
        display_name="P3-07 Retarget Request",
    )
    access = registration.access
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    artifacts = ArtifactService(database)

    def source_artifact(role: str, raw: bytes) -> Artifact:
        content = objects.put(raw, media_type="application/octet-stream")
        return artifacts.create_artifact(
            access,
            project_ref=access.project_ref,
            role=role,
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="animation.fixture-source",
            metadata={"media_type": "application/octet-stream"},
        )

    clip_artifact = source_artifact("animation.clip", b"exact editable clip bytes")
    mapping_artifact = source_artifact(
        "animation.retarget-mapping", b"exact retarget mapping bytes"
    )
    source_rig_artifact = source_artifact(
        "animation.source-rig", b"exact source rig bytes"
    )
    target_rig_artifact = source_artifact(
        "animation.target-rig", b"exact target rig bytes"
    )
    assert all(item.content_ref is not None for item in (
        clip_artifact,
        mapping_artifact,
        source_rig_artifact,
        target_rig_artifact,
    ))

    def rig(name: str, artifact: Artifact, skeleton_digest: str) -> CharacterRigRef:
        assert artifact.content_ref is not None
        return CharacterRigRef(
            project_ref=access.project_ref,
            character_id=f"{name}-character",
            character_artifact_ref=f"artifact://character/{name}/source/v1",
            character_content_sha256="a" * 64,
            mesh_ref=f"artifact://character/{name}/mesh/v1",
            mesh_content_sha256="b" * 64,
            skeleton_ref=f"artifact://character/{name}/skeleton/v1",
            skeleton_content_sha256=skeleton_digest,
            rig_id=f"{name}-rig",
            rig_artifact_ref=artifact.artifact_ref.value,
            rig_content_sha256=artifact.content_ref.digest,
            scale=(1.0, 1.0, 1.0),
            coordinate_system={"up": "Z", "forward": "Y"},
            coordinate_convention_ref="contract://coordinate/z-up/v1",
            rest_pose_ref=f"artifact://character/{name}/rest-pose/v1",
            provenance_ref=f"provenance://character/{name}/rig/v1",
            tool_provenance_ref="provenance://tool/character/v1",
            script_provenance_ref="provenance://script/character/v1",
            target_metadata={},
        )

    source_rig = rig("source", source_rig_artifact, "c" * 64)
    target_rig = rig("target", target_rig_artifact, "d" * 64)
    assert clip_artifact.content_ref is not None
    clip = AnimationClip(
        project_ref=access.project_ref,
        clip_id="walk-cycle",
        source_artifact_ref=clip_artifact.artifact_ref.value,
        content_sha256=clip_artifact.content_ref.digest,
        character_rig_ref=source_rig,
        start_time=0.0,
        end_time=1.0,
        duration_seconds=1.0,
        frame_rate=30.0,
        time_unit="seconds",
        channel_summary={"translation": 3, "rotation": 4},
        root_motion_metadata={"policy": "preserve"},
        loop_metadata={"mode": "seamless"},
        coordinate_system={"up": "Z", "forward": "Y"},
        coordinate_convention_ref="contract://coordinate/z-up/v1",
        tool_provenance_ref="provenance://tool/animation/v1",
        runtime_ref="runtime://animation/reference/v1",
        content_ref=f"content://sha256/{clip_artifact.content_ref.digest}",
    )
    assert mapping_artifact.content_ref is not None
    mapping = RetargetMapping(
        project_ref=access.project_ref,
        mapping_id="walk-source-to-target",
        mapping_version="1.0.0",
        source_rig_ref=source_rig,
        target_rig_ref=target_rig,
        bone_mappings=(
            BoneMapping("hip", "pelvis"),
            BoneMapping("spine", "spine-main"),
        ),
        mapping_ref=mapping_artifact.artifact_ref.value,
        content_sha256=mapping_artifact.content_ref.digest,
    )
    request = RetargetRequest(
        project_ref=access.project_ref,
        request_id="walk-retarget",
        clip=clip,
        source_rig_ref=source_rig,
        target_rig_ref=target_rig,
        mapping=mapping,
        source_scale=(1.0, 1.0, 1.0),
        target_scale=(1.0, 1.0, 1.0),
        transform=(1.0,) * 16,
        root_motion_metadata={"policy": "preserve"},
        output_contract_refs=("contract://output/animation/v1",),
        policy_refs={name: f"policy://animation/{name}/v1" for name in _POLICIES},
        policy_versions={name: "1.0.0" for name in _POLICIES},
        request_version="1.0.0",
    )
    return _Fixture(
        database=database,
        access=access,
        objects=objects,
        artifacts=artifacts,
        adapter=ReferenceThreeDToolAdapter(database, objects),
        request=request,
        source_artifacts=(
            clip_artifact,
            mapping_artifact,
            source_rig_artifact,
            target_rig_artifact,
        ),
    )


def test_persisted_retarget_request_has_exact_bytes_lineage_and_idempotent_readback(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    publication = fixture.adapter.persistRetargetRequest(
        fixture.access, fixture.request
    )
    stored = fixture.objects.read(publication.request_content_ref)
    artifact = fixture.artifacts.get_artifact(
        fixture.access, publication.request_artifact_ref
    )
    replayed = ReferenceThreeDToolAdapter(
        fixture.database, fixture.objects
    ).persistRetargetRequest(fixture.access, fixture.request)

    assert stored == fixture.request.canonical_bytes()
    assert stored == json.dumps(
        json.loads(stored),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert publication.request_content_ref.digest == fixture.request.request_sha256
    assert publication.request.request_id == "walk-retarget"
    assert publication.request.request_version == "1.0.0"
    assert artifact.role == "3d.retarget-request"
    assert artifact.derivation_type == "3d.retarget-request"
    assert set(artifact.source_artifact_refs) == {
        item.artifact_ref for item in fixture.source_artifacts
    }
    assert replayed == publication
    assert ReferenceThreeDToolAdapter(
        fixture.database, fixture.objects
    ).verifyRetargetRequestPublication(fixture.access, replayed) == publication


def test_retarget_request_persistence_rejects_cross_pairs_forgery_and_conflicts(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    publication = fixture.adapter.persistRetargetRequest(
        fixture.access, fixture.request
    )
    unrelated = fixture.objects.put(
        b"unrelated clip bytes", media_type="application/octet-stream"
    )
    cross_paired = replace(
        fixture.request,
        request_id="cross-paired-request",
        clip=replace(fixture.request.clip, content_sha256=unrelated.digest),
    )
    forged = replace(
        fixture.request,
        request_id="forged-source-request",
        mapping=replace(
            fixture.request.mapping,
            mapping_ref=(
                f"artifact://{fixture.access.project_ref.value}/"
                f"{fixture.source_artifacts[1].artifact_ref.artifact_id}/"
                f"{fixture.source_artifacts[1].artifact_ref.revision + 1}"
            ),
        ),
    )
    conflicting = replace(
        fixture.request,
        root_motion_metadata={"policy": "extract"},
    )

    with pytest.raises(AnimationContractError, match="source content identity changed"):
        fixture.adapter.persistRetargetRequest(fixture.access, cross_paired)
    with pytest.raises(AnimationContractError, match="source Artifact is not durable"):
        fixture.adapter.persistRetargetRequest(fixture.access, forged)
    with pytest.raises(
        AnimationContractError,
        match="ID and version conflict with durable bytes",
    ):
        fixture.adapter.persistRetargetRequest(fixture.access, conflicting)
    with pytest.raises(AnimationContractError):
        fixture.adapter.verifyRetargetRequestPublication(
            fixture.access,
            replace(
                publication,
                request_artifact_ref=fixture.source_artifacts[0].artifact_ref,
            ),
        )


def test_retarget_request_sqlite_record_is_immutable(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    publication = fixture.adapter.persistRetargetRequest(
        fixture.access, fixture.request
    )
    key = (
        fixture.access.project_ref.value,
        "adapter://3d/reference/v1",
        fixture.request.request_id,
        fixture.request.request_version,
    )
    connection = sqlite3.connect(fixture.database)
    try:
        row = connection.execute(
            "SELECT request_semantic_sha256,artifact_id,artifact_revision,content_sha256 "
            "FROM three_d_retarget_request_records WHERE project_id=? AND adapter_ref=? "
            "AND request_id=? AND request_version=?",
            key,
        ).fetchone()
        assert row == (
            fixture.request.request_sha256,
            publication.request_artifact_ref.artifact_id,
            publication.request_artifact_ref.revision,
            fixture.request.request_sha256,
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE three_d_retarget_request_records SET content_sha256=? "
                "WHERE project_id=? AND adapter_ref=? AND request_id=? AND request_version=?",
                ("0" * 64, *key),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM three_d_retarget_request_records WHERE project_id=? "
                "AND adapter_ref=? AND request_id=? AND request_version=?",
                key,
            )
        connection.rollback()
    finally:
        connection.close()

    assert fixture.adapter.verifyRetargetRequestPublication(
        fixture.access, publication
    ) == publication
