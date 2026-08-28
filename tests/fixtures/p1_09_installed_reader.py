"""Restart from P1-09 state in a separate installed-wheel process."""

from __future__ import annotations

import os
from pathlib import Path

from biella import (
    CapabilityImplementationRef,
    CapabilityImplementationRegistry,
    ProjectAccess,
    ProjectRef,
    RoutingDecisionRef,
    RoutingOutcome,
    RoutingService,
)


database = Path(os.environ["BIELLA_DATABASE"])
project_ref = ProjectRef(os.environ["BIELLA_PROJECT_ID"])
access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
routing = RoutingService(database)
decision = routing.get_decision(
    access,
    RoutingDecisionRef(project_ref, os.environ["BIELLA_DECISION_ID"]),
)
implementation = CapabilityImplementationRegistry(database).get(
    access,
    CapabilityImplementationRef(project_ref, os.environ["BIELLA_IMPLEMENTATION_ID"]),
)
assert decision.outcome is RoutingOutcome.ROUTED
assert decision.record_sha256 == os.environ["BIELLA_DECISION_SHA256"]
assert decision.task_digest == os.environ["BIELLA_TASK_DIGEST"]
assert decision.selected_implementation_ref == implementation.implementation_ref
assert decision.selected_resource_ref is not None
assert decision.selected_snapshot_ref is not None
