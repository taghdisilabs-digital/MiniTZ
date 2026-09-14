"""Durable Project identity and isolation contracts for P0-02."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
from types import MappingProxyType
from typing import Mapping, cast
from uuid import uuid4


_NAMESPACE_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_PROJECT_REF_PATTERN = re.compile(r"prj_[0-9a-f]{32}")
_ACCESS_TOKEN_PATTERN = re.compile(r"paccess_[0-9a-f]{64}")
_RECORD_ID_PATTERN = re.compile(r"rec_[0-9a-f]{32}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_CONFIGURATION_REF_PATTERN = re.compile(r"config://sha256/[0-9a-f]{64}")
_METADATA_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_RESERVED_NAMESPACES = frozenset({"quarantine", "migration-quarantine"})


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ProjectError(Exception):
    """Base class for Project contract failures."""


class ProjectNamespaceError(ProjectError):
    """Project namespace is malformed or reserved."""


class ProjectConflictError(ProjectError):
    """A unique Project identity or namespace already exists."""


class ProjectCreationError(ProjectError):
    """Atomic Project creation failed and was rolled back."""


class ProjectIntegrityError(ProjectError):
    """Durable Project state is malformed or internally inconsistent."""


class ProjectNotFoundError(ProjectError):
    """The requested Project does not exist in the caller's scope."""


class ProjectScopeError(ProjectError):
    """A Project-scoped operation crossed an isolation boundary."""


class ProjectRetentionError(ProjectError):
    """Project deletion conflicts with the explicit retention contract."""


class ProjectConfigurationError(ProjectError):
    """A Project configuration reference is missing or malformed."""


def _require_timezone_aware_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ProjectIntegrityError(f"{field_name} must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProjectIntegrityError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProjectIntegrityError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return value


def _validate_namespace(namespace: object) -> str:
    if (
        not isinstance(namespace, str)
        or len(namespace) < 2
        or len(namespace) > 63
        or _NAMESPACE_PATTERN.fullmatch(namespace) is None
        or namespace in _RESERVED_NAMESPACES
    ):
        raise ProjectNamespaceError("Invalid or reserved Project namespace")
    return namespace


def _validate_display_name(display_name: object) -> str:
    if (
        not isinstance(display_name, str)
        or not display_name.strip()
        or len(display_name) > 120
        or any(ord(character) < 32 for character in display_name)
    ):
        raise ProjectIntegrityError("display_name must be bounded printable text")
    return display_name


def _freeze_metadata(metadata: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(metadata, Mapping):
        raise ProjectIntegrityError("metadata must be a mapping")
    copied = dict(metadata)
    if len(copied) > 32:
        raise ProjectIntegrityError("metadata exceeds 32 entries")
    for key, value in copied.items():
        if not isinstance(key, str) or _METADATA_KEY_PATTERN.fullmatch(key) is None:
            raise ProjectIntegrityError("metadata key is malformed")
        if not isinstance(value, str) or len(value) > 1024:
            raise ProjectIntegrityError("metadata value is malformed or too large")
    return MappingProxyType(copied)


def _freeze_configuration_refs(
    configuration_refs: Mapping[str, str],
) -> Mapping[str, str]:
    if not isinstance(configuration_refs, Mapping):
        raise ProjectConfigurationError("configuration_refs must be a mapping")
    copied = dict(configuration_refs)
    if len(copied) > 32:
        raise ProjectConfigurationError("configuration_refs exceeds 32 entries")
    for key, value in copied.items():
        if not isinstance(key, str) or _METADATA_KEY_PATTERN.fullmatch(key) is None:
            raise ProjectConfigurationError("configuration reference key is malformed")
        if (
            not isinstance(value, str)
            or _CONFIGURATION_REF_PATTERN.fullmatch(value) is None
        ):
            raise ProjectConfigurationError("configuration reference is malformed")
    return MappingProxyType(copied)


@dataclass(frozen=True)
class ProjectRef:
    """Opaque, stable Project identity."""

    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.value, str)
            or _PROJECT_REF_PATTERN.fullmatch(self.value) is None
        ):
            raise ProjectIntegrityError("ProjectRef is malformed")

    @classmethod
    def new(cls) -> "ProjectRef":
        return cls(f"prj_{uuid4().hex}")


