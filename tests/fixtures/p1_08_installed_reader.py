"""Restart from P1-08 state in a separate installed-wheel process."""

from __future__ import annotations

import os
from pathlib import Path

from biella import ProjectAccess, ProjectRef, ResourceAllocationRef, SchedulerService


database = Path(os.environ["BIELLA_DATABASE"])
project_ref = ProjectRef(os.environ["BIELLA_PROJECT_ID"])
access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
scheduler = SchedulerService(database)
allocation = scheduler.get_allocation(
    access,
    ResourceAllocationRef(project_ref, os.environ["BIELLA_ALLOCATION_ID"]),
)
assert allocation.status == "RESERVED"
assert allocation.reservations[0].snapshot_record_sha256
queue = scheduler.list_queue(access, project_ref)
assert len(queue) == 1
assert queue[0].status == "WAITING"
assert queue[0].request.semantic_digest == os.environ["BIELLA_REQUEST_DIGEST"]
metrics = scheduler.metrics(access, project_ref)
assert metrics.active_allocations == 1
assert metrics.queue_pressure == 1
