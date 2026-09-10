"""Durable, fenced, resource-aware concurrent Graph scheduling for P1-08."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .execution import NodeExecutionAttempt, NodeExecutionService
from .graph import Graph, GraphRef, Node, NodeRef
from .project import ProjectAccess, ProjectRef, ProjectStore
from .resource import (
    QuantitySource,
    ResourceDeviceSnapshot,
    ResourceFit,
    ResourceFitRequest,
    ResourceHealth,
    ResourceArtifactLocality,
    ResourceIntegrityError as ResourceInventoryIntegrityError,
    ResourceRef,
    ResourceService,
    ResourceSnapshot,
    ResourceSnapshotRef,
    ResourceWorkspaceLocality,
    evaluateResourceFit,
)
from .run import ExecutionAttempt, RunRef, RunService


_ALLOCATION_ID = re.compile(r"ral_[0-9a-f]{32}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")
_ACTIVE = {"RESERVED", "DISPATCHING", "DISPATCHED"}
_STATUSES = _ACTIVE | {"RELEASED", "EXPIRED", "CANCELLED", "FAILED"}
_OUTCOMES = {"COMPLETED", "CANCELLED", "EXECUTOR_LOST", "DISPATCH_FAILED", "TERMINAL"}


class SchedulerError(Exception):
    """Base scheduler failure."""


class SchedulerContractError(SchedulerError, ValueError):
    """A scheduling request or durable record is malformed."""


class SchedulerScopeError(SchedulerError):
    """A scheduler operation crossed Project scope."""


class SchedulerConflictError(SchedulerError):
    """Current resource, side-effect, or fenced authority conflicts."""


class SchedulerAuthorityError(SchedulerError):
    """Current Run, Node, or allocation authority is absent."""


class SchedulerNotFoundError(SchedulerError):
    """An exact ResourceAllocation was not found."""


class SchedulerIntegrityError(SchedulerError):
    """Persisted scheduler evidence failed verification."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _sha(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise SchedulerContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SchedulerContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchedulerContractError(f"{name} must be timezone-aware")
    return value


def _capacity(value: Mapping[str, float], name: str) -> Mapping[str, float]:
    if not isinstance(value, Mapping) or len(value) > 128:
        raise SchedulerContractError(f"{name} is malformed or unbounded")
    result: dict[str, float] = {}
    for key, amount in value.items():
        if not isinstance(key, str) or re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", key) is None:
            raise SchedulerContractError(f"{name} metric is malformed")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or amount < 0:
            raise SchedulerContractError(f"{name} amount is invalid")
        result[key] = float(amount)
    return MappingProxyType(dict(sorted(result.items())))


def _texts(value: Sequence[str], name: str, *, refs: bool = False) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SchedulerContractError(f"{name} must be a sequence")
    result = tuple(value)
    if len(result) > 128 or len(result) != len(set(result)):
        raise SchedulerContractError(f"{name} is duplicated or unbounded")
    for item in result:
        if not isinstance(item, str) or not item or len(item.encode()) > 1024:
            raise SchedulerContractError(f"{name} contains malformed text")
        if refs and re.fullmatch(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]+", item) is None:
            raise SchedulerContractError(f"{name} requires absolute targets")
    return tuple(sorted(result))


@dataclass(frozen=True, order=True)
class ResourceAllocationRef:
    project_ref: ProjectRef
    allocation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.allocation_id, str) or _ALLOCATION_ID.fullmatch(self.allocation_id) is None:
            raise SchedulerContractError("ResourceAllocation identity is malformed")

    @property
    def value(self) -> str:
        return f"resource-allocation://{self.project_ref.value}/{self.allocation_id}"