@dataclass(frozen=True)
class ProjectAccess:
    """Unforgeable caller capability kept separate from public Project identity."""

    project_ref: ProjectRef
    token: str = dataclass_field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.token, str)
            or _ACCESS_TOKEN_PATTERN.fullmatch(self.token) is None
        ):
            raise ProjectIntegrityError("Project access token is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "ProjectAccess":
        return cls(project_ref, f"paccess_{secrets.token_hex(32)}")


@dataclass(frozen=True)
class Project:
    """Small provider- and domain-neutral durable Project primitive."""

    project_ref: ProjectRef
    namespace: str
    display_name: str
    metadata: Mapping[str, str]
    configuration_refs: Mapping[str, str]
    artifact_namespace: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        _validate_namespace(self.namespace)
        _validate_display_name(self.display_name)
        expected_artifact_namespace = (
            f"artifact-namespace://project/{self.project_ref.value}"
        )
        if self.artifact_namespace != expected_artifact_namespace:
            raise ProjectIntegrityError("artifact_namespace does not match project identity")
        _require_timezone_aware_timestamp(self.created_at, "created_at")
        _require_timezone_aware_timestamp(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        object.__setattr__(
            self,
            "configuration_refs",
            _freeze_configuration_refs(self.configuration_refs),
        )

    @property
    def project_id(self) -> str:
        return self.project_ref.value


@dataclass(frozen=True)
class ProjectRegistration:
    """Atomic Project creation result containing data and its initial capability."""

    project: Project
    access: ProjectAccess

    def __post_init__(self) -> None:
        if not isinstance(self.project, Project):
            raise TypeError("project must be Project")
        if not isinstance(self.access, ProjectAccess):
            raise TypeError("access must be ProjectAccess")
        if self.project.project_ref != self.access.project_ref:
            raise ProjectIntegrityError("Project registration identity mismatch")


@dataclass(frozen=True)
class ProjectScoped:
    """Reference contract for a record belonging to exactly one Project."""

    project_ref: ProjectRef
    record_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.record_id, str)
            or _RECORD_ID_PATTERN.fullmatch(self.record_id) is None
        ):
            raise ProjectIntegrityError("record_id is malformed")
        if (
            not isinstance(self.content_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.content_sha256) is None
        ):
            raise ProjectIntegrityError("content_sha256 is malformed")


