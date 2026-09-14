"""Migration quarantine and normalization contracts for P0-01."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Mapping, cast


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_identity_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MigrationProvenanceError(f"{field_name} must be a non-empty string")
    return value


def _require_timestamp(value: object, field_name: str) -> str:
    timestamp = _require_identity_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise MigrationProvenanceError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MigrationProvenanceError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        )
    return timestamp


def _freeze_metadata(metadata: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(metadata, Mapping):
        raise MigrationProvenanceError("immutable_metadata must be a mapping")
    copied = dict(metadata)
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in copied.items()):
        raise MigrationProvenanceError("immutable_metadata keys and values must be strings")
    return MappingProxyType(copied)


def _metadata_digest(metadata: Mapping[str, str]) -> str:
    encoded = json.dumps(
        dict(metadata),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _canonical_record_bytes(record: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(record),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _write_once(path: Path, payload: bytes) -> bool:
    """Atomically publish immutable bytes without replacing an existing path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            return False
        try:
            directory_descriptor = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return True
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return True
    finally:
        temporary_path.unlink(missing_ok=True)


class MigrationError(Exception):
    """Base class for migration pipeline errors."""


class MigrationIntegrityError(MigrationError):
    """Digest/provenance integrity failure in migration artifacts."""


class MigrationProvenanceError(MigrationError):
    """Required provenance fields are missing or malformed."""


class MigrationClassificationError(MigrationError):
    """Migration classification is missing, malformed, or invalid."""


class MigrationClassification(str, Enum):
    UNIVERSAL_GOOD = "UNIVERSAL_GOOD"
    UNIVERSAL_REWRITE = "UNIVERSAL_REWRITE"
    PROJECT_SPECIFIC = "PROJECT_SPECIFIC"
    HISTORICAL_EVIDENCE = "HISTORICAL_EVIDENCE"
    DUPLICATE = "DUPLICATE"
    OBSOLETE_OR_DRIFT = "OBSOLETE_OR_DRIFT"


def normalize_classification(value: str | MigrationClassification | None) -> MigrationClassification:
    if value is None:
        raise MigrationClassificationError("Classification is required for normalization")
    if isinstance(value, MigrationClassification):
        return value
    try:
        return MigrationClassification(value)
    except ValueError as exc:
        raise MigrationClassificationError(f"Invalid migration classification: {value}") from exc


@dataclass(frozen=True)
class MigrationSource:
    """Raw historical source and immutable provenance required for migration."""

    raw_bytes: bytes | bytearray
    source_locator: str
    source_type: str
    source_manifest_identity: str | None = None
    acquisition_time: str = field(default_factory=_now_utc)
    immutable_metadata: Mapping[str, str] = field(default_factory=dict)
    expected_raw_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.raw_bytes, (bytes, bytearray)):
            raise MigrationProvenanceError("raw_bytes must be bytes-like")
        object.__setattr__(self, "raw_bytes", bytes(self.raw_bytes))
        _require_identity_text(self.source_locator, "source_locator")
        _require_identity_text(self.source_type, "source_type")
        _require_timestamp(self.acquisition_time, "acquisition_time")
        if self.source_manifest_identity is not None:
            _require_identity_text(
                self.source_manifest_identity,
                "source_manifest_identity",
            )
        object.__setattr__(
            self,
            "immutable_metadata",
            _freeze_metadata(self.immutable_metadata),
        )
        if self.expected_raw_sha256 is not None:
            expected = self.expected_raw_sha256.lower()
            if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
                raise MigrationIntegrityError("expected_raw_sha256 must be a SHA-256 hex digest")
            if expected != self.raw_sha256:
                raise MigrationIntegrityError(
                    "expected_raw_sha256 does not match raw source digest"
                )
            object.__setattr__(self, "expected_raw_sha256", expected)

    @property
    def raw_sha256(self) -> str:
        return sha256(self.raw_bytes).hexdigest()


