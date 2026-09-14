"""Provider-neutral, durable semantic Capability contracts for P0-03."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast


_CAPABILITY_ID_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+"
)
_SEMANTIC_VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
)
_CONTRACT_ROLE_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_ABSOLUTE_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SIDE_EFFECT_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+"
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class CapabilityError(Exception):
    """Base class for Capability contract failures."""


class CapabilityContractError(CapabilityError):
    """A semantic Capability contract is malformed."""


class CapabilityConflictError(CapabilityError):
    """An immutable Capability version conflicts with an existing contract."""


class CapabilityNotFoundError(CapabilityError):
    """A requested CapabilityRef has no durable semantic contract."""


class CapabilityIntegrityError(CapabilityError):
    """Persisted Capability evidence is malformed or has been changed."""


def _validate_capability_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or _CAPABILITY_ID_PATTERN.fullmatch(value) is None
    ):
        raise CapabilityContractError("Capability identity must be namespaced text")
    return value


def _validate_version(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 64
        or _SEMANTIC_VERSION_PATTERN.fullmatch(value) is None
    ):
        raise CapabilityContractError("Capability version must be semantic x.y.z")
    return value


def _version_key(version: str) -> tuple[int, int, int]:
    matched = _SEMANTIC_VERSION_PATTERN.fullmatch(version)
    if matched is None:
        raise CapabilityIntegrityError("Persisted Capability version is malformed")
    major, minor, patch = matched.groups()
    return (int(major), int(minor), int(patch))


def _validate_description(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 2048
        or any(ord(character) < 32 and character not in "\n\t" for character in value)
    ):
        raise CapabilityContractError("Capability description is malformed or unbounded")
    return value


def _validate_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise CapabilityContractError(f"{field_name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CapabilityContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CapabilityContractError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return value


def _freeze_contract(
    value: Mapping[str, str],
    field_name: str,
) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise CapabilityContractError(f"{field_name} must be a mapping")
    copied = dict(value)
    if len(copied) > 64:
        raise CapabilityContractError(f"{field_name} exceeds 64 roles")
    for role, contract_ref in copied.items():
        if (
            not isinstance(role, str)
            or _CONTRACT_ROLE_PATTERN.fullmatch(role) is None
        ):
            raise CapabilityContractError(f"{field_name} role is malformed")
        if (
            not isinstance(contract_ref, str)
            or len(contract_ref) > 576
            or _ABSOLUTE_REF_PATTERN.fullmatch(contract_ref) is None
        ):
            raise CapabilityContractError(
                f"{field_name} value must be a bounded absolute contract reference"
            )
    return MappingProxyType(copied)


def _freeze_side_effects(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CapabilityContractError("side_effects must be a sequence")
    copied = tuple(value)
    if len(copied) > 32 or len(set(copied)) != len(copied):
        raise CapabilityContractError("side_effects are duplicated or unbounded")
    for side_effect in copied:
        if (
            not isinstance(side_effect, str)
            or len(side_effect) > 128
            or _SIDE_EFFECT_PATTERN.fullmatch(side_effect) is None
        ):
            raise CapabilityContractError("side_effect identity is malformed")
    return tuple(sorted(copied))


@dataclass(frozen=True, order=True)
class CapabilityRef:
    """Stable namespaced semantic identity and explicit immutable version."""

    capability_id: str
    version: str

    def __post_init__(self) -> None:
        _validate_capability_id(self.capability_id)
        _validate_version(self.version)

    @property
    def namespace(self) -> str:
        return self.capability_id.split(".", 1)[0]

    @property
    def name(self) -> str:
        return self.capability_id.split(".", 1)[1]

    @property
    def value(self) -> str:
        return f"{self.capability_id}@{self.version}"


@dataclass(frozen=True)
class Capability:
    """Immutable semantic ability, independent from any physical executor."""

    capability_ref: CapabilityRef
    description: str
    input_contract: Mapping[str, str] = field(default_factory=dict)
    output_contract: Mapping[str, str] = field(default_factory=dict)
    side_effects: tuple[str, ...] = ()
    created_at: str = field(default_factory=_now_utc)
    deprecated: bool = False
    superseded_by: CapabilityRef | None = None
    contract_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        _validate_description(self.description)
        _validate_timestamp(self.created_at, "created_at")
        if not isinstance(self.deprecated, bool):
            raise CapabilityContractError("deprecated must be boolean")
        if self.superseded_by is not None and not isinstance(
            self.superseded_by,
            CapabilityRef,
        ):
            raise TypeError("superseded_by must be CapabilityRef")
        if self.superseded_by is not None and not self.deprecated:
            raise CapabilityContractError("supersession requires deprecation")
        object.__setattr__(
            self,
            "input_contract",
            _freeze_contract(self.input_contract, "input_contract"),
        )
        object.__setattr__(
            self,
            "output_contract",
            _freeze_contract(self.output_contract, "output_contract"),
        )
        object.__setattr__(self, "side_effects", _freeze_side_effects(self.side_effects))
        object.__setattr__(self, "contract_sha256", self._semantic_digest())

    @property
    def capability_id(self) -> str:
        return self.capability_ref.capability_id

    @property
    def namespace(self) -> str:
        return self.capability_ref.namespace

    @property
    def name(self) -> str:
        return self.capability_ref.name

    @property
    def version(self) -> str:
        return self.capability_ref.version

    def _semantic_digest(self) -> str:
        canonical = json.dumps(
            {
                "capability_id": self.capability_id,
                "description": self.description,
                "input_contract": dict(self.input_contract),
                "output_contract": dict(self.output_contract),
                "side_effects": list(self.side_effects),
                "version": self.version,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class CapabilityLifecycle:
    """Append-only lifecycle evidence that never rewrites semantic contracts."""

    event_id: int
    capability_ref: CapabilityRef
    event_type: str
    superseded_by: CapabilityRef | None
    created_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, int) or self.event_id <= 0:
            raise CapabilityIntegrityError("Capability lifecycle event ID is malformed")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        if self.event_type != "deprecated":
            raise CapabilityIntegrityError("Capability lifecycle event type is malformed")
        if self.superseded_by is not None and not isinstance(
            self.superseded_by,
            CapabilityRef,
        ):
            raise TypeError("superseded_by must be CapabilityRef")
        try:
            _validate_timestamp(self.created_at, "created_at")
        except CapabilityContractError as exc:
            raise CapabilityIntegrityError(str(exc)) from exc


class CapabilityRegistry:
    """Durable data-driven registry for immutable semantic Capability versions."""

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
                CREATE TABLE IF NOT EXISTS capabilities (
                    namespace TEXT NOT NULL,
                    name TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    description TEXT NOT NULL,
                    input_contract_json TEXT NOT NULL,
                    output_contract_json TEXT NOT NULL,
                    side_effects_json TEXT NOT NULL,
                    contract_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (capability_id, version),
                    UNIQUE (namespace, name, version)
                );

                CREATE INDEX IF NOT EXISTS capabilities_namespace_name
                    ON capabilities(namespace, name);

                CREATE TABLE IF NOT EXISTS capability_lifecycle (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type = 'deprecated'),
                    superseded_by_id TEXT,
                    superseded_by_version TEXT,
                    created_at TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL,
                    UNIQUE (capability_id, version, event_type),
                    CHECK (
                        (superseded_by_id IS NULL AND superseded_by_version IS NULL)
                        OR
                        (superseded_by_id IS NOT NULL AND superseded_by_version IS NOT NULL)
                    ),
                    FOREIGN KEY (capability_id, version)
                        REFERENCES capabilities(capability_id, version) ON DELETE RESTRICT,
                    FOREIGN KEY (superseded_by_id, superseded_by_version)
                        REFERENCES capabilities(capability_id, version) ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS capabilities_no_update
                BEFORE UPDATE ON capabilities
                BEGIN
                    SELECT RAISE(ABORT, 'Capability records are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS capabilities_no_delete
                BEFORE DELETE ON capabilities
                BEGIN
                    SELECT RAISE(ABORT, 'Capability history cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS capability_lifecycle_no_update
                BEFORE UPDATE ON capability_lifecycle
                BEGIN
                    SELECT RAISE(ABORT, 'Capability lifecycle evidence is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS capability_lifecycle_no_delete
                BEFORE DELETE ON capability_lifecycle
                BEGIN
                    SELECT RAISE(ABORT, 'Capability lifecycle history cannot be deleted');
                END;
                """
            )
        finally:
            connection.close()

    def register(self, capability: Capability) -> Capability:
        if not isinstance(capability, Capability):
            raise TypeError("Capability is required")
        if capability.deprecated or capability.superseded_by is not None:
            raise CapabilityContractError(
                "Lifecycle state must be recorded through the registry"
            )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            registered = self._register_with_connection(connection, capability)
            connection.commit()
            return registered
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _register_with_connection(
        self,
        connection: sqlite3.Connection,
        capability: Capability,
    ) -> Capability:
        """Register on an existing transaction owned by a composite registry."""

        if not isinstance(capability, Capability):
            raise TypeError("Capability is required")
        if capability.deprecated or capability.superseded_by is not None:
            raise CapabilityContractError(
                "Lifecycle state must be recorded through the registry"
            )
        existing_row = connection.execute(
            """
            SELECT * FROM capabilities
            WHERE capability_id = ? AND version = ?
            """,
            (capability.capability_id, capability.version),
        ).fetchone()
        if existing_row is not None:
            existing = self._capability_from_row(connection, existing_row)
            if not hmac.compare_digest(
                existing.contract_sha256,
                capability.contract_sha256,
            ):
                raise CapabilityConflictError(
                    "Capability version already has a different immutable contract"
                )
            return existing
        connection.execute(
            """
            INSERT INTO capabilities (
                namespace,
                name,
                capability_id,
                version,
                description,
                input_contract_json,
                output_contract_json,
                side_effects_json,
                contract_sha256,
                record_sha256,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capability.namespace,
                capability.name,
                capability.capability_id,
                capability.version,
                capability.description,
                self._serialize_mapping(capability.input_contract),
                self._serialize_mapping(capability.output_contract),
                self._serialize_sequence(capability.side_effects),
                capability.contract_sha256,
                self._record_sha256(capability),
                capability.created_at,
            ),
        )
        self._after_capability_insert(connection, capability)
        return capability

    def _after_capability_insert(
        self,
        connection: sqlite3.Connection,
        capability: Capability,
    ) -> None:
        del connection, capability

    def get(self, capability_ref: CapabilityRef) -> Capability:
        connection = self._connect()
        try:
            return self._get_with_connection(connection, capability_ref)
        finally:
            connection.close()

    def _get_with_connection(
        self,
        connection: sqlite3.Connection,
        capability_ref: CapabilityRef,
    ) -> Capability:
        """Read and verify one Capability inside a caller-owned transaction."""

        self._require_ref(capability_ref)
        row = self._fetch_row(connection, capability_ref)
        return self._capability_from_row(connection, row)

    def list_versions(self, capability_id: str) -> tuple[Capability, ...]:
        validated_id = _validate_capability_id(capability_id)
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM capabilities WHERE capability_id = ?",
                (validated_id,),
            ).fetchall()
            capabilities = [
                self._capability_from_row(connection, row) for row in rows
            ]
            return tuple(sorted(capabilities, key=lambda item: _version_key(item.version)))
        finally:
            connection.close()

    def deprecate(
        self,
        capability_ref: CapabilityRef,
        *,
        superseded_by: CapabilityRef | None = None,
    ) -> Capability:
        self._require_ref(capability_ref)
        if superseded_by is not None:
            self._require_ref(superseded_by)
            if superseded_by == capability_ref:
                raise CapabilityContractError("Capability cannot supersede itself")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            base = self._capability_from_row(
                connection,
                self._fetch_row(connection, capability_ref),
            )
            if superseded_by is not None:
                self._capability_from_row(
                    connection,
                    self._fetch_row(connection, superseded_by),
                )
            existing = connection.execute(
                """
                SELECT * FROM capability_lifecycle
                WHERE capability_id = ? AND version = ? AND event_type = 'deprecated'
                """,
                (capability_ref.capability_id, capability_ref.version),
            ).fetchone()
            if existing is not None:
                event = self._lifecycle_from_row(existing)
                if event.superseded_by != superseded_by:
                    raise CapabilityConflictError(
                        "Capability lifecycle already has different immutable evidence"
                    )
                connection.commit()
                return replace(
                    base,
                    deprecated=True,
                    superseded_by=event.superseded_by,
                )
            lifecycle_created_at = _now_utc()
            connection.execute(
                """
                INSERT INTO capability_lifecycle (
                    capability_id,
                    version,
                    event_type,
                    superseded_by_id,
                    superseded_by_version,
                    created_at,
                    event_sha256
                ) VALUES (?, ?, 'deprecated', ?, ?, ?, ?)
                """,
                (
                    capability_ref.capability_id,
                    capability_ref.version,
                    None if superseded_by is None else superseded_by.capability_id,
                    None if superseded_by is None else superseded_by.version,
                    lifecycle_created_at,
                    self._lifecycle_sha256(
                        capability_ref,
                        "deprecated",
                        superseded_by,
                        lifecycle_created_at,
                    ),
                ),
            )
            connection.commit()
            return replace(base, deprecated=True, superseded_by=superseded_by)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def lifecycle_history(
        self,
        capability_ref: CapabilityRef,
    ) -> tuple[CapabilityLifecycle, ...]:
        self._require_ref(capability_ref)
        connection = self._connect()
        try:
            self._capability_from_row(
                connection,
                self._fetch_row(connection, capability_ref),
            )
            rows = connection.execute(
                """
                SELECT * FROM capability_lifecycle
                WHERE capability_id = ? AND version = ?
                ORDER BY event_id
                """,
                (capability_ref.capability_id, capability_ref.version),
            ).fetchall()
            return tuple(self._lifecycle_from_row(row) for row in rows)
        finally:
            connection.close()

    def schema_fingerprint(self) -> str:
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT type, name, sql FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()
        finally:
            connection.close()
        canonical = json.dumps(
            [tuple(row) for row in rows],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _serialize_mapping(value: Mapping[str, str]) -> str:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _serialize_sequence(value: Sequence[str]) -> str:
        return json.dumps(
            list(value),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def _record_sha256(cls, capability: Capability) -> str:
        canonical = json.dumps(
            {
                "capability_id": capability.capability_id,
                "contract_sha256": capability.contract_sha256,
                "created_at": capability.created_at,
                "description": capability.description,
                "input_contract": dict(capability.input_contract),
                "name": capability.name,
                "namespace": capability.namespace,
                "output_contract": dict(capability.output_contract),
                "side_effects": list(capability.side_effects),
                "version": capability.version,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _lifecycle_sha256(
        capability_ref: CapabilityRef,
        event_type: str,
        superseded_by: CapabilityRef | None,
        created_at: str,
    ) -> str:
        canonical = json.dumps(
            {
                "capability_ref": capability_ref.value,
                "created_at": created_at,
                "event_type": event_type,
                "superseded_by": (
                    None if superseded_by is None else superseded_by.value
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _deserialize_mapping(value: object, field_name: str) -> Mapping[str, str]:
        if not isinstance(value, str):
            raise CapabilityIntegrityError(f"{field_name} is not serialized text")
        try:
            decoded = cast(object, json.loads(value))
        except json.JSONDecodeError as exc:
            raise CapabilityIntegrityError(f"{field_name} is malformed") from exc
        if not isinstance(decoded, dict):
            raise CapabilityIntegrityError(f"{field_name} is malformed")
        return cast(Mapping[str, str], decoded)

    @staticmethod
    def _deserialize_sequence(value: object, field_name: str) -> tuple[str, ...]:
        if not isinstance(value, str):
            raise CapabilityIntegrityError(f"{field_name} is not serialized text")
        try:
            decoded = cast(object, json.loads(value))
        except json.JSONDecodeError as exc:
            raise CapabilityIntegrityError(f"{field_name} is malformed") from exc
        if not isinstance(decoded, list):
            raise CapabilityIntegrityError(f"{field_name} is malformed")
        return tuple(cast(list[str], decoded))

    def _capability_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> Capability:
        try:
            capability_ref = CapabilityRef(
                cast(str, row["capability_id"]),
                cast(str, row["version"]),
            )
            if (
                row["namespace"] != capability_ref.namespace
                or row["name"] != capability_ref.name
            ):
                raise CapabilityIntegrityError(
                    "Persisted Capability namespace does not match identity"
                )
            base = Capability(
                capability_ref=capability_ref,
                description=cast(str, row["description"]),
                input_contract=self._deserialize_mapping(
                    row["input_contract_json"],
                    "input_contract_json",
                ),
                output_contract=self._deserialize_mapping(
                    row["output_contract_json"],
                    "output_contract_json",
                ),
                side_effects=self._deserialize_sequence(
                    row["side_effects_json"],
                    "side_effects_json",
                ),
                created_at=cast(str, row["created_at"]),
            )
        except CapabilityIntegrityError:
            raise
        except (CapabilityContractError, TypeError, KeyError) as exc:
            raise CapabilityIntegrityError(
                "Persisted Capability contract is malformed"
            ) from exc
        persisted_digest = row["contract_sha256"]
        if (
            not isinstance(persisted_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_digest) is None
            or not hmac.compare_digest(base.contract_sha256, persisted_digest)
        ):
            raise CapabilityIntegrityError(
                "Persisted Capability contract digest verification failed"
            )
        persisted_record_digest = row["record_sha256"]
        if (
            not isinstance(persisted_record_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_record_digest) is None
            or not hmac.compare_digest(
                self._record_sha256(base),
                persisted_record_digest,
            )
        ):
            raise CapabilityIntegrityError(
                "Persisted Capability record digest verification failed"
            )
        lifecycle_row = connection.execute(
            """
            SELECT * FROM capability_lifecycle
            WHERE capability_id = ? AND version = ? AND event_type = 'deprecated'
            """,
            (capability_ref.capability_id, capability_ref.version),
        ).fetchone()
        if lifecycle_row is None:
            return base
        event = self._lifecycle_from_row(lifecycle_row)
        if event.capability_ref != capability_ref:
            raise CapabilityIntegrityError(
                "Persisted Capability lifecycle identity is inconsistent"
            )
        if event.superseded_by == capability_ref:
            raise CapabilityIntegrityError(
                "Persisted Capability cannot supersede itself"
            )
        if event.superseded_by is not None:
            try:
                self._fetch_row(connection, event.superseded_by)
            except CapabilityNotFoundError as exc:
                raise CapabilityIntegrityError(
                    "Persisted Capability successor does not exist"
                ) from exc
        return replace(base, deprecated=True, superseded_by=event.superseded_by)

    @classmethod
    def _lifecycle_from_row(cls, row: sqlite3.Row) -> CapabilityLifecycle:
        successor_id = row["superseded_by_id"]
        successor_version = row["superseded_by_version"]
        if (successor_id is None) != (successor_version is None):
            raise CapabilityIntegrityError(
                "Persisted Capability supersession reference is incomplete"
            )
        try:
            event = CapabilityLifecycle(
                event_id=cast(int, row["event_id"]),
                capability_ref=CapabilityRef(
                    cast(str, row["capability_id"]),
                    cast(str, row["version"]),
                ),
                event_type=cast(str, row["event_type"]),
                superseded_by=(
                    None
                    if successor_id is None
                    else CapabilityRef(
                        cast(str, successor_id),
                        cast(str, successor_version),
                    )
                ),
                created_at=cast(str, row["created_at"]),
            )
        except (CapabilityContractError, TypeError) as exc:
            raise CapabilityIntegrityError(
                "Persisted Capability lifecycle evidence is malformed"
            ) from exc
        persisted_event_digest = row["event_sha256"]
        if (
            not isinstance(persisted_event_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_event_digest) is None
            or not hmac.compare_digest(
                cls._lifecycle_sha256(
                    event.capability_ref,
                    event.event_type,
                    event.superseded_by,
                    event.created_at,
                ),
                persisted_event_digest,
            )
        ):
            raise CapabilityIntegrityError(
                "Persisted Capability lifecycle digest verification failed"
            )
        return event

    @staticmethod
    def _require_ref(value: object) -> CapabilityRef:
        if not isinstance(value, CapabilityRef):
            raise TypeError("CapabilityRef is required")
        return value

    @staticmethod
    def _fetch_row(
        connection: sqlite3.Connection,
        capability_ref: CapabilityRef,
    ) -> sqlite3.Row:
        row = cast(
            sqlite3.Row | None,
            connection.execute(
                """
                SELECT * FROM capabilities
                WHERE capability_id = ? AND version = ?
                """,
                (capability_ref.capability_id, capability_ref.version),
            ).fetchone(),
        )
        if row is None:
            raise CapabilityNotFoundError("CapabilityRef not found")
        return row