@dataclass(frozen=True)
class ResourceClaim:
    resource_ref: ResourceRef
    fit_request: ResourceFitRequest = field(default_factory=ResourceFitRequest)
    requested_capacity: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.resource_ref, ResourceRef) or not isinstance(self.fit_request, ResourceFitRequest):
            raise SchedulerContractError("ResourceClaim requires exact Resource and fit contracts")
        object.__setattr__(self, "requested_capacity", _capacity(self.requested_capacity, "requested_capacity"))
        for metric, amount in self.requested_capacity.items():
            fit_amount = self.fit_request.required_available.get(metric)
            if fit_amount is None or fit_amount < amount:
                raise SchedulerContractError("Reserved capacity must be included in required_available")

    def payload(self) -> dict[str, object]:
        request = self.fit_request
        return {
            "resource_ref": self.resource_ref.value,
            "requested_capacity": dict(self.requested_capacity),
            "fit": {
                "required_effective": dict(request.required_effective),
                "required_available": dict(request.required_available),
                "reduced_available": dict(request.reduced_available),
                "maximum_pressure": dict(request.maximum_pressure),
                "required_device_kind": request.required_device_kind,
                "required_device_features": list(request.required_device_features),
                "required_device_available": dict(request.required_device_available),
                "reduced_device_available": dict(request.reduced_device_available),
                "required_loaded_model_refs": list(request.required_loaded_model_refs),
                "required_installed_tool_refs": list(request.required_installed_tool_refs),
                "required_artifact_refs": [item.to_payload() for item in request.required_artifact_refs],
                "required_workspace_refs": [item.to_payload() for item in request.required_workspace_refs],
                "maximum_cost": request.maximum_cost,
            },
        }

    @classmethod
    def from_payload(cls, project_ref: ProjectRef, payload: object) -> "ResourceClaim":
        if not isinstance(payload, dict):
            raise SchedulerIntegrityError("Queued ResourceClaim is malformed")
        try:
            resource_value = cast(str, payload["resource_ref"])
            prefix = f"resource://{project_ref.value}/"
            if not resource_value.startswith(prefix):
                raise SchedulerScopeError("Queued ResourceClaim crossed Project scope")
            fit = cast(dict[str, object], payload["fit"])
            request = ResourceFitRequest(
                required_effective=cast(dict[str, float], fit["required_effective"]),
                required_available=cast(dict[str, float], fit["required_available"]),
                reduced_available=cast(dict[str, float], fit["reduced_available"]),
                maximum_pressure=cast(dict[str, float], fit["maximum_pressure"]),
                required_device_kind=cast(str | None, fit["required_device_kind"]),
                required_device_features=tuple(cast(list[str], fit["required_device_features"])),
                required_device_available=cast(dict[str, float], fit["required_device_available"]),
                reduced_device_available=cast(dict[str, float], fit["reduced_device_available"]),
                required_loaded_model_refs=tuple(cast(list[str], fit["required_loaded_model_refs"])),
                required_installed_tool_refs=tuple(cast(list[str], fit["required_installed_tool_refs"])),
                required_artifact_refs=tuple(
                    ResourceArtifactLocality.from_payload(item)
                    for item in cast(list[object], fit["required_artifact_refs"])
                ),
                required_workspace_refs=tuple(
                    ResourceWorkspaceLocality.from_payload(item)
                    for item in cast(list[object], fit["required_workspace_refs"])
                ),
                maximum_cost=cast(float | None, fit["maximum_cost"]),
            )
            return cls(
                ResourceRef(project_ref, resource_value.removeprefix(prefix)),
                request,
                cast(dict[str, float], payload["requested_capacity"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchedulerIntegrityError("Queued ResourceClaim is malformed") from exc


@dataclass(frozen=True)
class SchedulingRequest:
    node_ref: NodeRef
    claims: tuple[ResourceClaim, ...]
    priority: int = 0
    deadline: str | None = None
    queued_at: str = field(default_factory=_now)
    side_effect_targets: tuple[str, ...] = ()
    allow_reduced_fit: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.node_ref, NodeRef):
            raise TypeError("node_ref must be NodeRef")
        if not isinstance(self.claims, tuple) or not self.claims or len(self.claims) > 32:
            raise SchedulerContractError("SchedulingRequest requires bounded Resource claims")
        if not all(isinstance(item, ResourceClaim) for item in self.claims):
            raise SchedulerContractError("claims must contain ResourceClaim")
        refs = tuple(item.resource_ref for item in self.claims)
        if len(refs) != len(set(refs)) or any(item.project_ref != self.node_ref.project_ref for item in refs):
            raise SchedulerScopeError("SchedulingRequest Resource scope is invalid")
        object.__setattr__(self, "claims", tuple(sorted(self.claims, key=lambda item: item.resource_ref.value)))
        if isinstance(self.priority, bool) or not isinstance(self.priority, int) or not -1000 <= self.priority <= 1000:
            raise SchedulerContractError("priority is outside the bounded range")
        if self.deadline is not None:
            _timestamp(self.deadline, "deadline")
        _timestamp(self.queued_at, "queued_at")
        object.__setattr__(self, "side_effect_targets", _texts(self.side_effect_targets, "side_effect_targets", refs=True))
        if not isinstance(self.allow_reduced_fit, bool):
            raise SchedulerContractError("allow_reduced_fit must be boolean")

    @property
    def semantic_digest(self) -> str:
        return _sha(self.payload())

    def payload(self) -> dict[str, object]:
        return {
            "allow_reduced_fit": self.allow_reduced_fit,
            "claims": [item.payload() for item in self.claims],
            "deadline": self.deadline,
            "node_ref": self.node_ref.value,
            "priority": self.priority,
            "queued_at": self.queued_at,
            "side_effect_targets": list(self.side_effect_targets),
        }

    @classmethod
    def from_payload(cls, project_ref: ProjectRef, payload: object) -> "SchedulingRequest":
        if not isinstance(payload, dict):
            raise SchedulerIntegrityError("Queued SchedulingRequest is malformed")
        try:
            node_value = cast(str, payload["node_ref"])
            match = re.fullmatch(
                rf"node://({re.escape(project_ref.value)})/(gph_[0-9a-f]{{32}})/([1-9][0-9]*)/(nod_[0-9a-f]{{32}})",
                node_value,
            )
            if match is None:
                raise SchedulerScopeError("Queued NodeRef crossed Project scope")
            return cls(
                NodeRef(GraphRef(project_ref, match.group(2), int(match.group(3))), match.group(4)),
                tuple(ResourceClaim.from_payload(project_ref, item) for item in cast(list[object], payload["claims"])),
                priority=cast(int, payload["priority"]),
                deadline=cast(str | None, payload["deadline"]),
                queued_at=cast(str, payload["queued_at"]),
                side_effect_targets=tuple(cast(list[str], payload["side_effect_targets"])),
                allow_reduced_fit=cast(bool, payload["allow_reduced_fit"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchedulerIntegrityError("Queued SchedulingRequest is malformed") from exc


@dataclass(frozen=True)
class ResourceReservation:
    resource_ref: ResourceRef
    snapshot_ref: ResourceSnapshotRef
    snapshot_record_sha256: str
    requested_capacity: Mapping[str, float]
    effective_capacity: Mapping[str, float]
    device_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.snapshot_ref.resource_ref != self.resource_ref:
            raise SchedulerScopeError("Reservation snapshot and Resource differ")
        if re.fullmatch(r"[0-9a-f]{64}", self.snapshot_record_sha256) is None:
            raise SchedulerContractError("Reservation snapshot digest is malformed")
        object.__setattr__(self, "requested_capacity", _capacity(self.requested_capacity, "requested_capacity"))
        object.__setattr__(self, "effective_capacity", _capacity(self.effective_capacity, "effective_capacity"))
        object.__setattr__(self, "device_ids", _texts(self.device_ids, "device_ids"))

    def payload(self) -> dict[str, object]:
        return {
            "device_ids": list(self.device_ids),
            "effective_capacity": dict(self.effective_capacity),
            "requested_capacity": dict(self.requested_capacity),
            "resource_ref": self.resource_ref.value,
            "snapshot_record_sha256": self.snapshot_record_sha256,
            "snapshot_ref": self.snapshot_ref.value,
        }


@dataclass(frozen=True)
class ResourceAllocation:
    allocation_ref: ResourceAllocationRef
    node_ref: NodeRef
    run_ref: RunRef
    run_attempt_id: str
    run_attempt_fence: int
    request_digest: str
    reservations: tuple[ResourceReservation, ...]
    side_effect_targets: tuple[str, ...]
    allocation_generation: int
    fence: int
    owner_ref: str
    lease_expires_at: str | None
    status: str
    state_version: int
    dispatch_idempotency_key: str | None
    node_attempt_id: str | None
    node_attempt_fence: int | None
    terminal_outcome: str | None
    created_at: str
    updated_at: str
    identity_sha256: str = field(init=False)
    state_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.allocation_ref.project_ref != self.node_ref.project_ref or self.run_ref.project_ref != self.node_ref.project_ref:
            raise SchedulerScopeError("ResourceAllocation Project scope mismatch")
        if re.fullmatch(r"att_[0-9a-f]{32}", self.run_attempt_id) is None or self.run_attempt_fence < 1:
            raise SchedulerContractError("ResourceAllocation Run attempt authority is malformed")
        if not isinstance(self.reservations, tuple) or not self.reservations or any(item.resource_ref.project_ref != self.node_ref.project_ref for item in self.reservations):
            raise SchedulerContractError("ResourceAllocation reservations are invalid")
        if self.status not in _STATUSES or self.allocation_generation < 1 or self.fence < 1 or self.state_version < 1:
            raise SchedulerContractError("ResourceAllocation state is malformed")
        if re.fullmatch(r"[0-9a-f]{64}", self.request_digest) is None:
            raise SchedulerContractError("ResourceAllocation request digest is malformed")
        _texts(self.side_effect_targets, "side_effect_targets", refs=True)
        if not isinstance(self.owner_ref, str) or len(self.owner_ref.encode()) > 1024 or re.fullmatch(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]+", self.owner_ref) is None:
            raise SchedulerContractError("ResourceAllocation owner is malformed")
        if self.status in _ACTIVE:
            if self.lease_expires_at is None or self.terminal_outcome is not None:
                raise SchedulerContractError("Active allocation requires a lease and no outcome")
            _timestamp(self.lease_expires_at, "lease_expires_at")
        elif self.lease_expires_at is not None or self.terminal_outcome is None:
            raise SchedulerContractError("Terminal allocation requires outcome and no lease")
        if self.status == "RESERVED" and self.dispatch_idempotency_key is not None:
            raise SchedulerContractError("Reserved allocation cannot claim dispatch")
        if self.status in {"DISPATCHING", "DISPATCHED"} and (
            self.dispatch_idempotency_key is None
            or _KEY.fullmatch(self.dispatch_idempotency_key) is None
        ):
            raise SchedulerContractError("Dispatching allocation requires exact idempotency identity")
        if self.dispatch_idempotency_key is not None and _KEY.fullmatch(self.dispatch_idempotency_key) is None:
            raise SchedulerContractError("Dispatch idempotency identity is malformed")
        if (self.node_attempt_id is None) != (self.node_attempt_fence is None):
            raise SchedulerContractError("Node attempt binding is incomplete")
        if self.node_attempt_id is not None and (re.fullmatch(r"natt_[0-9a-f]{32}", self.node_attempt_id) is None or cast(int, self.node_attempt_fence) < 1):
            raise SchedulerContractError("Node attempt binding is malformed")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        identity = _sha({"allocation_ref": self.allocation_ref.value, "created_at": self.created_at, "node_ref": self.node_ref.value, "request_digest": self.request_digest, "run_attempt_fence": self.run_attempt_fence, "run_attempt_id": self.run_attempt_id, "run_id": self.run_ref.run_id})
        state = _sha(self._state_payload())
        object.__setattr__(self, "identity_sha256", identity)
        object.__setattr__(self, "state_sha256", state)

    @property
    def project_ref(self) -> ProjectRef:
        return self.allocation_ref.project_ref

    def _state_payload(self) -> dict[str, object]:
        return {
            "allocation_generation": self.allocation_generation,
            "allocation_ref": self.allocation_ref.value,
            "dispatch_idempotency_key": self.dispatch_idempotency_key,
            "fence": self.fence,
            "lease_expires_at": self.lease_expires_at,
            "node_attempt_fence": self.node_attempt_fence,
            "node_attempt_id": self.node_attempt_id,
            "owner_ref": self.owner_ref,
            "reservations": [item.payload() for item in self.reservations],
            "side_effect_targets": list(self.side_effect_targets),
            "state_version": self.state_version,
            "status": self.status,
            "terminal_outcome": self.terminal_outcome,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ScheduledDispatch:
    allocation: ResourceAllocation
    node_attempt: NodeExecutionAttempt


@dataclass(frozen=True)
class ScheduleCycleResult:
    dispatched: tuple[ScheduledDispatch, ...]
    deferred: tuple[NodeRef, ...]
    failures: Mapping[NodeRef, str]


@dataclass(frozen=True)
class SchedulerMetrics:
    active_allocations: int
    queue_pressure: int
    max_observed_productive_concurrency: int
    independent_nodes_serialized_without_reason: int = 0
    exclusive_resource_double_allocations: int = 0
    invalid_resource_overcommit: int = 0
    resource_leaks_after_terminal: int = 0
    permanent_starvation_under_ordinary_load: int = 0
    global_heavyweight_lock: int = 0


@dataclass(frozen=True)
class SchedulerQueueEntry:
    request: SchedulingRequest
    status: str
    exact_cause: str | None
    sequence: int
    updated_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.status not in {"WAITING", "DISPATCHED", "FAILED"} or self.sequence < 1:
            raise SchedulerContractError("Scheduler queue state is malformed")
        if self.status == "WAITING" and not self.exact_cause:
            raise SchedulerContractError("Waiting queue state requires an exact cause")
        if self.exact_cause is not None and (not self.exact_cause or len(self.exact_cause.encode()) > 4096):
            raise SchedulerContractError("Queue cause is malformed or unbounded")
        _timestamp(self.updated_at, "updated_at")
        object.__setattr__(self, "record_sha256", _sha({
            "exact_cause": self.exact_cause,
            "request": self.request.payload(),
            "sequence": self.sequence,
            "status": self.status,
            "updated_at": self.updated_at,
        }))


@dataclass(frozen=True)
class SchedulerFamilyAttachment:
    """A read-only semantic attachment for a scheduler implementation.

    Scheduling can plan and dispatch work, but it must never become a second
    authority for MiniTZ task order or status.  The attachment is explicit so
    callers can prove that relationship at construction time.
    """

    family_id: str
    progression_authority: str
    progression_mutation: bool = False
    mechanism: str = "GENERIC_SCHEDULER_PLAN_ONLY"

    def __post_init__(self) -> None:
        if self.family_id != "MINITZ_PROGRESSION_FAMILY":
            raise SchedulerContractError("unknown scheduler semantic family")
        if self.progression_authority != "MINITZ_TASK_PROGRAM_ONLY":
            raise SchedulerContractError("scheduler progression authority must be MiniTZ Task Program")
        if self.progression_mutation:
            raise SchedulerContractError("generic scheduler cannot mutate MiniTZ progression")
        if self.mechanism != "GENERIC_SCHEDULER_PLAN_ONLY":
            raise SchedulerContractError("scheduler family mechanism must remain plan-only")

    @classmethod
    def minitz(cls) -> "SchedulerFamilyAttachment":
        return cls(
            family_id="MINITZ_PROGRESSION_FAMILY",
            progression_authority="MINITZ_TASK_PROGRAM_ONLY",
        )


DispatchCallback = Callable[[ScheduledDispatch], None]


class Scheduler:
    """Atomic multi-Resource reservations plus concurrent Node dispatch."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        aging_seconds: float = 30.0,
        family_attachment: SchedulerFamilyAttachment | None = None,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        if not math.isfinite(aging_seconds) or aging_seconds <= 0:
            raise SchedulerContractError("aging_seconds must be positive and finite")
        if family_attachment is not None and not isinstance(family_attachment, SchedulerFamilyAttachment):
            raise SchedulerContractError("family_attachment must be a SchedulerFamilyAttachment")
        self.aging_seconds = float(aging_seconds)
        self._family_attachment = family_attachment
        self.projects = ProjectStore(self.database_path)
        self.resources = ResourceService(self.database_path)
        self.runs = RunService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.graphs = self.executions.graphs
        self._initialize_schema()

    @property
    def family_attachment(self) -> SchedulerFamilyAttachment | None:
        """Return the explicit semantic family attachment, if configured."""
        return self._family_attachment

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS resource_allocations (
                    project_id TEXT NOT NULL, allocation_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, run_attempt_id TEXT NOT NULL, run_attempt_fence INTEGER NOT NULL,
                    graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL, request_digest TEXT NOT NULL, created_at TEXT NOT NULL,
                    identity_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, allocation_id),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                      REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id, run_attempt_id, run_attempt_fence)
                      REFERENCES execution_attempts(project_id, run_id, attempt_id, fence)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS resource_allocation_states (
                    project_id TEXT NOT NULL, allocation_id TEXT NOT NULL, state_version INTEGER NOT NULL,
                    allocation_generation INTEGER NOT NULL, fence INTEGER NOT NULL, status TEXT NOT NULL,
                    owner_ref TEXT NOT NULL, lease_expires_at TEXT,
                    dispatch_idempotency_key TEXT, node_attempt_id TEXT,
                    node_attempt_fence INTEGER, terminal_outcome TEXT, updated_at TEXT NOT NULL,
                    state_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, allocation_id, state_version),
                    FOREIGN KEY (project_id, allocation_id) REFERENCES resource_allocations(project_id, allocation_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS resource_allocation_heads (
                    project_id TEXT NOT NULL, allocation_id TEXT NOT NULL, state_version INTEGER NOT NULL,
                    state_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL, head_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, allocation_id),
                    FOREIGN KEY (project_id, allocation_id, state_version)
                      REFERENCES resource_allocation_states(project_id, allocation_id, state_version)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS resource_allocation_reservations (
                    project_id TEXT NOT NULL, allocation_id TEXT NOT NULL, resource_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL, snapshot_record_sha256 TEXT NOT NULL,
                    requested_capacity_json TEXT NOT NULL, effective_capacity_json TEXT NOT NULL,
                    device_ids_json TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, allocation_id, resource_id),
                    FOREIGN KEY (project_id, allocation_id) REFERENCES resource_allocations(project_id, allocation_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, resource_id, snapshot_id, snapshot_record_sha256)
                      REFERENCES resource_snapshots(project_id, resource_id, snapshot_id, record_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS resource_allocation_side_effects (
                    project_id TEXT NOT NULL, allocation_id TEXT NOT NULL, target_ref TEXT NOT NULL,
                    PRIMARY KEY (project_id, allocation_id, target_ref),
                    FOREIGN KEY (project_id, allocation_id) REFERENCES resource_allocations(project_id, allocation_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS scheduler_idempotency (
                    project_id TEXT NOT NULL, operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL, allocation_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, operation, idempotency_key),
                    FOREIGN KEY (project_id, allocation_id) REFERENCES resource_allocations(project_id, allocation_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS scheduler_cycle_metrics (
                    cycle_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, cycle_sequence INTEGER NOT NULL,
                    previous_record_sha256 TEXT, started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL, queue_pressure INTEGER NOT NULL,
                    max_productive_concurrency INTEGER NOT NULL, record_sha256 TEXT NOT NULL,
                    UNIQUE (project_id, cycle_sequence),
                    UNIQUE (project_id, cycle_sequence, record_sha256)
                );
                CREATE TABLE IF NOT EXISTS scheduler_cycle_metric_heads (
                    project_id TEXT PRIMARY KEY, cycle_sequence INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    FOREIGN KEY (project_id, cycle_sequence, record_sha256)
                      REFERENCES scheduler_cycle_metrics(project_id, cycle_sequence, record_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS scheduler_queue_events (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL, sequence INTEGER NOT NULL, request_json TEXT NOT NULL,
                    request_digest TEXT NOT NULL, status TEXT NOT NULL, exact_cause TEXT,
                    updated_at TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id, sequence),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                      REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS scheduler_queue_heads (
                    project_id TEXT NOT NULL, graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL, sequence INTEGER NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, graph_id, graph_revision, node_id),
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id, sequence)
                      REFERENCES scheduler_queue_events(project_id, graph_id, graph_revision, node_id, sequence)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS resource_allocations_no_update BEFORE UPDATE ON resource_allocations
                  BEGIN SELECT RAISE(ABORT, 'ResourceAllocation identity is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocations_no_delete BEFORE DELETE ON resource_allocations
                  BEGIN SELECT RAISE(ABORT, 'ResourceAllocation identity cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_states_no_update BEFORE UPDATE ON resource_allocation_states
                  BEGIN SELECT RAISE(ABORT, 'ResourceAllocation state evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_states_no_delete BEFORE DELETE ON resource_allocation_states
                  BEGIN SELECT RAISE(ABORT, 'ResourceAllocation state evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_heads_no_delete BEFORE DELETE ON resource_allocation_heads
                  BEGIN SELECT RAISE(ABORT, 'ResourceAllocation head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_reservations_no_update BEFORE UPDATE ON resource_allocation_reservations
                  BEGIN SELECT RAISE(ABORT, 'Resource reservation evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_reservations_no_delete BEFORE DELETE ON resource_allocation_reservations
                  BEGIN SELECT RAISE(ABORT, 'Resource reservation evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_side_effects_no_update BEFORE UPDATE ON resource_allocation_side_effects
                  BEGIN SELECT RAISE(ABORT, 'Side-effect reservation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS resource_allocation_side_effects_no_delete BEFORE DELETE ON resource_allocation_side_effects
                  BEGIN SELECT RAISE(ABORT, 'Side-effect reservation cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_idempotency_no_update BEFORE UPDATE ON scheduler_idempotency
                  BEGIN SELECT RAISE(ABORT, 'Scheduler idempotency is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_idempotency_no_delete BEFORE DELETE ON scheduler_idempotency
                  BEGIN SELECT RAISE(ABORT, 'Scheduler idempotency cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_cycle_metrics_no_update BEFORE UPDATE ON scheduler_cycle_metrics
                  BEGIN SELECT RAISE(ABORT, 'Scheduler cycle metric evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_cycle_metrics_no_delete BEFORE DELETE ON scheduler_cycle_metrics
                  BEGIN SELECT RAISE(ABORT, 'Scheduler cycle metric evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_cycle_metric_heads_no_delete BEFORE DELETE ON scheduler_cycle_metric_heads
                  BEGIN SELECT RAISE(ABORT, 'Scheduler cycle metric head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_cycle_metric_heads_monotonic BEFORE UPDATE ON scheduler_cycle_metric_heads
                  WHEN NEW.project_id != OLD.project_id OR NEW.cycle_sequence != OLD.cycle_sequence + 1
                  BEGIN SELECT RAISE(ABORT, 'Scheduler cycle metric head must advance monotonically'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_queue_events_no_update BEFORE UPDATE ON scheduler_queue_events
                  BEGIN SELECT RAISE(ABORT, 'Scheduler queue evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_queue_events_no_delete BEFORE DELETE ON scheduler_queue_events
                  BEGIN SELECT RAISE(ABORT, 'Scheduler queue evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS scheduler_queue_heads_no_delete BEFORE DELETE ON scheduler_queue_heads
                  BEGIN SELECT RAISE(ABORT, 'Scheduler queue head cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _db_now(connection: sqlite3.Connection) -> str:
        return cast(str, connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')").fetchone()[0])

    @staticmethod
    def _lease(now: str, seconds: int | float) -> str:
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(float(seconds)) or not 0.01 <= seconds <= 86400:
            raise SchedulerContractError("lease_seconds must be between 0.01 and 86400")
        return (datetime.fromisoformat(now) + timedelta(seconds=float(seconds))).isoformat(timespec="microseconds")

    @staticmethod
    def _head_sha(allocation: ResourceAllocation) -> str:
        return _sha({"allocation_ref": allocation.allocation_ref.value, "state_sha256": allocation.state_sha256, "state_version": allocation.state_version, "updated_at": allocation.updated_at})

    @staticmethod
    def _cycle_metric_sha(
        cycle_id: str,
        project_ref: ProjectRef,
        cycle_sequence: int,
        previous_record_sha256: str | None,
        started_at: str,
        finished_at: str,
        queue_pressure: int,
        max_productive_concurrency: int,
    ) -> str:
        return _sha(
            {
                "cycle_id": cycle_id,
                "cycle_sequence": cycle_sequence,
                "finished_at": finished_at,
                "max_productive_concurrency": max_productive_concurrency,
                "previous_record_sha256": previous_record_sha256,
                "project_ref": project_ref.value,
                "queue_pressure": queue_pressure,
                "started_at": started_at,
            }
        )

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except Exception as exc:
            raise SchedulerScopeError("Scheduler Project scope mismatch") from exc

    def _node(self, graph: Graph, ref: NodeRef) -> Node:
        for node in graph.nodes:
            if node.node_ref == ref:
                return node
        raise SchedulerAuthorityError("Node is not in the active Graph")

    def _current_snapshot(self, connection: sqlite3.Connection, claim: ResourceClaim, now: str, *, allow_reduced_fit: bool) -> ResourceSnapshot:
        row = connection.execute(
            """SELECT snapshots.*,
                      heads.snapshot_id AS head_snapshot_id,
                      heads.sequence AS head_sequence,
                      heads.record_sha256 AS head_record_sha256,
                      heads.updated_at AS head_updated_at,
                      heads.head_sha256 AS head_sha256,
                      (SELECT MAX(history.sequence) FROM resource_snapshots history
                        WHERE history.project_id=heads.project_id
                          AND history.resource_id=heads.resource_id) AS maximum_sequence
               FROM resource_snapshot_heads heads
               JOIN resource_snapshots snapshots ON snapshots.project_id=heads.project_id
                AND snapshots.resource_id=heads.resource_id AND snapshots.snapshot_id=heads.snapshot_id
                AND snapshots.record_sha256=heads.record_sha256
               WHERE heads.project_id=? AND heads.resource_id=?""",
            (claim.resource_ref.project_ref.value, claim.resource_ref.resource_id),
        ).fetchone()
        if row is None:
            exists = connection.execute(
                "SELECT 1 FROM resource_snapshots WHERE project_id=? AND resource_id=? LIMIT 1",
                (claim.resource_ref.project_ref.value, claim.resource_ref.resource_id),
            ).fetchone()
            if exists is not None:
                raise SchedulerIntegrityError("ResourceSnapshot head is missing or inconsistent")
            raise SchedulerConflictError("Resource has no current observation")
        try:
            snapshot = self.resources._snapshot_from_head_row(row)
            self.resources._verify_snapshot_chain(connection, snapshot)
        except ResourceInventoryIntegrityError as exc:
            raise SchedulerIntegrityError("Current ResourceSnapshot evidence is inconsistent") from exc
        result = evaluateResourceFit(snapshot, claim.fit_request, at=now)
        if result.classification is ResourceFit.FIT or (
            allow_reduced_fit and result.classification is ResourceFit.FIT_REDUCED
        ):
            return snapshot
        raise SchedulerConflictError(f"Resource is not schedulable now: {result.classification.value}:{','.join(result.causes)}")

    @staticmethod
    def _known_available(snapshot: ResourceSnapshot, metric: str) -> float:
        quantity = snapshot.available_capacity.get(metric)
        if quantity is None or quantity.source_kind is QuantitySource.UNKNOWN or quantity.value is None:
            raise SchedulerConflictError(f"Resource availability is unknown: {metric}")
        return float(quantity.value)

    def _all_allocations(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
    ) -> tuple[ResourceAllocation, ...]:
        identity_ids = {
            cast(str, row[0])
            for row in connection.execute(
                "SELECT allocation_id FROM resource_allocations WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
        }
        head_ids = {
            cast(str, row[0])
            for row in connection.execute(
                "SELECT allocation_id FROM resource_allocation_heads WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
        }
        state_ids = {
            cast(str, row[0])
            for row in connection.execute(
                "SELECT DISTINCT allocation_id FROM resource_allocation_states WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
        }
        reservation_ids = {
            cast(str, row[0])
            for row in connection.execute(
                "SELECT DISTINCT allocation_id FROM resource_allocation_reservations WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
        }
        side_effect_ids = {
            cast(str, row[0])
            for row in connection.execute(
                "SELECT DISTINCT allocation_id FROM resource_allocation_side_effects WHERE project_id=?",
                (project_ref.value,),
            ).fetchall()
        }
        if (
            identity_ids != head_ids
            or identity_ids != state_ids
            or reservation_ids != identity_ids
            or not side_effect_ids.issubset(identity_ids)
        ):
            raise SchedulerIntegrityError("ResourceAllocation identity and evidence sets differ")
        refs = tuple(
            ResourceAllocationRef(project_ref, allocation_id)
            for allocation_id in sorted(identity_ids)
        )
        return tuple(self._fetch(connection, ref) for ref in refs)

    def _active_allocations(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
    ) -> tuple[ResourceAllocation, ...]:
        return tuple(
            allocation
            for allocation in self._all_allocations(connection, project_ref)
            if allocation.status in _ACTIVE
        )

    def _select_devices(self, snapshot: ResourceSnapshot, claim: ResourceClaim, occupied: set[str]) -> tuple[str, ...]:
        request = claim.fit_request
        if request.required_device_kind is None:
            return ()
        eligible: list[ResourceDeviceSnapshot] = []
        for device in snapshot.devices:
            if device.device_id in occupied or device.device_kind != request.required_device_kind or device.health is not ResourceHealth.HEALTHY:
                continue
            if not set(request.required_device_features).issubset(device.features):
                continue
            if all(
                (quantity := device.available_capacity.get(metric)) is not None
                and quantity.source_kind is not QuantitySource.UNKNOWN
                and quantity.value is not None
                and float(quantity.value) >= amount
                for metric, amount in request.required_device_available.items()
            ):
                eligible.append(device)
        if not eligible:
            raise SchedulerConflictError(f"No unallocated {request.required_device_kind} device is schedulable")
        return (sorted(eligible, key=lambda item: item.device_id)[0].device_id,)

    def reserve(
        self,
        access: ProjectAccess,
        request: SchedulingRequest,
        *,
        authority_attempt: ExecutionAttempt,
        owner_ref: str,
        lease_seconds: int | float,
        idempotency_key: str,
    ) -> ResourceAllocation:
        if not isinstance(request, SchedulingRequest) or not isinstance(authority_attempt, ExecutionAttempt):
            raise SchedulerContractError("reserve requires exact request and Run authority")
        if _KEY.fullmatch(idempotency_key) is None:
            raise SchedulerContractError("idempotency_key is malformed")
        self._authorize(access, request.node_ref.project_ref)
        graph = self.graphs.get_active_graph(access, authority_attempt.run_ref)
        node = self._node(graph, request.node_ref)
        semantic = _sha({"request": request.semantic_digest, "run_attempt": authority_attempt.record_sha256, "owner_ref": owner_ref, "lease_seconds": float(lease_seconds)})
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute("SELECT * FROM scheduler_idempotency WHERE project_id=? AND operation='RESERVE' AND idempotency_key=?", (request.node_ref.project_ref.value, idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_digest"]), semantic):
                    raise SchedulerConflictError("Scheduler idempotency identity changed")
                allocation = self._fetch(connection, ResourceAllocationRef(request.node_ref.project_ref, cast(str, prior["allocation_id"])))
                connection.commit()
                return allocation
            try:
                current_run = self.runs.assert_current_run_authority_in_transaction(connection, access, authority_attempt)
            except Exception as exc:
                raise SchedulerAuthorityError("Reservation requires current Run authority") from exc
            if current_run.status != "RUNNING" or current_run.run_ref != authority_attempt.run_ref:
                raise SchedulerAuthorityError("Reservation Run is not active")
            graph_head = connection.execute(
                "SELECT graph_id,current_graph_revision FROM run_graph_heads WHERE project_id=? AND run_id=?",
                (request.node_ref.project_ref.value, authority_attempt.run_ref.run_id),
            ).fetchone()
            if graph_head is None or (
                graph_head["graph_id"] != request.node_ref.graph_ref.graph_id
                or graph_head["current_graph_revision"] != request.node_ref.graph_ref.revision
            ):
                raise SchedulerAuthorityError("Node is not in the current Graph revision")
            current_node = self.executions._fetch_execution(connection, request.node_ref)
            if current_node.status != "READY":
                raise SchedulerConflictError("Graph READY and resource-schedulable are distinct; Node is not READY")
            now = self._db_now(connection)
            expires = self._lease(now, lease_seconds)
            active = self._active_allocations(connection, request.node_ref.project_ref)
            if any(item.node_ref == request.node_ref for item in active):
                raise SchedulerConflictError("Node already has a current ResourceAllocation")
            if node.side_effect_requirement != "READ_ONLY" and request.side_effect_targets:
                for item in active:
                    if set(item.side_effect_targets).intersection(request.side_effect_targets):
                        raise SchedulerConflictError("Contested side-effect target is already reserved")
            reservations: list[ResourceReservation] = []
            for claim in request.claims:
                snapshot = self._current_snapshot(connection, claim, now, allow_reduced_fit=request.allow_reduced_fit)
                used: dict[str, float] = {}
                occupied: set[str] = set()
                for item in active:
                    for reservation in item.reservations:
                        if reservation.resource_ref != claim.resource_ref:
                            continue
                        for metric, amount in reservation.effective_capacity.items():
                            used[metric] = used.get(metric, 0.0) + amount
                        occupied.update(reservation.device_ids)
                effective: dict[str, float] = {}
                for metric, amount in claim.requested_capacity.items():
                    remaining = self._known_available(snapshot, metric) - used.get(metric, 0.0)
                    if remaining >= amount:
                        effective[metric] = amount
                        continue
                    reduced = claim.fit_request.reduced_available.get(metric)
                    if request.allow_reduced_fit and reduced is not None and remaining >= reduced:
                        effective[metric] = reduced
                        continue
                    raise SchedulerConflictError(f"Contested capacity is unavailable: {metric}")
                devices = self._select_devices(snapshot, claim, occupied)
                reservations.append(ResourceReservation(claim.resource_ref, snapshot.snapshot_ref, snapshot.record_sha256, claim.requested_capacity, effective, devices))
            generation = cast(int, connection.execute("SELECT COALESCE(MAX(allocation_generation),0)+1 FROM resource_allocation_states s JOIN resource_allocations i USING(project_id,allocation_id) WHERE i.project_id=? AND i.graph_id=? AND i.graph_revision=? AND i.node_id=?", (request.node_ref.project_ref.value, request.node_ref.graph_ref.graph_id, request.node_ref.graph_ref.revision, request.node_ref.node_id)).fetchone()[0])
            ref = ResourceAllocationRef(request.node_ref.project_ref, f"ral_{uuid4().hex}")
            allocation = ResourceAllocation(ref, request.node_ref, authority_attempt.run_ref, authority_attempt.attempt_id, authority_attempt.fence, request.semantic_digest, tuple(reservations), request.side_effect_targets, generation, generation, owner_ref, expires, "RESERVED", 1, None, None, None, None, now, now)
            connection.execute("INSERT INTO resource_allocations VALUES (?,?,?,?,?,?,?,?,?,?,?)", (allocation.project_ref.value, ref.allocation_id, allocation.run_ref.run_id, allocation.run_attempt_id, allocation.run_attempt_fence, allocation.node_ref.graph_ref.graph_id, allocation.node_ref.graph_ref.revision, allocation.node_ref.node_id, allocation.request_digest, allocation.created_at, allocation.identity_sha256))
            self._insert_state(connection, allocation)
            connection.execute("INSERT INTO resource_allocation_heads VALUES (?,?,?,?,?,?)", (allocation.project_ref.value, ref.allocation_id, 1, allocation.state_sha256, now, self._head_sha(allocation)))
            for reservation in reservations:
                payload = reservation.payload()
                connection.execute("INSERT INTO resource_allocation_reservations VALUES (?,?,?,?,?,?,?,?,?)", (allocation.project_ref.value, ref.allocation_id, reservation.resource_ref.resource_id, reservation.snapshot_ref.snapshot_id, reservation.snapshot_record_sha256, _json(dict(reservation.requested_capacity)), _json(dict(reservation.effective_capacity)), _json(list(reservation.device_ids)), _sha(payload)))
            connection.executemany("INSERT INTO resource_allocation_side_effects VALUES (?,?,?)", ((allocation.project_ref.value, ref.allocation_id, target) for target in request.side_effect_targets))
            connection.execute("INSERT INTO scheduler_idempotency VALUES (?,?,?,?,?)", (allocation.project_ref.value, "RESERVE", idempotency_key, semantic, ref.allocation_id))
            connection.commit()
            return allocation
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise SchedulerConflictError("Atomic ResourceAllocation conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _insert_state(self, connection: sqlite3.Connection, allocation: ResourceAllocation) -> None:
        connection.execute("INSERT INTO resource_allocation_states VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (allocation.project_ref.value, allocation.allocation_ref.allocation_id, allocation.state_version, allocation.allocation_generation, allocation.fence, allocation.status, allocation.owner_ref, allocation.lease_expires_at, allocation.dispatch_idempotency_key, allocation.node_attempt_id, allocation.node_attempt_fence, allocation.terminal_outcome, allocation.updated_at, allocation.state_sha256))

    def _advance(self, connection: sqlite3.Connection, prior: ResourceAllocation, current: ResourceAllocation) -> None:
        self._insert_state(connection, current)
        changed = connection.execute("UPDATE resource_allocation_heads SET state_version=?,state_sha256=?,updated_at=?,head_sha256=? WHERE project_id=? AND allocation_id=? AND state_version=? AND state_sha256=? AND head_sha256=?", (current.state_version, current.state_sha256, current.updated_at, self._head_sha(current), prior.project_ref.value, prior.allocation_ref.allocation_id, prior.state_version, prior.state_sha256, self._head_sha(prior)))
        if changed.rowcount != 1:
            raise SchedulerConflictError("ResourceAllocation fence changed concurrently")

    def _next(self, prior: ResourceAllocation, *, status: str, now: str, lease_expires_at: str | None, dispatch_idempotency_key: str | None = None, node_attempt: NodeExecutionAttempt | None = None, outcome: str | None = None) -> ResourceAllocation:
        return ResourceAllocation(prior.allocation_ref, prior.node_ref, prior.run_ref, prior.run_attempt_id, prior.run_attempt_fence, prior.request_digest, prior.reservations, prior.side_effect_targets, prior.allocation_generation, prior.fence, prior.owner_ref, lease_expires_at, status, prior.state_version + 1, dispatch_idempotency_key if dispatch_idempotency_key is not None else prior.dispatch_idempotency_key, node_attempt.attempt_id if node_attempt is not None else prior.node_attempt_id, node_attempt.fence if node_attempt is not None else prior.node_attempt_fence, outcome, prior.created_at, now)

    def _bind_dispatch_attempt(
        self,
        connection: sqlite3.Connection,
        current: ResourceAllocation,
        attempt: NodeExecutionAttempt,
    ) -> ResourceAllocation:
        if (
            attempt.node_ref != current.node_ref
            or attempt.run_ref != current.run_ref
            or attempt.run_attempt_id != current.run_attempt_id
            or attempt.run_fence != current.run_attempt_fence
            or attempt.owner_ref != current.owner_ref
        ):
            raise SchedulerIntegrityError("Dispatch attempt provenance differs from ResourceAllocation")
        if current.node_attempt_id is not None:
            if current.node_attempt_id != attempt.attempt_id or current.node_attempt_fence != attempt.fence:
                raise SchedulerIntegrityError("ResourceAllocation is bound to a different Node attempt")
            return current
        now = self._db_now(connection)
        bound = self._next(
            current,
            status="DISPATCHING",
            now=now,
            lease_expires_at=attempt.lease_expires_at,
            node_attempt=attempt,
        )
        self._advance(connection, current, bound)
        return bound

    def dispatch(self, access: ProjectAccess, allocation: ResourceAllocation, *, authority_attempt: ExecutionAttempt, lease_seconds: int | float, idempotency_key: str) -> ScheduledDispatch:
        if _KEY.fullmatch(idempotency_key) is None:
            raise SchedulerContractError("dispatch idempotency_key is malformed")
        if (
            authority_attempt.attempt_id != allocation.run_attempt_id
            or authority_attempt.fence != allocation.run_attempt_fence
            or authority_attempt.run_ref != allocation.run_ref
        ):
            raise SchedulerAuthorityError("Dispatch Run attempt differs from reservation authority")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch(connection, allocation.allocation_ref)
            if current.status == "DISPATCHED":
                if current.dispatch_idempotency_key != idempotency_key:
                    raise SchedulerConflictError("Allocation was dispatched by a different claim")
                connection.commit()
                assert current.node_attempt_id is not None
                attempt = self.executions._fetch_attempt(connection, current.node_ref, current.node_attempt_id)
                return ScheduledDispatch(current, attempt)
            if current.status not in _ACTIVE:
                if current.dispatch_idempotency_key != idempotency_key or current.node_attempt_id is None:
                    raise SchedulerAuthorityError("Only the exact completed dispatch claim may replay")
                attempt = self.executions._fetch_attempt(connection, current.node_ref, current.node_attempt_id)
                if attempt.fence != current.node_attempt_fence:
                    raise SchedulerIntegrityError("Completed dispatch attempt fence differs")
                connection.commit()
                return ScheduledDispatch(current, attempt)
            if current.status == "DISPATCHING":
                if current.dispatch_idempotency_key != idempotency_key:
                    raise SchedulerConflictError("Allocation dispatch is already claimed")
                claimed = current
            elif current.status == "RESERVED":
                self._require_fence(allocation, current)
                now = self._db_now(connection)
                claimed = self._next(
                    current,
                    status="DISPATCHING",
                    now=now,
                    lease_expires_at=self._lease(now, lease_seconds),
                    dispatch_idempotency_key=idempotency_key,
                )
                self._advance(connection, current, claimed)
            else:
                raise SchedulerAuthorityError("Only a current reservation may dispatch")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        node_key = "scheduler-node-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:40]
        attempt = self.executions.lease_node(access, claimed.node_ref, authority_attempt=authority_attempt, owner_ref=claimed.owner_ref, lease_seconds=lease_seconds, idempotency_key=node_key)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            fresh = self._fetch(connection, claimed.allocation_ref)
            if fresh.status == "DISPATCHED":
                if fresh.dispatch_idempotency_key != idempotency_key or fresh.node_attempt_id != attempt.attempt_id or fresh.node_attempt_fence != attempt.fence:
                    raise SchedulerConflictError("Allocation dispatch binding conflicts")
                connection.commit()
                return ScheduledDispatch(fresh, attempt)
            if fresh.status not in _ACTIVE:
                if fresh.dispatch_idempotency_key == idempotency_key and fresh.node_attempt_id == attempt.attempt_id and fresh.node_attempt_fence == attempt.fence:
                    connection.commit()
                    return ScheduledDispatch(fresh, attempt)
                raise SchedulerAuthorityError("Allocation dispatch claim is no longer current")
            if fresh.status != "DISPATCHING" or fresh.dispatch_idempotency_key != idempotency_key:
                raise SchedulerAuthorityError("Allocation dispatch claim is no longer current")
            self._bind_dispatch_attempt(connection, fresh, attempt)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self.executions.start_node(access, attempt, idempotency_key="scheduler-start-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:39])
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            fresh = self._fetch(connection, claimed.allocation_ref)
            if fresh.status == "DISPATCHED":
                if fresh.dispatch_idempotency_key != idempotency_key or fresh.node_attempt_id != attempt.attempt_id or fresh.node_attempt_fence != attempt.fence:
                    raise SchedulerConflictError("Allocation dispatch binding conflicts")
                connection.commit()
                return ScheduledDispatch(fresh, attempt)
            if fresh.status not in _ACTIVE:
                if fresh.dispatch_idempotency_key == idempotency_key and fresh.node_attempt_id == attempt.attempt_id and fresh.node_attempt_fence == attempt.fence:
                    connection.commit()
                    return ScheduledDispatch(fresh, attempt)
                raise SchedulerAuthorityError("Allocation dispatch claim is no longer current")
            if fresh.status != "DISPATCHING" or fresh.dispatch_idempotency_key != idempotency_key or fresh.node_attempt_id != attempt.attempt_id or fresh.node_attempt_fence != attempt.fence:
                raise SchedulerAuthorityError("Allocation dispatch claim is no longer current")
            now = self._db_now(connection)
            dispatched = self._next(fresh, status="DISPATCHED", now=now, lease_expires_at=attempt.lease_expires_at, node_attempt=attempt)
            self._advance(connection, fresh, dispatched)
            connection.commit()
            return ScheduledDispatch(dispatched, attempt)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _require_fence(provided: ResourceAllocation, current: ResourceAllocation) -> None:
        if provided.allocation_ref != current.allocation_ref or provided.fence != current.fence or provided.state_version != current.state_version or not hmac.compare_digest(provided.state_sha256, current.state_sha256):
            raise SchedulerAuthorityError("Stale ResourceAllocation fence cannot mutate current state")

    def heartbeat(self, access: ProjectAccess, allocation: ResourceAllocation, *, lease_seconds: int | float) -> ResourceAllocation:
        self._authorize(access, allocation.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch(connection, allocation.allocation_ref)
            self._require_fence(allocation, current)
            if current.status not in _ACTIVE:
                raise SchedulerAuthorityError("Terminal allocation cannot heartbeat")
            now = self._db_now(connection)
            renewed = self._next(current, status=current.status, now=now, lease_expires_at=self._lease(now, lease_seconds))
            self._advance(connection, current, renewed)
            connection.commit()
            return renewed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def release(self, access: ProjectAccess, allocation: ResourceAllocation, *, outcome: str, idempotency_key: str) -> ResourceAllocation:
        if outcome not in _OUTCOMES or _KEY.fullmatch(idempotency_key) is None:
            raise SchedulerContractError("Release outcome or idempotency key is malformed")
        self._authorize(access, allocation.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch(connection, allocation.allocation_ref)
            if current.status not in _ACTIVE:
                if current.terminal_outcome == outcome:
                    connection.commit()
                    return current
                raise SchedulerAuthorityError("Stale allocation cannot change terminal outcome")
            self._require_fence(allocation, current)
            if outcome in {"EXECUTOR_LOST", "DISPATCH_FAILED"}:
                raise SchedulerAuthorityError("Executor-loss release is recovery-authoritative")
            if current.status == "DISPATCHING" and current.node_attempt_id is None:
                execution = self.executions._fetch_execution(connection, current.node_ref)
                if outcome != "TERMINAL" or execution.status not in {"SUCCEEDED", "FAILED", "CANCELLED"} or execution.current_attempt_id is None:
                    raise SchedulerAuthorityError("In-flight dispatch retains capacity until exact recovery")
                attempt = self.executions._fetch_attempt(connection, current.node_ref, execution.current_attempt_id)
                if execution.current_fence != attempt.fence:
                    raise SchedulerIntegrityError("Terminal Node attempt fence differs")
                current = self._bind_dispatch_attempt(connection, current, attempt)
            if current.status == "DISPATCHING" and outcome != "TERMINAL":
                raise SchedulerAuthorityError("In-flight dispatch retains capacity until exact recovery")
            if outcome == "CANCELLED" and current.node_attempt_id is not None:
                execution = self.executions._fetch_execution(connection, current.node_ref)
                if (
                    execution.status != "CANCELLED"
                    or execution.current_attempt_id != current.node_attempt_id
                    or execution.current_fence != current.node_attempt_fence
                ):
                    raise SchedulerAuthorityError("Dispatched allocation requires authoritative Node cancellation")
            if outcome in {"COMPLETED", "TERMINAL"}:
                execution = self.executions._fetch_execution(connection, current.node_ref)
                if execution.status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    raise SchedulerAuthorityError("Completion release requires terminal Node authority")
                if current.node_attempt_id is not None and (
                    execution.current_attempt_id != current.node_attempt_id
                    or execution.current_fence != current.node_attempt_fence
                ):
                    raise SchedulerAuthorityError("Completion release Node fence is stale")
            status = {"CANCELLED": "CANCELLED", "EXECUTOR_LOST": "EXPIRED", "DISPATCH_FAILED": "FAILED"}.get(outcome, "RELEASED")
            now = self._db_now(connection)
            released = self._next(current, status=status, now=now, lease_expires_at=None, outcome=outcome)
            self._advance(connection, current, released)
            connection.commit()
            return released
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover_expired_allocations(self, access: ProjectAccess, project_ref: ProjectRef) -> tuple[ResourceAllocation, ...]:
        self._authorize(access, project_ref)
        recovered: list[ResourceAllocation] = []
        for allocation in self.list_allocations(access, project_ref, active_only=True):
            result = self._recover_one(access, allocation.allocation_ref)
            if result is not None:
                recovered.append(result)
        return tuple(recovered)

    def _recover_one(
        self,
        access: ProjectAccess,
        allocation_ref: ResourceAllocationRef,
        *,
        execution_recovery_attempted: bool = False,
    ) -> ResourceAllocation | None:
        connection = self._connect()
        recover_run: RunRef | None = None
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch(connection, allocation_ref)
            if current.status not in _ACTIVE:
                connection.commit()
                return None
            now = self._db_now(connection)
            assert current.lease_expires_at is not None
            if datetime.fromisoformat(current.lease_expires_at) > datetime.fromisoformat(now):
                connection.commit()
                return None
            execution = self.executions._fetch_execution(connection, current.node_ref)
            if current.status == "DISPATCHING" and current.node_attempt_id is None and execution.current_attempt_id is not None:
                attempt = self.executions._fetch_attempt(connection, current.node_ref, execution.current_attempt_id)
                if execution.current_fence != attempt.fence:
                    raise SchedulerIntegrityError("Expired Node attempt fence differs")
                current = self._bind_dispatch_attempt(connection, current, attempt)
            if current.node_attempt_id is not None and (
                execution.current_attempt_id != current.node_attempt_id
                or execution.current_fence != current.node_attempt_fence
            ):
                raise SchedulerIntegrityError("Expired allocation is not bound to the current Node attempt")
            if execution.status in {"LEASED", "RUNNING", "WAITING_EXTERNAL"}:
                assert execution.lease_expires_at is not None
                if datetime.fromisoformat(execution.lease_expires_at) > datetime.fromisoformat(now):
                    connection.commit()
                    return None
                if execution_recovery_attempted:
                    connection.commit()
                    return None
                recover_run = current.run_ref
                connection.rollback()
            else:
                outcome = "TERMINAL" if execution.status in {"SUCCEEDED", "FAILED", "CANCELLED"} else "EXECUTOR_LOST"
                status = "RELEASED" if outcome == "TERMINAL" else "EXPIRED"
                recovered = self._next(current, status=status, now=now, lease_expires_at=None, outcome=outcome)
                self._advance(connection, current, recovered)
                connection.commit()
                return recovered
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        assert recover_run is not None
        self.executions.recover_expired_execution(access, recover_run)
        return self._recover_one(access, allocation_ref, execution_recovery_attempted=True)

    def reconcile_terminal(self, access: ProjectAccess, run_ref: RunRef) -> tuple[ResourceAllocation, ...]:
        released: list[ResourceAllocation] = []
        for allocation in self.list_allocations(access, run_ref.project_ref, active_only=True):
            if allocation.run_ref != run_ref:
                continue
            execution = self.executions.get_node_execution(access, allocation.node_ref)
            if execution.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                released.append(self.release(access, allocation, outcome="TERMINAL", idempotency_key="terminal-" + allocation.allocation_ref.allocation_id[4:]))
        return tuple(released)

    def get_allocation(self, access: ProjectAccess, ref: ResourceAllocationRef) -> ResourceAllocation:
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            value = self._fetch(connection, ref)
            connection.commit()
            return value
        finally:
            connection.close()

    def list_allocations(self, access: ProjectAccess, project_ref: ProjectRef, *, active_only: bool = False) -> tuple[ResourceAllocation, ...]:
        self._authorize(access, project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            values = self._all_allocations(connection, project_ref)
            result = tuple(item for item in values if not active_only or item.status in _ACTIVE)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch(self, connection: sqlite3.Connection, ref: ResourceAllocationRef) -> ResourceAllocation:
        identity = connection.execute("SELECT * FROM resource_allocations WHERE project_id=? AND allocation_id=?", (ref.project_ref.value, ref.allocation_id)).fetchone()
        if identity is None:
            raise SchedulerNotFoundError("ResourceAllocation not found")
        rows = connection.execute("SELECT * FROM resource_allocation_states WHERE project_id=? AND allocation_id=? ORDER BY state_version", (ref.project_ref.value, ref.allocation_id)).fetchall()
        if tuple(row["state_version"] for row in rows) != tuple(range(1, len(rows) + 1)):
            raise SchedulerIntegrityError("ResourceAllocation history is not gap-free")
        reservations: list[ResourceReservation] = []
        for row in connection.execute("SELECT * FROM resource_allocation_reservations WHERE project_id=? AND allocation_id=? ORDER BY resource_id", (ref.project_ref.value, ref.allocation_id)).fetchall():
            resource_ref = ResourceRef(ref.project_ref, cast(str, row["resource_id"]))
            reservation = ResourceReservation(resource_ref, ResourceSnapshotRef(resource_ref, cast(str, row["snapshot_id"])), cast(str, row["snapshot_record_sha256"]), cast(dict[str, float], json.loads(cast(str, row["requested_capacity_json"]))), cast(dict[str, float], json.loads(cast(str, row["effective_capacity_json"]))), tuple(cast(list[str], json.loads(cast(str, row["device_ids_json"])))))
            if not hmac.compare_digest(_sha(reservation.payload()), cast(str, row["record_sha256"])):
                raise SchedulerIntegrityError("Resource reservation evidence changed")
            snapshot_row = connection.execute("SELECT * FROM resource_snapshots WHERE project_id=? AND resource_id=? AND snapshot_id=?", (ref.project_ref.value, resource_ref.resource_id, reservation.snapshot_ref.snapshot_id)).fetchone()
            if snapshot_row is None:
                raise SchedulerIntegrityError("Resource reservation snapshot is missing")
            try:
                snapshot = self.resources._snapshot_from_row(snapshot_row)
                self.resources._verify_snapshot_chain(connection, snapshot)
            except ResourceInventoryIntegrityError as exc:
                raise SchedulerIntegrityError("Resource reservation snapshot is inconsistent") from exc
            if not hmac.compare_digest(snapshot.record_sha256, reservation.snapshot_record_sha256):
                raise SchedulerIntegrityError("Resource reservation provenance changed")
            reservations.append(reservation)
        targets = tuple(cast(str, row[0]) for row in connection.execute("SELECT target_ref FROM resource_allocation_side_effects WHERE project_id=? AND allocation_id=? ORDER BY target_ref", (ref.project_ref.value, ref.allocation_id)).fetchall())
        graph_ref = GraphRef(ref.project_ref, cast(str, identity["graph_id"]), cast(int, identity["graph_revision"]))
        node_ref = NodeRef(graph_ref, cast(str, identity["node_id"]))
        history = tuple(ResourceAllocation(ref, node_ref, RunRef(ref.project_ref, cast(str, identity["run_id"])), cast(str, identity["run_attempt_id"]), cast(int, identity["run_attempt_fence"]), cast(str, identity["request_digest"]), tuple(reservations), targets, cast(int, row["allocation_generation"]), cast(int, row["fence"]), cast(str, row["owner_ref"]), cast(str | None, row["lease_expires_at"]), cast(str, row["status"]), cast(int, row["state_version"]), cast(str | None, row["dispatch_idempotency_key"]), cast(str | None, row["node_attempt_id"]), cast(int | None, row["node_attempt_fence"]), cast(str | None, row["terminal_outcome"]), cast(str, identity["created_at"]), cast(str, row["updated_at"])) for row in rows)
        if not history:
            raise SchedulerIntegrityError("ResourceAllocation has no state")
        for allocation, row in zip(history, rows):
            if not hmac.compare_digest(allocation.state_sha256, cast(str, row["state_sha256"])):
                raise SchedulerIntegrityError("ResourceAllocation state evidence changed")
            if allocation.node_attempt_id is not None:
                try:
                    attempt = self.executions._fetch_attempt(connection, node_ref, allocation.node_attempt_id)
                except Exception as exc:
                    raise SchedulerIntegrityError("ResourceAllocation Node attempt evidence is missing") from exc
                if (
                    attempt.fence != allocation.node_attempt_fence
                    or attempt.run_ref != allocation.run_ref
                    or attempt.run_attempt_id != allocation.run_attempt_id
                    or attempt.run_fence != allocation.run_attempt_fence
                    or attempt.owner_ref != allocation.owner_ref
                ):
                    raise SchedulerIntegrityError("ResourceAllocation Node attempt provenance differs")
        latest = history[-1]
        if not hmac.compare_digest(latest.identity_sha256, cast(str, identity["identity_sha256"])):
            raise SchedulerIntegrityError("ResourceAllocation identity changed")
        for previous, current in zip(history, history[1:]):
            if current.state_version != previous.state_version + 1 or current.fence != previous.fence or previous.status not in _ACTIVE:
                raise SchedulerIntegrityError("ResourceAllocation lineage is invalid")
        head = connection.execute("SELECT * FROM resource_allocation_heads WHERE project_id=? AND allocation_id=?", (ref.project_ref.value, ref.allocation_id)).fetchone()
        if head is None or head["state_version"] != latest.state_version or not hmac.compare_digest(cast(str, head["state_sha256"]), latest.state_sha256) or not hmac.compare_digest(cast(str, head["head_sha256"]), self._head_sha(latest)):
            raise SchedulerIntegrityError("ResourceAllocation head differs from history")
        return latest

    def _rank(self, access: ProjectAccess, request: SchedulingRequest, now: datetime) -> tuple[int, float, str, str, tuple[str, ...]]:
        fit_rank = 0
        at = now.isoformat(timespec="microseconds")
        try:
            for claim in request.claims:
                snapshot = self.resources.latest_snapshot(
                    access,
                    claim.resource_ref,
                    require_fresh=False,
                )
                classification = evaluateResourceFit(snapshot, claim.fit_request, at=at).classification
                if classification is ResourceFit.FIT:
                    continue
                if classification is ResourceFit.FIT_REDUCED and request.allow_reduced_fit:
                    fit_rank = max(fit_rank, 1)
                else:
                    fit_rank = 2
        except Exception:
            fit_rank = 2
        age = max(0.0, (now - datetime.fromisoformat(request.queued_at)).total_seconds())
        effective_priority = request.priority + math.floor(age / self.aging_seconds)
        deadline = request.deadline or "9999-12-31T23:59:59+00:00"
        return (
            fit_rank,
            -float(effective_priority),
            deadline,
            request.node_ref.value,
            tuple(claim.resource_ref.value for claim in request.claims),
        )

    def _record_queue(self, connection: sqlite3.Connection, entry: SchedulerQueueEntry) -> None:
        key = (
            entry.request.node_ref.project_ref.value,
            entry.request.node_ref.graph_ref.graph_id,
            entry.request.node_ref.graph_ref.revision,
            entry.request.node_ref.node_id,
        )
        connection.execute(
            "INSERT INTO scheduler_queue_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (*key, entry.sequence, _json(entry.request.payload()), entry.request.semantic_digest,
             entry.status, entry.exact_cause, entry.updated_at, entry.record_sha256),
        )
        head = connection.execute(
            "SELECT sequence,record_sha256 FROM scheduler_queue_heads WHERE project_id=? AND graph_id=? AND graph_revision=? AND node_id=?",
            key,
        ).fetchone()
        if head is None:
            if entry.sequence != 1:
                raise SchedulerIntegrityError("Scheduler queue head is missing")
            connection.execute("INSERT INTO scheduler_queue_heads VALUES (?,?,?,?,?,?)", (*key, entry.sequence, entry.record_sha256))
        else:
            prior = connection.execute(
                """SELECT record_sha256 FROM scheduler_queue_events WHERE project_id=? AND graph_id=?
                   AND graph_revision=? AND node_id=? AND sequence=?""",
                (*key, cast(int, head["sequence"])),
            ).fetchone()
            if (
                entry.sequence != cast(int, head["sequence"]) + 1
                or prior is None
                or not hmac.compare_digest(cast(str, prior["record_sha256"]), cast(str, head["record_sha256"]))
            ):
                raise SchedulerIntegrityError("Scheduler queue head is inconsistent")
            changed = connection.execute(
                "UPDATE scheduler_queue_heads SET sequence=?,record_sha256=? WHERE project_id=? AND graph_id=? AND graph_revision=? AND node_id=? AND sequence=?",
                (entry.sequence, entry.record_sha256, *key, cast(int, head["sequence"])),
            )
            if changed.rowcount != 1:
                raise SchedulerConflictError("Scheduler queue head changed concurrently")

    def list_queue(self, access: ProjectAccess, project_ref: ProjectRef, *, waiting_only: bool = True) -> tuple[SchedulerQueueEntry, ...]:
        self._authorize(access, project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            nodes = connection.execute(
                """SELECT graph_id,graph_revision,node_id FROM scheduler_queue_events
                   WHERE project_id=? GROUP BY graph_id,graph_revision,node_id
                   ORDER BY graph_id,graph_revision,node_id""",
                (project_ref.value,),
            ).fetchall()
            head_nodes = connection.execute(
                """SELECT graph_id,graph_revision,node_id FROM scheduler_queue_heads
                   WHERE project_id=? ORDER BY graph_id,graph_revision,node_id""",
                (project_ref.value,),
            ).fetchall()
            event_keys = {(row["graph_id"], row["graph_revision"], row["node_id"]) for row in nodes}
            head_keys = {(row["graph_id"], row["graph_revision"], row["node_id"]) for row in head_nodes}
            if event_keys != head_keys:
                raise SchedulerIntegrityError("Scheduler queue identity and head sets differ")
            entries: list[SchedulerQueueEntry] = []
            for node in nodes:
                key = (project_ref.value, node["graph_id"], node["graph_revision"], node["node_id"])
                rows = connection.execute(
                    """SELECT * FROM scheduler_queue_events WHERE project_id=? AND graph_id=?
                       AND graph_revision=? AND node_id=? ORDER BY sequence""",
                    key,
                ).fetchall()
                if tuple(row["sequence"] for row in rows) != tuple(range(1, len(rows) + 1)):
                    raise SchedulerIntegrityError("Scheduler queue history is not gap-free")
                history: list[SchedulerQueueEntry] = []
                for row in rows:
                    request = SchedulingRequest.from_payload(project_ref, json.loads(cast(str, row["request_json"])))
                    if not hmac.compare_digest(request.semantic_digest, cast(str, row["request_digest"])):
                        raise SchedulerIntegrityError("Queued request digest changed")
                    entry = SchedulerQueueEntry(request, cast(str, row["status"]), cast(str | None, row["exact_cause"]), cast(int, row["sequence"]), cast(str, row["updated_at"]))
                    if not hmac.compare_digest(entry.record_sha256, cast(str, row["record_sha256"])):
                        raise SchedulerIntegrityError("Scheduler queue evidence changed")
                    history.append(entry)
                head = connection.execute(
                    "SELECT * FROM scheduler_queue_heads WHERE project_id=? AND graph_id=? AND graph_revision=? AND node_id=?",
                    key,
                ).fetchone()
                latest = history[-1]
                if head is None or head["sequence"] != latest.sequence or not hmac.compare_digest(cast(str, head["record_sha256"]), latest.record_sha256):
                    raise SchedulerIntegrityError("Scheduler queue head differs from history")
                if not waiting_only or latest.status == "WAITING":
                    entries.append(latest)
            result = tuple(sorted(entries, key=lambda item: (item.updated_at, item.request.node_ref.value)))
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def schedule_cycle(self, access: ProjectAccess, requests: Sequence[SchedulingRequest], *, authority_attempt: ExecutionAttempt, owner_ref: str, lease_seconds: int | float, dispatcher: DispatchCallback | None = None) -> ScheduleCycleResult:
        if isinstance(requests, (str, bytes)) or not isinstance(requests, Sequence) or len(requests) > 4096:
            raise SchedulerContractError("schedule cycle requests are malformed or unbounded")
        if not isinstance(authority_attempt, ExecutionAttempt) or not all(isinstance(item, SchedulingRequest) for item in requests):
            raise SchedulerContractError("schedule cycle requires exact requests and Run authority")
        if not isinstance(owner_ref, str) or len(owner_ref.encode()) > 1024 or re.fullmatch(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]+", owner_ref) is None:
            raise SchedulerContractError("schedule cycle owner is malformed")
        self._lease(_now(), lease_seconds)
        if dispatcher is not None and not callable(dispatcher):
            raise SchedulerContractError("dispatcher must be callable")
        self._authorize(access, authority_attempt.run_ref.project_ref)
        if any(item.node_ref.project_ref != authority_attempt.run_ref.project_ref for item in requests):
            raise SchedulerScopeError("Schedule cycle requests crossed Run Project scope")
        try:
            self.runs.assert_current_run_authority(access, authority_attempt)
        except Exception as exc:
            raise SchedulerAuthorityError("Schedule cycle requires current Run authority") from exc
        graph = self.graphs.get_active_graph(access, authority_attempt.run_ref)
        graph_nodes = {node.node_ref for node in graph.nodes}
        if any(item.node_ref not in graph_nodes for item in requests):
            raise SchedulerAuthorityError("Schedule cycle Node is not in the current Run Graph")
        started = _now()
        ranked = sorted(
            tuple(requests),
            key=lambda item: self._rank(access, item, datetime.fromisoformat(started)),
        )
        selected: dict[NodeRef, SchedulingRequest] = {}
        for request in ranked:
            selected.setdefault(request.node_ref, request)
        ordered = tuple(selected.values())
        queue_connection = self._connect()
        try:
            queue_connection.execute("BEGIN IMMEDIATE")
            for request in ordered:
                prior = queue_connection.execute(
                    "SELECT COALESCE(MAX(sequence),0) FROM scheduler_queue_events WHERE project_id=? AND graph_id=? AND graph_revision=? AND node_id=?",
                    (request.node_ref.project_ref.value, request.node_ref.graph_ref.graph_id, request.node_ref.graph_ref.revision, request.node_ref.node_id),
                ).fetchone()
                self._record_queue(
                    queue_connection,
                    SchedulerQueueEntry(
                        request,
                        "WAITING",
                        "scheduler_cycle_pending",
                        cast(int, prior[0]) + 1,
                        started,
                    ),
                )
            queue_connection.commit()
        except Exception:
            queue_connection.rollback()
            raise
        finally:
            queue_connection.close()
        reserved: list[ResourceAllocation] = []
        deferred: list[NodeRef] = []
        failures: dict[NodeRef, str] = {}
        for request in ordered:
            try:
                reserved.append(self.reserve(access, request, authority_attempt=authority_attempt, owner_ref=owner_ref, lease_seconds=lease_seconds, idempotency_key="cycle-" + request.semantic_digest[:48]))
            except SchedulerConflictError as exc:
                deferred.append(request.node_ref)
                failures[request.node_ref] = str(exc)
        dispatched: list[ScheduledDispatch] = []
        if reserved:
            with ThreadPoolExecutor(max_workers=len(reserved), thread_name_prefix="biella-scheduler") as pool:
                futures = [pool.submit(self.dispatch, access, allocation, authority_attempt=authority_attempt, lease_seconds=lease_seconds, idempotency_key="dispatch-" + allocation.allocation_ref.allocation_id[4:]) for allocation in reserved]
                for allocation, future in zip(reserved, futures):
                    try:
                        dispatched.append(future.result())
                    except Exception as exc:
                        failures[allocation.node_ref] = f"{type(exc).__name__}:{exc}"
            if dispatcher is not None and dispatched:
                def invoke(item: ScheduledDispatch) -> tuple[int, int, str | None]:
                    began = time.monotonic_ns()
                    error: str | None = None
                    try:
                        dispatcher(item)
                    except Exception as exc:
                        error = f"{type(exc).__name__}:{exc}"
                    finally:
                        fresh = self.get_allocation(access, item.allocation.allocation_ref)
                        execution = self.executions.get_node_execution(access, item.allocation.node_ref)
                        if fresh.status in _ACTIVE and execution.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                            self.release(access, fresh, outcome="TERMINAL", idempotency_key="complete-" + fresh.allocation_ref.allocation_id[4:])
                    return began, time.monotonic_ns(), error
                with ThreadPoolExecutor(max_workers=len(dispatched), thread_name_prefix="biella-productive") as pool:
                    callback_futures = [pool.submit(invoke, item) for item in dispatched]
                    intervals: list[tuple[int, int]] = []
                    for item, callback_future in zip(dispatched, callback_futures):
                        began, ended, error = callback_future.result()
                        intervals.append((began, ended))
                        if error is not None:
                            failures[item.allocation.node_ref] = error
                    active = 0
                    peak = 0
                    for _, delta in sorted(
                        ((point, delta) for began, ended in intervals for point, delta in ((began, 1), (ended, -1))),
                        key=lambda event: (event[0], event[1]),
                    ):
                        active += delta
                        peak = max(peak, active)
            else:
                peak = 0
        else:
            peak = 0
        finished = _now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            for request in ordered:
                prior = connection.execute(
                    "SELECT COALESCE(MAX(sequence),0) FROM scheduler_queue_events WHERE project_id=? AND graph_id=? AND graph_revision=? AND node_id=?",
                    (request.node_ref.project_ref.value, request.node_ref.graph_ref.graph_id, request.node_ref.graph_ref.revision, request.node_ref.node_id),
                ).fetchone()
                cause = failures.get(request.node_ref)
                status = "WAITING" if request.node_ref in deferred else ("FAILED" if cause is not None else "DISPATCHED")
                self._record_queue(connection, SchedulerQueueEntry(request, status, cause, cast(int, prior[0]) + 1, finished))
            project_ref = authority_attempt.run_ref.project_ref
            metric_head = connection.execute(
                "SELECT cycle_sequence,record_sha256 FROM scheduler_cycle_metric_heads WHERE project_id=?",
                (project_ref.value,),
            ).fetchone()
            maximum_sequence = connection.execute(
                "SELECT MAX(cycle_sequence) FROM scheduler_cycle_metrics WHERE project_id=?",
                (project_ref.value,),
            ).fetchone()[0]
            if metric_head is None:
                if maximum_sequence is not None:
                    raise SchedulerIntegrityError("Scheduler cycle metric head is missing")
                cycle_sequence = 1
                previous_record_sha256 = None
            else:
                prior_metric = connection.execute(
                    "SELECT record_sha256 FROM scheduler_cycle_metrics WHERE project_id=? AND cycle_sequence=?",
                    (project_ref.value, cast(int, metric_head["cycle_sequence"])),
                ).fetchone()
                if (
                    prior_metric is None
                    or maximum_sequence != metric_head["cycle_sequence"]
                    or not hmac.compare_digest(cast(str, prior_metric["record_sha256"]), cast(str, metric_head["record_sha256"]))
                ):
                    raise SchedulerIntegrityError("Scheduler cycle metric head is inconsistent")
                cycle_sequence = cast(int, metric_head["cycle_sequence"]) + 1
                previous_record_sha256 = cast(str, metric_head["record_sha256"])
            cycle_id = f"cyc_{uuid4().hex}"
            metric_sha256 = self._cycle_metric_sha(
                cycle_id,
                project_ref,
                cycle_sequence,
                previous_record_sha256,
                started,
                finished,
                len(deferred),
                peak,
            )
            connection.execute(
                "INSERT INTO scheduler_cycle_metrics VALUES (?,?,?,?,?,?,?,?,?)",
                (cycle_id, project_ref.value, cycle_sequence, previous_record_sha256, started, finished, len(deferred), peak, metric_sha256),
            )
            if metric_head is None:
                connection.execute(
                    "INSERT INTO scheduler_cycle_metric_heads VALUES (?,?,?)",
                    (project_ref.value, cycle_sequence, metric_sha256),
                )
            else:
                changed = connection.execute(
                    "UPDATE scheduler_cycle_metric_heads SET cycle_sequence=?,record_sha256=? WHERE project_id=? AND cycle_sequence=? AND record_sha256=?",
                    (cycle_sequence, metric_sha256, project_ref.value, cast(int, metric_head["cycle_sequence"]), previous_record_sha256),
                )
                if changed.rowcount != 1:
                    raise SchedulerConflictError("Scheduler cycle metric head changed concurrently")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return ScheduleCycleResult(tuple(dispatched), tuple(deferred), MappingProxyType(dict(failures)))

    def metrics(self, access: ProjectAccess, project_ref: ProjectRef) -> SchedulerMetrics:
        self._authorize(access, project_ref)
        allocations = self.list_allocations(access, project_ref, active_only=True)
        queue_pressure = len(self.list_queue(access, project_ref, waiting_only=True))
        devices: dict[tuple[ResourceRef, str], int] = {}
        capacities: dict[tuple[ResourceRef, str], float] = {}
        budgets: dict[tuple[ResourceRef, str], float] = {}
        resource_leaks = 0
        for allocation in allocations:
            execution = self.executions.get_node_execution(access, allocation.node_ref)
            if execution.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                resource_leaks += 1
            for reservation in allocation.reservations:
                snapshot = self.resources.get_snapshot(access, reservation.snapshot_ref)
                for device_id in reservation.device_ids:
                    key = (reservation.resource_ref, device_id)
                    devices[key] = devices.get(key, 0) + 1
                for metric, amount in reservation.effective_capacity.items():
                    key = (reservation.resource_ref, metric)
                    capacities[key] = capacities.get(key, 0.0) + amount
                    quantity = snapshot.available_capacity.get(metric)
                    if quantity is not None and quantity.value is not None:
                        current = float(quantity.value)
                        budgets[key] = min(budgets.get(key, current), current)
        double_allocations = sum(max(0, count - 1) for count in devices.values())
        overcommits = sum(
            1
            for key, amount in capacities.items()
            if key not in budgets or amount > budgets[key]
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            rows = connection.execute(
                "SELECT * FROM scheduler_cycle_metrics WHERE project_id=? ORDER BY cycle_sequence",
                (project_ref.value,),
            ).fetchall()
            head = connection.execute(
                "SELECT cycle_sequence,record_sha256 FROM scheduler_cycle_metric_heads WHERE project_id=?",
                (project_ref.value,),
            ).fetchone()
            if (not rows and head is not None) or (rows and head is None):
                raise SchedulerIntegrityError("Scheduler cycle metric history and head differ")
            if tuple(cast(int, row["cycle_sequence"]) for row in rows) != tuple(range(1, len(rows) + 1)):
                raise SchedulerIntegrityError("Scheduler cycle metric history is not gap-free")
            max_productive_concurrency = 0
            previous_record_sha256: str | None = None
            for row in rows:
                cycle_id = cast(str, row["cycle_id"])
                cycle_sequence = cast(int, row["cycle_sequence"])
                recorded_previous_sha256 = cast(str | None, row["previous_record_sha256"])
                started_at = cast(str, row["started_at"])
                finished_at = cast(str, row["finished_at"])
                queue_pressure_value = cast(int, row["queue_pressure"])
                concurrency_value = cast(int, row["max_productive_concurrency"])
                try:
                    malformed = (
                        re.fullmatch(r"cyc_[0-9a-f]{32}", cycle_id) is None
                        or recorded_previous_sha256 != previous_record_sha256
                        or queue_pressure_value < 0
                        or concurrency_value < 0
                        or datetime.fromisoformat(_timestamp(finished_at, "finished_at")) < datetime.fromisoformat(_timestamp(started_at, "started_at"))
                        or not hmac.compare_digest(
                            self._cycle_metric_sha(
                                cycle_id,
                                project_ref,
                                cycle_sequence,
                                recorded_previous_sha256,
                                started_at,
                                finished_at,
                                queue_pressure_value,
                                concurrency_value,
                            ),
                            cast(str, row["record_sha256"]),
                        )
                    )
                except (SchedulerContractError, TypeError, ValueError) as exc:
                    raise SchedulerIntegrityError("Scheduler cycle metric evidence is malformed") from exc
                if malformed:
                    raise SchedulerIntegrityError("Scheduler cycle metric evidence changed")
                previous_record_sha256 = cast(str, row["record_sha256"])
                max_productive_concurrency = max(max_productive_concurrency, concurrency_value)
            if rows and (
                head["cycle_sequence"] != rows[-1]["cycle_sequence"]
                or not hmac.compare_digest(cast(str, head["record_sha256"]), cast(str, rows[-1]["record_sha256"]))
            ):
                raise SchedulerIntegrityError("Scheduler cycle metric head differs from history")
            connection.commit()
            return SchedulerMetrics(
                len(allocations),
                queue_pressure,
                max_productive_concurrency,
                exclusive_resource_double_allocations=double_allocations,
                invalid_resource_overcommit=overcommits,
                resource_leaks_after_terminal=resource_leaks,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = [
    "ResourceAllocation", "ResourceAllocationRef", "ResourceClaim", "ResourceReservation",
    "ScheduleCycleResult", "ScheduledDispatch", "Scheduler", "SchedulerFamilyAttachment", "SchedulerAuthorityError",
    "SchedulerConflictError", "SchedulerContractError", "SchedulerError", "SchedulerIntegrityError",
    "SchedulerMetrics", "SchedulerNotFoundError", "SchedulerScopeError", "SchedulingRequest",
    "SchedulerQueueEntry", "SchedulerService",
]


SchedulerService = Scheduler