@dataclass(frozen=True)
class QuarantineRef:
    """Opaque reference for raw historical bytes; not a normal runtime artifact."""

    raw_sha256: str
    source_locator: str
    source_type: str
    source_manifest_identity: str | None
    byte_size: int
    acquisition_time: str
    immutable_metadata: Mapping[str, str]
    created_at: str = field(default_factory=_now_utc)

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256) is None:
            raise MigrationIntegrityError("raw_sha256 must be a lowercase SHA-256 hex digest")
        _require_identity_text(self.source_locator, "source_locator")
        _require_identity_text(self.source_type, "source_type")
        _require_timestamp(self.acquisition_time, "acquisition_time")
        _require_timestamp(self.created_at, "created_at")
        if self.source_manifest_identity is not None:
            _require_identity_text(
                self.source_manifest_identity,
                "source_manifest_identity",
            )
        if not isinstance(self.byte_size, int) or self.byte_size < 0:
            raise MigrationProvenanceError("byte_size must be a non-negative integer")
        object.__setattr__(
            self,
            "immutable_metadata",
            _freeze_metadata(self.immutable_metadata),
        )

    def identity_key(self) -> str:
        identity = json.dumps(
            {
                "raw_sha256": self.raw_sha256,
                "source_locator": self.source_locator,
                "source_manifest_identity": self.source_manifest_identity,
                "source_type": self.source_type,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return sha256(identity).hexdigest()


@dataclass(frozen=True)
class SemanticExtraction:
    """Meaning-only extraction output from quarantined bytes."""

    source_ref: QuarantineRef
    extracted_text: str
    source_type: str
    extracted_at: str = field(default_factory=_now_utc)

    def __post_init__(self) -> None:
        if not isinstance(self.source_ref, QuarantineRef):
            raise MigrationIntegrityError("source_ref must be a QuarantineRef")
        if not isinstance(self.extracted_text, str):
            raise MigrationIntegrityError("extracted_text must be a string")
        if self.source_type != self.source_ref.source_type:
            raise MigrationProvenanceError("extraction source_type does not match source_ref")
        _require_timestamp(self.extracted_at, "extracted_at")


def _provenance_for(source_ref: QuarantineRef) -> Mapping[str, str]:
    return MappingProxyType(
        {
            "source_identity_key": source_ref.identity_key(),
            "source_locator": source_ref.source_locator,
            "raw_sha256": source_ref.raw_sha256,
            "source_type": source_ref.source_type,
            "source_manifest_identity": source_ref.source_manifest_identity or "",
            "acquisition_time": source_ref.acquisition_time,
            "immutable_metadata_sha256": _metadata_digest(source_ref.immutable_metadata),
        }
    )


@dataclass(frozen=True, init=False)
class NormalizedMigrationCandidate:
    """Normalized candidate with immutable provenance and explicit classification."""

    source_ref: QuarantineRef
    classification: MigrationClassification
    normalized_text: str
    provenance_chain: Mapping[str, str]
    normalized_at: str = field(default_factory=_now_utc)
    candidate_id: str = field(init=False)

    def __new__(cls, *args: object, **kwargs: object) -> "NormalizedMigrationCandidate":
        raise MigrationIntegrityError(
            "NormalizedMigrationCandidate must be created by verified quarantine normalization"
        )

    def __post_init__(self) -> None:
        if not isinstance(self.source_ref, QuarantineRef):
            raise MigrationIntegrityError("source_ref must be a QuarantineRef")
        if not isinstance(self.normalized_text, str) or not self.normalized_text.strip():
            raise MigrationProvenanceError("normalized_text is required")
        if not isinstance(self.provenance_chain, Mapping) or not self.provenance_chain:
            raise MigrationProvenanceError("provenance_chain is required")
        classification = normalize_classification(self.classification)
        expected_provenance = _provenance_for(self.source_ref)
        for field_name, expected_value in expected_provenance.items():
            if self.provenance_chain.get(field_name) != expected_value:
                raise MigrationProvenanceError(
                    f"provenance_chain field does not match source_ref: {field_name}"
                )
        object.__setattr__(self, "classification", classification)
        object.__setattr__(
            self,
            "provenance_chain",
            MappingProxyType(dict(self.provenance_chain)),
        )
        object.__setattr__(
            self,
            "candidate_id",
            self._build_candidate_id(),
        )
        _require_timestamp(self.normalized_at, "normalized_at")

    def _build_candidate_id(self) -> str:
        payload = (
            f"{self.source_ref.identity_key()}|"
            f"{self.classification.value}|{self.normalized_text}"
        ).encode("utf-8")
        return sha256(payload).hexdigest()


class MigrationQuarantine:
    """Durable content-addressed quarantine for raw migration sources."""

    _record_schema = "minitz.quarantine_ref/v1"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self._objects_root = self.root / "objects"
        self._refs_root = self.root / "refs"
        self._objects_root.mkdir(parents=True, exist_ok=True)
        self._refs_root.mkdir(parents=True, exist_ok=True)

    def _object_path(self, raw_sha256: str) -> Path:
        return self._objects_root / raw_sha256[:2] / f"{raw_sha256}.bin"

    def _ref_path(self, identity_key: str) -> Path:
        return self._refs_root / f"{identity_key}.json"

    def _serialize_ref(self, source_ref: QuarantineRef) -> bytes:
        record: dict[str, object] = {
            "schema": self._record_schema,
            "identity_key": source_ref.identity_key(),
            "raw_sha256": source_ref.raw_sha256,
            "source_locator": source_ref.source_locator,
            "source_type": source_ref.source_type,
            "source_manifest_identity": source_ref.source_manifest_identity,
            "byte_size": source_ref.byte_size,
            "acquisition_time": source_ref.acquisition_time,
            "immutable_metadata": dict(source_ref.immutable_metadata),
            "created_at": source_ref.created_at,
        }
        record["record_sha256"] = sha256(_canonical_record_bytes(record)).hexdigest()
        return _canonical_record_bytes(record) + b"\n"

    def _load_ref(self, identity_key: str) -> QuarantineRef:
        ref_path = self._ref_path(identity_key)
        try:
            raw_record = cast(object, json.loads(ref_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise MigrationIntegrityError("Quarantine reference metadata is unreadable") from exc
        if not isinstance(raw_record, dict):
            raise MigrationIntegrityError("Quarantine reference metadata is malformed")
        record = cast(Mapping[str, object], raw_record)
        record_sha256 = record.get("record_sha256")
        if not isinstance(record_sha256, str) or re.fullmatch(
            r"[0-9a-f]{64}",
            record_sha256,
        ) is None:
            raise MigrationIntegrityError("Quarantine reference record digest is malformed")
        unsigned_record = {
            key: value
            for key, value in record.items()
            if key != "record_sha256"
        }
        if sha256(_canonical_record_bytes(unsigned_record)).hexdigest() != record_sha256:
            raise MigrationIntegrityError("Quarantine reference record digest mismatch")
        if record.get("schema") != self._record_schema:
            raise MigrationIntegrityError("Unsupported quarantine reference schema")
        if record.get("identity_key") != identity_key:
            raise MigrationIntegrityError("Quarantine reference identity mismatch")

        source_manifest_identity = record.get("source_manifest_identity")
        if source_manifest_identity is not None and not isinstance(
            source_manifest_identity,
            str,
        ):
            raise MigrationIntegrityError("Quarantine manifest identity is malformed")
        immutable_metadata = record.get("immutable_metadata")
        if not isinstance(immutable_metadata, Mapping):
            raise MigrationIntegrityError("Quarantine immutable metadata is malformed")

        try:
            source_ref = QuarantineRef(
                raw_sha256=cast(str, record["raw_sha256"]),
                source_locator=cast(str, record["source_locator"]),
                source_type=cast(str, record["source_type"]),
                source_manifest_identity=source_manifest_identity,
                byte_size=cast(int, record["byte_size"]),
                acquisition_time=cast(str, record["acquisition_time"]),
                immutable_metadata=cast(Mapping[str, str], immutable_metadata),
                created_at=cast(str, record["created_at"]),
            )
        except (KeyError, TypeError, MigrationError) as exc:
            raise MigrationIntegrityError("Quarantine reference metadata is malformed") from exc
        if source_ref.identity_key() != identity_key:
            raise MigrationIntegrityError("Quarantine reference identity does not verify")
        return source_ref

    def _read_verified_object(self, source_ref: QuarantineRef) -> bytes:
        object_path = self._object_path(source_ref.raw_sha256)
        try:
            raw_bytes = object_path.read_bytes()
        except OSError as exc:
            raise MigrationIntegrityError("Quarantined bytes are unavailable") from exc
        if len(raw_bytes) != source_ref.byte_size:
            raise MigrationIntegrityError("Quarantined byte size mismatch")
        if sha256(raw_bytes).hexdigest() != source_ref.raw_sha256:
            raise MigrationIntegrityError("Digest mismatch")
        return raw_bytes

    def ingest(self, source: MigrationSource) -> QuarantineRef:
        if not isinstance(source, MigrationSource):
            raise TypeError("source must be MigrationSource")
        ref = QuarantineRef(
            raw_sha256=source.raw_sha256,
            source_locator=source.source_locator,
            source_type=source.source_type,
            source_manifest_identity=source.source_manifest_identity,
            byte_size=len(source.raw_bytes),
            acquisition_time=source.acquisition_time,
            immutable_metadata=source.immutable_metadata,
        )

        identity_key = ref.identity_key()
        object_path = self._object_path(ref.raw_sha256)
        _write_once(object_path, bytes(source.raw_bytes))

        stored_bytes = self._read_verified_object(ref)
        if stored_bytes != source.raw_bytes:
            raise MigrationIntegrityError("Stored quarantine bytes do not match source")

        ref_path = self._ref_path(identity_key)
        _write_once(ref_path, self._serialize_ref(ref))
        stored_ref = self._load_ref(identity_key)
        if stored_ref.immutable_metadata != source.immutable_metadata:
            raise MigrationProvenanceError(
                "Same source identity has conflicting immutable metadata"
            )
        if stored_ref.raw_sha256 != source.raw_sha256:
            raise MigrationIntegrityError("Stored quarantine digest does not match source")
        return stored_ref

    def read_raw(self, source_ref: QuarantineRef) -> bytes:
        if not isinstance(source_ref, QuarantineRef):
            raise TypeError("source_ref must be QuarantineRef")
        ref_path = self._ref_path(source_ref.identity_key())
        if not ref_path.is_file():
            raise MigrationIntegrityError("QuarantineRef not found")
        stored_ref = self._load_ref(source_ref.identity_key())
        if stored_ref != source_ref:
            raise MigrationIntegrityError("QuarantineRef mismatch")
        return self._read_verified_object(source_ref)

    def extract(self, source_ref: QuarantineRef) -> SemanticExtraction:
        raw = self.read_raw(source_ref)
        extracted = raw.decode("utf-8", errors="replace")
        return SemanticExtraction(
            source_ref=source_ref,
            extracted_text=extracted,
            source_type=source_ref.source_type,
        )

    def normalize(
        self,
        extraction: SemanticExtraction,
        classification: str | MigrationClassification | None,
        *,
        normalized_text: str | None = None,
    ) -> NormalizedMigrationCandidate:
        if not isinstance(extraction, SemanticExtraction):
            raise TypeError("extraction must be SemanticExtraction")
        raw = self.read_raw(extraction.source_ref)
        expected_text = raw.decode("utf-8", errors="replace")
        if extraction.extracted_text != expected_text:
            raise MigrationIntegrityError("SemanticExtraction does not match quarantined bytes")
        if extraction.source_type != extraction.source_ref.source_type:
            raise MigrationProvenanceError("SemanticExtraction source_type mismatch")
        parsed_classification = normalize_classification(classification)

        normalized = normalized_text if normalized_text is not None else extraction.extracted_text.strip()
        candidate = object.__new__(NormalizedMigrationCandidate)
        object.__setattr__(candidate, "source_ref", extraction.source_ref)
        object.__setattr__(candidate, "classification", parsed_classification)
        object.__setattr__(candidate, "normalized_text", normalized)
        object.__setattr__(
            candidate,
            "provenance_chain",
            _provenance_for(extraction.source_ref),
        )
        object.__setattr__(candidate, "normalized_at", _now_utc())
        candidate.__post_init__()
        return candidate

    @property
    def raw_sources_count(self) -> int:
        return sum(1 for path in self._refs_root.glob("*.json") if path.is_file())
