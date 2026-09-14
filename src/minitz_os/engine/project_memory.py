"""Durable, isolated, versioned Project knowledge with explicit placement."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .artifact import (
    Artifact,
    ArtifactError,
    ArtifactRef,
    ArtifactService,
    ContentRef,
)
from .project import (
    ProjectAccess,
    ProjectError,
    ProjectRef,
    ProjectScopeError,
    ProjectStore,
)


_CANDIDATE_ID_PATTERN = re.compile(r"pkc_[0-9a-f]{32}")
_KNOWLEDGE_ID_PATTERN = re.compile(r"pkn_[0-9a-f]{32}")
_TYPE_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+")
_KEY_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_ACTOR_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s]+")
_RESOLUTION_STATUSES = {"CONFLICT", "CURRENT"}


class ProjectKnowledgeError(Exception):
    """Base class for Project knowledge failures."""


class ProjectKnowledgeContractError(ProjectKnowledgeError, ValueError):
    """A Project knowledge request or value is malformed."""


class ProjectKnowledgeScopeError(ProjectKnowledgeError):
    """A Project knowledge request crossed exact Project scope."""


class ProjectKnowledgeNotFoundError(ProjectKnowledgeError):
    """The requested candidate or knowledge revision does not exist."""


class ProjectKnowledgeConflictError(ProjectKnowledgeError):
    """A placement or current-resolution request conflicts with durable state."""


class ProjectKnowledgeIntegrityError(ProjectKnowledgeError):
    """Durable Project knowledge failed exact integrity verification."""


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
        raise ProjectKnowledgeContractError(f"{field_name} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProjectKnowledgeContractError(f"{field_name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProjectKnowledgeContractError(f"{field_name} must be timezone-aware")
    return value


def _validate_key(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise ProjectKnowledgeContractError(f"{field_name} is malformed")
    return value


def _validate_type(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or _TYPE_PATTERN.fullmatch(value) is None
    ):
        raise ProjectKnowledgeContractError(f"{field_name} is malformed")
    return value


def _validate_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ProjectKnowledgeIntegrityError(f"{field_name} is malformed")
    return value


def _freeze_applicability(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ProjectKnowledgeContractError("applicability must be a mapping")
    copied = dict(value)
    if len(copied) > 32:
        raise ProjectKnowledgeContractError("applicability is unbounded")
    for key, item in copied.items():
        _validate_key(key, "applicability key")
        if not isinstance(item, str) or not item or len(item.encode()) > 2048:
            raise ProjectKnowledgeContractError("applicability value is malformed")
    return MappingProxyType(dict(sorted(copied.items())))


def _freeze_artifact_refs(
    values: Sequence[ArtifactRef],
    project_ref: ProjectRef,
    field_name: str,
) -> tuple[ArtifactRef, ...]:
    copied = tuple(values)
    if len(copied) > 64:
        raise ProjectKnowledgeContractError(f"{field_name} is unbounded")
    if not all(isinstance(item, ArtifactRef) for item in copied):
        raise ProjectKnowledgeContractError(
            f"{field_name} accepts only exact ArtifactRef values"
        )
    if any(item.project_ref != project_ref for item in copied):
        raise ProjectKnowledgeScopeError(f"{field_name} crossed Project scope")
    if len(set(copied)) != len(copied):
        raise ProjectKnowledgeContractError(f"{field_name} contains duplicates")
    return copied


def _freeze_knowledge_refs(
    values: Sequence[ProjectKnowledgeRef],
    knowledge_ref: ProjectKnowledgeRef,
    field_name: str,
) -> tuple[ProjectKnowledgeRef, ...]:
    copied = tuple(values)
    if len(copied) > 64:
        raise ProjectKnowledgeContractError(f"{field_name} is unbounded")
    if not all(isinstance(item, ProjectKnowledgeRef) for item in copied):
        raise ProjectKnowledgeContractError(
            f"{field_name} accepts only ProjectKnowledgeRef values"
        )
    if any(
        item.project_ref != knowledge_ref.project_ref
        or item.knowledge_id != knowledge_ref.knowledge_id
        or item.version >= knowledge_ref.version
        for item in copied
    ):
        raise ProjectKnowledgeContractError(
            f"{field_name} must reference an earlier revision of the same knowledge"
        )
    if len(set(copied)) != len(copied):
        raise ProjectKnowledgeContractError(f"{field_name} contains duplicates")
    return tuple(sorted(copied, key=lambda item: item.version))


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
        raise ProjectKnowledgeContractError(
            "exactly one statement or content_ref is required"
        )
    if statement is not None:
        if (
            not isinstance(statement, str)
            or not statement.strip()
            or len(statement.encode()) > 8192
        ):
            raise ProjectKnowledgeContractError("statement is empty or unbounded")
        return statement, None
    if not isinstance(content_ref, ContentRef):
        raise ProjectKnowledgeContractError("content_ref must be ContentRef")
    return None, content_ref


@dataclass(frozen=True, order=True)
class ProjectKnowledgeCandidateRef:
    """Exact identity of one durable, non-authoritative observation candidate."""

    project_ref: ProjectRef
    candidate_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.candidate_id, str)
            or _CANDIDATE_ID_PATTERN.fullmatch(self.candidate_id) is None
        ):
            raise ProjectKnowledgeContractError("candidate identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> ProjectKnowledgeCandidateRef:
        return cls(project_ref, f"pkc_{uuid4().hex}")

    @property
    def value(self) -> str:
        return (
            f"project-knowledge-candidate://{self.project_ref.value}/"
            f"{self.candidate_id}"
        )


@dataclass(frozen=True, order=True)
class ProjectKnowledgeRef:
    """Exact identity of one immutable Project knowledge revision."""

    project_ref: ProjectRef
    knowledge_id: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.knowledge_id, str)
            or _KNOWLEDGE_ID_PATTERN.fullmatch(self.knowledge_id) is None
        ):
            raise ProjectKnowledgeContractError("knowledge identity is malformed")
        if (
            not isinstance(self.version, int)
            or isinstance(self.version, bool)
            or self.version < 1
        ):
            raise ProjectKnowledgeContractError("knowledge version must be positive")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> ProjectKnowledgeRef:
        return cls(project_ref, f"pkn_{uuid4().hex}", 1)

    def next_version(self) -> ProjectKnowledgeRef:
        return ProjectKnowledgeRef(
            self.project_ref,
            self.knowledge_id,
            self.version + 1,
        )

    @property
    def value(self) -> str:
        return (
            f"project-knowledge://{self.project_ref.value}/"
            f"{self.knowledge_id}/{self.version}"
        )


@dataclass(frozen=True)
class ProjectKnowledgeCandidate:
    """Durable observation that is not accepted Project truth."""

    candidate_ref: ProjectKnowledgeCandidateRef
    idempotency_key: str
    origin_type: str
    knowledge_type: str
    statement: str | None
    content_ref: ContentRef | None
    applicability: Mapping[str, str]
    source_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    provenance_sha256: str
    created_at: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_ref, ProjectKnowledgeCandidateRef):
            raise ProjectKnowledgeContractError("candidate_ref is required")
        _validate_key(self.idempotency_key, "idempotency_key")
        _validate_type(self.origin_type, "origin_type")
        _validate_type(self.knowledge_type, "knowledge_type")
        statement, content_ref = _validate_statement_or_content(
            self.statement,
            self.content_ref,
        )
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "content_ref", content_ref)
        object.__setattr__(self, "applicability", _freeze_applicability(self.applicability))
        sources = _freeze_artifact_refs(
            self.source_refs,
            self.project_ref,
            "source_refs",
        )
        evidence = _freeze_artifact_refs(
            self.evidence_refs,
            self.project_ref,
            "evidence_refs",
        )
        if not sources:
            raise ProjectKnowledgeContractError(
                "candidate requires exact provenance source_refs"
            )
        object.__setattr__(self, "source_refs", sources)
        object.__setattr__(self, "evidence_refs", evidence)
        _validate_sha256(self.provenance_sha256, "provenance_sha256")
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(self, "semantic_digest", _sha256(self._semantic_payload()))
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "created_at": self.created_at,
                    "provenance_sha256": self.provenance_sha256,
                    "semantic_digest": self.semantic_digest,
                }
            ),
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.candidate_ref.project_ref

    @property
    def status(self) -> str:
        return "CANDIDATE"

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "applicability": dict(self.applicability),
            "candidate_ref": self.candidate_ref.value,
            "content_ref": _content_payload(self.content_ref),
            "evidence_refs": [item.value for item in self.evidence_refs],
            "idempotency_key": self.idempotency_key,
            "knowledge_type": self.knowledge_type,
            "origin_type": self.origin_type,
            "source_refs": [item.value for item in self.source_refs],
            "statement": self.statement,
        }


@dataclass(frozen=True)
class ProjectKnowledge:
    """One immutable, explicitly accepted Project knowledge revision."""

    knowledge_ref: ProjectKnowledgeRef
    candidate_ref: ProjectKnowledgeCandidateRef
    candidate_record_sha256: str
    knowledge_type: str
    statement: str | None
    content_ref: ContentRef | None
    applicability: Mapping[str, str]
    source_refs: tuple[ArtifactRef, ...]
    evidence_refs: tuple[ArtifactRef, ...]
    provenance_sha256: str
    accepted_by: str
    accepted_at: str
    supersedes_refs: tuple[ProjectKnowledgeRef, ...]
    contradicts_refs: tuple[ProjectKnowledgeRef, ...]
    placement_idempotency_key: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.knowledge_ref, ProjectKnowledgeRef):
            raise ProjectKnowledgeContractError("knowledge_ref is required")
        if not isinstance(self.candidate_ref, ProjectKnowledgeCandidateRef):
            raise ProjectKnowledgeContractError("candidate_ref is required")
        if self.candidate_ref.project_ref != self.project_ref:
            raise ProjectKnowledgeScopeError("candidate crossed Project scope")
        _validate_sha256(self.candidate_record_sha256, "candidate_record_sha256")
        _validate_type(self.knowledge_type, "knowledge_type")
        statement, content_ref = _validate_statement_or_content(
            self.statement,
            self.content_ref,
        )
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "content_ref", content_ref)
        object.__setattr__(self, "applicability", _freeze_applicability(self.applicability))
        object.__setattr__(
            self,
            "source_refs",
            _freeze_artifact_refs(self.source_refs, self.project_ref, "source_refs"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_artifact_refs(self.evidence_refs, self.project_ref, "evidence_refs"),
        )
        _validate_sha256(self.provenance_sha256, "provenance_sha256")
        if (
            not isinstance(self.accepted_by, str)
            or len(self.accepted_by.encode()) > 1024
            or _ACTOR_PATTERN.fullmatch(self.accepted_by) is None
        ):
            raise ProjectKnowledgeContractError("accepted_by is malformed")
        _validate_timestamp(self.accepted_at, "accepted_at")
        supersedes = _freeze_knowledge_refs(
            self.supersedes_refs,
            self.knowledge_ref,
            "supersedes_refs",
        )
        contradicts = _freeze_knowledge_refs(
            self.contradicts_refs,
            self.knowledge_ref,
            "contradicts_refs",
        )
        if set(supersedes) & set(contradicts):
            raise ProjectKnowledgeContractError(
                "one revision cannot be both superseded and contradicted"
            )
        object.__setattr__(self, "supersedes_refs", supersedes)
        object.__setattr__(self, "contradicts_refs", contradicts)
        _validate_key(self.placement_idempotency_key, "placement_idempotency_key")
        object.__setattr__(self, "semantic_digest", _sha256(self._semantic_payload()))
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "accepted_at": self.accepted_at,
                    "semantic_digest": self.semantic_digest,
                }
            ),
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.knowledge_ref.project_ref

    @property
    def status(self) -> str:
        return "ACCEPTED"

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "accepted_by": self.accepted_by,
            "applicability": dict(self.applicability),
            "candidate_record_sha256": self.candidate_record_sha256,
            "candidate_ref": self.candidate_ref.value,
            "content_ref": _content_payload(self.content_ref),
            "contradicts_refs": [item.value for item in self.contradicts_refs],
            "evidence_refs": [item.value for item in self.evidence_refs],
            "knowledge_ref": self.knowledge_ref.value,
            "knowledge_type": self.knowledge_type,
            "placement_idempotency_key": self.placement_idempotency_key,
            "provenance_sha256": self.provenance_sha256,
            "source_refs": [item.value for item in self.source_refs],
            "statement": self.statement,
            "supersedes_refs": [item.value for item in self.supersedes_refs],
        }


@dataclass(frozen=True)
class ProjectKnowledgeResolution:
    """Conflict-aware effective state for one Project knowledge identity."""

    project_ref: ProjectRef
    knowledge_id: str
    status: str
    current: ProjectKnowledge | None
    candidates: tuple[ProjectKnowledge, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise ProjectKnowledgeContractError("ProjectRef is required")
        if (
            not isinstance(self.knowledge_id, str)
            or _KNOWLEDGE_ID_PATTERN.fullmatch(self.knowledge_id) is None
        ):
            raise ProjectKnowledgeContractError("knowledge identity is malformed")
        if self.status not in _RESOLUTION_STATUSES:
            raise ProjectKnowledgeContractError("resolution status is malformed")
        object.__setattr__(self, "candidates", tuple(self.candidates))
        if not self.candidates:
            raise ProjectKnowledgeIntegrityError("resolution has no candidates")
        if any(
            item.project_ref != self.project_ref
            or item.knowledge_ref.knowledge_id != self.knowledge_id
            for item in self.candidates
        ):
            raise ProjectKnowledgeIntegrityError("resolution identity differs")
        if self.status == "CURRENT":
            if len(self.candidates) != 1 or self.current != self.candidates[0]:
                raise ProjectKnowledgeIntegrityError("current resolution is inconsistent")
        elif self.current is not None or len(self.candidates) < 2:
            raise ProjectKnowledgeIntegrityError("conflict resolution is inconsistent")


class ProjectKnowledgeService:
    """Authoritative Project-scoped candidate, placement, and resolution service."""

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
                CREATE TABLE IF NOT EXISTS project_knowledge_candidates (
                    project_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    origin_type TEXT NOT NULL,
                    knowledge_type TEXT NOT NULL,
                    statement TEXT,
                    content_json TEXT,
                    applicability_json TEXT NOT NULL,
                    provenance_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, candidate_id),
                    UNIQUE (project_id, idempotency_key),
                    UNIQUE (project_id, candidate_id, record_sha256),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS project_knowledge_candidate_artifacts (
                    project_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    binding_kind TEXT NOT NULL CHECK(binding_kind IN ('source', 'evidence')),
                    position INTEGER NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, candidate_id, binding_kind, position),
                    UNIQUE (project_id, candidate_id, binding_kind, artifact_id, artifact_revision),
                    FOREIGN KEY (project_id, candidate_id)
                        REFERENCES project_knowledge_candidates(project_id, candidate_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id, artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS project_knowledge_revisions (
                    project_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    candidate_id TEXT NOT NULL,
                    candidate_record_sha256 TEXT NOT NULL,
                    accepted_by TEXT NOT NULL,
                    accepted_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    placement_request_sha256 TEXT NOT NULL,
                    relations_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, knowledge_id, version),
                    UNIQUE (project_id, idempotency_key),
                    UNIQUE (project_id, candidate_id),
                    UNIQUE (project_id, knowledge_id, version, record_sha256),
                    FOREIGN KEY (project_id, candidate_id, candidate_record_sha256)
                        REFERENCES project_knowledge_candidates(
                            project_id, candidate_id, record_sha256
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS project_knowledge_relations (
                    project_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    from_version INTEGER NOT NULL,
                    relation_kind TEXT NOT NULL CHECK(relation_kind IN ('supersedes', 'contradicts')),
                    position INTEGER NOT NULL,
                    target_version INTEGER NOT NULL,
                    target_record_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        project_id, knowledge_id, from_version, relation_kind, position
                    ),
                    UNIQUE (
                        project_id, knowledge_id, from_version, relation_kind, target_version
                    ),
                    FOREIGN KEY (project_id, knowledge_id, from_version)
                        REFERENCES project_knowledge_revisions(
                            project_id, knowledge_id, version
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, knowledge_id, target_version, target_record_sha256
                    ) REFERENCES project_knowledge_revisions(
                        project_id, knowledge_id, version, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS project_knowledge_heads (
                    project_id TEXT NOT NULL,
                    knowledge_id TEXT NOT NULL,
                    latest_version INTEGER NOT NULL,
                    latest_record_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, knowledge_id),
                    FOREIGN KEY (
                        project_id, knowledge_id, latest_version, latest_record_sha256
                    ) REFERENCES project_knowledge_revisions(
                        project_id, knowledge_id, version, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS project_knowledge_candidates_no_update
                BEFORE UPDATE ON project_knowledge_candidates
                BEGIN SELECT RAISE(ABORT, 'Project knowledge candidates are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_candidates_no_delete
                BEFORE DELETE ON project_knowledge_candidates
                BEGIN SELECT RAISE(ABORT, 'Project knowledge candidates cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_candidate_artifacts_no_update
                BEFORE UPDATE ON project_knowledge_candidate_artifacts
                BEGIN SELECT RAISE(ABORT, 'Project knowledge provenance is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_candidate_artifacts_no_delete
                BEFORE DELETE ON project_knowledge_candidate_artifacts
                BEGIN SELECT RAISE(ABORT, 'Project knowledge provenance cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_revisions_no_update
                BEFORE UPDATE ON project_knowledge_revisions
                BEGIN SELECT RAISE(ABORT, 'Project knowledge revisions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_revisions_no_delete
                BEFORE DELETE ON project_knowledge_revisions
                BEGIN SELECT RAISE(ABORT, 'Project knowledge revisions cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_relations_no_update
                BEFORE UPDATE ON project_knowledge_relations
                BEGIN SELECT RAISE(ABORT, 'Project knowledge relations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_relations_no_delete
                BEFORE DELETE ON project_knowledge_relations
                BEGIN SELECT RAISE(ABORT, 'Project knowledge relations cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_heads_no_delete
                BEFORE DELETE ON project_knowledge_heads
                BEGIN SELECT RAISE(ABORT, 'Project knowledge heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS project_knowledge_heads_monotonic
                BEFORE UPDATE ON project_knowledge_heads
                WHEN NEW.project_id != OLD.project_id
                    OR NEW.knowledge_id != OLD.knowledge_id
                    OR NEW.latest_version != OLD.latest_version + 1
                    OR NEW.updated_at < OLD.updated_at
                BEGIN SELECT RAISE(ABORT, 'Project knowledge head must advance monotonically'); END;
                """
            )
        finally:
            connection.close()

    def record_candidate(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        idempotency_key: str,
        origin_type: str,
        knowledge_type: str,
        statement: str | None,
        content_ref: ContentRef | None,
        applicability: Mapping[str, str],
        source_refs: Sequence[ArtifactRef],
        evidence_refs: Sequence[ArtifactRef],
    ) -> ProjectKnowledgeCandidate:
        _validate_key(idempotency_key, "idempotency_key")
        _validate_type(origin_type, "origin_type")
        _validate_type(knowledge_type, "knowledge_type")
        normalized_statement, normalized_content = _validate_statement_or_content(
            statement,
            content_ref,
        )
        normalized_applicability = _freeze_applicability(applicability)
        normalized_sources = _freeze_artifact_refs(
            source_refs,
            project_ref,
            "source_refs",
        )
        normalized_evidence = _freeze_artifact_refs(
            evidence_refs,
            project_ref,
            "evidence_refs",
        )
        if not normalized_sources:
            raise ProjectKnowledgeContractError(
                "candidate requires exact provenance source_refs"
            )
        request_sha256 = self._candidate_request_sha256(
            project_ref,
            idempotency_key,
            origin_type,
            knowledge_type,
            normalized_statement,
            normalized_content,
            normalized_applicability,
            normalized_sources,
            normalized_evidence,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize(connection, requesting_access, project_ref)
            prior = connection.execute(
                """
                SELECT candidate_id, request_sha256
                FROM project_knowledge_candidates
                WHERE project_id = ? AND idempotency_key = ?
                """,
                (project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(
                    cast(str, prior["request_sha256"]),
                    request_sha256,
                ):
                    raise ProjectKnowledgeConflictError(
                        "candidate idempotency key has different semantics"
                    )
                result = self._fetch_candidate(
                    connection,
                    ProjectKnowledgeCandidateRef(
                        project_ref,
                        cast(str, prior["candidate_id"]),
                    ),
                )
                connection.commit()
                return result
            artifacts = self._verified_artifacts(
                connection,
                normalized_sources,
                normalized_evidence,
            )
            provenance_sha256 = self._provenance_sha256(artifacts)
            candidate = ProjectKnowledgeCandidate(
                candidate_ref=ProjectKnowledgeCandidateRef.new(project_ref),
                idempotency_key=idempotency_key,
                origin_type=origin_type,
                knowledge_type=knowledge_type,
                statement=normalized_statement,
                content_ref=normalized_content,
                applicability=normalized_applicability,
                source_refs=normalized_sources,
                evidence_refs=normalized_evidence,
                provenance_sha256=provenance_sha256,
                created_at=_now_utc(),
            )
            connection.execute(
                """
                INSERT INTO project_knowledge_candidates VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    project_ref.value,
                    candidate.candidate_ref.candidate_id,
                    candidate.idempotency_key,
                    candidate.origin_type,
                    candidate.knowledge_type,
                    candidate.statement,
                    None
                    if candidate.content_ref is None
                    else _json(_content_payload(candidate.content_ref)),
                    _json(dict(candidate.applicability)),
                    candidate.provenance_sha256,
                    candidate.created_at,
                    request_sha256,
                    candidate.semantic_digest,
                    candidate.record_sha256,
                ),
            )
            self._insert_candidate_artifacts(connection, candidate, artifacts)
            connection.commit()
            return candidate
        except (ProjectScopeError, ArtifactError) as exc:
            connection.rollback()
            if isinstance(exc, ProjectScopeError):
                raise ProjectKnowledgeScopeError("Project knowledge scope mismatch") from exc
            raise ProjectKnowledgeIntegrityError(
                "candidate provenance failed Artifact verification"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_candidate(
        self,
        requesting_access: ProjectAccess,
        candidate_ref: ProjectKnowledgeCandidateRef,
    ) -> ProjectKnowledgeCandidate:
        if not isinstance(candidate_ref, ProjectKnowledgeCandidateRef):
            raise ProjectKnowledgeContractError("candidate_ref is required")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize(connection, requesting_access, candidate_ref.project_ref)
            candidate = self._fetch_candidate(connection, candidate_ref)
            connection.commit()
            return candidate
        except ProjectScopeError as exc:
            connection.rollback()
            raise ProjectKnowledgeScopeError("Project knowledge scope mismatch") from exc
        except ArtifactError as exc:
            connection.rollback()
            raise ProjectKnowledgeIntegrityError(
                "candidate provenance failed Artifact verification"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def place_candidate(
        self,
        requesting_access: ProjectAccess,
        candidate_ref: ProjectKnowledgeCandidateRef,
        *,
        knowledge_ref: ProjectKnowledgeRef,
        accepted_by: str,
        idempotency_key: str,
        supersedes_refs: Sequence[ProjectKnowledgeRef] = (),
        contradicts_refs: Sequence[ProjectKnowledgeRef] = (),
    ) -> ProjectKnowledge:
        if not isinstance(candidate_ref, ProjectKnowledgeCandidateRef):
            raise ProjectKnowledgeContractError("candidate_ref is required")
        if not isinstance(knowledge_ref, ProjectKnowledgeRef):
            raise ProjectKnowledgeContractError("knowledge_ref is required")
        if candidate_ref.project_ref != knowledge_ref.project_ref:
            raise ProjectKnowledgeScopeError("candidate and knowledge scope differ")
        _validate_key(idempotency_key, "idempotency_key")
        if (
            not isinstance(accepted_by, str)
            or len(accepted_by.encode()) > 1024
            or _ACTOR_PATTERN.fullmatch(accepted_by) is None
        ):
            raise ProjectKnowledgeContractError("accepted_by is malformed")
        normalized_supersedes = _freeze_knowledge_refs(
            supersedes_refs,
            knowledge_ref,
            "supersedes_refs",
        )
        normalized_contradicts = _freeze_knowledge_refs(
            contradicts_refs,
            knowledge_ref,
            "contradicts_refs",
        )
        if set(normalized_supersedes) & set(normalized_contradicts):
            raise ProjectKnowledgeContractError(
                "one revision cannot supersede and contradict the same revision"
            )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize(connection, requesting_access, knowledge_ref.project_ref)
            candidate = self._fetch_candidate(connection, candidate_ref)
            placement_request_sha256 = self._placement_request_sha256(
                candidate,
                knowledge_ref,
                accepted_by,
                idempotency_key,
                normalized_supersedes,
                normalized_contradicts,
            )
            prior = connection.execute(
                """
                SELECT knowledge_id, version, placement_request_sha256
                FROM project_knowledge_revisions
                WHERE project_id = ? AND idempotency_key = ?
                """,
                (knowledge_ref.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                if not hmac.compare_digest(
                    cast(str, prior["placement_request_sha256"]),
                    placement_request_sha256,
                ):
                    raise ProjectKnowledgeConflictError(
                        "placement idempotency key has different semantics"
                    )
                result = self._fetch_knowledge(
                    connection,
                    ProjectKnowledgeRef(
                        knowledge_ref.project_ref,
                        cast(str, prior["knowledge_id"]),
                        cast(int, prior["version"]),
                    ),
                )
                connection.commit()
                return result
            placed = connection.execute(
                """
                SELECT 1 FROM project_knowledge_revisions
                WHERE project_id = ? AND candidate_id = ?
                """,
                (candidate.project_ref.value, candidate.candidate_ref.candidate_id),
            ).fetchone()
            if placed is not None:
                raise ProjectKnowledgeConflictError(
                    "candidate was already explicitly placed"
                )
            history = self._fetch_history_if_present(connection, knowledge_ref)
            expected_version = len(history) + 1
            if knowledge_ref.version != expected_version:
                raise ProjectKnowledgeConflictError(
                    "knowledge version does not advance exact durable history"
                )
            active_refs = self._active_refs(history)
            if not history:
                if normalized_supersedes or normalized_contradicts:
                    raise ProjectKnowledgeConflictError(
                        "initial knowledge cannot relate to missing history"
                    )
            else:
                known_refs = {item.knowledge_ref for item in history}
                requested_refs = set(normalized_supersedes) | set(normalized_contradicts)
                if not requested_refs.issubset(known_refs):
                    raise ProjectKnowledgeConflictError(
                        "knowledge relationship target was not found"
                    )
                if bool(normalized_supersedes) == bool(normalized_contradicts):
                    raise ProjectKnowledgeConflictError(
                        "new knowledge must explicitly supersede or contradict current state"
                    )
                relation_refs = (
                    set(normalized_supersedes)
                    if normalized_supersedes
                    else set(normalized_contradicts)
                )
                if relation_refs != active_refs:
                    raise ProjectKnowledgeConflictError(
                        "placement must address every current candidate"
                    )
            prior_by_ref = {item.knowledge_ref: item for item in history}
            relation_payload = self._relation_payload(
                normalized_supersedes,
                normalized_contradicts,
                prior_by_ref,
            )
            relations_sha256 = _sha256(relation_payload)
            knowledge = ProjectKnowledge(
                knowledge_ref=knowledge_ref,
                candidate_ref=candidate.candidate_ref,
                candidate_record_sha256=candidate.record_sha256,
                knowledge_type=candidate.knowledge_type,
                statement=candidate.statement,
                content_ref=candidate.content_ref,
                applicability=candidate.applicability,
                source_refs=candidate.source_refs,
                evidence_refs=candidate.evidence_refs,
                provenance_sha256=candidate.provenance_sha256,
                accepted_by=accepted_by,
                accepted_at=_now_utc(),
                supersedes_refs=normalized_supersedes,
                contradicts_refs=normalized_contradicts,
                placement_idempotency_key=idempotency_key,
            )
            connection.execute(
                """
                INSERT INTO project_knowledge_revisions VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    knowledge.project_ref.value,
                    knowledge.knowledge_ref.knowledge_id,
                    knowledge.knowledge_ref.version,
                    knowledge.candidate_ref.candidate_id,
                    knowledge.candidate_record_sha256,
                    knowledge.accepted_by,
                    knowledge.accepted_at,
                    knowledge.placement_idempotency_key,
                    placement_request_sha256,
                    relations_sha256,
                    knowledge.semantic_digest,
                    knowledge.record_sha256,
                ),
            )
            self._insert_relations(connection, knowledge, prior_by_ref)
            self._advance_head(connection, knowledge)
            connection.commit()
            return knowledge
        except ProjectScopeError as exc:
            connection.rollback()
            raise ProjectKnowledgeScopeError("Project knowledge scope mismatch") from exc
        except ArtifactError as exc:
            connection.rollback()
            raise ProjectKnowledgeIntegrityError(
                "candidate provenance failed Artifact verification"
            ) from exc
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ProjectKnowledgeConflictError("Project knowledge placement conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def supersede_candidate(
        self,
        requesting_access: ProjectAccess,
        candidate_ref: ProjectKnowledgeCandidateRef,
        *,
        prior_ref: ProjectKnowledgeRef,
        accepted_by: str,
        idempotency_key: str,
    ) -> ProjectKnowledge:
        resolution = self.resolve_current(requesting_access, prior_ref)
        if resolution.status != "CURRENT" or resolution.current is None:
            raise ProjectKnowledgeConflictError(
                "unresolved conflict requires explicit multi-candidate resolution"
            )
        if resolution.current.knowledge_ref != prior_ref:
            raise ProjectKnowledgeConflictError("prior_ref is not current knowledge")
        history = self.list_history(requesting_access, prior_ref)
        return self.place_candidate(
            requesting_access,
            candidate_ref,
            knowledge_ref=history[-1].knowledge_ref.next_version(),
            accepted_by=accepted_by,
            idempotency_key=idempotency_key,
            supersedes_refs=(prior_ref,),
        )

    def get_knowledge(
        self,
        requesting_access: ProjectAccess,
        knowledge_ref: ProjectKnowledgeRef,
    ) -> ProjectKnowledge:
        history = self.list_history(requesting_access, knowledge_ref)
        result = next(
            (item for item in history if item.knowledge_ref == knowledge_ref),
            None,
        )
        if result is None:
            raise ProjectKnowledgeNotFoundError("Project knowledge revision not found")
        return result

    def list_history(
        self,
        requesting_access: ProjectAccess,
        knowledge_ref: ProjectKnowledgeRef,
    ) -> tuple[ProjectKnowledge, ...]:
        if not isinstance(knowledge_ref, ProjectKnowledgeRef):
            raise ProjectKnowledgeContractError("knowledge_ref is required")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize(connection, requesting_access, knowledge_ref.project_ref)
            history = self._fetch_history(connection, knowledge_ref)
            connection.commit()
            return history
        except ProjectScopeError as exc:
            connection.rollback()
            raise ProjectKnowledgeScopeError("Project knowledge scope mismatch") from exc
        except ArtifactError as exc:
            connection.rollback()
            raise ProjectKnowledgeIntegrityError(
                "knowledge provenance failed Artifact verification"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def resolve_current(
        self,
        requesting_access: ProjectAccess,
        knowledge_ref: ProjectKnowledgeRef,
    ) -> ProjectKnowledgeResolution:
        history = self.list_history(requesting_access, knowledge_ref)
        active_refs = self._active_refs(history)
        active = tuple(
            item for item in history if item.knowledge_ref in active_refs
        )
        if len(active) == 1:
            return ProjectKnowledgeResolution(
                project_ref=knowledge_ref.project_ref,
                knowledge_id=knowledge_ref.knowledge_id,
                status="CURRENT",
                current=active[0],
                candidates=active,
            )
        return ProjectKnowledgeResolution(
            project_ref=knowledge_ref.project_ref,
            knowledge_id=knowledge_ref.knowledge_id,
            status="CONFLICT",
            current=None,
            candidates=active,
        )

    def list_knowledge(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
        *,
        knowledge_type: str | None = None,
    ) -> tuple[ProjectKnowledge, ...]:
        if knowledge_type is not None:
            _validate_type(knowledge_type, "knowledge_type")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize(connection, requesting_access, project_ref)
            rows = connection.execute(
                """
                SELECT DISTINCT knowledge_id FROM project_knowledge_revisions
                WHERE project_id = ? ORDER BY knowledge_id
                """,
                (project_ref.value,),
            ).fetchall()
            head_rows = connection.execute(
                """
                SELECT knowledge_id FROM project_knowledge_heads
                WHERE project_id = ? ORDER BY knowledge_id
                """,
                (project_ref.value,),
            ).fetchall()
            revision_ids = tuple(cast(str, row["knowledge_id"]) for row in rows)
            head_ids = tuple(cast(str, row["knowledge_id"]) for row in head_rows)
            if revision_ids != head_ids:
                raise ProjectKnowledgeIntegrityError(
                    "Project knowledge heads and revision histories differ"
                )
            result: list[ProjectKnowledge] = []
            for row in rows:
                reference = ProjectKnowledgeRef(
                    project_ref,
                    cast(str, row["knowledge_id"]),
                    1,
                )
                result.extend(self._fetch_history(connection, reference))
            filtered = tuple(
                item
                for item in result
                if knowledge_type is None or item.knowledge_type == knowledge_type
            )
            connection.commit()
            return filtered
        except ProjectScopeError as exc:
            connection.rollback()
            raise ProjectKnowledgeScopeError("Project knowledge scope mismatch") from exc
        except ArtifactError as exc:
            connection.rollback()
            raise ProjectKnowledgeIntegrityError(
                "knowledge provenance failed Artifact verification"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def search_knowledge(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
        *,
        knowledge_type: str | None = None,
        applicability: Mapping[str, str] | None = None,
        statement_contains: str | None = None,
    ) -> tuple[ProjectKnowledge, ...]:
        query = {} if applicability is None else _freeze_applicability(applicability)
        if statement_contains is not None and (
            not isinstance(statement_contains, str)
            or not statement_contains
            or len(statement_contains.encode()) > 2048
        ):
            raise ProjectKnowledgeContractError("statement_contains is malformed")
        records = self.list_knowledge(
            requesting_access,
            project_ref,
            knowledge_type=knowledge_type,
        )
        needle = None if statement_contains is None else statement_contains.casefold()
        return tuple(
            item
            for item in records
            if all(item.applicability.get(key) == value for key, value in query.items())
            and (
                needle is None
                or (item.statement is not None and needle in item.statement.casefold())
            )
        )

    def _authorize(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        project_ref: ProjectRef,
    ) -> None:
        authorized = self.projects._authorize(connection, access)
        if authorized != project_ref:
            raise ProjectScopeError("Project scope mismatch")
        self.projects._fetch_project(connection, project_ref)

    def _verified_artifacts(
        self,
        connection: sqlite3.Connection,
        source_refs: tuple[ArtifactRef, ...],
        evidence_refs: tuple[ArtifactRef, ...],
    ) -> tuple[tuple[str, int, Artifact], ...]:
        result: list[tuple[str, int, Artifact]] = []
        for kind, refs in (("source", source_refs), ("evidence", evidence_refs)):
            for position, artifact_ref in enumerate(refs):
                result.append(
                    (
                        kind,
                        position,
                        self.artifacts._fetch_artifact(connection, artifact_ref),
                    )
                )
        return tuple(result)

    @staticmethod
    def _provenance_sha256(
        artifacts: tuple[tuple[str, int, Artifact], ...],
    ) -> str:
        return _sha256(
            [
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "artifact_ref": artifact.artifact_ref.value,
                    "kind": kind,
                    "position": position,
                }
                for kind, position, artifact in artifacts
            ]
        )

    def _insert_candidate_artifacts(
        self,
        connection: sqlite3.Connection,
        candidate: ProjectKnowledgeCandidate,
        artifacts: tuple[tuple[str, int, Artifact], ...],
    ) -> None:
        for kind, position, artifact in artifacts:
            record = _sha256(
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "artifact_ref": artifact.artifact_ref.value,
                    "candidate_ref": candidate.candidate_ref.value,
                    "kind": kind,
                    "position": position,
                }
            )
            connection.execute(
                "INSERT INTO project_knowledge_candidate_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    candidate.project_ref.value,
                    candidate.candidate_ref.candidate_id,
                    kind,
                    position,
                    artifact.artifact_id,
                    artifact.revision,
                    artifact.record_sha256,
                    record,
                ),
            )

    def _fetch_candidate(
        self,
        connection: sqlite3.Connection,
        candidate_ref: ProjectKnowledgeCandidateRef,
    ) -> ProjectKnowledgeCandidate:
        row = connection.execute(
            """
            SELECT * FROM project_knowledge_candidates
            WHERE project_id = ? AND candidate_id = ?
            """,
            (candidate_ref.project_ref.value, candidate_ref.candidate_id),
        ).fetchone()
        if row is None:
            raise ProjectKnowledgeNotFoundError("Project knowledge candidate not found")
        binding_rows = connection.execute(
            """
            SELECT * FROM project_knowledge_candidate_artifacts
            WHERE project_id = ? AND candidate_id = ?
            ORDER BY binding_kind DESC, position
            """,
            (candidate_ref.project_ref.value, candidate_ref.candidate_id),
        ).fetchall()
        artifacts: list[tuple[str, int, Artifact]] = []
        positions: dict[str, list[int]] = {"evidence": [], "source": []}
        for binding in binding_rows:
            kind = cast(str, binding["binding_kind"])
            position = cast(int, binding["position"])
            artifact = self.artifacts._fetch_artifact(
                connection,
                ArtifactRef(
                    candidate_ref.project_ref,
                    cast(str, binding["artifact_id"]),
                    cast(int, binding["artifact_revision"]),
                ),
            )
            if artifact.record_sha256 != binding["artifact_record_sha256"]:
                raise ProjectKnowledgeIntegrityError(
                    "candidate Artifact provenance record differs"
                )
            expected_binding = _sha256(
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "artifact_ref": artifact.artifact_ref.value,
                    "candidate_ref": candidate_ref.value,
                    "kind": kind,
                    "position": position,
                }
            )
            self._verify_digest(
                expected_binding,
                binding["record_sha256"],
                "candidate Artifact binding",
            )
            positions[kind].append(position)
            artifacts.append((kind, position, artifact))
        for kind, observed in positions.items():
            if observed != list(range(len(observed))):
                raise ProjectKnowledgeIntegrityError(
                    f"candidate {kind} provenance is not gap-free"
                )
        artifacts_tuple = tuple(artifacts)
        provenance_sha256 = self._provenance_sha256(artifacts_tuple)
        self._verify_digest(
            provenance_sha256,
            row["provenance_sha256"],
            "candidate provenance",
        )
        source_refs = tuple(
            artifact.artifact_ref
            for kind, _, artifact in artifacts_tuple
            if kind == "source"
        )
        evidence_refs = tuple(
            artifact.artifact_ref
            for kind, _, artifact in artifacts_tuple
            if kind == "evidence"
        )
        candidate = ProjectKnowledgeCandidate(
            candidate_ref=candidate_ref,
            idempotency_key=cast(str, row["idempotency_key"]),
            origin_type=cast(str, row["origin_type"]),
            knowledge_type=cast(str, row["knowledge_type"]),
            statement=None if row["statement"] is None else cast(str, row["statement"]),
            content_ref=self._content_from_json(row["content_json"]),
            applicability=self._mapping_from_json(
                row["applicability_json"],
                "candidate applicability",
            ),
            source_refs=source_refs,
            evidence_refs=evidence_refs,
            provenance_sha256=provenance_sha256,
            created_at=cast(str, row["created_at"]),
        )
        self._verify_digest(
            candidate.semantic_digest,
            row["semantic_digest"],
            "candidate semantic digest",
        )
        self._verify_digest(
            candidate.record_sha256,
            row["record_sha256"],
            "candidate record",
        )
        request_sha256 = self._candidate_request_sha256(
            candidate.project_ref,
            candidate.idempotency_key,
            candidate.origin_type,
            candidate.knowledge_type,
            candidate.statement,
            candidate.content_ref,
            candidate.applicability,
            candidate.source_refs,
            candidate.evidence_refs,
        )
        self._verify_digest(
            request_sha256,
            row["request_sha256"],
            "candidate request",
        )
        return candidate

    def _fetch_knowledge(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: ProjectKnowledgeRef,
    ) -> ProjectKnowledge:
        history = self._fetch_history(connection, knowledge_ref)
        result = next(
            (item for item in history if item.knowledge_ref == knowledge_ref),
            None,
        )
        if result is None:
            raise ProjectKnowledgeNotFoundError("Project knowledge revision not found")
        return result

    def _fetch_history_if_present(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: ProjectKnowledgeRef,
    ) -> tuple[ProjectKnowledge, ...]:
        exists = connection.execute(
            """
            SELECT 1 FROM project_knowledge_revisions
            WHERE project_id = ? AND knowledge_id = ? LIMIT 1
            """,
            (knowledge_ref.project_ref.value, knowledge_ref.knowledge_id),
        ).fetchone()
        if exists is None:
            return ()
        return self._fetch_history(connection, knowledge_ref)

    def _fetch_history(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: ProjectKnowledgeRef,
    ) -> tuple[ProjectKnowledge, ...]:
        rows = connection.execute(
            """
            SELECT * FROM project_knowledge_revisions
            WHERE project_id = ? AND knowledge_id = ?
            ORDER BY version
            """,
            (knowledge_ref.project_ref.value, knowledge_ref.knowledge_id),
        ).fetchall()
        if not rows:
            head = connection.execute(
                """
                SELECT 1 FROM project_knowledge_heads
                WHERE project_id = ? AND knowledge_id = ?
                """,
                (knowledge_ref.project_ref.value, knowledge_ref.knowledge_id),
            ).fetchone()
            if head is not None:
                raise ProjectKnowledgeIntegrityError(
                    "Project knowledge head exists without revision history"
                )
            raise ProjectKnowledgeNotFoundError("Project knowledge was not found")
        if tuple(row["version"] for row in rows) != tuple(range(1, len(rows) + 1)):
            raise ProjectKnowledgeIntegrityError(
                "Project knowledge history is not gap-free"
            )
        by_version: dict[int, ProjectKnowledge] = {}
        for row in rows:
            version = cast(int, row["version"])
            candidate = self._fetch_candidate(
                connection,
                ProjectKnowledgeCandidateRef(
                    knowledge_ref.project_ref,
                    cast(str, row["candidate_id"]),
                ),
            )
            if candidate.record_sha256 != row["candidate_record_sha256"]:
                raise ProjectKnowledgeIntegrityError(
                    "knowledge candidate exact record differs"
                )
            supersedes, contradicts, relation_payload = self._fetch_relations(
                connection,
                knowledge_ref,
                version,
                by_version,
            )
            relations_sha256 = _sha256(relation_payload)
            self._verify_digest(
                relations_sha256,
                row["relations_sha256"],
                "knowledge relations",
            )
            knowledge = ProjectKnowledge(
                knowledge_ref=ProjectKnowledgeRef(
                    knowledge_ref.project_ref,
                    knowledge_ref.knowledge_id,
                    version,
                ),
                candidate_ref=candidate.candidate_ref,
                candidate_record_sha256=candidate.record_sha256,
                knowledge_type=candidate.knowledge_type,
                statement=candidate.statement,
                content_ref=candidate.content_ref,
                applicability=candidate.applicability,
                source_refs=candidate.source_refs,
                evidence_refs=candidate.evidence_refs,
                provenance_sha256=candidate.provenance_sha256,
                accepted_by=cast(str, row["accepted_by"]),
                accepted_at=cast(str, row["accepted_at"]),
                supersedes_refs=supersedes,
                contradicts_refs=contradicts,
                placement_idempotency_key=cast(str, row["idempotency_key"]),
            )
            self._verify_digest(
                knowledge.semantic_digest,
                row["semantic_digest"],
                "knowledge semantic digest",
            )
            self._verify_digest(
                knowledge.record_sha256,
                row["record_sha256"],
                "knowledge record",
            )
            placement_request_sha256 = self._placement_request_sha256(
                candidate,
                knowledge.knowledge_ref,
                knowledge.accepted_by,
                knowledge.placement_idempotency_key,
                knowledge.supersedes_refs,
                knowledge.contradicts_refs,
            )
            self._verify_digest(
                placement_request_sha256,
                row["placement_request_sha256"],
                "knowledge placement request",
            )
            by_version[version] = knowledge
        history = tuple(by_version[version] for version in sorted(by_version))
        head = connection.execute(
            """
            SELECT * FROM project_knowledge_heads
            WHERE project_id = ? AND knowledge_id = ?
            """,
            (knowledge_ref.project_ref.value, knowledge_ref.knowledge_id),
        ).fetchone()
        latest = history[-1]
        if (
            head is None
            or head["latest_version"] != latest.knowledge_ref.version
            or head["latest_record_sha256"] != latest.record_sha256
            or head["updated_at"] != latest.accepted_at
        ):
            raise ProjectKnowledgeIntegrityError(
                "Project knowledge head differs from history"
            )
        self._verify_digest(
            self._head_sha256(latest),
            head["record_sha256"],
            "Project knowledge head",
        )
        self._validate_history_semantics(history)
        return history

    def _fetch_relations(
        self,
        connection: sqlite3.Connection,
        knowledge_ref: ProjectKnowledgeRef,
        from_version: int,
        prior_by_version: Mapping[int, ProjectKnowledge],
    ) -> tuple[
        tuple[ProjectKnowledgeRef, ...],
        tuple[ProjectKnowledgeRef, ...],
        list[dict[str, object]],
    ]:
        rows = connection.execute(
            """
            SELECT * FROM project_knowledge_relations
            WHERE project_id = ? AND knowledge_id = ? AND from_version = ?
            ORDER BY relation_kind DESC, position
            """,
            (
                knowledge_ref.project_ref.value,
                knowledge_ref.knowledge_id,
                from_version,
            ),
        ).fetchall()
        positions: dict[str, list[int]] = {"contradicts": [], "supersedes": []}
        result: dict[str, list[ProjectKnowledgeRef]] = {
            "contradicts": [],
            "supersedes": [],
        }
        payload: list[dict[str, object]] = []
        for row in rows:
            kind = cast(str, row["relation_kind"])
            position = cast(int, row["position"])
            target_version = cast(int, row["target_version"])
            target = prior_by_version.get(target_version)
            if target is None or target.record_sha256 != row["target_record_sha256"]:
                raise ProjectKnowledgeIntegrityError(
                    "knowledge relationship target differs"
                )
            target_ref = target.knowledge_ref
            expected = _sha256(
                {
                    "from_ref": ProjectKnowledgeRef(
                        knowledge_ref.project_ref,
                        knowledge_ref.knowledge_id,
                        from_version,
                    ).value,
                    "kind": kind,
                    "position": position,
                    "target_record_sha256": target.record_sha256,
                    "target_ref": target_ref.value,
                }
            )
            self._verify_digest(expected, row["record_sha256"], "knowledge relation")
            positions[kind].append(position)
            result[kind].append(target_ref)
            payload.append(
                {
                    "kind": kind,
                    "position": position,
                    "target_record_sha256": target.record_sha256,
                    "target_ref": target_ref.value,
                }
            )
        for kind, observed in positions.items():
            if observed != list(range(len(observed))):
                raise ProjectKnowledgeIntegrityError(
                    f"knowledge {kind} relations are not gap-free"
                )
        return (
            tuple(result["supersedes"]),
            tuple(result["contradicts"]),
            payload,
        )

    def _insert_relations(
        self,
        connection: sqlite3.Connection,
        knowledge: ProjectKnowledge,
        prior_by_ref: Mapping[ProjectKnowledgeRef, ProjectKnowledge],
    ) -> None:
        for kind, refs in (
            ("supersedes", knowledge.supersedes_refs),
            ("contradicts", knowledge.contradicts_refs),
        ):
            for position, target_ref in enumerate(refs):
                target = prior_by_ref[target_ref]
                record = _sha256(
                    {
                        "from_ref": knowledge.knowledge_ref.value,
                        "kind": kind,
                        "position": position,
                        "target_record_sha256": target.record_sha256,
                        "target_ref": target_ref.value,
                    }
                )
                connection.execute(
                    "INSERT INTO project_knowledge_relations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        knowledge.project_ref.value,
                        knowledge.knowledge_ref.knowledge_id,
                        knowledge.knowledge_ref.version,
                        kind,
                        position,
                        target_ref.version,
                        target.record_sha256,
                        record,
                    ),
                )

    def _advance_head(
        self,
        connection: sqlite3.Connection,
        knowledge: ProjectKnowledge,
    ) -> None:
        head_record = self._head_sha256(knowledge)
        if knowledge.knowledge_ref.version == 1:
            connection.execute(
                "INSERT INTO project_knowledge_heads VALUES (?, ?, ?, ?, ?, ?)",
                (
                    knowledge.project_ref.value,
                    knowledge.knowledge_ref.knowledge_id,
                    knowledge.knowledge_ref.version,
                    knowledge.record_sha256,
                    knowledge.accepted_at,
                    head_record,
                ),
            )
            return
        result = connection.execute(
            """
            UPDATE project_knowledge_heads
            SET latest_version = ?, latest_record_sha256 = ?, updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND knowledge_id = ? AND latest_version = ?
            """,
            (
                knowledge.knowledge_ref.version,
                knowledge.record_sha256,
                knowledge.accepted_at,
                head_record,
                knowledge.project_ref.value,
                knowledge.knowledge_ref.knowledge_id,
                knowledge.knowledge_ref.version - 1,
            ),
        )
        if result.rowcount != 1:
            raise ProjectKnowledgeConflictError(
                "Project knowledge head did not advance"
            )

    @staticmethod
    def _active_refs(
        history: Sequence[ProjectKnowledge],
    ) -> set[ProjectKnowledgeRef]:
        all_refs = {item.knowledge_ref for item in history}
        superseded = {
            target
            for item in history
            for target in item.supersedes_refs
        }
        active = all_refs - superseded
        if history and not active:
            raise ProjectKnowledgeIntegrityError(
                "Project knowledge has no current candidates"
            )
        return active

    @classmethod
    def _validate_history_semantics(
        cls,
        history: tuple[ProjectKnowledge, ...],
    ) -> None:
        active: set[ProjectKnowledgeRef] = set()
        for index, item in enumerate(history):
            if index == 0:
                if item.supersedes_refs or item.contradicts_refs:
                    raise ProjectKnowledgeIntegrityError(
                        "initial knowledge has invalid relationships"
                    )
                active.add(item.knowledge_ref)
                continue
            if bool(item.supersedes_refs) == bool(item.contradicts_refs):
                raise ProjectKnowledgeIntegrityError(
                    "knowledge relationship classification is ambiguous"
                )
            addressed = (
                set(item.supersedes_refs)
                if item.supersedes_refs
                else set(item.contradicts_refs)
            )
            if addressed != active:
                raise ProjectKnowledgeIntegrityError(
                    "knowledge revision does not address exact current state"
                )
            active -= set(item.supersedes_refs)
            active.add(item.knowledge_ref)
        if cls._active_refs(history) != active:
            raise ProjectKnowledgeIntegrityError(
                "knowledge current-state derivation differs"
            )

    @staticmethod
    def _candidate_request_sha256(
        project_ref: ProjectRef,
        idempotency_key: str,
        origin_type: str,
        knowledge_type: str,
        statement: str | None,
        content_ref: ContentRef | None,
        applicability: Mapping[str, str],
        source_refs: Sequence[ArtifactRef],
        evidence_refs: Sequence[ArtifactRef],
    ) -> str:
        return _sha256(
            {
                "applicability": dict(applicability),
                "content_ref": _content_payload(content_ref),
                "evidence_refs": [item.value for item in evidence_refs],
                "idempotency_key": idempotency_key,
                "knowledge_type": knowledge_type,
                "origin_type": origin_type,
                "project_ref": project_ref.value,
                "source_refs": [item.value for item in source_refs],
                "statement": statement,
            }
        )

    @staticmethod
    def _placement_request_sha256(
        candidate: ProjectKnowledgeCandidate,
        knowledge_ref: ProjectKnowledgeRef,
        accepted_by: str,
        idempotency_key: str,
        supersedes_refs: Sequence[ProjectKnowledgeRef],
        contradicts_refs: Sequence[ProjectKnowledgeRef],
    ) -> str:
        return _sha256(
            {
                "accepted_by": accepted_by,
                "candidate_record_sha256": candidate.record_sha256,
                "candidate_ref": candidate.candidate_ref.value,
                "contradicts_refs": [item.value for item in contradicts_refs],
                "idempotency_key": idempotency_key,
                "knowledge_ref": knowledge_ref.value,
                "supersedes_refs": [item.value for item in supersedes_refs],
            }
        )

    @staticmethod
    def _relation_payload(
        supersedes_refs: Sequence[ProjectKnowledgeRef],
        contradicts_refs: Sequence[ProjectKnowledgeRef],
        prior_by_ref: Mapping[ProjectKnowledgeRef, ProjectKnowledge],
    ) -> list[dict[str, object]]:
        payload: list[dict[str, object]] = []
        for kind, refs in (
            ("supersedes", supersedes_refs),
            ("contradicts", contradicts_refs),
        ):
            for position, target_ref in enumerate(refs):
                target = prior_by_ref[target_ref]
                payload.append(
                    {
                        "kind": kind,
                        "position": position,
                        "target_record_sha256": target.record_sha256,
                        "target_ref": target_ref.value,
                    }
                )
        return payload

    @staticmethod
    def _head_sha256(knowledge: ProjectKnowledge) -> str:
        return _sha256(
            {
                "knowledge_id": knowledge.knowledge_ref.knowledge_id,
                "latest_record_sha256": knowledge.record_sha256,
                "latest_version": knowledge.knowledge_ref.version,
                "project_ref": knowledge.project_ref.value,
                "updated_at": knowledge.accepted_at,
            }
        )

    @staticmethod
    def _mapping_from_json(value: object, field_name: str) -> Mapping[str, str]:
        if not isinstance(value, str):
            raise ProjectKnowledgeIntegrityError(f"{field_name} is malformed")
        try:
            loaded = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ProjectKnowledgeIntegrityError(f"{field_name} is malformed") from exc
        if not isinstance(loaded, dict):
            raise ProjectKnowledgeIntegrityError(f"{field_name} is malformed")
        try:
            return _freeze_applicability(cast(dict[str, str], loaded))
        except ProjectKnowledgeError as exc:
            raise ProjectKnowledgeIntegrityError(f"{field_name} is malformed") from exc

    @staticmethod
    def _content_from_json(value: object) -> ContentRef | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ProjectKnowledgeIntegrityError("candidate content_ref is malformed")
        try:
            loaded = json.loads(value)
            if not isinstance(loaded, dict):
                raise TypeError
            return ContentRef(
                algorithm=cast(str, loaded["algorithm"]),
                digest=cast(str, loaded["digest"]),
                size_bytes=cast(int, loaded["size_bytes"]),
                media_type=cast(str, loaded["media_type"]),
            )
        except (ArtifactError, KeyError, TypeError, ValueError) as exc:
            raise ProjectKnowledgeIntegrityError(
                "candidate content_ref is malformed"
            ) from exc

    @staticmethod
    def _verify_digest(expected: str, observed: object, label: str) -> None:
        if (
            not isinstance(observed, str)
            or _SHA256_PATTERN.fullmatch(observed) is None
            or not hmac.compare_digest(expected, observed)
        ):
            raise ProjectKnowledgeIntegrityError(f"{label} failed integrity verification")
