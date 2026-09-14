"""Provider-neutral dynamic runtime Resource inventory for P1-07."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import sqlite3
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .artifact import ArtifactError, ArtifactRef, ArtifactService
from .project import ProjectAccess, ProjectRef, ProjectStore


_RESOURCE_ID_PATTERN = re.compile(r"res_[0-9a-f]{32}")
_SNAPSHOT_ID_PATTERN = re.compile(r"rsn_[0-9a-f]{32}")
_KIND_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_METRIC_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_UNIT_PATTERN = re.compile(r"[a-z][a-z0-9_./%-]{0,31}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_TEXT_LIMIT = 1024


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ResourceContractError(f"{field_name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ResourceContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResourceContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return value


def _parsed_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _bounded_text(value: object, field_name: str, *, allow_empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or (not allow_empty and not value)
        or len(value) > _TEXT_LIMIT
        or any(ord(character) < 32 for character in value)
    ):
        raise ResourceContractError(f"{field_name} is malformed or unbounded")
    return value


def _freeze_text_mapping(
    values: Mapping[str, str], field_name: str, *, limit: int = 128
) -> Mapping[str, str]:
    if not isinstance(values, Mapping):
        raise ResourceContractError(f"{field_name} must be a mapping")
    copied = dict(values)
    if len(copied) > limit:
        raise ResourceContractError(f"{field_name} is unbounded")
    for key, value in copied.items():
        if not isinstance(key, str) or _METRIC_PATTERN.fullmatch(key) is None:
            raise ResourceContractError(f"{field_name} key is malformed")
        _bounded_text(value, f"{field_name} value", allow_empty=True)
    return MappingProxyType(dict(sorted(copied.items())))


def _freeze_text_sequence(
    values: Sequence[str], field_name: str, *, limit: int = 256
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ResourceContractError(f"{field_name} must be a sequence")
    copied = tuple(values)
    if len(copied) > limit or len(set(copied)) != len(copied):
        raise ResourceContractError(f"{field_name} is duplicated or unbounded")
    for value in copied:
        _bounded_text(value, field_name)
    return tuple(sorted(copied))


class ResourceError(Exception):
    """Base class for Resource inventory failures."""


class ResourceContractError(ResourceError):
    """A Resource contract is malformed or unsafe."""


class ResourceScopeError(ResourceError):
    """A Resource operation crossed a Project boundary."""


class ResourceConflictError(ResourceError):
    """An immutable Resource identity conflicts with durable state."""


class ResourceNotFoundError(ResourceError):
    """A requested Resource or ResourceSnapshot does not exist."""


class ResourceIntegrityError(ResourceError):
    """Durable Resource evidence is malformed or has changed."""


class ResourceStaleError(ResourceError):
    """A caller tried to use an expired observation as current truth."""


class QuantitySource(str, Enum):
    """Truth classification for one capacity value."""

    CONFIGURED = "CONFIGURED"
    MEASURED = "MEASURED"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


class ResourceHealth(str, Enum):
    """Observed health, never inferred from static configuration."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ResourceFit(str, Enum):
    """Technical fit result; independent from semantic Capability identity."""

    FIT = "FIT"
    FIT_REDUCED = "FIT_REDUCED"
    REQUIRES_OTHER_RESOURCE = "REQUIRES_OTHER_RESOURCE"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ResourceQuantity:
    """A value with explicit units, truth source, and provenance."""

    value: int | float | None
    unit: str
    source_kind: QuantitySource
    source_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, QuantitySource):
            raise TypeError("source_kind must be QuantitySource")
        if not isinstance(self.unit, str) or _UNIT_PATTERN.fullmatch(self.unit) is None:
            raise ResourceContractError("ResourceQuantity unit is malformed")
        _bounded_text(self.source_ref, "source_ref")
        if self.source_kind is QuantitySource.UNKNOWN:
            if self.value is not None:
                raise ResourceContractError("UNKNOWN quantity must not contain a value")
        elif (
            isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or not math.isfinite(float(self.value))
            or self.value < 0
        ):
            raise ResourceContractError("Known quantity must be finite and non-negative")

    @classmethod
    def configured(
        cls, value: int | float, unit: str, source_ref: str
    ) -> "ResourceQuantity":
        return cls(value, unit, QuantitySource.CONFIGURED, source_ref)

    @classmethod
    def measured(
        cls, value: int | float, unit: str, source_ref: str
    ) -> "ResourceQuantity":
        return cls(value, unit, QuantitySource.MEASURED, source_ref)

    @classmethod
    def derived(
        cls, value: int | float, unit: str, source_ref: str
    ) -> "ResourceQuantity":
        return cls(value, unit, QuantitySource.DERIVED, source_ref)

    @classmethod
    def unknown(cls, unit: str, source_ref: str) -> "ResourceQuantity":
        return cls(None, unit, QuantitySource.UNKNOWN, source_ref)

    def to_payload(self) -> dict[str, object]:
        return {
            "source_kind": self.source_kind.value,
            "source_ref": self.source_ref,
            "unit": self.unit,
            "value": self.value,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceQuantity":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted quantity is malformed")
        try:
            return cls(
                value=cast(int | float | None, payload["value"]),
                unit=cast(str, payload["unit"]),
                source_kind=QuantitySource(cast(str, payload["source_kind"])),
                source_ref=cast(str, payload["source_ref"]),
            )
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted quantity is malformed") from exc


def _freeze_quantities(
    values: Mapping[str, ResourceQuantity],
    field_name: str,
    *,
    configured: bool,
) -> Mapping[str, ResourceQuantity]:
    if not isinstance(values, Mapping):
        raise ResourceContractError(f"{field_name} must be a mapping")
    copied = dict(values)
    if len(copied) > 256:
        raise ResourceContractError(f"{field_name} is unbounded")
    for metric, quantity in copied.items():
        if not isinstance(metric, str) or _METRIC_PATTERN.fullmatch(metric) is None:
            raise ResourceContractError(f"{field_name} metric is malformed")
        if not isinstance(quantity, ResourceQuantity):
            raise ResourceContractError(f"{field_name} values must be ResourceQuantity")
        if configured and quantity.source_kind is not QuantitySource.CONFIGURED:
            raise ResourceContractError("Resource configuration must be labeled CONFIGURED")
        if not configured and quantity.source_kind is QuantitySource.CONFIGURED:
            raise ResourceContractError("Configured capacity cannot be labeled observed")
    return MappingProxyType(dict(sorted(copied.items())))


def _quantities_payload(
    values: Mapping[str, ResourceQuantity],
) -> dict[str, object]:
    return {key: value.to_payload() for key, value in values.items()}


def _quantities_from_payload(payload: object) -> Mapping[str, ResourceQuantity]:
    if not isinstance(payload, dict):
        raise ResourceIntegrityError("Persisted capacity mapping is malformed")
    return {
        cast(str, key): ResourceQuantity.from_payload(value)
        for key, value in payload.items()
    }


