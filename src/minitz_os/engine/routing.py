"""Project-scoped capability implementation and current compute routing for P1-09."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .capability import CapabilityIntegrityError, CapabilityRef, CapabilityRegistry
from .graph import GraphIntegrityError, GraphRef, GraphScopeError, GraphService, Node, NodeRef
from .project import ProjectAccess, ProjectIntegrityError, ProjectNotFoundError, ProjectRef, ProjectScopeError, ProjectStore
from .resource import (
    QuantitySource,
    Resource,
    ResourceFit,
    ResourceFitRequest,
    ResourceHealth,
    ResourceIntegrityError,
    ResourceNotFoundError,
    ResourceRef,
    ResourceScopeError,
    ResourceService,
    ResourceSnapshotRef,
    ResourceStaleError,
    evaluateResourceFit,
)
from .run import ExecutionAttempt, RunIntegrityError, RunRef, RunScopeError, RunService
from .scheduler import ResourceClaim, SchedulingRequest
from .task import Task, TaskIntegrityError, TaskNotFoundError, TaskRef, TaskRevisionService, TaskScopeError


_IMPLEMENTATION_ID = re.compile(r"cimpl_[0-9a-f]{32}")
_DECISION_ID = re.compile(r"rdec_[0-9a-f]{32}")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]+")
_SHA = re.compile(r"[0-9a-f]{64}")
_SIDE_EFFECT_LEVEL = {"READ_ONLY": 0, "PROJECT_WRITE": 1, "EXTERNAL_WRITE": 2}
_RANKING_VERSION = "p1.deterministic.v1"


class RoutingError(Exception):
    """Base routing failure."""


class RoutingContractError(RoutingError, ValueError):
    """A routing contract is malformed."""


class RoutingScopeError(RoutingError):
    """A routing operation crossed Project scope."""


class RoutingAuthorityError(RoutingError):
    """Current Task, Run, Graph, Node, or attempt authority is absent."""


class RoutingConflictError(RoutingError):
    """A durable routing identity conflicts with current evidence."""


class RoutingNotFoundError(RoutingError):
    """An exact implementation or decision was not found."""


class RoutingIntegrityError(RoutingError):
    """Persisted routing evidence failed verification."""


class ImplementationKind(str, Enum):
    MODEL = "MODEL"
    TOOL = "TOOL"
    RUNTIME = "RUNTIME"


class RoutingRejectionCode(str, Enum):
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    FEATURE_MISMATCH = "FEATURE_MISMATCH"
    INPUT_FEATURE_MISMATCH = "INPUT_FEATURE_MISMATCH"
    OUTPUT_FEATURE_MISMATCH = "OUTPUT_FEATURE_MISMATCH"
    IMPLEMENTATION_POLICY_DENIED = "IMPLEMENTATION_POLICY_DENIED"
    PROVIDER_DENIED = "PROVIDER_DENIED"
    RUNTIME_DENIED = "RUNTIME_DENIED"
    DATA_POLICY_DENIED = "DATA_POLICY_DENIED"
    EGRESS_POLICY_DENIED = "EGRESS_POLICY_DENIED"
    SIDE_EFFECT_DENIED = "SIDE_EFFECT_DENIED"
    CONTEXT_LIMIT_EXCEEDED = "CONTEXT_LIMIT_EXCEEDED"
    TOOL_LIMIT_EXCEEDED = "TOOL_LIMIT_EXCEEDED"
    RESOURCE_KIND_MISMATCH = "RESOURCE_KIND_MISMATCH"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    RESOURCE_FIT_FAILED = "RESOURCE_FIT_FAILED"
    IMPLEMENTATION_UNHEALTHY = "IMPLEMENTATION_UNHEALTHY"


class RoutingOutcome(str, Enum):
    ROUTED = "ROUTED"
    NO_ELIGIBLE_IMPLEMENTATION = "NO_ELIGIBLE_IMPLEMENTATION"
    RESOURCE_TEMPORARILY_UNAVAILABLE = "RESOURCE_TEMPORARILY_UNAVAILABLE"
    POLICY_DENIED = "POLICY_DENIED"
    IMPLEMENTATION_UNHEALTHY = "IMPLEMENTATION_UNHEALTHY"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _evidence_json(value: object, name: str) -> str:
    try:
        serialized = _json(value)
        parsed = json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise RoutingContractError(f"{name} evidence is not canonical JSON") from exc
    if not isinstance(parsed, dict) or _json(parsed) != serialized:
        raise RoutingContractError(f"{name} evidence must be a canonical object")
    return serialized


def _validate_evidence_json(serialized: object, name: str) -> str:
    if not isinstance(serialized, str):
        raise RoutingContractError(f"{name} evidence must be serialized text")
    try:
        parsed = json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise RoutingContractError(f"{name} evidence is not valid JSON") from exc
    canonical = _evidence_json(parsed, name)
    if not hmac.compare_digest(canonical, serialized):
        raise RoutingContractError(f"{name} evidence is not canonically serialized")
    return canonical


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise RoutingContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RoutingContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RoutingContractError(f"{name} must be timezone-aware")
    return value


def _ref(value: object, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or len(value.encode()) > 1024 or _REF.fullmatch(value) is None:
        raise RoutingContractError(f"{name} must be an exact absolute reference")
    return value


def _texts(values: Sequence[str], name: str, *, refs: bool = False, limit: int = 128) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RoutingContractError(f"{name} must be a sequence")
    copied = tuple(values)
    if len(copied) > limit or len(copied) != len(set(copied)):
        raise RoutingContractError(f"{name} is duplicated or unbounded")
    for value in copied:
        if not isinstance(value, str) or not value or len(value.encode()) > 1024:
            raise RoutingContractError(f"{name} contains malformed text")
        if refs and _REF.fullmatch(value) is None:
            raise RoutingContractError(f"{name} requires exact absolute references")
        if not refs and _NAME.fullmatch(value) is None:
            raise RoutingContractError(f"{name} contains malformed feature identity")
    return tuple(sorted(copied))


def _metadata(values: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(values, Mapping) or len(values) > 128:
        raise RoutingContractError("metadata is malformed or unbounded")
    copied: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or _NAME.fullmatch(key) is None:
            raise RoutingContractError("metadata key is malformed")
        if not isinstance(value, str) or len(value.encode()) > 2048:
            raise RoutingContractError("metadata value is malformed or unbounded")
        copied[key] = value
    return MappingProxyType(dict(sorted(copied.items())))


def _fit_payload(request: ResourceFitRequest) -> dict[str, object]:
    return {
        "maximum_cost": request.maximum_cost,
        "maximum_pressure": dict(request.maximum_pressure),
        "reduced_available": dict(request.reduced_available),
        "reduced_device_available": dict(request.reduced_device_available),
        "required_artifact_refs": [item.to_payload() for item in request.required_artifact_refs],
        "required_available": dict(request.required_available),
        "required_device_available": dict(request.required_device_available),
        "required_device_features": list(request.required_device_features),
        "required_device_kind": request.required_device_kind,
        "required_effective": dict(request.required_effective),
        "required_installed_tool_refs": list(request.required_installed_tool_refs),
        "required_loaded_model_refs": list(request.required_loaded_model_refs),
        "required_workspace_refs": [item.to_payload() for item in request.required_workspace_refs],
    }


def _fit_from_payload(payload: object) -> ResourceFitRequest:
    from .resource import ResourceArtifactLocality, ResourceWorkspaceLocality

    if not isinstance(payload, dict):
        raise RoutingIntegrityError("Persisted Resource fit request is malformed")
    try:
        return ResourceFitRequest(
            required_effective=cast(dict[str, float], payload["required_effective"]),
            required_available=cast(dict[str, float], payload["required_available"]),
            reduced_available=cast(dict[str, float], payload["reduced_available"]),
            maximum_pressure=cast(dict[str, float], payload["maximum_pressure"]),
            required_device_kind=cast(str | None, payload["required_device_kind"]),
            required_device_features=tuple(cast(list[str], payload["required_device_features"])),
            required_device_available=cast(dict[str, float], payload["required_device_available"]),
            reduced_device_available=cast(dict[str, float], payload["reduced_device_available"]),
            required_loaded_model_refs=tuple(cast(list[str], payload["required_loaded_model_refs"])),
            required_installed_tool_refs=tuple(cast(list[str], payload["required_installed_tool_refs"])),
            required_artifact_refs=tuple(ResourceArtifactLocality.from_payload(item) for item in cast(list[object], payload["required_artifact_refs"])),
            required_workspace_refs=tuple(ResourceWorkspaceLocality.from_payload(item) for item in cast(list[object], payload["required_workspace_refs"])),
            maximum_cost=cast(float | None, payload["maximum_cost"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RoutingIntegrityError("Persisted Resource fit request is malformed") from exc


@dataclass(frozen=True, order=True)
class CapabilityImplementationRef:
    project_ref: ProjectRef
    implementation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.implementation_id, str) or _IMPLEMENTATION_ID.fullmatch(self.implementation_id) is None:
            raise RoutingContractError("CapabilityImplementation identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "CapabilityImplementationRef":
        return cls(project_ref, f"cimpl_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"capability-implementation://{self.project_ref.value}/{self.implementation_id}"


@dataclass(frozen=True)
class CapabilityImplementation:
    implementation_ref: CapabilityImplementationRef
    capability_ref: CapabilityRef
    implementation_version: str
    implementation_kind: ImplementationKind
    adapter_ref: str
    runtime_ref: str
    provider_ref: str | None = None
    model_ref: str | None = None
    tool_ref: str | None = None
    features: tuple[str, ...] = ()
    input_features: tuple[str, ...] = ()
    output_features: tuple[str, ...] = ()
    side_effect_authority: str = "READ_ONLY"
    supported_data_policy_refs: tuple[str, ...] = ()
    remote_egress: bool = False
    supported_egress_policy_refs: tuple[str, ...] = ()
    maximum_context_tokens: int | None = None
    maximum_tool_count: int | None = None
    resource_kinds: tuple[str, ...] = ()
    resource_fit: ResourceFitRequest = field(default_factory=ResourceFitRequest)
    declared_priority: int = 0
    latency_hint_ms: float | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.implementation_ref, CapabilityImplementationRef):
            raise TypeError("implementation_ref must be CapabilityImplementationRef")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        if not isinstance(self.implementation_version, str) or _VERSION.fullmatch(self.implementation_version) is None:
            raise RoutingContractError("implementation_version must be semantic numeric version")
        if not isinstance(self.implementation_kind, ImplementationKind):
            raise RoutingContractError("implementation_kind is malformed")
        _ref(self.adapter_ref, "adapter_ref")
        _ref(self.runtime_ref, "runtime_ref")
        _ref(self.provider_ref, "provider_ref", optional=True)
        _ref(self.model_ref, "model_ref", optional=True)
        _ref(self.tool_ref, "tool_ref", optional=True)
        if self.implementation_kind is ImplementationKind.MODEL and (self.model_ref is None or self.tool_ref is not None):
            raise RoutingContractError("MODEL implementation requires only model_ref")
        if self.implementation_kind is ImplementationKind.TOOL and (self.tool_ref is None or self.model_ref is not None):
            raise RoutingContractError("TOOL implementation requires only tool_ref")
        if self.implementation_kind is ImplementationKind.RUNTIME and (self.model_ref is not None or self.tool_ref is not None):
            raise RoutingContractError("RUNTIME implementation cannot bind model or tool identity")
        object.__setattr__(self, "features", _texts(self.features, "features"))
        object.__setattr__(self, "input_features", _texts(self.input_features, "input_features"))
        object.__setattr__(self, "output_features", _texts(self.output_features, "output_features"))
        if self.side_effect_authority not in _SIDE_EFFECT_LEVEL:
            raise RoutingContractError("side_effect_authority is malformed")
        object.__setattr__(self, "supported_data_policy_refs", _texts(self.supported_data_policy_refs, "supported_data_policy_refs", refs=True))
        object.__setattr__(self, "supported_egress_policy_refs", _texts(self.supported_egress_policy_refs, "supported_egress_policy_refs", refs=True))
        if not isinstance(self.remote_egress, bool):
            raise RoutingContractError("remote_egress must be boolean")
        for value, name in ((self.maximum_context_tokens, "maximum_context_tokens"), (self.maximum_tool_count, "maximum_tool_count")):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise RoutingContractError(f"{name} is invalid")
        object.__setattr__(self, "resource_kinds", _texts(self.resource_kinds, "resource_kinds"))
        if not self.resource_kinds or not isinstance(self.resource_fit, ResourceFitRequest):
            raise RoutingContractError("implementation requires resource kinds and exact fit")
        if isinstance(self.declared_priority, bool) or not isinstance(self.declared_priority, int) or not -1000 <= self.declared_priority <= 1000:
            raise RoutingContractError("declared_priority is invalid")
        if self.latency_hint_ms is not None and (isinstance(self.latency_hint_ms, bool) or not isinstance(self.latency_hint_ms, (int, float)) or not math.isfinite(float(self.latency_hint_ms)) or self.latency_hint_ms < 0):
            raise RoutingContractError("latency_hint_ms is invalid")
        object.__setattr__(self, "metadata", _metadata(self.metadata))
        _timestamp(self.created_at, "created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.implementation_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "capability_ref": self.capability_ref.value,
            "created_at": self.created_at,
            "declared_priority": self.declared_priority,
            "features": list(self.features),
            "implementation_kind": self.implementation_kind.value,
            "implementation_ref": self.implementation_ref.value,
            "implementation_version": self.implementation_version,
            "input_features": list(self.input_features),
            "latency_hint_ms": self.latency_hint_ms,
            "maximum_context_tokens": self.maximum_context_tokens,
            "maximum_tool_count": self.maximum_tool_count,
            "metadata": dict(self.metadata),
            "model_ref": self.model_ref,
            "output_features": list(self.output_features),
            "provider_ref": self.provider_ref,
            "remote_egress": self.remote_egress,
            "resource_fit": _fit_payload(self.resource_fit),
            "resource_kinds": list(self.resource_kinds),
            "runtime_ref": self.runtime_ref,
            "side_effect_authority": self.side_effect_authority,
            "supported_data_policy_refs": list(self.supported_data_policy_refs),
            "supported_egress_policy_refs": list(self.supported_egress_policy_refs),
            "tool_ref": self.tool_ref,
        }

    @classmethod
    def from_payload(cls, project_ref: ProjectRef, payload: object) -> "CapabilityImplementation":
        if not isinstance(payload, dict):
            raise RoutingIntegrityError("Persisted CapabilityImplementation is malformed")
        try:
            prefix = f"capability-implementation://{project_ref.value}/"
            implementation_value = cast(str, payload["implementation_ref"])
            if not implementation_value.startswith(prefix):
                raise RoutingScopeError("Persisted CapabilityImplementation crossed Project scope")
            capability_value = cast(str, payload["capability_ref"])
            capability_id, version = capability_value.rsplit("@", 1)
            return cls(
                CapabilityImplementationRef(project_ref, implementation_value.removeprefix(prefix)),
                CapabilityRef(capability_id, version),
                cast(str, payload["implementation_version"]),
                ImplementationKind(cast(str, payload["implementation_kind"])),
                cast(str, payload["adapter_ref"]),
                cast(str, payload["runtime_ref"]),
                provider_ref=cast(str | None, payload["provider_ref"]),
                model_ref=cast(str | None, payload["model_ref"]),
                tool_ref=cast(str | None, payload["tool_ref"]),
                features=tuple(cast(list[str], payload["features"])),
                input_features=tuple(cast(list[str], payload["input_features"])),
                output_features=tuple(cast(list[str], payload["output_features"])),
                side_effect_authority=cast(str, payload["side_effect_authority"]),
                supported_data_policy_refs=tuple(cast(list[str], payload["supported_data_policy_refs"])),
                remote_egress=cast(bool, payload["remote_egress"]),
                supported_egress_policy_refs=tuple(cast(list[str], payload["supported_egress_policy_refs"])),
                maximum_context_tokens=cast(int | None, payload["maximum_context_tokens"]),
                maximum_tool_count=cast(int | None, payload["maximum_tool_count"]),
                resource_kinds=tuple(cast(list[str], payload["resource_kinds"])),
                resource_fit=_fit_from_payload(payload["resource_fit"]),
                declared_priority=cast(int, payload["declared_priority"]),
                latency_hint_ms=cast(float | None, payload["latency_hint_ms"]),
                metadata=cast(dict[str, str], payload["metadata"]),
                created_at=cast(str, payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RoutingIntegrityError("Persisted CapabilityImplementation is malformed") from exc


@dataclass(frozen=True)
class RoutingPolicy:
    project_ref: ProjectRef
    policy_ref: str
    allow_remote_egress: bool = False
    allowed_implementation_refs: tuple[CapabilityImplementationRef, ...] = ()
    denied_implementation_refs: tuple[CapabilityImplementationRef, ...] = ()
    allowed_provider_refs: tuple[str, ...] = ()
    denied_provider_refs: tuple[str, ...] = ()
    allowed_runtime_refs: tuple[str, ...] = ()
    permitted_data_policy_refs: tuple[str, ...] = ()
    permitted_egress_policy_refs: tuple[str, ...] = ()
    preferred_implementation_refs: tuple[CapabilityImplementationRef, ...] = ()
    maximum_context_tokens: int | None = None
    maximum_tool_count: int | None = None
    policy_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        _ref(self.policy_ref, "policy_ref")
        if not isinstance(self.allow_remote_egress, bool):
            raise RoutingContractError("allow_remote_egress must be boolean")
        for name in ("allowed_implementation_refs", "denied_implementation_refs", "preferred_implementation_refs"):
            values = cast(tuple[CapabilityImplementationRef, ...], getattr(self, name))
            if not isinstance(values, tuple) or len(values) != len(set(values)) or any(not isinstance(item, CapabilityImplementationRef) or item.project_ref != self.project_ref for item in values):
                raise RoutingScopeError(f"{name} is invalid or crossed Project scope")
        object.__setattr__(self, "allowed_provider_refs", _texts(self.allowed_provider_refs, "allowed_provider_refs", refs=True))
        object.__setattr__(self, "denied_provider_refs", _texts(self.denied_provider_refs, "denied_provider_refs", refs=True))
        object.__setattr__(self, "allowed_runtime_refs", _texts(self.allowed_runtime_refs, "allowed_runtime_refs", refs=True))
        object.__setattr__(self, "permitted_data_policy_refs", _texts(self.permitted_data_policy_refs, "permitted_data_policy_refs", refs=True))
        object.__setattr__(self, "permitted_egress_policy_refs", _texts(self.permitted_egress_policy_refs, "permitted_egress_policy_refs", refs=True))
        for value, name in ((self.maximum_context_tokens, "maximum_context_tokens"), (self.maximum_tool_count, "maximum_tool_count")):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise RoutingContractError(f"{name} is invalid")
        object.__setattr__(self, "policy_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "allow_remote_egress": self.allow_remote_egress,
            "allowed_implementation_refs": [item.value for item in self.allowed_implementation_refs],
            "allowed_provider_refs": list(self.allowed_provider_refs),
            "allowed_runtime_refs": list(self.allowed_runtime_refs),
            "denied_implementation_refs": [item.value for item in self.denied_implementation_refs],
            "denied_provider_refs": list(self.denied_provider_refs),
            "maximum_context_tokens": self.maximum_context_tokens,
            "maximum_tool_count": self.maximum_tool_count,
            "permitted_data_policy_refs": list(self.permitted_data_policy_refs),
            "permitted_egress_policy_refs": list(self.permitted_egress_policy_refs),
            "policy_ref": self.policy_ref,
            "preferred_implementation_refs": [item.value for item in self.preferred_implementation_refs],
            "project_ref": self.project_ref.value,
        }

    @classmethod
    def from_evidence(cls, project_ref: ProjectRef, payload: object) -> "RoutingPolicy":
        required = {
            "allow_remote_egress", "allowed_implementation_refs", "allowed_provider_refs",
            "allowed_runtime_refs", "denied_implementation_refs", "denied_provider_refs",
            "maximum_context_tokens", "maximum_tool_count", "permitted_data_policy_refs",
            "permitted_egress_policy_refs", "policy_ref", "preferred_implementation_refs",
            "project_ref",
        }
        if not isinstance(payload, dict) or set(payload) != required or payload.get("project_ref") != project_ref.value:
            raise RoutingIntegrityError("Persisted RoutingPolicy evidence schema is malformed")
        prefix = f"capability-implementation://{project_ref.value}/"

        def implementation_refs(name: str) -> tuple[CapabilityImplementationRef, ...]:
            values = payload[name]
            if not isinstance(values, list) or any(not isinstance(value, str) or not value.startswith(prefix) for value in values):
                raise RoutingIntegrityError(f"Persisted RoutingPolicy {name} is malformed")
            return tuple(CapabilityImplementationRef(project_ref, value.removeprefix(prefix)) for value in values)

        try:
            policy = cls(
                project_ref,
                cast(str, payload["policy_ref"]),
                allow_remote_egress=cast(bool, payload["allow_remote_egress"]),
                allowed_implementation_refs=implementation_refs("allowed_implementation_refs"),
                denied_implementation_refs=implementation_refs("denied_implementation_refs"),
                allowed_provider_refs=tuple(cast(list[str], payload["allowed_provider_refs"])),
                denied_provider_refs=tuple(cast(list[str], payload["denied_provider_refs"])),
                allowed_runtime_refs=tuple(cast(list[str], payload["allowed_runtime_refs"])),
                permitted_data_policy_refs=tuple(cast(list[str], payload["permitted_data_policy_refs"])),
                permitted_egress_policy_refs=tuple(cast(list[str], payload["permitted_egress_policy_refs"])),
                preferred_implementation_refs=implementation_refs("preferred_implementation_refs"),
                maximum_context_tokens=cast(int | None, payload["maximum_context_tokens"]),
                maximum_tool_count=cast(int | None, payload["maximum_tool_count"]),
            )
        except (KeyError, TypeError, ValueError, RoutingError) as exc:
            if isinstance(exc, RoutingIntegrityError):
                raise
            raise RoutingIntegrityError("Persisted RoutingPolicy evidence is malformed") from exc
        if _json(policy.payload()) != _json(payload):
            raise RoutingIntegrityError("Persisted RoutingPolicy evidence is not exact")
        return policy


@dataclass(frozen=True)
class RoutingRequest:
    task_ref: TaskRef
    node_ref: NodeRef
    capability_ref: CapabilityRef
    authority_attempt: ExecutionAttempt
    policy: RoutingPolicy
    resource_refs: tuple[ResourceRef, ...]
    required_features: tuple[str, ...] = ()
    required_input_features: tuple[str, ...] = ()
    required_output_features: tuple[str, ...] = ()
    context_tokens: int = 0
    tool_count: int = 0
    allow_reduced_fit: bool = False
    idempotency_key: str = "route"
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.task_ref, TaskRef) or not isinstance(self.node_ref, NodeRef) or not isinstance(self.capability_ref, CapabilityRef):
            raise RoutingContractError("RoutingRequest requires exact Task, Node, and Capability refs")
        if not isinstance(self.authority_attempt, ExecutionAttempt) or not isinstance(self.policy, RoutingPolicy):
            raise RoutingContractError("RoutingRequest requires exact Run authority and policy")
        project_ref = self.task_ref.project_ref
        if self.node_ref.project_ref != project_ref or self.authority_attempt.run_ref.project_ref != project_ref or self.policy.project_ref != project_ref:
            raise RoutingScopeError("RoutingRequest crossed Project scope")
        if not isinstance(self.resource_refs, tuple) or len(self.resource_refs) > 256 or len(self.resource_refs) != len(set(self.resource_refs)) or any(not isinstance(item, ResourceRef) or item.project_ref != project_ref for item in self.resource_refs):
            raise RoutingScopeError("RoutingRequest Resource scope is invalid")
        object.__setattr__(self, "resource_refs", tuple(sorted(self.resource_refs, key=lambda item: item.value)))
        object.__setattr__(self, "required_features", _texts(self.required_features, "required_features"))
        object.__setattr__(self, "required_input_features", _texts(self.required_input_features, "required_input_features"))
        object.__setattr__(self, "required_output_features", _texts(self.required_output_features, "required_output_features"))
        for value, name in ((self.context_tokens, "context_tokens"), (self.tool_count, "tool_count")):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RoutingContractError(f"{name} is invalid")
        if not isinstance(self.allow_reduced_fit, bool) or not isinstance(self.idempotency_key, str) or _KEY.fullmatch(self.idempotency_key) is None:
            raise RoutingContractError("RoutingRequest reduced-fit or idempotency contract is malformed")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.task_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "allow_reduced_fit": self.allow_reduced_fit,
            "authority_attempt": self.authority_attempt.record_sha256,
            "capability_ref": self.capability_ref.value,
            "context_tokens": self.context_tokens,
            "node_ref": self.node_ref.value,
            "policy_sha256": self.policy.policy_sha256,
            "required_features": list(self.required_features),
            "required_input_features": list(self.required_input_features),
            "required_output_features": list(self.required_output_features),
            "resource_refs": [item.value for item in self.resource_refs],
            "task_ref": f"task://{self.project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}",
            "tool_count": self.tool_count,
        }

    @classmethod
    def from_evidence(
        cls,
        payload: object,
        *,
        task_ref: TaskRef,
        node_ref: NodeRef,
        capability_ref: CapabilityRef,
        authority_attempt: ExecutionAttempt,
        policy: RoutingPolicy,
    ) -> "RoutingRequest":
        required = {
            "allow_reduced_fit", "authority_attempt", "capability_ref", "context_tokens",
            "node_ref", "policy_sha256", "required_features", "required_input_features",
            "required_output_features", "resource_refs", "task_ref", "tool_count",
        }
        project_ref = task_ref.project_ref
        if not isinstance(payload, dict) or set(payload) != required:
            raise RoutingIntegrityError("Persisted RoutingRequest evidence schema is malformed")
        resource_prefix = f"resource://{project_ref.value}/"
        resources = payload.get("resource_refs")
        if not isinstance(resources, list) or any(not isinstance(value, str) or not value.startswith(resource_prefix) for value in resources):
            raise RoutingIntegrityError("Persisted RoutingRequest Resource evidence is malformed")
        try:
            request = cls(
                task_ref,
                node_ref,
                capability_ref,
                authority_attempt,
                policy,
                tuple(ResourceRef(project_ref, value.removeprefix(resource_prefix)) for value in resources),
                required_features=tuple(cast(list[str], payload["required_features"])),
                required_input_features=tuple(cast(list[str], payload["required_input_features"])),
                required_output_features=tuple(cast(list[str], payload["required_output_features"])),
                context_tokens=cast(int, payload["context_tokens"]),
                tool_count=cast(int, payload["tool_count"]),
                allow_reduced_fit=cast(bool, payload["allow_reduced_fit"]),
                idempotency_key="receipt-readback",
            )
        except (KeyError, TypeError, ValueError, RoutingError) as exc:
            if isinstance(exc, RoutingIntegrityError):
                raise
            raise RoutingIntegrityError("Persisted RoutingRequest evidence is malformed") from exc
        if _json(request.payload()) != _json(payload):
            raise RoutingIntegrityError("Persisted RoutingRequest evidence is not exact")
        return request


@dataclass(frozen=True, order=True)
class RoutingRejection:
    code: RoutingRejectionCode
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, RoutingRejectionCode) or not isinstance(self.detail, str) or not self.detail or len(self.detail.encode()) > 2048:
            raise RoutingContractError("Routing rejection is malformed or unbounded")

    def payload(self) -> dict[str, str]:
        return {"code": self.code.value, "detail": self.detail}


@dataclass(frozen=True)
class ImplementationResolution:
    implementation: CapabilityImplementation
    rejections: tuple[RoutingRejection, ...]
    preference_rank: int

    @property
    def eligible(self) -> bool:
        return not self.rejections


@dataclass(frozen=True)
class ComputePlacement:
    resource_ref: ResourceRef
    snapshot_ref: ResourceSnapshotRef | None
    snapshot_record_sha256: str | None
    fit_classification: str | None
    rejections: tuple[RoutingRejection, ...]
    ranking_factors: Mapping[str, str]

    @property
    def eligible(self) -> bool:
        return not self.rejections and self.snapshot_ref is not None


@dataclass(frozen=True)
class RoutingCandidate:
    implementation_ref: CapabilityImplementationRef
    implementation_record_sha256: str
    resource_ref: ResourceRef | None
    snapshot_ref: ResourceSnapshotRef | None
    snapshot_record_sha256: str | None
    rejections: tuple[RoutingRejection, ...]
    ranking_factors: Mapping[str, str]
    candidate_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if _SHA.fullmatch(self.implementation_record_sha256) is None:
            raise RoutingContractError("Implementation evidence digest is malformed")
        if self.resource_ref is not None and self.resource_ref.project_ref != self.implementation_ref.project_ref:
            raise RoutingScopeError("Routing candidate crossed Project scope")
        if (self.snapshot_ref is None) != (self.snapshot_record_sha256 is None):
            raise RoutingContractError("Routing candidate snapshot evidence is incomplete")
        if self.snapshot_ref is not None and (self.resource_ref != self.snapshot_ref.resource_ref or _SHA.fullmatch(cast(str, self.snapshot_record_sha256)) is None):
            raise RoutingContractError("Routing candidate snapshot evidence differs")
        if not isinstance(self.rejections, tuple) or not all(isinstance(item, RoutingRejection) for item in self.rejections):
            raise RoutingContractError("Routing candidate rejections are malformed")
        if not isinstance(self.ranking_factors, Mapping) or len(self.ranking_factors) > 32:
            raise RoutingContractError("Routing ranking factors are malformed")
        factors: dict[str, str] = {}
        for key, value in self.ranking_factors.items():
            if not isinstance(key, str) or _NAME.fullmatch(key) is None or not isinstance(value, str) or len(value.encode()) > 512:
                raise RoutingContractError("Routing ranking factor is malformed")
            factors[key] = value
        object.__setattr__(self, "ranking_factors", MappingProxyType(dict(sorted(factors.items()))))
        object.__setattr__(self, "candidate_sha256", _digest(self.payload()))

    @property
    def eligible(self) -> bool:
        return not self.rejections and self.resource_ref is not None and self.snapshot_ref is not None

    def payload(self) -> dict[str, object]:
        return {
            "implementation_record_sha256": self.implementation_record_sha256,
            "implementation_ref": self.implementation_ref.value,
            "ranking_factors": dict(self.ranking_factors),
            "rejections": [item.payload() for item in self.rejections],
            "resource_ref": None if self.resource_ref is None else self.resource_ref.value,
            "snapshot_record_sha256": self.snapshot_record_sha256,
            "snapshot_ref": None if self.snapshot_ref is None else self.snapshot_ref.value,
        }


@dataclass(frozen=True, order=True)
class RoutingDecisionRef:
    project_ref: ProjectRef
    decision_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.decision_id, str) or _DECISION_ID.fullmatch(self.decision_id) is None:
            raise RoutingContractError("RoutingDecision identity is malformed")

    @property
    def value(self) -> str:
        return f"routing-decision://{self.project_ref.value}/{self.decision_id}"


@dataclass(frozen=True)
class RoutingDecision:
    decision_ref: RoutingDecisionRef
    task_ref: TaskRef
    task_digest: str
    node_ref: NodeRef
    run_id: str
    run_attempt_id: str
    run_attempt_fence: int
    capability_ref: CapabilityRef
    capability_record_sha256: str
    request_sha256: str
    policy_sha256: str
    request_evidence_json: str
    policy_evidence_json: str
    candidates: tuple[RoutingCandidate, ...]
    selected_implementation_ref: CapabilityImplementationRef | None
    selected_resource_ref: ResourceRef | None
    selected_snapshot_ref: ResourceSnapshotRef | None
    selected_snapshot_record_sha256: str | None
    outcome: RoutingOutcome
    ranking_version: str
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project_ref = self.decision_ref.project_ref
        if self.task_ref.project_ref != project_ref or self.node_ref.project_ref != project_ref:
            raise RoutingScopeError("RoutingDecision crossed Project scope")
        for value in (self.task_digest, self.capability_record_sha256, self.request_sha256, self.policy_sha256):
            if _SHA.fullmatch(value) is None:
                raise RoutingContractError("RoutingDecision digest is malformed")
        request_json = _validate_evidence_json(self.request_evidence_json, "RoutingRequest")
        policy_json = _validate_evidence_json(self.policy_evidence_json, "RoutingPolicy")
        request_evidence = cast(dict[str, object], json.loads(request_json))
        policy_evidence = cast(dict[str, object], json.loads(policy_json))
        if not hmac.compare_digest(_digest(request_evidence), self.request_sha256) or not hmac.compare_digest(_digest(policy_evidence), self.policy_sha256):
            raise RoutingIntegrityError("RoutingDecision request or policy evidence digest differs")
        if (
            request_evidence.get("task_ref") != f"task://{project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}"
            or request_evidence.get("node_ref") != self.node_ref.value
            or request_evidence.get("capability_ref") != self.capability_ref.value
            or request_evidence.get("policy_sha256") != self.policy_sha256
            or policy_evidence.get("project_ref") != project_ref.value
        ):
            raise RoutingIntegrityError("RoutingDecision evidence identities differ from the receipt")
        if not isinstance(self.run_id, str) or not self.run_id.startswith("run_") or not isinstance(self.run_attempt_id, str) or not self.run_attempt_id.startswith("att_") or self.run_attempt_fence < 1:
            raise RoutingContractError("RoutingDecision Run authority is malformed")
        if not isinstance(self.candidates, tuple) or len(self.candidates) > 4096:
            raise RoutingContractError("RoutingDecision requires bounded candidate evidence")
        if self.outcome is RoutingOutcome.ROUTED:
            if self.selected_implementation_ref is None or self.selected_resource_ref is None or self.selected_snapshot_ref is None or self.selected_snapshot_record_sha256 is None:
                raise RoutingContractError("Routed decision requires separate implementation and compute selection")
            if not any(item.eligible and item.implementation_ref == self.selected_implementation_ref and item.resource_ref == self.selected_resource_ref and item.snapshot_ref == self.selected_snapshot_ref for item in self.candidates):
                raise RoutingIntegrityError("RoutingDecision selection is not an eligible candidate")
        elif any(value is not None for value in (self.selected_implementation_ref, self.selected_resource_ref, self.selected_snapshot_ref, self.selected_snapshot_record_sha256)):
            raise RoutingContractError("No-route decision cannot contain a selection")
        if self.ranking_version != _RANKING_VERSION:
            raise RoutingContractError("Routing ranking version is unsupported")
        _timestamp(self.created_at, "created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.decision_ref.project_ref

    @property
    def request_evidence(self) -> Mapping[str, object]:
        return MappingProxyType(cast(dict[str, object], json.loads(self.request_evidence_json)))

    @property
    def policy_evidence(self) -> Mapping[str, object]:
        return MappingProxyType(cast(dict[str, object], json.loads(self.policy_evidence_json)))

    def payload(self) -> dict[str, object]:
        return {
            "candidates": [item.candidate_sha256 for item in self.candidates],
            "capability_ref": self.capability_ref.value,
            "capability_record_sha256": self.capability_record_sha256,
            "created_at": self.created_at,
            "decision_ref": self.decision_ref.value,
            "node_ref": self.node_ref.value,
            "outcome": self.outcome.value,
            "policy_sha256": self.policy_sha256,
            "policy_evidence_json": self.policy_evidence_json,
            "ranking_version": self.ranking_version,
            "request_sha256": self.request_sha256,
            "request_evidence_json": self.request_evidence_json,
            "run_attempt_fence": self.run_attempt_fence,
            "run_attempt_id": self.run_attempt_id,
            "run_id": self.run_id,
            "selected_implementation_ref": None if self.selected_implementation_ref is None else self.selected_implementation_ref.value,
            "selected_resource_ref": None if self.selected_resource_ref is None else self.selected_resource_ref.value,
            "selected_snapshot_record_sha256": self.selected_snapshot_record_sha256,
            "selected_snapshot_ref": None if self.selected_snapshot_ref is None else self.selected_snapshot_ref.value,
            "task_digest": self.task_digest,
            "task_ref": f"task://{self.project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}",
        }


class CapabilityImplementationRegistry:
    """Immutable Project-scoped registry separate from semantic Capability."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self._initialize_schema()

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
                CREATE TABLE IF NOT EXISTS capability_implementations (
                    project_id TEXT NOT NULL, implementation_id TEXT NOT NULL,
                    capability_id TEXT NOT NULL, capability_version TEXT NOT NULL,
                    implementation_version TEXT NOT NULL, implementation_kind TEXT NOT NULL,
                    implementation_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, implementation_id),
                    UNIQUE (project_id, implementation_id, record_sha256),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                    FOREIGN KEY (capability_id, capability_version)
                      REFERENCES capabilities(capability_id, version) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS capability_implementation_idempotency (
                    project_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    semantic_sha256 TEXT NOT NULL, implementation_id TEXT NOT NULL,
                    PRIMARY KEY (project_id, idempotency_key),
                    UNIQUE (project_id, implementation_id),
                    FOREIGN KEY (project_id, implementation_id)
                      REFERENCES capability_implementations(project_id, implementation_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS capability_implementation_registry_entries (
                    project_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    implementation_id TEXT NOT NULL, implementation_record_sha256 TEXT NOT NULL,
                    previous_entry_sha256 TEXT, created_at TEXT NOT NULL, entry_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, sequence),
                    UNIQUE (project_id, sequence, entry_sha256),
                    UNIQUE (project_id, implementation_id),
                    FOREIGN KEY (project_id, implementation_id, implementation_record_sha256)
                      REFERENCES capability_implementations(project_id, implementation_id, record_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS capability_implementation_registry_heads (
                    project_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL,
                    entry_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL, head_sha256 TEXT NOT NULL,
                    FOREIGN KEY (project_id, sequence, entry_sha256)
                      REFERENCES capability_implementation_registry_entries(project_id, sequence, entry_sha256)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS capability_implementation_registry_anchors (
                    project_id TEXT PRIMARY KEY, anchor_sha256 TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS capability_implementations_no_update BEFORE UPDATE ON capability_implementations
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation records are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementations_no_delete BEFORE DELETE ON capability_implementations
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_idempotency_no_update BEFORE UPDATE ON capability_implementation_idempotency
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation idempotency is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_idempotency_no_delete BEFORE DELETE ON capability_implementation_idempotency
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation idempotency cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_registry_entries_no_update BEFORE UPDATE ON capability_implementation_registry_entries
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation registry history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_registry_entries_no_delete BEFORE DELETE ON capability_implementation_registry_entries
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation registry history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_registry_heads_no_delete BEFORE DELETE ON capability_implementation_registry_heads
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation registry head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_registry_heads_monotonic BEFORE UPDATE ON capability_implementation_registry_heads
                  WHEN NEW.project_id != OLD.project_id
                    OR NEW.sequence != OLD.sequence + 1
                    OR NOT EXISTS (
                      SELECT 1 FROM capability_implementation_registry_entries AS entry
                      WHERE entry.project_id=NEW.project_id AND entry.sequence=NEW.sequence
                        AND entry.entry_sha256=NEW.entry_sha256
                        AND entry.previous_entry_sha256=OLD.entry_sha256
                        AND entry.created_at=NEW.updated_at
                    )
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation registry head must advance by one verified entry'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_registry_anchors_no_update BEFORE UPDATE ON capability_implementation_registry_anchors
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation registry anchor is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS capability_implementation_registry_anchors_no_delete BEFORE DELETE ON capability_implementation_registry_anchors
                  BEGIN SELECT RAISE(ABORT, 'CapabilityImplementation registry anchor cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise RoutingIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise RoutingScopeError("CapabilityImplementation Project scope mismatch") from exc

    @staticmethod
    def _entry_sha256(
        project_ref: ProjectRef,
        sequence: int,
        implementation_ref: CapabilityImplementationRef,
        implementation_record_sha256: str,
        previous_entry_sha256: str | None,
        created_at: str,
    ) -> str:
        return _digest(
            {
                "created_at": created_at,
                "implementation_record_sha256": implementation_record_sha256,
                "implementation_ref": implementation_ref.value,
                "previous_entry_sha256": previous_entry_sha256,
                "project_ref": project_ref.value,
                "sequence": sequence,
            }
        )

    @staticmethod
    def _head_sha256(project_ref: ProjectRef, sequence: int, entry_sha256: str, updated_at: str) -> str:
        return _digest(
            {
                "entry_sha256": entry_sha256,
                "project_ref": project_ref.value,
                "sequence": sequence,
                "updated_at": updated_at,
            }
        )

    @staticmethod
    def _anchor_sha256(project_ref: ProjectRef) -> str:
        return _digest(
            {
                "kind": "capability-implementation-registry",
                "project_ref": project_ref.value,
                "schema_version": 1,
            }
        )

    def _ensure_registry_anchor(self, connection: sqlite3.Connection, project_ref: ProjectRef) -> None:
        expected = self._anchor_sha256(project_ref)
        row = connection.execute(
            "SELECT anchor_sha256 FROM capability_implementation_registry_anchors WHERE project_id=?",
            (project_ref.value,),
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO capability_implementation_registry_anchors(project_id,anchor_sha256) VALUES (?,?)",
                (project_ref.value, expected),
            )
        elif not hmac.compare_digest(cast(str, row["anchor_sha256"]), expected):
            raise RoutingIntegrityError("CapabilityImplementation registry Project anchor changed")

    def _verify_registry(self, connection: sqlite3.Connection, project_ref: ProjectRef) -> None:
        entries = connection.execute(
            "SELECT * FROM capability_implementation_registry_entries WHERE project_id=? ORDER BY sequence",
            (project_ref.value,),
        ).fetchall()
        implementation_rows = connection.execute(
            "SELECT implementation_id,record_sha256 FROM capability_implementations WHERE project_id=? ORDER BY implementation_id",
            (project_ref.value,),
        ).fetchall()
        idempotency_rows = connection.execute(
            "SELECT implementation_id,semantic_sha256 FROM capability_implementation_idempotency WHERE project_id=? ORDER BY implementation_id",
            (project_ref.value,),
        ).fetchall()
        head = connection.execute(
            "SELECT * FROM capability_implementation_registry_heads WHERE project_id=?",
            (project_ref.value,),
        ).fetchone()
        anchor = connection.execute(
            "SELECT anchor_sha256 FROM capability_implementation_registry_anchors WHERE project_id=?",
            (project_ref.value,),
        ).fetchone()
        if not entries:
            if implementation_rows or idempotency_rows or head is not None or anchor is not None:
                raise RoutingIntegrityError("CapabilityImplementation registry history is missing")
            return
        if anchor is None or not hmac.compare_digest(cast(str, anchor["anchor_sha256"]), self._anchor_sha256(project_ref)):
            raise RoutingIntegrityError("CapabilityImplementation registry Project anchor is missing or changed")
        if tuple(cast(int, row["sequence"]) for row in entries) != tuple(range(1, len(entries) + 1)):
            raise RoutingIntegrityError("CapabilityImplementation registry sequence has a gap")
        previous: str | None = None
        entry_identities: dict[str, str] = {}
        for row in entries:
            implementation_ref = CapabilityImplementationRef(project_ref, cast(str, row["implementation_id"]))
            created_at = cast(str, row["created_at"])
            expected = self._entry_sha256(
                project_ref,
                cast(int, row["sequence"]),
                implementation_ref,
                cast(str, row["implementation_record_sha256"]),
                previous,
                created_at,
            )
            if row["previous_entry_sha256"] != previous or not hmac.compare_digest(expected, cast(str, row["entry_sha256"])):
                raise RoutingIntegrityError("CapabilityImplementation registry provenance changed")
            previous = expected
            entry_identities[implementation_ref.implementation_id] = cast(str, row["implementation_record_sha256"])
        implementations = {cast(str, row["implementation_id"]): cast(str, row["record_sha256"]) for row in implementation_rows}
        idempotency = {cast(str, row["implementation_id"]): cast(str, row["semantic_sha256"]) for row in idempotency_rows}
        if entry_identities != implementations or entry_identities != idempotency:
            raise RoutingIntegrityError("CapabilityImplementation registry identity sets differ")
        for implementation_id in sorted(implementations):
            self._fetch(connection, CapabilityImplementationRef(project_ref, implementation_id))
        last = entries[-1]
        if head is None or head["sequence"] != last["sequence"] or head["entry_sha256"] != last["entry_sha256"] or head["updated_at"] != last["created_at"]:
            raise RoutingIntegrityError("CapabilityImplementation registry head differs from history")
        expected_head = self._head_sha256(project_ref, cast(int, head["sequence"]), cast(str, head["entry_sha256"]), cast(str, head["updated_at"]))
        if not hmac.compare_digest(expected_head, cast(str, head["head_sha256"])):
            raise RoutingIntegrityError("CapabilityImplementation registry head digest changed")

    def register(self, access: ProjectAccess, implementation: CapabilityImplementation, *, idempotency_key: str) -> CapabilityImplementation:
        if not isinstance(implementation, CapabilityImplementation) or not isinstance(idempotency_key, str) or _KEY.fullmatch(idempotency_key) is None:
            raise RoutingContractError("register requires exact implementation and idempotency identity")
        self._authorize(access, implementation.project_ref)
        self.capabilities.get(implementation.capability_ref)
        semantic = implementation.record_sha256
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._verify_registry(connection, implementation.project_ref)
            self._ensure_registry_anchor(connection, implementation.project_ref)
            prior = connection.execute("SELECT * FROM capability_implementation_idempotency WHERE project_id=? AND idempotency_key=?", (implementation.project_ref.value, idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["semantic_sha256"]), semantic):
                    raise RoutingConflictError("CapabilityImplementation idempotency identity changed")
                value = self._fetch(connection, CapabilityImplementationRef(implementation.project_ref, cast(str, prior["implementation_id"])))
                connection.commit()
                return value
            connection.execute(
                "INSERT INTO capability_implementations VALUES (?,?,?,?,?,?,?,?,?)",
                (implementation.project_ref.value, implementation.implementation_ref.implementation_id, implementation.capability_ref.capability_id, implementation.capability_ref.version, implementation.implementation_version, implementation.implementation_kind.value, _json(implementation.payload()), implementation.created_at, implementation.record_sha256),
            )
            connection.execute("INSERT INTO capability_implementation_idempotency VALUES (?,?,?,?)", (implementation.project_ref.value, idempotency_key, semantic, implementation.implementation_ref.implementation_id))
            head = connection.execute(
                "SELECT * FROM capability_implementation_registry_heads WHERE project_id=?",
                (implementation.project_ref.value,),
            ).fetchone()
            sequence = 1 if head is None else cast(int, head["sequence"]) + 1
            previous_entry_sha256 = None if head is None else cast(str, head["entry_sha256"])
            entry_sha256 = self._entry_sha256(
                implementation.project_ref,
                sequence,
                implementation.implementation_ref,
                implementation.record_sha256,
                previous_entry_sha256,
                implementation.created_at,
            )
            connection.execute(
                "INSERT INTO capability_implementation_registry_entries VALUES (?,?,?,?,?,?,?)",
                (
                    implementation.project_ref.value,
                    sequence,
                    implementation.implementation_ref.implementation_id,
                    implementation.record_sha256,
                    previous_entry_sha256,
                    implementation.created_at,
                    entry_sha256,
                ),
            )
            head_sha256 = self._head_sha256(implementation.project_ref, sequence, entry_sha256, implementation.created_at)
            if head is None:
                connection.execute(
                    "INSERT INTO capability_implementation_registry_heads VALUES (?,?,?,?,?)",
                    (implementation.project_ref.value, sequence, entry_sha256, implementation.created_at, head_sha256),
                )
            else:
                connection.execute(
                    "UPDATE capability_implementation_registry_heads SET sequence=?,entry_sha256=?,updated_at=?,head_sha256=? WHERE project_id=?",
                    (sequence, entry_sha256, implementation.created_at, head_sha256, implementation.project_ref.value),
                )
            self._verify_registry(connection, implementation.project_ref)
            connection.commit()
            return implementation
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RoutingConflictError("CapabilityImplementation registration conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch(self, connection: sqlite3.Connection, ref: CapabilityImplementationRef) -> CapabilityImplementation:
        row = connection.execute("SELECT * FROM capability_implementations WHERE project_id=? AND implementation_id=?", (ref.project_ref.value, ref.implementation_id)).fetchone()
        if row is None:
            raise RoutingNotFoundError("CapabilityImplementation not found")
        implementation = CapabilityImplementation.from_payload(ref.project_ref, json.loads(cast(str, row["implementation_json"])))
        if implementation.implementation_ref != ref or not hmac.compare_digest(implementation.record_sha256, cast(str, row["record_sha256"])) or row["capability_id"] != implementation.capability_ref.capability_id or row["capability_version"] != implementation.capability_ref.version:
            raise RoutingIntegrityError("CapabilityImplementation evidence changed")
        return implementation

    def get(self, access: ProjectAccess, ref: CapabilityImplementationRef) -> CapabilityImplementation:
        self._authorize(access, ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._verify_registry(connection, ref.project_ref)
            value = self._fetch(connection, ref)
            connection.commit()
            return value
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_for_capability(self, access: ProjectAccess, project_ref: ProjectRef, capability_ref: CapabilityRef) -> tuple[CapabilityImplementation, ...]:
        self._authorize(access, project_ref)
        self.capabilities.get(capability_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._verify_registry(connection, project_ref)
            rows = connection.execute("SELECT implementation_id FROM capability_implementations WHERE project_id=? AND capability_id=? AND capability_version=? ORDER BY implementation_id", (project_ref.value, capability_ref.capability_id, capability_ref.version)).fetchall()
            values = tuple(self._fetch(connection, CapabilityImplementationRef(project_ref, cast(str, row["implementation_id"]))) for row in rows)
            connection.commit()
            return values
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class ImplementationResolver:
    """Hard-constraint resolver; ranking never revives rejected implementations."""

    @staticmethod
    def resolve(implementations: Sequence[CapabilityImplementation], task: Task, node: Node, request: RoutingRequest) -> tuple[ImplementationResolution, ...]:
        policy = request.policy
        preferred = {ref: index for index, ref in enumerate(policy.preferred_implementation_refs)}
        resolutions: list[ImplementationResolution] = []
        for implementation in sorted(tuple(implementations), key=lambda item: item.implementation_ref.value):
            rejected: list[RoutingRejection] = []

            def reject(code: RoutingRejectionCode, detail: str) -> None:
                value = RoutingRejection(code, detail)
                if value not in rejected:
                    rejected.append(value)

            if implementation.capability_ref != request.capability_ref:
                reject(RoutingRejectionCode.CAPABILITY_MISMATCH, "exact Capability version differs")
            if not set(request.required_features).issubset(implementation.features):
                reject(RoutingRejectionCode.FEATURE_MISMATCH, "required implementation features are absent")
            if not set(request.required_input_features).issubset(implementation.input_features):
                reject(RoutingRejectionCode.INPUT_FEATURE_MISMATCH, "required input features are absent")
            if not set(request.required_output_features).issubset(implementation.output_features):
                reject(RoutingRejectionCode.OUTPUT_FEATURE_MISMATCH, "required output features are absent")
            if policy.allowed_implementation_refs and implementation.implementation_ref not in policy.allowed_implementation_refs:
                reject(RoutingRejectionCode.IMPLEMENTATION_POLICY_DENIED, "implementation is outside Project allowlist")
            if implementation.implementation_ref in policy.denied_implementation_refs:
                reject(RoutingRejectionCode.IMPLEMENTATION_POLICY_DENIED, "implementation is explicitly denied")
            if policy.allowed_provider_refs and implementation.provider_ref not in policy.allowed_provider_refs:
                reject(RoutingRejectionCode.PROVIDER_DENIED, "provider is outside Project allowlist")
            if implementation.provider_ref in policy.denied_provider_refs:
                reject(RoutingRejectionCode.PROVIDER_DENIED, "provider is explicitly denied")
            if policy.allowed_runtime_refs and implementation.runtime_ref not in policy.allowed_runtime_refs:
                reject(RoutingRejectionCode.RUNTIME_DENIED, "runtime is outside Project allowlist")
            if task.data_policy_ref is not None and (task.data_policy_ref not in implementation.supported_data_policy_refs or (policy.permitted_data_policy_refs and task.data_policy_ref not in policy.permitted_data_policy_refs)):
                reject(RoutingRejectionCode.DATA_POLICY_DENIED, "exact Task data policy is unsupported")
            if implementation.remote_egress and (not policy.allow_remote_egress or task.egress_policy_ref is None or task.egress_policy_ref not in implementation.supported_egress_policy_refs or (policy.permitted_egress_policy_refs and task.egress_policy_ref not in policy.permitted_egress_policy_refs)):
                reject(RoutingRejectionCode.EGRESS_POLICY_DENIED, "remote route lacks exact Task and Project egress authority")
            if _SIDE_EFFECT_LEVEL[implementation.side_effect_authority] > min(_SIDE_EFFECT_LEVEL[task.side_effect_authority], _SIDE_EFFECT_LEVEL[node.side_effect_requirement]):
                reject(RoutingRejectionCode.SIDE_EFFECT_DENIED, "implementation side effects exceed Task or Node authority")
            context_limit = implementation.maximum_context_tokens
            if policy.maximum_context_tokens is not None:
                context_limit = policy.maximum_context_tokens if context_limit is None else min(context_limit, policy.maximum_context_tokens)
            if context_limit is not None and request.context_tokens > context_limit:
                reject(RoutingRejectionCode.CONTEXT_LIMIT_EXCEEDED, "workload context exceeds hard limit")
            tool_limit = implementation.maximum_tool_count
            if policy.maximum_tool_count is not None:
                tool_limit = policy.maximum_tool_count if tool_limit is None else min(tool_limit, policy.maximum_tool_count)
            if tool_limit is not None and request.tool_count > tool_limit:
                reject(RoutingRejectionCode.TOOL_LIMIT_EXCEEDED, "workload tool count exceeds hard limit")
            resolutions.append(ImplementationResolution(implementation, tuple(sorted(rejected)), preferred.get(implementation.implementation_ref, len(preferred) + 1)))
        return tuple(resolutions)


class ComputeResolver:
    """Current Resource placement using only exact ResourceSnapshot evidence."""

    def __init__(self, database_path: str | Path) -> None:
        self.resources = ResourceService(database_path)

    @staticmethod
    def _known_score(values: Mapping[str, object]) -> float:
        total = 0.0
        for value in values.values():
            source = getattr(value, "source_kind", None)
            amount = getattr(value, "value", None)
            if source is QuantitySource.UNKNOWN or amount is None:
                return math.inf
            total += float(amount)
        return total

    def resolve(self, access: ProjectAccess, implementation: CapabilityImplementation, resource_refs: Sequence[ResourceRef], *, allow_reduced_fit: bool) -> tuple[ComputePlacement, ...]:
        placements: list[ComputePlacement] = []
        for resource_ref in sorted(tuple(resource_refs), key=lambda item: item.value):
            rejected: list[RoutingRejection] = []
            snapshot_ref: ResourceSnapshotRef | None = None
            snapshot_sha: str | None = None
            classification: str | None = None
            factors: dict[str, str] = {"resource_tie_breaker": resource_ref.value}
            try:
                resource = self.resources.get_resource(access, resource_ref)
                if resource.resource_kind not in implementation.resource_kinds:
                    rejected.append(RoutingRejection(RoutingRejectionCode.RESOURCE_KIND_MISMATCH, f"resource kind {resource.resource_kind} is incompatible"))
                snapshot = self.resources.latest_snapshot(access, resource_ref, require_fresh=False)
                snapshot_ref = snapshot.snapshot_ref
                snapshot_sha = snapshot.record_sha256
                evaluation = evaluateResourceFit(snapshot, implementation.resource_fit)
                classification = evaluation.classification.value
                if snapshot.health in {ResourceHealth.UNHEALTHY, ResourceHealth.UNKNOWN}:
                    rejected.append(RoutingRejection(RoutingRejectionCode.IMPLEMENTATION_UNHEALTHY, ",".join(evaluation.causes) or f"Resource health is {snapshot.health.value}"))
                elif not snapshot.is_fresh():
                    rejected.append(RoutingRejection(RoutingRejectionCode.RESOURCE_UNAVAILABLE, ",".join(evaluation.causes) or "ResourceSnapshot is stale"))
                elif evaluation.classification is ResourceFit.FIT_REDUCED and not allow_reduced_fit:
                    rejected.append(RoutingRejection(RoutingRejectionCode.RESOURCE_FIT_FAILED, "FIT_REDUCED requires explicit permission"))
                elif evaluation.classification in {ResourceFit.TEMPORARILY_UNAVAILABLE, ResourceFit.UNKNOWN}:
                    rejected.append(RoutingRejection(RoutingRejectionCode.RESOURCE_UNAVAILABLE, ",".join(evaluation.causes) or f"Resource fit is {evaluation.classification.value}"))
                elif evaluation.classification not in {ResourceFit.FIT, ResourceFit.FIT_REDUCED}:
                    rejected.append(RoutingRejection(RoutingRejectionCode.RESOURCE_FIT_FAILED, ",".join(evaluation.causes) or f"Resource fit is {evaluation.classification.value}"))
                pressure_score = self._known_score(cast(Mapping[str, object], snapshot.pressure))
                cost_score = math.inf if snapshot.known_cost.source_kind is QuantitySource.UNKNOWN or snapshot.known_cost.value is None else float(snapshot.known_cost.value)
                locality_hits = sum((len(snapshot.locality.loaded_model_refs), len(snapshot.locality.local_model_refs), len(snapshot.locality.installed_tool_refs), len(snapshot.locality.warm_cache_refs)))
                latency_value = snapshot.observation.runtime_attributes.get("routing.latency_ms")
                try:
                    current_latency = float(latency_value) if latency_value is not None else math.inf
                except ValueError:
                    current_latency = math.inf
                factors.update(
                    {
                        "cost_score": "unknown" if math.isinf(cost_score) else format(cost_score, ".12g"),
                        "current_latency_ms": "unknown" if math.isinf(current_latency) else format(current_latency, ".12g"),
                        "fit_classification": classification,
                        "locality_hits": str(locality_hits),
                        "pressure_score": "unknown" if math.isinf(pressure_score) else format(pressure_score, ".12g"),
                        "snapshot_ref": snapshot.snapshot_ref.value,
                    }
                )
            except ResourceScopeError as exc:
                raise RoutingScopeError("Compute resolution crossed Project scope") from exc
            except ResourceIntegrityError as exc:
                raise RoutingIntegrityError("Compute Resource evidence failed verification") from exc
            except (ResourceNotFoundError, ResourceStaleError) as exc:
                rejected.append(RoutingRejection(RoutingRejectionCode.RESOURCE_UNAVAILABLE, f"{type(exc).__name__}:{exc}"))
            placements.append(ComputePlacement(resource_ref, snapshot_ref, snapshot_sha, classification, tuple(sorted(set(rejected))), MappingProxyType(dict(sorted(factors.items())))))
        return tuple(placements)


class RoutingService:
    """Layered implementation then compute resolution with durable receipts."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.registry = CapabilityImplementationRegistry(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.resources = ResourceService(self.database_path)
        self.implementation_resolver = ImplementationResolver()
        self.compute_resolver = ComputeResolver(self.database_path)
        self._initialize_schema()

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
                CREATE TABLE IF NOT EXISTS routing_decisions (
                    project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
                    task_id TEXT NOT NULL, task_revision INTEGER NOT NULL, task_digest TEXT NOT NULL,
                    run_id TEXT NOT NULL, run_attempt_id TEXT NOT NULL, run_attempt_fence INTEGER NOT NULL,
                    graph_id TEXT NOT NULL, graph_revision INTEGER NOT NULL, node_id TEXT NOT NULL,
                    capability_id TEXT NOT NULL, capability_version TEXT NOT NULL,
                    capability_record_sha256 TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL, policy_sha256 TEXT NOT NULL,
                    request_evidence_json TEXT NOT NULL, policy_evidence_json TEXT NOT NULL,
                    outcome TEXT NOT NULL, selected_implementation_id TEXT,
                    selected_implementation_record_sha256 TEXT, selected_resource_id TEXT,
                    selected_snapshot_id TEXT, selected_snapshot_record_sha256 TEXT,
                    candidate_count INTEGER NOT NULL, ranking_version TEXT NOT NULL,
                    created_at TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, decision_id),
                    UNIQUE (project_id, decision_id, record_sha256),
                    FOREIGN KEY (project_id, task_id, task_revision)
                      REFERENCES task_revisions(project_id, task_id, revision) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id, run_attempt_id, run_attempt_fence)
                      REFERENCES execution_attempts(project_id, run_id, attempt_id, fence) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, node_id)
                      REFERENCES graph_nodes(project_id, graph_id, graph_revision, node_id) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, selected_implementation_id, selected_implementation_record_sha256)
                      REFERENCES capability_implementations(project_id, implementation_id, record_sha256) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, selected_resource_id, selected_snapshot_id, selected_snapshot_record_sha256)
                      REFERENCES resource_snapshots(project_id, resource_id, snapshot_id, record_sha256) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS routing_decision_candidates (
                    project_id TEXT NOT NULL, decision_id TEXT NOT NULL, candidate_index INTEGER NOT NULL,
                    implementation_id TEXT NOT NULL, implementation_record_sha256 TEXT NOT NULL,
                    resource_id TEXT, snapshot_id TEXT, snapshot_record_sha256 TEXT,
                    candidate_json TEXT NOT NULL, candidate_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, decision_id, candidate_index),
                    FOREIGN KEY (project_id, decision_id) REFERENCES routing_decisions(project_id, decision_id) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, implementation_id, implementation_record_sha256)
                      REFERENCES capability_implementations(project_id, implementation_id, record_sha256) ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, resource_id, snapshot_id, snapshot_record_sha256)
                      REFERENCES resource_snapshots(project_id, resource_id, snapshot_id, record_sha256) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS routing_idempotency (
                    project_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL, decision_id TEXT NOT NULL,
                    decision_record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, idempotency_key),
                    UNIQUE (project_id, decision_id),
                    FOREIGN KEY (project_id, decision_id, decision_record_sha256)
                      REFERENCES routing_decisions(project_id, decision_id, record_sha256) ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS routing_decisions_no_update BEFORE UPDATE ON routing_decisions
                  BEGIN SELECT RAISE(ABORT, 'RoutingDecision evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS routing_decisions_no_delete BEFORE DELETE ON routing_decisions
                  BEGIN SELECT RAISE(ABORT, 'RoutingDecision evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS routing_decision_candidates_no_update BEFORE UPDATE ON routing_decision_candidates
                  BEGIN SELECT RAISE(ABORT, 'Routing candidate evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS routing_decision_candidates_no_delete BEFORE DELETE ON routing_decision_candidates
                  BEGIN SELECT RAISE(ABORT, 'Routing candidate evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS routing_idempotency_no_update BEFORE UPDATE ON routing_idempotency
                  BEGIN SELECT RAISE(ABORT, 'Routing idempotency evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS routing_idempotency_no_delete BEFORE DELETE ON routing_idempotency
                  BEGIN SELECT RAISE(ABORT, 'Routing idempotency evidence cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _node(nodes: Sequence[Node], ref: NodeRef) -> Node:
        for node in nodes:
            if node.node_ref == ref:
                return node
        raise RoutingAuthorityError("Routing Node is not in the active Graph")

    @staticmethod
    def _factor_number(value: str | None) -> float:
        if value is None or value == "unknown":
            return math.inf
        try:
            return float(value)
        except ValueError:
            return math.inf

    def _candidate_rank(self, candidate: RoutingCandidate) -> tuple[float, float, float, float, float, float, float, str, str]:
        factors = candidate.ranking_factors
        return (
            self._factor_number(factors.get("project_preference_rank")),
            -self._factor_number(factors.get("declared_priority")),
            self._factor_number(factors.get("fit_rank")),
            self._factor_number(factors.get("pressure_score")),
            self._factor_number(factors.get("cost_score")),
            self._factor_number(factors.get("current_latency_ms")),
            -self._factor_number(factors.get("locality_hits")),
            candidate.implementation_ref.value,
            cast(ResourceRef, candidate.resource_ref).value,
        )

    def route(self, access: ProjectAccess, request: RoutingRequest) -> RoutingDecision:
        if not isinstance(request, RoutingRequest):
            raise RoutingContractError("route requires exact RoutingRequest")
        try:
            self.projects.get_project(access, request.project_ref)
        except ProjectIntegrityError as exc:
            raise RoutingIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise RoutingScopeError("Routing Project scope mismatch") from exc
        try:
            task = self.tasks.get_task(access, request.task_ref)
        except TaskIntegrityError as exc:
            raise RoutingIntegrityError("Routing Task evidence failed verification") from exc
        except TaskScopeError as exc:
            raise RoutingScopeError("Routing Task crossed Project scope") from exc
        except TaskNotFoundError as exc:
            raise RoutingAuthorityError("Routing Task is absent") from exc
        try:
            current_run = self.runs.assert_current_run_authority(access, request.authority_attempt)
        except RunIntegrityError as exc:
            raise RoutingIntegrityError("Routing Run evidence failed verification") from exc
        except RunScopeError as exc:
            raise RoutingScopeError("Routing Run crossed Project scope") from exc
        except Exception as exc:
            raise RoutingAuthorityError("Routing requires current Run authority") from exc
        if current_run.task_ref != task.task_ref or not hmac.compare_digest(current_run.task_digest, task.canonical_digest):
            raise RoutingAuthorityError("Routing Task differs from current Run")
        try:
            graph = self.graphs.get_active_graph(access, current_run.run_ref)
        except GraphIntegrityError as exc:
            raise RoutingIntegrityError("Routing Graph evidence failed verification") from exc
        except GraphScopeError as exc:
            raise RoutingScopeError("Routing Graph crossed Project scope") from exc
        except Exception as exc:
            raise RoutingAuthorityError("Routing requires an active Graph") from exc
        node = self._node(graph.nodes, request.node_ref)
        if request.capability_ref not in task.required_capabilities or request.capability_ref not in node.required_capabilities:
            raise RoutingAuthorityError("Routing Capability is not required by Task and Node")
        try:
            capability = self.registry.capabilities.get(request.capability_ref)
        except CapabilityIntegrityError as exc:
            raise RoutingIntegrityError("Routing Capability evidence failed verification") from exc
        except Exception as exc:
            raise RoutingAuthorityError("Routing Capability is absent") from exc
        capability_record_sha256 = CapabilityRegistry._record_sha256(capability)
        implementations = self.registry.list_for_capability(access, request.project_ref, request.capability_ref)
        resolutions = self.implementation_resolver.resolve(implementations, task, node, request)
        candidates: list[RoutingCandidate] = []
        for resolution in resolutions:
            implementation = resolution.implementation
            common_factors = {
                "declared_priority": str(implementation.declared_priority),
                "implementation_tie_breaker": implementation.implementation_ref.value,
                "latency_hint_ms": "unknown" if implementation.latency_hint_ms is None else format(float(implementation.latency_hint_ms), ".12g"),
                "project_preference_rank": str(resolution.preference_rank),
                "ranking_version": _RANKING_VERSION,
            }
            if not resolution.eligible:
                candidates.append(RoutingCandidate(implementation.implementation_ref, implementation.record_sha256, None, None, None, resolution.rejections, common_factors))
                continue
            placements = self.compute_resolver.resolve(access, implementation, request.resource_refs, allow_reduced_fit=request.allow_reduced_fit)
            if not placements:
                candidates.append(RoutingCandidate(implementation.implementation_ref, implementation.record_sha256, None, None, None, (RoutingRejection(RoutingRejectionCode.RESOURCE_UNAVAILABLE, "no current Resource candidates were supplied"),), common_factors))
                continue
            for placement in placements:
                factors = dict(common_factors)
                factors.update(placement.ranking_factors)
                factors["fit_rank"] = "0" if placement.fit_classification == ResourceFit.FIT.value else "1"
                candidates.append(RoutingCandidate(implementation.implementation_ref, implementation.record_sha256, placement.resource_ref, placement.snapshot_ref, placement.snapshot_record_sha256, placement.rejections, factors))
        eligible = [item for item in candidates if item.eligible]
        if eligible:
            selected = min(eligible, key=self._candidate_rank)
            outcome = RoutingOutcome.ROUTED
            selected_implementation = selected.implementation_ref
            selected_resource = selected.resource_ref
            selected_snapshot = selected.snapshot_ref
            selected_snapshot_sha = selected.snapshot_record_sha256
        else:
            codes = {rejection.code for candidate in candidates for rejection in candidate.rejections}
            if codes and codes.issubset({RoutingRejectionCode.IMPLEMENTATION_POLICY_DENIED, RoutingRejectionCode.PROVIDER_DENIED, RoutingRejectionCode.RUNTIME_DENIED, RoutingRejectionCode.DATA_POLICY_DENIED, RoutingRejectionCode.EGRESS_POLICY_DENIED, RoutingRejectionCode.SIDE_EFFECT_DENIED}):
                outcome = RoutingOutcome.POLICY_DENIED
            elif RoutingRejectionCode.IMPLEMENTATION_UNHEALTHY in codes and codes.issubset({RoutingRejectionCode.IMPLEMENTATION_UNHEALTHY, RoutingRejectionCode.RESOURCE_KIND_MISMATCH}):
                outcome = RoutingOutcome.IMPLEMENTATION_UNHEALTHY
            elif codes.intersection({RoutingRejectionCode.RESOURCE_UNAVAILABLE, RoutingRejectionCode.RESOURCE_FIT_FAILED, RoutingRejectionCode.IMPLEMENTATION_UNHEALTHY, RoutingRejectionCode.RESOURCE_KIND_MISMATCH}):
                outcome = RoutingOutcome.RESOURCE_TEMPORARILY_UNAVAILABLE
            else:
                outcome = RoutingOutcome.NO_ELIGIBLE_IMPLEMENTATION
            selected_implementation = None
            selected_resource = None
            selected_snapshot = None
            selected_snapshot_sha = None
        created_at = _now()
        decision = RoutingDecision(
            RoutingDecisionRef(request.project_ref, f"rdec_{uuid4().hex}"),
            task.task_ref,
            task.canonical_digest,
            node.node_ref,
            current_run.run_ref.run_id,
            request.authority_attempt.attempt_id,
            request.authority_attempt.fence,
            request.capability_ref,
            capability_record_sha256,
            request.request_sha256,
            request.policy.policy_sha256,
            _json(request.payload()),
            _json(request.policy.payload()),
            tuple(candidates),
            selected_implementation,
            selected_resource,
            selected_snapshot,
            selected_snapshot_sha,
            outcome,
            _RANKING_VERSION,
            created_at,
        )
        return self._persist(access, request, decision)

    def _persist(self, access: ProjectAccess, request: RoutingRequest, decision: RoutingDecision) -> RoutingDecision:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute("SELECT * FROM routing_idempotency WHERE project_id=? AND idempotency_key=?", (request.project_ref.value, request.idempotency_key)).fetchone()
            if prior is not None:
                if not hmac.compare_digest(cast(str, prior["request_sha256"]), request.request_sha256):
                    raise RoutingConflictError("Routing idempotency identity changed")
                value = self._fetch(connection, RoutingDecisionRef(request.project_ref, cast(str, prior["decision_id"])))
                connection.commit()
                return value
            try:
                authorized_project = ProjectStore._authorize(connection, access)
                persisted_task = self.tasks._fetch_task(connection, request.task_ref)
                current_run = self.runs.assert_current_run_authority_in_transaction(connection, access, request.authority_attempt)
                current_graph = self.graphs._fetch_graph(connection, request.node_ref.graph_ref)
            except ProjectIntegrityError as exc:
                raise RoutingIntegrityError("Routing persistence Project evidence failed verification") from exc
            except (ProjectNotFoundError, ProjectScopeError, TaskScopeError, RunScopeError, GraphScopeError) as exc:
                raise RoutingScopeError("Routing persistence crossed Project scope") from exc
            except (TaskIntegrityError, RunIntegrityError, GraphIntegrityError) as exc:
                raise RoutingIntegrityError("Routing persistence authority evidence failed verification") from exc
            except Exception as exc:
                raise RoutingAuthorityError("Routing persistence requires current exact authority") from exc
            if authorized_project != request.project_ref:
                raise RoutingScopeError("Routing persistence Project access differs")
            persisted_node = self._node(current_graph.nodes, request.node_ref)
            active_graph = connection.execute(
                "SELECT graph_id,current_graph_revision FROM run_graph_heads WHERE project_id=? AND run_id=?",
                (request.project_ref.value, current_run.run_ref.run_id),
            ).fetchone()
            if (
                active_graph is None
                or active_graph["graph_id"] != request.node_ref.graph_ref.graph_id
                or active_graph["current_graph_revision"] != request.node_ref.graph_ref.revision
                or persisted_task.task_ref != decision.task_ref
                or not hmac.compare_digest(persisted_task.canonical_digest, decision.task_digest)
                or current_run.run_ref.run_id != decision.run_id
                or current_run.task_ref != persisted_task.task_ref
                or not hmac.compare_digest(current_run.task_digest, persisted_task.canonical_digest)
                or current_graph.run_ref != current_run.run_ref
                or persisted_node.node_ref != decision.node_ref
                or request.request_sha256 != decision.request_sha256
                or request.policy.policy_sha256 != decision.policy_sha256
                or _json(request.payload()) != decision.request_evidence_json
                or _json(request.policy.payload()) != decision.policy_evidence_json
            ):
                raise RoutingAuthorityError("Routing persistence authority or request evidence changed")
            try:
                capability_row = CapabilityRegistry._fetch_row(connection, request.capability_ref)
                capability = self.registry.capabilities._capability_from_row(connection, capability_row)
            except CapabilityIntegrityError as exc:
                raise RoutingIntegrityError("Routing Capability evidence failed verification") from exc
            except Exception as exc:
                raise RoutingIntegrityError("Routing Capability evidence is missing or malformed") from exc
            if not hmac.compare_digest(CapabilityRegistry._record_sha256(capability), decision.capability_record_sha256):
                raise RoutingIntegrityError("Routing Capability record changed before persistence")
            self.registry._verify_registry(connection, request.project_ref)
            registered_refs = {
                CapabilityImplementationRef(request.project_ref, cast(str, row["implementation_id"]))
                for row in connection.execute(
                    "SELECT implementation_id FROM capability_implementations WHERE project_id=? AND capability_id=? AND capability_version=?",
                    (request.project_ref.value, request.capability_ref.capability_id, request.capability_ref.version),
                ).fetchall()
            }
            candidate_refs = {candidate.implementation_ref for candidate in decision.candidates}
            if candidate_refs != registered_refs:
                raise RoutingConflictError("CapabilityImplementation registry changed during routing")
            verified_snapshots: set[ResourceSnapshotRef] = set()
            for candidate in decision.candidates:
                implementation = self.registry._fetch(connection, candidate.implementation_ref)
                if not hmac.compare_digest(implementation.record_sha256, candidate.implementation_record_sha256):
                    raise RoutingIntegrityError("Routing candidate implementation evidence changed before persistence")
                if candidate.snapshot_ref is None:
                    if candidate.resource_ref is not None:
                        current_head = connection.execute(
                            "SELECT 1 FROM resource_snapshot_heads WHERE project_id=? AND resource_id=?",
                            (request.project_ref.value, candidate.resource_ref.resource_id),
                        ).fetchone()
                        if current_head is not None:
                            raise RoutingConflictError("Routing Resource availability changed during routing")
                    continue
                if candidate.snapshot_ref in verified_snapshots:
                    continue
                snapshot_row = connection.execute(
                    """
                    SELECT snapshots.*,
                           heads.snapshot_id AS head_snapshot_id,
                           heads.sequence AS head_sequence,
                           heads.record_sha256 AS head_record_sha256,
                           heads.updated_at AS head_updated_at,
                           heads.head_sha256 AS head_sha256,
                           (SELECT MAX(history.sequence) FROM resource_snapshots AS history
                             WHERE history.project_id=heads.project_id AND history.resource_id=heads.resource_id)
                             AS maximum_sequence
                    FROM resource_snapshot_heads AS heads
                    JOIN resource_snapshots AS snapshots
                      ON snapshots.project_id=heads.project_id
                     AND snapshots.resource_id=heads.resource_id
                     AND snapshots.snapshot_id=heads.snapshot_id
                     AND snapshots.record_sha256=heads.record_sha256
                    WHERE heads.project_id=? AND heads.resource_id=?
                    """,
                    (
                        request.project_ref.value,
                        candidate.snapshot_ref.resource_ref.resource_id,
                    ),
                ).fetchone()
                if snapshot_row is None:
                    raise RoutingIntegrityError("Routing candidate ResourceSnapshot disappeared before persistence")
                try:
                    snapshot = self.resources._snapshot_from_head_row(snapshot_row)
                    self.resources._verify_snapshot_chain(connection, snapshot)
                except ResourceIntegrityError as exc:
                    raise RoutingIntegrityError("Routing current Resource head failed verification") from exc
                if (
                    snapshot.snapshot_ref != candidate.snapshot_ref
                    or not hmac.compare_digest(snapshot.record_sha256, cast(str, candidate.snapshot_record_sha256))
                ):
                    raise RoutingConflictError("Routing candidate ResourceSnapshot is no longer current")
                verified_snapshots.add(candidate.snapshot_ref)
            selected_impl_sha: str | None = None
            if decision.selected_implementation_ref is not None:
                selected_impl_sha = next(item.implementation_record_sha256 for item in decision.candidates if item.eligible and item.implementation_ref == decision.selected_implementation_ref and item.resource_ref == decision.selected_resource_ref)
            connection.execute(
                "INSERT INTO routing_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (decision.project_ref.value, decision.decision_ref.decision_id, decision.task_ref.task_id, decision.task_ref.revision, decision.task_digest, decision.run_id, decision.run_attempt_id, decision.run_attempt_fence, decision.node_ref.graph_ref.graph_id, decision.node_ref.graph_ref.revision, decision.node_ref.node_id, decision.capability_ref.capability_id, decision.capability_ref.version, decision.capability_record_sha256, decision.request_sha256, decision.policy_sha256, decision.request_evidence_json, decision.policy_evidence_json, decision.outcome.value, None if decision.selected_implementation_ref is None else decision.selected_implementation_ref.implementation_id, selected_impl_sha, None if decision.selected_resource_ref is None else decision.selected_resource_ref.resource_id, None if decision.selected_snapshot_ref is None else decision.selected_snapshot_ref.snapshot_id, decision.selected_snapshot_record_sha256, len(decision.candidates), decision.ranking_version, decision.created_at, decision.record_sha256),
            )
            for index, candidate in enumerate(decision.candidates, start=1):
                connection.execute(
                    "INSERT INTO routing_decision_candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (decision.project_ref.value, decision.decision_ref.decision_id, index, candidate.implementation_ref.implementation_id, candidate.implementation_record_sha256, None if candidate.resource_ref is None else candidate.resource_ref.resource_id, None if candidate.snapshot_ref is None else candidate.snapshot_ref.snapshot_id, candidate.snapshot_record_sha256, _json(candidate.payload()), candidate.candidate_sha256),
                )
            connection.execute("INSERT INTO routing_idempotency VALUES (?,?,?,?,?)", (request.project_ref.value, request.idempotency_key, request.request_sha256, decision.decision_ref.decision_id, decision.record_sha256))
            connection.commit()
            return decision
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RoutingConflictError("RoutingDecision persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _parse_candidate(project_ref: ProjectRef, payload: object) -> RoutingCandidate:
        if not isinstance(payload, dict):
            raise RoutingIntegrityError("Persisted routing candidate is malformed")
        try:
            impl_prefix = f"capability-implementation://{project_ref.value}/"
            impl_value = cast(str, payload["implementation_ref"])
            if not impl_value.startswith(impl_prefix):
                raise RoutingScopeError("Routing candidate implementation crossed Project scope")
            resource_value = cast(str | None, payload["resource_ref"])
            resource_ref = None
            if resource_value is not None:
                resource_prefix = f"resource://{project_ref.value}/"
                if not resource_value.startswith(resource_prefix):
                    raise RoutingScopeError("Routing candidate Resource crossed Project scope")
                resource_ref = ResourceRef(project_ref, resource_value.removeprefix(resource_prefix))
            snapshot_value = cast(str | None, payload["snapshot_ref"])
            snapshot_ref = None
            if snapshot_value is not None:
                assert resource_ref is not None
                prefix = f"resource-snapshot://{project_ref.value}/{resource_ref.resource_id}/"
                if not snapshot_value.startswith(prefix):
                    raise RoutingScopeError("Routing candidate snapshot crossed Resource scope")
                snapshot_ref = ResourceSnapshotRef(resource_ref, snapshot_value.removeprefix(prefix))
            return RoutingCandidate(
                CapabilityImplementationRef(project_ref, impl_value.removeprefix(impl_prefix)),
                cast(str, payload["implementation_record_sha256"]),
                resource_ref,
                snapshot_ref,
                cast(str | None, payload["snapshot_record_sha256"]),
                tuple(RoutingRejection(RoutingRejectionCode(cast(str, item["code"])), cast(str, item["detail"])) for item in cast(list[dict[str, object]], payload["rejections"])),
                cast(dict[str, str], payload["ranking_factors"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RoutingIntegrityError("Persisted routing candidate is malformed") from exc

    def _fetch(self, connection: sqlite3.Connection, ref: RoutingDecisionRef) -> RoutingDecision:
        row = connection.execute("SELECT * FROM routing_decisions WHERE project_id=? AND decision_id=?", (ref.project_ref.value, ref.decision_id)).fetchone()
        if row is None:
            orphan_candidate = connection.execute(
                "SELECT 1 FROM routing_decision_candidates WHERE project_id=? AND decision_id=? LIMIT 1",
                (ref.project_ref.value, ref.decision_id),
            ).fetchone()
            orphan_idempotency = connection.execute(
                "SELECT 1 FROM routing_idempotency WHERE project_id=? AND decision_id=? LIMIT 1",
                (ref.project_ref.value, ref.decision_id),
            ).fetchone()
            if orphan_candidate is not None or orphan_idempotency is not None:
                raise RoutingIntegrityError("RoutingDecision is missing while durable dependent evidence remains")
            raise RoutingNotFoundError("RoutingDecision not found")
        self.registry._verify_registry(connection, ref.project_ref)
        candidate_rows = connection.execute("SELECT * FROM routing_decision_candidates WHERE project_id=? AND decision_id=? ORDER BY candidate_index", (ref.project_ref.value, ref.decision_id)).fetchall()
        if len(candidate_rows) != row["candidate_count"] or tuple(item["candidate_index"] for item in candidate_rows) != tuple(range(1, len(candidate_rows) + 1)):
            raise RoutingIntegrityError("RoutingDecision candidate evidence is incomplete")
        candidates: list[RoutingCandidate] = []
        for candidate_row in candidate_rows:
            try:
                candidate_payload = json.loads(cast(str, candidate_row["candidate_json"]))
            except (TypeError, ValueError) as exc:
                raise RoutingIntegrityError("Persisted routing candidate is not valid JSON") from exc
            candidate = self._parse_candidate(ref.project_ref, candidate_payload)
            expected_columns = (
                candidate.implementation_ref.implementation_id,
                candidate.implementation_record_sha256,
                None if candidate.resource_ref is None else candidate.resource_ref.resource_id,
                None if candidate.snapshot_ref is None else candidate.snapshot_ref.snapshot_id,
                candidate.snapshot_record_sha256,
            )
            persisted_columns = tuple(
                candidate_row[name]
                for name in (
                    "implementation_id",
                    "implementation_record_sha256",
                    "resource_id",
                    "snapshot_id",
                    "snapshot_record_sha256",
                )
            )
            if persisted_columns != expected_columns:
                raise RoutingIntegrityError("RoutingDecision candidate columns differ from its receipt")
            implementation = self.registry._fetch(connection, candidate.implementation_ref)
            if not hmac.compare_digest(implementation.record_sha256, candidate.implementation_record_sha256) or not hmac.compare_digest(candidate.candidate_sha256, cast(str, candidate_row["candidate_sha256"])):
                raise RoutingIntegrityError("RoutingDecision candidate evidence changed")
            if candidate.snapshot_ref is not None:
                snapshot_row = connection.execute("SELECT * FROM resource_snapshots WHERE project_id=? AND resource_id=? AND snapshot_id=?", (ref.project_ref.value, candidate.snapshot_ref.resource_ref.resource_id, candidate.snapshot_ref.snapshot_id)).fetchone()
                if snapshot_row is None:
                    raise RoutingIntegrityError("RoutingDecision ResourceSnapshot evidence is missing")
                try:
                    snapshot = self.resources._snapshot_from_row(snapshot_row)
                    self.resources._verify_snapshot_chain(connection, snapshot)
                except ResourceIntegrityError as exc:
                    raise RoutingIntegrityError("RoutingDecision ResourceSnapshot evidence failed verification") from exc
                if snapshot.snapshot_ref != candidate.snapshot_ref or not hmac.compare_digest(snapshot.record_sha256, cast(str, candidate.snapshot_record_sha256)):
                    raise RoutingIntegrityError("RoutingDecision ResourceSnapshot evidence changed")
            candidates.append(candidate)
        node_ref = NodeRef(GraphRef(ref.project_ref, cast(str, row["graph_id"]), cast(int, row["graph_revision"])), cast(str, row["node_id"]))
        raw_selection = (
            row["selected_implementation_id"],
            row["selected_implementation_record_sha256"],
            row["selected_resource_id"],
            row["selected_snapshot_id"],
            row["selected_snapshot_record_sha256"],
        )
        if any(value is None for value in raw_selection) and any(value is not None for value in raw_selection):
            raise RoutingIntegrityError("RoutingDecision selected evidence is incomplete")
        task_ref = TaskRef(ref.project_ref, cast(str, row["task_id"]), cast(int, row["task_revision"]))
        run_ref = RunRef(ref.project_ref, cast(str, row["run_id"]))
        graph_ref = GraphRef(ref.project_ref, cast(str, row["graph_id"]), cast(int, row["graph_revision"]))
        try:
            task = self.tasks._fetch_task(connection, task_ref)
            run = self.runs._fetch_run(connection, run_ref)
            attempt = self.runs._fetch_attempt(connection, run, cast(str, row["run_attempt_id"]))
            graph = self.graphs._fetch_graph(connection, graph_ref)
            node = self._node(graph.nodes, node_ref)
            capability_ref = CapabilityRef(cast(str, row["capability_id"]), cast(str, row["capability_version"]))
            capability_row = CapabilityRegistry._fetch_row(connection, capability_ref)
            capability = self.registry.capabilities._capability_from_row(connection, capability_row)
            request_evidence = json.loads(cast(str, row["request_evidence_json"]))
            policy_evidence = json.loads(cast(str, row["policy_evidence_json"]))
            policy = RoutingPolicy.from_evidence(ref.project_ref, policy_evidence)
            reconstructed_request = RoutingRequest.from_evidence(
                request_evidence,
                task_ref=task_ref,
                node_ref=node_ref,
                capability_ref=capability_ref,
                authority_attempt=attempt,
                policy=policy,
            )
        except (CapabilityIntegrityError, TaskIntegrityError, RunIntegrityError, GraphIntegrityError) as exc:
            raise RoutingIntegrityError("RoutingDecision authority provenance failed verification") from exc
        except Exception as exc:
            raise RoutingIntegrityError("RoutingDecision authority provenance is malformed or missing") from exc
        if (
            not hmac.compare_digest(task.canonical_digest, cast(str, row["task_digest"]))
            or run.task_ref != task.task_ref
            or not hmac.compare_digest(run.task_digest, task.canonical_digest)
            or graph.task_ref != task.task_ref
            or not hmac.compare_digest(graph.task_digest, task.canonical_digest)
            or graph.run_ref != run.run_ref
            or node.node_ref != node_ref
            or attempt.fence != row["run_attempt_fence"]
            or reconstructed_request.request_sha256 != row["request_sha256"]
            or policy.policy_sha256 != row["policy_sha256"]
            or not hmac.compare_digest(CapabilityRegistry._record_sha256(capability), cast(str, row["capability_record_sha256"]))
        ):
            raise RoutingIntegrityError("RoutingDecision authority provenance differs from its receipt")
        selected_impl = None if row["selected_implementation_id"] is None else CapabilityImplementationRef(ref.project_ref, cast(str, row["selected_implementation_id"]))
        selected_resource = None if row["selected_resource_id"] is None else ResourceRef(ref.project_ref, cast(str, row["selected_resource_id"]))
        selected_snapshot = None if row["selected_snapshot_id"] is None else ResourceSnapshotRef(cast(ResourceRef, selected_resource), cast(str, row["selected_snapshot_id"]))
        selection_columns = (
            row["selected_implementation_record_sha256"],
            row["selected_snapshot_record_sha256"],
        )
        if selected_impl is None:
            if any(value is not None for value in selection_columns):
                raise RoutingIntegrityError("No-route RoutingDecision contains hidden selection evidence")
        else:
            selected_candidates = tuple(
                candidate
                for candidate in candidates
                if candidate.eligible
                and candidate.implementation_ref == selected_impl
                and candidate.resource_ref == selected_resource
                and candidate.snapshot_ref == selected_snapshot
            )
            if len(selected_candidates) != 1 or selection_columns != (
                selected_candidates[0].implementation_record_sha256,
                selected_candidates[0].snapshot_record_sha256,
            ):
                raise RoutingIntegrityError("RoutingDecision selected columns differ from candidate evidence")
        decision = RoutingDecision(
            ref,
            task_ref,
            cast(str, row["task_digest"]),
            node_ref,
            cast(str, row["run_id"]),
            cast(str, row["run_attempt_id"]),
            cast(int, row["run_attempt_fence"]),
            capability_ref,
            cast(str, row["capability_record_sha256"]),
            cast(str, row["request_sha256"]),
            cast(str, row["policy_sha256"]),
            cast(str, row["request_evidence_json"]),
            cast(str, row["policy_evidence_json"]),
            tuple(candidates),
            selected_impl,
            selected_resource,
            selected_snapshot,
            cast(str | None, row["selected_snapshot_record_sha256"]),
            RoutingOutcome(cast(str, row["outcome"])),
            cast(str, row["ranking_version"]),
            cast(str, row["created_at"]),
        )
        if not hmac.compare_digest(decision.record_sha256, cast(str, row["record_sha256"])):
            raise RoutingIntegrityError("RoutingDecision evidence changed")
        idempotency_rows = connection.execute(
            "SELECT request_sha256,decision_record_sha256 FROM routing_idempotency WHERE project_id=? AND decision_id=?",
            (ref.project_ref.value, ref.decision_id),
        ).fetchall()
        if len(idempotency_rows) != 1 or not hmac.compare_digest(cast(str, idempotency_rows[0]["request_sha256"]), decision.request_sha256) or not hmac.compare_digest(cast(str, idempotency_rows[0]["decision_record_sha256"]), decision.record_sha256):
            raise RoutingIntegrityError("RoutingDecision immutable idempotency anchor is missing or changed")
        return decision

    def get_decision(self, access: ProjectAccess, ref: RoutingDecisionRef) -> RoutingDecision:
        try:
            self.projects.get_project(access, ref.project_ref)
        except ProjectIntegrityError as exc:
            raise RoutingIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise RoutingScopeError("RoutingDecision Project scope mismatch") from exc
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            value = self._fetch(connection, ref)
            connection.commit()
            return value
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def scheduling_request(self, access: ProjectAccess, decision: RoutingDecision, *, priority: int = 0, deadline: str | None = None, queued_at: str | None = None) -> SchedulingRequest:
        current = self.get_decision(access, decision.decision_ref)
        if not hmac.compare_digest(current.record_sha256, decision.record_sha256):
            raise RoutingAuthorityError("Stale RoutingDecision cannot authorize scheduler request")
        if current.outcome is not RoutingOutcome.ROUTED or current.selected_implementation_ref is None or current.selected_resource_ref is None:
            raise RoutingAuthorityError("No-route decision cannot authorize scheduler request")
        implementation = self.registry.get(access, current.selected_implementation_ref)
        return SchedulingRequest(
            current.node_ref,
            (ResourceClaim(current.selected_resource_ref, implementation.resource_fit, implementation.resource_fit.required_available),),
            priority=priority,
            deadline=deadline,
            queued_at=_now() if queued_at is None else queued_at,
            allow_reduced_fit=False,
        )


__all__ = [
    "CapabilityImplementation", "CapabilityImplementationRef", "CapabilityImplementationRegistry",
    "ComputePlacement", "ComputeResolver", "ImplementationKind", "ImplementationResolution",
    "ImplementationResolver", "RoutingAuthorityError", "RoutingCandidate", "RoutingConflictError",
    "RoutingContractError", "RoutingDecision", "RoutingDecisionRef", "RoutingError", "RoutingIntegrityError",
    "RoutingNotFoundError", "RoutingOutcome", "RoutingPolicy", "RoutingRejection", "RoutingRejectionCode",
    "RoutingRequest", "RoutingScopeError", "RoutingService",
]
