"""Evidence-bounded cache, locality, and placement performance learning.

This module supplies performance hints only.  Project, Artifact, Run, Resource,
and scheduler records remain authoritative and are never represented as caches.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType

from .artifact import ArtifactRef, ContentRef
from .project import ProjectRef
from .resource import ResourceLocality, ResourceRef, ResourceSnapshotRef


_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1024}")
_CACHE_KEY = re.compile(r"cache-key://sha256/[0-9a-f]{64}")
_TIMING_METRICS = (
    "cold_start_seconds",
    "load_seconds",
    "transfer_seconds",
    "execution_seconds",
    "congestion_seconds",
    "fragmentation_seconds",
)
_PLACEMENT_METRICS = frozenset(
    {
        *_TIMING_METRICS,
        "total_seconds",
        "latency_ms",
        "locality_hit_rate",
        "cache_hit_rate",
        "throughput_bytes_per_second",
        "transfer_bytes",
        "rebuild_seconds",
        "memory_bytes",
        "storage_bytes",
        "vram_bytes",
        "reliability",
        "cost",
    }
)
_CURRENT_EVIDENCE = frozenset(
    {
        "OBSERVED",
        "SUPPORTED",
        "STRONG",
    }
)


class PlacementLearningError(ValueError):
    """Placement evidence is malformed, stale, incompatible, or authoritative."""


class PlacementEvidenceState(str, Enum):
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"
    INSUFFICIENT = "INSUFFICIENT"
    OBSERVED = "OBSERVED"
    SUPPORTED = "SUPPORTED"
    STRONG = "STRONG"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"
    DISABLED = "DISABLED"


class CacheAuthority(str, Enum):
    """Authority class of bytes considered by locality optimization."""

    REBUILDABLE = "REBUILDABLE"
    EPHEMERAL = "EPHEMERAL"
    AUTHORITATIVE = "AUTHORITATIVE"


class CacheReuseState(str, Enum):
    UNKNOWN = "UNKNOWN"
    COLD = "COLD"
    WARM = "WARM"
    HIT = "HIT"
    MISS = "MISS"
    STALE = "STALE"
    INCOMPATIBLE = "INCOMPATIBLE"


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise PlacementLearningError("placement evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _key(value: object, label: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise PlacementLearningError(f"{label} is malformed")
    return value


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise PlacementLearningError(f"{label} must be an exact reference")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PlacementLearningError(f"{label} must be a SHA-256 digest")
    return value


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise PlacementLearningError(f"{label} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PlacementLearningError(f"{label} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PlacementLearningError(f"{label} must be a timezone-aware timestamp")
    return parsed


def _fresh_window(observed_at: str, fresh_until: str, label: str) -> None:
    observed = _timestamp(observed_at, f"{label} observed_at")
    fresh = _timestamp(fresh_until, f"{label} fresh_until")
    if fresh <= observed or fresh <= datetime.now(timezone.utc):
        raise PlacementLearningError(f"{label} freshness must be future and follow observation")


def _evidence_refs(values: Sequence[str], label: str, *, required: bool = True) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PlacementLearningError(f"{label} is malformed")
    copied = tuple(values)
    if (required and not copied) or len(copied) > 128 or len(set(copied)) != len(copied):
        raise PlacementLearningError(f"{label} is missing, duplicated, or unbounded")
    for value in copied:
        _ref(value, label)
    return tuple(sorted(copied))


def _metrics(values: Mapping[str, float | None], label: str) -> Mapping[str, float | None]:
    if not isinstance(values, Mapping) or not values or len(values) > 64:
        raise PlacementLearningError(f"{label} is missing, malformed, or unbounded")
    copied: dict[str, float | None] = {}
    for key, value in values.items():
        _key(key, f"{label} key")
        if key not in _PLACEMENT_METRICS:
            raise PlacementLearningError(f"{label} contains unsupported metric {key}")
        if value is None:
            copied[key] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise PlacementLearningError(f"{label} values must be finite or unknown")
        if float(value) < 0.0:
            raise PlacementLearningError(f"{label} values cannot be negative")
        copied[key] = float(value)
    return MappingProxyType(dict(sorted(copied.items())))


def _optional_nonnegative(value: float | int | None, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise PlacementLearningError(f"{label} must be finite or unknown")
    if float(value) < 0.0:
        raise PlacementLearningError(f"{label} cannot be negative")
    return float(value)


def _content_payload(content_ref: ContentRef) -> dict[str, object]:
    if not isinstance(content_ref, ContentRef):
        raise PlacementLearningError("content identity is malformed")
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _locality_payload(locality: ResourceLocality) -> dict[str, object]:
    if not isinstance(locality, ResourceLocality):
        raise PlacementLearningError("Resource locality is malformed")
    return {
        "installed_tools": list(locality.installed_tool_refs),
        "loaded_implementations": list(locality.loaded_model_refs),
        "local_artifacts": [
            {
                "artifact": item.artifact_ref.value,
                "record": item.artifact_record_sha256,
            }
            for item in locality.local_artifact_refs
        ],
        "local_implementations": list(locality.local_model_refs),
        "local_workspaces": [
            {
                "project": item.project_ref.value,
                "workspace": item.workspace_ref,
            }
            for item in locality.local_workspace_refs
        ],
        "observed_dimensions": list(locality.observed_dimensions),
        "warm_caches": list(locality.warm_cache_refs),
    }


def _bind_identity(current: str | None, expected: str, label: str) -> str:
    if current is None:
        return expected
    _sha(current, label)
    if current != expected:
        raise PlacementLearningError(f"{label} does not match exact bound inputs")
    return current


@dataclass(frozen=True)
class CacheIdentity:
    """A privacy-safe key binding all inputs required for cache compatibility."""

    project_ref: ProjectRef
    cache_ref: str
    implementation_ref: str
    source_content_ref: ContentRef
    context_ref: str
    tool_ref: str
    configuration_digest: str
    authority: CacheAuthority = CacheAuthority.REBUILDABLE
    identity_binding: str | None = None
    cache_key: str = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise PlacementLearningError("cache Project is malformed")
        _ref(self.cache_ref, "cache")
        if not self.cache_ref.startswith("cache://"):
            raise PlacementLearningError("only rebuildable cache references may be cache identities")
        for value, label in (
            (self.implementation_ref, "implementation"),
            (self.context_ref, "context"),
            (self.tool_ref, "tool"),
        ):
            _ref(value, label)
        _sha(self.configuration_digest, "configuration digest")
        if not isinstance(self.authority, CacheAuthority):
            raise PlacementLearningError("cache authority class is malformed")
        if self.authority is CacheAuthority.AUTHORITATIVE:
            raise PlacementLearningError("authoritative objects cannot be treated as cache")
        payload = {
            "authority": self.authority.value,
            "cache": self.cache_ref,
            "configuration": self.configuration_digest,
            "context": self.context_ref,
            "implementation": self.implementation_ref,
            "project": self.project_ref.value,
            "source": _content_payload(self.source_content_ref),
            "tool": self.tool_ref,
        }
        binding = _digest(payload)
        object.__setattr__(self, "identity_binding", _bind_identity(self.identity_binding, binding, "cache identity binding"))
        object.__setattr__(self, "cache_key", f"cache-key://sha256/{binding}")
        object.__setattr__(self, "canonical_digest", _digest({"cache_key": self.cache_key, **payload}))

    @property
    def eviction_allowed(self) -> bool:
        return self.authority in {CacheAuthority.REBUILDABLE, CacheAuthority.EPHEMERAL}

    @property
    def correctness_authority_allowed(self) -> bool:
        return False


@dataclass(frozen=True)
class LocalityObservation:
    """Immutable, fresh, exact Resource-locality evidence for one Project."""

    project_ref: ProjectRef
    observation_id: str
    version: int
    resource_snapshot_ref: ResourceSnapshotRef
    resource_snapshot_record_sha256: str
    locality: ResourceLocality
    observed_at: str
    fresh_until: str
    evidence_refs: tuple[str, ...]
    cache_identities: tuple[CacheIdentity, ...] = ()
    measurements: Mapping[str, float | None] = field(default_factory=lambda: MappingProxyType({}))
    output_content_ref: ContentRef | None = None
    output_valid: bool | None = None
    supersedes: str | None = None
    identity_binding: str | None = None
    observation_ref: str = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.resource_snapshot_ref, ResourceSnapshotRef):
            raise PlacementLearningError("locality Project or Resource snapshot is malformed")
        if self.resource_snapshot_ref.resource_ref.project_ref != self.project_ref:
            raise PlacementLearningError("locality snapshot crossed Project scope")
        _key(self.observation_id, "locality observation identity")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise PlacementLearningError("locality observation version must be positive")
        _sha(self.resource_snapshot_record_sha256, "Resource snapshot record digest")
        locality_payload = _locality_payload(self.locality)
        for artifact_locality in self.locality.local_artifact_refs:
            if artifact_locality.artifact_ref.project_ref != self.project_ref:
                raise PlacementLearningError("local Artifact locality crossed Project scope")
        for workspace_locality in self.locality.local_workspace_refs:
            if workspace_locality.project_ref != self.project_ref:
                raise PlacementLearningError("local Workspace locality crossed Project scope")
        refs = _evidence_refs(self.evidence_refs, "locality evidence")
        object.__setattr__(self, "evidence_refs", refs)
        _fresh_window(self.observed_at, self.fresh_until, "locality observation")
        identities = tuple(self.cache_identities)
        if len(identities) > 256 or len({cache_identity.cache_key for cache_identity in identities}) != len(identities):
            raise PlacementLearningError("cache identities are duplicated or unbounded")
        for cache_identity in identities:
            if not isinstance(cache_identity, CacheIdentity) or cache_identity.project_ref != self.project_ref:
                raise PlacementLearningError("cache identity crossed Project scope")
        object.__setattr__(self, "cache_identities", tuple(sorted(identities, key=lambda cache_identity: cache_identity.cache_key)))
        if self.measurements:
            object.__setattr__(self, "measurements", _metrics(self.measurements, "locality measurements"))
        elif not isinstance(self.measurements, Mapping):
            raise PlacementLearningError("locality measurements are malformed")
        else:
            object.__setattr__(self, "measurements", MappingProxyType({}))
        if self.output_content_ref is not None:
            _content_payload(self.output_content_ref)
        if self.output_valid is not None and not isinstance(self.output_valid, bool):
            raise PlacementLearningError("output validity must be true, false, or unknown")
        if self.supersedes is not None:
            _ref(self.supersedes, "superseded locality observation")
        binding_payload = {
            "caches": [item.cache_key for item in self.cache_identities],
            "locality": locality_payload,
            "observation_id": self.observation_id,
            "project": self.project_ref.value,
            "resource": self.resource_snapshot_ref.resource_ref.value,
            "snapshot": self.resource_snapshot_ref.snapshot_id,
            "snapshot_record": self.resource_snapshot_record_sha256,
            "version": self.version,
        }
        binding = _digest(binding_payload)
        object.__setattr__(self, "identity_binding", _bind_identity(self.identity_binding, binding, "locality identity binding"))
        ref = f"locality-observation://{self.project_ref.value}/{self.observation_id}/{self.version}/{binding[:32]}"
        object.__setattr__(self, "observation_ref", ref)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "cache_keys": [item.cache_key for item in self.cache_identities],
            "evidence": list(self.evidence_refs),
            "fresh_until": self.fresh_until,
            "identity_binding": self.identity_binding,
            "locality": _locality_payload(self.locality),
            "measurements": dict(self.measurements),
            "observation": self.observation_ref,
            "observed_at": self.observed_at,
            "output": None if self.output_content_ref is None else _content_payload(self.output_content_ref),
            "output_valid": self.output_valid,
            "project": self.project_ref.value,
            "resource_snapshot": self.resource_snapshot_ref.snapshot_id,
            "resource_snapshot_record": self.resource_snapshot_record_sha256,
            "supersedes": self.supersedes,
        }

    def is_fresh(self, at: datetime | None = None) -> bool:
        point = datetime.now(timezone.utc) if at is None else at
        if point.tzinfo is None or point.utcoffset() is None:
            raise PlacementLearningError("freshness point must be timezone-aware")
        return point < _timestamp(self.fresh_until, "locality fresh_until")


@dataclass(frozen=True)
class PlacementEstimate:
    """Versioned performance estimate for one exact workload placement."""

    project_ref: ProjectRef
    estimate_id: str
    version: int
    workload_ref: str
    workload_digest: str
    artifact_ref: ArtifactRef
    content_ref: ContentRef
    workspace_ref: str
    locality_observation: LocalityObservation
    target_resource_ref: ResourceRef
    resource_identity_digest: str
    metrics: Mapping[str, float | None]
    evidence_refs: tuple[str, ...]
    observed_at: str
    fresh_until: str
    supersedes: str | None
    evidence_state: PlacementEvidenceState = PlacementEvidenceState.OBSERVED
    calibration_ref: str | None = None
    identity_binding: str | None = None
    estimate_ref: str = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.artifact_ref, ArtifactRef):
            raise PlacementLearningError("placement Project or Artifact is malformed")
        if self.artifact_ref.project_ref != self.project_ref:
            raise PlacementLearningError("placement Artifact crossed Project scope")
        _content_payload(self.content_ref)
        _key(self.estimate_id, "placement estimate identity")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise PlacementLearningError("placement estimate version must be positive")
        _ref(self.workload_ref, "placement workload")
        _sha(self.workload_digest, "placement workload digest")
        _ref(self.workspace_ref, "placement Workspace")
        if not isinstance(self.locality_observation, LocalityObservation) or self.locality_observation.project_ref != self.project_ref:
            raise PlacementLearningError("placement locality crossed Project scope")
        if not isinstance(self.target_resource_ref, ResourceRef) or self.target_resource_ref.project_ref != self.project_ref:
            raise PlacementLearningError("placement Resource crossed Project scope")
        if self.locality_observation.resource_snapshot_ref.resource_ref != self.target_resource_ref:
            raise PlacementLearningError("placement Resource differs from locality snapshot")
        _sha(self.resource_identity_digest, "placement Resource identity digest")
        if self.resource_identity_digest != self.locality_observation.resource_snapshot_record_sha256:
            raise PlacementLearningError("placement Resource identity is stale")
        object.__setattr__(self, "metrics", _metrics(self.metrics, "placement metrics"))
        refs = _evidence_refs(self.evidence_refs, "placement evidence")
        object.__setattr__(self, "evidence_refs", refs)
        _fresh_window(self.observed_at, self.fresh_until, "placement estimate")
        if _timestamp(self.fresh_until, "placement fresh_until") > _timestamp(
            self.locality_observation.fresh_until, "locality fresh_until"
        ):
            raise PlacementLearningError("placement estimate outlives its locality evidence")
        if not isinstance(self.evidence_state, PlacementEvidenceState):
            raise PlacementLearningError("placement evidence state is malformed")
        if self.evidence_state.value in _CURRENT_EVIDENCE and not refs:
            raise PlacementLearningError("current placement evidence requires exact evidence refs")
        if self.supersedes is not None:
            _ref(self.supersedes, "superseded placement estimate")
        if self.calibration_ref is not None:
            _ref(self.calibration_ref, "placement calibration")
        binding_payload = {
            "artifact": self.artifact_ref.value,
            "content": _content_payload(self.content_ref),
            "estimate_id": self.estimate_id,
            "locality": self.locality_observation.observation_ref,
            "project": self.project_ref.value,
            "resource": self.target_resource_ref.value,
            "resource_identity": self.resource_identity_digest,
            "version": self.version,
            "workload": self.workload_ref,
            "workload_digest": self.workload_digest,
            "workspace": self.workspace_ref,
        }
        binding = _digest(binding_payload)
        object.__setattr__(self, "identity_binding", _bind_identity(self.identity_binding, binding, "placement identity binding"))
        ref = f"placement-estimate://{self.project_ref.value}/{self.estimate_id}/{self.version}/{binding[:32]}"
        object.__setattr__(self, "estimate_ref", ref)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @property
    def routing_override_allowed(self) -> bool:
        return False

    @property
    def correctness_authority_allowed(self) -> bool:
        return False

    @property
    def estimated_total_seconds(self) -> float | None:
        explicit = self.metrics.get("total_seconds")
        if explicit is not None:
            return explicit
        known = [self.metrics.get(key) for key in _TIMING_METRICS]
        values = [value for value in known if value is not None]
        return None if not values else float(sum(values))

    def payload(self) -> dict[str, object]:
        return {
            "artifact": self.artifact_ref.value,
            "calibration": self.calibration_ref,
            "content": _content_payload(self.content_ref),
            "evidence": list(self.evidence_refs),
            "evidence_state": self.evidence_state.value,
            "estimate": self.estimate_ref,
            "fresh_until": self.fresh_until,
            "identity_binding": self.identity_binding,
            "locality": self.locality_observation.canonical_digest,
            "metrics": dict(self.metrics),
            "observed_at": self.observed_at,
            "project": self.project_ref.value,
            "resource": self.target_resource_ref.value,
            "resource_identity": self.resource_identity_digest,
            "supersedes": self.supersedes,
            "workload": self.workload_ref,
            "workload_digest": self.workload_digest,
            "workspace": self.workspace_ref,
        }

    def is_fresh(self, at: datetime | None = None) -> bool:
        point = datetime.now(timezone.utc) if at is None else at
        if point.tzinfo is None or point.utcoffset() is None:
            raise PlacementLearningError("freshness point must be timezone-aware")
        return point < _timestamp(self.fresh_until, "placement fresh_until")


@dataclass(frozen=True)
class CacheRetentionEstimate:
    """Rebuildable-cache retention value under capacity and pressure costs."""

    project_ref: ProjectRef
    estimate_id: str
    version: int
    cache_ref: str
    content_ref: ContentRef
    locality_observation: LocalityObservation
    evidence_state: PlacementEvidenceState
    expected_retention_seconds: float | int | None
    evidence_refs: tuple[str, ...]
    observed_at: str
    fresh_until: str
    supersedes: str | None
    authority: CacheAuthority = CacheAuthority.REBUILDABLE
    expected_reuse_count: float | int | None = None
    rebuild_seconds: float | int | None = None
    load_seconds: float | int | None = None
    transfer_seconds: float | int | None = None
    memory_cost_seconds: float | int | None = None
    storage_cost_seconds: float | int | None = None
    congestion_penalty_seconds: float | int | None = None
    fragmentation_penalty_seconds: float | int | None = None
    identity_binding: str | None = None
    estimate_ref: str = field(init=False)
    canonical_digest: str = field(init=False)
    retention_value_seconds: float | None = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.locality_observation, LocalityObservation):
            raise PlacementLearningError("retention Project or locality is malformed")
        if self.locality_observation.project_ref != self.project_ref:
            raise PlacementLearningError("retention locality crossed Project scope")
        _key(self.estimate_id, "retention estimate identity")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise PlacementLearningError("retention estimate version must be positive")
        _ref(self.cache_ref, "retained cache")
        if not self.cache_ref.startswith("cache://"):
            raise PlacementLearningError("Artifact, checkpoint, Run, and Knowledge truth cannot be cache")
        _content_payload(self.content_ref)
        if not isinstance(self.evidence_state, PlacementEvidenceState):
            raise PlacementLearningError("retention evidence state is malformed")
        if not isinstance(self.authority, CacheAuthority) or self.authority is CacheAuthority.AUTHORITATIVE:
            raise PlacementLearningError("authoritative objects cannot be retained or evicted as cache")
        retention = _optional_nonnegative(self.expected_retention_seconds, "expected retention")
        object.__setattr__(self, "expected_retention_seconds", retention)
        numeric_names = (
            "expected_reuse_count",
            "rebuild_seconds",
            "load_seconds",
            "transfer_seconds",
            "memory_cost_seconds",
            "storage_cost_seconds",
            "congestion_penalty_seconds",
            "fragmentation_penalty_seconds",
        )
        numeric: dict[str, float | None] = {}
        for name in numeric_names:
            value = _optional_nonnegative(getattr(self, name), name.replace("_", " "))
            numeric[name] = value
            object.__setattr__(self, name, value)
        refs = _evidence_refs(
            self.evidence_refs,
            "retention evidence",
            required=self.evidence_state is not PlacementEvidenceState.UNKNOWN_EVIDENCE,
        )
        object.__setattr__(self, "evidence_refs", refs)
        _fresh_window(self.observed_at, self.fresh_until, "retention estimate")
        if _timestamp(self.fresh_until, "retention fresh_until") > _timestamp(
            self.locality_observation.fresh_until, "locality fresh_until"
        ):
            raise PlacementLearningError("retention estimate outlives its locality evidence")
        if self.evidence_state is PlacementEvidenceState.UNKNOWN_EVIDENCE:
            if retention is not None:
                raise PlacementLearningError("unknown retention evidence cannot assert a retention duration")
        elif retention is None:
            raise PlacementLearningError("observed retention evidence requires a retention duration")
        if self.evidence_state.value in _CURRENT_EVIDENCE and not refs:
            raise PlacementLearningError("current retention evidence requires exact evidence refs")
        if self.supersedes is not None:
            _ref(self.supersedes, "superseded retention estimate")
        benefit_inputs = (numeric["rebuild_seconds"], numeric["load_seconds"], numeric["transfer_seconds"])
        cost_inputs = (
            numeric["memory_cost_seconds"],
            numeric["storage_cost_seconds"],
            numeric["congestion_penalty_seconds"],
            numeric["fragmentation_penalty_seconds"],
        )
        if any(value is not None for value in (*benefit_inputs, *cost_inputs)):
            reuse = 1.0 if numeric["expected_reuse_count"] is None else numeric["expected_reuse_count"]
            assert reuse is not None
            benefit = reuse * sum(value or 0.0 for value in benefit_inputs)
            costs = sum(value or 0.0 for value in cost_inputs)
            retention_value = benefit - costs
        else:
            retention_value = None
        object.__setattr__(self, "retention_value_seconds", retention_value)
        binding_payload = {
            "authority": self.authority.value,
            "cache": self.cache_ref,
            "content": _content_payload(self.content_ref),
            "estimate_id": self.estimate_id,
            "locality": self.locality_observation.observation_ref,
            "project": self.project_ref.value,
            "version": self.version,
        }
        binding = _digest(binding_payload)
        object.__setattr__(self, "identity_binding", _bind_identity(self.identity_binding, binding, "retention identity binding"))
        ref = f"cache-retention-estimate://{self.project_ref.value}/{self.estimate_id}/{self.version}/{binding[:32]}"
        object.__setattr__(self, "estimate_ref", ref)
        object.__setattr__(self, "canonical_digest", _digest(self.payload()))

    @property
    def promotion_allowed(self) -> bool:
        return False

    @property
    def routing_override_allowed(self) -> bool:
        return False

    @property
    def eviction_allowed(self) -> bool:
        return self.authority in {CacheAuthority.REBUILDABLE, CacheAuthority.EPHEMERAL}

    def payload(self) -> dict[str, object]:
        return {
            "authority": self.authority.value,
            "cache": self.cache_ref,
            "content": _content_payload(self.content_ref),
            "evidence": list(self.evidence_refs),
            "evidence_state": self.evidence_state.value,
            "estimate": self.estimate_ref,
            "expected_retention_seconds": self.expected_retention_seconds,
            "expected_reuse_count": self.expected_reuse_count,
            "fresh_until": self.fresh_until,
            "identity_binding": self.identity_binding,
            "locality": self.locality_observation.canonical_digest,
            "observed_at": self.observed_at,
            "penalties": {
                "congestion_seconds": self.congestion_penalty_seconds,
                "fragmentation_seconds": self.fragmentation_penalty_seconds,
                "memory_cost_seconds": self.memory_cost_seconds,
                "storage_cost_seconds": self.storage_cost_seconds,
            },
            "project": self.project_ref.value,
            "retention_value_seconds": self.retention_value_seconds,
            "supersedes": self.supersedes,
            "value_inputs": {
                "load_seconds": self.load_seconds,
                "rebuild_seconds": self.rebuild_seconds,
                "transfer_seconds": self.transfer_seconds,
            },
        }

    def is_fresh(self, at: datetime | None = None) -> bool:
        point = datetime.now(timezone.utc) if at is None else at
        if point.tzinfo is None or point.utcoffset() is None:
            raise PlacementLearningError("freshness point must be timezone-aware")
        return point < _timestamp(self.fresh_until, "retention fresh_until")


class PlacementLearningService:
    """Ranks only hard-eligible placements and plans rebuildable-cache eviction."""

    def __init__(self, project_ref: ProjectRef) -> None:
        if not isinstance(project_ref, ProjectRef):
            raise PlacementLearningError("placement service Project is malformed")
        self.project_ref = project_ref

    def cache_key(
        self,
        implementation_ref: str,
        source_content_ref: ContentRef,
        context_ref: str,
        tool_ref: str,
        *,
        configuration_digest: str | None = None,
    ) -> str:
        """Return a non-reversible key scoped by Project and every exact input."""
        for value, label in (
            (implementation_ref, "implementation"),
            (context_ref, "context"),
            (tool_ref, "tool"),
        ):
            _ref(value, label)
        config = "0" * 64 if configuration_digest is None else _sha(configuration_digest, "configuration digest")
        digest = _digest(
            {
                "configuration": config,
                "context": context_ref,
                "implementation": implementation_ref,
                "project": self.project_ref.value,
                "source": _content_payload(source_content_ref),
                "tool": tool_ref,
            }
        )
        return f"cache-key://sha256/{digest}"

    def validate_reuse(self, project_ref: ProjectRef, cache_ref: str, identity_ref: str) -> None:
        """Fail closed for foreign, non-cache, stale, or non-exact reuse hints."""
        if project_ref != self.project_ref:
            raise PlacementLearningError("cache reuse crossed Project scope")
        _ref(cache_ref, "cache reuse")
        if not cache_ref.startswith("cache://"):
            raise PlacementLearningError("cache reuse target is not rebuildable cache")
        if not isinstance(identity_ref, str) or _CACHE_KEY.fullmatch(identity_ref) is None:
            raise PlacementLearningError("cache reuse identity is stale or incompatible")

    def validate_cache_reuse(
        self,
        observation: LocalityObservation,
        cached_identity: CacheIdentity,
        required_identity: CacheIdentity,
        *,
        at: datetime | None = None,
    ) -> None:
        if (
            observation.project_ref != self.project_ref
            or cached_identity.project_ref != self.project_ref
            or required_identity.project_ref != self.project_ref
        ):
            raise PlacementLearningError("cache reuse crossed Project scope")
        if not observation.is_fresh(at):
            raise PlacementLearningError("cache reuse locality is stale")
        if cached_identity.cache_ref not in observation.locality.warm_cache_refs:
            raise PlacementLearningError("cache is not observed warm on the target Resource")
        if cached_identity.cache_key != required_identity.cache_key:
            raise PlacementLearningError("cache identity is stale or incompatible")

    def rank_resources(
        self,
        candidate_refs: Sequence[str],
        hard_eligible_resource_refs: Iterable[str],
    ) -> tuple[str, ...]:
        """Filter an existing order; locality never admits an ineligible Resource."""
        if isinstance(candidate_refs, (str, bytes)) or not isinstance(candidate_refs, Sequence):
            raise PlacementLearningError("candidate Resource order is malformed")
        eligible = frozenset(hard_eligible_resource_refs)
        for value in (*candidate_refs, *eligible):
            _ref(value, "Resource candidate")
        if len(set(candidate_refs)) != len(candidate_refs):
            raise PlacementLearningError("candidate Resource order contains duplicates")
        return tuple(value for value in candidate_refs if value in eligible)

    @staticmethod
    def _estimate_identity(estimate: PlacementEstimate) -> tuple[str, ...]:
        return (
            estimate.workload_ref,
            estimate.workload_digest,
            estimate.artifact_ref.value,
            estimate.content_ref.digest,
            estimate.workspace_ref,
            estimate.target_resource_ref.value,
        )

    def active_estimates(self, estimates: Sequence[PlacementEstimate]) -> tuple[PlacementEstimate, ...]:
        if isinstance(estimates, (str, bytes)) or not isinstance(estimates, Sequence) or len(estimates) > 4096:
            raise PlacementLearningError("placement estimate set is malformed or unbounded")
        values = tuple(estimates)
        if not all(isinstance(item, PlacementEstimate) for item in values):
            raise PlacementLearningError("placement estimate set contains malformed evidence")
        by_ref = {item.estimate_ref: item for item in values}
        if len(by_ref) != len(values):
            raise PlacementLearningError("placement estimate identity is duplicated")
        for item in values:
            if item.project_ref != self.project_ref:
                raise PlacementLearningError("placement estimate crossed Project scope")
            if item.supersedes is None:
                continue
            prior = by_ref.get(item.supersedes)
            if prior is not None and (
                self._estimate_identity(prior) != self._estimate_identity(item)
                or prior.version >= item.version
            ):
                raise PlacementLearningError("placement supersession identity is invalid")
        active: dict[tuple[str, ...], PlacementEstimate] = {}
        for item in values:
            identity = self._estimate_identity(item)
            prior = active.get(identity)
            if prior is None or item.version > prior.version:
                active[identity] = item
            elif item.version == prior.version:
                raise PlacementLearningError("placement estimate revision is ambiguous")
        return tuple(sorted(active.values(), key=lambda item: item.estimate_ref))

    def rank_estimates(
        self,
        estimates: Sequence[PlacementEstimate],
        *,
        hard_eligible_resource_refs: Iterable[ResourceRef],
        current_resource_identities: Mapping[ResourceRef, str],
        at: datetime | None = None,
    ) -> tuple[PlacementEstimate, ...]:
        """Rank performance after hard eligibility and current identity checks."""
        eligible = frozenset(hard_eligible_resource_refs)
        for resource_ref in eligible:
            if not isinstance(resource_ref, ResourceRef) or resource_ref.project_ref != self.project_ref:
                raise PlacementLearningError("hard-eligible Resource crossed Project scope")
        ranked: list[tuple[float, str, PlacementEstimate]] = []
        for estimate in self.active_estimates(estimates):
            if estimate.target_resource_ref not in eligible:
                continue
            current_digest = current_resource_identities.get(estimate.target_resource_ref)
            if current_digest is None:
                continue
            _sha(current_digest, "current Resource identity digest")
            if current_digest != estimate.resource_identity_digest:
                raise PlacementLearningError("placement Resource identity changed before ranking")
            if not estimate.is_fresh(at) or not estimate.locality_observation.is_fresh(at):
                raise PlacementLearningError("placement evidence is stale")
            if estimate.evidence_state.value not in _CURRENT_EVIDENCE:
                continue
            total = estimate.estimated_total_seconds
            ranked.append((math.inf if total is None else total, estimate.estimate_ref, estimate))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2] for item in ranked)

    def plan_eviction(
        self,
        candidates: Sequence[CacheIdentity | CacheRetentionEstimate | ArtifactRef | str],
    ) -> tuple[str, ...]:
        """Order rebuildable cache only; this method never deletes authoritative bytes."""
        if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence) or len(candidates) > 4096:
            raise PlacementLearningError("cache eviction candidates are malformed or unbounded")
        ranked: list[tuple[float, str]] = []
        for candidate in candidates:
            if isinstance(candidate, ArtifactRef):
                raise PlacementLearningError("Artifact truth cannot be an eviction candidate")
            if isinstance(candidate, CacheIdentity):
                if candidate.project_ref != self.project_ref or not candidate.eviction_allowed:
                    raise PlacementLearningError("cache eviction crossed Project scope or authority")
                ranked.append((0.0, candidate.cache_ref))
                continue
            if isinstance(candidate, CacheRetentionEstimate):
                if candidate.project_ref != self.project_ref or not candidate.eviction_allowed:
                    raise PlacementLearningError("retention eviction crossed Project scope or authority")
                value = candidate.retention_value_seconds
                ranked.append((math.inf if value is None else value, candidate.cache_ref))
                continue
            _ref(candidate, "cache eviction candidate")
            if not candidate.startswith("cache://"):
                raise PlacementLearningError("authoritative object cannot be an eviction candidate")
            ranked.append((0.0, candidate))
        if len({item[1] for item in ranked}) != len(ranked):
            raise PlacementLearningError("cache eviction candidates are duplicated")
        ranked.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[1] for item in ranked)


CacheObjectAuthority = CacheAuthority


__all__ = [
    "CacheAuthority",
    "CacheIdentity",
    "CacheObjectAuthority",
    "CacheRetentionEstimate",
    "CacheReuseState",
    "LocalityObservation",
    "PlacementEvidenceState",
    "PlacementEstimate",
    "PlacementLearningError",
    "PlacementLearningService",
]