@dataclass(frozen=True, order=True)
class ResourceRef:
    """Opaque, provider-neutral Resource identity within one Project."""

    project_ref: ProjectRef
    resource_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.resource_id, str)
            or _RESOURCE_ID_PATTERN.fullmatch(self.resource_id) is None
        ):
            raise ResourceContractError("Resource identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "ResourceRef":
        return cls(project_ref, f"res_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"resource://{self.project_ref.value}/{self.resource_id}"


@dataclass(frozen=True, order=True)
class ResourceSnapshotRef:
    """Exact immutable observation identity for one Resource."""

    resource_ref: ResourceRef
    snapshot_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        if (
            not isinstance(self.snapshot_id, str)
            or _SNAPSHOT_ID_PATTERN.fullmatch(self.snapshot_id) is None
        ):
            raise ResourceContractError("ResourceSnapshot identity is malformed")

    @property
    def project_ref(self) -> ProjectRef:
        return self.resource_ref.project_ref

    @property
    def value(self) -> str:
        return (
            f"resource-snapshot://{self.project_ref.value}/"
            f"{self.resource_ref.resource_id}/{self.snapshot_id}"
        )


@dataclass(frozen=True)
class Resource:
    """Immutable configured identity; never a claim about current capacity."""

    resource_ref: ResourceRef
    resource_kind: str
    locality_ref: str
    configured_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    static_attributes: Mapping[str, str] = field(default_factory=dict)
    ownership_metadata: Mapping[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_utc)
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        if (
            not isinstance(self.resource_kind, str)
            or _KIND_PATTERN.fullmatch(self.resource_kind) is None
        ):
            raise ResourceContractError("resource_kind is malformed")
        _bounded_text(self.locality_ref, "locality_ref")
        _timestamp(self.created_at, "created_at")
        object.__setattr__(
            self,
            "configured_capacity",
            _freeze_quantities(
                self.configured_capacity,
                "configured_capacity",
                configured=True,
            ),
        )
        object.__setattr__(
            self,
            "static_attributes",
            _freeze_text_mapping(self.static_attributes, "static_attributes"),
        )
        object.__setattr__(
            self,
            "ownership_metadata",
            _freeze_text_mapping(self.ownership_metadata, "ownership_metadata"),
        )
        semantic = _sha256(self._semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"resource_ref": self.resource_ref.value, "semantic_digest": semantic}),
        )

    @classmethod
    def create(
        cls,
        project_ref: ProjectRef,
        *,
        resource_kind: str,
        locality_ref: str,
        configured_capacity: Mapping[str, ResourceQuantity] | None = None,
        static_attributes: Mapping[str, str] | None = None,
        ownership_metadata: Mapping[str, str] | None = None,
    ) -> "Resource":
        return cls(
            resource_ref=ResourceRef.new(project_ref),
            resource_kind=resource_kind,
            locality_ref=locality_ref,
            configured_capacity=(
                {} if configured_capacity is None else configured_capacity
            ),
            static_attributes={} if static_attributes is None else static_attributes,
            ownership_metadata=(
                {} if ownership_metadata is None else ownership_metadata
            ),
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.resource_ref.project_ref

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "configured_capacity": _quantities_payload(self.configured_capacity),
            "created_at": self.created_at,
            "locality_ref": self.locality_ref,
            "ownership_metadata": dict(self.ownership_metadata),
            "resource_kind": self.resource_kind,
            "static_attributes": dict(self.static_attributes),
        }

    def to_payload(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "project_id": self.project_ref.value,
            "record_sha256": self.record_sha256,
            "resource_id": self.resource_ref.resource_id,
            "semantic_digest": self.semantic_digest,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "Resource":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted Resource is malformed")
        try:
            resource = cls(
                resource_ref=ResourceRef(
                    ProjectRef(cast(str, payload["project_id"])),
                    cast(str, payload["resource_id"]),
                ),
                resource_kind=cast(str, payload["resource_kind"]),
                locality_ref=cast(str, payload["locality_ref"]),
                configured_capacity=_quantities_from_payload(
                    payload["configured_capacity"]
                ),
                static_attributes=cast(Mapping[str, str], payload["static_attributes"]),
                ownership_metadata=cast(
                    Mapping[str, str], payload["ownership_metadata"]
                ),
                created_at=cast(str, payload["created_at"]),
            )
            if (
                payload.get("semantic_digest") != resource.semantic_digest
                or payload.get("record_sha256") != resource.record_sha256
            ):
                raise ResourceIntegrityError("Persisted Resource digest mismatch")
            return resource
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted Resource is malformed") from exc


@dataclass(frozen=True)
class ResourceDeviceSnapshot:
    """One observed device without imposing a vendor-specific schema."""

    device_id: str
    device_kind: str
    vendor: str | None = None
    model: str | None = None
    features: tuple[str, ...] = ()
    health: ResourceHealth = ResourceHealth.UNKNOWN
    physical_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    effective_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    used_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    available_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _bounded_text(self.device_id, "device_id")
        if not isinstance(self.device_kind, str) or _KIND_PATTERN.fullmatch(self.device_kind) is None:
            raise ResourceContractError("device_kind is malformed")
        if self.vendor is not None:
            _bounded_text(self.vendor, "vendor")
        if self.model is not None:
            _bounded_text(self.model, "model")
        if not isinstance(self.health, ResourceHealth):
            raise TypeError("health must be ResourceHealth")
        object.__setattr__(self, "features", _freeze_text_sequence(self.features, "features"))
        for field_name in (
            "physical_capacity",
            "effective_capacity",
            "used_capacity",
            "available_capacity",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_quantities(
                    cast(Mapping[str, ResourceQuantity], getattr(self, field_name)),
                    field_name,
                    configured=False,
                ),
            )
        object.__setattr__(
            self,
            "attributes",
            _freeze_text_mapping(self.attributes, "device attributes"),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "attributes": dict(self.attributes),
            "available_capacity": _quantities_payload(self.available_capacity),
            "device_id": self.device_id,
            "device_kind": self.device_kind,
            "effective_capacity": _quantities_payload(self.effective_capacity),
            "features": list(self.features),
            "health": self.health.value,
            "model": self.model,
            "physical_capacity": _quantities_payload(self.physical_capacity),
            "used_capacity": _quantities_payload(self.used_capacity),
            "vendor": self.vendor,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceDeviceSnapshot":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted device observation is malformed")
        try:
            return cls(
                device_id=cast(str, payload["device_id"]),
                device_kind=cast(str, payload["device_kind"]),
                vendor=cast(str | None, payload["vendor"]),
                model=cast(str | None, payload["model"]),
                features=tuple(cast(list[str], payload["features"])),
                health=ResourceHealth(cast(str, payload["health"])),
                physical_capacity=_quantities_from_payload(payload["physical_capacity"]),
                effective_capacity=_quantities_from_payload(payload["effective_capacity"]),
                used_capacity=_quantities_from_payload(payload["used_capacity"]),
                available_capacity=_quantities_from_payload(payload["available_capacity"]),
                attributes=cast(Mapping[str, str], payload["attributes"]),
            )
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted device observation is malformed") from exc


@dataclass(frozen=True, order=True)
class ResourceArtifactLocality:
    """Exact Project-scoped Artifact revision and immutable record evidence."""

    artifact_ref: ArtifactRef
    artifact_record_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")
        if (
            not isinstance(self.artifact_record_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.artifact_record_sha256) is None
        ):
            raise ResourceContractError("Artifact locality record digest is malformed")

    @property
    def project_ref(self) -> ProjectRef:
        return self.artifact_ref.project_ref

    @property
    def value(self) -> str:
        return f"{self.artifact_ref.value}?record_sha256={self.artifact_record_sha256}"

    def to_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_ref.artifact_id,
            "artifact_record_sha256": self.artifact_record_sha256,
            "project_id": self.project_ref.value,
            "revision": self.artifact_ref.revision,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceArtifactLocality":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted Artifact locality is malformed")
        try:
            return cls(
                artifact_ref=ArtifactRef(
                    ProjectRef(cast(str, payload["project_id"])),
                    cast(str, payload["artifact_id"]),
                    cast(int, payload["revision"]),
                ),
                artifact_record_sha256=cast(
                    str, payload["artifact_record_sha256"]
                ),
            )
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted Artifact locality is malformed") from exc


@dataclass(frozen=True, order=True)
class ResourceWorkspaceLocality:
    """Explicit Project-scoped workspace locality identity."""

    project_ref: ProjectRef
    workspace_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        _bounded_text(self.workspace_ref, "workspace_ref")

    @property
    def value(self) -> str:
        return f"workspace-locality://{self.project_ref.value}/{self.workspace_ref}"

    def to_payload(self) -> dict[str, object]:
        return {
            "project_id": self.project_ref.value,
            "workspace_ref": self.workspace_ref,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceWorkspaceLocality":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted workspace locality is malformed")
        try:
            return cls(
                project_ref=ProjectRef(cast(str, payload["project_id"])),
                workspace_ref=cast(str, payload["workspace_ref"]),
            )
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted workspace locality is malformed") from exc


