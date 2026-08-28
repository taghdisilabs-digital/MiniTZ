"""Project-scoped Artifact, ContentRef, SourceRef, and derivation identity."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .project import (
    ProjectAccess,
    ProjectRef,
    ProjectScopeError,
    ProjectStore,
)
from .run import (
    ExecutionAttempt,
    RunAuthorityError,
    RunError,
    RunRef,
    RunService,
)
from .task import TaskInputRef, TaskRef


_ARTIFACT_ID_PATTERN = re.compile(r"art_[0-9a-f]{32}")
_DERIVATION_ID_PATTERN = re.compile(r"drv_[0-9a-f]{32}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_TYPE_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+")
_MEDIA_TYPE_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9!#$&^_.+-]{0,126}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}"
)
_ABSOLUTE_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_GIT_OBJECT_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_METADATA_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_SEMANTIC_METADATA_KEYS = {
    "media_encoding",
    "media_profile",
    "media_type",
    "schema_ref",
    "schema_version",
    "semantic_label",
    "semantic_version",
}


class ArtifactError(Exception):
    """Base class for Artifact identity failures."""


class ArtifactContractError(ArtifactError, ValueError):
    """An Artifact or derivation contract is malformed."""


class ArtifactContentError(ArtifactContractError):
    """Exact content or source identity is malformed or mismatched."""


class ArtifactScopeError(ArtifactError):
    """An Artifact operation crossed its authenticated Project scope."""


class ArtifactConflictError(ArtifactError):
    """An immutable Artifact revision conflicts with durable state."""


class ArtifactNotFoundError(ArtifactError):
    """An exact Artifact revision does not exist in the authorized Project."""


class ArtifactIntegrityError(ArtifactError):
    """Persisted Artifact or derivation evidence failed integrity verification."""


class ArtifactAuthorityError(ArtifactError):
    """Run or Task authority cannot publish the requested Artifact."""


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


def _validate_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ArtifactContractError(f"{field_name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ArtifactContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ArtifactContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return value


def _validate_type(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or _TYPE_PATTERN.fullmatch(value) is None
    ):
        raise ArtifactContractError(f"{field_name} must be an extensible namespaced string")
    return value


def _freeze_metadata(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ArtifactContractError("Artifact metadata must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise ArtifactContractError("Artifact metadata exceeds 64 entries")
    for key, item in copied.items():
        if not isinstance(key, str) or _METADATA_KEY_PATTERN.fullmatch(key) is None:
            raise ArtifactContractError("Artifact metadata key is malformed")
        if key not in _SEMANTIC_METADATA_KEYS:
            raise ArtifactContentError(
                "Artifact metadata accepts only explicit semantic media or schema fields"
            )
        if not isinstance(item, str) or len(item) > 2048:
            raise ArtifactContractError("Artifact metadata value is malformed or unbounded")
    return MappingProxyType(copied)


@dataclass(frozen=True, order=True)
class ContentRef:
    """Exact immutable content identity, independent of logical ownership and location."""

    algorithm: str
    digest: str
    size_bytes: int
    media_type: str = field(compare=False)

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ArtifactContentError("ContentRef algorithm must be sha256")
        if not isinstance(self.digest, str) or _SHA256_PATTERN.fullmatch(self.digest) is None:
            raise ArtifactContentError("ContentRef digest must be 64 lowercase hexadecimal characters")
        if (
            not isinstance(self.size_bytes, int)
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 0
        ):
            raise ArtifactContentError("ContentRef size must be a non-negative integer")
        if (
            not isinstance(self.media_type, str)
            or len(self.media_type) > 255
            or _MEDIA_TYPE_PATTERN.fullmatch(self.media_type) is None
        ):
            raise ArtifactContentError("ContentRef media type is malformed")

    @property
    def value(self) -> str:
        return f"content://sha256/{self.digest}?size={self.size_bytes}"

    @classmethod
    def from_bytes(cls, payload: bytes, *, media_type: str) -> "ContentRef":
        if not isinstance(payload, bytes):
            raise ArtifactContentError("ContentRef payload must be immutable bytes")
        return cls(
            algorithm="sha256",
            digest=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            media_type=media_type,
        )

    def verify(self, payload: bytes) -> None:
        observed = ContentRef.from_bytes(payload, media_type=self.media_type)
        if observed != self:
            raise ArtifactContentError("ContentRef digest or size does not match bytes")


def _canonical_content_refs(values: Sequence[ContentRef]) -> tuple[ContentRef, ...]:
    canonical: dict[tuple[str, str, int], ContentRef] = {}
    for item in values:
        identity = (item.algorithm, item.digest, item.size_bytes)
        existing = canonical.get(identity)
        if existing is not None and existing.media_type != item.media_type:
            raise ArtifactContentError(
                "One content identity cannot carry conflicting media annotations"
            )
        canonical[identity] = item
    return tuple(canonical[identity] for identity in sorted(canonical))


@dataclass(frozen=True, order=True)
class ArtifactRef:
    """Exact logical identity of one immutable Project-scoped Artifact revision."""

    project_ref: ProjectRef
    artifact_id: str
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.artifact_id, str)
            or _ARTIFACT_ID_PATTERN.fullmatch(self.artifact_id) is None
        ):
            raise ArtifactContractError("Artifact identity is malformed")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 1
        ):
            raise ArtifactContractError("Artifact revision must be a positive integer")

    @property
    def value(self) -> str:
        return (
            f"artifact://{self.project_ref.value}/{self.artifact_id}"
            f"/{self.revision}"
        )


@dataclass(frozen=True, order=True)
class SourceRef:
    """Exact Project-scoped source identity without physical-storage authority."""

    project_ref: ProjectRef
    source_kind: str
    locator: str
    exact_revision: str | None
    content_ref: ContentRef | None
    retrieved_at: str | None
    canonical_digest: str = field(init=False, compare=True)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        _validate_type(self.source_kind, "source_kind")
        if (
            not isinstance(self.locator, str)
            or len(self.locator) > 1056
            or _ABSOLUTE_REF_PATTERN.fullmatch(self.locator) is None
        ):
            raise ArtifactContentError("SourceRef locator must be a bounded absolute reference")
        if self.exact_revision is not None and (
            not isinstance(self.exact_revision, str)
            or not self.exact_revision.strip()
            or len(self.exact_revision) > 1024
        ):
            raise ArtifactContentError("SourceRef exact revision is malformed")
        if self.content_ref is not None and not isinstance(self.content_ref, ContentRef):
            raise ArtifactContentError("SourceRef content_ref must be ContentRef")
        if self.retrieved_at is not None:
            _validate_timestamp(self.retrieved_at, "retrieved_at")
        if (
            self.exact_revision is None
            and self.content_ref is None
            and self.retrieved_at is None
        ):
            raise ArtifactContentError(
                "SourceRef must include an exact revision, content identity, or retrieval evidence"
            )
        if self.source_kind == "git.repository":
            matched = re.fullmatch(
                r"commit:([0-9a-f]{40}|[0-9a-f]{64});tree:([0-9a-f]{40}|[0-9a-f]{64})",
                "" if self.exact_revision is None else self.exact_revision,
            )
            if (
                matched is None
                or self.content_ref is not None
                or self.retrieved_at is not None
            ):
                raise ArtifactContentError(
                    "Git SourceRef requires exact commit and tree objects"
                )
        elif self.source_kind == "file.content" and (
            self.content_ref is None
            or self.exact_revision is not None
            or self.retrieved_at is not None
        ):
            raise ArtifactContentError("File SourceRef requires exact content identity")
        elif self.source_kind == "database.revision" and self.exact_revision is None:
            raise ArtifactContentError("Database SourceRef requires exact source revision")
        elif self.source_kind == "remote.object" and self.retrieved_at is None:
            raise ArtifactContentError(
                "Remote object SourceRef requires retrieval timestamp evidence"
            )
        object.__setattr__(self, "canonical_digest", self._digest())

    @property
    def value(self) -> str:
        return f"source://{self.project_ref.value}/sha256/{self.canonical_digest}"

    def _digest(self) -> str:
        return _sha256(
            {
                "content_ref": _content_payload(self.content_ref),
                "exact_revision": self.exact_revision,
                "locator": self.locator,
                "project_id": self.project_ref.value,
                "retrieved_at": self.retrieved_at,
                "source_kind": self.source_kind,
            }
        )

    @classmethod
    def git(
        cls,
        project_ref: ProjectRef,
        *,
        repository: str,
        commit: str,
        tree: str,
    ) -> "SourceRef":
        if (
            not isinstance(commit, str)
            or _GIT_OBJECT_PATTERN.fullmatch(commit) is None
            or not isinstance(tree, str)
            or _GIT_OBJECT_PATTERN.fullmatch(tree) is None
        ):
            raise ArtifactContentError("Git SourceRef requires exact commit and tree objects")
        return cls(
            project_ref=project_ref,
            source_kind="git.repository",
            locator=repository,
            exact_revision=f"commit:{commit};tree:{tree}",
            content_ref=None,
            retrieved_at=None,
        )

    @classmethod
    def file(
        cls,
        project_ref: ProjectRef,
        *,
        locator: str,
        content_ref: ContentRef,
    ) -> "SourceRef":
        if not isinstance(content_ref, ContentRef):
            raise ArtifactContentError("File SourceRef requires exact content identity")
        return cls(
            project_ref=project_ref,
            source_kind="file.content",
            locator=locator,
            exact_revision=None,
            content_ref=content_ref,
            retrieved_at=None,
        )

    @classmethod
    def database(
        cls,
        project_ref: ProjectRef,
        *,
        locator: str,
        revision: str,
    ) -> "SourceRef":
        return cls(
            project_ref=project_ref,
            source_kind="database.revision",
            locator=locator,
            exact_revision=revision,
            content_ref=None,
            retrieved_at=None,
        )

    @classmethod
    def remote_object(
        cls,
        project_ref: ProjectRef,
        *,
        locator: str,
        retrieved_at: str,
        content_ref: ContentRef | None = None,
        revision: str | None = None,
    ) -> "SourceRef":
        _validate_timestamp(retrieved_at, "retrieved_at")
        return cls(
            project_ref=project_ref,
            source_kind="remote.object",
            locator=locator,
            exact_revision=revision,
            content_ref=content_ref,
            retrieved_at=retrieved_at,
        )


def _content_payload(content_ref: ContentRef | None) -> dict[str, object] | None:
    if content_ref is None:
        return None
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _source_payload(source_ref: SourceRef) -> dict[str, object]:
    return {
        "canonical_digest": source_ref.canonical_digest,
        "content_ref": _content_payload(source_ref.content_ref),
        "exact_revision": source_ref.exact_revision,
        "locator": source_ref.locator,
        "project_ref": source_ref.project_ref.value,
        "retrieved_at": source_ref.retrieved_at,
        "source_kind": source_ref.source_kind,
    }


@dataclass(frozen=True)
class Artifact:
    """Immutable logical Artifact revision with exact content and provenance."""

    artifact_ref: ArtifactRef
    role: str
    content_ref: ContentRef | None
    source_refs: tuple[SourceRef, ...]
    source_artifact_refs: tuple[ArtifactRef, ...]
    source_content_refs: tuple[ContentRef, ...]
    derivation_type: str | None
    producer_run_ref: RunRef | None
    producer_attempt_id: str | None
    producer_fence: int | None
    metadata: Mapping[str, str]
    created_at: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")
        _validate_type(self.role, "role")
        if self.content_ref is not None and not isinstance(self.content_ref, ContentRef):
            raise ArtifactContentError("Artifact content_ref must be ContentRef")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(item, SourceRef) for item in self.source_refs
        ):
            raise ArtifactContentError("Artifact source_refs must contain SourceRef")
        if not isinstance(self.source_artifact_refs, tuple) or not all(
            isinstance(item, ArtifactRef) for item in self.source_artifact_refs
        ):
            raise ArtifactContentError(
                "Artifact source_artifact_refs must contain ArtifactRef"
            )
        if not isinstance(self.source_content_refs, tuple) or not all(
            isinstance(item, ContentRef) for item in self.source_content_refs
        ):
            raise ArtifactContentError(
                "Artifact source_content_refs must contain ContentRef"
            )
        sources = tuple(
            sorted(set(self.source_refs), key=lambda item: item.canonical_digest)
        )
        source_artifacts = tuple(
            sorted(
                set(self.source_artifact_refs),
                key=lambda item: (item.artifact_id, item.revision),
            )
        )
        source_contents = _canonical_content_refs(self.source_content_refs)
        if len(sources) > 128 or len(source_artifacts) > 128 or len(source_contents) > 128:
            raise ArtifactContractError("Artifact provenance collection is unbounded")
        for source in sources:
            if source.project_ref != self.project_ref:
                raise ArtifactScopeError("Artifact Project scope mismatch")
        for source_artifact in source_artifacts:
            if source_artifact.project_ref != self.project_ref:
                raise ArtifactScopeError("Artifact Project scope mismatch")
        object.__setattr__(self, "source_refs", sources)
        object.__setattr__(self, "source_artifact_refs", source_artifacts)
        object.__setattr__(self, "source_content_refs", source_contents)
        has_provenance = bool(
            sources
            or source_artifacts
            or source_contents
            or self.producer_run_ref is not None
        )
        if has_provenance:
            if self.derivation_type is None:
                raise ArtifactContractError("Artifact provenance requires derivation_type")
            _validate_type(self.derivation_type, "derivation_type")
        elif self.derivation_type is not None:
            raise ArtifactContractError("Artifact without provenance cannot claim derivation")
        producer_values = (
            self.producer_run_ref,
            self.producer_attempt_id,
            self.producer_fence,
        )
        if any(value is not None for value in producer_values) and not all(
            value is not None for value in producer_values
        ):
            raise ArtifactContractError("Artifact producer Run authority is incomplete")
        if self.producer_run_ref is not None:
            if not isinstance(self.producer_run_ref, RunRef):
                raise ArtifactContractError("producer_run_ref must be RunRef")
            if self.producer_run_ref.project_ref != self.project_ref:
                raise ArtifactScopeError("Artifact Project scope mismatch")
            if (
                not isinstance(self.producer_attempt_id, str)
                or re.fullmatch(r"att_[0-9a-f]{32}", self.producer_attempt_id) is None
                or not isinstance(self.producer_fence, int)
                or isinstance(self.producer_fence, bool)
                or self.producer_fence < 1
            ):
                raise ArtifactContractError("Artifact producer attempt or fence is malformed")
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(self, "semantic_digest", self._semantic_digest())
        object.__setattr__(self, "record_sha256", self._record_digest())

    @property
    def project_ref(self) -> ProjectRef:
        return self.artifact_ref.project_ref

    @property
    def artifact_id(self) -> str:
        return self.artifact_ref.artifact_id

    @property
    def revision(self) -> int:
        return self.artifact_ref.revision

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "content_ref": _content_payload(self.content_ref),
            "derivation_type": self.derivation_type,
            "metadata": dict(self.metadata),
            "producer_attempt_id": self.producer_attempt_id,
            "producer_fence": self.producer_fence,
            "producer_run_ref": (
                None if self.producer_run_ref is None else self.producer_run_ref.run_id
            ),
            "project_ref": self.project_ref.value,
            "role": self.role,
            "source_artifact_refs": [item.value for item in self.source_artifact_refs],
            "source_content_refs": [
                _content_payload(item) for item in self.source_content_refs
            ],
            "source_refs": [_source_payload(item) for item in self.source_refs],
        }

    def _semantic_digest(self) -> str:
        return _sha256(self._semantic_payload())

    def _record_digest(self) -> str:
        return _sha256(
            {
                "artifact_id": self.artifact_id,
                "created_at": self.created_at,
                "project_id": self.project_ref.value,
                "revision": self.revision,
                "semantic_digest": self.semantic_digest,
            }
        )


@dataclass(frozen=True)
class ArtifactDerivation:
    """Immutable generic provenance relationship for one Artifact revision."""

    derivation_id: str
    output_ref: ArtifactRef
    relationship: str
    source_refs: tuple[SourceRef, ...]
    source_artifact_refs: tuple[ArtifactRef, ...]
    source_content_refs: tuple[ContentRef, ...]
    producer_run_ref: RunRef | None
    producer_attempt_id: str | None
    producer_fence: int | None
    created_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.derivation_id, str)
            or _DERIVATION_ID_PATTERN.fullmatch(self.derivation_id) is None
        ):
            raise ArtifactContractError("ArtifactDerivation identity is malformed")
        if not isinstance(self.output_ref, ArtifactRef):
            raise TypeError("output_ref must be ArtifactRef")
        _validate_type(self.relationship, "relationship")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(item, SourceRef) for item in self.source_refs
        ):
            raise ArtifactContentError(
                "ArtifactDerivation source_refs must contain SourceRef"
            )
        if not isinstance(self.source_artifact_refs, tuple) or not all(
            isinstance(item, ArtifactRef) for item in self.source_artifact_refs
        ):
            raise ArtifactContentError(
                "ArtifactDerivation source_artifact_refs must contain ArtifactRef"
            )
        if not isinstance(self.source_content_refs, tuple) or not all(
            isinstance(item, ContentRef) for item in self.source_content_refs
        ):
            raise ArtifactContentError(
                "ArtifactDerivation source_content_refs must contain ContentRef"
            )
        sources = tuple(
            sorted(set(self.source_refs), key=lambda item: item.canonical_digest)
        )
        source_artifacts = tuple(
            sorted(
                set(self.source_artifact_refs),
                key=lambda item: (item.artifact_id, item.revision),
            )
        )
        source_contents = _canonical_content_refs(self.source_content_refs)
        if (
            len(sources) > 128
            or len(source_artifacts) > 128
            or len(source_contents) > 128
        ):
            raise ArtifactContractError(
                "ArtifactDerivation provenance collection is unbounded"
            )
        object.__setattr__(self, "source_refs", sources)
        object.__setattr__(self, "source_artifact_refs", source_artifacts)
        object.__setattr__(self, "source_content_refs", source_contents)
        if any(source.project_ref != self.output_ref.project_ref for source in self.source_refs):
            raise ArtifactScopeError("Artifact Project scope mismatch")
        if any(
            source.project_ref != self.output_ref.project_ref
            for source in self.source_artifact_refs
        ):
            raise ArtifactScopeError("Artifact Project scope mismatch")
        producer_values = (
            self.producer_run_ref,
            self.producer_attempt_id,
            self.producer_fence,
        )
        if any(value is not None for value in producer_values) and not all(
            value is not None for value in producer_values
        ):
            raise ArtifactContractError(
                "ArtifactDerivation producer Run authority is incomplete"
            )
        if self.producer_run_ref is not None:
            if not isinstance(self.producer_run_ref, RunRef):
                raise ArtifactContractError("producer_run_ref must be RunRef")
            if self.producer_run_ref.project_ref != self.output_ref.project_ref:
                raise ArtifactScopeError("Artifact Project scope mismatch")
            if (
                not isinstance(self.producer_attempt_id, str)
                or re.fullmatch(r"att_[0-9a-f]{32}", self.producer_attempt_id) is None
                or not isinstance(self.producer_fence, int)
                or isinstance(self.producer_fence, bool)
                or self.producer_fence < 1
            ):
                raise ArtifactContractError(
                    "ArtifactDerivation producer attempt or fence is malformed"
                )
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(self, "record_sha256", self._record_digest())

    def _record_digest(self) -> str:
        return _sha256(
            {
                "created_at": self.created_at,
                "derivation_id": self.derivation_id,
                "output_ref": self.output_ref.value,
                "producer_attempt_id": self.producer_attempt_id,
                "producer_fence": self.producer_fence,
                "producer_run_ref": (
                    None if self.producer_run_ref is None else self.producer_run_ref.run_id
                ),
                "relationship": self.relationship,
                "source_artifact_refs": [item.value for item in self.source_artifact_refs],
                "source_content_refs": [
                    _content_payload(item) for item in self.source_content_refs
                ],
                "source_refs": [_source_payload(item) for item in self.source_refs],
            }
        )


class ArtifactService:
    """Durable Project-scoped Artifact revision and provenance service."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.runs = RunService(self.database_path)
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
                CREATE UNIQUE INDEX IF NOT EXISTS execution_attempts_exact_artifact_authority
                    ON execution_attempts(project_id, run_id, attempt_id, fence);

                CREATE TABLE IF NOT EXISTS artifact_revisions (
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content_json TEXT,
                    source_refs_json TEXT NOT NULL,
                    source_artifact_refs_json TEXT NOT NULL,
                    source_content_refs_json TEXT NOT NULL,
                    derivation_type TEXT,
                    producer_run_id TEXT,
                    producer_attempt_id TEXT,
                    producer_fence INTEGER,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, artifact_id, revision),
                    UNIQUE (project_id, artifact_id, revision, record_sha256),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, producer_run_id,
                        producer_attempt_id, producer_fence
                    ) REFERENCES execution_attempts(
                        project_id, run_id, attempt_id, fence
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS artifact_heads (
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    current_revision INTEGER NOT NULL,
                    current_record_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, artifact_id),
                    FOREIGN KEY (
                        project_id, artifact_id,
                        current_revision, current_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS artifact_source_artifact_bindings (
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    source_artifact_id TEXT NOT NULL,
                    source_revision INTEGER NOT NULL,
                    source_record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        project_id, artifact_id, revision,
                        source_artifact_id, source_revision
                    ),
                    FOREIGN KEY (project_id, artifact_id, revision)
                        REFERENCES artifact_revisions(project_id, artifact_id, revision)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, source_artifact_id,
                        source_revision, source_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    )
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS artifact_derivations (
                    project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    derivation_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    source_refs_json TEXT NOT NULL,
                    source_artifact_refs_json TEXT NOT NULL,
                    source_content_refs_json TEXT NOT NULL,
                    producer_run_id TEXT,
                    producer_attempt_id TEXT,
                    producer_fence INTEGER,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, artifact_id, revision, derivation_id),
                    FOREIGN KEY (project_id, artifact_id, revision)
                        REFERENCES artifact_revisions(project_id, artifact_id, revision)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, producer_run_id,
                        producer_attempt_id, producer_fence
                    ) REFERENCES execution_attempts(
                        project_id, run_id, attempt_id, fence
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS artifact_task_input_bindings (
                    project_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    input_kind TEXT NOT NULL,
                    identity_ref TEXT NOT NULL,
                    identity_digest TEXT NOT NULL,
                    artifact_id TEXT,
                    artifact_revision INTEGER,
                    artifact_record_sha256 TEXT,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, record_id),
                    UNIQUE (project_id, input_kind, identity_ref, identity_digest),
                    FOREIGN KEY (project_id, record_id, identity_digest)
                        REFERENCES project_scoped_records(
                            project_id, record_id, content_sha256
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    )
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS artifact_revisions_no_update
                BEFORE UPDATE ON artifact_revisions
                BEGIN SELECT RAISE(ABORT, 'Artifact revisions are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_revisions_no_delete
                BEFORE DELETE ON artifact_revisions
                BEGIN SELECT RAISE(ABORT, 'Artifact revisions cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_source_bindings_no_update
                BEFORE UPDATE ON artifact_source_artifact_bindings
                BEGIN SELECT RAISE(ABORT, 'Artifact source bindings are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_source_bindings_no_delete
                BEFORE DELETE ON artifact_source_artifact_bindings
                BEGIN SELECT RAISE(ABORT, 'Artifact source bindings cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_derivations_no_update
                BEFORE UPDATE ON artifact_derivations
                BEGIN SELECT RAISE(ABORT, 'Artifact derivations are immutable'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_derivations_no_delete
                BEFORE DELETE ON artifact_derivations
                BEGIN SELECT RAISE(ABORT, 'Artifact derivations cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_task_inputs_no_update
                BEFORE UPDATE ON artifact_task_input_bindings
                BEGIN SELECT RAISE(ABORT, 'Artifact Task input bridge is immutable'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_task_inputs_no_delete
                BEFORE DELETE ON artifact_task_input_bindings
                BEGIN SELECT RAISE(ABORT, 'Artifact Task input bridge cannot be deleted'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_heads_monotonic_update
                BEFORE UPDATE ON artifact_heads
                WHEN
                    NEW.project_id != OLD.project_id
                    OR NEW.artifact_id != OLD.artifact_id
                    OR NEW.current_revision != OLD.current_revision + 1
                    OR NEW.updated_at < OLD.updated_at
                BEGIN SELECT RAISE(ABORT, 'Artifact head must advance monotonically'); END;

                CREATE TRIGGER IF NOT EXISTS artifact_heads_no_delete
                BEFORE DELETE ON artifact_heads
                BEGIN SELECT RAISE(ABORT, 'Artifact head cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def create_artifact(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        role: str,
        content_ref: ContentRef | None,
        source_refs: Sequence[SourceRef],
        source_artifact_refs: Sequence[ArtifactRef],
        source_content_refs: Sequence[ContentRef],
        derivation_type: str,
        metadata: Mapping[str, str],
    ) -> Artifact:
        self._validate_request_scope(
            requesting_access,
            project_ref,
            source_refs,
            source_artifact_refs,
            source_content_refs,
        )
        return self._create_artifact(
            requesting_access,
            ArtifactRef(project_ref, f"art_{uuid4().hex}", 1),
            role=role,
            content_ref=content_ref,
            source_refs=source_refs,
            source_artifact_refs=source_artifact_refs,
            source_content_refs=source_content_refs,
            derivation_type=derivation_type,
            metadata=metadata,
            producer_attempt=None,
            expected_task_ref=None,
            expected_task_digest=None,
            expected_prior=None,
        )

    def create_revision(
        self,
        requesting_access: ProjectAccess,
        *,
        prior_ref: ArtifactRef,
        role: str,
        content_ref: ContentRef | None,
        source_refs: Sequence[SourceRef],
        source_artifact_refs: Sequence[ArtifactRef],
        source_content_refs: Sequence[ContentRef],
        derivation_type: str,
        metadata: Mapping[str, str],
    ) -> Artifact:
        prior = self.get_artifact(requesting_access, prior_ref)
        self._validate_request_scope(
            requesting_access,
            prior.project_ref,
            source_refs,
            source_artifact_refs,
            source_content_refs,
        )
        return self._create_artifact(
            requesting_access,
            ArtifactRef(prior.project_ref, prior.artifact_id, prior.revision + 1),
            role=role,
            content_ref=content_ref,
            source_refs=source_refs,
            source_artifact_refs=source_artifact_refs,
            source_content_refs=source_content_refs,
            derivation_type=derivation_type,
            metadata=metadata,
            producer_attempt=None,
            expected_task_ref=None,
            expected_task_digest=None,
            expected_prior=prior,
        )

    def publish_from_run(
        self,
        requesting_access: ProjectAccess,
        *,
        producer_attempt: ExecutionAttempt,
        expected_task_ref: TaskRef,
        expected_task_digest: str,
        role: str,
        content_ref: ContentRef | None,
        source_refs: Sequence[SourceRef],
        source_artifact_refs: Sequence[ArtifactRef],
        source_content_refs: Sequence[ContentRef],
        derivation_type: str,
        metadata: Mapping[str, str],
    ) -> Artifact:
        if not isinstance(producer_attempt, ExecutionAttempt):
            raise ArtifactAuthorityError("ExecutionAttempt is required for Run output")
        project_ref = producer_attempt.run_ref.project_ref
        self._validate_request_scope(
            requesting_access,
            project_ref,
            source_refs,
            source_artifact_refs,
            source_content_refs,
        )
        return self._create_artifact(
            requesting_access,
            ArtifactRef(project_ref, f"art_{uuid4().hex}", 1),
            role=role,
            content_ref=content_ref,
            source_refs=source_refs,
            source_artifact_refs=source_artifact_refs,
            source_content_refs=source_content_refs,
            derivation_type=derivation_type,
            metadata=metadata,
            producer_attempt=producer_attempt,
            expected_task_ref=expected_task_ref,
            expected_task_digest=expected_task_digest,
            expected_prior=None,
        )

    def get_artifact(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> Artifact:
        self._authorize(requesting_access, artifact_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            artifact = self._fetch_artifact(connection, artifact_ref)
            connection.commit()
            return artifact
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_derivations(
        self,
        requesting_access: ProjectAccess,
        artifact_ref: ArtifactRef,
    ) -> tuple[ArtifactDerivation, ...]:
        self._authorize(requesting_access, artifact_ref.project_ref)
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            artifact = self._fetch_artifact(connection, artifact_ref)
            derivations = self._fetch_derivations(connection, artifact)
            connection.commit()
            return derivations
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_task_input_ref(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        identity: ArtifactRef | SourceRef | ContentRef,
    ) -> TaskInputRef:
        self._authorize(requesting_access, project_ref)
        artifact_id: str | None = None
        artifact_revision: int | None = None
        artifact_record_sha256: str | None = None
        if isinstance(identity, ArtifactRef):
            if identity.project_ref != project_ref:
                raise ArtifactScopeError("Artifact Project scope mismatch")
            artifact = self.get_artifact(requesting_access, identity)
            identity_ref = identity.value
            identity_digest = (
                artifact.semantic_digest
                if artifact.content_ref is None
                else artifact.content_ref.digest
            )
            input_kind = "artifact"
            artifact_id = identity.artifact_id
            artifact_revision = identity.revision
            artifact_record_sha256 = artifact.record_sha256
        elif isinstance(identity, SourceRef):
            if identity.project_ref != project_ref:
                raise ArtifactScopeError("Artifact Project scope mismatch")
            identity_ref = identity.value
            identity_digest = (
                identity.canonical_digest
                if identity.content_ref is None
                else identity.content_ref.digest
            )
            input_kind = "source"
        elif isinstance(identity, ContentRef):
            identity_ref = identity.value
            identity_digest = identity.digest
            input_kind = "content"
        else:
            raise ArtifactContentError("Active Task identity must be ArtifactRef, SourceRef, or ContentRef")
        task_input = TaskInputRef(
            project_ref=project_ref,
            input_kind=input_kind,
            source_ref=identity_ref,
            content_sha256=identity_digest,
        )
        record_sha256 = _sha256(
            {
                "artifact_id": artifact_id,
                "artifact_record_sha256": artifact_record_sha256,
                "artifact_revision": artifact_revision,
                "identity_digest": identity_digest,
                "identity_ref": identity_ref,
                "input_kind": input_kind,
                "project_id": project_ref.value,
                "record_id": task_input.record_id,
            }
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO project_scoped_records (
                    project_id, record_id, content_sha256
                ) VALUES (?, ?, ?)
                """,
                (project_ref.value, task_input.record_id, identity_digest),
            )
            existing = connection.execute(
                """
                SELECT * FROM artifact_task_input_bindings
                WHERE project_id = ? AND record_id = ?
                """,
                (project_ref.value, task_input.record_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO artifact_task_input_bindings (
                        project_id, record_id, input_kind, identity_ref,
                        identity_digest, artifact_id, artifact_revision,
                        artifact_record_sha256, record_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_ref.value,
                        task_input.record_id,
                        input_kind,
                        identity_ref,
                        identity_digest,
                        artifact_id,
                        artifact_revision,
                        artifact_record_sha256,
                        record_sha256,
                    ),
                )
            elif (
                existing["identity_ref"] != identity_ref
                or existing["identity_digest"] != identity_digest
                or existing["artifact_record_sha256"] != artifact_record_sha256
                or existing["record_sha256"] != record_sha256
            ):
                raise ArtifactConflictError("Artifact Task input identity conflicts")
            connection.commit()
            return task_input
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_artifact(
        self,
        access: ProjectAccess,
        artifact_ref: ArtifactRef,
        *,
        role: str,
        content_ref: ContentRef | None,
        source_refs: Sequence[SourceRef],
        source_artifact_refs: Sequence[ArtifactRef],
        source_content_refs: Sequence[ContentRef],
        derivation_type: str,
        metadata: Mapping[str, str],
        producer_attempt: ExecutionAttempt | None,
        expected_task_ref: TaskRef | None,
        expected_task_digest: str | None,
        expected_prior: Artifact | None,
    ) -> Artifact:
        if content_ref is not None and not isinstance(content_ref, ContentRef):
            raise ArtifactContentError("Artifact content_ref must be ContentRef")
        producer_run_ref = None if producer_attempt is None else producer_attempt.run_ref
        producer_attempt_id = None if producer_attempt is None else producer_attempt.attempt_id
        producer_fence = None if producer_attempt is None else producer_attempt.fence
        has_provenance = bool(
            source_refs
            or source_artifact_refs
            or source_content_refs
            or producer_attempt is not None
        )
        candidate_derivation_type = derivation_type if has_provenance else None
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now = self._database_now(connection)
            if producer_attempt is not None:
                if (
                    not isinstance(expected_task_ref, TaskRef)
                    or not isinstance(expected_task_digest, str)
                    or _SHA256_PATTERN.fullmatch(expected_task_digest) is None
                ):
                    raise ArtifactAuthorityError("Exact expected Task identity is required")
                try:
                    run = self.runs.assert_current_run_authority_in_transaction(
                        connection,
                        access,
                        producer_attempt,
                    )
                except (RunAuthorityError, RunError) as exc:
                    raise ArtifactAuthorityError("Run does not hold current Artifact authority") from exc
                if (
                    run.task_ref != expected_task_ref
                    or not hmac.compare_digest(run.task_digest, expected_task_digest)
                ):
                    raise ArtifactAuthorityError("Run Task revision or digest does not match")
            self._verify_source_artifacts_in_transaction(
                connection,
                artifact_ref.project_ref,
                source_artifact_refs,
            )
            artifact = Artifact(
                artifact_ref=artifact_ref,
                role=role,
                content_ref=content_ref,
                source_refs=tuple(source_refs),
                source_artifact_refs=tuple(source_artifact_refs),
                source_content_refs=tuple(source_content_refs),
                derivation_type=candidate_derivation_type,
                producer_run_ref=producer_run_ref,
                producer_attempt_id=producer_attempt_id,
                producer_fence=producer_fence,
                metadata=metadata,
                created_at=now,
            )
            if expected_prior is not None:
                head = self._fetch_head(connection, expected_prior.artifact_ref)
                if head["current_revision"] != expected_prior.revision:
                    raise ArtifactConflictError("Artifact revision predecessor is stale")
                persisted_prior = self._fetch_artifact(connection, expected_prior.artifact_ref)
                if persisted_prior != expected_prior:
                    raise ArtifactConflictError("Artifact revision predecessor changed")
                if artifact.semantic_digest == expected_prior.semantic_digest:
                    raise ArtifactConflictError("New Artifact revision requires a material change")
            self._insert_artifact(connection, artifact)
            self._insert_source_bindings(connection, artifact)
            self._insert_derivation(connection, artifact)
            if expected_prior is None:
                self._insert_initial_head(connection, artifact)
            else:
                self._advance_head(connection, expected_prior, artifact)
            connection.commit()
            return artifact
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _validate_request_scope(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        source_refs: Sequence[SourceRef],
        source_artifact_refs: Sequence[ArtifactRef],
        source_content_refs: Sequence[ContentRef],
    ) -> None:
        self._authorize(access, project_ref)
        for values, expected_type in (
            (source_refs, SourceRef),
            (source_artifact_refs, ArtifactRef),
            (source_content_refs, ContentRef),
        ):
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
                raise ArtifactContentError("Artifact provenance must be a sequence")
            if not all(isinstance(value, expected_type) for value in values):
                raise ArtifactContentError("Artifact provenance contains an invalid identity")
        if any(source.project_ref != project_ref for source in source_refs):
            raise ArtifactScopeError("Artifact Project scope mismatch")
        if any(source.project_ref != project_ref for source in source_artifact_refs):
            raise ArtifactScopeError("Artifact Project scope mismatch")
        for source in source_artifact_refs:
            self.get_artifact(access, source)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        if not isinstance(project_ref, ProjectRef):
            raise TypeError("ProjectRef is required")
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise ArtifactScopeError("Artifact Project scope mismatch") from exc

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute(
            "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
        ).fetchone()[0]
        if not isinstance(value, str):
            raise ArtifactIntegrityError("Durable database time is unavailable")
        return _validate_timestamp(value, "database_now")

    @staticmethod
    def _verify_source_artifacts_in_transaction(
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
        source_refs: Sequence[ArtifactRef],
    ) -> None:
        for source in source_refs:
            row = connection.execute(
                """
                SELECT 1 FROM artifact_revisions
                WHERE project_id = ? AND artifact_id = ? AND revision = ?
                """,
                (project_ref.value, source.artifact_id, source.revision),
            ).fetchone()
            if row is None:
                raise ArtifactContentError("Exact source Artifact does not exist")

    @staticmethod
    def _insert_artifact(connection: sqlite3.Connection, artifact: Artifact) -> None:
        connection.execute(
            """
            INSERT INTO artifact_revisions (
                project_id, artifact_id, revision, role, content_json,
                source_refs_json, source_artifact_refs_json,
                source_content_refs_json, derivation_type,
                producer_run_id, producer_attempt_id, producer_fence,
                metadata_json, created_at, semantic_digest, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.project_ref.value,
                artifact.artifact_id,
                artifact.revision,
                artifact.role,
                None if artifact.content_ref is None else _json(_content_payload(artifact.content_ref)),
                _json([_source_payload(item) for item in artifact.source_refs]),
                _json([item.value for item in artifact.source_artifact_refs]),
                _json([_content_payload(item) for item in artifact.source_content_refs]),
                artifact.derivation_type,
                None if artifact.producer_run_ref is None else artifact.producer_run_ref.run_id,
                artifact.producer_attempt_id,
                artifact.producer_fence,
                _json(dict(artifact.metadata)),
                artifact.created_at,
                artifact.semantic_digest,
                artifact.record_sha256,
            ),
        )

    @staticmethod
    def _insert_source_bindings(connection: sqlite3.Connection, artifact: Artifact) -> None:
        bindings: list[tuple[str, str, int, str, int, str]] = []
        for source in artifact.source_artifact_refs:
            row = connection.execute(
                """
                SELECT record_sha256 FROM artifact_revisions
                WHERE project_id = ? AND artifact_id = ? AND revision = ?
                """,
                (
                    artifact.project_ref.value,
                    source.artifact_id,
                    source.revision,
                ),
            ).fetchone()
            if row is None or not isinstance(row["record_sha256"], str):
                raise ArtifactIntegrityError("Exact source Artifact record is missing")
            bindings.append(
                (
                    artifact.project_ref.value,
                    artifact.artifact_id,
                    artifact.revision,
                    source.artifact_id,
                    source.revision,
                    row["record_sha256"],
                )
            )
        connection.executemany(
            """
            INSERT INTO artifact_source_artifact_bindings (
                project_id, artifact_id, revision,
                source_artifact_id, source_revision, source_record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            bindings,
        )

    @staticmethod
    def _insert_derivation(connection: sqlite3.Connection, artifact: Artifact) -> None:
        if artifact.derivation_type is None:
            return
        derivation = ArtifactDerivation(
            derivation_id=f"drv_{uuid4().hex}",
            output_ref=artifact.artifact_ref,
            relationship=artifact.derivation_type,
            source_refs=artifact.source_refs,
            source_artifact_refs=artifact.source_artifact_refs,
            source_content_refs=artifact.source_content_refs,
            producer_run_ref=artifact.producer_run_ref,
            producer_attempt_id=artifact.producer_attempt_id,
            producer_fence=artifact.producer_fence,
            created_at=artifact.created_at,
        )
        connection.execute(
            """
            INSERT INTO artifact_derivations (
                project_id, artifact_id, revision, derivation_id, relationship,
                source_refs_json, source_artifact_refs_json,
                source_content_refs_json, producer_run_id,
                producer_attempt_id, producer_fence, created_at, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.project_ref.value,
                artifact.artifact_id,
                artifact.revision,
                derivation.derivation_id,
                derivation.relationship,
                _json([_source_payload(item) for item in derivation.source_refs]),
                _json([item.value for item in derivation.source_artifact_refs]),
                _json([_content_payload(item) for item in derivation.source_content_refs]),
                None if derivation.producer_run_ref is None else derivation.producer_run_ref.run_id,
                derivation.producer_attempt_id,
                derivation.producer_fence,
                derivation.created_at,
                derivation.record_sha256,
            ),
        )

    @classmethod
    def _insert_initial_head(cls, connection: sqlite3.Connection, artifact: Artifact) -> None:
        connection.execute(
            """
            INSERT INTO artifact_heads (
                project_id, artifact_id, current_revision,
                current_record_sha256, updated_at, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.project_ref.value,
                artifact.artifact_id,
                artifact.revision,
                artifact.record_sha256,
                artifact.created_at,
                cls._head_sha256(artifact),
            ),
        )

    @classmethod
    def _advance_head(
        cls,
        connection: sqlite3.Connection,
        prior: Artifact,
        current: Artifact,
    ) -> None:
        updated = connection.execute(
            """
            UPDATE artifact_heads
            SET current_revision = ?, current_record_sha256 = ?,
                updated_at = ?, record_sha256 = ?
            WHERE project_id = ? AND artifact_id = ?
              AND current_revision = ? AND current_record_sha256 = ?
            """,
            (
                current.revision,
                current.record_sha256,
                current.created_at,
                cls._head_sha256(current),
                prior.project_ref.value,
                prior.artifact_id,
                prior.revision,
                prior.record_sha256,
            ),
        )
        if updated.rowcount != 1:
            raise ArtifactConflictError("Artifact head changed concurrently")

    @staticmethod
    def _head_sha256(artifact: Artifact) -> str:
        return _sha256(
            {
                "artifact_id": artifact.artifact_id,
                "current_record_sha256": artifact.record_sha256,
                "current_revision": artifact.revision,
                "project_id": artifact.project_ref.value,
                "updated_at": artifact.created_at,
            }
        )

    def _fetch_head(
        self,
        connection: sqlite3.Connection,
        artifact_ref: ArtifactRef,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM artifact_heads WHERE project_id = ? AND artifact_id = ?",
            (artifact_ref.project_ref.value, artifact_ref.artifact_id),
        ).fetchone()
        if row is None:
            raise ArtifactIntegrityError("Artifact head is missing")
        return cast(sqlite3.Row, row)

    def _fetch_artifact(
        self,
        connection: sqlite3.Connection,
        artifact_ref: ArtifactRef,
    ) -> Artifact:
        if not connection.in_transaction:
            raise ArtifactIntegrityError("Artifact reads require one explicit durable snapshot")
        rows = connection.execute(
            """
            SELECT * FROM artifact_revisions
            WHERE project_id = ? AND artifact_id = ?
            ORDER BY revision
            """,
            (artifact_ref.project_ref.value, artifact_ref.artifact_id),
        ).fetchall()
        if not rows:
            raise ArtifactNotFoundError("Artifact revision not found")
        artifacts = tuple(self._artifact_from_row(row) for row in rows)
        if tuple(item.revision for item in artifacts) != tuple(range(1, len(artifacts) + 1)):
            raise ArtifactIntegrityError("Artifact revisions are not gap-free")
        head = self._fetch_head(connection, artifact_ref)
        latest = artifacts[-1]
        if (
            head["current_revision"] != latest.revision
            or head["current_record_sha256"] != latest.record_sha256
            or head["updated_at"] != latest.created_at
        ):
            raise ArtifactIntegrityError("Artifact history does not match durable head")
        self._verify_digest(
            self._head_sha256(latest),
            head["record_sha256"],
            "Artifact head",
        )
        selected = next(
            (item for item in artifacts if item.revision == artifact_ref.revision),
            None,
        )
        if selected is None:
            raise ArtifactNotFoundError("Artifact revision not found")
        binding_rows = connection.execute(
            """
            SELECT source_artifact_id, source_revision, source_record_sha256
            FROM artifact_source_artifact_bindings
            WHERE project_id = ? AND artifact_id = ? AND revision = ?
            """,
            (selected.project_ref.value, selected.artifact_id, selected.revision),
        ).fetchall()
        persisted_sources_list: list[ArtifactRef] = []
        for binding in binding_rows:
            source_ref = ArtifactRef(
                selected.project_ref,
                cast(str, binding["source_artifact_id"]),
                cast(int, binding["source_revision"]),
            )
            source_row = connection.execute(
                """
                SELECT * FROM artifact_revisions
                WHERE project_id = ? AND artifact_id = ? AND revision = ?
                """,
                (
                    source_ref.project_ref.value,
                    source_ref.artifact_id,
                    source_ref.revision,
                ),
            ).fetchone()
            if source_row is None:
                raise ArtifactIntegrityError("Exact source Artifact record is missing")
            source_artifact = self._artifact_from_row(cast(sqlite3.Row, source_row))
            self._verify_digest(
                source_artifact.record_sha256,
                binding["source_record_sha256"],
                "Artifact source binding",
            )
            persisted_sources_list.append(source_ref)
        persisted_sources = tuple(
            sorted(
                persisted_sources_list,
                key=lambda item: (item.artifact_id, item.revision),
            )
        )
        if persisted_sources != selected.source_artifact_refs:
            raise ArtifactIntegrityError("Artifact source bindings are inconsistent")
        derivations = self._fetch_derivations(connection, selected)
        if (selected.derivation_type is None) != (len(derivations) == 0):
            raise ArtifactIntegrityError("Artifact derivation evidence is inconsistent")
        if len(derivations) > 1:
            raise ArtifactIntegrityError("Artifact revision has conflicting derivations")
        return selected

    def _artifact_from_row(self, row: sqlite3.Row) -> Artifact:
        try:
            project_ref = ProjectRef(cast(str, row["project_id"]))
            artifact = Artifact(
                artifact_ref=ArtifactRef(
                    project_ref,
                    cast(str, row["artifact_id"]),
                    cast(int, row["revision"]),
                ),
                role=cast(str, row["role"]),
                content_ref=self._parse_optional_content(cast(str | None, row["content_json"])),
                source_refs=tuple(
                    self._parse_source(value)
                    for value in cast(list[dict[str, object]], json.loads(cast(str, row["source_refs_json"])))
                ),
                source_artifact_refs=tuple(
                    self._parse_artifact_ref(value)
                    for value in cast(list[str], json.loads(cast(str, row["source_artifact_refs_json"])))
                ),
                source_content_refs=tuple(
                    self._parse_content(value)
                    for value in cast(list[dict[str, object]], json.loads(cast(str, row["source_content_refs_json"])))
                ),
                derivation_type=cast(str | None, row["derivation_type"]),
                producer_run_ref=(
                    None
                    if row["producer_run_id"] is None
                    else RunRef(project_ref, cast(str, row["producer_run_id"]))
                ),
                producer_attempt_id=cast(str | None, row["producer_attempt_id"]),
                producer_fence=cast(int | None, row["producer_fence"]),
                metadata=cast(dict[str, str], json.loads(cast(str, row["metadata_json"]))),
                created_at=cast(str, row["created_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ArtifactError) as exc:
            raise ArtifactIntegrityError("Persisted Artifact revision is malformed") from exc
        self._verify_digest(
            artifact.semantic_digest,
            row["semantic_digest"],
            "Artifact semantic contract",
        )
        self._verify_digest(
            artifact.record_sha256,
            row["record_sha256"],
            "Artifact revision",
        )
        return artifact

    def _fetch_derivations(
        self,
        connection: sqlite3.Connection,
        artifact: Artifact,
    ) -> tuple[ArtifactDerivation, ...]:
        rows = connection.execute(
            """
            SELECT * FROM artifact_derivations
            WHERE project_id = ? AND artifact_id = ? AND revision = ?
            ORDER BY derivation_id
            """,
            (artifact.project_ref.value, artifact.artifact_id, artifact.revision),
        ).fetchall()
        derivations: list[ArtifactDerivation] = []
        for row in rows:
            try:
                derivation = ArtifactDerivation(
                    derivation_id=cast(str, row["derivation_id"]),
                    output_ref=artifact.artifact_ref,
                    relationship=cast(str, row["relationship"]),
                    source_refs=tuple(
                        self._parse_source(value)
                        for value in cast(list[dict[str, object]], json.loads(cast(str, row["source_refs_json"])))
                    ),
                    source_artifact_refs=tuple(
                        self._parse_artifact_ref(value)
                        for value in cast(list[str], json.loads(cast(str, row["source_artifact_refs_json"])))
                    ),
                    source_content_refs=tuple(
                        self._parse_content(value)
                        for value in cast(list[dict[str, object]], json.loads(cast(str, row["source_content_refs_json"])))
                    ),
                    producer_run_ref=(
                        None
                        if row["producer_run_id"] is None
                        else RunRef(artifact.project_ref, cast(str, row["producer_run_id"]))
                    ),
                    producer_attempt_id=cast(str | None, row["producer_attempt_id"]),
                    producer_fence=cast(int | None, row["producer_fence"]),
                    created_at=cast(str, row["created_at"]),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, ArtifactError) as exc:
                raise ArtifactIntegrityError("Persisted Artifact derivation is malformed") from exc
            if (
                derivation.relationship != artifact.derivation_type
                or derivation.source_refs != artifact.source_refs
                or derivation.source_artifact_refs != artifact.source_artifact_refs
                or derivation.source_content_refs != artifact.source_content_refs
                or derivation.producer_run_ref != artifact.producer_run_ref
                or derivation.producer_attempt_id != artifact.producer_attempt_id
                or derivation.producer_fence != artifact.producer_fence
            ):
                raise ArtifactIntegrityError("Artifact derivation does not match revision provenance")
            self._verify_digest(
                derivation.record_sha256,
                row["record_sha256"],
                "Artifact derivation",
            )
            derivations.append(derivation)
        return tuple(derivations)

    @staticmethod
    def _parse_content(value: Mapping[str, object]) -> ContentRef:
        return ContentRef(
            algorithm=cast(str, value["algorithm"]),
            digest=cast(str, value["digest"]),
            size_bytes=cast(int, value["size_bytes"]),
            media_type=cast(str, value["media_type"]),
        )

    @classmethod
    def _parse_optional_content(cls, value: str | None) -> ContentRef | None:
        if value is None:
            return None
        parsed = cast(dict[str, object], json.loads(value))
        return cls._parse_content(parsed)

    @classmethod
    def _parse_source(cls, value: Mapping[str, object]) -> SourceRef:
        content_raw = cast(dict[str, object] | None, value["content_ref"])
        source = SourceRef(
            project_ref=ProjectRef(cast(str, value["project_ref"])),
            source_kind=cast(str, value["source_kind"]),
            locator=cast(str, value["locator"]),
            exact_revision=cast(str | None, value["exact_revision"]),
            content_ref=None if content_raw is None else cls._parse_content(content_raw),
            retrieved_at=cast(str | None, value["retrieved_at"]),
        )
        persisted = value["canonical_digest"]
        if not isinstance(persisted, str) or not hmac.compare_digest(
            source.canonical_digest,
            persisted,
        ):
            raise ArtifactIntegrityError("SourceRef canonical digest is inconsistent")
        return source

    @staticmethod
    def _parse_artifact_ref(value: str) -> ArtifactRef:
        matched = re.fullmatch(
            r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)",
            value,
        )
        if matched is None:
            raise ArtifactIntegrityError("Persisted ArtifactRef is malformed")
        return ArtifactRef(ProjectRef(matched.group(1)), matched.group(2), int(matched.group(3)))

    @staticmethod
    def _verify_digest(expected: str, persisted: object, label: str) -> None:
        if (
            not isinstance(persisted, str)
            or _SHA256_PATTERN.fullmatch(persisted) is None
            or not hmac.compare_digest(expected, persisted)
        ):
            raise ArtifactIntegrityError(f"{label} failed integrity verification")
