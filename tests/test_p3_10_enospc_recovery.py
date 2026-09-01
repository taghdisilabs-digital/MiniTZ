from __future__ import annotations

import pytest

from biella.vfx_recovery import (
    SimulationRecoveryContractError,
    VerifiedSimulationSegment,
    plan_resource_exhaustion_recovery,
)

SPEC = "a" * 64


def test_enospc_recovery_for_1_300_preserves_1_200_and_dispatches_only_201_300() -> None:
    plan = plan_resource_exhaustion_recovery(
        specification_digest=SPEC,
        frame_start=1,
        frame_end=300,
        failed_frame=237,
        failure_reason="ENOSPC: no space left on device while writing frame 237 cache",
        verified_segments=(
            VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
            VerifiedSimulationSegment(SPEC, 101, 200, "artifact://p/checkpoint-200/1", "c" * 64, "natt_" + "2" * 32, 1),
        ),
        dispatchable_frames=range(201, 301),
    )

    assert plan.failure_classification == "RESOURCE_EXHAUSTED"
    assert plan.failure_reason == "ENOSPC: no space left on device while writing frame 237 cache"
    assert plan.preserved_segments == ((1, 100), (101, 200))
    assert plan.latest_verified_frame == 200
    assert plan.resume_frame_start == 201
    assert plan.resume_frame_end == 300
    assert plan.frames_to_dispatch == tuple(range(201, 301))
    assert plan.frames_to_recompute == ()
    assert plan.cache_authority == "REBUILDABLE_ONLY"
    assert plan.requires_spec_checkpoint_content_verification


def test_enospc_recovery_fails_closed_on_gaps_in_verified_prefix() -> None:
    with pytest.raises(SimulationRecoveryContractError, match="continuous verified prefix"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="disk full",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
                VerifiedSimulationSegment(SPEC, 150, 200, "artifact://p/checkpoint-200/1", "c" * 64, "natt_" + "2" * 32, 1),
            ),
            dispatchable_frames=range(201, 301),
        )


def test_enospc_recovery_rejects_redispatch_of_verified_frames() -> None:
    with pytest.raises(SimulationRecoveryContractError, match="must not include already verified frames"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="No space left on device",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
                VerifiedSimulationSegment(SPEC, 101, 200, "artifact://p/checkpoint-200/1", "c" * 64, "natt_" + "2" * 32, 1),
            ),
            dispatchable_frames=range(1, 301),
        )


def test_enospc_recovery_rejects_non_resource_failure_reason() -> None:
    with pytest.raises(SimulationRecoveryContractError, match="resource exhaustion"):
        plan_resource_exhaustion_recovery(
            specification_digest=SPEC,
            frame_start=1,
            frame_end=300,
            failed_frame=237,
            failure_reason="operator cancelled",
            verified_segments=(
                VerifiedSimulationSegment(SPEC, 1, 100, "artifact://p/checkpoint-100/1", "b" * 64, "natt_" + "1" * 32, 1),
            ),
            dispatchable_frames=range(101, 301),
        )