@dataclass(frozen=True)
class ResourceLocality:
    """Locality evidence with explicit observed-versus-unknown dimensions."""

    loaded_model_refs: tuple[str, ...] = ()
    local_model_refs: tuple[str, ...] = ()
    installed_tool_refs: tuple[str, ...] = ()
    warm_cache_refs: tuple[str, ...] = ()
    local_artifact_refs: tuple[ResourceArtifactLocality, ...] = ()
    local_workspace_refs: tuple[ResourceWorkspaceLocality, ...] = ()
    observed_dimensions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "loaded_model_refs",
            "local_model_refs",
            "installed_tool_refs",
            "warm_cache_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_sequence(
                    cast(Sequence[str], getattr(self, field_name)), field_name
                ),
            )
        if not isinstance(self.local_artifact_refs, tuple) or not all(
            isinstance(item, ResourceArtifactLocality)
            for item in self.local_artifact_refs
        ):
            raise ResourceContractError(
                "local_artifact_refs must contain exact Artifact evidence"
            )
        if (
            len(self.local_artifact_refs) > 256
            or len(set(self.local_artifact_refs)) != len(self.local_artifact_refs)
        ):
            raise ResourceContractError("local_artifact_refs is duplicated or unbounded")
        object.__setattr__(
            self,
            "local_artifact_refs",
            tuple(sorted(self.local_artifact_refs)),
        )
        if not isinstance(self.local_workspace_refs, tuple) or not all(
            isinstance(item, ResourceWorkspaceLocality)
            for item in self.local_workspace_refs
        ):
            raise ResourceContractError(
                "local_workspace_refs must contain Project-scoped workspace evidence"
            )
        if (
            len(self.local_workspace_refs) > 256
            or len(set(self.local_workspace_refs)) != len(self.local_workspace_refs)
        ):
            raise ResourceContractError("local_workspace_refs is duplicated or unbounded")
        object.__setattr__(
            self,
            "local_workspace_refs",
            tuple(sorted(self.local_workspace_refs)),
        )
        dimensions = set(
            _freeze_text_sequence(
                self.observed_dimensions,
                "observed_dimensions",
                limit=6,
            )
        )
        for field_name in (
            "loaded_model_refs",
            "local_model_refs",
            "installed_tool_refs",
            "warm_cache_refs",
            "local_artifact_refs",
            "local_workspace_refs",
        ):
            if cast(tuple[object, ...], getattr(self, field_name)):
                dimensions.add(field_name)
        allowed = {
            "loaded_model_refs",
            "local_model_refs",
            "installed_tool_refs",
            "warm_cache_refs",
            "local_artifact_refs",
            "local_workspace_refs",
        }
        if not dimensions.issubset(allowed):
            raise ResourceContractError("observed locality dimension is malformed")
        object.__setattr__(self, "observed_dimensions", tuple(sorted(dimensions)))

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            field_name: list(cast(tuple[str, ...], getattr(self, field_name)))
            for field_name in (
                "loaded_model_refs",
                "local_model_refs",
                "installed_tool_refs",
                "warm_cache_refs",
            )
        }
        payload["local_artifact_refs"] = [
            item.to_payload() for item in self.local_artifact_refs
        ]
        payload["local_workspace_refs"] = [
            item.to_payload() for item in self.local_workspace_refs
        ]
        payload["observed_dimensions"] = list(self.observed_dimensions)
        return payload

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceLocality":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted locality is malformed")
        try:
            return cls(
                loaded_model_refs=tuple(cast(list[str], payload["loaded_model_refs"])),
                local_model_refs=tuple(cast(list[str], payload["local_model_refs"])),
                installed_tool_refs=tuple(cast(list[str], payload["installed_tool_refs"])),
                warm_cache_refs=tuple(cast(list[str], payload["warm_cache_refs"])),
                local_artifact_refs=tuple(
                    ResourceArtifactLocality.from_payload(item)
                    for item in cast(list[object], payload["local_artifact_refs"])
                ),
                local_workspace_refs=tuple(
                    ResourceWorkspaceLocality.from_payload(item)
                    for item in cast(list[object], payload["local_workspace_refs"])
                ),
                observed_dimensions=tuple(
                    cast(list[str], payload["observed_dimensions"])
                ),
            )
        except (KeyError, TypeError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted locality is malformed") from exc


@dataclass(frozen=True)
class ResourceObservation:
    """Observer output before it is durably chained to a Resource."""

    observed_at: str
    fresh_for_seconds: int
    health: ResourceHealth
    physical_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    effective_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    used_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    available_capacity: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    pressure: Mapping[str, ResourceQuantity] = field(default_factory=dict)
    devices: tuple[ResourceDeviceSnapshot, ...] = ()
    locality: ResourceLocality = field(default_factory=ResourceLocality)
    runtime_attributes: Mapping[str, str] = field(default_factory=dict)
    known_cost: ResourceQuantity = field(
        default_factory=lambda: ResourceQuantity.unknown(
            "usd_per_hour", "observer://cost/unavailable"
        )
    )
    failure_causes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _timestamp(self.observed_at, "observed_at")
        if (
            isinstance(self.fresh_for_seconds, bool)
            or not isinstance(self.fresh_for_seconds, int)
            or self.fresh_for_seconds < 0
            or self.fresh_for_seconds > 86400
        ):
            raise ResourceContractError("fresh_for_seconds is invalid")
        if not isinstance(self.health, ResourceHealth):
            raise TypeError("health must be ResourceHealth")
        if self.fresh_for_seconds == 0 and self.health is not ResourceHealth.UNKNOWN:
            raise ResourceContractError("Only UNKNOWN observations may be immediately stale")
        for field_name in (
            "physical_capacity",
            "effective_capacity",
            "used_capacity",
            "available_capacity",
            "pressure",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_quantities(
                    cast(Mapping[str, ResourceQuantity], getattr(self, field_name)),
                    field_name,
                    configured=False,
                ),
            )
        if not isinstance(self.devices, tuple) or not all(
            isinstance(device, ResourceDeviceSnapshot) for device in self.devices
        ):
            raise ResourceContractError("devices must contain ResourceDeviceSnapshot")
        if len(self.devices) > 128 or len({item.device_id for item in self.devices}) != len(self.devices):
            raise ResourceContractError("devices are duplicated or unbounded")
        object.__setattr__(self, "devices", tuple(sorted(self.devices, key=lambda item: item.device_id)))
        if not isinstance(self.locality, ResourceLocality):
            raise TypeError("locality must be ResourceLocality")
        object.__setattr__(
            self,
            "runtime_attributes",
            _freeze_text_mapping(self.runtime_attributes, "runtime_attributes"),
        )
        if (
            not isinstance(self.known_cost, ResourceQuantity)
            or self.known_cost.source_kind is QuantitySource.CONFIGURED
        ):
            raise ResourceContractError("known_cost must be observed or UNKNOWN")
        object.__setattr__(
            self,
            "failure_causes",
            _freeze_text_sequence(self.failure_causes, "failure_causes", limit=16),
        )
        if self.failure_causes and self.health is not ResourceHealth.UNKNOWN:
            raise ResourceContractError("Observer failure cannot be labeled healthy")

    def to_payload(self) -> dict[str, object]:
        return {
            "available_capacity": _quantities_payload(self.available_capacity),
            "devices": [item.to_payload() for item in self.devices],
            "effective_capacity": _quantities_payload(self.effective_capacity),
            "failure_causes": list(self.failure_causes),
            "fresh_for_seconds": self.fresh_for_seconds,
            "health": self.health.value,
            "known_cost": self.known_cost.to_payload(),
            "locality": self.locality.to_payload(),
            "observed_at": self.observed_at,
            "physical_capacity": _quantities_payload(self.physical_capacity),
            "pressure": _quantities_payload(self.pressure),
            "runtime_attributes": dict(self.runtime_attributes),
            "used_capacity": _quantities_payload(self.used_capacity),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceObservation":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted observation is malformed")
        try:
            return cls(
                observed_at=cast(str, payload["observed_at"]),
                fresh_for_seconds=cast(int, payload["fresh_for_seconds"]),
                health=ResourceHealth(cast(str, payload["health"])),
                physical_capacity=_quantities_from_payload(payload["physical_capacity"]),
                effective_capacity=_quantities_from_payload(payload["effective_capacity"]),
                used_capacity=_quantities_from_payload(payload["used_capacity"]),
                available_capacity=_quantities_from_payload(payload["available_capacity"]),
                pressure=_quantities_from_payload(payload["pressure"]),
                devices=tuple(
                    ResourceDeviceSnapshot.from_payload(item)
                    for item in cast(list[object], payload["devices"])
                ),
                locality=ResourceLocality.from_payload(payload["locality"]),
                runtime_attributes=cast(
                    Mapping[str, str], payload["runtime_attributes"]
                ),
                known_cost=ResourceQuantity.from_payload(payload["known_cost"]),
                failure_causes=tuple(cast(list[str], payload["failure_causes"])),
            )
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted observation is malformed") from exc


@dataclass(frozen=True)
class ResourceSnapshot:
    """Immutable, freshness-bounded, provenance-chained Resource evidence."""

    snapshot_ref: ResourceSnapshotRef
    resource_record_sha256: str
    sequence: int
    observer_id: str
    observation: ResourceObservation
    previous_record_sha256: str | None
    observation_sha256: str = field(init=False)
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_ref, ResourceSnapshotRef):
            raise TypeError("snapshot_ref must be ResourceSnapshotRef")
        if (
            not isinstance(self.resource_record_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.resource_record_sha256) is None
        ):
            raise ResourceContractError("resource_record_sha256 is malformed")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise ResourceContractError("snapshot sequence is invalid")
        if not isinstance(self.observer_id, str) or _KIND_PATTERN.fullmatch(self.observer_id) is None:
            raise ResourceContractError("observer_id is malformed")
        if not isinstance(self.observation, ResourceObservation):
            raise TypeError("observation must be ResourceObservation")
        if self.previous_record_sha256 is not None and (
            not isinstance(self.previous_record_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.previous_record_sha256) is None
        ):
            raise ResourceContractError("previous_record_sha256 is malformed")
        if self.sequence == 1 and self.previous_record_sha256 is not None:
            raise ResourceContractError("First snapshot cannot have a predecessor")
        if self.sequence > 1 and self.previous_record_sha256 is None:
            raise ResourceContractError("Later snapshot requires a predecessor")
        observation_sha = _sha256(self.observation.to_payload())
        expected_snapshot_id = "rsn_" + _sha256(
            {
                "observation_sha256": observation_sha,
                "previous_record_sha256": self.previous_record_sha256,
                "resource_record_sha256": self.resource_record_sha256,
                "resource_ref": self.resource_ref.value,
            }
        )[:32]
        if self.snapshot_ref.snapshot_id != expected_snapshot_id:
            raise ResourceIntegrityError("ResourceSnapshot content identity mismatch")
        object.__setattr__(self, "observation_sha256", observation_sha)
        semantic = _sha256(self._semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"semantic_digest": semantic, "snapshot_ref": self.snapshot_ref.value}),
        )

    @property
    def resource_ref(self) -> ResourceRef:
        return self.snapshot_ref.resource_ref

    @property
    def project_ref(self) -> ProjectRef:
        return self.resource_ref.project_ref

    @property
    def observed_at(self) -> str:
        return self.observation.observed_at

    @property
    def fresh_until(self) -> str:
        return (
            _parsed_timestamp(self.observed_at)
            + timedelta(seconds=self.observation.fresh_for_seconds)
        ).isoformat(timespec="microseconds")

    @property
    def health(self) -> ResourceHealth:
        return self.observation.health

    @property
    def physical_capacity(self) -> Mapping[str, ResourceQuantity]:
        return self.observation.physical_capacity

    @property
    def effective_capacity(self) -> Mapping[str, ResourceQuantity]:
        return self.observation.effective_capacity

    @property
    def used_capacity(self) -> Mapping[str, ResourceQuantity]:
        return self.observation.used_capacity

    @property
    def available_capacity(self) -> Mapping[str, ResourceQuantity]:
        return self.observation.available_capacity

    @property
    def pressure(self) -> Mapping[str, ResourceQuantity]:
        return self.observation.pressure

    @property
    def devices(self) -> tuple[ResourceDeviceSnapshot, ...]:
        return self.observation.devices

    @property
    def locality(self) -> ResourceLocality:
        return self.observation.locality

    @property
    def known_cost(self) -> ResourceQuantity:
        return self.observation.known_cost

    @property
    def failure_causes(self) -> tuple[str, ...]:
        return self.observation.failure_causes

    def is_fresh(self, at: str | None = None) -> bool:
        comparison = _parsed_timestamp(_now_utc() if at is None else _timestamp(at, "at"))
        return _parsed_timestamp(self.observed_at) <= comparison < _parsed_timestamp(
            self.fresh_until
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "observation_sha256": self.observation_sha256,
            "observer_id": self.observer_id,
            "previous_record_sha256": self.previous_record_sha256,
            "resource_record_sha256": self.resource_record_sha256,
            "sequence": self.sequence,
        }

    def to_payload(self) -> dict[str, object]:
        return {
            **self._semantic_payload(),
            "observation": self.observation.to_payload(),
            "project_id": self.project_ref.value,
            "record_sha256": self.record_sha256,
            "resource_id": self.resource_ref.resource_id,
            "semantic_digest": self.semantic_digest,
            "snapshot_id": self.snapshot_ref.snapshot_id,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ResourceSnapshot":
        if not isinstance(payload, dict):
            raise ResourceIntegrityError("Persisted ResourceSnapshot is malformed")
        try:
            snapshot = cls(
                snapshot_ref=ResourceSnapshotRef(
                    ResourceRef(
                        ProjectRef(cast(str, payload["project_id"])),
                        cast(str, payload["resource_id"]),
                    ),
                    cast(str, payload["snapshot_id"]),
                ),
                resource_record_sha256=cast(str, payload["resource_record_sha256"]),
                sequence=cast(int, payload["sequence"]),
                observer_id=cast(str, payload["observer_id"]),
                observation=ResourceObservation.from_payload(payload["observation"]),
                previous_record_sha256=cast(
                    str | None, payload["previous_record_sha256"]
                ),
            )
            if (
                payload.get("observation_sha256") != snapshot.observation_sha256
                or payload.get("semantic_digest") != snapshot.semantic_digest
                or payload.get("record_sha256") != snapshot.record_sha256
            ):
                raise ResourceIntegrityError("Persisted ResourceSnapshot digest mismatch")
            return snapshot
        except (KeyError, TypeError, ValueError, ResourceContractError) as exc:
            raise ResourceIntegrityError("Persisted ResourceSnapshot is malformed") from exc


class ResourceObserver(ABC):
    """Replaceable observer; implementations report facts but do not persist them."""

    @property
    @abstractmethod
    def observer_id(self) -> str:
        """Stable provider-neutral observer implementation identity."""

    @abstractmethod
    def observe(self, resource: Resource) -> ResourceObservation:
        """Observe current runtime state without mutating semantic Capability state."""


class FakeResourceObserver(ResourceObserver):
    """Deterministic TEST/REFERENCE observer for exact scenario coverage."""

    def __init__(
        self,
        observations: Sequence[ResourceObservation | Exception],
        *,
        observer_id: str = "test.reference",
    ) -> None:
        if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
            raise ResourceContractError("observations must be a sequence")
        if not observations or not all(
            isinstance(item, (ResourceObservation, Exception)) for item in observations
        ):
            raise ResourceContractError("Fake observer requires deterministic results")
        if _KIND_PATTERN.fullmatch(observer_id) is None:
            raise ResourceContractError("observer_id is malformed")
        self._observer_id = observer_id
        self._observations = tuple(observations)
        self._position = 0

    @property
    def observer_id(self) -> str:
        return self._observer_id

    @property
    def observations_consumed(self) -> int:
        return self._position

    def observe(self, resource: Resource) -> ResourceObservation:
        if not isinstance(resource, Resource):
            raise TypeError("resource must be Resource")
        if self._position >= len(self._observations):
            raise ResourceError("Deterministic fake observer is exhausted")
        result = self._observations[self._position]
        self._position += 1
        if isinstance(result, Exception):
            raise result
        return result


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def _read_int(path: Path) -> int | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    return value if value >= 0 else None


def _meminfo() -> dict[str, int]:
    text = _read_text(Path("/proc/meminfo"))
    if text is None:
        return {}
    result: dict[str, int] = {}
    for line in text.splitlines():
        name, separator, remainder = line.partition(":")
        if not separator:
            continue
        parts = remainder.strip().split()
        if not parts:
            continue
        try:
            value = int(parts[0])
        except ValueError:
            continue
        if value < 0:
            continue
        multiplier = 1024 if len(parts) > 1 and parts[1] == "kB" else 1
        result[name] = value * multiplier
    return result


def _cgroup_directory() -> Path | None:
    text = _read_text(Path("/proc/self/cgroup"))
    if text is None:
        return None
    for line in text.splitlines():
        hierarchy, controllers, relative = line.split(":", 2)
        if hierarchy == "0" and controllers == "":
            return Path("/sys/fs/cgroup") / relative.lstrip("/")
    return None


def _default_route_interface() -> str | None:
    text = _read_text(Path("/proc/net/route"))
    if text is None:
        return None
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 4 and fields[1] == "00000000":
            try:
                flags = int(fields[3], 16)
            except ValueError:
                continue
            if flags & 0x1:
                return fields[0]
    return None


def _generic_gpu_devices() -> tuple[ResourceDeviceSnapshot, ...]:
    devices: list[ResourceDeviceSnapshot] = []
    for render_node in sorted(Path("/sys/class/drm").glob("renderD*")):
        device_path = render_node / "device"
        vendor_code = _read_text(device_path / "vendor")
        model_code = _read_text(device_path / "device")
        vendor = None if vendor_code is None else f"pci:{vendor_code}"
        model = None if model_code is None else f"pci:{model_code}"
        unknown_vram = ResourceQuantity.unknown(
            "bytes", f"sysfs://{device_path}/vram-unavailable"
        )
        devices.append(
            ResourceDeviceSnapshot(
                device_id=f"drm:{render_node.name}",
                device_kind="gpu",
                vendor=vendor,
                model=model,
                health=ResourceHealth.UNKNOWN,
                physical_capacity={"vram.bytes": unknown_vram},
                effective_capacity={"vram.bytes": unknown_vram},
                used_capacity={"vram.bytes": unknown_vram},
                available_capacity={"vram.bytes": unknown_vram},
                attributes={"observation.interface": "linux.drm.sysfs"},
            )
        )
    return tuple(devices)


class LocalResourceObserver(ResourceObserver):
    """Real Linux/local observer using only current host and runtime sources."""

    def __init__(
        self,
        *,
        fresh_for_seconds: int = 30,
        locality: ResourceLocality | None = None,
        expected_locality_ref: str | None = None,
    ) -> None:
        if (
            isinstance(fresh_for_seconds, bool)
            or not isinstance(fresh_for_seconds, int)
            or fresh_for_seconds < 1
            or fresh_for_seconds > 3600
        ):
            raise ResourceContractError("fresh_for_seconds is invalid")
        self.fresh_for_seconds = fresh_for_seconds
        self.locality = ResourceLocality() if locality is None else locality
        self.expected_locality_ref = (
            f"host://{socket.gethostname()}"
            if expected_locality_ref is None
            else _bounded_text(expected_locality_ref, "expected_locality_ref")
        )

    @property
    def observer_id(self) -> str:
        return "local.linux"

    def observe(self, resource: Resource) -> ResourceObservation:
        if not isinstance(resource, Resource):
            raise TypeError("resource must be Resource")
        if resource.locality_ref != self.expected_locality_ref:
            raise ResourceScopeError(
                "Local observer cannot attribute this host to another Resource locality"
            )
        observed_at = _now_utc()
        physical: dict[str, ResourceQuantity] = {}
        effective: dict[str, ResourceQuantity] = {}
        used: dict[str, ResourceQuantity] = {}
        available: dict[str, ResourceQuantity] = {}
        pressure: dict[str, ResourceQuantity] = {}
        attributes: dict[str, str] = {
            "host.name": socket.gethostname(),
            "runtime.architecture": platform.machine() or "unknown",
            "runtime.kernel": platform.release() or "unknown",
            "runtime.os": platform.system() or "unknown",
        }

        logical_cpu = os.cpu_count()
        if logical_cpu is None:
            cpu_physical = ResourceQuantity.unknown(
                "count", "runtime://python/os.cpu_count"
            )
        else:
            cpu_physical = ResourceQuantity.measured(
                logical_cpu, "count", "runtime://python/os.cpu_count"
            )
        physical["cpu.logical_count"] = cpu_physical

        cgroup = _cgroup_directory()
        cpu_effective_value: float | None = None
        if logical_cpu is not None:
            cpu_effective_value = float(logical_cpu)
        if cgroup is not None:
            attributes["container.cgroup_path"] = str(cgroup)
            attributes["container.cgroup_version"] = "2"
            cpu_max = _read_text(cgroup / "cpu.max")
            if cpu_max is not None:
                attributes["container.cpu_max"] = cpu_max
                quota_text, _, period_text = cpu_max.partition(" ")
                if quota_text != "max":
                    try:
                        quota = int(quota_text)
                        period = int(period_text)
                        quota_cpu = quota / period
                    except (ValueError, ZeroDivisionError):
                        quota_cpu = -1.0
                    if quota_cpu >= 0:
                        cpu_effective_value = (
                            quota_cpu
                            if cpu_effective_value is None
                            else min(cpu_effective_value, quota_cpu)
                        )
        else:
            attributes["container.cgroup_version"] = "unknown"

        if cpu_effective_value is None:
            effective["cpu.logical_count"] = ResourceQuantity.unknown(
                "count", "observer://cpu/effective-unavailable"
            )
        else:
            effective["cpu.logical_count"] = ResourceQuantity.derived(
                cpu_effective_value,
                "count",
                "observer://cpu/physical-and-cgroup-limit",
            )
        try:
            load_1m = os.getloadavg()[0]
        except OSError:
            load_1m = None
        if load_1m is None:
            used["cpu.logical_count"] = ResourceQuantity.unknown(
                "count", "runtime://python/os.getloadavg"
            )
            available["cpu.logical_count"] = ResourceQuantity.unknown(
                "count", "observer://cpu/availability-unavailable"
            )
            pressure["cpu.load_ratio"] = ResourceQuantity.unknown(
                "ratio", "runtime://python/os.getloadavg"
            )
        else:
            used["cpu.logical_count"] = ResourceQuantity.measured(
                load_1m, "count", "runtime://python/os.getloadavg/1m"
            )
            if cpu_effective_value is None:
                available["cpu.logical_count"] = ResourceQuantity.unknown(
                    "count", "observer://cpu/effective-unavailable"
                )
                pressure["cpu.load_ratio"] = ResourceQuantity.unknown(
                    "ratio", "observer://cpu/effective-unavailable"
                )
            else:
                available["cpu.logical_count"] = ResourceQuantity.derived(
                    max(cpu_effective_value - load_1m, 0.0),
                    "count",
                    "observer://cpu/effective-minus-load1m",
                )
                pressure["cpu.load_ratio"] = ResourceQuantity.derived(
                    load_1m / cpu_effective_value if cpu_effective_value > 0 else 1.0,
                    "ratio",
                    "observer://cpu/load1m-over-effective",
                )

        memory = _meminfo()
        memory_total = memory.get("MemTotal")
        memory_available = memory.get("MemAvailable")
        if memory_total is None:
            physical["memory.bytes"] = ResourceQuantity.unknown(
                "bytes", "procfs:///proc/meminfo/MemTotal"
            )
        else:
            physical["memory.bytes"] = ResourceQuantity.measured(
                memory_total, "bytes", "procfs:///proc/meminfo/MemTotal"
            )
        memory_limit: int | None = None
        memory_current: int | None = None
        if cgroup is not None:
            limit_text = _read_text(cgroup / "memory.max")
            if limit_text is not None:
                attributes["container.memory_max"] = limit_text
                if limit_text != "max":
                    try:
                        parsed_limit = int(limit_text)
                    except ValueError:
                        parsed_limit = -1
                    if parsed_limit >= 0:
                        memory_limit = parsed_limit
            memory_current = _read_int(cgroup / "memory.current")
        effective_memory: int | None = memory_total
        if memory_limit is not None:
            effective_memory = (
                memory_limit
                if effective_memory is None
                else min(effective_memory, memory_limit)
            )
        if effective_memory is None:
            effective["memory.bytes"] = ResourceQuantity.unknown(
                "bytes", "observer://memory/effective-unavailable"
            )
        else:
            effective["memory.bytes"] = ResourceQuantity.derived(
                effective_memory,
                "bytes",
                "observer://memory/physical-and-cgroup-limit",
            )
        if memory_current is not None and memory_limit is not None:
            current_used = min(memory_current, memory_limit)
            current_available = max(memory_limit - memory_current, 0)
            used_source = f"cgroup://{cgroup}/memory.current"
        elif memory_total is not None and memory_available is not None:
            current_used = max(memory_total - memory_available, 0)
            current_available = memory_available
            if effective_memory is not None:
                current_available = min(current_available, effective_memory)
            used_source = "procfs:///proc/meminfo/MemAvailable"
        else:
            current_used = None
            current_available = None
            used_source = "observer://memory/usage-unavailable"
        if current_used is None or current_available is None:
            used["memory.bytes"] = ResourceQuantity.unknown("bytes", used_source)
            available["memory.bytes"] = ResourceQuantity.unknown("bytes", used_source)
            pressure["memory.used_ratio"] = ResourceQuantity.unknown("ratio", used_source)
        else:
            used["memory.bytes"] = ResourceQuantity.derived(
                current_used, "bytes", used_source
            )
            available["memory.bytes"] = ResourceQuantity.derived(
                current_available, "bytes", used_source
            )
            pressure["memory.used_ratio"] = ResourceQuantity.derived(
                current_used / effective_memory
                if effective_memory is not None and effective_memory > 0
                else 0.0,
                "ratio",
                "observer://memory/used-over-effective",
            )

        try:
            storage = shutil.disk_usage(Path.cwd())
        except OSError:
            storage = None
        if storage is None:
            for target in (physical, effective, used, available):
                target["storage.workspace.bytes"] = ResourceQuantity.unknown(
                    "bytes", "runtime://python/shutil.disk_usage"
                )
        else:
            physical["storage.workspace.bytes"] = ResourceQuantity.measured(
                storage.total, "bytes", "runtime://python/shutil.disk_usage"
            )
            effective["storage.workspace.bytes"] = ResourceQuantity.measured(
                storage.total, "bytes", "runtime://python/shutil.disk_usage"
            )
            used["storage.workspace.bytes"] = ResourceQuantity.measured(
                storage.used, "bytes", "runtime://python/shutil.disk_usage"
            )
            available["storage.workspace.bytes"] = ResourceQuantity.measured(
                storage.free, "bytes", "runtime://python/shutil.disk_usage"
            )
        available["storage.throughput_bps"] = ResourceQuantity.unknown(
            "bytes_per_second", "observer://storage/benchmark-not-run"
        )
        available["network.bandwidth_bps"] = ResourceQuantity.unknown(
            "bytes_per_second", "observer://network/benchmark-not-run"
        )
        available["network.latency_ms"] = ResourceQuantity.unknown(
            "milliseconds", "observer://network/probe-not-run"
        )
        route_interface = _default_route_interface()
        attributes["network.default_route"] = "absent" if route_interface is None else "present"
        if route_interface is not None:
            attributes["network.default_interface"] = route_interface
        pressure["queue.used_ratio"] = ResourceQuantity.unknown(
            "ratio", "observer://queue/not-integrated"
        )
        pressure["allocation.used_ratio"] = ResourceQuantity.unknown(
            "ratio", "observer://allocation/not-integrated"
        )

        health = (
            ResourceHealth.HEALTHY
            if logical_cpu is not None and memory_total is not None and storage is not None
            else ResourceHealth.UNKNOWN
        )
        return ResourceObservation(
            observed_at=observed_at,
            fresh_for_seconds=self.fresh_for_seconds,
            health=health,
            physical_capacity=physical,
            effective_capacity=effective,
            used_capacity=used,
            available_capacity=available,
            pressure=pressure,
            devices=_generic_gpu_devices(),
            locality=self.locality,
            runtime_attributes=attributes,
            known_cost=ResourceQuantity.unknown(
                "usd_per_hour", "observer://cost/not-configured-as-observed"
            ),
        )


@dataclass(frozen=True)
class ResourceFitRequest:
    """Exact technical requirements; reduced thresholds require explicit permission."""

    required_effective: Mapping[str, float] = field(default_factory=dict)
    required_available: Mapping[str, float] = field(default_factory=dict)
    reduced_available: Mapping[str, float] = field(default_factory=dict)
    maximum_pressure: Mapping[str, float] = field(default_factory=dict)
    required_device_kind: str | None = None
    required_device_features: tuple[str, ...] = ()
    required_device_available: Mapping[str, float] = field(default_factory=dict)
    reduced_device_available: Mapping[str, float] = field(default_factory=dict)
    required_loaded_model_refs: tuple[str, ...] = ()
    required_installed_tool_refs: tuple[str, ...] = ()
    required_artifact_refs: tuple[ResourceArtifactLocality, ...] = ()
    required_workspace_refs: tuple[ResourceWorkspaceLocality, ...] = ()
    maximum_cost: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "required_effective",
            "required_available",
            "reduced_available",
            "maximum_pressure",
            "required_device_available",
            "reduced_device_available",
        ):
            values = cast(Mapping[str, float], getattr(self, field_name))
            if not isinstance(values, Mapping) or len(values) > 128:
                raise ResourceContractError(f"{field_name} is malformed or unbounded")
            copied: dict[str, float] = {}
            for metric, value in values.items():
                if not isinstance(metric, str) or _METRIC_PATTERN.fullmatch(metric) is None:
                    raise ResourceContractError(f"{field_name} metric is malformed")
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or value < 0
                ):
                    raise ResourceContractError(f"{field_name} value is invalid")
                copied[metric] = float(value)
            object.__setattr__(self, field_name, MappingProxyType(dict(sorted(copied.items()))))
        for metric, reduced in self.reduced_available.items():
            required = self.required_available.get(metric)
            if required is None or reduced >= required:
                raise ResourceContractError(
                    "Reduced thresholds must be lower than an exact required threshold"
                )
        for metric, reduced in self.reduced_device_available.items():
            required = self.required_device_available.get(metric)
            if required is None or reduced >= required:
                raise ResourceContractError(
                    "Reduced device thresholds must be lower than an exact requirement"
                )
        if self.required_device_kind is not None and (
            not isinstance(self.required_device_kind, str)
            or _KIND_PATTERN.fullmatch(self.required_device_kind) is None
        ):
            raise ResourceContractError("required_device_kind is malformed")
        if (
            self.required_device_features or self.required_device_available
        ) and self.required_device_kind is None:
            raise ResourceContractError(
                "Device feature or capacity requirements require required_device_kind"
            )
        for field_name in (
            "required_device_features",
            "required_loaded_model_refs",
            "required_installed_tool_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_sequence(cast(Sequence[str], getattr(self, field_name)), field_name),
            )
        if not isinstance(self.required_artifact_refs, tuple) or not all(
            isinstance(item, ResourceArtifactLocality)
            for item in self.required_artifact_refs
        ):
            raise ResourceContractError(
                "required_artifact_refs must contain exact Artifact evidence"
            )
        if (
            len(self.required_artifact_refs) > 256
            or len(set(self.required_artifact_refs))
            != len(self.required_artifact_refs)
        ):
            raise ResourceContractError(
                "required_artifact_refs is duplicated or unbounded"
            )
        object.__setattr__(
            self,
            "required_artifact_refs",
            tuple(sorted(self.required_artifact_refs)),
        )
        if not isinstance(self.required_workspace_refs, tuple) or not all(
            isinstance(item, ResourceWorkspaceLocality)
            for item in self.required_workspace_refs
        ):
            raise ResourceContractError(
                "required_workspace_refs must contain Project-scoped workspace evidence"
            )
        if (
            len(self.required_workspace_refs) > 256
            or len(set(self.required_workspace_refs))
            != len(self.required_workspace_refs)
        ):
            raise ResourceContractError(
                "required_workspace_refs is duplicated or unbounded"
            )
        object.__setattr__(
            self,
            "required_workspace_refs",
            tuple(sorted(self.required_workspace_refs)),
        )
        if self.maximum_cost is not None and (
            isinstance(self.maximum_cost, bool)
            or not isinstance(self.maximum_cost, (int, float))
            or not math.isfinite(float(self.maximum_cost))
            or self.maximum_cost < 0
        ):
            raise ResourceContractError("maximum_cost is invalid")


