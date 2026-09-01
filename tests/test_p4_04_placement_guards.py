from __future__ import annotations

import pytest

from biella.artifact import ArtifactRef, ContentRef
from biella.project import ProjectRef


def test_placement_guard_contract_requires_exact_cache_and_truth_identities() -> None:
    from biella.placement_learning import PlacementLearningError, PlacementLearningService

    project = ProjectRef.new()
    service = PlacementLearningService(project)
    source = ContentRef.from_bytes(b"source", media_type="application/octet-stream")
    first = service.cache_key("implementation://a/v1", source, "context://a/v1", "tool://a/v1")
    assert first != service.cache_key("implementation://b/v1", source, "context://a/v1", "tool://a/v1")
    assert first != service.cache_key("implementation://a/v1", source, "context://b/v1", "tool://a/v1")
    authoritative = ArtifactRef(project, "art_" + "a" * 32, 1)
    with pytest.raises(PlacementLearningError):
        service.plan_eviction((authoritative,))


def test_placement_guard_rejects_foreign_stale_reuse_and_preserves_hard_eligibility() -> None:
    from biella.placement_learning import PlacementLearningError, PlacementLearningService

    project, foreign = ProjectRef.new(), ProjectRef.new()
    service = PlacementLearningService(project)
    with pytest.raises(PlacementLearningError):
        service.validate_reuse(ProjectRef.new(), "cache://foreign", "identity://stale")
    assert service.rank_resources(("resource://cold-idle", "resource://warm-overloaded"), {"resource://cold-idle"}) == ("resource://cold-idle",)
