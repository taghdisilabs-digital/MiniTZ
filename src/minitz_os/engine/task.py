"""Durable, Project-scoped universal Task revisions for P0-04."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import TypeAlias, cast
from uuid import uuid4

from .capability import (
    CapabilityContractError,
    CapabilityNotFoundError,
    CapabilityRef,
    CapabilityRegistry,
)
from .project import (
    ProjectAccess,
    ProjectIntegrityError,
    ProjectRef,
    ProjectScopeError,
    ProjectScoped,
    ProjectStore,
)


TaskValue: TypeAlias = str | int | float | bool | None

_TASK_ID_PATTERN = re.compile(r"tsk_[0-9a-f]{32}")
_TASK_TYPE_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+"
)
_RECORD_SOURCE_PATTERN = re.compile(r"project-record://(rec_[0-9a-f]{32})")
_ARTIFACT_IDENTITY_SOURCE_PATTERN = re.compile(
    r"artifact://(prj_[0-9a-f]{32})/(art_[0-9a-f]{32})/([1-9][0-9]*)"
)
_ACTIVE_IDENTITY_SOURCE_PATTERN = re.compile(
    r"(?:"
    r"artifact://prj_[0-9a-f]{32}/art_[0-9a-f]{32}/[1-9][0-9]*"
    r"|source://prj_[0-9a-f]{32}/sha256/[0-9a-f]{64}"
    r"|content://sha256/[0-9a-f]{64}\?size=[0-9]+"
    r")"
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_ABSOLUTE_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SIDE_EFFECT_LEVELS = {
    "READ_ONLY": 0,
    "CANDIDATE_WRITE": 1,
    "PROJECT_WRITE": 2,
    "EXTERNAL_SIDE_EFFECT": 3,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class TaskError(Exception):
    """Base class for universal Task failures."""


class TaskContractError(TaskError):
    """Task semantic content is malformed."""


class TaskInputError(TaskError):
    """A Task input is not an exact authorized active reference."""


class TaskScopeError(TaskError):
    """A Task operation crossed its owning Project boundary."""


class TaskConflictError(TaskError):
    """An idempotency key or immutable revision has conflicting semantics."""


class TaskNotFoundError(TaskError):
    """A requested Task revision does not exist in the authorized Project."""


class TaskIntegrityError(TaskError):
    """Persisted Task revision evidence failed integrity verification."""


class TaskSideEffectError(TaskError):
    """A requested side effect exceeds the Task's explicit authority."""


def _validate_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TaskContractError(f"{field_name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise TaskContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TaskContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return value


def _validate_bounded_text(
    value: object,
    field_name: str,
    maximum: int,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 and character not in "\n\t" for character in value)
    ):
        raise TaskContractError(f"{field_name} is malformed or unbounded")
    return value


def _validate_optional_ref(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > 576
        or _ABSOLUTE_REF_PATTERN.fullmatch(value) is None
    ):
        raise TaskContractError(f"{field_name} must be a bounded absolute reference")
    return value


