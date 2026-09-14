"""One Project-scoped MiniTZ isolation family over existing isolation realizations.

The family is an attachment/evidence boundary only. Project, Workspace, isolated
runtime, and ProjectCell keep their existing identities and lifecycle owners.
This module never schedules, executes, advances, or completes work.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast

from .isolated_runtime import RuntimeRef
from .project import ProjectAccess, ProjectRef, ProjectStore
from .workspace import WorkspaceRef

_SHA256 = re.compile(r"[0-9a-f]{64}")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")
_NAMESPACE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,2048}")
_SECRET_KEY = re.compile(r"(?:^|[_-])(?:token|secret|password|credential|api[_-]?key|private[_-]?key)(?:$|[_-])", re.I)
_SECRET_TEXT = re.compile(r"(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)", re.I)


class IsolationFamilyError(ValueError):
    """Base isolation-family failure."""


class IsolationFamilyContractError(IsolationFamilyError):
    """An isolation-family record is malformed or unsafe."""


class IsolationFamilyScopeError(IsolationFamilyError):
    """An attachment crossed an exact Project boundary."""


class IsolationFamilyAuthorityError(IsolationFamilyError, PermissionError):
    """An attachment attempted to weaken Project isolation authority."""


class IsolationFamilyConflictError(IsolationFamilyError):
    """Immutable idempotency semantics or evidence conflict."""


class IsolationFamilyIntegrityError(IsolationFamilyError):
    """Persisted attachment evidence failed exact verification."""


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise IsolationFamilyContractError("isolation-family evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise IsolationFamilyContractError(f"{label} must be a SHA-256 digest")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise IsolationFamilyContractError("idempotency key is malformed")
    return value


def _evidence_refs(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise IsolationFamilyContractError("evidence refs must be a sequence")
    copied = tuple(values)
    if len(copied) > 256 or len(copied) != len(set(copied)):
        raise IsolationFamilyContractError("evidence refs are duplicated or unbounded")
    if any(not isinstance(item, str) or _REF.fullmatch(item) is None for item in copied):
        raise IsolationFamilyContractError("evidence ref must be an exact absolute reference")
    return tuple(sorted(copied))


def _scan_secret(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and _SECRET_KEY.search(key) and isinstance(item, str) and item.strip():
                raise IsolationFamilyContractError("secret material must not enter isolation-family evidence")
            _scan_secret(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _scan_secret(item)
        return
    if isinstance(value, str) and _SECRET_TEXT.search(value):
        raise IsolationFamilyContractError("secret material must not enter isolation-family evidence")


def _project_ref(value: object, label: str) -> ProjectRef:
    if not isinstance(value, str):
        raise IsolationFamilyContractError(f"{label} is missing")
    try:
        return ProjectRef(value)
    except Exception as exc:
        raise IsolationFamilyContractError(f"{label} is malformed") from exc


def _require_namespace(value: object) -> str:
    if not isinstance(value, str) or _NAMESPACE.fullmatch(value) is None:
        raise IsolationFamilyContractError("ProjectCell namespace is malformed")
    return value


@dataclass(frozen=True)
class ProjectCellIsolationBinding:
    project_ref: ProjectRef
    project_namespace: str
    cell_ref: str
    native_task_ref: str
    native_run_ref: str
    cell_task_id: str
    task_identity_state: str
    checkpoint_id: str
    checkpoint_sha256: str
    manifest_sha256: str
    task_envelope_sha256: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise IsolationFamilyContractError("ProjectCell ProjectRef is malformed")
        _require_namespace(self.project_namespace)
        if self.cell_ref != f"project-cell://{self.project_namespace}":
            raise IsolationFamilyContractError("ProjectCell semantic reference is inconsistent")
        for value, label in ((self.native_task_ref, "native task"), (self.native_run_ref, "native run")):
            if not isinstance(value, str) or _REF.fullmatch(value) is None:
                raise IsolationFamilyContractError(f"{label} reference is malformed")
            if self.project_ref.value not in value:
                raise IsolationFamilyScopeError(f"{label} crossed Project scope")
        if self.task_identity_state not in {"UNVERIFIED", "SCOPED"}:
            raise IsolationFamilyContractError("ProjectCell task identity state is malformed")
        if not isinstance(self.cell_task_id, str) or not self.cell_task_id:
            raise IsolationFamilyContractError("ProjectCell task identity is missing")
        if not isinstance(self.checkpoint_id, str) or not self.checkpoint_id.startswith("chk_"):
            raise IsolationFamilyContractError("ProjectCell checkpoint identity is malformed")
        _sha(self.checkpoint_sha256, "checkpoint digest")
        _sha(self.manifest_sha256, "manifest digest")
        _sha(self.task_envelope_sha256, "task envelope digest")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "cell_ref": self.cell_ref,
            "cell_task_id": self.cell_task_id,
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_sha256": self.checkpoint_sha256,
            "manifest_sha256": self.manifest_sha256,
            "native_run_ref": self.native_run_ref,
            "native_task_ref": self.native_task_ref,
            "project_namespace": self.project_namespace,
            "project_ref": self.project_ref.value,
            "task_envelope_sha256": self.task_envelope_sha256,
            "task_identity_state": self.task_identity_state,
        }

    @classmethod
    def from_records(
        cls,
        manifest: Mapping[str, object],
        task_envelope: Mapping[str, object],
        checkpoint_pointer: Mapping[str, object],
        *,
        manifest_sha256: str,
        task_envelope_sha256: str,
    ) -> "ProjectCellIsolationBinding":
        for value in (manifest, task_envelope, checkpoint_pointer):
            if not isinstance(value, Mapping):
                raise IsolationFamilyContractError("ProjectCell evidence must be mappings")
            _scan_secret(value)
        project_id = _require_namespace(manifest.get("project_id"))
        if task_envelope.get("project_id") != project_id or checkpoint_pointer.get("project_id") != project_id:
            raise IsolationFamilyScopeError("ProjectCell records crossed Project namespace")
        binding = manifest.get("engine_binding")
        if not isinstance(binding, Mapping):
            raise IsolationFamilyContractError("ProjectCell native engine binding is missing")
        project_ref = _project_ref(binding.get("project_ref"), "native ProjectRef")
        native_task_ref = str(binding.get("task_ref") or "")
        native_run_ref = str(binding.get("run_ref") or "")
        run_id = str(task_envelope.get("run_id") or "")
        if not native_run_ref.endswith("/" + run_id):
            raise IsolationFamilyScopeError("ProjectCell Run identity differs from native binding")
        checkpoint_id = str(checkpoint_pointer.get("checkpoint_id") or "")
        if task_envelope.get("current_checkpoint_id") != checkpoint_id:
            raise IsolationFamilyScopeError("ProjectCell checkpoint pointer differs from task envelope")
        forbidden = task_envelope.get("forbidden_scope")
        if not isinstance(forbidden, Mapping) or forbidden.get("cross_project_cells") is not True:
            raise IsolationFamilyAuthorityError("cross-project access must remain forbidden")
        if forbidden.get("credentials_in_remote_context") is not True:
            raise IsolationFamilyAuthorityError("credential egress must remain forbidden")
        cell_task_id = str(task_envelope.get("task_id") or "")
        return cls(
            project_ref=project_ref,
            project_namespace=project_id,
            cell_ref=f"project-cell://{project_id}",
            native_task_ref=native_task_ref,
            native_run_ref=native_run_ref,
            cell_task_id=cell_task_id,
            task_identity_state="UNVERIFIED" if cell_task_id == "UNVERIFIED" else "SCOPED",
            checkpoint_id=checkpoint_id,
            checkpoint_sha256=_sha(checkpoint_pointer.get("checkpoint_sha256"), "checkpoint digest"),
            manifest_sha256=_sha(manifest_sha256, "manifest digest"),
            task_envelope_sha256=_sha(task_envelope_sha256, "task envelope digest"),
        )


@dataclass(frozen=True)
class IsolationFamilyReceipt:
    project_ref: ProjectRef
    project_namespace: str
    workspace_refs: tuple[WorkspaceRef, ...]
    runtime_refs: tuple[RuntimeRef, ...]
    project_cells: tuple[ProjectCellIsolationBinding, ...]
    evidence_refs: tuple[str, ...]
    created_at: str
    family_ref: str = field(init=False)
    progression_authority: bool = field(default=False, init=False)
    execution_authority: bool = field(default=False, init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_ref", f"isolation-family://{self.project_ref.value}")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "authority": "PROJECT",
            "evidence_refs": list(self.evidence_refs),
            "execution_authority": False,
            "family_ref": getattr(self, "family_ref", f"isolation-family://{self.project_ref.value}"),
            "implementation_plurality_preserved": True,
            "layers": {
                "isolated_runtime": [item.value for item in self.runtime_refs],
                "project_cell": [item.payload() | {"record_sha256": item.record_sha256} for item in self.project_cells],
                "workspace": [item.value for item in self.workspace_refs],
            },
            "progression_authority": False,
            "project_namespace": self.project_namespace,
            "project_ref": self.project_ref.value,
            "created_at": self.created_at,
        }


class IsolationFamilyService:
    """Persist immutable relation receipts without becoming an isolation controller."""

    progression_authority = False
    execution_authority = False

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
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
                CREATE TABLE IF NOT EXISTS isolation_family_receipts (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, idempotency_key)
                );
                CREATE TRIGGER IF NOT EXISTS isolation_family_receipts_no_update
                  BEFORE UPDATE ON isolation_family_receipts
                  BEGIN SELECT RAISE(ABORT, 'IsolationFamily receipt is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS isolation_family_receipts_no_delete
                  BEFORE DELETE ON isolation_family_receipts
                  BEGIN SELECT RAISE(ABORT, 'IsolationFamily receipt cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _workspaces(project_ref: ProjectRef, values: Sequence[WorkspaceRef]) -> tuple[WorkspaceRef, ...]:
        copied = tuple(values)
        if len(copied) > 256 or len(copied) != len(set(copied)):
            raise IsolationFamilyContractError("Workspace attachments are duplicated or unbounded")
        if any(not isinstance(item, WorkspaceRef) or item.project_ref != project_ref for item in copied):
            raise IsolationFamilyScopeError("Workspace attachment crossed Project boundary")
        return tuple(sorted(copied, key=lambda item: item.value))

    @staticmethod
    def _runtimes(project_ref: ProjectRef, values: Sequence[RuntimeRef]) -> tuple[RuntimeRef, ...]:
        copied = tuple(values)
        if len(copied) > 256 or len(copied) != len(set(copied)):
            raise IsolationFamilyContractError("Runtime attachments are duplicated or unbounded")
        if any(not isinstance(item, RuntimeRef) or item.project_ref != project_ref for item in copied):
            raise IsolationFamilyScopeError("Runtime attachment crossed Project boundary")
        return tuple(sorted(copied, key=lambda item: item.value))

    @staticmethod
    def _cells(
        project_ref: ProjectRef,
        namespace: str,
        values: Sequence[ProjectCellIsolationBinding],
    ) -> tuple[ProjectCellIsolationBinding, ...]:
        copied = tuple(values)
        if len(copied) > 256 or len(copied) != len(set(copied)):
            raise IsolationFamilyContractError("ProjectCell attachments are duplicated or unbounded")
        for item in copied:
            if not isinstance(item, ProjectCellIsolationBinding) or item.project_ref != project_ref:
                raise IsolationFamilyScopeError("ProjectCell attachment crossed Project boundary")
            if item.project_namespace != namespace:
                raise IsolationFamilyScopeError("ProjectCell namespace differs from native Project namespace")
        return tuple(sorted(copied, key=lambda item: item.cell_ref))

    def attach(
        self,
        access: ProjectAccess,
        *,
        workspace_refs: Sequence[WorkspaceRef] = (),
        runtime_refs: Sequence[RuntimeRef] = (),
        project_cells: Sequence[ProjectCellIsolationBinding] = (),
        evidence_refs: Sequence[str] = (),
        idempotency_key: str,
    ) -> IsolationFamilyReceipt:
        if not isinstance(access, ProjectAccess):
            raise IsolationFamilyContractError("Project access is required")
        key = _key(idempotency_key)
        project = self.projects.get_project(access, access.project_ref)
        project_ref = project.project_ref
        workspaces = self._workspaces(project_ref, workspace_refs)
        runtimes = self._runtimes(project_ref, runtime_refs)
        cells = self._cells(project_ref, project.namespace, project_cells)
        evidence = _evidence_refs(evidence_refs)
        if not workspaces and not runtimes and not cells:
            raise IsolationFamilyContractError("isolation family requires at least one realization")
        semantic = {
            "authority": "PROJECT",
            "evidence_refs": list(evidence),
            "execution_authority": False,
            "family_ref": f"isolation-family://{project_ref.value}",
            "implementation_plurality_preserved": True,
            "layers": {
                "isolated_runtime": [item.value for item in runtimes],
                "project_cell": [item.payload() | {"record_sha256": item.record_sha256} for item in cells],
                "workspace": [item.value for item in workspaces],
            },
            "progression_authority": False,
            "project_namespace": project.namespace,
            "project_ref": project_ref.value,
        }
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT receipt_json,receipt_sha256 FROM isolation_family_receipts WHERE project_id=? AND idempotency_key=?",
                (project_ref.value, key),
            ).fetchone()
            if row is not None:
                try:
                    stored = json.loads(cast(str, row["receipt_json"]))
                except json.JSONDecodeError as exc:
                    raise IsolationFamilyIntegrityError("persisted isolation-family receipt JSON is malformed") from exc
                if not isinstance(stored, dict):
                    raise IsolationFamilyIntegrityError("persisted isolation-family receipt is malformed")
                stored_semantic = {key_name: value for key_name, value in stored.items() if key_name != "created_at"}
                if not hmac.compare_digest(_digest(stored_semantic), _digest(semantic)):
                    raise IsolationFamilyConflictError("idempotency key already binds different isolation evidence")
                receipt = IsolationFamilyReceipt(
                    project_ref, project.namespace, workspaces, runtimes, cells, evidence,
                    str(stored.get("created_at") or ""),
                )
                if not hmac.compare_digest(receipt.record_sha256, cast(str, row["receipt_sha256"])):
                    raise IsolationFamilyIntegrityError("persisted isolation-family receipt digest differs")
                if _canonical(receipt.payload()) != cast(str, row["receipt_json"]):
                    raise IsolationFamilyIntegrityError("persisted isolation-family receipt readback differs")
                connection.commit()
                return receipt
            created_at = cast(str, connection.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')"
            ).fetchone()[0])
            receipt = IsolationFamilyReceipt(
                project_ref, project.namespace, workspaces, runtimes, cells, evidence, created_at,
            )
            serialized = _canonical(receipt.payload())
            connection.execute(
                "INSERT INTO isolation_family_receipts(project_id,idempotency_key,receipt_json,receipt_sha256) VALUES (?,?,?,?)",
                (project_ref.value, key, serialized, receipt.record_sha256),
            )
            connection.commit()
            return receipt
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


MiniTZIsolationFamily = IsolationFamilyService


__all__ = [
    "IsolationFamilyAuthorityError",
    "IsolationFamilyConflictError",
    "IsolationFamilyContractError",
    "IsolationFamilyError",
    "IsolationFamilyIntegrityError",
    "IsolationFamilyReceipt",
    "IsolationFamilyScopeError",
    "IsolationFamilyService",
    "MiniTZIsolationFamily",
    "ProjectCellIsolationBinding",
]
