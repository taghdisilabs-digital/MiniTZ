"""Task-scoped VFX simulation recovery planning.

This module records the deterministic recovery decision used by the P3-10
simulation adapter path when storage/resource pressure interrupts a long bake.
It is deliberately provider-neutral data and does not introduce a second
scheduler, object store, cache, or validation framework.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
import re
from typing import Literal

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .project import ProjectAccess, ProjectRef
from .vfx_pack import SimulationCheckpointRef, SimulationContractError, SimulationSpecification

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
_ARTIFACT_REF = re.compile(r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)")
_RESOURCE_EXHAUSTION_MARKERS = (
    "enospc",
    "no space left on device",
    "disk full",
    "resource exhausted",
    "storage exhausted",
    "out of space",
)


class SimulationRecoveryContractError(ValueError):
    """A simulation recovery plan would violate P3-10 recovery guarantees."""


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise SimulationRecoveryContractError(f"{name} must be an exact sha256 digest")
    return value


def _ref(value: object, name: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise SimulationRecoveryContractError(f"{name} must be a bounded absolute ref")
    return value


def _attempt(value: object, fence: object) -> tuple[str, int]:
    if not isinstance(value, str) or _ATTEMPT.fullmatch(value) is None:
        raise SimulationRecoveryContractError("producer_attempt_id is invalid")
    if not isinstance(fence, int) or isinstance(fence, bool) or fence < 1:
        raise SimulationRecoveryContractError("producer_fence is invalid")
    return value, fence


def _frame(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SimulationRecoveryContractError(f"{name} must be an integer frame")
    return value


def _resource_exhaustion(reason: str) -> bool:
    lowered = reason.lower()
    return any(marker in lowered for marker in _RESOURCE_EXHAUSTION_MARKERS)


@dataclass(frozen=True)
class VerifiedSimulationSegment:
    """A durable verified checkpoint segment, not rebuildable cache authority."""

    specification_digest: str
    frame_start: int
    frame_end: int
    checkpoint_artifact_ref: str
    checkpoint_content_sha256: str
    producer_attempt_id: str
    producer_fence: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "specification_digest", _sha256(self.specification_digest, "specification_digest"))
        start = _frame(self.frame_start, "frame_start")
        end = _frame(self.frame_end, "frame_end")
        if start < 0 or end < start:
            raise SimulationRecoveryContractError("verified segment frame range is invalid")
        object.__setattr__(self, "frame_start", start)
        object.__setattr__(self, "frame_end", end)
        object.__setattr__(self, "checkpoint_artifact_ref", _ref(self.checkpoint_artifact_ref, "checkpoint_artifact_ref"))
        object.__setattr__(self, "checkpoint_content_sha256", _sha256(self.checkpoint_content_sha256, "checkpoint_content_sha256"))
        attempt, fence = _attempt(self.producer_attempt_id, self.producer_fence)
        object.__setattr__(self, "producer_attempt_id", attempt)
        object.__setattr__(self, "producer_fence", fence)


@dataclass(frozen=True)
class SimulationResourceRecoveryPlan:
    """Exact P3-10 recovery decision for interrupted long simulations."""

    specification_digest: str
    failure_classification: Literal["RESOURCE_EXHAUSTED"]
    failure_reason: str
    frame_start: int
    frame_end: int
    failed_frame: int
    preserved_segments: tuple[tuple[int, int], ...]
    latest_verified_frame: int | None
    resume_frame_start: int
    resume_frame_end: int
    frames_to_dispatch: tuple[int, ...]
    frames_to_recompute: tuple[int, ...]
    cache_authority: Literal["REBUILDABLE_ONLY"]
    requires_spec_checkpoint_content_verification: bool
    authority_verified: bool = False
    authoritative_checkpoint_artifact_refs: tuple[str, ...] = ()
    authoritative_checkpoint_content_refs: tuple[str, ...] = ()
    authoritative_checkpoint_record_sha256s: tuple[str, ...] = ()
    authoritative_checkpoint_node_producers: tuple[tuple[str, int], ...] = ()
    authoritative_checkpoint_artifact_producers: tuple[tuple[str, int], ...] = ()

    def evidence_payload(self) -> dict[str, object]:
        """Return stable machine-readable evidence for Drive/GitHub reports."""
        return {
            "specification_digest": self.specification_digest,
            "failure_classification": self.failure_classification,
            "failure_reason": self.failure_reason,
            "frame_start": self.frame_start,
            "frame_end": self.frame_end,
            "failed_frame": self.failed_frame,
            "preserved_segments": [list(segment) for segment in self.preserved_segments],
            "latest_verified_frame": self.latest_verified_frame,
            "resume_frame_start": self.resume_frame_start,
            "resume_frame_end": self.resume_frame_end,
            "frames_to_dispatch_count": len(self.frames_to_dispatch),
            "frames_to_dispatch_first": self.frames_to_dispatch[0] if self.frames_to_dispatch else None,
            "frames_to_dispatch_last": self.frames_to_dispatch[-1] if self.frames_to_dispatch else None,
            "frames_to_recompute": list(self.frames_to_recompute),
            "cache_authority": self.cache_authority,
            "requires_spec_checkpoint_content_verification": self.requires_spec_checkpoint_content_verification,
            "authority_verified": self.authority_verified,
            "authoritative_checkpoint_artifact_refs": list(self.authoritative_checkpoint_artifact_refs),
            "authoritative_checkpoint_content_refs": list(self.authoritative_checkpoint_content_refs),
            "authoritative_checkpoint_record_sha256s": list(self.authoritative_checkpoint_record_sha256s),
            "authoritative_checkpoint_node_producers": [list(item) for item in self.authoritative_checkpoint_node_producers],
            "authoritative_checkpoint_artifact_producers": [list(item) for item in self.authoritative_checkpoint_artifact_producers],
        }


def _ordered_segments(
    specification_digest: str,
    frame_start: int,
    failed_frame: int,
    verified_segments: Sequence[VerifiedSimulationSegment],
) -> tuple[VerifiedSimulationSegment, ...]:
    ordered = tuple(sorted(verified_segments, key=lambda item: (item.frame_start, item.frame_end)))
    expected = frame_start
    attempt_fences: dict[str, int] = {}
    for segment in ordered:
        if segment.specification_digest != specification_digest:
            raise SimulationRecoveryContractError("verified segment uses incompatible specification digest")
        known_fence = attempt_fences.setdefault(segment.producer_attempt_id, segment.producer_fence)
        if known_fence != segment.producer_fence:
            raise SimulationRecoveryContractError("verified segment producer attempt/fence is stale or inconsistent")
        if segment.frame_start != expected:
            raise SimulationRecoveryContractError("verified segments must form a continuous verified prefix")
        if segment.frame_end >= failed_frame:
            raise SimulationRecoveryContractError("verified segments cannot include the failed or later frame")
        expected = segment.frame_end + 1
    return ordered


def _dispatch_frames(values: Iterable[int], latest_verified_frame: int | None, frame_end: int) -> tuple[int, ...]:
    frames = tuple(values)
    if not frames:
        raise SimulationRecoveryContractError("dispatchable_frames cannot be empty")
    for frame in frames:
        _frame(frame, "dispatchable_frame")
    if len(set(frames)) != len(frames) or frames != tuple(sorted(frames)):
        raise SimulationRecoveryContractError("dispatchable_frames must be unique and sorted")
    if latest_verified_frame is not None and any(frame <= latest_verified_frame for frame in frames):
        raise SimulationRecoveryContractError("dispatchable_frames must not include already verified frames")
    if frames[-1] != frame_end:
        raise SimulationRecoveryContractError("dispatchable_frames must reach the requested simulation end")
    return frames


def plan_resource_exhaustion_recovery(
    *,
    specification_digest: str,
    frame_start: int,
    frame_end: int,
    failed_frame: int,
    failure_reason: str,
    verified_segments: Sequence[VerifiedSimulationSegment],
    dispatchable_frames: Iterable[int],
) -> SimulationResourceRecoveryPlan:
    """Plan a fail-closed resume after ENOSPC/resource exhaustion.

    The plan preserves durable verified checkpoint segments and dispatches only
    the unverified suffix. It never treats simulation cache as sole authority.
    """
    digest = _sha256(specification_digest, "specification_digest")
    start = _frame(frame_start, "frame_start")
    end = _frame(frame_end, "frame_end")
    failed = _frame(failed_frame, "failed_frame")
    if start < 0 or end < start or not start <= failed <= end:
        raise SimulationRecoveryContractError("simulation frame range is invalid")
    if not isinstance(failure_reason, str) or not failure_reason.strip():
        raise SimulationRecoveryContractError("failure_reason is required")
    reason = " ".join(failure_reason.split())[:4096]
    if not _resource_exhaustion(reason):
        raise SimulationRecoveryContractError("failure_reason must identify resource exhaustion")

    ordered = _ordered_segments(digest, start, failed, verified_segments)
    latest = ordered[-1].frame_end if ordered else None
    resume_start = start if latest is None else latest + 1
    frames = _dispatch_frames(dispatchable_frames, latest, end)
    expected_frames = tuple(range(resume_start, end + 1))
    if frames != expected_frames:
        raise SimulationRecoveryContractError("dispatchable_frames must exactly cover the unverified suffix")

    return SimulationResourceRecoveryPlan(
        specification_digest=digest,
        failure_classification="RESOURCE_EXHAUSTED",
        failure_reason=reason,
        frame_start=start,
        frame_end=end,
        failed_frame=failed,
        preserved_segments=tuple((segment.frame_start, segment.frame_end) for segment in ordered),
        latest_verified_frame=latest,
        resume_frame_start=resume_start,
        resume_frame_end=end,
        frames_to_dispatch=frames,
        frames_to_recompute=(),
        cache_authority="REBUILDABLE_ONLY",
        requires_spec_checkpoint_content_verification=True,
    )


def _exact_artifact_ref(value: str, project_ref: ProjectRef, name: str) -> ArtifactRef:
    matched = _ARTIFACT_REF.fullmatch(value)
    if matched is None:
        raise SimulationRecoveryContractError(f"{name} must be an exact Project ArtifactRef")
    if matched.group(1) != project_ref.value:
        raise SimulationRecoveryContractError(f"{name} crosses Project scope")
    return ArtifactRef(project_ref, matched.group(2), int(matched.group(3)))


def _authoritative_artifact(
    artifacts: ArtifactService,
    access: ProjectAccess,
    artifact_ref: ArtifactRef,
    expected_digest: str,
    name: str,
) -> tuple[Artifact, ContentRef]:
    try:
        artifact = artifacts.get_artifact(access, artifact_ref)
    except ArtifactError as exc:
        raise SimulationRecoveryContractError(f"{name} Artifact authority is missing or corrupt") from exc
    content = artifact.content_ref
    if content is None or content.digest != expected_digest:
        raise SimulationRecoveryContractError(f"{name} Artifact ContentRef is incompatible")
    return artifact, content


def plan_verified_resource_exhaustion_recovery(
    *,
    artifacts: ArtifactService,
    access: ProjectAccess,
    specification: SimulationSpecification,
    verified_checkpoints: Sequence[SimulationCheckpointRef],
    failed_frame: int,
    failure_reason: str,
    dispatchable_frames: Iterable[int],
) -> SimulationResourceRecoveryPlan:
    """Plan ENOSPC recovery from exact persisted VFX checkpoint authority.

    This function verifies existing specification inputs and checkpoint
    Artifacts. It does not execute, emulate, or claim a Blender simulation.
    """
    if not isinstance(artifacts, ArtifactService) or not isinstance(access, ProjectAccess):
        raise SimulationRecoveryContractError("ArtifactService and ProjectAccess are required")
    if not isinstance(specification, SimulationSpecification):
        raise SimulationRecoveryContractError("SimulationSpecification is required")
    if access.project_ref != specification.project_ref:
        raise SimulationRecoveryContractError("SimulationSpecification crosses Project scope")
    try:
        specification.__post_init__()
    except SimulationContractError as exc:
        raise SimulationRecoveryContractError("SimulationSpecification authority is corrupt") from exc

    source_artifacts: list[tuple[Artifact, ContentRef]] = []
    for name, value, digest in (
        ("scene source", specification.scene_ref, specification.scene_sha256),
        ("geometry source", specification.geometry_ref, specification.geometry_sha256),
        ("animation source", specification.animation_ref, specification.animation_sha256),
    ):
        source_ref = _exact_artifact_ref(value, access.project_ref, name)
        source_artifacts.append(_authoritative_artifact(artifacts, access, source_ref, digest, name))

    checkpoints = tuple(verified_checkpoints)
    if not checkpoints:
        raise SimulationRecoveryContractError("verified_checkpoints cannot be empty")
    if not all(isinstance(item, SimulationCheckpointRef) for item in checkpoints):
        raise SimulationRecoveryContractError("verified_checkpoints must contain SimulationCheckpointRef")
    ordered = tuple(sorted(checkpoints, key=lambda item: item.frame))
    if ordered != checkpoints or len({item.frame for item in ordered}) != len(ordered):
        raise SimulationRecoveryContractError("verified_checkpoints must be unique and ordered")

    expected_predecessor = source_artifacts[0]
    expected_predecessor_ref = expected_predecessor[0].artifact_ref
    expected_predecessor_content = expected_predecessor[1]
    segment_start = specification.frame_start
    segments: list[VerifiedSimulationSegment] = []
    checkpoint_artifact_refs: list[str] = []
    checkpoint_content_refs: list[str] = []
    checkpoint_record_sha256s: list[str] = []
    checkpoint_node_producers: list[tuple[str, int]] = []
    checkpoint_artifact_producers: list[tuple[str, int]] = []
    artifact_attempt_fences: dict[str, int] = {}
    for checkpoint in ordered:
        try:
            checkpoint.__post_init__()
        except SimulationContractError as exc:
            raise SimulationRecoveryContractError("SimulationCheckpointRef authority is corrupt") from exc
        if checkpoint.project_ref != access.project_ref or checkpoint.specification != specification:
            raise SimulationRecoveryContractError("SimulationCheckpointRef specification or tool is incompatible")
        if checkpoint.frame < segment_start:
            raise SimulationRecoveryContractError("SimulationCheckpointRef range is incompatible")
        predecessor_ref = _exact_artifact_ref(checkpoint.predecessor_artifact_ref, access.project_ref, "checkpoint predecessor")
        if predecessor_ref != expected_predecessor_ref or checkpoint.predecessor_content_sha256 != expected_predecessor_content.digest:
            raise SimulationRecoveryContractError("SimulationCheckpointRef source chain is incompatible")
        checkpoint_ref = _exact_artifact_ref(checkpoint.artifact_ref, access.project_ref, "checkpoint")
        artifact, content = _authoritative_artifact(artifacts, access, checkpoint_ref, checkpoint.content_sha256, "checkpoint")
        if artifact.role != "vfx.checkpoint":
            raise SimulationRecoveryContractError("checkpoint Artifact role is incompatible")
        if expected_predecessor_ref not in artifact.source_artifact_refs or expected_predecessor_content not in artifact.source_content_refs:
            raise SimulationRecoveryContractError("checkpoint Artifact source provenance is incompatible")
        if artifact.producer_attempt_id is None or artifact.producer_fence is None:
            raise SimulationRecoveryContractError("checkpoint Artifact producer attempt/fence is missing")
        known_artifact_fence = artifact_attempt_fences.setdefault(artifact.producer_attempt_id, artifact.producer_fence)
        if known_artifact_fence != artifact.producer_fence:
            raise SimulationRecoveryContractError("checkpoint Artifact producer attempt/fence is stale or inconsistent")
        segments.append(
            VerifiedSimulationSegment(
                specification.canonical_digest,
                segment_start,
                checkpoint.frame,
                checkpoint.artifact_ref,
                checkpoint.content_sha256,
                checkpoint.producer_attempt_id,
                checkpoint.producer_fence,
            )
        )
        checkpoint_artifact_refs.append(checkpoint.artifact_ref)
        checkpoint_content_refs.append(content.value)
        checkpoint_record_sha256s.append(artifact.record_sha256)
        checkpoint_node_producers.append((checkpoint.producer_attempt_id, checkpoint.producer_fence))
        checkpoint_artifact_producers.append((artifact.producer_attempt_id, artifact.producer_fence))
        expected_predecessor_ref = checkpoint_ref
        expected_predecessor_content = content
        segment_start = checkpoint.frame + 1

    plan = plan_resource_exhaustion_recovery(
        specification_digest=specification.canonical_digest,
        frame_start=specification.frame_start,
        frame_end=specification.frame_end,
        failed_frame=failed_frame,
        failure_reason=failure_reason,
        verified_segments=segments,
        dispatchable_frames=dispatchable_frames,
    )
    return replace(
        plan,
        authority_verified=True,
        authoritative_checkpoint_artifact_refs=tuple(checkpoint_artifact_refs),
        authoritative_checkpoint_content_refs=tuple(checkpoint_content_refs),
        authoritative_checkpoint_record_sha256s=tuple(checkpoint_record_sha256s),
        authoritative_checkpoint_node_producers=tuple(checkpoint_node_producers),
        authoritative_checkpoint_artifact_producers=tuple(checkpoint_artifact_producers),
    )