def _freeze_output_contract(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise TaskContractError("output_contract must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise TaskContractError("output_contract exceeds 64 entries")
    for key, contract_ref in copied.items():
        if not isinstance(key, str) or _KEY_PATTERN.fullmatch(key) is None:
            raise TaskContractError("output_contract key is malformed")
        if (
            not isinstance(contract_ref, str)
            or len(contract_ref) > 576
            or _ABSOLUTE_REF_PATTERN.fullmatch(contract_ref) is None
        ):
            raise TaskContractError("output_contract reference is malformed")
    return MappingProxyType(copied)


def _freeze_values(
    value: Mapping[str, TaskValue],
    field_name: str,
) -> Mapping[str, TaskValue]:
    if not isinstance(value, Mapping):
        raise TaskContractError(f"{field_name} must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise TaskContractError(f"{field_name} exceeds 64 entries")
    for key, item in copied.items():
        if not isinstance(key, str) or _KEY_PATTERN.fullmatch(key) is None:
            raise TaskContractError(f"{field_name} key is malformed")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise TaskContractError(f"{field_name} value is not a JSON scalar")
        if isinstance(item, float) and not math.isfinite(item):
            raise TaskContractError(f"{field_name} contains a non-finite number")
        if isinstance(item, str) and len(item) > 2048:
            raise TaskContractError(f"{field_name} string value is unbounded")
    return MappingProxyType(copied)


def _freeze_text_set(
    value: Sequence[str],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TaskContractError(f"{field_name} must be a sequence")
    copied = tuple(value)
    if len(copied) > 64:
        raise TaskContractError(f"{field_name} exceeds 64 entries")
    for item in copied:
        _validate_bounded_text(item, field_name, 512)
    return tuple(sorted(set(copied)))


@dataclass(frozen=True, order=True)
class TaskInputRef:
    """Exact Project-owned immutable record reference safe for active Tasks."""

    project_ref: ProjectRef
    input_kind: str
    source_ref: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if (
            not isinstance(self.input_kind, str)
            or _KEY_PATTERN.fullmatch(self.input_kind) is None
        ):
            raise TaskInputError("Task input kind is malformed")
        if (
            not isinstance(self.source_ref, str)
            or (
                _RECORD_SOURCE_PATTERN.fullmatch(self.source_ref) is None
                and _ACTIVE_IDENTITY_SOURCE_PATTERN.fullmatch(self.source_ref) is None
            )
        ):
            raise TaskInputError("Task input must be an exact active Project identity")
        if (
            not isinstance(self.content_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.content_sha256) is None
        ):
            raise TaskInputError("Task input content digest is malformed")

    @property
    def record_id(self) -> str:
        matched = _RECORD_SOURCE_PATTERN.fullmatch(self.source_ref)
        if matched is not None:
            return matched.group(1)
        if _ACTIVE_IDENTITY_SOURCE_PATTERN.fullmatch(self.source_ref) is None:
            raise TaskInputError("Task input source is malformed")
        bridge_identity = "\x00".join(
            (
                self.project_ref.value,
                self.input_kind,
                self.source_ref,
                self.content_sha256,
            )
        )
        return f"rec_{hashlib.sha256(bridge_identity.encode()).hexdigest()[:32]}"

    @classmethod
    def from_project_scoped(
        cls,
        record: ProjectScoped,
        *,
        input_kind: str,
    ) -> "TaskInputRef":
        if not isinstance(record, ProjectScoped):
            raise TaskInputError("ProjectScoped record is required")
        return cls(
            project_ref=record.project_ref,
            input_kind=input_kind,
            source_ref=f"project-record://{record.record_id}",
            content_sha256=record.content_sha256,
        )


@dataclass(frozen=True, order=True)
class TaskRef:
    """Exact identity of one immutable Task revision in one Project."""

    project_ref: ProjectRef
    task_id: str
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.task_id, str) or _TASK_ID_PATTERN.fullmatch(self.task_id) is None:
            raise TaskContractError("Task identity is malformed")
        if not isinstance(self.revision, int) or isinstance(self.revision, bool) or self.revision < 1:
            raise TaskContractError("Task revision must be a positive integer")


@dataclass(frozen=True)
class Task:
    """Immutable universal requested outcome with no execution topology."""

    task_ref: TaskRef
    idempotency_key: str
    task_type: str
    objective: str
    required_capabilities: tuple[CapabilityRef, ...]
    input_refs: tuple[TaskInputRef, ...]
    output_contract: Mapping[str, str]
    constraints: Mapping[str, TaskValue]
    side_effect_authority: str
    data_policy_ref: str | None
    egress_policy_ref: str | None
    evidence_requirements: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    resource_hints: Mapping[str, TaskValue]
    created_at: str = field(default_factory=_now_utc)
    canonical_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.task_ref, TaskRef):
            raise TypeError("task_ref must be TaskRef")
        _validate_bounded_text(self.idempotency_key, "idempotency_key", 256)
        if _TASK_TYPE_PATTERN.fullmatch(self.task_type) is None or len(self.task_type) > 128:
            raise TaskContractError("task_type must be an extensible namespaced string")
        _validate_bounded_text(self.objective, "objective", 8192)
        if not isinstance(self.required_capabilities, tuple) or not all(
            isinstance(item, CapabilityRef) for item in self.required_capabilities
        ):
            raise TaskContractError("required_capabilities must contain CapabilityRef")
        if not isinstance(self.input_refs, tuple) or not all(
            isinstance(item, TaskInputRef) for item in self.input_refs
        ):
            raise TaskInputError("input_refs must contain only TaskInputRef")
        capabilities = tuple(sorted(set(self.required_capabilities)))
        inputs = tuple(sorted(set(self.input_refs)))
        if len(capabilities) > 64 or len(inputs) > 128:
            raise TaskContractError("Task capability or input collection is unbounded")
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "input_refs", inputs)
        object.__setattr__(self, "output_contract", _freeze_output_contract(self.output_contract))
        object.__setattr__(self, "constraints", _freeze_values(self.constraints, "constraints"))
        if self.side_effect_authority not in _SIDE_EFFECT_LEVELS:
            raise TaskContractError("side_effect_authority is malformed")
        object.__setattr__(self, "data_policy_ref", _validate_optional_ref(self.data_policy_ref, "data_policy_ref"))
        object.__setattr__(self, "egress_policy_ref", _validate_optional_ref(self.egress_policy_ref, "egress_policy_ref"))
        object.__setattr__(self, "evidence_requirements", _freeze_text_set(self.evidence_requirements, "evidence_requirements"))
        object.__setattr__(self, "acceptance_criteria", _freeze_text_set(self.acceptance_criteria, "acceptance_criteria"))
        object.__setattr__(self, "resource_hints", _freeze_values(self.resource_hints, "resource_hints"))
        _validate_timestamp(self.created_at, "created_at")
        object.__setattr__(self, "canonical_digest", self._canonical_digest())
        object.__setattr__(self, "record_sha256", self._record_digest())

    @property
    def project_ref(self) -> ProjectRef:
        return self.task_ref.project_ref

    @property
    def task_id(self) -> str:
        return self.task_ref.task_id

    @property
    def revision(self) -> int:
        return self.task_ref.revision

    def _canonical_payload(self) -> dict[str, object]:
        return {
            "acceptance_criteria": list(self.acceptance_criteria),
            "constraints": dict(self.constraints),
            "data_policy_ref": self.data_policy_ref,
            "egress_policy_ref": self.egress_policy_ref,
            "evidence_requirements": list(self.evidence_requirements),
            "input_refs": [
                {
                    "content_sha256": item.content_sha256,
                    "input_kind": item.input_kind,
                    "project_ref": item.project_ref.value,
                    "source_ref": item.source_ref,
                }
                for item in self.input_refs
            ],
            "objective": self.objective,
            "output_contract": dict(self.output_contract),
            "project_ref": self.project_ref.value,
            "required_capabilities": [item.value for item in self.required_capabilities],
            "resource_hints": dict(self.resource_hints),
            "side_effect_authority": self.side_effect_authority,
            "task_type": self.task_type,
        }

    def _canonical_digest(self) -> str:
        canonical = json.dumps(
            self._canonical_payload(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _record_digest(self) -> str:
        record = {
            "canonical_digest": self.canonical_digest,
            "created_at": self.created_at,
            "idempotency_key": self.idempotency_key,
            "revision": self.revision,
            "task_id": self.task_id,
        }
        return hashlib.sha256(
            json.dumps(record, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()


class TaskRevisionService:
    """Atomic Task creation, canonicalization, revision, and read service."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
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
                CREATE TABLE IF NOT EXISTS task_revisions (
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    required_capabilities_json TEXT NOT NULL,
                    input_refs_json TEXT NOT NULL,
                    output_contract_json TEXT NOT NULL,
                    constraints_json TEXT NOT NULL,
                    side_effect_authority TEXT NOT NULL,
                    data_policy_ref TEXT,
                    egress_policy_ref TEXT,
                    evidence_requirements_json TEXT NOT NULL,
                    acceptance_criteria_json TEXT NOT NULL,
                    resource_hints_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    canonical_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, task_id, revision),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS task_revisions_canonical_digest
                    ON task_revisions(project_id, canonical_digest);

                CREATE UNIQUE INDEX IF NOT EXISTS project_scoped_records_exact_identity
                    ON project_scoped_records(project_id, record_id, content_sha256);

                CREATE TABLE IF NOT EXISTS task_capability_bindings (
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    capability_id TEXT NOT NULL,
                    capability_version TEXT NOT NULL,
                    PRIMARY KEY (
                        project_id, task_id, revision,
                        capability_id, capability_version
                    ),
                    FOREIGN KEY (project_id, task_id, revision)
                        REFERENCES task_revisions(project_id, task_id, revision) ON DELETE RESTRICT,
                    FOREIGN KEY (capability_id, capability_version)
                        REFERENCES capabilities(capability_id, version) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS task_input_bindings (
                    project_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    input_project_id TEXT NOT NULL,
                    input_kind TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    PRIMARY KEY (
                        project_id, task_id, revision,
                        input_project_id, input_kind, source_ref
                    ),
                    FOREIGN KEY (project_id, task_id, revision)
                        REFERENCES task_revisions(project_id, task_id, revision) ON DELETE RESTRICT,
                    FOREIGN KEY (input_project_id, record_id, content_sha256)
                        REFERENCES project_scoped_records(
                            project_id, record_id, content_sha256
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS task_idempotency (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    canonical_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, idempotency_key),
                    FOREIGN KEY (project_id, task_id, revision)
                        REFERENCES task_revisions(project_id, task_id, revision) ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS task_revisions_no_update
                BEFORE UPDATE ON task_revisions
                BEGIN
                    SELECT RAISE(ABORT, 'Task revisions are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS task_revisions_no_delete
                BEFORE DELETE ON task_revisions
                BEGIN
                    SELECT RAISE(ABORT, 'Task revision history cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS task_idempotency_no_update
                BEFORE UPDATE ON task_idempotency
                BEGIN
                    SELECT RAISE(ABORT, 'Task idempotency records are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS task_idempotency_no_delete
                BEFORE DELETE ON task_idempotency
                BEGIN
                    SELECT RAISE(ABORT, 'Task idempotency history cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS task_capability_bindings_no_update
                BEFORE UPDATE ON task_capability_bindings
                BEGIN
                    SELECT RAISE(ABORT, 'Task Capability bindings are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS task_capability_bindings_no_delete
                BEFORE DELETE ON task_capability_bindings
                BEGIN
                    SELECT RAISE(ABORT, 'Task Capability bindings cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS task_input_bindings_no_update
                BEFORE UPDATE ON task_input_bindings
                BEGIN
                    SELECT RAISE(ABORT, 'Task input bindings are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS task_input_bindings_no_delete
                BEFORE DELETE ON task_input_bindings
                BEGIN
                    SELECT RAISE(ABORT, 'Task input bindings cannot be deleted');
                END;
                """
            )
        finally:
            connection.close()

    def create_task(
        self,
        requesting_access: ProjectAccess,
        *,
        project_ref: ProjectRef,
        idempotency_key: str,
        task_type: str,
        objective: str,
        required_capabilities: Sequence[CapabilityRef],
        input_refs: Sequence[TaskInputRef],
        output_contract: Mapping[str, str],
        constraints: Mapping[str, TaskValue],
        side_effect_authority: str,
        data_policy_ref: str | None,
        egress_policy_ref: str | None,
        evidence_requirements: Sequence[str],
        acceptance_criteria: Sequence[str],
        resource_hints: Mapping[str, TaskValue],
    ) -> Task:
        self._validate_dependencies(
            requesting_access,
            project_ref,
            required_capabilities,
            input_refs,
        )
        candidate = self._make_task(
            TaskRef(project_ref, f"tsk_{uuid4().hex}", 1),
            idempotency_key=idempotency_key,
            task_type=task_type,
            objective=objective,
            required_capabilities=required_capabilities,
            input_refs=input_refs,
            output_contract=output_contract,
            constraints=constraints,
            side_effect_authority=side_effect_authority,
            data_policy_ref=data_policy_ref,
            egress_policy_ref=egress_policy_ref,
            evidence_requirements=evidence_requirements,
            acceptance_criteria=acceptance_criteria,
            resource_hints=resource_hints,
        )
        return self._persist_candidate(candidate)

    def create_revision(
        self,
        requesting_access: ProjectAccess,
        *,
        prior_ref: TaskRef,
        idempotency_key: str,
        task_type: str,
        objective: str,
        required_capabilities: Sequence[CapabilityRef],
        input_refs: Sequence[TaskInputRef],
        output_contract: Mapping[str, str],
        constraints: Mapping[str, TaskValue],
        side_effect_authority: str,
        data_policy_ref: str | None,
        egress_policy_ref: str | None,
        evidence_requirements: Sequence[str],
        acceptance_criteria: Sequence[str],
        resource_hints: Mapping[str, TaskValue],
    ) -> Task:
        prior = self.get_task(requesting_access, prior_ref)
        self._validate_dependencies(
            requesting_access,
            prior.project_ref,
            required_capabilities,
            input_refs,
        )
        candidate = self._make_task(
            TaskRef(prior.project_ref, prior.task_id, prior.revision + 1),
            idempotency_key=idempotency_key,
            task_type=task_type,
            objective=objective,
            required_capabilities=required_capabilities,
            input_refs=input_refs,
            output_contract=output_contract,
            constraints=constraints,
            side_effect_authority=side_effect_authority,
            data_policy_ref=data_policy_ref,
            egress_policy_ref=egress_policy_ref,
            evidence_requirements=evidence_requirements,
            acceptance_criteria=acceptance_criteria,
            resource_hints=resource_hints,
        )
        if candidate.canonical_digest == prior.canonical_digest:
            raise TaskConflictError("New Task revision must contain a material change")
        return self._persist_candidate(candidate, expected_prior=prior_ref)

    def get_task(
        self,
        requesting_access: ProjectAccess,
        task_ref: TaskRef,
    ) -> Task:
        if not isinstance(task_ref, TaskRef):
            raise TypeError("TaskRef is required")
        try:
            self.projects.get_project(requesting_access, task_ref.project_ref)
        except ProjectScopeError as exc:
            raise TaskScopeError("Task Project scope mismatch") from exc
        connection = self._connect()
        try:
            return self._fetch_task(connection, task_ref)
        finally:
            connection.close()

    @staticmethod
    def require_side_effect_within(task: Task, requested_authority: str) -> None:
        if not isinstance(task, Task):
            raise TypeError("Task is required")
        if requested_authority not in _SIDE_EFFECT_LEVELS:
            raise TaskSideEffectError("Requested side-effect authority is malformed")
        if _SIDE_EFFECT_LEVELS[requested_authority] > _SIDE_EFFECT_LEVELS[task.side_effect_authority]:
            raise TaskSideEffectError("Requested side effect exceeds Task authority")

    def _validate_dependencies(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        capability_refs: Sequence[CapabilityRef],
        input_refs: Sequence[TaskInputRef],
    ) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise TaskScopeError("Task Project scope mismatch") from exc
        if isinstance(capability_refs, (str, bytes)) or not isinstance(capability_refs, Sequence):
            raise TaskContractError("required_capabilities must be a sequence")
        for capability_ref in capability_refs:
            if not isinstance(capability_ref, CapabilityRef):
                raise TaskContractError("required_capabilities must contain CapabilityRef")
            try:
                self.capabilities.get(capability_ref)
            except CapabilityNotFoundError as exc:
                raise TaskContractError("Required CapabilityRef is not registered") from exc
        if isinstance(input_refs, (str, bytes)) or not isinstance(input_refs, Sequence):
            raise TaskInputError("input_refs must be a sequence")
        connection = self._connect()
        try:
            for input_ref in input_refs:
                if not isinstance(input_ref, TaskInputRef):
                    raise TaskInputError("Active Task inputs must be TaskInputRef")
                if input_ref.project_ref != project_ref:
                    raise TaskScopeError("Task Project scope mismatch")
                record = ProjectScoped(
                    project_ref=input_ref.project_ref,
                    record_id=input_ref.record_id,
                    content_sha256=input_ref.content_sha256,
                )
                try:
                    observed = self.projects.read_scoped_record(access, record)
                except ProjectScopeError as exc:
                    raise TaskInputError("Exact Task input does not exist") from exc
                if observed.content_sha256 != input_ref.content_sha256:
                    raise TaskInputError("Exact Task input digest does not match")
                try:
                    self._verify_active_identity_bridge(connection, input_ref)
                except TaskIntegrityError as exc:
                    raise TaskInputError("Exact active Task input bridge is invalid") from exc
        finally:
            connection.close()

    @staticmethod
    def _make_task(
        task_ref: TaskRef,
        *,
        idempotency_key: str,
        task_type: str,
        objective: str,
        required_capabilities: Sequence[CapabilityRef],
        input_refs: Sequence[TaskInputRef],
        output_contract: Mapping[str, str],
        constraints: Mapping[str, TaskValue],
        side_effect_authority: str,
        data_policy_ref: str | None,
        egress_policy_ref: str | None,
        evidence_requirements: Sequence[str],
        acceptance_criteria: Sequence[str],
        resource_hints: Mapping[str, TaskValue],
    ) -> Task:
        return Task(
            task_ref=task_ref,
            idempotency_key=idempotency_key,
            task_type=task_type,
            objective=objective,
            required_capabilities=tuple(required_capabilities),
            input_refs=tuple(input_refs),
            output_contract=output_contract,
            constraints=constraints,
            side_effect_authority=side_effect_authority,
            data_policy_ref=data_policy_ref,
            egress_policy_ref=egress_policy_ref,
            evidence_requirements=tuple(evidence_requirements),
            acceptance_criteria=tuple(acceptance_criteria),
            resource_hints=resource_hints,
        )

    def _persist_candidate(
        self,
        candidate: Task,
        *,
        expected_prior: TaskRef | None = None,
    ) -> Task:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            idempotent = connection.execute(
                "SELECT * FROM task_idempotency WHERE project_id = ? AND idempotency_key = ?",
                (candidate.project_ref.value, candidate.idempotency_key),
            ).fetchone()
            if idempotent is not None:
                self._verify_idempotency_row(idempotent)
                existing_ref = TaskRef(
                    candidate.project_ref,
                    cast(str, idempotent["task_id"]),
                    cast(int, idempotent["revision"]),
                )
                existing = self._fetch_task(connection, existing_ref)
                if (
                    existing.canonical_digest != candidate.canonical_digest
                    or idempotent["canonical_digest"] != existing.canonical_digest
                    or (
                        expected_prior is not None
                        and existing.task_ref != candidate.task_ref
                    )
                ):
                    raise TaskConflictError("Task idempotency key has conflicting semantics")
                connection.commit()
                return existing
            if expected_prior is not None:
                latest = cast(
                    int,
                    connection.execute(
                        "SELECT MAX(revision) FROM task_revisions WHERE project_id = ? AND task_id = ?",
                        (candidate.project_ref.value, candidate.task_id),
                    ).fetchone()[0],
                )
                if latest != expected_prior.revision:
                    raise TaskConflictError("Task revision predecessor is stale")
            self._insert_task(connection, candidate)
            connection.execute(
                """
                INSERT INTO task_idempotency (
                    project_id, idempotency_key, task_id, revision,
                    canonical_digest, created_at, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.project_ref.value,
                    candidate.idempotency_key,
                    candidate.task_id,
                    candidate.revision,
                    candidate.canonical_digest,
                    candidate.created_at,
                    self._idempotency_sha256(candidate),
                ),
            )
            connection.commit()
            return candidate
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _insert_task(self, connection: sqlite3.Connection, task: Task) -> None:
        connection.execute(
            """
            INSERT INTO task_revisions (
                project_id, task_id, revision, idempotency_key, task_type,
                objective, required_capabilities_json, input_refs_json,
                output_contract_json, constraints_json, side_effect_authority,
                data_policy_ref, egress_policy_ref, evidence_requirements_json,
                acceptance_criteria_json, resource_hints_json, created_at,
                canonical_digest, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.project_ref.value,
                task.task_id,
                task.revision,
                task.idempotency_key,
                task.task_type,
                task.objective,
                self._json([item.value for item in task.required_capabilities]),
                self._json([
                    {
                        "project_ref": item.project_ref.value,
                        "input_kind": item.input_kind,
                        "source_ref": item.source_ref,
                        "content_sha256": item.content_sha256,
                    }
                    for item in task.input_refs
                ]),
                self._json(dict(task.output_contract)),
                self._json(dict(task.constraints)),
                task.side_effect_authority,
                task.data_policy_ref,
                task.egress_policy_ref,
                self._json(list(task.evidence_requirements)),
                self._json(list(task.acceptance_criteria)),
                self._json(dict(task.resource_hints)),
                task.created_at,
                task.canonical_digest,
                task.record_sha256,
            ),
        )
        connection.executemany(
            """
            INSERT INTO task_capability_bindings (
                project_id, task_id, revision, capability_id, capability_version
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    task.project_ref.value,
                    task.task_id,
                    task.revision,
                    capability_ref.capability_id,
                    capability_ref.version,
                )
                for capability_ref in task.required_capabilities
            ),
        )
        connection.executemany(
            """
            INSERT INTO task_input_bindings (
                project_id, task_id, revision, input_project_id,
                input_kind, source_ref, record_id, content_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    task.project_ref.value,
                    task.task_id,
                    task.revision,
                    input_ref.project_ref.value,
                    input_ref.input_kind,
                    input_ref.source_ref,
                    input_ref.record_id,
                    input_ref.content_sha256,
                )
                for input_ref in task.input_refs
            ),
        )

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def _idempotency_sha256(cls, task: Task) -> str:
        return hashlib.sha256(
            cls._json(
                {
                    "canonical_digest": task.canonical_digest,
                    "created_at": task.created_at,
                    "idempotency_key": task.idempotency_key,
                    "project_id": task.project_ref.value,
                    "revision": task.revision,
                    "task_id": task.task_id,
                }
            ).encode()
        ).hexdigest()

    @classmethod
    def _verify_idempotency_row(cls, row: sqlite3.Row) -> None:
        canonical = cls._json(
            {
                "canonical_digest": row["canonical_digest"],
                "created_at": row["created_at"],
                "idempotency_key": row["idempotency_key"],
                "project_id": row["project_id"],
                "revision": row["revision"],
                "task_id": row["task_id"],
            }
        )
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        persisted = row["record_sha256"]
        if not isinstance(persisted, str) or not hmac.compare_digest(expected, persisted):
            raise TaskIntegrityError("Task idempotency record failed integrity verification")

    @classmethod
    def _verify_active_identity_bridge(
        cls,
        connection: sqlite3.Connection,
        input_ref: TaskInputRef,
    ) -> None:
        if _RECORD_SOURCE_PATTERN.fullmatch(input_ref.source_ref) is not None:
            return
        try:
            row = connection.execute(
                """
                SELECT * FROM artifact_task_input_bindings
                WHERE project_id = ? AND record_id = ?
                """,
                (input_ref.project_ref.value, input_ref.record_id),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            raise TaskIntegrityError("Active Task input bridge is unavailable") from exc
        if row is None:
            raise TaskIntegrityError("Active Task input bridge is missing")
        artifact_id = cast(str | None, row["artifact_id"])
        artifact_revision = cast(int | None, row["artifact_revision"])
        artifact_record_sha256 = cast(str | None, row["artifact_record_sha256"])
        identity_digest = cast(str, row["identity_digest"])
        identity_ref = cast(str, row["identity_ref"])
        input_kind = cast(str, row["input_kind"])
        if (
            row["project_id"] != input_ref.project_ref.value
            or row["record_id"] != input_ref.record_id
            or input_kind != input_ref.input_kind
            or identity_ref != input_ref.source_ref
            or not hmac.compare_digest(identity_digest, input_ref.content_sha256)
        ):
            raise TaskIntegrityError("Active Task input bridge identity is inconsistent")
        expected_record_sha256 = hashlib.sha256(
            cls._json(
                {
                    "artifact_id": artifact_id,
                    "artifact_record_sha256": artifact_record_sha256,
                    "artifact_revision": artifact_revision,
                    "identity_digest": identity_digest,
                    "identity_ref": identity_ref,
                    "input_kind": input_kind,
                    "project_id": input_ref.project_ref.value,
                    "record_id": input_ref.record_id,
                }
            ).encode()
        ).hexdigest()
        persisted_record_sha256 = row["record_sha256"]
        if (
            not isinstance(persisted_record_sha256, str)
            or not hmac.compare_digest(expected_record_sha256, persisted_record_sha256)
        ):
            raise TaskIntegrityError("Active Task input bridge failed integrity verification")
        artifact_match = _ARTIFACT_IDENTITY_SOURCE_PATTERN.fullmatch(identity_ref)
        if input_kind == "artifact":
            if (
                artifact_match is None
                or artifact_match.group(1) != input_ref.project_ref.value
                or artifact_match.group(2) != artifact_id
                or int(artifact_match.group(3)) != artifact_revision
            ):
                raise TaskIntegrityError("Artifact Task input bridge is malformed")
            artifact_row = connection.execute(
                """
                SELECT * FROM artifact_revisions
                WHERE project_id = ? AND artifact_id = ? AND revision = ?
                """,
                (input_ref.project_ref.value, artifact_id, artifact_revision),
            ).fetchone()
            if artifact_row is None:
                raise TaskIntegrityError("Exact Artifact Task input no longer exists")
            try:
                content_json = cast(str | None, artifact_row["content_json"])
                content_payload = (
                    None
                    if content_json is None
                    else cast(dict[str, object], json.loads(content_json))
                )
                expected_semantic_digest = hashlib.sha256(
                    cls._json(
                        {
                            "content_ref": content_payload,
                            "derivation_type": artifact_row["derivation_type"],
                            "metadata": cast(
                                dict[str, str],
                                json.loads(cast(str, artifact_row["metadata_json"])),
                            ),
                            "producer_attempt_id": artifact_row["producer_attempt_id"],
                            "producer_fence": artifact_row["producer_fence"],
                            "producer_run_ref": artifact_row["producer_run_id"],
                            "project_ref": artifact_row["project_id"],
                            "role": artifact_row["role"],
                            "source_artifact_refs": cast(
                                list[str],
                                json.loads(
                                    cast(str, artifact_row["source_artifact_refs_json"])
                                ),
                            ),
                            "source_content_refs": cast(
                                list[dict[str, object]],
                                json.loads(
                                    cast(str, artifact_row["source_content_refs_json"])
                                ),
                            ),
                            "source_refs": cast(
                                list[dict[str, object]],
                                json.loads(cast(str, artifact_row["source_refs_json"])),
                            ),
                        }
                    ).encode()
                ).hexdigest()
                persisted_semantic_digest = cast(str, artifact_row["semantic_digest"])
                if not hmac.compare_digest(
                    expected_semantic_digest,
                    persisted_semantic_digest,
                ):
                    raise TaskIntegrityError(
                        "Exact Artifact Task input semantic digest is inconsistent"
                    )
                expected_artifact_record_sha256 = hashlib.sha256(
                    cls._json(
                        {
                            "artifact_id": artifact_row["artifact_id"],
                            "created_at": artifact_row["created_at"],
                            "project_id": artifact_row["project_id"],
                            "revision": artifact_row["revision"],
                            "semantic_digest": persisted_semantic_digest,
                        }
                    ).encode()
                ).hexdigest()
                persisted_artifact_record_sha256 = cast(
                    str,
                    artifact_row["record_sha256"],
                )
                if (
                    artifact_record_sha256 is None
                    or not hmac.compare_digest(
                        expected_artifact_record_sha256,
                        persisted_artifact_record_sha256,
                    )
                    or not hmac.compare_digest(
                        artifact_record_sha256,
                        persisted_artifact_record_sha256,
                    )
                ):
                    raise TaskIntegrityError(
                        "Exact Artifact Task input record digest is inconsistent"
                    )
                artifact_digest = (
                    persisted_semantic_digest
                    if content_payload is None
                    else cast(str, content_payload["digest"])
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise TaskIntegrityError("Exact Artifact Task input is malformed") from exc
            if not hmac.compare_digest(artifact_digest, identity_digest):
                raise TaskIntegrityError("Artifact Task input digest is inconsistent")
        elif input_kind in {"source", "content"}:
            if (
                artifact_id is not None
                or artifact_revision is not None
                or artifact_record_sha256 is not None
            ):
                raise TaskIntegrityError("Non-Artifact Task input claims Artifact identity")
        else:
            raise TaskIntegrityError("Active Task input kind is unsupported")

    def _fetch_task(self, connection: sqlite3.Connection, task_ref: TaskRef) -> Task:
        row = connection.execute(
            """
            SELECT * FROM task_revisions
            WHERE project_id = ? AND task_id = ? AND revision = ?
            """,
            (task_ref.project_ref.value, task_ref.task_id, task_ref.revision),
        ).fetchone()
        if row is None:
            raise TaskNotFoundError("Task revision not found")
        return self._task_from_row(connection, row)

    def _task_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> Task:
        try:
            capabilities_raw = cast(list[str], json.loads(cast(str, row["required_capabilities_json"])))
            inputs_raw = cast(list[dict[str, object]], json.loads(cast(str, row["input_refs_json"])))
            task = Task(
                task_ref=TaskRef(
                    ProjectRef(cast(str, row["project_id"])),
                    cast(str, row["task_id"]),
                    cast(int, row["revision"]),
                ),
                idempotency_key=cast(str, row["idempotency_key"]),
                task_type=cast(str, row["task_type"]),
                objective=cast(str, row["objective"]),
                required_capabilities=tuple(self._parse_capability_ref(value) for value in capabilities_raw),
                input_refs=tuple(
                    TaskInputRef(
                        ProjectRef(cast(str, value["project_ref"])),
                        cast(str, value["input_kind"]),
                        cast(str, value["source_ref"]),
                        cast(str, value["content_sha256"]),
                    )
                    for value in inputs_raw
                ),
                output_contract=cast(dict[str, str], json.loads(cast(str, row["output_contract_json"]))),
                constraints=cast(dict[str, TaskValue], json.loads(cast(str, row["constraints_json"]))),
                side_effect_authority=cast(str, row["side_effect_authority"]),
                data_policy_ref=cast(str | None, row["data_policy_ref"]),
                egress_policy_ref=cast(str | None, row["egress_policy_ref"]),
                evidence_requirements=tuple(cast(list[str], json.loads(cast(str, row["evidence_requirements_json"])))),
                acceptance_criteria=tuple(cast(list[str], json.loads(cast(str, row["acceptance_criteria_json"])))),
                resource_hints=cast(dict[str, TaskValue], json.loads(cast(str, row["resource_hints_json"]))),
                created_at=cast(str, row["created_at"]),
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            CapabilityContractError,
            ProjectIntegrityError,
            TaskError,
        ) as exc:
            raise TaskIntegrityError("Persisted Task revision is malformed") from exc
        persisted_canonical_digest = row["canonical_digest"]
        if (
            not isinstance(persisted_canonical_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_canonical_digest) is None
            or not hmac.compare_digest(
                task.canonical_digest,
                persisted_canonical_digest,
            )
        ):
            raise TaskIntegrityError("Persisted Task canonical digest verification failed")
        persisted_record_digest = row["record_sha256"]
        if (
            not isinstance(persisted_record_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_record_digest) is None
            or not hmac.compare_digest(task.record_sha256, persisted_record_digest)
        ):
            raise TaskIntegrityError("Persisted Task record digest verification failed")
        capability_rows = connection.execute(
            """
            SELECT capability_id, capability_version
            FROM task_capability_bindings
            WHERE project_id = ? AND task_id = ? AND revision = ?
            """,
            (task.project_ref.value, task.task_id, task.revision),
        ).fetchall()
        persisted_capabilities = tuple(
            sorted(
                CapabilityRef(
                    cast(str, binding["capability_id"]),
                    cast(str, binding["capability_version"]),
                )
                for binding in capability_rows
            )
        )
        if persisted_capabilities != task.required_capabilities:
            raise TaskIntegrityError("Task Capability bindings are inconsistent")
        input_rows = connection.execute(
            """
            SELECT
                binding.input_project_id,
                binding.input_kind,
                binding.source_ref,
                binding.record_id,
                binding.content_sha256,
                source.project_id AS verified_source_project_id
            FROM task_input_bindings AS binding
            LEFT JOIN project_scoped_records AS source
              ON source.project_id = binding.input_project_id
             AND source.record_id = binding.record_id
             AND source.content_sha256 = binding.content_sha256
            WHERE binding.project_id = ?
              AND binding.task_id = ?
              AND binding.revision = ?
            """,
            (task.project_ref.value, task.task_id, task.revision),
        ).fetchall()
        parsed_inputs: list[TaskInputRef] = []
        for binding in input_rows:
            input_ref = TaskInputRef(
                ProjectRef(cast(str, binding["input_project_id"])),
                cast(str, binding["input_kind"]),
                cast(str, binding["source_ref"]),
                cast(str, binding["content_sha256"]),
            )
            if binding["record_id"] != input_ref.record_id:
                raise TaskIntegrityError("Task input binding identity is inconsistent")
            if binding["verified_source_project_id"] is None:
                raise TaskIntegrityError("Task exact input source no longer exists")
            self._verify_active_identity_bridge(connection, input_ref)
            parsed_inputs.append(input_ref)
        persisted_inputs = tuple(sorted(parsed_inputs))
        if persisted_inputs != task.input_refs:
            raise TaskIntegrityError("Task input bindings are inconsistent")
        return task

    @staticmethod
    def _parse_capability_ref(value: str) -> CapabilityRef:
        capability_id, separator, version = value.rpartition("@")
        if not separator:
            raise TaskIntegrityError("Persisted CapabilityRef is malformed")
        return CapabilityRef(capability_id, version)
