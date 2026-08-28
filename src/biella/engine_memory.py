"""Durable, evidence-backed Engine knowledge with a controlled promotion boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn, cast
import unicodedata
from uuid import uuid4

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .project import Project, ProjectAccess, ProjectError, ProjectRef, ProjectScopeError, ProjectStore
from .project_memory import ProjectKnowledgeCandidate, ProjectKnowledgeService
from .run import RunError, RunRef, RunService

if TYPE_CHECKING:
    from .migration import NormalizedMigrationCandidate


_CANDIDATE_ID_PATTERN = re.compile(r"kc_[0-9a-f]{32}")
_KNOWLEDGE_ID_PATTERN = re.compile(r"kn_[0-9a-f]{32}")
_AUTHORITY_ID_PATTERN = re.compile(r"kpa_[0-9a-f]{32}")
_AUTHORITY_TOKEN_PATTERN = re.compile(r"kpsecret_[0-9a-f]{64}")
_PROVISIONING_ID_PATTERN = re.compile(r"kpr_[0-9a-f]{32}")
_PROVISIONING_TOKEN_PATTERN = re.compile(r"kproot_[0-9a-f]{64}")
_SCOPE_EVIDENCE_ID_PATTERN = re.compile(r"kse_[0-9a-f]{32}")
_KEY_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")
_TYPE_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_SCOPES = {"ENGINE", "PROJECT", "HISTORICAL"}
_EVIDENCE_STRENGTHS = {"OBSERVATION", "SUPPORTED", "CORROBORATED"}
_DECISION_STATUSES = {"ELIGIBLE", "ROUTE_PROJECT"}
_RESOLUTION_STATUSES = {"CURRENT", "CONFLICT"}


class KnowledgeError(Exception):
    """Base class for controlled knowledge failures."""


class KnowledgeContractError(KnowledgeError, ValueError):
    """A knowledge request or value is malformed."""


class KnowledgeAuthorityError(KnowledgeError, PermissionError):
    """The caller lacks the promotion capability."""


class KnowledgeScopeError(KnowledgeError):
    """A request crossed or misclassified an exact knowledge scope."""


class KnowledgeNotFoundError(KnowledgeError):
    """The requested candidate, decision, or revision does not exist."""


class KnowledgeConflictError(KnowledgeError):
    """A request conflicts with durable knowledge state."""


class KnowledgeIntegrityError(KnowledgeError):
    """Durable knowledge or its evidence failed verification."""


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise KnowledgeContractError(f"{field_name} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise KnowledgeContractError(f"{field_name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise KnowledgeContractError(f"{field_name} must be timezone-aware")
    return value


def _validate_key(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise KnowledgeContractError(f"{field_name} is malformed")
    return value


def _validate_type(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or _TYPE_PATTERN.fullmatch(value) is None
    ):
        raise KnowledgeContractError(f"{field_name} is malformed")
    return value


def _validate_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise KnowledgeIntegrityError(f"{field_name} is malformed")
    return value


def _validate_scope(value: object) -> str:
    if not isinstance(value, str) or value not in _SCOPES:
        raise KnowledgeContractError("knowledge scope is malformed")
    return value


def _validate_evidence_strength(value: object) -> str:
    if not isinstance(value, str) or value not in _EVIDENCE_STRENGTHS:
        raise KnowledgeContractError("evidence strength is malformed")
    return value


def _freeze_strings(
    values: Sequence[str],
    field_name: str,
    *,
    limit: int = 32,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise KnowledgeContractError(f"{field_name} must be a sequence")
    copied = tuple(values)
    if len(copied) > limit:
        raise KnowledgeContractError(f"{field_name} is unbounded")
    if any(
        not isinstance(item, str)
        or not item.strip()
        or len(item.encode()) > 2048
        for item in copied
    ):
        raise KnowledgeContractError(f"{field_name} contains malformed text")
    if len(set(copied)) != len(copied):
        raise KnowledgeContractError(f"{field_name} contains duplicates")
    return copied


def _freeze_mapping(
    value: Mapping[str, str],
    field_name: str,
    *,
    limit: int = 32,
    allow_empty_values: bool = False,
) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise KnowledgeContractError(f"{field_name} must be a mapping")
    copied = dict(value)
    if len(copied) > limit:
        raise KnowledgeContractError(f"{field_name} is unbounded")
    for key, item in copied.items():
        _validate_key(key, f"{field_name} key")
        if (
            not isinstance(item, str)
            or (not item and not allow_empty_values)
            or len(item.encode()) > 4096
        ):
            raise KnowledgeContractError(f"{field_name} value is malformed")
    return MappingProxyType(dict(sorted(copied.items())))


def _content_payload(content_ref: ContentRef | None) -> dict[str, object] | None:
    if content_ref is None:
        return None
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _validate_statement_or_content(
    statement: object,
    content_ref: object,
) -> tuple[str | None, ContentRef | None]:
    if (statement is None) == (content_ref is None):
        raise KnowledgeContractError("exactly one statement or content_ref is required")
    if statement is not None:
        if (
            not isinstance(statement, str)
            or not statement.strip()
            or len(statement.encode()) > 16384
        ):
            raise KnowledgeContractError("statement is empty or unbounded")
        return statement, None
    if not isinstance(content_ref, ContentRef):
        raise KnowledgeContractError("content_ref must be ContentRef")
    return None, content_ref


def _freeze_project_artifact_refs(
    values: Sequence[ArtifactRef],
    project_ref: ProjectRef,
    field_name: str,
) -> tuple[ArtifactRef, ...]:
    copied = tuple(values)
    if len(copied) > 64:
        raise KnowledgeContractError(f"{field_name} is unbounded")
    if not all(isinstance(item, ArtifactRef) for item in copied):
        raise KnowledgeContractError(f"{field_name} accepts exact ArtifactRef values")
    if any(item.project_ref != project_ref for item in copied):
        raise KnowledgeScopeError(f"{field_name} crossed Project scope")
    if len(set(copied)) != len(copied):
        raise KnowledgeContractError(f"{field_name} contains duplicates")
    return copied


def _freeze_global_artifact_refs(
    values: Sequence[ArtifactRef],
    field_name: str,
) -> tuple[ArtifactRef, ...]:
    copied = tuple(values)
    if len(copied) > 256:
        raise KnowledgeContractError(f"{field_name} is unbounded")
    if not all(isinstance(item, ArtifactRef) for item in copied):
        raise KnowledgeContractError(f"{field_name} accepts exact ArtifactRef values")
    if len(set(copied)) != len(copied):
        raise KnowledgeContractError(f"{field_name} contains duplicates")
    return tuple(sorted(copied, key=lambda item: item.value))


def _canonical_statement(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()


def _equivalence_sha256(
    knowledge_type: str,
    statement: str | None,
    content_ref: ContentRef | None,
    applicability: Mapping[str, str],
) -> str:
    return _sha256(
        {
            "applicability": dict(applicability),
            "content_ref": _content_payload(content_ref),
            "knowledge_type": knowledge_type,
            "statement": _canonical_statement(statement),
        }
    )


@dataclass(frozen=True)
class KnowledgeScopeSignals:
    """Structured contamination and uncertainty signals for scope policy."""

    project_identifiers: Sequence[str] = ()
    project_paths: Sequence[str] = ()
    private_endpoints: Sequence[str] = ()
    project_preferences: Sequence[str] = ()
    historical_authority: bool = False
    uncertain: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "project_identifiers",
            _freeze_strings(self.project_identifiers, "project_identifiers"),
        )
        object.__setattr__(
            self,
            "project_paths",
            _freeze_strings(self.project_paths, "project_paths"),
        )
        object.__setattr__(
            self,
            "private_endpoints",
            _freeze_strings(self.private_endpoints, "private_endpoints"),
        )
        object.__setattr__(
            self,
            "project_preferences",
            _freeze_strings(self.project_preferences, "project_preferences"),
        )
        if not isinstance(self.historical_authority, bool):
            raise KnowledgeContractError("historical_authority must be boolean")
        if not isinstance(self.uncertain, bool):
            raise KnowledgeContractError("uncertain must be boolean")

    def as_payload(self) -> dict[str, object]:
        return {
            "historical_authority": self.historical_authority,
            "private_endpoints": list(self.private_endpoints),
            "project_identifiers": list(self.project_identifiers),
            "project_paths": list(self.project_paths),
            "project_preferences": list(self.project_preferences),
            "uncertain": self.uncertain,
        }


@dataclass(frozen=True, order=True)
class KnowledgeCandidateRef:
    """Exact identity of one non-authoritative candidate and source Project."""

    source_project_ref: ProjectRef
    candidate_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_project_ref, ProjectRef):
            raise KnowledgeContractError("source ProjectRef is required")
        if (
            not isinstance(self.candidate_id, str)
            or _CANDIDATE_ID_PATTERN.fullmatch(self.candidate_id) is None
        ):
            raise KnowledgeContractError("candidate identity is malformed")

    @classmethod
    def new(cls, source_project_ref: ProjectRef) -> KnowledgeCandidateRef:
        return cls(source_project_ref, f"kc_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"knowledge-candidate://{self.source_project_ref.value}/{self.candidate_id}"


@dataclass(frozen=True, order=True)
class KnowledgeRef:
    """Exact identity of one immutable scoped knowledge revision."""

    scope: str
    project_ref: ProjectRef | None
    knowledge_id: str
    version: int

    def __post_init__(self) -> None:
        _validate_scope(self.scope)
        if self.scope == "PROJECT":
            if not isinstance(self.project_ref, ProjectRef):
                raise KnowledgeContractError("PROJECT KnowledgeRef requires ProjectRef")
        elif self.project_ref is not None:
            raise KnowledgeContractError("global KnowledgeRef cannot carry ProjectRef")
        if (
            not isinstance(self.knowledge_id, str)
            or _KNOWLEDGE_ID_PATTERN.fullmatch(self.knowledge_id) is None
        ):
            raise KnowledgeContractError("knowledge identity is malformed")
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 1
        ):
            raise KnowledgeContractError("knowledge version must be positive")

    @classmethod
    def new(
        cls,
        scope: str,
        project_ref: ProjectRef | None = None,
    ) -> KnowledgeRef:
        return cls(scope, project_ref, f"kn_{uuid4().hex}", 1)

    def next_version(self) -> KnowledgeRef:
        return KnowledgeRef(
            self.scope,
            self.project_ref,
            self.knowledge_id,
            self.version + 1,
        )

    @property
    def value(self) -> str:
        scope_identity = (
            "global" if self.project_ref is None else self.project_ref.value
        )
        return (
            f"knowledge://{self.scope.lower()}/{scope_identity}/"
            f"{self.knowledge_id}/{self.version}"
        )


@dataclass(frozen=True, order=True)
class KnowledgePromotionAccess:
    """Opaque capability for classification and supported placement."""

    authority_id: str
    token: str = field(compare=False, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.authority_id, str)
            or _AUTHORITY_ID_PATTERN.fullmatch(self.authority_id) is None
        ):
            raise KnowledgeContractError("promotion authority identity is malformed")
        if (
            not isinstance(self.token, str)
            or _AUTHORITY_TOKEN_PATTERN.fullmatch(self.token) is None
        ):
            raise KnowledgeContractError("promotion authority token is malformed")

    @classmethod
    def new(cls) -> KnowledgePromotionAccess:
        return cls(f"kpa_{uuid4().hex}", f"kpsecret_{secrets.token_hex(32)}")


@dataclass(frozen=True, order=True)
class KnowledgeProvisioningAccess:
    """Deployment root capability kept outside Project and executor APIs."""

    root_id: str
    token: str = field(compare=False, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.root_id, str)
            or _PROVISIONING_ID_PATTERN.fullmatch(self.root_id) is None
        ):
            raise KnowledgeContractError("provisioning root identity is malformed")
        if (
            not isinstance(self.token, str)
            or _PROVISIONING_TOKEN_PATTERN.fullmatch(self.token) is None
        ):
            raise KnowledgeContractError("provisioning root token is malformed")

@dataclass(frozen=True)
class KnowledgeScopeEvidence:
    """Independent durable evidence used by the promotion scope classifier."""

    evidence_id: str
    idempotency_key: str
    evidence_refs: tuple[ArtifactRef, ...]
    universality_basis: str
    content_semantics_verified: bool
    provenance_sha256: str
    recorded_by: str
    recorded_at: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.evidence_id, str)
            or _SCOPE_EVIDENCE_ID_PATTERN.fullmatch(self.evidence_id) is None
        ):
            raise KnowledgeContractError("scope evidence identity is malformed")
        _validate_key(self.idempotency_key, "idempotency_key")
        evidence = _freeze_global_artifact_refs(self.evidence_refs, "evidence_refs")
        if len({item.project_ref for item in evidence}) < 2:
            raise KnowledgeContractError(
                "scope evidence requires independent exact evidence from two Projects"
            )
        object.__setattr__(self, "evidence_refs", evidence)
        if (
            not isinstance(self.universality_basis, str)
            or not self.universality_basis.strip()
            or len(self.universality_basis.encode()) > 4096
        ):
            raise KnowledgeContractError("scope evidence basis is malformed")
        if not isinstance(self.content_semantics_verified, bool):
            raise KnowledgeContractError("content_semantics_verified must be boolean")
        _validate_sha256(self.provenance_sha256, "provenance_sha256")
        if (
            not isinstance(self.recorded_by, str)
            or _AUTHORITY_ID_PATTERN.fullmatch(self.recorded_by) is None
        ):
            raise KnowledgeContractError("scope evidence recorder is malformed")
        _validate_timestamp(self.recorded_at, "recorded_at")
        semantic = _sha256(
            {
                "content_semantics_verified": self.content_semantics_verified,
                "evidence_id": self.evidence_id,
                "evidence_refs": [item.value for item in self.evidence_refs],
                "idempotency_key": self.idempotency_key,
                "provenance_sha256": self.provenance_sha256,
                "recorded_by": self.recorded_by,
                "universality_basis": self.universality_basis,
            }
        )
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"recorded_at": self.recorded_at, "semantic_digest": semantic}),
        )


@dataclass(frozen=True)
class KnowledgeCandidate:
    """Immutable observation; never supported knowledge by itself."""

    candidate_ref: KnowledgeCandidateRef
    idempotency_key: str
    proposed_scope: str
    origin_type: str
    knowledge_type: str
    statement: str | None
    content_ref: ContentRef | None
    applicability: Mapping[str, str]
    source_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    source_run_ref: RunRef | None
    source_run_identity_sha256: str | None
    evidence_strength: str
    universality_basis: str | None
    scope_signals: KnowledgeScopeSignals
    migration_candidate_id: str | None
    migration_classification: str | None
    migration_provenance: Mapping[str, str]
    provenance_sha256: str
    created_at: str
    equivalence_sha256: str = field(init=False)
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_ref, KnowledgeCandidateRef):
            raise KnowledgeContractError("candidate_ref is required")
        _validate_key(self.idempotency_key, "idempotency_key")
        _validate_scope(self.proposed_scope)
        _validate_type(self.origin_type, "origin_type")
        _validate_type(self.knowledge_type, "knowledge_type")
        statement, content_ref = _validate_statement_or_content(
            self.statement,
            self.content_ref,
        )
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "content_ref", content_ref)
        applicability = _freeze_mapping(self.applicability, "applicability")
        object.__setattr__(self, "applicability", applicability)
        sources = _freeze_project_artifact_refs(
            self.source_refs,
            self.source_project_ref,
            "source_refs",
        )
        evidence = _freeze_project_artifact_refs(
            self.evidence_refs,
            self.source_project_ref,
            "evidence_refs",
        )
        if not sources:
            raise KnowledgeContractError("candidate requires provenance source_refs")
        object.__setattr__(self, "source_refs", sources)
        object.__setattr__(self, "evidence_refs", evidence)
        if self.source_run_ref is not None:
            if (
                not isinstance(self.source_run_ref, RunRef)
                or self.source_run_ref.project_ref != self.source_project_ref
            ):
                raise KnowledgeScopeError("source Run crossed Project scope")
            _validate_sha256(
                self.source_run_identity_sha256,
                "source_run_identity_sha256",
            )
        elif self.source_run_identity_sha256 is not None:
            raise KnowledgeContractError("Run identity digest has no source Run")
        _validate_evidence_strength(self.evidence_strength)
        if self.universality_basis is not None and (
            not isinstance(self.universality_basis, str)
            or not self.universality_basis.strip()
            or len(self.universality_basis.encode()) > 4096
        ):
            raise KnowledgeContractError("universality_basis is malformed")
        if not isinstance(self.scope_signals, KnowledgeScopeSignals):
            raise KnowledgeContractError("KnowledgeScopeSignals is required")
        migration_provenance = _freeze_mapping(
            self.migration_provenance,
            "migration_provenance",
            limit=64,
            allow_empty_values=True,
        )
        object.__setattr__(self, "migration_provenance", migration_provenance)
        if (self.migration_candidate_id is None) != (
            self.migration_classification is None
        ):
            raise KnowledgeContractError("migration identity and classification differ")
        if self.migration_candidate_id is not None:
            if (
                not isinstance(self.migration_candidate_id, str)
                or _SHA256_PATTERN.fullmatch(self.migration_candidate_id) is None
                or not migration_provenance
            ):
                raise KnowledgeContractError("normalized migration identity is malformed")
            if self.origin_type != "migration.normalized":
                raise KnowledgeContractError("migration candidate origin is malformed")
        elif migration_provenance:
            raise KnowledgeContractError("migration provenance has no normalized candidate")
        _validate_sha256(self.provenance_sha256, "provenance_sha256")
        _validate_timestamp(self.created_at, "created_at")
        equivalence = _equivalence_sha256(
            self.knowledge_type,
            self.statement,
            self.content_ref,
            applicability,
        )
        object.__setattr__(self, "equivalence_sha256", equivalence)
        semantic = _sha256(self._semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "created_at": self.created_at,
                    "provenance_sha256": self.provenance_sha256,
                    "semantic_digest": semantic,
                }
            ),
        )

    @property
    def source_project_ref(self) -> ProjectRef:
        return self.candidate_ref.source_project_ref

    @property
    def status(self) -> str:
        return "CANDIDATE"

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "candidate_ref": self.candidate_ref.value,
            "content_ref": _content_payload(self.content_ref),
            "equivalence_sha256": self.equivalence_sha256,
            "evidence_refs": [item.value for item in self.evidence_refs],
            "evidence_strength": self.evidence_strength,
            "idempotency_key": self.idempotency_key,
            "knowledge_type": self.knowledge_type,
            "migration_candidate_id": self.migration_candidate_id,
            "migration_classification": self.migration_classification,
            "migration_provenance": dict(self.migration_provenance),
            "origin_type": self.origin_type,
            "proposed_scope": self.proposed_scope,
            "scope_signals": self.scope_signals.as_payload(),
            "source_refs": [item.value for item in self.source_refs],
            "source_run_identity_sha256": self.source_run_identity_sha256,
            "source_run_ref": (
                None
                if self.source_run_ref is None
                else {
                    "project_id": self.source_run_ref.project_ref.value,
                    "run_id": self.source_run_ref.run_id,
                }
            ),
            "statement": self.statement,
            "universality_basis": self.universality_basis,
        }


def _freeze_knowledge_refs(
    values: Sequence[KnowledgeRef],
    field_name: str,
) -> tuple[KnowledgeRef, ...]:
    copied = tuple(values)
    if len(copied) > 128:
        raise KnowledgeContractError(f"{field_name} is unbounded")
    if not all(isinstance(item, KnowledgeRef) for item in copied):
        raise KnowledgeContractError(f"{field_name} accepts KnowledgeRef values")
    if len(set(copied)) != len(copied):
        raise KnowledgeContractError(f"{field_name} contains duplicates")
    return tuple(sorted(copied, key=lambda item: item.value))


@dataclass(frozen=True)
class KnowledgeScopeDecision:
    """Durable classifier and evidence-resolution result for one candidate."""

    candidate_ref: KnowledgeCandidateRef
    candidate_record_sha256: str
    classified_scope: str
    project_ref: ProjectRef | None
    scope_evidence_id: str | None
    scope_evidence_record_sha256: str | None
    status: str
    reasons: tuple[str, ...]
    duplicate_refs: tuple[KnowledgeRef, ...]
    contradicts_refs: tuple[KnowledgeRef, ...]
    idempotency_key: str
    evaluated_by: str
    evaluated_at: str
    request_sha256: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_ref, KnowledgeCandidateRef):
            raise KnowledgeContractError("candidate_ref is required")
        _validate_sha256(self.candidate_record_sha256, "candidate_record_sha256")
        _validate_scope(self.classified_scope)
        if self.classified_scope == "PROJECT":
            if self.project_ref != self.candidate_ref.source_project_ref:
                raise KnowledgeScopeError("classified Project scope differs")
            expected_status = "ROUTE_PROJECT"
        else:
            if self.project_ref is not None:
                raise KnowledgeScopeError("global classification carries ProjectRef")
            expected_status = "ELIGIBLE"
        if self.status not in _DECISION_STATUSES or self.status != expected_status:
            raise KnowledgeContractError("classification status is malformed")
        if (self.scope_evidence_id is None) != (
            self.scope_evidence_record_sha256 is None
        ):
            raise KnowledgeContractError("scope evidence identity and digest differ")
        if self.scope_evidence_id is not None:
            if _SCOPE_EVIDENCE_ID_PATTERN.fullmatch(self.scope_evidence_id) is None:
                raise KnowledgeContractError("scope evidence identity is malformed")
            _validate_sha256(
                self.scope_evidence_record_sha256,
                "scope_evidence_record_sha256",
            )
        object.__setattr__(self, "reasons", _freeze_strings(self.reasons, "reasons"))
        duplicates = _freeze_knowledge_refs(self.duplicate_refs, "duplicate_refs")
        contradicts = _freeze_knowledge_refs(self.contradicts_refs, "contradicts_refs")
        if set(duplicates) & set(contradicts):
            raise KnowledgeConflictError("one revision cannot duplicate and contradict")
        for ref in (*duplicates, *contradicts):
            if ref.scope != self.classified_scope or ref.project_ref != self.project_ref:
                raise KnowledgeScopeError("classification relationship crossed scope")
        object.__setattr__(self, "duplicate_refs", duplicates)
        object.__setattr__(self, "contradicts_refs", contradicts)
        _validate_key(self.idempotency_key, "idempotency_key")
        if (
            not isinstance(self.evaluated_by, str)
            or _AUTHORITY_ID_PATTERN.fullmatch(self.evaluated_by) is None
        ):
            raise KnowledgeContractError("evaluated_by is malformed")
        _validate_timestamp(self.evaluated_at, "evaluated_at")
        _validate_sha256(self.request_sha256, "request_sha256")
        semantic = _sha256(self._semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"evaluated_at": self.evaluated_at, "semantic_digest": semantic}),
        )

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "candidate_record_sha256": self.candidate_record_sha256,
            "candidate_ref": self.candidate_ref.value,
            "classified_scope": self.classified_scope,
            "contradicts_refs": [item.value for item in self.contradicts_refs],
            "duplicate_refs": [item.value for item in self.duplicate_refs],
            "evaluated_by": self.evaluated_by,
            "idempotency_key": self.idempotency_key,
            "project_ref": None if self.project_ref is None else self.project_ref.value,
            "reasons": list(self.reasons),
            "scope_evidence_id": self.scope_evidence_id,
            "scope_evidence_record_sha256": self.scope_evidence_record_sha256,
            "request_sha256": self.request_sha256,
            "status": self.status,
        }


@dataclass(frozen=True)
class Knowledge:
    """One immutable supported or historical knowledge revision."""

    knowledge_ref: KnowledgeRef
    candidate_ref: KnowledgeCandidateRef
    candidate_record_sha256: str
    decision_record_sha256: str
    knowledge_type: str
    statement: str | None
    content_ref: ContentRef | None
    applicability: Mapping[str, str]
    source_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    evidence_strength: str
    provenance_sha256: str
    migration_candidate_id: str | None
    promoted_by: str
    promoted_at: str
    supersedes_refs: tuple[KnowledgeRef, ...]
    contradicts_refs: tuple[KnowledgeRef, ...]
    placement_idempotency_key: str
    equivalence_sha256: str = field(init=False)
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.knowledge_ref, KnowledgeRef):
            raise KnowledgeContractError("knowledge_ref is required")
        if self.scope == "PROJECT":
            raise KnowledgeScopeError("accepted PROJECT truth belongs to ProjectKnowledge")
        if not isinstance(self.candidate_ref, KnowledgeCandidateRef):
            raise KnowledgeContractError("candidate_ref is required")
        _validate_sha256(self.candidate_record_sha256, "candidate_record_sha256")
        _validate_sha256(self.decision_record_sha256, "decision_record_sha256")
        _validate_type(self.knowledge_type, "knowledge_type")
        statement, content_ref = _validate_statement_or_content(
            self.statement,
            self.content_ref,
        )
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "content_ref", content_ref)
        applicability = _freeze_mapping(self.applicability, "applicability")
        object.__setattr__(self, "applicability", applicability)
        object.__setattr__(
            self,
            "source_refs",
            _freeze_global_artifact_refs(self.source_refs, "source_refs"),
        )
        evidence = _freeze_global_artifact_refs(self.evidence_refs, "evidence_refs")
        object.__setattr__(self, "evidence_refs", evidence)
        _validate_evidence_strength(self.evidence_strength)
        if self.scope == "ENGINE" and not evidence:
            raise KnowledgeContractError("supported ENGINE knowledge requires evidence")
        _validate_sha256(self.provenance_sha256, "provenance_sha256")
        if self.migration_candidate_id is not None and (
            not isinstance(self.migration_candidate_id, str)
            or _SHA256_PATTERN.fullmatch(self.migration_candidate_id) is None
        ):
            raise KnowledgeContractError("migration candidate identity is malformed")
        if (
            not isinstance(self.promoted_by, str)
            or _AUTHORITY_ID_PATTERN.fullmatch(self.promoted_by) is None
        ):
            raise KnowledgeContractError("promoted_by is malformed")
        _validate_timestamp(self.promoted_at, "promoted_at")
        supersedes = _freeze_knowledge_refs(self.supersedes_refs, "supersedes_refs")
        contradicts = _freeze_knowledge_refs(self.contradicts_refs, "contradicts_refs")
        for ref in (*supersedes, *contradicts):
            if (
                ref.scope != self.scope
                or ref.project_ref != self.project_ref
                or ref.knowledge_id != self.knowledge_ref.knowledge_id
                or ref.version >= self.knowledge_ref.version
            ):
                raise KnowledgeContractError("knowledge relationship is not earlier history")
        if set(supersedes) & set(contradicts):
            raise KnowledgeConflictError("revision cannot supersede and contradict one target")
        object.__setattr__(self, "supersedes_refs", supersedes)
        object.__setattr__(self, "contradicts_refs", contradicts)
        _validate_key(self.placement_idempotency_key, "placement_idempotency_key")
        equivalence = _equivalence_sha256(
            self.knowledge_type,
            self.statement,
            self.content_ref,
            applicability,
        )
        object.__setattr__(self, "equivalence_sha256", equivalence)
        semantic = _sha256(self._semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"promoted_at": self.promoted_at, "semantic_digest": semantic}),
        )

    def __hash__(self) -> int:
        return hash((self.knowledge_ref, self.record_sha256))

    @property
    def scope(self) -> str:
        return self.knowledge_ref.scope

    @property
    def project_ref(self) -> ProjectRef | None:
        return self.knowledge_ref.project_ref

    @property
    def status(self) -> str:
        return "SUPPORTED" if self.scope == "ENGINE" else "HISTORICAL"

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "candidate_record_sha256": self.candidate_record_sha256,
            "candidate_ref": self.candidate_ref.value,
            "content_ref": _content_payload(self.content_ref),
            "contradicts_refs": [item.value for item in self.contradicts_refs],
            "decision_record_sha256": self.decision_record_sha256,
            "equivalence_sha256": self.equivalence_sha256,
            "evidence_refs": [item.value for item in self.evidence_refs],
            "evidence_strength": self.evidence_strength,
            "knowledge_ref": self.knowledge_ref.value,
            "knowledge_type": self.knowledge_type,
            "migration_candidate_id": self.migration_candidate_id,
            "placement_idempotency_key": self.placement_idempotency_key,
            "promoted_by": self.promoted_by,
            "provenance_sha256": self.provenance_sha256,
            "source_refs": [item.value for item in self.source_refs],
            "statement": self.statement,
            "supersedes_refs": [item.value for item in self.supersedes_refs],
        }


@dataclass(frozen=True)
class KnowledgeResolution:
    """Current supported state or an explicit unresolved contradiction."""

    scope: str
    project_ref: ProjectRef | None
    knowledge_id: str
    status: str
    current: Knowledge | None
    candidates: tuple[Knowledge, ...]

    def __post_init__(self) -> None:
        _validate_scope(self.scope)
        if self.scope == "PROJECT":
            raise KnowledgeScopeError("Project currentness belongs to ProjectKnowledge")
        if self.project_ref is not None:
            raise KnowledgeScopeError("global resolution cannot carry ProjectRef")
        if (
            not isinstance(self.knowledge_id, str)
            or _KNOWLEDGE_ID_PATTERN.fullmatch(self.knowledge_id) is None
        ):
            raise KnowledgeContractError("knowledge identity is malformed")
        if self.status not in _RESOLUTION_STATUSES:
            raise KnowledgeContractError("resolution status is malformed")
        object.__setattr__(self, "candidates", tuple(self.candidates))
        if not self.candidates:
            raise KnowledgeIntegrityError("resolution has no candidates")
        if any(
            item.scope != self.scope
            or item.project_ref != self.project_ref
            or item.knowledge_ref.knowledge_id != self.knowledge_id
            for item in self.candidates
        ):
            raise KnowledgeIntegrityError("resolution identity differs")
        if self.status == "CURRENT":
            if len(self.candidates) != 1 or self.current != self.candidates[0]:
                raise KnowledgeIntegrityError("current resolution is inconsistent")
        elif self.current is not None or len(self.candidates) < 2:
            raise KnowledgeIntegrityError("conflict resolution is inconsistent")


class KnowledgeScopeClassifier:
    """Extensible structured policy plus observed Project-identity defense."""

    def classify(
        self,
        candidate: KnowledgeCandidate,
        project: Project,
        scope_evidence: KnowledgeScopeEvidence | None,
    ) -> tuple[str, ProjectRef | None, tuple[str, ...]]:
        if candidate.proposed_scope == "HISTORICAL" or (
            candidate.scope_signals.historical_authority
        ):
            return "HISTORICAL", None, ("historical_authority",)
        migration_classification = candidate.migration_classification
        if migration_classification in {
            "HISTORICAL_EVIDENCE",
            "DUPLICATE",
            "OBSOLETE_OR_DRIFT",
        }:
            return "HISTORICAL", None, ("historical_migration_classification",)
        if candidate.proposed_scope == "PROJECT":
            return "PROJECT", candidate.source_project_ref, ("proposed_project_scope",)

        signals: KnowledgeScopeSignals = candidate.scope_signals
        structured_reasons: list[str] = []
        if signals.project_identifiers:
            structured_reasons.append("structured_project_identifier")
        if signals.project_paths:
            structured_reasons.append("structured_project_path")
        if signals.private_endpoints:
            structured_reasons.append("structured_private_endpoint")
        if signals.project_preferences:
            structured_reasons.append("structured_project_preference")
        if signals.uncertain:
            structured_reasons.append("uncertain_scope")

        observed_text = " ".join(
            (
                candidate.statement or "",
                *candidate.applicability.values(),
            )
        ).casefold()
        observed_identities = {
            candidate.source_project_ref.value.casefold(),
            project.namespace.casefold(),
            project.display_name.casefold(),
        }
        if any(identity and identity in observed_text for identity in observed_identities):
            structured_reasons.append("observed_source_project_identity")
        if structured_reasons:
            return "PROJECT", candidate.source_project_ref, tuple(structured_reasons)
        if candidate.evidence_strength == "OBSERVATION":
            return "PROJECT", candidate.source_project_ref, ("insufficient_evidence_strength",)
        if not candidate.evidence_refs:
            return "PROJECT", candidate.source_project_ref, ("missing_supporting_evidence",)
        if candidate.universality_basis is None:
            return "PROJECT", candidate.source_project_ref, ("missing_universality_basis",)
        if scope_evidence is None:
            return "PROJECT", candidate.source_project_ref, ("missing_independent_scope_evidence",)
        if candidate.content_ref is not None and not scope_evidence.content_semantics_verified:
            return "PROJECT", candidate.source_project_ref, ("opaque_content_not_semantically_verified",)
        return "ENGINE", None, ("project_neutral_supported_candidate",)


class KnowledgeService:
    """Candidate, classifier, resolver, and privileged placement boundary."""

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.runs = RunService(self.database_path)
        self.project_knowledge = ProjectKnowledgeService(self.database_path)
        self.classifier = KnowledgeScopeClassifier()
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
                CREATE TABLE IF NOT EXISTS knowledge_provisioning_roots (
                    root_id TEXT PRIMARY KEY NOT NULL,
                    token_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    UNIQUE (root_id, record_sha256)
                );

                CREATE TABLE IF NOT EXISTS knowledge_promotion_authorities (
                    authority_id TEXT PRIMARY KEY NOT NULL,
                    token_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    UNIQUE (authority_id, record_sha256)
                );

                CREATE TABLE IF NOT EXISTS knowledge_candidates (
                    source_project_id TEXT NOT NULL,
                    candidate_id TEXT PRIMARY KEY NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    proposed_scope TEXT NOT NULL,
                    origin_type TEXT NOT NULL,
                    knowledge_type TEXT NOT NULL,
                    statement TEXT,
                    content_json TEXT,
                    applicability_json TEXT NOT NULL,
                    source_run_id TEXT,
                    source_run_identity_sha256 TEXT,
                    evidence_strength TEXT NOT NULL,
                    universality_basis TEXT,
                    scope_signals_json TEXT NOT NULL,
                    migration_candidate_id TEXT,
                    migration_classification TEXT,
                    migration_provenance_json TEXT NOT NULL,
                    provenance_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    equivalence_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    UNIQUE (source_project_id, idempotency_key),
                    UNIQUE (candidate_id, record_sha256),
                    FOREIGN KEY (source_project_id) REFERENCES projects(project_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_candidate_artifacts (
                    candidate_id TEXT NOT NULL,
                    binding_kind TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (candidate_id, binding_kind, position),
                    UNIQUE (
                        candidate_id, binding_kind, project_id,
                        artifact_id, artifact_revision
                    ),
                    FOREIGN KEY (candidate_id) REFERENCES knowledge_candidates(candidate_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_scope_decisions (
                    candidate_id TEXT PRIMARY KEY NOT NULL,
                    candidate_record_sha256 TEXT NOT NULL,
                    classified_scope TEXT NOT NULL,
                    project_scope_id TEXT,
                    scope_evidence_id TEXT,
                    scope_evidence_record_sha256 TEXT,
                    status TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    duplicate_refs_json TEXT NOT NULL,
                    contradicts_refs_json TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    evaluated_by TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    UNIQUE (candidate_id, record_sha256),
                    FOREIGN KEY (candidate_id, candidate_record_sha256)
                        REFERENCES knowledge_candidates(candidate_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (evaluated_by)
                        REFERENCES knowledge_promotion_authorities(authority_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (scope_evidence_id, scope_evidence_record_sha256)
                        REFERENCES knowledge_scope_evidence(evidence_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_scope_evidence (
                    evidence_id TEXT PRIMARY KEY NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    universality_basis TEXT NOT NULL,
                    content_semantics_verified INTEGER NOT NULL,
                    provenance_sha256 TEXT NOT NULL,
                    recorded_by TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    UNIQUE (evidence_id, record_sha256),
                    FOREIGN KEY (recorded_by)
                        REFERENCES knowledge_promotion_authorities(authority_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_scope_evidence_artifacts (
                    evidence_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (evidence_id, position),
                    FOREIGN KEY (evidence_id) REFERENCES knowledge_scope_evidence(evidence_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_revisions (
                    scope TEXT NOT NULL,
                    project_scope_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    candidate_id TEXT NOT NULL,
                    candidate_record_sha256 TEXT NOT NULL,
                    decision_record_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    knowledge_type TEXT NOT NULL,
                    statement TEXT,
                    content_json TEXT,
                    applicability_json TEXT NOT NULL,
                    evidence_strength TEXT NOT NULL,
                    provenance_sha256 TEXT NOT NULL,
                    migration_candidate_id TEXT,
                    promoted_by TEXT NOT NULL,
                    promoted_at TEXT NOT NULL,
                    placement_idempotency_key TEXT UNIQUE NOT NULL,
                    placement_request_sha256 TEXT NOT NULL,
                    equivalence_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (scope, project_scope_id, knowledge_id, version),
                    UNIQUE (scope, project_scope_id, knowledge_id, version, record_sha256),
                    UNIQUE (candidate_id),
                    FOREIGN KEY (candidate_id, candidate_record_sha256)
                        REFERENCES knowledge_candidates(candidate_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (candidate_id, decision_record_sha256)
                        REFERENCES knowledge_scope_decisions(candidate_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (promoted_by)
                        REFERENCES knowledge_promotion_authorities(authority_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_revision_artifacts (
                    scope TEXT NOT NULL,
                    project_scope_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    binding_kind TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        scope, project_scope_id, knowledge_id, version,
                        binding_kind, position
                    ),
                    FOREIGN KEY (scope, project_scope_id, knowledge_id, version)
                        REFERENCES knowledge_revisions(
                            scope, project_scope_id, knowledge_id, version
                        ) ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    source_scope TEXT NOT NULL,
                    source_project_scope_id TEXT NOT NULL,
                    source_knowledge_id TEXT NOT NULL,
                    source_version INTEGER NOT NULL,
                    relation_type TEXT NOT NULL,
                    target_scope TEXT NOT NULL,
                    target_project_scope_id TEXT NOT NULL,
                    target_knowledge_id TEXT NOT NULL,
                    target_version INTEGER NOT NULL,
                    target_record_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        source_scope, source_project_scope_id,
                        source_knowledge_id, source_version,
                        relation_type, target_version
                    ),
                    FOREIGN KEY (
                        source_scope, source_project_scope_id,
                        source_knowledge_id, source_version
                    ) REFERENCES knowledge_revisions(
                        scope, project_scope_id, knowledge_id, version
                    ) ON DELETE RESTRICT,
                    FOREIGN KEY (
                        target_scope, target_project_scope_id,
                        target_knowledge_id, target_version,
                        target_record_sha256
                    ) REFERENCES knowledge_revisions(
                        scope, project_scope_id, knowledge_id, version, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS knowledge_identity_heads (
                    scope TEXT NOT NULL,
                    project_scope_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    maximum_version INTEGER NOT NULL,
                    history_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (scope, project_scope_id, knowledge_id)
                );

                CREATE TABLE IF NOT EXISTS knowledge_search_cache (
                    cache_key TEXT PRIMARY KEY NOT NULL,
                    value_json TEXT NOT NULL,
                    built_at TEXT NOT NULL
                );

                CREATE TRIGGER IF NOT EXISTS knowledge_provisioning_roots_no_update
                BEFORE UPDATE ON knowledge_provisioning_roots
                BEGIN SELECT RAISE(ABORT, 'Knowledge provisioning root is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_provisioning_roots_no_delete
                BEFORE DELETE ON knowledge_provisioning_roots
                BEGIN SELECT RAISE(ABORT, 'Knowledge provisioning root cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_promotion_authorities_no_update
                BEFORE UPDATE ON knowledge_promotion_authorities
                BEGIN SELECT RAISE(ABORT, 'Knowledge authority is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_promotion_authorities_no_delete
                BEFORE DELETE ON knowledge_promotion_authorities
                BEGIN SELECT RAISE(ABORT, 'Knowledge authority cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_candidates_no_update
                BEFORE UPDATE ON knowledge_candidates
                BEGIN SELECT RAISE(ABORT, 'Knowledge candidate is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_candidates_no_delete
                BEFORE DELETE ON knowledge_candidates
                BEGIN SELECT RAISE(ABORT, 'Knowledge candidate cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_candidate_artifacts_no_update
                BEFORE UPDATE ON knowledge_candidate_artifacts
                BEGIN SELECT RAISE(ABORT, 'Candidate evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_candidate_artifacts_no_delete
                BEFORE DELETE ON knowledge_candidate_artifacts
                BEGIN SELECT RAISE(ABORT, 'Candidate evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_scope_decisions_no_update
                BEFORE UPDATE ON knowledge_scope_decisions
                BEGIN SELECT RAISE(ABORT, 'Scope decision is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_scope_decisions_no_delete
                BEFORE DELETE ON knowledge_scope_decisions
                BEGIN SELECT RAISE(ABORT, 'Scope decision cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_scope_evidence_no_update
                BEFORE UPDATE ON knowledge_scope_evidence
                BEGIN SELECT RAISE(ABORT, 'Scope evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_scope_evidence_no_delete
                BEFORE DELETE ON knowledge_scope_evidence
                BEGIN SELECT RAISE(ABORT, 'Scope evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_scope_evidence_artifacts_no_update
                BEFORE UPDATE ON knowledge_scope_evidence_artifacts
                BEGIN SELECT RAISE(ABORT, 'Scope evidence binding is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_scope_evidence_artifacts_no_delete
                BEFORE DELETE ON knowledge_scope_evidence_artifacts
                BEGIN SELECT RAISE(ABORT, 'Scope evidence binding cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_revisions_no_update
                BEFORE UPDATE ON knowledge_revisions
                BEGIN SELECT RAISE(ABORT, 'Knowledge revision is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_revisions_no_delete
                BEFORE DELETE ON knowledge_revisions
                BEGIN SELECT RAISE(ABORT, 'Knowledge revision cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_revision_artifacts_no_update
                BEFORE UPDATE ON knowledge_revision_artifacts
                BEGIN SELECT RAISE(ABORT, 'Knowledge evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_revision_artifacts_no_delete
                BEFORE DELETE ON knowledge_revision_artifacts
                BEGIN SELECT RAISE(ABORT, 'Knowledge evidence cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_relations_no_update
                BEFORE UPDATE ON knowledge_relations
                BEGIN SELECT RAISE(ABORT, 'Knowledge relation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_relations_no_delete
                BEFORE DELETE ON knowledge_relations
                BEGIN SELECT RAISE(ABORT, 'Knowledge relation cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_identity_heads_monotonic_update
                BEFORE UPDATE ON knowledge_identity_heads
                WHEN NEW.maximum_version != OLD.maximum_version + 1
                  OR NEW.updated_at < OLD.updated_at
                BEGIN SELECT RAISE(ABORT, 'Knowledge head must advance monotonically'); END;
                CREATE TRIGGER IF NOT EXISTS knowledge_identity_heads_no_delete
                BEFORE DELETE ON knowledge_identity_heads
                BEGIN SELECT RAISE(ABORT, 'Knowledge head cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _authorize_provisioning(
        self,
        connection: sqlite3.Connection,
        access: KnowledgeProvisioningAccess,
    ) -> str:
        if not isinstance(access, KnowledgeProvisioningAccess):
            raise KnowledgeAuthorityError("KnowledgeProvisioningAccess is required")
        rows = connection.execute(
            "SELECT * FROM knowledge_provisioning_roots ORDER BY root_id"
        ).fetchall()
        if not rows:
            raise KnowledgeAuthorityError("deployment provisioning root is not configured")
        if len(rows) != 1:
            raise KnowledgeIntegrityError("multiple provisioning roots exist")
        row = rows[0]
        observed_record = _sha256(
            {
                "created_at": row["created_at"],
                "root_id": row["root_id"],
                "token_sha256": row["token_sha256"],
            }
        )
        self._verify_digest(
            cast(str, row["record_sha256"]),
            observed_record,
            "provisioning root",
        )
        token_sha256 = hashlib.sha256(access.token.encode()).hexdigest()
        if row["root_id"] != access.root_id or not hmac.compare_digest(
            cast(str, row["token_sha256"]),
            token_sha256,
        ):
            raise KnowledgeAuthorityError("provisioning root credentials differ")
        return access.root_id

    def provision_promotion_authority(
        self,
        provisioning_access: KnowledgeProvisioningAccess,
    ) -> KnowledgePromotionAccess:
        access = KnowledgePromotionAccess.new()
        created_at = _now_utc()
        token_sha256 = hashlib.sha256(access.token.encode()).hexdigest()
        record_sha256 = _sha256(
            {
                "authority_id": access.authority_id,
                "created_at": created_at,
                "token_sha256": token_sha256,
            }
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize_provisioning(connection, provisioning_access)
            if connection.execute(
                "SELECT 1 FROM knowledge_promotion_authorities LIMIT 1"
            ).fetchone() is not None:
                raise KnowledgeConflictError("promotion authority is already bootstrapped")
            connection.execute(
                "INSERT INTO knowledge_promotion_authorities VALUES (?, ?, ?, ?)",
                (access.authority_id, token_sha256, created_at, record_sha256),
            )
            connection.commit()
            return access
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_scope_evidence(
        self,
        promotion_access: KnowledgePromotionAccess,
        *,
        idempotency_key: str,
        evidence_refs: Sequence[ArtifactRef],
        universality_basis: str,
        content_semantics_verified: bool,
    ) -> KnowledgeScopeEvidence:
        _validate_key(idempotency_key, "idempotency_key")
        normalized_refs = _freeze_global_artifact_refs(
            evidence_refs,
            "evidence_refs",
        )
        if len({item.project_ref for item in normalized_refs}) < 2:
            raise KnowledgeContractError(
                "scope evidence requires independent exact evidence from two Projects"
            )
        if (
            not isinstance(universality_basis, str)
            or not universality_basis.strip()
            or len(universality_basis.encode()) > 4096
        ):
            raise KnowledgeContractError("scope evidence basis is malformed")
        if not isinstance(content_semantics_verified, bool):
            raise KnowledgeContractError("content_semantics_verified must be boolean")
        request_sha256 = _sha256(
            {
                "content_semantics_verified": content_semantics_verified,
                "evidence_refs": [item.value for item in normalized_refs],
                "idempotency_key": idempotency_key,
                "universality_basis": universality_basis,
            }
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            authority_id = self._authorize_promotion(connection, promotion_access)
            prior = connection.execute(
                "SELECT * FROM knowledge_scope_evidence WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(
                    cast(str, prior["request_sha256"]),
                    request_sha256,
                ):
                    raise KnowledgeConflictError(
                        "scope evidence idempotency key has different semantics"
                    )
                result = self._fetch_scope_evidence(
                    connection,
                    cast(str, prior["evidence_id"]),
                )
                connection.commit()
                return result
            artifacts = tuple(
                self.artifacts._fetch_artifact(connection, ref)
                for ref in normalized_refs
            )
            if any(item.role != "knowledge.scope-evidence" for item in artifacts):
                raise KnowledgeIntegrityError(
                    "scope classification evidence lacks its independent role"
                )
            provenance_sha256 = _sha256(
                {
                    "artifacts": [
                        {
                            "position": position,
                            "record_sha256": artifact.record_sha256,
                            "ref": artifact.artifact_ref.value,
                        }
                        for position, artifact in enumerate(artifacts)
                    ],
                    "recorded_by": authority_id,
                }
            )
            evidence = KnowledgeScopeEvidence(
                evidence_id=f"kse_{uuid4().hex}",
                idempotency_key=idempotency_key,
                evidence_refs=normalized_refs,
                universality_basis=universality_basis,
                content_semantics_verified=content_semantics_verified,
                provenance_sha256=provenance_sha256,
                recorded_by=authority_id,
                recorded_at=_now_utc(),
            )
            connection.execute(
                "INSERT INTO knowledge_scope_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    evidence.evidence_id,
                    evidence.idempotency_key,
                    evidence.universality_basis,
                    int(evidence.content_semantics_verified),
                    evidence.provenance_sha256,
                    evidence.recorded_by,
                    evidence.recorded_at,
                    request_sha256,
                    evidence.semantic_digest,
                    evidence.record_sha256,
                ),
            )
            for position, artifact in enumerate(artifacts):
                binding_record = _sha256(
                    {
                        "artifact_record_sha256": artifact.record_sha256,
                        "artifact_ref": artifact.artifact_ref.value,
                        "evidence_id": evidence.evidence_id,
                        "position": position,
                    }
                )
                connection.execute(
                    "INSERT INTO knowledge_scope_evidence_artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        evidence.evidence_id,
                        position,
                        artifact.artifact_ref.project_ref.value,
                        artifact.artifact_ref.artifact_id,
                        artifact.artifact_ref.revision,
                        artifact.record_sha256,
                        binding_record,
                    ),
                )
            connection.commit()
            return evidence
        except (ArtifactError, ProjectError) as exc:
            connection.rollback()
            raise KnowledgeIntegrityError(
                "scope evidence failed exact artifact verification"
            ) from exc
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise KnowledgeConflictError("scope evidence write conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch_scope_evidence(
        self,
        connection: sqlite3.Connection,
        evidence_id: str,
    ) -> KnowledgeScopeEvidence:
        if (
            not isinstance(evidence_id, str)
            or _SCOPE_EVIDENCE_ID_PATTERN.fullmatch(evidence_id) is None
        ):
            raise KnowledgeContractError("scope evidence identity is malformed")
        row = connection.execute(
            "SELECT * FROM knowledge_scope_evidence WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("scope evidence does not exist")
        binding_rows = connection.execute(
            """
            SELECT * FROM knowledge_scope_evidence_artifacts
            WHERE evidence_id = ? ORDER BY position
            """,
            (evidence_id,),
        ).fetchall()
        if [item["position"] for item in binding_rows] != list(range(len(binding_rows))):
            raise KnowledgeIntegrityError("scope evidence positions are not contiguous")
        artifacts: list[Artifact] = []
        try:
            for binding in binding_rows:
                artifact_ref = ArtifactRef(
                    ProjectRef(cast(str, binding["project_id"])),
                    cast(str, binding["artifact_id"]),
                    cast(int, binding["artifact_revision"]),
                )
                artifact = self.artifacts._fetch_artifact(connection, artifact_ref)
                if artifact.role != "knowledge.scope-evidence":
                    raise KnowledgeIntegrityError(
                        "scope classification evidence lost its independent role"
                    )
                self._verify_digest(
                    cast(str, binding["artifact_record_sha256"]),
                    artifact.record_sha256,
                    "scope evidence artifact",
                )
                binding_record = _sha256(
                    {
                        "artifact_record_sha256": artifact.record_sha256,
                        "artifact_ref": artifact.artifact_ref.value,
                        "evidence_id": evidence_id,
                        "position": binding["position"],
                    }
                )
                self._verify_digest(
                    cast(str, binding["record_sha256"]),
                    binding_record,
                    "scope evidence binding",
                )
                artifacts.append(artifact)
        except (ArtifactError, ProjectError) as exc:
            raise KnowledgeIntegrityError(
                "scope evidence failed exact artifact verification"
            ) from exc
        refs = tuple(item.artifact_ref for item in artifacts)
        recorded_by = cast(str, row["recorded_by"])
        self._verify_registered_authority(connection, recorded_by)
        provenance_sha256 = _sha256(
            {
                "artifacts": [
                    {
                        "position": position,
                        "record_sha256": artifact.record_sha256,
                        "ref": artifact.artifact_ref.value,
                    }
                    for position, artifact in enumerate(artifacts)
                ],
                "recorded_by": recorded_by,
            }
        )
        self._verify_digest(
            cast(str, row["provenance_sha256"]),
            provenance_sha256,
            "scope evidence provenance",
        )
        content_semantics_raw = row["content_semantics_verified"]
        if type(content_semantics_raw) is not int or content_semantics_raw not in (0, 1):
            raise KnowledgeIntegrityError("content_semantics_verified is malformed")
        evidence = KnowledgeScopeEvidence(
            evidence_id=cast(str, row["evidence_id"]),
            idempotency_key=cast(str, row["idempotency_key"]),
            evidence_refs=refs,
            universality_basis=cast(str, row["universality_basis"]),
            content_semantics_verified=bool(content_semantics_raw),
            provenance_sha256=cast(str, row["provenance_sha256"]),
            recorded_by=recorded_by,
            recorded_at=cast(str, row["recorded_at"]),
        )
        request_sha256 = _sha256(
            {
                "content_semantics_verified": evidence.content_semantics_verified,
                "evidence_refs": [item.value for item in evidence.evidence_refs],
                "idempotency_key": evidence.idempotency_key,
                "universality_basis": evidence.universality_basis,
            }
        )
        self._verify_digest(
            cast(str, row["request_sha256"]),
            request_sha256,
            "scope evidence request",
        )
        self._verify_digest(
            cast(str, row["semantic_digest"]),
            evidence.semantic_digest,
            "scope evidence semantics",
        )
        self._verify_digest(
            cast(str, row["record_sha256"]),
            evidence.record_sha256,
            "scope evidence record",
        )
        return evidence

    def write_supported_knowledge(self, _: object) -> NoReturn:
        raise KnowledgeAuthorityError(
            "direct supported writes are prohibited; use candidate evaluation and promotion"
        )

    def record_candidate(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        idempotency_key: str,
        proposed_scope: str,
        origin_type: str,
        knowledge_type: str,
        statement: str | None,
        content_ref: ContentRef | None,
        applicability: Mapping[str, str],
        source_refs: Sequence[ArtifactRef],
        evidence_refs: Sequence[ArtifactRef],
        source_run_ref: RunRef | None,
        evidence_strength: str,
        universality_basis: str | None,
        scope_signals: KnowledgeScopeSignals,
    ) -> KnowledgeCandidate:
        if origin_type == "migration.normalized":
            raise KnowledgeContractError(
                "normalized migration candidates require the dedicated verified mapping seam"
            )
        return self._record_candidate(
            requesting_access,
            project_ref=project_ref,
            idempotency_key=idempotency_key,
            proposed_scope=proposed_scope,
            origin_type=origin_type,
            knowledge_type=knowledge_type,
            statement=statement,
            content_ref=content_ref,
            applicability=applicability,
            source_refs=source_refs,
            evidence_refs=evidence_refs,
            source_run_ref=source_run_ref,
            evidence_strength=evidence_strength,
            universality_basis=universality_basis,
            scope_signals=scope_signals,
            migration_candidate_id=None,
            migration_classification=None,
            migration_provenance={},
        )

    def record_normalized_migration_candidate(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        idempotency_key: str,
        normalized_candidate: NormalizedMigrationCandidate,
        knowledge_type: str,
        applicability: Mapping[str, str],
        source_refs: Sequence[ArtifactRef],
        evidence_refs: Sequence[ArtifactRef],
        evidence_strength: str,
        universality_basis: str | None,
        scope_signals: KnowledgeScopeSignals,
    ) -> KnowledgeCandidate:
        from .migration import (
            MigrationClassification,
            NormalizedMigrationCandidate as VerifiedNormalizedMigrationCandidate,
        )

        if not isinstance(normalized_candidate, VerifiedNormalizedMigrationCandidate):
            raise KnowledgeContractError("verified NormalizedMigrationCandidate is required")
        classification = normalized_candidate.classification
        if classification in {
            MigrationClassification.UNIVERSAL_GOOD,
            MigrationClassification.UNIVERSAL_REWRITE,
        }:
            proposed_scope = "ENGINE"
        elif classification is MigrationClassification.PROJECT_SPECIFIC:
            proposed_scope = "PROJECT"
        else:
            proposed_scope = "HISTORICAL"
        return self._record_candidate(
            requesting_access,
            project_ref=project_ref,
            idempotency_key=idempotency_key,
            proposed_scope=proposed_scope,
            origin_type="migration.normalized",
            knowledge_type=knowledge_type,
            statement=normalized_candidate.normalized_text,
            content_ref=None,
            applicability=applicability,
            source_refs=source_refs,
            evidence_refs=evidence_refs,
            source_run_ref=None,
            evidence_strength=evidence_strength,
            universality_basis=universality_basis,
            scope_signals=scope_signals,
            migration_candidate_id=normalized_candidate.candidate_id,
            migration_classification=classification.value,
            migration_provenance=normalized_candidate.provenance_chain,
        )

    def _record_candidate(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        idempotency_key: str,
        proposed_scope: str,
        origin_type: str,
        knowledge_type: str,
        statement: str | None,
        content_ref: ContentRef | None,
        applicability: Mapping[str, str],
        source_refs: Sequence[ArtifactRef],
        evidence_refs: Sequence[ArtifactRef],
        source_run_ref: RunRef | None,
        evidence_strength: str,
        universality_basis: str | None,
        scope_signals: KnowledgeScopeSignals,
        migration_candidate_id: str | None,
        migration_classification: str | None,
        migration_provenance: Mapping[str, str],
    ) -> KnowledgeCandidate:
        _validate_key(idempotency_key, "idempotency_key")
        _validate_scope(proposed_scope)
        _validate_type(origin_type, "origin_type")
        _validate_type(knowledge_type, "knowledge_type")
        normalized_statement, normalized_content = _validate_statement_or_content(
            statement,
            content_ref,
        )
        normalized_applicability = _freeze_mapping(applicability, "applicability")
        normalized_sources = _freeze_project_artifact_refs(
            source_refs,
            project_ref,
            "source_refs",
        )
        normalized_evidence = _freeze_project_artifact_refs(
            evidence_refs,
            project_ref,
            "evidence_refs",
        )
        if not normalized_sources:
            raise KnowledgeContractError("candidate requires provenance source_refs")
        _validate_evidence_strength(evidence_strength)
        if not isinstance(scope_signals, KnowledgeScopeSignals):
            raise KnowledgeContractError("KnowledgeScopeSignals is required")
        normalized_migration = _freeze_mapping(
            migration_provenance,
            "migration_provenance",
            limit=64,
            allow_empty_values=True,
        )
        request_sha256 = self._candidate_request_sha256(
            project_ref,
            idempotency_key,
            proposed_scope,
            origin_type,
            knowledge_type,
            normalized_statement,
            normalized_content,
            normalized_applicability,
            normalized_sources,
            normalized_evidence,
            source_run_ref,
            evidence_strength,
            universality_basis,
            scope_signals,
            migration_candidate_id,
            migration_classification,
            normalized_migration,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize_project(connection, requesting_access, project_ref)
            prior = connection.execute(
                """
                SELECT candidate_id, request_sha256
                FROM knowledge_candidates
                WHERE source_project_id = ? AND idempotency_key = ?
                """,
                (project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(
                    cast(str, prior["request_sha256"]),
                    request_sha256,
                ):
                    raise KnowledgeConflictError(
                        "candidate idempotency key has different semantics"
                    )
                result = self._fetch_candidate(
                    connection,
                    KnowledgeCandidateRef(project_ref, cast(str, prior["candidate_id"])),
                )
                connection.commit()
                return result
            artifacts = self._verified_project_artifacts(
                connection,
                normalized_sources,
                normalized_evidence,
            )
            run_identity = self._verified_run_identity(
                connection,
                project_ref,
                source_run_ref,
            )
            provenance_sha256 = self._candidate_provenance_sha256(
                artifacts,
                source_run_ref,
                run_identity,
                migration_candidate_id,
                normalized_migration,
            )
            candidate = KnowledgeCandidate(
                candidate_ref=KnowledgeCandidateRef.new(project_ref),
                idempotency_key=idempotency_key,
                proposed_scope=proposed_scope,
                origin_type=origin_type,
                knowledge_type=knowledge_type,
                statement=normalized_statement,
                content_ref=normalized_content,
                applicability=normalized_applicability,
                source_refs=normalized_sources,
                evidence_refs=normalized_evidence,
                source_run_ref=source_run_ref,
                source_run_identity_sha256=run_identity,
                evidence_strength=evidence_strength,
                universality_basis=universality_basis,
                scope_signals=scope_signals,
                migration_candidate_id=migration_candidate_id,
                migration_classification=migration_classification,
                migration_provenance=normalized_migration,
                provenance_sha256=provenance_sha256,
                created_at=_now_utc(),
            )
            connection.execute(
                """
                INSERT INTO knowledge_candidates VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    candidate.source_project_ref.value,
                    candidate.candidate_ref.candidate_id,
                    candidate.idempotency_key,
                    candidate.proposed_scope,
                    candidate.origin_type,
                    candidate.knowledge_type,
                    candidate.statement,
                    None
                    if candidate.content_ref is None
                    else _json(_content_payload(candidate.content_ref)),
                    _json(dict(candidate.applicability)),
                    None if candidate.source_run_ref is None else candidate.source_run_ref.run_id,
                    candidate.source_run_identity_sha256,
                    candidate.evidence_strength,
                    candidate.universality_basis,
                    _json(candidate.scope_signals.as_payload()),
                    candidate.migration_candidate_id,
                    candidate.migration_classification,
                    _json(dict(candidate.migration_provenance)),
                    candidate.provenance_sha256,
                    candidate.created_at,
                    request_sha256,
                    candidate.equivalence_sha256,
                    candidate.semantic_digest,
                    candidate.record_sha256,
                ),
            )
            self._insert_candidate_artifacts(connection, candidate, artifacts)
            connection.commit()
            return candidate
        except (ProjectError, ArtifactError, RunError) as exc:
            connection.rollback()
            if isinstance(exc, ProjectScopeError):
                raise KnowledgeScopeError("candidate Project scope mismatch") from exc
            raise KnowledgeIntegrityError("candidate provenance failed verification") from exc
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise KnowledgeConflictError("candidate write conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_candidate(
        self,
        requesting_access: ProjectAccess,
        candidate_ref: KnowledgeCandidateRef,
    ) -> KnowledgeCandidate:
        if not isinstance(candidate_ref, KnowledgeCandidateRef):
            raise KnowledgeContractError("candidate_ref is required")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize_project(
                connection,
                requesting_access,
                candidate_ref.source_project_ref,
            )
            result = self._fetch_candidate(connection, candidate_ref)
            connection.commit()
            return result
        except ProjectScopeError as exc:
            connection.rollback()
            raise KnowledgeScopeError("candidate Project scope mismatch") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def classify_candidate(
        self,
        promotion_access: KnowledgePromotionAccess,
        candidate_ref: KnowledgeCandidateRef,
        *,
        idempotency_key: str,
        contradicts_refs: Sequence[KnowledgeRef] = (),
        scope_evidence: KnowledgeScopeEvidence | None = None,
    ) -> KnowledgeScopeDecision:
        if not isinstance(candidate_ref, KnowledgeCandidateRef):
            raise KnowledgeContractError("candidate_ref is required")
        _validate_key(idempotency_key, "idempotency_key")
        normalized_contradicts = _freeze_knowledge_refs(
            contradicts_refs,
            "contradicts_refs",
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            authority_id = self._authorize_promotion(connection, promotion_access)
            candidate = self._fetch_candidate(connection, candidate_ref)
            durable_scope_evidence: KnowledgeScopeEvidence | None = None
            if scope_evidence is not None:
                if not isinstance(scope_evidence, KnowledgeScopeEvidence):
                    raise KnowledgeContractError("KnowledgeScopeEvidence is required")
                durable_scope_evidence = self._fetch_scope_evidence(
                    connection,
                    scope_evidence.evidence_id,
                )
                if durable_scope_evidence != scope_evidence:
                    raise KnowledgeIntegrityError(
                        "scope evidence differs from durable state"
                    )
            project = self.projects._fetch_project(
                connection,
                candidate.source_project_ref,
            )
            classified_scope, project_ref, reasons = self.classifier.classify(
                candidate,
                project,
                durable_scope_evidence,
            )
            for ref in normalized_contradicts:
                if ref.scope != classified_scope or ref.project_ref != project_ref:
                    raise KnowledgeScopeError("contradiction crossed classified scope")
                self._fetch_knowledge(connection, ref)
            duplicate_refs = self._find_duplicate_active_refs(
                connection,
                classified_scope,
                project_ref,
                candidate.equivalence_sha256,
            )
            if set(duplicate_refs) & set(normalized_contradicts):
                raise KnowledgeConflictError("candidate cannot duplicate and contradict")
            request_sha256 = _sha256(
                {
                    "candidate_record_sha256": candidate.record_sha256,
                    "candidate_ref": candidate.candidate_ref.value,
                    "contradicts_refs": [item.value for item in normalized_contradicts],
                    "idempotency_key": idempotency_key,
                    "scope_evidence_record_sha256": (
                        None
                        if durable_scope_evidence is None
                        else durable_scope_evidence.record_sha256
                    ),
                }
            )
            prior = connection.execute(
                "SELECT * FROM knowledge_scope_decisions WHERE candidate_id = ?",
                (candidate_ref.candidate_id,),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(
                    cast(str, prior["request_sha256"]),
                    request_sha256,
                ):
                    raise KnowledgeConflictError(
                        "candidate already has a different scope decision"
                    )
                decision = self._decision_from_row(connection, prior)
                connection.commit()
                return decision
            decision = KnowledgeScopeDecision(
                candidate_ref=candidate.candidate_ref,
                candidate_record_sha256=candidate.record_sha256,
                classified_scope=classified_scope,
                project_ref=project_ref,
                scope_evidence_id=(
                    None
                    if durable_scope_evidence is None
                    else durable_scope_evidence.evidence_id
                ),
                scope_evidence_record_sha256=(
                    None
                    if durable_scope_evidence is None
                    else durable_scope_evidence.record_sha256
                ),
                status="ROUTE_PROJECT" if classified_scope == "PROJECT" else "ELIGIBLE",
                reasons=reasons,
                duplicate_refs=duplicate_refs,
                contradicts_refs=normalized_contradicts,
                idempotency_key=idempotency_key,
                evaluated_by=authority_id,
                evaluated_at=_now_utc(),
                request_sha256=request_sha256,
            )
            connection.execute(
                "INSERT INTO knowledge_scope_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision.candidate_ref.candidate_id,
                    decision.candidate_record_sha256,
                    decision.classified_scope,
                    None if decision.project_ref is None else decision.project_ref.value,
                    decision.scope_evidence_id,
                    decision.scope_evidence_record_sha256,
                    decision.status,
                    _json(list(decision.reasons)),
                    _json([self._ref_payload(item) for item in decision.duplicate_refs]),
                    _json([self._ref_payload(item) for item in decision.contradicts_refs]),
                    decision.idempotency_key,
                    decision.evaluated_by,
                    decision.evaluated_at,
                    decision.request_sha256,
                    decision.semantic_digest,
                    decision.record_sha256,
                ),
            )
            connection.commit()
            return decision
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise KnowledgeConflictError("scope decision conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def route_candidate_to_project(
        self,
        requesting_access: ProjectAccess,
        decision: KnowledgeScopeDecision,
        *,
        idempotency_key: str,
    ) -> ProjectKnowledgeCandidate:
        if not isinstance(decision, KnowledgeScopeDecision):
            raise KnowledgeContractError("KnowledgeScopeDecision is required")
        if decision.classified_scope != "PROJECT" or decision.project_ref is None:
            raise KnowledgeScopeError("only PROJECT decisions can route to ProjectKnowledge")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize_project(connection, requesting_access, decision.project_ref)
            stored_decision = self._fetch_decision(connection, decision.candidate_ref)
            if stored_decision != decision:
                raise KnowledgeIntegrityError("scope decision differs from durable state")
            candidate = self._fetch_candidate(connection, decision.candidate_ref)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        applicability = dict(candidate.applicability)
        if len(applicability) >= 32 and "source_candidate" not in applicability:
            raise KnowledgeContractError("Project route cannot bind source candidate")
        applicability["source_candidate"] = candidate.candidate_ref.value
        return self.project_knowledge.record_candidate(
            requesting_access,
            project_ref=decision.project_ref,
            idempotency_key=idempotency_key,
            origin_type="engine.scope-route",
            knowledge_type=candidate.knowledge_type,
            statement=candidate.statement,
            content_ref=candidate.content_ref,
            applicability=applicability,
            source_refs=candidate.source_refs,
            evidence_refs=candidate.evidence_refs,
        )

    def promote_candidate(
        self,
        promotion_access: KnowledgePromotionAccess,
        decision: KnowledgeScopeDecision,
        *,
        knowledge_ref: KnowledgeRef,
        idempotency_key: str,
        supersedes_refs: Sequence[KnowledgeRef] = (),
        contradicts_refs: Sequence[KnowledgeRef] = (),
    ) -> Knowledge:
        if not isinstance(decision, KnowledgeScopeDecision):
            raise KnowledgeContractError("KnowledgeScopeDecision is required")
        if not isinstance(knowledge_ref, KnowledgeRef):
            raise KnowledgeContractError("knowledge_ref is required")
        _validate_key(idempotency_key, "idempotency_key")
        supplied_supersedes = _freeze_knowledge_refs(supersedes_refs, "supersedes_refs")
        supplied_contradicts = _freeze_knowledge_refs(contradicts_refs, "contradicts_refs")
        if decision.classified_scope == "PROJECT":
            raise KnowledgeScopeError("PROJECT candidate must route to ProjectKnowledge")
        if (
            knowledge_ref.scope != decision.classified_scope
            or knowledge_ref.project_ref != decision.project_ref
        ):
            raise KnowledgeScopeError("placement scope differs from classifier decision")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            authority_id = self._authorize_promotion(connection, promotion_access)
            stored_decision = self._fetch_decision(connection, decision.candidate_ref)
            if stored_decision != decision:
                raise KnowledgeIntegrityError("scope decision differs from durable state")
            candidate = self._fetch_candidate(connection, decision.candidate_ref)
            if candidate.record_sha256 != decision.candidate_record_sha256:
                raise KnowledgeIntegrityError("candidate changed after scope decision")
            if decision.duplicate_refs:
                if supplied_supersedes or supplied_contradicts:
                    raise KnowledgeConflictError("duplicate resolution relations are automatic")
                if any(
                    ref.scope != knowledge_ref.scope
                    or ref.project_ref != knowledge_ref.project_ref
                    or ref.knowledge_id != knowledge_ref.knowledge_id
                    for ref in decision.duplicate_refs
                ):
                    raise KnowledgeConflictError(
                        "duplicate candidate must continue one exact knowledge identity"
                    )
                normalized_supersedes = decision.duplicate_refs
                normalized_contradicts: tuple[KnowledgeRef, ...] = ()
            else:
                normalized_supersedes = supplied_supersedes
                normalized_contradicts = supplied_contradicts
                if normalized_contradicts != decision.contradicts_refs:
                    raise KnowledgeConflictError(
                        "placement contradiction differs from evaluated contradiction"
                    )
            if set(normalized_supersedes) & set(normalized_contradicts):
                raise KnowledgeConflictError("one target has two relationship types")
            request_sha256 = self._placement_request_sha256(
                candidate,
                decision,
                knowledge_ref,
                idempotency_key,
                normalized_supersedes,
                normalized_contradicts,
            )
            prior = connection.execute(
                "SELECT * FROM knowledge_revisions WHERE placement_idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(
                    cast(str, prior["placement_request_sha256"]),
                    request_sha256,
                ):
                    raise KnowledgeConflictError(
                        "placement idempotency key has different semantics"
                    )
                result = self._fetch_knowledge(
                    connection,
                    KnowledgeRef(
                        cast(str, prior["scope"]),
                        self._project_ref_from_storage(cast(str, prior["project_scope_id"])),
                        cast(str, prior["knowledge_id"]),
                        cast(int, prior["version"]),
                    ),
                )
                connection.commit()
                return result
            history = self._fetch_history_if_present(connection, knowledge_ref)
            expected_version = len(history) + 1
            if knowledge_ref.version != expected_version:
                raise KnowledgeConflictError("knowledge version does not advance history")
            if not history:
                if normalized_supersedes or normalized_contradicts:
                    raise KnowledgeConflictError("initial knowledge cannot relate to missing history")
            else:
                active_refs = self._active_refs(history)
                requested = set(normalized_supersedes) | set(normalized_contradicts)
                if requested != active_refs:
                    raise KnowledgeConflictError("placement must address every current candidate")
                if bool(normalized_supersedes) == bool(normalized_contradicts):
                    raise KnowledgeConflictError(
                        "new knowledge must supersede or contradict current state"
                    )
            artifacts = self._verified_project_artifacts(
                connection,
                candidate.source_refs,
                candidate.evidence_refs,
            )
            sources = list(candidate.source_refs)
            evidence = list(candidate.evidence_refs)
            prior_by_ref = {item.knowledge_ref: item for item in history}
            if decision.duplicate_refs:
                for prior_ref in decision.duplicate_refs:
                    prior_knowledge = prior_by_ref[prior_ref]
                    sources.extend(prior_knowledge.source_refs)
                    evidence.extend(prior_knowledge.evidence_refs)
            normalized_sources = _freeze_global_artifact_refs(
                tuple(dict.fromkeys(sources)),
                "source_refs",
            )
            normalized_evidence = _freeze_global_artifact_refs(
                tuple(dict.fromkeys(evidence)),
                "evidence_refs",
            )
            global_artifacts = self._verified_global_artifacts(
                connection,
                normalized_sources,
                normalized_evidence,
            )
            provenance_sha256 = _sha256(
                {
                    "artifacts": [
                        {
                            "kind": kind,
                            "position": position,
                            "ref": artifact.artifact_ref.value,
                            "record_sha256": artifact.record_sha256,
                        }
                        for kind, position, artifact in global_artifacts
                    ],
                    "candidate_record_sha256": candidate.record_sha256,
                    "decision_record_sha256": decision.record_sha256,
                    "relations": [
                        {
                            "record_sha256": prior_by_ref[ref].record_sha256,
                            "ref": ref.value,
                            "type": relation_type,
                        }
                        for relation_type, refs in (
                            ("SUPERSEDES", normalized_supersedes),
                            ("CONTRADICTS", normalized_contradicts),
                        )
                        for ref in refs
                    ],
                }
            )
            knowledge = Knowledge(
                knowledge_ref=knowledge_ref,
                candidate_ref=candidate.candidate_ref,
                candidate_record_sha256=candidate.record_sha256,
                decision_record_sha256=decision.record_sha256,
                knowledge_type=candidate.knowledge_type,
                statement=candidate.statement,
                content_ref=candidate.content_ref,
                applicability=candidate.applicability,
                source_refs=normalized_sources,
                evidence_refs=normalized_evidence,
                evidence_strength=candidate.evidence_strength,
                provenance_sha256=provenance_sha256,
                migration_candidate_id=candidate.migration_candidate_id,
                promoted_by=authority_id,
                promoted_at=_now_utc(),
                supersedes_refs=normalized_supersedes,
                contradicts_refs=normalized_contradicts,
                placement_idempotency_key=idempotency_key,
            )
            scope_key = self._scope_key(knowledge_ref.project_ref)
            connection.execute(
                """
                INSERT INTO knowledge_revisions VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    knowledge.scope,
                    scope_key,
                    knowledge.knowledge_ref.knowledge_id,
                    knowledge.knowledge_ref.version,
                    knowledge.candidate_ref.candidate_id,
                    knowledge.candidate_record_sha256,
                    knowledge.decision_record_sha256,
                    knowledge.status,
                    knowledge.knowledge_type,
                    knowledge.statement,
                    None
                    if knowledge.content_ref is None
                    else _json(_content_payload(knowledge.content_ref)),
                    _json(dict(knowledge.applicability)),
                    knowledge.evidence_strength,
                    knowledge.provenance_sha256,
                    knowledge.migration_candidate_id,
                    knowledge.promoted_by,
                    knowledge.promoted_at,
                    knowledge.placement_idempotency_key,
                    request_sha256,
                    knowledge.equivalence_sha256,
                    knowledge.semantic_digest,
                    knowledge.record_sha256,
                ),
            )
            self._insert_revision_artifacts(connection, knowledge, global_artifacts)
            self._insert_relations(connection, knowledge, prior_by_ref)
            self._advance_identity_head(connection, knowledge, (*history, knowledge))
            connection.commit()
            return knowledge
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise KnowledgeConflictError("knowledge placement conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_knowledge(
        self,
        promotion_access: KnowledgePromotionAccess,
        knowledge_ref: KnowledgeRef,
    ) -> Knowledge:
        history = self.list_history(promotion_access, knowledge_ref)
        result = next((item for item in history if item.knowledge_ref == knowledge_ref), None)
        if result is None:
            raise KnowledgeNotFoundError("knowledge revision not found")
        return result

    def list_history(
        self,
        promotion_access: KnowledgePromotionAccess,
        knowledge_ref: KnowledgeRef,
    ) -> tuple[Knowledge, ...]:
        if not isinstance(knowledge_ref, KnowledgeRef):
            raise KnowledgeContractError("knowledge_ref is required")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize_promotion(connection, promotion_access)
            history = self._fetch_history(connection, knowledge_ref)
            connection.commit()
            return history
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def resolve_current(
        self,
        promotion_access: KnowledgePromotionAccess,
        knowledge_ref: KnowledgeRef,
    ) -> KnowledgeResolution:
        history = self.list_history(promotion_access, knowledge_ref)
        active_refs = self._active_refs(history)
        active = tuple(item for item in history if item.knowledge_ref in active_refs)
        if len(active) == 1:
            return KnowledgeResolution(
                scope=knowledge_ref.scope,
                project_ref=knowledge_ref.project_ref,
                knowledge_id=knowledge_ref.knowledge_id,
                status="CURRENT",
                current=active[0],
                candidates=active,
            )
        return KnowledgeResolution(
            scope=knowledge_ref.scope,
            project_ref=knowledge_ref.project_ref,
            knowledge_id=knowledge_ref.knowledge_id,
            status="CONFLICT",
            current=None,
            candidates=active,
        )

    def list_knowledge(
        self,
        promotion_access: KnowledgePromotionAccess,
        *,
        scope: str,
        project_ref: ProjectRef | None = None,
    ) -> tuple[Knowledge, ...]:
        _validate_scope(scope)
        if scope == "PROJECT":
            raise KnowledgeScopeError("Project listing belongs to ProjectKnowledge")
        if project_ref is not None:
            raise KnowledgeScopeError("global knowledge listing cannot carry ProjectRef")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize_promotion(connection, promotion_access)
            head_rows = connection.execute(
                """
                SELECT knowledge_id FROM knowledge_identity_heads
                WHERE scope = ? AND project_scope_id = '' ORDER BY knowledge_id
                """,
                (scope,),
            ).fetchall()
            revision_rows = connection.execute(
                """
                SELECT DISTINCT knowledge_id FROM knowledge_revisions
                WHERE scope = ? AND project_scope_id = '' ORDER BY knowledge_id
                """,
                (scope,),
            ).fetchall()
            head_ids = tuple(cast(str, row["knowledge_id"]) for row in head_rows)
            revision_ids = tuple(cast(str, row["knowledge_id"]) for row in revision_rows)
            if head_ids != revision_ids:
                raise KnowledgeIntegrityError("knowledge head and history identities differ")
            results: list[Knowledge] = []
            for knowledge_id in head_ids:
                seed = KnowledgeRef(scope, None, knowledge_id, 1)
                history = self._fetch_history(connection, seed)
                active_refs = self._active_refs(history)
                results.extend(
                    item for item in history if item.knowledge_ref in active_refs
                )
            connection.commit()
            return tuple(results)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def search_knowledge(
        self,
        promotion_access: KnowledgePromotionAccess,
        *,
        scope: str,
        applicability: Mapping[str, str] | None = None,
        text: str | None = None,
    ) -> tuple[Knowledge, ...]:
        filters = {} if applicability is None else dict(
            _freeze_mapping(applicability, "applicability")
        )
        if text is not None and (
            not isinstance(text, str) or not text.strip() or len(text.encode()) > 4096
        ):
            raise KnowledgeContractError("search text is malformed")
        needle = None if text is None else text.casefold()
        return tuple(
            item
            for item in self.list_knowledge(promotion_access, scope=scope)
            if all(item.applicability.get(key) == value for key, value in filters.items())
            and (
                needle is None
                or (item.statement is not None and needle in item.statement.casefold())
            )
        )

    def rebuild_search_cache(
        self,
        promotion_access: KnowledgePromotionAccess,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize_promotion(connection, promotion_access)
            connection.execute("DELETE FROM knowledge_search_cache")
            rows = connection.execute(
                "SELECT scope, project_scope_id, knowledge_id, version, record_sha256 FROM knowledge_revisions"
            ).fetchall()
            for row in rows:
                cache_key = _sha256(
                    {
                        "knowledge_id": row["knowledge_id"],
                        "project_scope_id": row["project_scope_id"],
                        "scope": row["scope"],
                        "version": row["version"],
                    }
                )
                connection.execute(
                    "INSERT INTO knowledge_search_cache VALUES (?, ?, ?)",
                    (cache_key, _json(dict(row)), _now_utc()),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def clear_search_cache(
        self,
        promotion_access: KnowledgePromotionAccess,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize_promotion(connection, promotion_access)
            connection.execute("DELETE FROM knowledge_search_cache")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _authorize_project(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        project_ref: ProjectRef,
    ) -> None:
        authorized = self.projects._authorize(connection, access)
        if authorized != project_ref:
            raise ProjectScopeError("Project scope mismatch")
        self.projects._fetch_project(connection, project_ref)

    def _authorize_promotion(
        self,
        connection: sqlite3.Connection,
        access: KnowledgePromotionAccess,
    ) -> str:
        if not isinstance(access, KnowledgePromotionAccess):
            raise KnowledgeAuthorityError("KnowledgePromotionAccess is required")
        row = self._verify_registered_authority(connection, access.authority_id)
        token_sha256 = hashlib.sha256(access.token.encode()).hexdigest()
        if not hmac.compare_digest(cast(str, row["token_sha256"]), token_sha256):
            raise KnowledgeAuthorityError("promotion authority token differs")
        return access.authority_id

    def _verify_registered_authority(
        self,
        connection: sqlite3.Connection,
        authority_id: str,
    ) -> sqlite3.Row:
        if (
            not isinstance(authority_id, str)
            or _AUTHORITY_ID_PATTERN.fullmatch(authority_id) is None
        ):
            raise KnowledgeAuthorityError("promotion authority identity is malformed")
        row = connection.execute(
            "SELECT * FROM knowledge_promotion_authorities WHERE authority_id = ?",
            (authority_id,),
        ).fetchone()
        if row is None:
            raise KnowledgeAuthorityError("promotion authority is not registered")
        observed_record = _sha256(
            {
                "authority_id": row["authority_id"],
                "created_at": row["created_at"],
                "token_sha256": row["token_sha256"],
            }
        )
        self._verify_digest(
            cast(str, row["record_sha256"]),
            observed_record,
            "promotion authority",
        )
        return cast(sqlite3.Row, row)

    def _verified_project_artifacts(
        self,
        connection: sqlite3.Connection,
        source_refs: tuple[ArtifactRef, ...],
        evidence_refs: tuple[ArtifactRef, ...],
    ) -> tuple[tuple[str, int, Artifact], ...]:
        result: list[tuple[str, int, Artifact]] = []
        for kind, refs in (("source", source_refs), ("evidence", evidence_refs)):
            for position, artifact_ref in enumerate(refs):
                result.append(
                    (kind, position, self.artifacts._fetch_artifact(connection, artifact_ref))
                )
        return tuple(result)

    def _verified_global_artifacts(
        self,
        connection: sqlite3.Connection,
        source_refs: tuple[ArtifactRef, ...],
        evidence_refs: tuple[ArtifactRef, ...],
    ) -> tuple[tuple[str, int, Artifact], ...]:
        return self._verified_project_artifacts(connection, source_refs, evidence_refs)

    def _verified_run_identity(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
        run_ref: RunRef | None,
    ) -> str | None:
        if run_ref is None:
            return None
        if not isinstance(run_ref, RunRef) or run_ref.project_ref != project_ref:
            raise KnowledgeScopeError("source Run crossed Project scope")
        try:
            run = self.runs._fetch_run(connection, run_ref)
        except RunError as exc:
            raise KnowledgeIntegrityError("source Run failed verification") from exc
        return run.identity_sha256

    @staticmethod
    def _candidate_provenance_sha256(
        artifacts: tuple[tuple[str, int, Artifact], ...],
        source_run_ref: RunRef | None,
        source_run_identity_sha256: str | None,
        migration_candidate_id: str | None,
        migration_provenance: Mapping[str, str],
    ) -> str:
        return _sha256(
            {
                "artifacts": [
                    {
                        "kind": kind,
                        "position": position,
                        "record_sha256": artifact.record_sha256,
                        "ref": artifact.artifact_ref.value,
                    }
                    for kind, position, artifact in artifacts
                ],
                "migration_candidate_id": migration_candidate_id,
                "migration_provenance": dict(migration_provenance),
                "source_run_identity_sha256": source_run_identity_sha256,
                "source_run_ref": (
                    None
                    if source_run_ref is None
                    else {
                        "project_id": source_run_ref.project_ref.value,
                        "run_id": source_run_ref.run_id,
                    }
                ),
            }
        )

    def _insert_candidate_artifacts(
        self,
        connection: sqlite3.Connection,
        candidate: KnowledgeCandidate,
        artifacts: tuple[tuple[str, int, Artifact], ...],
    ) -> None:
        for kind, position, artifact in artifacts:
            record_sha256 = _sha256(
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "artifact_ref": artifact.artifact_ref.value,
                    "candidate_ref": candidate.candidate_ref.value,
                    "kind": kind,
                    "position": position,
                }
            )
            connection.execute(
                "INSERT INTO knowledge_candidate_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    candidate.candidate_ref.candidate_id,
                    kind,
                    position,
                    artifact.project_ref.value,
                    artifact.artifact_id,
                    artifact.revision,
                    artifact.record_sha256,
                    record_sha256,
                ),
            )

    def _fetch_candidate(
        self,
        connection: sqlite3.Connection,
        candidate_ref: KnowledgeCandidateRef,
    ) -> KnowledgeCandidate:
        row = connection.execute(
            "SELECT * FROM knowledge_candidates WHERE candidate_id = ?",
            (candidate_ref.candidate_id,),
        ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("knowledge candidate not found")
        if cast(str, row["source_project_id"]) != candidate_ref.source_project_ref.value:
            raise KnowledgeScopeError("candidate identity is private to another Project")
        bindings = connection.execute(
            """
            SELECT * FROM knowledge_candidate_artifacts
            WHERE candidate_id = ? ORDER BY binding_kind DESC, position
            """,
            (candidate_ref.candidate_id,),
        ).fetchall()
        artifacts = self._artifacts_from_bindings(
            connection,
            candidate_ref.value,
            bindings,
        )
        sources = tuple(
            artifact.artifact_ref for kind, _, artifact in artifacts if kind == "source"
        )
        evidence = tuple(
            artifact.artifact_ref for kind, _, artifact in artifacts if kind == "evidence"
        )
        source_run_ref = (
            None
            if row["source_run_id"] is None
            else RunRef(
                candidate_ref.source_project_ref,
                cast(str, row["source_run_id"]),
            )
        )
        run_identity = self._verified_run_identity(
            connection,
            candidate_ref.source_project_ref,
            source_run_ref,
        )
        if run_identity != row["source_run_identity_sha256"]:
            raise KnowledgeIntegrityError("source Run identity differs")
        scope_signals_raw = self._mapping_object_from_json(
            row["scope_signals_json"],
            "scope_signals",
        )
        scope_signals = KnowledgeScopeSignals(
            project_identifiers=self._string_sequence(
                scope_signals_raw.get("project_identifiers"),
                "project_identifiers",
            ),
            project_paths=self._string_sequence(
                scope_signals_raw.get("project_paths"),
                "project_paths",
            ),
            private_endpoints=self._string_sequence(
                scope_signals_raw.get("private_endpoints"),
                "private_endpoints",
            ),
            project_preferences=self._string_sequence(
                scope_signals_raw.get("project_preferences"),
                "project_preferences",
            ),
            historical_authority=self._boolean(
                scope_signals_raw.get("historical_authority"),
                "historical_authority",
            ),
            uncertain=self._boolean(
                scope_signals_raw.get("uncertain"),
                "uncertain",
            ),
        )
        migration_provenance = self._string_mapping_from_json(
            row["migration_provenance_json"],
            "migration_provenance",
        )
        candidate = KnowledgeCandidate(
            candidate_ref=candidate_ref,
            idempotency_key=cast(str, row["idempotency_key"]),
            proposed_scope=cast(str, row["proposed_scope"]),
            origin_type=cast(str, row["origin_type"]),
            knowledge_type=cast(str, row["knowledge_type"]),
            statement=cast(str | None, row["statement"]),
            content_ref=self._content_from_json(row["content_json"]),
            applicability=self._string_mapping_from_json(
                row["applicability_json"],
                "applicability",
            ),
            source_refs=sources,
            evidence_refs=evidence,
            source_run_ref=source_run_ref,
            source_run_identity_sha256=cast(
                str | None,
                row["source_run_identity_sha256"],
            ),
            evidence_strength=cast(str, row["evidence_strength"]),
            universality_basis=cast(str | None, row["universality_basis"]),
            scope_signals=scope_signals,
            migration_candidate_id=cast(str | None, row["migration_candidate_id"]),
            migration_classification=cast(
                str | None,
                row["migration_classification"],
            ),
            migration_provenance=migration_provenance,
            provenance_sha256=cast(str, row["provenance_sha256"]),
            created_at=cast(str, row["created_at"]),
        )
        expected_provenance = self._candidate_provenance_sha256(
            artifacts,
            source_run_ref,
            run_identity,
            candidate.migration_candidate_id,
            migration_provenance,
        )
        self._verify_digest(candidate.provenance_sha256, expected_provenance, "candidate provenance")
        self._verify_digest(
            cast(str, row["equivalence_sha256"]),
            candidate.equivalence_sha256,
            "candidate equivalence",
        )
        self._verify_digest(
            cast(str, row["semantic_digest"]),
            candidate.semantic_digest,
            "candidate semantics",
        )
        self._verify_digest(
            cast(str, row["record_sha256"]),
            candidate.record_sha256,
            "candidate record",
        )
        return candidate

    def _artifacts_from_bindings(
        self,
        connection: sqlite3.Connection,
        owner_ref: str,
        rows: Sequence[sqlite3.Row],
    ) -> tuple[tuple[str, int, Artifact], ...]:
        result: list[tuple[str, int, Artifact]] = []
        positions: dict[str, list[int]] = {"source": [], "evidence": []}
        for row in rows:
            kind = cast(str, row["binding_kind"])
            position = cast(int, row["position"])
            if kind not in positions:
                raise KnowledgeIntegrityError("artifact binding kind is malformed")
            positions[kind].append(position)
            artifact_ref = ArtifactRef(
                ProjectRef(cast(str, row["project_id"])),
                cast(str, row["artifact_id"]),
                cast(int, row["artifact_revision"]),
            )
            artifact = self.artifacts._fetch_artifact(connection, artifact_ref)
            self._verify_digest(
                cast(str, row["artifact_record_sha256"]),
                artifact.record_sha256,
                "artifact binding",
            )
            expected_record = _sha256(
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "artifact_ref": artifact.artifact_ref.value,
                    "candidate_ref" if owner_ref.startswith("knowledge-candidate://") else "knowledge_ref": owner_ref,
                    "kind": kind,
                    "position": position,
                }
            )
            self._verify_digest(
                cast(str, row["record_sha256"]),
                expected_record,
                "artifact binding record",
            )
            result.append((kind, position, artifact))
        for kind, observed in positions.items():
            if observed != list(range(len(observed))):
                raise KnowledgeIntegrityError(f"{kind} artifact positions are not contiguous")
        return tuple(result)

    def _decision_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> KnowledgeScopeDecision:
        candidate_row = connection.execute(
            "SELECT source_project_id FROM knowledge_candidates WHERE candidate_id = ?",
            (row["candidate_id"],),
        ).fetchone()
        if candidate_row is None:
            raise KnowledgeIntegrityError("scope decision lost its candidate")
        decision = KnowledgeScopeDecision(
            candidate_ref=KnowledgeCandidateRef(
                ProjectRef(cast(str, candidate_row["source_project_id"])),
                cast(str, row["candidate_id"]),
            ),
            candidate_record_sha256=cast(str, row["candidate_record_sha256"]),
            classified_scope=cast(str, row["classified_scope"]),
            project_ref=(
                None
                if row["project_scope_id"] is None
                else ProjectRef(cast(str, row["project_scope_id"]))
            ),
            scope_evidence_id=cast(str | None, row["scope_evidence_id"]),
            scope_evidence_record_sha256=cast(
                str | None,
                row["scope_evidence_record_sha256"],
            ),
            status=cast(str, row["status"]),
            reasons=tuple(
                self._string_sequence_from_json(row["reasons_json"], "reasons")
            ),
            duplicate_refs=self._refs_from_json(
                row["duplicate_refs_json"],
                "duplicate_refs",
            ),
            contradicts_refs=self._refs_from_json(
                row["contradicts_refs_json"],
                "contradicts_refs",
            ),
            idempotency_key=cast(str, row["idempotency_key"]),
            evaluated_by=cast(str, row["evaluated_by"]),
            evaluated_at=cast(str, row["evaluated_at"]),
            request_sha256=cast(str, row["request_sha256"]),
        )
        candidate = self._fetch_candidate(connection, decision.candidate_ref)
        if candidate.record_sha256 != decision.candidate_record_sha256:
            raise KnowledgeIntegrityError("scope decision candidate digest differs")
        scope_evidence: KnowledgeScopeEvidence | None = None
        if decision.scope_evidence_id is not None:
            scope_evidence = self._fetch_scope_evidence(
                connection,
                decision.scope_evidence_id,
            )
            if scope_evidence.record_sha256 != decision.scope_evidence_record_sha256:
                raise KnowledgeIntegrityError("scope decision evidence digest differs")
        project = self.projects._fetch_project(
            connection,
            candidate.source_project_ref,
        )
        classified_scope, project_ref, reasons = self.classifier.classify(
            candidate,
            project,
            scope_evidence,
        )
        if (
            decision.classified_scope != classified_scope
            or decision.project_ref != project_ref
            or decision.reasons != reasons
        ):
            raise KnowledgeIntegrityError("scope decision differs from classifier result")
        self._verify_registered_authority(connection, decision.evaluated_by)
        request_sha256 = _sha256(
            {
                "candidate_record_sha256": candidate.record_sha256,
                "candidate_ref": candidate.candidate_ref.value,
                "contradicts_refs": [
                    item.value for item in decision.contradicts_refs
                ],
                "idempotency_key": decision.idempotency_key,
                "scope_evidence_record_sha256": (
                    None if scope_evidence is None else scope_evidence.record_sha256
                ),
            }
        )
        self._verify_digest(
            decision.request_sha256,
            request_sha256,
            "scope decision request",
        )
        self._verify_digest(
            cast(str, row["semantic_digest"]),
            decision.semantic_digest,
            "scope decision semantics",
        )
        self._verify_digest(
            cast(str, row["record_sha256"]),
            decision.record_sha256,
            "scope decision record",
        )
        return decision

    def _fetch_decision(
        self,
        connection: sqlite3.Connection,
        candidate_ref: KnowledgeCandidateRef,
    ) -> KnowledgeScopeDecision:
        row = connection.execute(
            "SELECT * FROM knowledge_scope_decisions WHERE candidate_id = ?",
            (candidate_ref.candidate_id,),
        ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("candidate has no scope decision")
        decision = self._decision_from_row(connection, row)
        if decision.candidate_ref != candidate_ref:
            raise KnowledgeScopeError("scope decision belongs to another Project")
        return decision

    def _find_duplicate_active_refs(
        self,
        connection: sqlite3.Connection,
        scope: str,
        project_ref: ProjectRef | None,
        equivalence_sha256: str,
    ) -> tuple[KnowledgeRef, ...]:
        scope_key = self._scope_key(project_ref)
        rows = connection.execute(
            """
            SELECT knowledge_id FROM knowledge_identity_heads
            WHERE scope = ? AND project_scope_id = ? ORDER BY knowledge_id
            """,
            (scope, scope_key),
        ).fetchall()
        matches: list[KnowledgeRef] = []
        for row in rows:
            seed = KnowledgeRef(
                scope,
                project_ref,
                cast(str, row["knowledge_id"]),
                1,
            )
            history = self._fetch_history(connection, seed)
            active_refs = self._active_refs(history)
            matches.extend(
                item.knowledge_ref
                for item in history
                if item.knowledge_ref in active_refs
                and hmac.compare_digest(item.equivalence_sha256, equivalence_sha256)
            )
        return tuple(sorted(matches, key=lambda item: item.value))

    def _fetch_knowledge(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: KnowledgeRef,
    ) -> Knowledge:
        scope_key = self._scope_key(knowledge_ref.project_ref)
        row = connection.execute(
            """
            SELECT * FROM knowledge_revisions
            WHERE scope = ? AND project_scope_id = ?
              AND knowledge_id = ? AND version = ?
            """,
            (
                knowledge_ref.scope,
                scope_key,
                knowledge_ref.knowledge_id,
                knowledge_ref.version,
            ),
        ).fetchone()
        if row is None:
            raise KnowledgeNotFoundError("knowledge revision not found")
        bindings = connection.execute(
            """
            SELECT * FROM knowledge_revision_artifacts
            WHERE scope = ? AND project_scope_id = ?
              AND knowledge_id = ? AND version = ?
            ORDER BY binding_kind DESC, position
            """,
            (
                knowledge_ref.scope,
                scope_key,
                knowledge_ref.knowledge_id,
                knowledge_ref.version,
            ),
        ).fetchall()
        artifacts = self._artifacts_from_bindings(
            connection,
            knowledge_ref.value,
            bindings,
        )
        sources = tuple(
            artifact.artifact_ref for kind, _, artifact in artifacts if kind == "source"
        )
        evidence = tuple(
            artifact.artifact_ref for kind, _, artifact in artifacts if kind == "evidence"
        )
        supersedes, contradicts, relation_records = self._fetch_relations(
            connection,
            knowledge_ref,
        )
        candidate_row = connection.execute(
            "SELECT source_project_id FROM knowledge_candidates WHERE candidate_id = ?",
            (row["candidate_id"],),
        ).fetchone()
        if candidate_row is None:
            raise KnowledgeIntegrityError("knowledge lost its candidate")
        candidate_ref = KnowledgeCandidateRef(
            ProjectRef(cast(str, candidate_row["source_project_id"])),
            cast(str, row["candidate_id"]),
        )
        candidate = self._fetch_candidate(connection, candidate_ref)
        decision = self._fetch_decision(connection, candidate_ref)
        knowledge = Knowledge(
            knowledge_ref=knowledge_ref,
            candidate_ref=candidate_ref,
            candidate_record_sha256=cast(str, row["candidate_record_sha256"]),
            decision_record_sha256=cast(str, row["decision_record_sha256"]),
            knowledge_type=cast(str, row["knowledge_type"]),
            statement=cast(str | None, row["statement"]),
            content_ref=self._content_from_json(row["content_json"]),
            applicability=self._string_mapping_from_json(
                row["applicability_json"],
                "applicability",
            ),
            source_refs=sources,
            evidence_refs=evidence,
            evidence_strength=cast(str, row["evidence_strength"]),
            provenance_sha256=cast(str, row["provenance_sha256"]),
            migration_candidate_id=cast(str | None, row["migration_candidate_id"]),
            promoted_by=cast(str, row["promoted_by"]),
            promoted_at=cast(str, row["promoted_at"]),
            supersedes_refs=supersedes,
            contradicts_refs=contradicts,
            placement_idempotency_key=cast(str, row["placement_idempotency_key"]),
        )
        if cast(str, row["status"]) != knowledge.status:
            raise KnowledgeIntegrityError("knowledge status differs")
        if candidate.record_sha256 != knowledge.candidate_record_sha256:
            raise KnowledgeIntegrityError("knowledge candidate digest differs")
        if decision.record_sha256 != knowledge.decision_record_sha256:
            raise KnowledgeIntegrityError("knowledge scope decision digest differs")
        if (
            knowledge.scope != decision.classified_scope
            or knowledge.project_ref != decision.project_ref
        ):
            raise KnowledgeIntegrityError("knowledge placement crossed classifier scope")
        candidate_fields_match = (
            knowledge.knowledge_type == candidate.knowledge_type
            and knowledge.statement == candidate.statement
            and knowledge.content_ref == candidate.content_ref
            and knowledge.applicability == candidate.applicability
            and knowledge.evidence_strength == candidate.evidence_strength
            and knowledge.migration_candidate_id == candidate.migration_candidate_id
        )
        if not candidate_fields_match:
            raise KnowledgeIntegrityError(
                "knowledge semantics differ from the classified candidate"
            )
        if knowledge.promoted_by != decision.evaluated_by:
            raise KnowledgeIntegrityError("knowledge promoter differs from evaluator")
        self._verify_registered_authority(connection, knowledge.promoted_by)
        for relation_ref in (
            *knowledge.supersedes_refs,
            *knowledge.contradicts_refs,
        ):
            if (
                relation_ref.scope != knowledge.scope
                or relation_ref.project_ref != knowledge.project_ref
                or relation_ref.knowledge_id != knowledge.knowledge_ref.knowledge_id
                or relation_ref.version >= knowledge.knowledge_ref.version
            ):
                raise KnowledgeIntegrityError(
                    "knowledge relation does not target earlier exact history"
                )
        if decision.duplicate_refs:
            if (
                knowledge.supersedes_refs != decision.duplicate_refs
                or knowledge.contradicts_refs
            ):
                raise KnowledgeIntegrityError(
                    "duplicate placement relations differ from the scope decision"
                )
            prior_knowledge = tuple(
                self._fetch_knowledge(connection, ref)
                for ref in decision.duplicate_refs
            )
            expected_sources = _freeze_global_artifact_refs(
                tuple(
                    dict.fromkeys(
                        (
                            *candidate.source_refs,
                            *(ref for item in prior_knowledge for ref in item.source_refs),
                        )
                    )
                ),
                "source_refs",
            )
            expected_evidence = _freeze_global_artifact_refs(
                tuple(
                    dict.fromkeys(
                        (
                            *candidate.evidence_refs,
                            *(ref for item in prior_knowledge for ref in item.evidence_refs),
                        )
                    )
                ),
                "evidence_refs",
            )
        else:
            if knowledge.contradicts_refs != decision.contradicts_refs:
                raise KnowledgeIntegrityError(
                    "knowledge contradiction differs from the scope decision"
                )
            expected_sources = _freeze_global_artifact_refs(
                candidate.source_refs,
                "source_refs",
            )
            expected_evidence = _freeze_global_artifact_refs(
                candidate.evidence_refs,
                "evidence_refs",
            )
        if (
            knowledge.source_refs != expected_sources
            or knowledge.evidence_refs != expected_evidence
        ):
            raise KnowledgeIntegrityError(
                "knowledge evidence differs from the classified candidate chain"
            )
        placement_request_sha256 = self._placement_request_sha256(
            candidate,
            decision,
            knowledge.knowledge_ref,
            knowledge.placement_idempotency_key,
            knowledge.supersedes_refs,
            knowledge.contradicts_refs,
        )
        self._verify_digest(
            cast(str, row["placement_request_sha256"]),
            placement_request_sha256,
            "knowledge placement request",
        )
        expected_provenance = _sha256(
            {
                "artifacts": [
                    {
                        "kind": kind,
                        "position": position,
                        "ref": artifact.artifact_ref.value,
                        "record_sha256": artifact.record_sha256,
                    }
                    for kind, position, artifact in artifacts
                ],
                "candidate_record_sha256": candidate.record_sha256,
                "decision_record_sha256": decision.record_sha256,
                "relations": relation_records,
            }
        )
        self._verify_digest(
            knowledge.provenance_sha256,
            expected_provenance,
            "knowledge provenance",
        )
        self._verify_digest(
            cast(str, row["equivalence_sha256"]),
            knowledge.equivalence_sha256,
            "knowledge equivalence",
        )
        self._verify_digest(
            cast(str, row["semantic_digest"]),
            knowledge.semantic_digest,
            "knowledge semantics",
        )
        self._verify_digest(
            cast(str, row["record_sha256"]),
            knowledge.record_sha256,
            "knowledge record",
        )
        return knowledge

    def _fetch_history_if_present(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: KnowledgeRef,
    ) -> tuple[Knowledge, ...]:
        scope_key = self._scope_key(knowledge_ref.project_ref)
        row = connection.execute(
            """
            SELECT 1 FROM knowledge_identity_heads
            WHERE scope = ? AND project_scope_id = ? AND knowledge_id = ?
            """,
            (knowledge_ref.scope, scope_key, knowledge_ref.knowledge_id),
        ).fetchone()
        if row is None:
            revision = connection.execute(
                """
                SELECT 1 FROM knowledge_revisions
                WHERE scope = ? AND project_scope_id = ? AND knowledge_id = ?
                """,
                (knowledge_ref.scope, scope_key, knowledge_ref.knowledge_id),
            ).fetchone()
            if revision is not None:
                raise KnowledgeIntegrityError("knowledge history lost its head")
            return ()
        return self._fetch_history(connection, knowledge_ref)

    def _fetch_history(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: KnowledgeRef,
    ) -> tuple[Knowledge, ...]:
        scope_key = self._scope_key(knowledge_ref.project_ref)
        head = connection.execute(
            """
            SELECT * FROM knowledge_identity_heads
            WHERE scope = ? AND project_scope_id = ? AND knowledge_id = ?
            """,
            (knowledge_ref.scope, scope_key, knowledge_ref.knowledge_id),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT version FROM knowledge_revisions
            WHERE scope = ? AND project_scope_id = ? AND knowledge_id = ?
            ORDER BY version
            """,
            (knowledge_ref.scope, scope_key, knowledge_ref.knowledge_id),
        ).fetchall()
        if head is None:
            if rows:
                raise KnowledgeIntegrityError("knowledge history lost its head")
            raise KnowledgeNotFoundError("knowledge history not found")
        if not rows:
            raise KnowledgeIntegrityError("knowledge head survived without history")
        versions = tuple(cast(int, row["version"]) for row in rows)
        maximum_version = cast(int, head["maximum_version"])
        if versions != tuple(range(1, maximum_version + 1)):
            raise KnowledgeIntegrityError("knowledge history is not contiguous")
        history = tuple(
            self._fetch_knowledge(
                connection,
                KnowledgeRef(
                    knowledge_ref.scope,
                    knowledge_ref.project_ref,
                    knowledge_ref.knowledge_id,
                    version,
                ),
            )
            for version in versions
        )
        history_sha256 = _sha256([item.record_sha256 for item in history])
        self._verify_digest(
            cast(str, head["history_sha256"]),
            history_sha256,
            "knowledge history",
        )
        expected_head_record = _sha256(
            {
                "history_sha256": history_sha256,
                "knowledge_id": knowledge_ref.knowledge_id,
                "maximum_version": maximum_version,
                "project_scope_id": scope_key,
                "scope": knowledge_ref.scope,
                "updated_at": head["updated_at"],
            }
        )
        self._verify_digest(
            cast(str, head["record_sha256"]),
            expected_head_record,
            "knowledge head",
        )
        return history

    @staticmethod
    def _active_refs(history: Sequence[Knowledge]) -> set[KnowledgeRef]:
        all_refs = {item.knowledge_ref for item in history}
        superseded = {
            target for item in history for target in item.supersedes_refs
        }
        active = all_refs - superseded
        if not active:
            raise KnowledgeIntegrityError("knowledge history has no active candidate")
        return active

    def _insert_revision_artifacts(
        self,
        connection: sqlite3.Connection,
        knowledge: Knowledge,
        artifacts: tuple[tuple[str, int, Artifact], ...],
    ) -> None:
        scope_key = self._scope_key(knowledge.project_ref)
        for kind, position, artifact in artifacts:
            record_sha256 = _sha256(
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "artifact_ref": artifact.artifact_ref.value,
                    "knowledge_ref": knowledge.knowledge_ref.value,
                    "kind": kind,
                    "position": position,
                }
            )
            connection.execute(
                "INSERT INTO knowledge_revision_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    knowledge.scope,
                    scope_key,
                    knowledge.knowledge_ref.knowledge_id,
                    knowledge.knowledge_ref.version,
                    kind,
                    position,
                    artifact.project_ref.value,
                    artifact.artifact_id,
                    artifact.revision,
                    artifact.record_sha256,
                    record_sha256,
                ),
            )

    def _insert_relations(
        self,
        connection: sqlite3.Connection,
        knowledge: Knowledge,
        prior_by_ref: Mapping[KnowledgeRef, Knowledge],
    ) -> None:
        source_scope_key = self._scope_key(knowledge.project_ref)
        for relation_type, refs in (
            ("SUPERSEDES", knowledge.supersedes_refs),
            ("CONTRADICTS", knowledge.contradicts_refs),
        ):
            for ref in refs:
                target = prior_by_ref.get(ref)
                if target is None:
                    raise KnowledgeIntegrityError("knowledge relation target is missing")
                target_scope_key = self._scope_key(ref.project_ref)
                record_sha256 = _sha256(
                    {
                        "relation_type": relation_type,
                        "source_ref": knowledge.knowledge_ref.value,
                        "target_record_sha256": target.record_sha256,
                        "target_ref": ref.value,
                    }
                )
                connection.execute(
                    "INSERT INTO knowledge_relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        knowledge.scope,
                        source_scope_key,
                        knowledge.knowledge_ref.knowledge_id,
                        knowledge.knowledge_ref.version,
                        relation_type,
                        ref.scope,
                        target_scope_key,
                        ref.knowledge_id,
                        ref.version,
                        target.record_sha256,
                        record_sha256,
                    ),
                )

    def _fetch_relations(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: KnowledgeRef,
    ) -> tuple[tuple[KnowledgeRef, ...], tuple[KnowledgeRef, ...], list[dict[str, str]]]:
        scope_key = self._scope_key(knowledge_ref.project_ref)
        rows = connection.execute(
            """
            SELECT * FROM knowledge_relations
            WHERE source_scope = ? AND source_project_scope_id = ?
              AND source_knowledge_id = ? AND source_version = ?
            ORDER BY relation_type, target_version
            """,
            (
                knowledge_ref.scope,
                scope_key,
                knowledge_ref.knowledge_id,
                knowledge_ref.version,
            ),
        ).fetchall()
        supersedes: list[KnowledgeRef] = []
        contradicts: list[KnowledgeRef] = []
        records: list[dict[str, str]] = []
        for row in rows:
            target_ref = KnowledgeRef(
                cast(str, row["target_scope"]),
                self._project_ref_from_storage(
                    cast(str, row["target_project_scope_id"])
                ),
                cast(str, row["target_knowledge_id"]),
                cast(int, row["target_version"]),
            )
            target_row = connection.execute(
                """
                SELECT record_sha256 FROM knowledge_revisions
                WHERE scope = ? AND project_scope_id = ?
                  AND knowledge_id = ? AND version = ?
                """,
                (
                    target_ref.scope,
                    self._scope_key(target_ref.project_ref),
                    target_ref.knowledge_id,
                    target_ref.version,
                ),
            ).fetchone()
            if target_row is None:
                raise KnowledgeIntegrityError("knowledge relation target disappeared")
            target_record = cast(str, target_row["record_sha256"])
            self._verify_digest(
                cast(str, row["target_record_sha256"]),
                target_record,
                "knowledge relation target",
            )
            relation_type = cast(str, row["relation_type"])
            expected_record = _sha256(
                {
                    "relation_type": relation_type,
                    "source_ref": knowledge_ref.value,
                    "target_record_sha256": target_record,
                    "target_ref": target_ref.value,
                }
            )
            self._verify_digest(
                cast(str, row["record_sha256"]),
                expected_record,
                "knowledge relation record",
            )
            if relation_type == "SUPERSEDES":
                supersedes.append(target_ref)
            elif relation_type == "CONTRADICTS":
                contradicts.append(target_ref)
            else:
                raise KnowledgeIntegrityError("knowledge relation type is malformed")
            records.append(
                {
                    "record_sha256": target_record,
                    "ref": target_ref.value,
                    "type": relation_type,
                }
            )
        return (
            tuple(sorted(supersedes, key=lambda item: item.value)),
            tuple(sorted(contradicts, key=lambda item: item.value)),
            records,
        )

    def _advance_identity_head(
        self,
        connection: sqlite3.Connection,
        knowledge: Knowledge,
        history: Sequence[Knowledge],
    ) -> None:
        scope_key = self._scope_key(knowledge.project_ref)
        history_sha256 = _sha256([item.record_sha256 for item in history])
        updated_at = knowledge.promoted_at
        record_sha256 = _sha256(
            {
                "history_sha256": history_sha256,
                "knowledge_id": knowledge.knowledge_ref.knowledge_id,
                "maximum_version": knowledge.knowledge_ref.version,
                "project_scope_id": scope_key,
                "scope": knowledge.scope,
                "updated_at": updated_at,
            }
        )
        prior = connection.execute(
            """
            SELECT maximum_version FROM knowledge_identity_heads
            WHERE scope = ? AND project_scope_id = ? AND knowledge_id = ?
            """,
            (knowledge.scope, scope_key, knowledge.knowledge_ref.knowledge_id),
        ).fetchone()
        if prior is None:
            if knowledge.knowledge_ref.version != 1:
                raise KnowledgeConflictError("initial knowledge version must be one")
            connection.execute(
                "INSERT INTO knowledge_identity_heads VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    knowledge.scope,
                    scope_key,
                    knowledge.knowledge_ref.knowledge_id,
                    knowledge.knowledge_ref.version,
                    history_sha256,
                    updated_at,
                    record_sha256,
                ),
            )
        else:
            if cast(int, prior["maximum_version"]) + 1 != knowledge.knowledge_ref.version:
                raise KnowledgeConflictError("knowledge head version differs")
            connection.execute(
                """
                UPDATE knowledge_identity_heads
                SET maximum_version = ?, history_sha256 = ?, updated_at = ?, record_sha256 = ?
                WHERE scope = ? AND project_scope_id = ? AND knowledge_id = ?
                """,
                (
                    knowledge.knowledge_ref.version,
                    history_sha256,
                    updated_at,
                    record_sha256,
                    knowledge.scope,
                    scope_key,
                    knowledge.knowledge_ref.knowledge_id,
                ),
            )

    @staticmethod
    def _candidate_request_sha256(
        project_ref: ProjectRef,
        idempotency_key: str,
        proposed_scope: str,
        origin_type: str,
        knowledge_type: str,
        statement: str | None,
        content_ref: ContentRef | None,
        applicability: Mapping[str, str],
        source_refs: tuple[ArtifactRef, ...],
        evidence_refs: tuple[ArtifactRef, ...],
        source_run_ref: RunRef | None,
        evidence_strength: str,
        universality_basis: str | None,
        scope_signals: KnowledgeScopeSignals,
        migration_candidate_id: str | None,
        migration_classification: str | None,
        migration_provenance: Mapping[str, str],
    ) -> str:
        return _sha256(
            {
                "applicability": dict(applicability),
                "content_ref": _content_payload(content_ref),
                "evidence_refs": [item.value for item in evidence_refs],
                "evidence_strength": evidence_strength,
                "idempotency_key": idempotency_key,
                "knowledge_type": knowledge_type,
                "migration_candidate_id": migration_candidate_id,
                "migration_classification": migration_classification,
                "migration_provenance": dict(migration_provenance),
                "origin_type": origin_type,
                "project_ref": project_ref.value,
                "proposed_scope": proposed_scope,
                "scope_signals": scope_signals.as_payload(),
                "source_refs": [item.value for item in source_refs],
                "source_run_ref": (
                    None
                    if source_run_ref is None
                    else {
                        "project_id": source_run_ref.project_ref.value,
                        "run_id": source_run_ref.run_id,
                    }
                ),
                "statement": statement,
                "universality_basis": universality_basis,
            }
        )

    @staticmethod
    def _placement_request_sha256(
        candidate: KnowledgeCandidate,
        decision: KnowledgeScopeDecision,
        knowledge_ref: KnowledgeRef,
        idempotency_key: str,
        supersedes_refs: tuple[KnowledgeRef, ...],
        contradicts_refs: tuple[KnowledgeRef, ...],
    ) -> str:
        return _sha256(
            {
                "candidate_record_sha256": candidate.record_sha256,
                "candidate_ref": candidate.candidate_ref.value,
                "contradicts_refs": [item.value for item in contradicts_refs],
                "decision_record_sha256": decision.record_sha256,
                "idempotency_key": idempotency_key,
                "knowledge_ref": knowledge_ref.value,
                "supersedes_refs": [item.value for item in supersedes_refs],
            }
        )

    @staticmethod
    def _scope_key(project_ref: ProjectRef | None) -> str:
        return "" if project_ref is None else project_ref.value

    @staticmethod
    def _project_ref_from_storage(value: str) -> ProjectRef | None:
        return None if value == "" else ProjectRef(value)

    @staticmethod
    def _ref_payload(ref: KnowledgeRef) -> dict[str, object]:
        return {
            "knowledge_id": ref.knowledge_id,
            "project_ref": None if ref.project_ref is None else ref.project_ref.value,
            "scope": ref.scope,
            "version": ref.version,
        }

    def _refs_from_json(
        self,
        value: object,
        field_name: str,
    ) -> tuple[KnowledgeRef, ...]:
        try:
            raw = cast(object, json.loads(cast(str, value)))
        except (TypeError, json.JSONDecodeError) as exc:
            raise KnowledgeIntegrityError(f"{field_name} is unreadable") from exc
        if not isinstance(raw, list):
            raise KnowledgeIntegrityError(f"{field_name} is malformed")
        refs: list[KnowledgeRef] = []
        for item in raw:
            if not isinstance(item, dict):
                raise KnowledgeIntegrityError(f"{field_name} item is malformed")
            try:
                project_value = item["project_ref"]
                refs.append(
                    KnowledgeRef(
                        cast(str, item["scope"]),
                        None
                        if project_value is None
                        else ProjectRef(cast(str, project_value)),
                        cast(str, item["knowledge_id"]),
                        cast(int, item["version"]),
                    )
                )
            except (KeyError, TypeError, KnowledgeError) as exc:
                raise KnowledgeIntegrityError(f"{field_name} item is malformed") from exc
        return _freeze_knowledge_refs(refs, field_name)

    @staticmethod
    def _mapping_object_from_json(
        value: object,
        field_name: str,
    ) -> Mapping[str, object]:
        try:
            raw = cast(object, json.loads(cast(str, value)))
        except (TypeError, json.JSONDecodeError) as exc:
            raise KnowledgeIntegrityError(f"{field_name} is unreadable") from exc
        if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
            raise KnowledgeIntegrityError(f"{field_name} is malformed")
        return cast(Mapping[str, object], raw)

    def _string_mapping_from_json(
        self,
        value: object,
        field_name: str,
    ) -> Mapping[str, str]:
        raw = self._mapping_object_from_json(value, field_name)
        if any(not isinstance(item, str) for item in raw.values()):
            raise KnowledgeIntegrityError(f"{field_name} values are malformed")
        return cast(Mapping[str, str], raw)

    @staticmethod
    def _string_sequence_from_json(value: object, field_name: str) -> tuple[str, ...]:
        try:
            raw = cast(object, json.loads(cast(str, value)))
        except (TypeError, json.JSONDecodeError) as exc:
            raise KnowledgeIntegrityError(f"{field_name} is unreadable") from exc
        return KnowledgeService._string_sequence(raw, field_name)

    @staticmethod
    def _string_sequence(value: object, field_name: str) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise KnowledgeIntegrityError(f"{field_name} is malformed")
        return tuple(cast(list[str], value))

    @staticmethod
    def _boolean(value: object, field_name: str) -> bool:
        if not isinstance(value, bool):
            raise KnowledgeIntegrityError(f"{field_name} is malformed")
        return value

    @staticmethod
    def _content_from_json(value: object) -> ContentRef | None:
        if value is None:
            return None
        try:
            raw = cast(object, json.loads(cast(str, value)))
        except (TypeError, json.JSONDecodeError) as exc:
            raise KnowledgeIntegrityError("content_ref is unreadable") from exc
        if not isinstance(raw, dict):
            raise KnowledgeIntegrityError("content_ref is malformed")
        try:
            return ContentRef(
                algorithm=cast(str, raw["algorithm"]),
                digest=cast(str, raw["digest"]),
                media_type=cast(str, raw["media_type"]),
                size_bytes=cast(int, raw["size_bytes"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise KnowledgeIntegrityError("content_ref is malformed") from exc

    @staticmethod
    def _verify_digest(expected: str, observed: str, label: str) -> None:
        _validate_sha256(expected, f"{label} digest")
        _validate_sha256(observed, f"observed {label} digest")
        if not hmac.compare_digest(expected, observed):
            raise KnowledgeIntegrityError(f"{label} digest differs")