class ProjectStore:
    """SQLite persistence enforcing Project scope on every record operation."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY NOT NULL,
                    namespace TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    configuration_refs_json TEXT NOT NULL,
                    artifact_namespace TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS projects_namespace_unique
                    ON projects(namespace);
                CREATE UNIQUE INDEX IF NOT EXISTS projects_artifact_namespace_unique
                    ON projects(artifact_namespace);

                CREATE TABLE IF NOT EXISTS project_roots (
                    project_id TEXT NOT NULL,
                    root_kind TEXT NOT NULL CHECK(root_kind IN ('artifact', 'configuration')),
                    PRIMARY KEY (project_id, root_kind),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS project_access (
                    project_id TEXT PRIMARY KEY NOT NULL,
                    token_sha256 TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS project_scoped_records (
                    project_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, record_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS project_scoped_records_digest
                    ON project_scoped_records(content_sha256);
                """
            )
        finally:
            connection.close()

    def _insert_required_roots(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
    ) -> None:
        connection.executemany(
            "INSERT INTO project_roots (project_id, root_kind) VALUES (?, ?)",
            (
                (project_ref.value, "artifact"),
                (project_ref.value, "configuration"),
            ),
        )

    def _insert_project_access(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO project_access (project_id, token_sha256, created_at)
            VALUES (?, ?, ?)
            """,
            (
                access.project_ref.value,
                self._token_sha256(access.token),
                created_at,
            ),
        )

    def create_project(
        self,
        *,
        namespace: str,
        display_name: str,
        metadata: Mapping[str, str] | None = None,
        configuration_refs: Mapping[str, str] | None = None,
    ) -> ProjectRegistration:
        project_ref = ProjectRef.new()
        access = ProjectAccess.new(project_ref)
        timestamp = _now_utc()
        project = Project(
            project_ref=project_ref,
            namespace=_validate_namespace(namespace),
            display_name=_validate_display_name(display_name),
            metadata={} if metadata is None else metadata,
            configuration_refs=(
                {} if configuration_refs is None else configuration_refs
            ),
            artifact_namespace=(
                f"artifact-namespace://project/{project_ref.value}"
            ),
            created_at=timestamp,
            updated_at=timestamp,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO projects (
                    project_id,
                    namespace,
                    display_name,
                    metadata_json,
                    configuration_refs_json,
                    artifact_namespace,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_ref.value,
                    project.namespace,
                    project.display_name,
                    self._serialize_mapping(project.metadata),
                    self._serialize_mapping(project.configuration_refs),
                    project.artifact_namespace,
                    project.created_at,
                    project.updated_at,
                ),
            )
            self._insert_required_roots(connection, project.project_ref)
            self._insert_project_access(connection, access, timestamp)
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ProjectConflictError("Project namespace or identity already exists") from exc
        except Exception as exc:
            connection.rollback()
            raise ProjectCreationError("Atomic Project creation failed") from exc
        finally:
            connection.close()
        return ProjectRegistration(project=project, access=access)

    def list_projects(self, requesting_access: ProjectAccess) -> tuple[Project, ...]:
        connection = self._connect()
        try:
            requester = self._authorize(connection, requesting_access)
            rows = connection.execute(
                "SELECT * FROM projects WHERE project_id = ? ORDER BY namespace",
                (requester.value,),
            ).fetchall()
            return tuple(self._project_from_row(row) for row in rows)
        finally:
            connection.close()

    def get_project(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
    ) -> Project:
        connection = self._connect()
        try:
            self._require_same_scope(connection, requesting_access, project_ref)
            return self._fetch_project(connection, project_ref)
        finally:
            connection.close()

    def update_project(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
        *,
        display_name: str | None = None,
        metadata: Mapping[str, str] | None = None,
        configuration_refs: Mapping[str, str] | None = None,
    ) -> Project:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_same_scope(connection, requesting_access, project_ref)
            current = self._fetch_project(connection, project_ref)
            updated = Project(
                project_ref=current.project_ref,
                namespace=current.namespace,
                display_name=(
                    current.display_name
                    if display_name is None
                    else _validate_display_name(display_name)
                ),
                metadata=current.metadata if metadata is None else metadata,
                configuration_refs=(
                    current.configuration_refs
                    if configuration_refs is None
                    else configuration_refs
                ),
                artifact_namespace=current.artifact_namespace,
                created_at=current.created_at,
                updated_at=_now_utc(),
            )
            result = connection.execute(
                """
                UPDATE projects
                SET display_name = ?, metadata_json = ?,
                    configuration_refs_json = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (
                    updated.display_name,
                    self._serialize_mapping(updated.metadata),
                    self._serialize_mapping(updated.configuration_refs),
                    updated.updated_at,
                    project_ref.value,
                ),
            )
            if result.rowcount != 1:
                raise ProjectNotFoundError("Project not found")
            connection.commit()
            return updated
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def resolve_configuration(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
        key: str,
    ) -> str:
        project = self.get_project(requesting_access, project_ref)
        try:
            return project.configuration_refs[key]
        except KeyError as exc:
            raise ProjectConfigurationError("Project configuration not found") from exc

    def resolve_artifact_namespace(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
    ) -> str:
        return self.get_project(requesting_access, project_ref).artifact_namespace

    def bind_scoped_record(
        self,
        requesting_access: ProjectAccess,
        record: ProjectScoped,
    ) -> ProjectScoped:
        connection = self._connect()
        try:
            requester = self._authorize(connection, requesting_access)
            self._require_record_scope(requester, record)
            self._fetch_project(connection, requester)
        finally:
            connection.close()
        return record

    def put_scoped_record(
        self,
        requesting_access: ProjectAccess,
        record: ProjectScoped,
    ) -> ProjectScoped:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            requester = self._authorize(connection, requesting_access)
            self._require_record_scope(requester, record)
            self._fetch_project(connection, requester)
            connection.execute(
                """
                INSERT INTO project_scoped_records (
                    project_id, record_id, content_sha256
                ) VALUES (?, ?, ?)
                ON CONFLICT(project_id, record_id)
                DO UPDATE SET content_sha256 = excluded.content_sha256
                """,
                (
                    record.project_ref.value,
                    record.record_id,
                    record.content_sha256,
                ),
            )
            connection.commit()
            return record
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read_scoped_record(
        self,
        requesting_access: ProjectAccess,
        record: ProjectScoped,
    ) -> ProjectScoped:
        connection = self._connect()
        try:
            requester = self._authorize(connection, requesting_access)
            self._require_record_scope(requester, record)
            self._fetch_project(connection, requester)
            row = connection.execute(
                """
                SELECT project_id, record_id, content_sha256
                FROM project_scoped_records
                WHERE project_id = ? AND record_id = ?
                """,
                (record.project_ref.value, record.record_id),
            ).fetchone()
            if row is None:
                raise ProjectScopeError("Project scope mismatch")
            return ProjectScoped(
                project_ref=ProjectRef(cast(str, row["project_id"])),
                record_id=cast(str, row["record_id"]),
                content_sha256=cast(str, row["content_sha256"]),
            )
        finally:
            connection.close()

    def delete_scoped_record(
        self,
        requesting_access: ProjectAccess,
        record: ProjectScoped,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            requester = self._authorize(connection, requesting_access)
            self._require_record_scope(requester, record)
            self._fetch_project(connection, requester)
            result = connection.execute(
                """
                DELETE FROM project_scoped_records
                WHERE project_id = ? AND record_id = ?
                """,
                (record.project_ref.value, record.record_id),
            )
            if result.rowcount != 1:
                raise ProjectScopeError("Project scope mismatch")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete_project(
        self,
        requesting_access: ProjectAccess,
        project_ref: ProjectRef,
    ) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._require_same_scope(connection, requesting_access, project_ref)
            self._fetch_project(connection, project_ref)
            record_count = cast(
                int,
                connection.execute(
                    """
                    SELECT COUNT(*) FROM project_scoped_records
                    WHERE project_id = ?
                    """,
                    (project_ref.value,),
                ).fetchone()[0],
            )
            if record_count:
                raise ProjectRetentionError(
                    "Project deletion is restricted while scoped records exist"
                )
            result = connection.execute(
                "DELETE FROM projects WHERE project_id = ?",
                (project_ref.value,),
            )
            if result.rowcount != 1:
                raise ProjectNotFoundError("Project not found")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _serialize_mapping(values: Mapping[str, str]) -> str:
        return json.dumps(
            dict(values),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _token_sha256(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def _authorize(
        cls,
        connection: sqlite3.Connection,
        requesting_access: object,
    ) -> ProjectRef:
        if not isinstance(requesting_access, ProjectAccess):
            raise TypeError("ProjectAccess capability is required")
        row = connection.execute(
            "SELECT token_sha256 FROM project_access WHERE project_id = ?",
            (requesting_access.project_ref.value,),
        ).fetchone()
        supplied_hash = cls._token_sha256(requesting_access.token)
        if row is None or not hmac.compare_digest(
            cast(str, row["token_sha256"]),
            supplied_hash,
        ):
            raise ProjectScopeError("Project scope mismatch")
        return requesting_access.project_ref

    @staticmethod
    def _deserialize_mapping(value: object, field_name: str) -> Mapping[str, str]:
        if not isinstance(value, str):
            raise ProjectIntegrityError(f"{field_name} is not serialized text")
        try:
            decoded = cast(object, json.loads(value))
        except json.JSONDecodeError as exc:
            raise ProjectIntegrityError(f"{field_name} is malformed") from exc
        if not isinstance(decoded, dict):
            raise ProjectIntegrityError(f"{field_name} is malformed")
        return cast(Mapping[str, str], decoded)

    def _project_from_row(self, row: sqlite3.Row) -> Project:
        return Project(
            project_ref=ProjectRef(cast(str, row["project_id"])),
            namespace=cast(str, row["namespace"]),
            display_name=cast(str, row["display_name"]),
            metadata=self._deserialize_mapping(row["metadata_json"], "metadata_json"),
            configuration_refs=self._deserialize_mapping(
                row["configuration_refs_json"],
                "configuration_refs_json",
            ),
            artifact_namespace=cast(str, row["artifact_namespace"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    def _fetch_project(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
    ) -> Project:
        row = connection.execute(
            "SELECT * FROM projects WHERE project_id = ?",
            (project_ref.value,),
        ).fetchone()
        if row is None:
            raise ProjectNotFoundError("Project not found")
        return self._project_from_row(row)

    @staticmethod
    def _require_project_ref(value: object) -> ProjectRef:
        if not isinstance(value, ProjectRef):
            raise TypeError("Project identity is required")
        return value

    @classmethod
    def _require_same_scope(
        cls,
        connection: sqlite3.Connection,
        requesting_access: object,
        project_ref: object,
    ) -> None:
        requester = cls._authorize(connection, requesting_access)
        target = cls._require_project_ref(project_ref)
        if requester != target:
            raise ProjectScopeError("Project scope mismatch")

    @classmethod
    def _require_record_scope(
        cls,
        requesting_project: object,
        record: object,
    ) -> None:
        requester = cls._require_project_ref(requesting_project)
        if not isinstance(record, ProjectScoped):
            raise TypeError("ProjectScoped record is required")
        if requester != record.project_ref:
            raise ProjectScopeError("Project scope mismatch")
