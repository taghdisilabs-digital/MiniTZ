"""Focused P4-04 cache, locality, residency, and placement contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from biella.artifact import Artifact, ArtifactService, ContentRef
from biella.placement_learning import (
    CacheRetentionEstimate,
    LocalityObservation,
    PlacementEvidenceState,
    PlacementEstimate,
    PlacementLearningError,
)
from biella.project import ProjectAccess
from biella.resource import Resource, ResourceArtifactLocality, ResourceLocality
from test_p1_07_resource_inventory import FakeResourceObserver, _inventory, _observation  # type: ignore[attr-defined]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _locality(
    tmp_path: Path,
) -> tuple[ProjectAccess, Resource, Artifact, LocalityObservation, ContentRef]:
    service, access, resource = _inventory(tmp_path)
    content = ContentRef.from_bytes(b"p4-04-local", media_type="application/octet-stream")
    artifact = ArtifactService(service.database_path).create_artifact(
        access,
        project_ref=resource.project_ref,
        role="resource.locality",
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="resource.observed",
        metadata={},
    )
    locality = ResourceLocality(
        loaded_model_refs=("model://p4-04/weights",),
        warm_cache_refs=("cache://p4-04/weights",),
        local_artifact_refs=(ResourceArtifactLocality(artifact.artifact_ref, artifact.record_sha256),),
        observed_dimensions=("loaded_model_refs", "warm_cache_refs", "local_artifact_refs"),
    )
    snapshot = service.observe_resource(
        access,
        resource.resource_ref,
        FakeResourceObserver((_observation(0, locality=locality),)),
    )
    observation = LocalityObservation(
        project_ref=resource.project_ref,
        observation_id="l40s-cache",
        version=1,
        resource_snapshot_ref=snapshot.snapshot_ref,
        resource_snapshot_record_sha256=snapshot.record_sha256,
        locality=locality,
        observed_at=_now(),
        fresh_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"),
        evidence_refs=(artifact.artifact_ref.value,),
    )
    return access, resource, artifact, observation, content


def test_locality_observation_is_project_scoped_versioned_and_snapshot_exact(tmp_path: Path) -> None:
    _, resource, _, observation, _ = _locality(tmp_path)

    assert observation.project_ref == resource.project_ref
    assert observation.locality.warm_cache_refs == ("cache://p4-04/weights",)
    assert len(observation.canonical_digest) == 64
    with pytest.raises(PlacementLearningError):
        replace(observation, resource_snapshot_record_sha256="0" * 64)


def test_placement_estimate_binds_artifact_content_workspace_and_locality(tmp_path: Path) -> None:
    _, resource, artifact, observation, content = _locality(tmp_path)
    estimate = PlacementEstimate(
        project_ref=resource.project_ref,
        estimate_id="artifact-placement",
        version=1,
        workload_ref="workload://p4-04/locality/v1",
        workload_digest="a" * 64,
        artifact_ref=artifact.artifact_ref,
        content_ref=content,
        workspace_ref="workspace://p4-04/current",
        locality_observation=observation,
        target_resource_ref=resource.resource_ref,
        resource_identity_digest=observation.resource_snapshot_record_sha256,
        metrics={"locality_hit_rate": 1.0, "transfer_seconds": 0.0, "cost": None},
        evidence_refs=(artifact.artifact_ref.value,),
        observed_at=_now(),
        fresh_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"),
        supersedes=None,
    )

    assert estimate.artifact_ref == artifact.artifact_ref
    assert estimate.content_ref == content
    assert estimate.metrics["cost"] is None
    with pytest.raises(PlacementLearningError):
        replace(estimate, content_ref=ContentRef.from_bytes(b"different", media_type="application/octet-stream"))


def test_cache_retention_is_evidence_bounded_unknown_safe_and_non_promotional(tmp_path: Path) -> None:
    _, resource, _, observation, content = _locality(tmp_path)
    retention = CacheRetentionEstimate(
        project_ref=resource.project_ref,
        estimate_id="weights-retention",
        version=1,
        cache_ref="cache://p4-04/weights",
        content_ref=content,
        locality_observation=observation,
        evidence_state=PlacementEvidenceState.UNKNOWN_EVIDENCE,
        expected_retention_seconds=None,
        evidence_refs=("artifact://cache-evidence/one",),
        observed_at=_now(),
        fresh_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"),
        supersedes=None,
    )

    assert retention.expected_retention_seconds is None
    assert retention.evidence_state is PlacementEvidenceState.UNKNOWN_EVIDENCE
    assert retention.promotion_allowed is False
    assert retention.routing_override_allowed is False
    with pytest.raises(PlacementLearningError):
        replace(retention, evidence_state=PlacementEvidenceState.OBSERVED, expected_retention_seconds=None)


def test_stale_or_cross_project_locality_cannot_lower_zero_kpi_guards(tmp_path: Path) -> None:
    _, resource, _, observation, content = _locality(tmp_path)
    with pytest.raises(PlacementLearningError):
        replace(observation, fresh_until=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds"))
    with pytest.raises(PlacementLearningError):
        CacheRetentionEstimate(
            project_ref=resource.project_ref,
            estimate_id="forged-cache",
            version=1,
            cache_ref="cache://p4-04/weights",
            content_ref=content,
            locality_observation=observation,
            evidence_state=PlacementEvidenceState.OBSERVED,
            expected_retention_seconds=30,
            evidence_refs=(),
            observed_at=_now(),
            fresh_until=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"),
            supersedes=None,
        )