@dataclass(frozen=True)
class ResourceFitEvaluation:
    """Evidence-backed result with exact causes and immutable evidence identity."""

    classification: ResourceFit
    resource_ref: ResourceRef
    snapshot_ref: ResourceSnapshotRef
    snapshot_record_sha256: str
    causes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.classification, ResourceFit):
            raise TypeError("classification must be ResourceFit")
        if not isinstance(self.resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        if not isinstance(self.snapshot_ref, ResourceSnapshotRef):
            raise TypeError("snapshot_ref must be ResourceSnapshotRef")
        if self.snapshot_ref.resource_ref != self.resource_ref:
            raise ResourceScopeError("Fit evidence Resource mismatch")
        if _SHA256_PATTERN.fullmatch(self.snapshot_record_sha256) is None:
            raise ResourceContractError("snapshot_record_sha256 is malformed")
        object.__setattr__(self, "causes", _freeze_text_sequence(self.causes, "causes"))
        if not self.causes:
            raise ResourceContractError("Fit evaluation requires at least one cause")


def _fit_result(
    classification: ResourceFit,
    snapshot: ResourceSnapshot,
    causes: Sequence[str],
) -> ResourceFitEvaluation:
    return ResourceFitEvaluation(
        classification=classification,
        resource_ref=snapshot.resource_ref,
        snapshot_ref=snapshot.snapshot_ref,
        snapshot_record_sha256=snapshot.record_sha256,
        causes=tuple(causes),
    )


def _known_value(
    values: Mapping[str, ResourceQuantity], metric: str
) -> float | None:
    quantity = values.get(metric)
    if quantity is None or quantity.source_kind is QuantitySource.UNKNOWN:
        return None
    assert quantity.value is not None
    return float(quantity.value)


def evaluateResourceFit(
    snapshot: ResourceSnapshot,
    request: ResourceFitRequest,
    *,
    at: str | None = None,
) -> ResourceFitEvaluation:
    """Classify technical fit without changing Task or Capability semantics."""

    if not isinstance(snapshot, ResourceSnapshot):
        raise TypeError("snapshot must be ResourceSnapshot")
    if not isinstance(request, ResourceFitRequest):
        raise TypeError("request must be ResourceFitRequest")
    if snapshot.failure_causes:
        return _fit_result(
            ResourceFit.UNKNOWN,
            snapshot,
            tuple(f"observer_failure:{cause}" for cause in snapshot.failure_causes),
        )
    if not snapshot.is_fresh(at):
        return _fit_result(ResourceFit.UNKNOWN, snapshot, ("snapshot_stale",))
    if snapshot.health is ResourceHealth.UNKNOWN:
        return _fit_result(ResourceFit.UNKNOWN, snapshot, ("resource_health_unknown",))
    if snapshot.health is ResourceHealth.UNHEALTHY:
        return _fit_result(
            ResourceFit.TEMPORARILY_UNAVAILABLE,
            snapshot,
            ("resource_unhealthy",),
        )
    if snapshot.health is ResourceHealth.DEGRADED:
        return _fit_result(
            ResourceFit.TEMPORARILY_UNAVAILABLE,
            snapshot,
            ("resource_degraded",),
        )

    unknown: list[str] = []
    hard_failure: list[str] = []
    temporary: list[str] = []
    reduced: list[str] = []
    for metric, required in request.required_effective.items():
        actual = _known_value(snapshot.effective_capacity, metric)
        if actual is None:
            unknown.append(f"effective_unknown:{metric}")
        elif actual < required:
            hard_failure.append(f"effective_insufficient:{metric}")
    for metric, required in request.required_available.items():
        actual = _known_value(snapshot.available_capacity, metric)
        if actual is None:
            unknown.append(f"available_unknown:{metric}")
            continue
        if actual >= required:
            continue
        reduced_minimum = request.reduced_available.get(metric)
        if reduced_minimum is not None and actual >= reduced_minimum:
            reduced.append(f"explicit_reduced_threshold:{metric}")
            continue
        effective = _known_value(snapshot.effective_capacity, metric)
        if effective is None:
            unknown.append(f"effective_unknown:{metric}")
        elif effective >= required:
            temporary.append(f"currently_unavailable:{metric}")
        else:
            hard_failure.append(f"resource_cannot_satisfy:{metric}")
    for metric, maximum in request.maximum_pressure.items():
        actual = _known_value(snapshot.pressure, metric)
        if actual is None:
            unknown.append(f"pressure_unknown:{metric}")
        elif actual > maximum:
            temporary.append(f"pressure_exceeded:{metric}")

    if request.required_device_kind is not None:
        matching_devices = tuple(
            item
            for item in snapshot.devices
            if item.device_kind == request.required_device_kind
            and set(request.required_device_features).issubset(item.features)
        )
        healthy_devices = tuple(
            item for item in matching_devices if item.health is ResourceHealth.HEALTHY
        )
        if not matching_devices:
            hard_failure.append(f"device_unavailable:{request.required_device_kind}")
        elif healthy_devices:
            pass
        elif any(item.health is ResourceHealth.UNKNOWN for item in matching_devices):
            unknown.append(f"device_health_unknown:{request.required_device_kind}")
        else:
            temporary.append(f"device_unhealthy:{request.required_device_kind}")
        if healthy_devices and request.required_device_available:
            exact_device = False
            reduced_device = False
            temporary_device = False
            unknown_device = False
            for device in healthy_devices:
                device_exact = True
                device_reduced = False
                device_temporary = False
                device_unknown = False
                for metric, required in request.required_device_available.items():
                    actual = _known_value(device.available_capacity, metric)
                    if actual is None:
                        device_unknown = True
                        device_exact = False
                        continue
                    if actual >= required:
                        continue
                    device_exact = False
                    reduced_minimum = request.reduced_device_available.get(metric)
                    if reduced_minimum is not None and actual >= reduced_minimum:
                        device_reduced = True
                        continue
                    device_effective = _known_value(device.effective_capacity, metric)
                    if device_effective is None:
                        device_unknown = True
                    elif device_effective >= required:
                        device_temporary = True
                exact_device = exact_device or device_exact
                reduced_device = reduced_device or (
                    not device_unknown and not device_temporary and device_reduced
                )
                temporary_device = temporary_device or device_temporary
                unknown_device = unknown_device or device_unknown
            if exact_device:
                pass
            elif reduced_device:
                reduced.append(
                    f"explicit_reduced_device_threshold:{request.required_device_kind}"
                )
            elif temporary_device:
                temporary.append(
                    f"device_currently_unavailable:{request.required_device_kind}"
                )
            elif unknown_device:
                unknown.append(
                    f"device_capacity_unknown:{request.required_device_kind}"
                )
            else:
                hard_failure.append(
                    f"device_cannot_satisfy:{request.required_device_kind}"
                )

    locality_checks = (
        (
            request.required_loaded_model_refs,
            snapshot.locality.loaded_model_refs,
            "loaded_model_refs",
            "loaded_model_missing",
        ),
        (
            request.required_installed_tool_refs,
            snapshot.locality.installed_tool_refs,
            "installed_tool_refs",
            "installed_tool_missing",
        ),
        (
            request.required_artifact_refs,
            snapshot.locality.local_artifact_refs,
            "local_artifact_refs",
            "artifact_not_local",
        ),
        (
            request.required_workspace_refs,
            snapshot.locality.local_workspace_refs,
            "local_workspace_refs",
            "workspace_not_local",
        ),
    )
    for required_refs, actual_refs, dimension, cause in locality_checks:
        if required_refs and dimension not in snapshot.locality.observed_dimensions:
            unknown.append(f"locality_unknown:{dimension}")
            continue
        for missing in sorted(
            set(required_refs) - set(actual_refs),
            key=lambda item: str(item),
        ):
            if isinstance(missing, str):
                missing_value = missing
            elif isinstance(missing, ResourceArtifactLocality):
                missing_value = missing.value
            elif isinstance(missing, ResourceWorkspaceLocality):
                missing_value = missing.value
            else:
                raise ResourceContractError("Locality requirement type is invalid")
            hard_failure.append(f"{cause}:{missing_value}")
    if request.maximum_cost is not None:
        if snapshot.known_cost.source_kind is QuantitySource.UNKNOWN:
            unknown.append("cost_unknown")
        else:
            assert snapshot.known_cost.value is not None
            if float(snapshot.known_cost.value) > request.maximum_cost:
                hard_failure.append("cost_exceeds_maximum")

    if unknown:
        return _fit_result(ResourceFit.UNKNOWN, snapshot, unknown)
    if hard_failure:
        return _fit_result(ResourceFit.REQUIRES_OTHER_RESOURCE, snapshot, hard_failure)
    if temporary:
        return _fit_result(ResourceFit.TEMPORARILY_UNAVAILABLE, snapshot, temporary)
    if reduced:
        return _fit_result(ResourceFit.FIT_REDUCED, snapshot, reduced)
    return _fit_result(ResourceFit.FIT, snapshot, ("all_requirements_satisfied",))


class ResourceService:
    """Durable Project-scoped Resource identities and append-only observations."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
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
                CREATE TABLE IF NOT EXISTS resources (
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    resource_kind TEXT NOT NULL,
                    locality_ref TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    resource_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, resource_id),
                    UNIQUE (project_id, resource_id, record_sha256),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS resource_snapshots (
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    observer_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    fresh_until TEXT NOT NULL,
                    health TEXT NOT NULL,
                    observation_sha256 TEXT NOT NULL,
                    previous_record_sha256 TEXT,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, resource_id, snapshot_id),
                    UNIQUE (project_id, resource_id, sequence),
                    UNIQUE (project_id, resource_id, snapshot_id, record_sha256),
                    FOREIGN KEY (project_id, resource_id)
                        REFERENCES resources(project_id, resource_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS resource_snapshot_heads (
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    head_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, resource_id),
                    FOREIGN KEY (project_id, resource_id, snapshot_id, record_sha256)
                        REFERENCES resource_snapshots(
                            project_id, resource_id, snapshot_id, record_sha256
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS resource_snapshot_artifact_bindings (
                    project_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        project_id, resource_id, snapshot_id,
                        artifact_id, artifact_revision
                    ),
                    FOREIGN KEY (project_id, resource_id, snapshot_id)
                        REFERENCES resource_snapshots(
                            project_id, resource_id, snapshot_id
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS resources_no_update
                BEFORE UPDATE ON resources
                BEGIN SELECT RAISE(ABORT, 'Resource identity and configuration are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS resources_no_delete
                BEFORE DELETE ON resources
                BEGIN SELECT RAISE(ABORT, 'Resource identity cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS resource_snapshots_no_update
                BEFORE UPDATE ON resource_snapshots
                BEGIN SELECT RAISE(ABORT, 'ResourceSnapshot evidence is immutable'); END;

                CREATE TRIGGER IF NOT EXISTS resource_snapshots_no_delete
                BEFORE DELETE ON resource_snapshots
                BEGIN SELECT RAISE(ABORT, 'ResourceSnapshot evidence cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS resource_snapshot_artifact_bindings_no_update
                BEFORE UPDATE ON resource_snapshot_artifact_bindings
                BEGIN SELECT RAISE(ABORT, 'ResourceSnapshot Artifact bindings are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS resource_snapshot_artifact_bindings_no_delete
                BEFORE DELETE ON resource_snapshot_artifact_bindings
                BEGIN SELECT RAISE(ABORT, 'ResourceSnapshot Artifact bindings cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS resource_snapshot_heads_no_delete
                BEFORE DELETE ON resource_snapshot_heads
                BEGIN SELECT RAISE(ABORT, 'ResourceSnapshot head cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _scoped_record_id(kind: str, record_sha256: str) -> str:
        return "rec_" + hashlib.sha256(
            f"resource:{kind}:{record_sha256}".encode("utf-8")
        ).hexdigest()[:32]

    @staticmethod
    def _resource_from_row(row: sqlite3.Row) -> Resource:
        raw = row["resource_json"]
        if not isinstance(raw, str):
            raise ResourceIntegrityError("Persisted Resource JSON is malformed")
        try:
            payload = cast(object, json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ResourceIntegrityError("Persisted Resource JSON is malformed") from exc
        resource = Resource.from_payload(payload)
        if (
            row["project_id"] != resource.project_ref.value
            or row["resource_id"] != resource.resource_ref.resource_id
            or row["semantic_digest"] != resource.semantic_digest
            or row["record_sha256"] != resource.record_sha256
            or row["resource_kind"] != resource.resource_kind
            or row["locality_ref"] != resource.locality_ref
            or row["created_at"] != resource.created_at
        ):
            raise ResourceIntegrityError("Persisted Resource row mismatch")
        return resource

    @staticmethod
    def _snapshot_from_row(row: sqlite3.Row) -> ResourceSnapshot:
        raw = row["snapshot_json"]
        if not isinstance(raw, str):
            raise ResourceIntegrityError("Persisted ResourceSnapshot JSON is malformed")
        try:
            payload = cast(object, json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ResourceIntegrityError("Persisted ResourceSnapshot JSON is malformed") from exc
        snapshot = ResourceSnapshot.from_payload(payload)
        if (
            row["project_id"] != snapshot.project_ref.value
            or row["resource_id"] != snapshot.resource_ref.resource_id
            or row["snapshot_id"] != snapshot.snapshot_ref.snapshot_id
            or row["sequence"] != snapshot.sequence
            or row["observer_id"] != snapshot.observer_id
            or row["observed_at"] != snapshot.observed_at
            or row["fresh_until"] != snapshot.fresh_until
            or row["health"] != snapshot.health.value
            or row["observation_sha256"] != snapshot.observation_sha256
            or row["previous_record_sha256"] != snapshot.previous_record_sha256
            or row["semantic_digest"] != snapshot.semantic_digest
            or row["record_sha256"] != snapshot.record_sha256
        ):
            raise ResourceIntegrityError("Persisted ResourceSnapshot row mismatch")
        return snapshot

    @classmethod
    def _snapshot_from_head_row(cls, row: sqlite3.Row) -> ResourceSnapshot:
        snapshot = cls._snapshot_from_row(row)
        updated_at = row["head_updated_at"]
        head_sha256 = row["head_sha256"]
        if not isinstance(updated_at, str) or not isinstance(head_sha256, str):
            raise ResourceIntegrityError("ResourceSnapshot head is malformed")
        expected_head_sha256 = _sha256(
            {
                "record_sha256": snapshot.record_sha256,
                "resource_ref": snapshot.resource_ref.value,
                "sequence": snapshot.sequence,
                "snapshot_ref": snapshot.snapshot_ref.value,
                "updated_at": updated_at,
            }
        )
        if (
            row["head_snapshot_id"] != snapshot.snapshot_ref.snapshot_id
            or row["head_sequence"] != snapshot.sequence
            or row["maximum_sequence"] != snapshot.sequence
            or row["head_record_sha256"] != snapshot.record_sha256
            or head_sha256 != expected_head_sha256
        ):
            raise ResourceIntegrityError("ResourceSnapshot head digest mismatch")
        return snapshot

    @classmethod
    def _verify_resource_evidence(
        cls,
        connection: sqlite3.Connection,
        resource: Resource,
    ) -> None:
        record_id = cls._scoped_record_id("resource", resource.record_sha256)
        row = connection.execute(
            """
            SELECT content_sha256 FROM project_scoped_records
            WHERE project_id = ? AND record_id = ?
            """,
            (resource.project_ref.value, record_id),
        ).fetchone()
        if row is None or row["content_sha256"] != resource.record_sha256:
            raise ResourceIntegrityError(
                "Resource Project-scoped evidence is missing or changed"
            )

    def _verify_snapshot_chain(
        self,
        connection: sqlite3.Connection,
        snapshot: ResourceSnapshot,
    ) -> None:
        resource_row = connection.execute(
            "SELECT * FROM resources WHERE project_id = ? AND resource_id = ?",
            (snapshot.project_ref.value, snapshot.resource_ref.resource_id),
        ).fetchone()
        if resource_row is None:
            raise ResourceIntegrityError("ResourceSnapshot parent Resource is missing")
        resource = self._resource_from_row(resource_row)
        self._verify_resource_evidence(connection, resource)
        if resource.record_sha256 != snapshot.resource_record_sha256:
            raise ResourceIntegrityError("ResourceSnapshot parent Resource digest mismatch")
        rows = connection.execute(
            """
            SELECT * FROM resource_snapshots
            WHERE project_id = ? AND resource_id = ? AND sequence <= ?
            ORDER BY sequence ASC
            """,
            (
                snapshot.project_ref.value,
                snapshot.resource_ref.resource_id,
                snapshot.sequence,
            ),
        ).fetchall()
        if len(rows) != snapshot.sequence:
            raise ResourceIntegrityError("ResourceSnapshot provenance chain has a gap")
        previous_sha256: str | None = None
        current: ResourceSnapshot | None = None
        scoped_evidence = (
            ("resource", resource.record_sha256),
            *tuple(
                ("snapshot", self._snapshot_from_row(row).record_sha256)
                for row in rows
            ),
        )
        for expected_sequence, row in enumerate(rows, start=1):
            current = self._snapshot_from_row(row)
            if (
                current.sequence != expected_sequence
                or current.previous_record_sha256 != previous_sha256
                or current.resource_record_sha256 != resource.record_sha256
            ):
                raise ResourceIntegrityError(
                    "ResourceSnapshot provenance chain is malformed"
                )
            previous_sha256 = current.record_sha256
            self._validate_locality_evidence(
                connection,
                resource,
                current.locality,
                snapshot_ref=current.snapshot_ref,
            )
        if current != snapshot:
            raise ResourceIntegrityError("ResourceSnapshot chain endpoint mismatch")
        for kind, record_sha256 in scoped_evidence:
            record_id = self._scoped_record_id(kind, record_sha256)
            scoped_row = connection.execute(
                """
                SELECT content_sha256 FROM project_scoped_records
                WHERE project_id = ? AND record_id = ?
                """,
                (snapshot.project_ref.value, record_id),
            ).fetchone()
            if scoped_row is None or scoped_row["content_sha256"] != record_sha256:
                raise ResourceIntegrityError(
                    "ResourceSnapshot Project-scoped evidence is missing or changed"
                )

    def _validate_locality_evidence(
        self,
        connection: sqlite3.Connection,
        resource: Resource,
        locality: ResourceLocality,
        *,
        snapshot_ref: ResourceSnapshotRef | None = None,
    ) -> None:
        for artifact in locality.local_artifact_refs:
            if artifact.project_ref != resource.project_ref:
                raise ResourceScopeError("Artifact locality Project scope mismatch")
            try:
                persisted_artifact = self.artifacts._fetch_artifact(
                    connection,
                    artifact.artifact_ref,
                )
            except ArtifactError as exc:
                raise ResourceIntegrityError(
                    "Artifact locality evidence is missing or corrupt"
                ) from exc
            if persisted_artifact.record_sha256 != artifact.artifact_record_sha256:
                raise ResourceIntegrityError("Artifact locality record digest mismatch")
        for workspace in locality.local_workspace_refs:
            if workspace.project_ref != resource.project_ref:
                raise ResourceScopeError("Workspace locality Project scope mismatch")
        if snapshot_ref is not None:
            binding_rows = connection.execute(
                """
                SELECT artifact_id, artifact_revision, artifact_record_sha256
                FROM resource_snapshot_artifact_bindings
                WHERE project_id = ? AND resource_id = ? AND snapshot_id = ?
                ORDER BY artifact_id, artifact_revision
                """,
                (
                    snapshot_ref.project_ref.value,
                    snapshot_ref.resource_ref.resource_id,
                    snapshot_ref.snapshot_id,
                ),
            ).fetchall()
            persisted_bindings = tuple(
                ResourceArtifactLocality(
                    ArtifactRef(
                        snapshot_ref.project_ref,
                        cast(str, row["artifact_id"]),
                        cast(int, row["artifact_revision"]),
                    ),
                    cast(str, row["artifact_record_sha256"]),
                )
                for row in binding_rows
            )
            if persisted_bindings != locality.local_artifact_refs:
                raise ResourceIntegrityError(
                    "ResourceSnapshot Artifact locality bindings are inconsistent"
                )

    def register_resource(
        self, requesting_access: ProjectAccess, resource: Resource
    ) -> Resource:
        if not isinstance(resource, Resource):
            raise TypeError("resource must be Resource")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            authorized = ProjectStore._authorize(connection, requesting_access)
            if authorized != resource.project_ref:
                raise ResourceScopeError("Resource Project scope mismatch")
            row = connection.execute(
                "SELECT * FROM resources WHERE project_id = ? AND resource_id = ?",
                (resource.project_ref.value, resource.resource_ref.resource_id),
            ).fetchone()
            if row is not None:
                existing = self._resource_from_row(row)
                if existing.record_sha256 != resource.record_sha256:
                    raise ResourceConflictError("Resource identity already has different configuration")
                self._verify_resource_evidence(connection, existing)
                connection.commit()
                return existing
            connection.execute(
                """
                INSERT INTO resources (
                    project_id, resource_id, resource_kind, locality_ref,
                    created_at, semantic_digest, record_sha256, resource_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource.project_ref.value,
                    resource.resource_ref.resource_id,
                    resource.resource_kind,
                    resource.locality_ref,
                    resource.created_at,
                    resource.semantic_digest,
                    resource.record_sha256,
                    _canonical_json(resource.to_payload()),
                ),
            )
            connection.execute(
                """
                INSERT INTO project_scoped_records (project_id, record_id, content_sha256)
                VALUES (?, ?, ?)
                """,
                (
                    resource.project_ref.value,
                    self._scoped_record_id("resource", resource.record_sha256),
                    resource.record_sha256,
                ),
            )
            connection.commit()
            return resource
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_resource(
        self, requesting_access: ProjectAccess, resource_ref: ResourceRef
    ) -> Resource:
        if not isinstance(resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            authorized = ProjectStore._authorize(connection, requesting_access)
            if authorized != resource_ref.project_ref:
                raise ResourceScopeError("Resource Project scope mismatch")
            row = connection.execute(
                "SELECT * FROM resources WHERE project_id = ? AND resource_id = ?",
                (resource_ref.project_ref.value, resource_ref.resource_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("Resource not found")
            resource = self._resource_from_row(row)
            self._verify_resource_evidence(connection, resource)
            connection.commit()
            return resource
        finally:
            connection.close()

    @staticmethod
    def _observer_failure(exc: Exception) -> ResourceObservation:
        cause = f"{type(exc).__name__}:{str(exc)}"
        if len(cause) > _TEXT_LIMIT:
            cause = cause[:_TEXT_LIMIT]
        if any(ord(character) < 32 for character in cause):
            cause = f"{type(exc).__name__}:observer failed with control characters"
        return ResourceObservation(
            observed_at=_now_utc(),
            fresh_for_seconds=0,
            health=ResourceHealth.UNKNOWN,
            failure_causes=(cause,),
            known_cost=ResourceQuantity.unknown(
                "usd_per_hour", "observer://failure/cost-unknown"
            ),
        )

    def observe_resource(
        self,
        requesting_access: ProjectAccess,
        resource_ref: ResourceRef,
        observer: ResourceObserver,
    ) -> ResourceSnapshot:
        if not isinstance(observer, ResourceObserver):
            raise TypeError("observer must be ResourceObserver")
        resource = self.get_resource(requesting_access, resource_ref)
        try:
            observation = observer.observe(resource)
            if not isinstance(observation, ResourceObservation):
                raise ResourceContractError("Observer returned an invalid result")
        except Exception as exc:
            observation = self._observer_failure(exc)
        return self.record_observation(
            requesting_access,
            resource_ref,
            observer.observer_id,
            observation,
            expected_resource_record_sha256=resource.record_sha256,
        )

    def record_observation(
        self,
        requesting_access: ProjectAccess,
        resource_ref: ResourceRef,
        observer_id: str,
        observation: ResourceObservation,
        *,
        expected_resource_record_sha256: str | None = None,
    ) -> ResourceSnapshot:
        if not isinstance(resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        if not isinstance(observation, ResourceObservation):
            raise TypeError("observation must be ResourceObservation")
        if not isinstance(observer_id, str) or _KIND_PATTERN.fullmatch(observer_id) is None:
            raise ResourceContractError("observer_id is malformed")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            authorized = ProjectStore._authorize(connection, requesting_access)
            if authorized != resource_ref.project_ref:
                raise ResourceScopeError("Resource Project scope mismatch")
            resource_row = connection.execute(
                "SELECT * FROM resources WHERE project_id = ? AND resource_id = ?",
                (resource_ref.project_ref.value, resource_ref.resource_id),
            ).fetchone()
            if resource_row is None:
                raise ResourceNotFoundError("Resource not found")
            resource = self._resource_from_row(resource_row)
            if (
                expected_resource_record_sha256 is not None
                and expected_resource_record_sha256 != resource.record_sha256
            ):
                raise ResourceConflictError("Resource changed while observation was running")
            head_row = connection.execute(
                """
                SELECT snapshots.*,
                       heads.snapshot_id AS head_snapshot_id,
                       heads.sequence AS head_sequence,
                       heads.record_sha256 AS head_record_sha256,
                       heads.updated_at AS head_updated_at,
                       heads.head_sha256 AS head_sha256,
                       (SELECT MAX(history.sequence)
                          FROM resource_snapshots AS history
                         WHERE history.project_id = heads.project_id
                           AND history.resource_id = heads.resource_id)
                           AS maximum_sequence
                FROM resource_snapshot_heads AS heads
                JOIN resource_snapshots AS snapshots
                  ON snapshots.project_id = heads.project_id
                 AND snapshots.resource_id = heads.resource_id
                 AND snapshots.snapshot_id = heads.snapshot_id
                 AND snapshots.record_sha256 = heads.record_sha256
                WHERE heads.project_id = ? AND heads.resource_id = ?
                """,
                (resource_ref.project_ref.value, resource_ref.resource_id),
            ).fetchone()
            previous = (
                None if head_row is None else self._snapshot_from_head_row(head_row)
            )
            if previous is not None:
                self._verify_snapshot_chain(connection, previous)
            self._validate_locality_evidence(
                connection,
                resource,
                observation.locality,
            )
            observation_sha = _sha256(observation.to_payload())
            if (
                previous is not None
                and previous.observer_id == observer_id
                and previous.observation_sha256 == observation_sha
            ):
                connection.commit()
                return previous
            previous_sha = None if previous is None else previous.record_sha256
            sequence = 1 if previous is None else previous.sequence + 1
            snapshot_id = "rsn_" + _sha256(
                {
                    "observation_sha256": observation_sha,
                    "previous_record_sha256": previous_sha,
                    "resource_record_sha256": resource.record_sha256,
                    "resource_ref": resource_ref.value,
                }
            )[:32]
            snapshot = ResourceSnapshot(
                snapshot_ref=ResourceSnapshotRef(resource_ref, snapshot_id),
                resource_record_sha256=resource.record_sha256,
                sequence=sequence,
                observer_id=observer_id,
                observation=observation,
                previous_record_sha256=previous_sha,
            )
            connection.execute(
                """
                INSERT INTO resource_snapshots (
                    project_id, resource_id, snapshot_id, sequence,
                    observer_id, observed_at, fresh_until, health,
                    observation_sha256, previous_record_sha256,
                    semantic_digest, record_sha256, snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource_ref.project_ref.value,
                    resource_ref.resource_id,
                    snapshot.snapshot_ref.snapshot_id,
                    snapshot.sequence,
                    snapshot.observer_id,
                    snapshot.observed_at,
                    snapshot.fresh_until,
                    snapshot.health.value,
                    snapshot.observation_sha256,
                    snapshot.previous_record_sha256,
                    snapshot.semantic_digest,
                    snapshot.record_sha256,
                    _canonical_json(snapshot.to_payload()),
                ),
            )
            connection.executemany(
                """
                INSERT INTO resource_snapshot_artifact_bindings (
                    project_id, resource_id, snapshot_id,
                    artifact_id, artifact_revision, artifact_record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        snapshot.project_ref.value,
                        snapshot.resource_ref.resource_id,
                        snapshot.snapshot_ref.snapshot_id,
                        artifact.artifact_ref.artifact_id,
                        artifact.artifact_ref.revision,
                        artifact.artifact_record_sha256,
                    )
                    for artifact in snapshot.locality.local_artifact_refs
                ),
            )
            timestamp = _now_utc()
            head_sha = _sha256(
                {
                    "record_sha256": snapshot.record_sha256,
                    "resource_ref": resource_ref.value,
                    "sequence": snapshot.sequence,
                    "snapshot_ref": snapshot.snapshot_ref.value,
                    "updated_at": timestamp,
                }
            )
            if previous is None:
                connection.execute(
                    """
                    INSERT INTO resource_snapshot_heads (
                        project_id, resource_id, snapshot_id, sequence,
                        record_sha256, updated_at, head_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resource_ref.project_ref.value,
                        resource_ref.resource_id,
                        snapshot.snapshot_ref.snapshot_id,
                        snapshot.sequence,
                        snapshot.record_sha256,
                        timestamp,
                        head_sha,
                    ),
                )
            else:
                result = connection.execute(
                    """
                    UPDATE resource_snapshot_heads
                    SET snapshot_id = ?, sequence = ?, record_sha256 = ?,
                        updated_at = ?, head_sha256 = ?
                    WHERE project_id = ? AND resource_id = ?
                      AND snapshot_id = ? AND sequence = ? AND record_sha256 = ?
                    """,
                    (
                        snapshot.snapshot_ref.snapshot_id,
                        snapshot.sequence,
                        snapshot.record_sha256,
                        timestamp,
                        head_sha,
                        resource_ref.project_ref.value,
                        resource_ref.resource_id,
                        previous.snapshot_ref.snapshot_id,
                        previous.sequence,
                        previous.record_sha256,
                    ),
                )
                if result.rowcount != 1:
                    raise ResourceConflictError("ResourceSnapshot head changed concurrently")
            connection.execute(
                """
                INSERT INTO project_scoped_records (project_id, record_id, content_sha256)
                VALUES (?, ?, ?)
                """,
                (
                    resource_ref.project_ref.value,
                    self._scoped_record_id("snapshot", snapshot.record_sha256),
                    snapshot.record_sha256,
                ),
            )
            connection.commit()
            return snapshot
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_snapshot(
        self,
        requesting_access: ProjectAccess,
        snapshot_ref: ResourceSnapshotRef,
    ) -> ResourceSnapshot:
        if not isinstance(snapshot_ref, ResourceSnapshotRef):
            raise TypeError("snapshot_ref must be ResourceSnapshotRef")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            authorized = ProjectStore._authorize(connection, requesting_access)
            if authorized != snapshot_ref.project_ref:
                raise ResourceScopeError("ResourceSnapshot Project scope mismatch")
            row = connection.execute(
                """
                SELECT * FROM resource_snapshots
                WHERE project_id = ? AND resource_id = ? AND snapshot_id = ?
                """,
                (
                    snapshot_ref.project_ref.value,
                    snapshot_ref.resource_ref.resource_id,
                    snapshot_ref.snapshot_id,
                ),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("ResourceSnapshot not found")
            snapshot = self._snapshot_from_row(row)
            self._verify_snapshot_chain(connection, snapshot)
            connection.commit()
            return snapshot
        finally:
            connection.close()

    def latest_snapshot(
        self,
        requesting_access: ProjectAccess,
        resource_ref: ResourceRef,
        *,
        require_fresh: bool = True,
        at: str | None = None,
    ) -> ResourceSnapshot:
        if not isinstance(resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            authorized = ProjectStore._authorize(connection, requesting_access)
            if authorized != resource_ref.project_ref:
                raise ResourceScopeError("ResourceSnapshot Project scope mismatch")
            row = connection.execute(
                """
                SELECT snapshots.*,
                       heads.snapshot_id AS head_snapshot_id,
                       heads.sequence AS head_sequence,
                       heads.record_sha256 AS head_record_sha256,
                       heads.updated_at AS head_updated_at,
                       heads.head_sha256 AS head_sha256,
                       (SELECT MAX(history.sequence)
                          FROM resource_snapshots AS history
                         WHERE history.project_id = heads.project_id
                           AND history.resource_id = heads.resource_id)
                           AS maximum_sequence
                FROM resource_snapshot_heads AS heads
                JOIN resource_snapshots AS snapshots
                  ON snapshots.project_id = heads.project_id
                 AND snapshots.resource_id = heads.resource_id
                 AND snapshots.snapshot_id = heads.snapshot_id
                 AND snapshots.record_sha256 = heads.record_sha256
                WHERE heads.project_id = ? AND heads.resource_id = ?
                """,
                (resource_ref.project_ref.value, resource_ref.resource_id),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("Resource has no observations")
            snapshot = self._snapshot_from_head_row(row)
            self._verify_snapshot_chain(connection, snapshot)
            if require_fresh and not snapshot.is_fresh(at):
                raise ResourceStaleError("Latest ResourceSnapshot is stale")
            connection.commit()
            return snapshot
        finally:
            connection.close()

    def list_snapshots(
        self,
        requesting_access: ProjectAccess,
        resource_ref: ResourceRef,
    ) -> tuple[ResourceSnapshot, ...]:
        if not isinstance(resource_ref, ResourceRef):
            raise TypeError("resource_ref must be ResourceRef")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            authorized = ProjectStore._authorize(connection, requesting_access)
            if authorized != resource_ref.project_ref:
                raise ResourceScopeError("ResourceSnapshot Project scope mismatch")
            rows = connection.execute(
                """
                SELECT * FROM resource_snapshots
                WHERE project_id = ? AND resource_id = ?
                ORDER BY sequence ASC
                """,
                (resource_ref.project_ref.value, resource_ref.resource_id),
            ).fetchall()
            snapshots = tuple(self._snapshot_from_row(row) for row in rows)
            if snapshots:
                self._verify_snapshot_chain(connection, snapshots[-1])
            connection.commit()
            return snapshots
        finally:
            connection.close()


__all__ = [
    "FakeResourceObserver",
    "LocalResourceObserver",
    "QuantitySource",
    "Resource",
    "ResourceArtifactLocality",
    "ResourceConflictError",
    "ResourceContractError",
    "ResourceDeviceSnapshot",
    "ResourceError",
    "ResourceFit",
    "ResourceFitEvaluation",
    "ResourceFitRequest",
    "ResourceHealth",
    "ResourceIntegrityError",
    "ResourceLocality",
    "ResourceNotFoundError",
    "ResourceObservation",
    "ResourceObserver",
    "ResourceQuantity",
    "ResourceRef",
    "ResourceScopeError",
    "ResourceService",
    "ResourceSnapshot",
    "ResourceSnapshotRef",
    "ResourceStaleError",
    "ResourceWorkspaceLocality",
    "evaluateResourceFit",
]
