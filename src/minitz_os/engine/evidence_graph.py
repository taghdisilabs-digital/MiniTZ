"""Storage-neutral evidence graph contracts for MiniTZ.

The graph in this module is a semantic family, not another operational
authority.  Records retain the exact identity of the store that produced
them, while relations describe how those records are related.  Callers are
responsible for persisting the immutable records in their native stores.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, TypeAlias, cast


MINITZ_SEMANTIC_GRAPH = "MiniTZ"
EVIDENCE_FAMILY_REF = "semantic-family://minitz/event-evidence/v1"
EVIDENCE_FAMILY_REVISION = 1
EVIDENCE_RECORD_SCHEMA = "minitz.evidence_record/v1"
EVIDENCE_RELATION_SCHEMA = "minitz.evidence_relation/v1"
EVIDENCE_AUTHORITY = "NONE_DERIVED_EVIDENCE"

_MAX_TEXT = 2048
_MAX_REF = 1056
_MAX_MAP_ITEMS = 64
_MAX_SEQUENCE_ITEMS = 128
_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth_secret",
    "authorization",
    "password",
    "passwd",
    "refresh_token",
    "login_token",
    "access_token",
    "secret",
)
_RAW_VALUE_KEY_PARTS = (
    "full_prompt",
    "model_output",
    "raw_output",
    "raw_provider_output",
    "prompt",
    "stdout",
    "stderr",
    "response_body",
    "completion",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"^sk-[A-Za-z0-9_-]{16,}$"),
    re.compile(r"^gh[pousr]_[A-Za-z0-9_]{16,}$"),
    re.compile(r"^Bearer\s+\S+$", re.IGNORECASE),
)

JSONValue: TypeAlias = (
    None | bool | int | float | str | tuple["JSONValue", ...] | Mapping[str, "JSONValue"]
)


class EvidenceGraphError(ValueError):
    """Base error for malformed or conflicting evidence-family values."""


class EvidenceContractError(EvidenceGraphError):
    """Raised when an evidence record or relation violates the contract."""


class EvidenceConflictError(EvidenceGraphError):
    """Raised when one exact identity is presented with competing content."""


class EvidenceKind(str, Enum):
    EVENT = "EVENT"
    CALL = "CALL"
    FAILURE = "FAILURE"
    ATTEMPT = "ATTEMPT"
    SESSION = "SESSION"
    TOOL_TRACE = "TOOL_TRACE"
    PROJECTION = "PROJECTION"
    REJECTION = "REJECTION"
    AUDIT_RECEIPT = "AUDIT_RECEIPT"
    SECRET_VERIFIER_RECEIPT = "SECRET_VERIFIER_RECEIPT"


class EvidenceRelationType(str, Enum):
    REALIZES = "REALIZES"
    REPRESENTS = "REPRESENTS"
    DERIVED_FROM = "DERIVED_FROM"
    HAS_PROVENANCE = "HAS_PROVENANCE"
    MEMBER_OF = "MEMBER_OF"
    BELONGS_TO_PROJECT = "BELONGS_TO_PROJECT"
    EXECUTES_IN = "EXECUTES_IN"
    CANDIDATE_FOR_HEAD = "CANDIDATE_FOR_HEAD"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    REVISION_OF = "REVISION_OF"


def _require_text(value: object, field_name: str, *, maximum: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise EvidenceContractError(f"{field_name} must be a non-empty bounded string")
    if any(ord(character) < 0x20 and character not in "\t\n\r" for character in value):
        raise EvidenceContractError(f"{field_name} contains a control character")
    return value


def _require_optional_text(value: object, field_name: str, *, maximum: int = _MAX_TEXT) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name, maximum=maximum)


def _check_safe_key(key: str, path: str) -> None:
    if not _KEY_RE.fullmatch(key):
        raise EvidenceContractError(f"{path} has an invalid key")
    lowered = key.lower()
    if any(part in lowered for part in _SECRET_KEY_PARTS):
        raise EvidenceContractError(f"{path} contains a credential field")
    if any(part in lowered for part in _RAW_VALUE_KEY_PARTS):
        raise EvidenceContractError(f"{path} contains an unbounded provider-output field")


def _check_safe_string(value: str, path: str) -> None:
    if any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
        raise EvidenceContractError(f"{path} contains a credential-like value")


def _freeze_json(value: object, path: str = "value") -> JSONValue:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceContractError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, str):
        bounded = _require_text(value, path)
        _check_safe_string(bounded, path)
        return bounded
    if isinstance(value, Mapping):
        if len(value) > _MAX_MAP_ITEMS:
            raise EvidenceContractError(f"{path} has too many fields")
        frozen: dict[str, JSONValue] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise EvidenceContractError(f"{path} has a non-string key")
            _check_safe_key(raw_key, f"{path}.{raw_key}")
            frozen[raw_key] = _freeze_json(raw_value, f"{path}.{raw_key}")
        return cast(JSONValue, MappingProxyType(frozen))
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        if len(value) > _MAX_SEQUENCE_ITEMS:
            raise EvidenceContractError(f"{path} has too many items")
        return tuple(_freeze_json(item, f"{path}[{index}]") for index, item in enumerate(value))
    raise EvidenceContractError(f"{path} is not JSON-compatible")


def _thaw_json(value: JSONValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_kind(value: EvidenceKind | str) -> str:
    normalized = value.value if isinstance(value, EvidenceKind) else str(value).upper()
    if normalized not in {kind.value for kind in EvidenceKind}:
        raise EvidenceContractError(f"unknown evidence kind: {normalized}")
    return normalized


def _normalize_relation_type(value: EvidenceRelationType | str) -> str:
    normalized = value.value if isinstance(value, EvidenceRelationType) else str(value).upper()
    if normalized not in {relation.value for relation in EvidenceRelationType}:
        raise EvidenceContractError(f"unknown evidence relation type: {normalized}")
    return normalized


def _validate_exact_ref(value: object, field_name: str) -> str:
    reference = _require_text(value, field_name, maximum=_MAX_REF)
    if "://" not in reference:
        raise EvidenceContractError(f"{field_name} must retain an exact URI-like identity")
    return reference


def _validate_timestamp(value: object, field_name: str) -> str:
    timestamp = _require_text(value, field_name, maximum=128)
    if timestamp != "UNKNOWN":
        try:
            timestamp_value = timestamp.replace("Z", "+00:00")
            from datetime import datetime

            datetime.fromisoformat(timestamp_value)
        except ValueError as exc:
            raise EvidenceContractError(f"{field_name} must be ISO-8601 or UNKNOWN") from exc
    return timestamp


@dataclass(frozen=True)
class EvidenceProvenance:
    """Required provenance attached to every semantic evidence record."""

    source_identity: str
    source_revision_or_observation: str
    source_sha256_or_private_receipt: str
    origin_kind: str
    observed_at_or_unknown: str
    extraction_or_derivation_ref: str
    scope_ref: str
    unknown_regions: tuple[str, ...] = ()
    evidence_state: str = "OBSERVED"

    def __post_init__(self) -> None:
        for field_name in (
            "source_identity",
            "source_revision_or_observation",
            "source_sha256_or_private_receipt",
            "origin_kind",
            "extraction_or_derivation_ref",
            "scope_ref",
            "evidence_state",
        ):
            _require_text(getattr(self, field_name), field_name)
        _validate_timestamp(self.observed_at_or_unknown, "observed_at_or_unknown")
        if len(self.unknown_regions) > _MAX_SEQUENCE_ITEMS:
            raise EvidenceContractError("unknown_regions has too many entries")
        normalized_regions = tuple(
            _require_text(region, "unknown_regions[]", maximum=256) for region in self.unknown_regions
        )
        object.__setattr__(self, "unknown_regions", normalized_regions)

    def to_payload(self) -> dict[str, object]:
        return {
            "source_identity": self.source_identity,
            "source_revision_or_observation": self.source_revision_or_observation,
            "source_sha256_or_private_receipt": self.source_sha256_or_private_receipt,
            "origin_kind": self.origin_kind,
            "observed_at_or_unknown": self.observed_at_or_unknown,
            "extraction_or_derivation_ref": self.extraction_or_derivation_ref,
            "scope_ref": self.scope_ref,
            "unknown_regions": list(self.unknown_regions),
            "evidence_state": self.evidence_state,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "EvidenceProvenance":
        raw_regions = payload.get("unknown_regions", ())
        if not isinstance(raw_regions, Sequence) or isinstance(raw_regions, (str, bytes, bytearray)):
            raise EvidenceContractError("unknown_regions must be a sequence")
        return cls(
            source_identity=_require_text(payload.get("source_identity"), "source_identity"),
            source_revision_or_observation=_require_text(
                payload.get("source_revision_or_observation"), "source_revision_or_observation"
            ),
            source_sha256_or_private_receipt=_require_text(
                payload.get("source_sha256_or_private_receipt"), "source_sha256_or_private_receipt"
            ),
            origin_kind=_require_text(payload.get("origin_kind"), "origin_kind"),
            observed_at_or_unknown=_validate_timestamp(
                payload.get("observed_at_or_unknown"), "observed_at_or_unknown"
            ),
            extraction_or_derivation_ref=_require_text(
                payload.get("extraction_or_derivation_ref"), "extraction_or_derivation_ref"
            ),
            scope_ref=_require_text(payload.get("scope_ref"), "scope_ref"),
            unknown_regions=tuple(
                _require_text(region, "unknown_regions[]", maximum=256) for region in raw_regions
            ),
            evidence_state=_require_text(payload.get("evidence_state", "OBSERVED"), "evidence_state"),
        )


@dataclass(frozen=True)
class EvidenceRecord:
    """An immutable exact-source record participating in the MiniTZ family."""

    record_kind: EvidenceKind | str
    exact_ref: str
    project_ref: str
    payload: Mapping[str, object]
    provenance: EvidenceProvenance
    task_ref: str | None = None
    run_ref: str | None = None
    session_ref: str | None = None
    attempt_ref: str | None = None
    semantic_graph: str = MINITZ_SEMANTIC_GRAPH
    family_ref: str = EVIDENCE_FAMILY_REF
    family_revision: int = EVIDENCE_FAMILY_REVISION
    authority: str = EVIDENCE_AUTHORITY
    projection_authority: bool = False
    progression_authority: bool = False
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_kind", _normalize_kind(self.record_kind))
        object.__setattr__(self, "exact_ref", _validate_exact_ref(self.exact_ref, "exact_ref"))
        object.__setattr__(self, "project_ref", _require_text(self.project_ref, "project_ref", maximum=256))
        object.__setattr__(self, "payload", _freeze_json(self.payload, "payload"))
        if (
            self.semantic_graph != MINITZ_SEMANTIC_GRAPH
            or self.family_ref != EVIDENCE_FAMILY_REF
            or not isinstance(self.family_revision, int)
            or isinstance(self.family_revision, bool)
            or self.family_revision != EVIDENCE_FAMILY_REVISION
        ):
            raise EvidenceContractError("evidence record is outside the MiniTZ semantic family")
        if self.authority != EVIDENCE_AUTHORITY:
            raise EvidenceContractError("evidence records cannot claim authority")
        if not isinstance(self.projection_authority, bool) or not isinstance(
            self.progression_authority, bool
        ):
            raise EvidenceContractError("evidence authority flags must be boolean")
        if self.projection_authority or self.progression_authority:
            raise EvidenceContractError("evidence records cannot own projections or progression")
        for field_name in ("task_ref", "run_ref", "session_ref", "attempt_ref"):
            optional_ref = _require_optional_text(getattr(self, field_name), field_name, maximum=_MAX_REF)
            if optional_ref is not None and "://" not in optional_ref:
                raise EvidenceContractError(f"{field_name} must retain a URI-like identity")
            object.__setattr__(self, field_name, optional_ref)
        payload_without_digest = self.to_payload(include_digest=False)
        object.__setattr__(self, "record_sha256", _digest(payload_without_digest))

    def to_payload(self, *, include_digest: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": EVIDENCE_RECORD_SCHEMA,
            "record_kind": self.record_kind,
            "exact_ref": self.exact_ref,
            "project_ref": self.project_ref,
            "task_ref": self.task_ref,
            "run_ref": self.run_ref,
            "session_ref": self.session_ref,
            "attempt_ref": self.attempt_ref,
            "semantic_graph": self.semantic_graph,
            "family_ref": self.family_ref,
            "family_revision": self.family_revision,
            "authority": self.authority,
            "projection_authority": self.projection_authority,
            "progression_authority": self.progression_authority,
            "payload": _thaw_json(cast(JSONValue, self.payload)),
            "provenance": self.provenance.to_payload(),
        }
        if include_digest:
            payload["record_sha256"] = self.record_sha256
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "EvidenceRecord":
        if payload.get("schema") != EVIDENCE_RECORD_SCHEMA:
            raise EvidenceContractError("unsupported evidence record schema")
        raw_payload = payload.get("payload")
        raw_provenance = payload.get("provenance")
        if not isinstance(raw_payload, Mapping) or not isinstance(raw_provenance, Mapping):
            raise EvidenceContractError("evidence record payload/provenance must be objects")
        record = cls(
            record_kind=cast(str, payload.get("record_kind")),
            exact_ref=cast(str, payload.get("exact_ref")),
            project_ref=cast(str, payload.get("project_ref")),
            task_ref=cast(str | None, payload.get("task_ref")),
            run_ref=cast(str | None, payload.get("run_ref")),
            session_ref=cast(str | None, payload.get("session_ref")),
            attempt_ref=cast(str | None, payload.get("attempt_ref")),
            semantic_graph=cast(str, payload.get("semantic_graph", MINITZ_SEMANTIC_GRAPH)),
            family_ref=cast(str, payload.get("family_ref", EVIDENCE_FAMILY_REF)),
            family_revision=cast(int, payload.get("family_revision", EVIDENCE_FAMILY_REVISION)),
            authority=cast(str, payload.get("authority", EVIDENCE_AUTHORITY)),
            projection_authority=bool(payload.get("projection_authority", False)),
            progression_authority=bool(payload.get("progression_authority", False)),
            payload=raw_payload,
            provenance=EvidenceProvenance.from_payload(raw_provenance),
        )
        supplied_digest = payload.get("record_sha256")
        if supplied_digest is not None and supplied_digest != record.record_sha256:
            raise EvidenceContractError("evidence record digest mismatch")
        return record


@dataclass(frozen=True)
class EvidenceRelation:
    """An immutable typed edge between exact-source identities."""

    relation_type: EvidenceRelationType | str
    left_exact_ref: str
    right_exact_ref: str
    project_ref: str
    scope_ref: str
    evidence_refs: tuple[str, ...]
    qualification: Mapping[str, object]
    provenance: EvidenceProvenance
    semantic_graph: str = MINITZ_SEMANTIC_GRAPH
    family_ref: str = EVIDENCE_FAMILY_REF
    family_revision: int = EVIDENCE_FAMILY_REVISION
    authority: str = EVIDENCE_AUTHORITY
    relation_id: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_type", _normalize_relation_type(self.relation_type))
        object.__setattr__(self, "left_exact_ref", _validate_exact_ref(self.left_exact_ref, "left_exact_ref"))
        object.__setattr__(self, "right_exact_ref", _validate_exact_ref(self.right_exact_ref, "right_exact_ref"))
        object.__setattr__(self, "project_ref", _require_text(self.project_ref, "project_ref", maximum=256))
        object.__setattr__(self, "scope_ref", _require_text(self.scope_ref, "scope_ref", maximum=_MAX_REF))
        if not self.evidence_refs:
            raise EvidenceContractError("relations require at least one provenance evidence reference")
        if len(self.evidence_refs) > _MAX_SEQUENCE_ITEMS:
            raise EvidenceContractError("relations have too many evidence references")
        normalized_refs = tuple(
            _validate_exact_ref(reference, "evidence_refs[]") for reference in self.evidence_refs
        )
        object.__setattr__(self, "evidence_refs", normalized_refs)
        object.__setattr__(self, "qualification", _freeze_json(self.qualification, "qualification"))
        if (
            self.semantic_graph != MINITZ_SEMANTIC_GRAPH
            or self.family_ref != EVIDENCE_FAMILY_REF
            or not isinstance(self.family_revision, int)
            or isinstance(self.family_revision, bool)
            or self.family_revision != EVIDENCE_FAMILY_REVISION
        ):
            raise EvidenceContractError("evidence relation is outside the MiniTZ semantic family")
        if self.authority != EVIDENCE_AUTHORITY:
            raise EvidenceContractError("evidence relations cannot claim authority")
        identity = self._identity_payload()
        identity_digest = _digest(identity)
        object.__setattr__(self, "relation_id", f"evidence-relation://sha256/{identity_digest}")
        object.__setattr__(self, "record_sha256", identity_digest)

    def _identity_payload(self) -> dict[str, object]:
        return {
            "schema": EVIDENCE_RELATION_SCHEMA,
            "semantic_graph": self.semantic_graph,
            "family_ref": self.family_ref,
            "family_revision": self.family_revision,
            "authority": self.authority,
            "relation_type": self.relation_type,
            "left_exact_ref": self.left_exact_ref,
            "right_exact_ref": self.right_exact_ref,
            "project_ref": self.project_ref,
            "scope_ref": self.scope_ref,
            "evidence_refs": list(self.evidence_refs),
            "qualification": _thaw_json(cast(JSONValue, self.qualification)),
            "provenance": self.provenance.to_payload(),
        }

    def to_payload(self, *, include_digest: bool = True) -> dict[str, object]:
        payload = self._identity_payload()
        payload["relation_id"] = self.relation_id
        if include_digest:
            payload["record_sha256"] = self.record_sha256
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "EvidenceRelation":
        if payload.get("schema") != EVIDENCE_RELATION_SCHEMA:
            raise EvidenceContractError("unsupported evidence relation schema")
        raw_evidence_refs = payload.get("evidence_refs")
        raw_qualification = payload.get("qualification")
        raw_provenance = payload.get("provenance")
        if (
            not isinstance(raw_evidence_refs, Sequence)
            or isinstance(raw_evidence_refs, (str, bytes, bytearray))
            or not isinstance(raw_qualification, Mapping)
            or not isinstance(raw_provenance, Mapping)
        ):
            raise EvidenceContractError("relation evidence/qualification/provenance fields are malformed")
        relation = cls(
            relation_type=cast(str, payload.get("relation_type")),
            left_exact_ref=cast(str, payload.get("left_exact_ref")),
            right_exact_ref=cast(str, payload.get("right_exact_ref")),
            project_ref=cast(str, payload.get("project_ref")),
            scope_ref=cast(str, payload.get("scope_ref")),
            evidence_refs=tuple(cast(str, reference) for reference in raw_evidence_refs),
            qualification=raw_qualification,
            provenance=EvidenceProvenance.from_payload(raw_provenance),
            semantic_graph=cast(str, payload.get("semantic_graph", MINITZ_SEMANTIC_GRAPH)),
            family_ref=cast(str, payload.get("family_ref", EVIDENCE_FAMILY_REF)),
            family_revision=cast(int, payload.get("family_revision", EVIDENCE_FAMILY_REVISION)),
            authority=cast(str, payload.get("authority", EVIDENCE_AUTHORITY)),
        )
        if payload.get("relation_id") not in (None, relation.relation_id):
            raise EvidenceContractError("evidence relation identity mismatch")
        if payload.get("record_sha256") not in (None, relation.record_sha256):
            raise EvidenceContractError("evidence relation digest mismatch")
        return relation


class EvidenceGraph:
    """Small in-memory normalizer used by adapters and validation code.

    It deliberately has no mutable head, scheduler, progression callback, or
    persistence side effect.  Native ledgers remain the owners of their raw
    records; this object only checks that normalized identities do not fork.
    """

    semantic_graph = MINITZ_SEMANTIC_GRAPH
    family_ref = EVIDENCE_FAMILY_REF
    family_revision = EVIDENCE_FAMILY_REVISION
    authority = EVIDENCE_AUTHORITY

    @staticmethod
    def record(
        *,
        record_kind: EvidenceKind | str,
        exact_ref: str,
        project_ref: str,
        payload: Mapping[str, object],
        provenance: EvidenceProvenance,
        task_ref: str | None = None,
        run_ref: str | None = None,
        session_ref: str | None = None,
        attempt_ref: str | None = None,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            record_kind=record_kind,
            exact_ref=exact_ref,
            project_ref=project_ref,
            payload=payload,
            provenance=provenance,
            task_ref=task_ref,
            run_ref=run_ref,
            session_ref=session_ref,
            attempt_ref=attempt_ref,
        )

    @staticmethod
    def relation(
        *,
        relation_type: EvidenceRelationType | str,
        left_exact_ref: str,
        right_exact_ref: str,
        project_ref: str,
        scope_ref: str,
        evidence_refs: Sequence[str],
        qualification: Mapping[str, object],
        provenance: EvidenceProvenance,
    ) -> EvidenceRelation:
        return EvidenceRelation(
            relation_type=relation_type,
            left_exact_ref=left_exact_ref,
            right_exact_ref=right_exact_ref,
            project_ref=project_ref,
            scope_ref=scope_ref,
            evidence_refs=tuple(evidence_refs),
            qualification=qualification,
            provenance=provenance,
        )

    @staticmethod
    def normalize(
        records: Sequence[EvidenceRecord], relations: Sequence[EvidenceRelation] = ()
    ) -> tuple[tuple[EvidenceRecord, ...], tuple[EvidenceRelation, ...]]:
        records_by_ref: dict[tuple[str, str], EvidenceRecord] = {}
        for record in records:
            key = (record.project_ref, record.exact_ref)
            previous = records_by_ref.get(key)
            if previous is not None and previous.to_payload() != record.to_payload():
                raise EvidenceConflictError(f"competing evidence for {record.exact_ref}")
            records_by_ref[key] = record

        relations_by_id: dict[str, EvidenceRelation] = {}
        for relation in relations:
            previous_relation = relations_by_id.get(relation.relation_id)
            if previous_relation is not None and previous_relation.to_payload() != relation.to_payload():
                raise EvidenceConflictError(f"competing relation for {relation.relation_id}")
            relations_by_id[relation.relation_id] = relation

        return (
            tuple(records_by_ref.values()),
            tuple(relations_by_id.values()),
        )


def derived_provenance(
    *,
    source_identity: str,
    source_revision_or_observation: str,
    source_sha256_or_private_receipt: str,
    origin_kind: str,
    observed_at_or_unknown: str,
    extraction_or_derivation_ref: str,
    scope_ref: str,
    unknown_regions: Sequence[str] = (),
    evidence_state: str = "OBSERVED",
) -> EvidenceProvenance:
    """Create validated provenance for an adapter-derived semantic view."""

    return EvidenceProvenance(
        source_identity=source_identity,
        source_revision_or_observation=source_revision_or_observation,
        source_sha256_or_private_receipt=source_sha256_or_private_receipt,
        origin_kind=origin_kind,
        observed_at_or_unknown=observed_at_or_unknown,
        extraction_or_derivation_ref=extraction_or_derivation_ref,
        scope_ref=scope_ref,
        unknown_regions=tuple(unknown_regions),
        evidence_state=evidence_state,
    )


__all__ = [
    "EVIDENCE_AUTHORITY",
    "EVIDENCE_FAMILY_REF",
    "EVIDENCE_FAMILY_REVISION",
    "EVIDENCE_RECORD_SCHEMA",
    "EVIDENCE_RELATION_SCHEMA",
    "MINITZ_SEMANTIC_GRAPH",
    "EvidenceConflictError",
    "EvidenceContractError",
    "EvidenceGraph",
    "EvidenceGraphError",
    "EvidenceKind",
    "EvidenceProvenance",
    "EvidenceRecord",
    "EvidenceRelation",
    "EvidenceRelationType",
    "derived_provenance",
]
