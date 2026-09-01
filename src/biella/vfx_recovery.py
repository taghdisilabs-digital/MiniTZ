"""Task-scoped VFX simulation recovery planning.

This module records the deterministic recovery decision used by the P3-10
simulation adapter path when storage/resource pressure interrupts a long bake.
It is deliberately provider-neutral data and does not introduce a second
scheduler, object store, cache, or validation framework.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import re
from typing import Literal

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
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
        }


def _ordered_segments(
    specification_digest: str,
    frame_start: int,
    failed_frame: int,
    verified_segments: Sequence[VerifiedSimulationSegment],
) -> tuple[VerifiedSimulationSegment, ...]:
    ordered = tuple(sorted(verified_segments, key=lambda item: (item.frame_start, item.frame_end)))
    expected = frame_start
    for segment in ordered:
        if segment.specification_digest != specification_digest:
            raise SimulationRecoveryContractError("verified segment uses incompatible specification digest")
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
