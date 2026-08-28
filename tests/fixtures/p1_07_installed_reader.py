"""Restart from P1-07 state using a separate installed-wheel process."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

from biella import (
    FakeResourceObserver,
    ProjectAccess,
    ProjectRef,
    ResourceHealth,
    ResourceObservation,
    ResourceQuantity,
    ResourceRef,
    ResourceService,
    ResourceSnapshotRef,
    ResourceStaleError,
)


database = Path(os.environ["BIELLA_DATABASE"])
project_ref = ProjectRef(os.environ["BIELLA_PROJECT_ID"])
access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
resource_ref = ResourceRef(project_ref, os.environ["BIELLA_RESOURCE_ID"])
snapshot_ref = ResourceSnapshotRef(resource_ref, os.environ["BIELLA_SNAPSHOT_ID"])
service = ResourceService(database)
resource = service.get_resource(access, resource_ref)
assert resource.configured_capacity["memory.bytes"].value == 128
old_snapshot = service.get_snapshot(access, snapshot_ref)
assert old_snapshot.sequence == 1
try:
    service.latest_snapshot(access, resource_ref)
except ResourceStaleError:
    pass
else:
    raise AssertionError("Restart accepted a stale observation as current")
fresh_observation = ResourceObservation(
    observed_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
    fresh_for_seconds=30,
    health=ResourceHealth.HEALTHY,
    physical_capacity={
        "memory.bytes": ResourceQuantity.measured(
            64, "bytes", "test://installed/new-sensor"
        )
    },
    effective_capacity={
        "memory.bytes": ResourceQuantity.derived(
            32, "bytes", "test://installed/new-limit"
        )
    },
    available_capacity={
        "memory.bytes": ResourceQuantity.derived(
            24, "bytes", "test://installed/new-availability"
        )
    },
)
fresh = service.observe_resource(
    access,
    resource_ref,
    FakeResourceObserver((fresh_observation,)),
)
assert fresh.sequence == 2
assert fresh.previous_record_sha256 == old_snapshot.record_sha256
assert service.latest_snapshot(access, resource_ref) == fresh
