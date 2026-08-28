"""Create durable P1-07 state using only the installed wheel."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from biella import (
    FakeResourceObserver,
    ProjectStore,
    Resource,
    ResourceHealth,
    ResourceObservation,
    ResourceQuantity,
    ResourceService,
)


database = Path(os.environ["BIELLA_DATABASE"])
registration = ProjectStore(database).create_project(
    namespace="installed-resource",
    display_name="Installed Resource",
)
resource = Resource.create(
    registration.project.project_ref,
    resource_kind="runtime.host",
    locality_ref="host://installed-writer",
    configured_capacity={
        "memory.bytes": ResourceQuantity.configured(
            128, "bytes", "config://installed/expected"
        )
    },
)
service = ResourceService(database)
service.register_resource(registration.access, resource)
old_observation = ResourceObservation(
    observed_at=datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat(
        timespec="microseconds"
    ),
    fresh_for_seconds=1,
    health=ResourceHealth.HEALTHY,
    physical_capacity={
        "memory.bytes": ResourceQuantity.measured(
            64, "bytes", "test://installed/old-sensor"
        )
    },
    effective_capacity={
        "memory.bytes": ResourceQuantity.derived(
            32, "bytes", "test://installed/old-limit"
        )
    },
    available_capacity={
        "memory.bytes": ResourceQuantity.derived(
            16, "bytes", "test://installed/old-availability"
        )
    },
)
snapshot = service.observe_resource(
    registration.access,
    resource.resource_ref,
    FakeResourceObserver((old_observation,)),
)
print(
    json.dumps(
        {
            "project_id": registration.project.project_ref.value,
            "resource_id": resource.resource_ref.resource_id,
            "snapshot_id": snapshot.snapshot_ref.snapshot_id,
            "token": registration.access.token,
        },
        sort_keys=True,
    )
)
