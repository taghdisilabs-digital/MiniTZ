"""Provider-neutral immutable byte storage behind :class:`ContentRef`."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import BinaryIO, Protocol, cast, runtime_checkable

from .artifact import ArtifactContentError, ContentRef


class ObjectStorageError(Exception):
    """Base class for physical content storage failures."""


class ObjectStorageIntegrityError(ObjectStorageError):
    """Stored bytes do not match their exact content identity."""


class ObjectStorageNotFoundError(ObjectStorageError):
    """The requested content object is not present in this backend."""


class ObjectStorageContractError(ObjectStorageError, ValueError):
    """A backend request is malformed."""


class ReplicaState(str, Enum):
    """Durable physical-replica state, separate from logical content identity."""

    AVAILABLE = "AVAILABLE"
    VERIFYING = "VERIFYING"
    CORRUPT = "CORRUPT"
    MISSING = "MISSING"
    UPLOADING = "UPLOADING"
    FAILED = "FAILED"


@runtime_checkable
class ContentReader(Protocol):
    """File-like streaming input whose reads can be bounded."""

    def read(self, size: int = -1) -> bytes:
        """Read at most ``size`` bytes."""


ContentSource = bytes | Iterable[bytes] | ContentReader
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _require_content_ref(value: object) -> ContentRef:
    if not isinstance(value, ContentRef):
        raise ObjectStorageContractError("content_ref must be ContentRef")
    return value


def _iter_chunks(source: ContentSource) -> Iterator[bytes]:
    if isinstance(source, bytes):
        yield source
        return
    if isinstance(source, ContentReader):
        while True:
            chunk = source.read(1024 * 1024)
            if not isinstance(chunk, bytes):
                raise ObjectStorageContractError(
                    "content stream reads must return immutable bytes"
                )
            if not chunk:
                return
            yield chunk
    if not isinstance(source, Iterable):
        raise ObjectStorageContractError(
            "content source must be bytes, a binary reader, or an iterable of bytes"
        )
    for iterable_chunk in source:
        if not isinstance(iterable_chunk, bytes):
            raise ObjectStorageContractError("content stream chunks must be immutable bytes")
        yield iterable_chunk


def _validate_expected(
    *,
    digest: str,
    size_bytes: int,
    expected_digest: str | None,
    expected_size: int | None,
) -> None:
    if expected_digest is not None and digest != expected_digest:
        raise ObjectStorageIntegrityError("content digest does not match expected digest")
    if expected_size is not None and size_bytes != expected_size:
        raise ObjectStorageIntegrityError("content size does not match expected size")


def _validate_expectation_contract(
    expected_digest: str | None,
    expected_size: int | None,
) -> None:
    if expected_digest is not None and (
        not isinstance(expected_digest, str)
        or _SHA256_PATTERN.fullmatch(expected_digest) is None
    ):
        raise ObjectStorageContractError(
            "expected_digest must be 64 lowercase hexadecimal characters"
        )
    if expected_size is not None and (
        not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size < 0
    ):
        raise ObjectStorageContractError(
            "expected_size must be a non-negative integer"
        )


@dataclass(frozen=True, order=True)
class ContentObject:
    """Verified immutable content metadata, independent of storage location."""

    algorithm: str
    digest: str
    size_bytes: int
    media_type: str = field(compare=False)
    created_at: str = field(compare=False)

    def __post_init__(self) -> None:
        ContentRef(
            algorithm=self.algorithm,
            digest=self.digest,
            size_bytes=self.size_bytes,
            media_type=self.media_type,
        )
        try:
            created = datetime.fromisoformat(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ArtifactContentError(
                "ContentObject created_at must be a timezone-aware ISO-8601 timestamp"
            ) from exc
        if created.tzinfo is None or created.utcoffset() is None:
            raise ArtifactContentError(
                "ContentObject created_at must be a timezone-aware ISO-8601 timestamp"
            )

    @property
    def content_ref(self) -> ContentRef:
        return ContentRef(
            algorithm=self.algorithm,
            digest=self.digest,
            size_bytes=self.size_bytes,
            media_type=self.media_type,
        )


@dataclass(frozen=True, order=True)
class ContentLocation:
    """One observed physical replica, deliberately excluded from identity."""

    backend_id: str
    locator: str
    content_digest: str = ""
    state: ReplicaState = ReplicaState.AVAILABLE
    size_bytes: int = 0
    verified_at: str | None = None
    created_at: str = "1970-01-01T00:00:00+00:00"
    failure_ref: str | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("backend_id", self.backend_id),
            ("locator", self.locator),
        ):
            if (
                not isinstance(value, str)
                or not value
                or len(value) > 4096
                or any(ord(character) < 32 for character in value)
            ):
                raise ObjectStorageContractError(
                    f"ContentLocation {field_name} is malformed"
                )
        if self.content_digest and _SHA256_PATTERN.fullmatch(self.content_digest) is None:
            raise ObjectStorageContractError("ContentLocation content_digest is malformed")
        if not isinstance(self.state, ReplicaState):
            raise ObjectStorageContractError("ContentLocation state is malformed")
        if (
            not isinstance(self.size_bytes, int)
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 0
        ):
            raise ObjectStorageContractError("ContentLocation size_bytes is malformed")
        timestamp_values = (
            ("verified_at", self.verified_at),
            ("created_at", cast(str | None, self.created_at)),
        )
        for timestamp_name, timestamp_value in timestamp_values:
            if timestamp_value is None:
                if timestamp_name == "verified_at":
                    continue
                raise ObjectStorageContractError(
                    f"ContentLocation {timestamp_name} is malformed"
                )
            if not isinstance(timestamp_value, str):
                raise ObjectStorageContractError(
                    f"ContentLocation {timestamp_name} is malformed"
                )
            try:
                parsed = datetime.fromisoformat(timestamp_value)
            except ValueError as exc:
                raise ObjectStorageContractError(
                    f"ContentLocation {timestamp_name} is malformed"
                ) from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ObjectStorageContractError(
                    f"ContentLocation {timestamp_name} is malformed"
                )
        if self.failure_ref is not None and (
            not isinstance(self.failure_ref, str)
            or not self.failure_ref.startswith("failure://sha256/")
            or _SHA256_PATTERN.fullmatch(self.failure_ref.removeprefix("failure://sha256/"))
            is None
        ):
            raise ObjectStorageContractError("ContentLocation failure_ref is malformed")


class ObjectStorageBackend(ABC):
    """Minimal provider-neutral contract for authoritative immutable bytes."""

    @abstractmethod
    def put(
        self,
        source: ContentSource,
        *,
        media_type: str,
        expected_digest: str | None = None,
        expected_size: int | None = None,
    ) -> ContentRef:
        """Store and verify immutable bytes."""

    @abstractmethod
    def read(self, content_ref: ContentRef) -> bytes:
        """Return bytes only after exact integrity verification."""

    @abstractmethod
    def open(self, content_ref: ContentRef) -> BinaryIO:
        """Open a verified streaming reader positioned at the first byte."""

    @abstractmethod
    def stat(self, content_ref: ContentRef) -> ContentObject:
        """Return verified immutable metadata."""

    @abstractmethod
    def exists(self, content_ref: ContentRef) -> bool:
        """Return whether an exact verified object is present."""

    @abstractmethod
    def location(self, content_ref: ContentRef) -> ContentLocation:
        """Return physical location separately from logical content identity."""

    @abstractmethod
    def verify(self, content_ref: ContentRef) -> bool:
        """Verify that stored bytes match the supplied identity."""


class MemoryObjectStorageBackend(ObjectStorageBackend):
    """Deterministic reference backend for contract tests and ephemeral use."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self._created_at: dict[tuple[str, str], str] = {}

    def put(
        self,
        source: ContentSource,
        *,
        media_type: str,
        expected_digest: str | None = None,
        expected_size: int | None = None,
    ) -> ContentRef:
        _validate_expectation_contract(expected_digest, expected_size)
        digest = hashlib.sha256()
        size_bytes = 0
        chunks: list[bytes] = []
        for chunk in _iter_chunks(source):
            digest.update(chunk)
            size_bytes += len(chunk)
            chunks.append(chunk)
        observed_digest = digest.hexdigest()
        _validate_expected(
            digest=observed_digest,
            size_bytes=size_bytes,
            expected_digest=expected_digest,
            expected_size=expected_size,
        )
        payload = b"".join(chunks)
        content_ref = ContentRef(
            algorithm="sha256",
            digest=observed_digest,
            size_bytes=size_bytes,
            media_type=media_type,
        )
        key = (content_ref.algorithm, content_ref.digest)
        self._created_at.setdefault(
            key,
            datetime.now(timezone.utc).isoformat(),
        )
        self._objects.setdefault(key, payload)
        self.verify(content_ref)
        return content_ref

    def read(self, content_ref: ContentRef) -> bytes:
        content_ref = _require_content_ref(content_ref)
        key = (content_ref.algorithm, content_ref.digest)
        try:
            payload = self._objects[key]
        except KeyError as exc:
            raise ObjectStorageNotFoundError("content object is not present") from exc
        try:
            content_ref.verify(payload)
        except ArtifactContentError as exc:
            raise ObjectStorageIntegrityError(
                "stored bytes failed digest or size verification"
            ) from exc
        return payload

    def open(self, content_ref: ContentRef) -> BinaryIO:
        return io.BytesIO(self.read(content_ref))

    def stat(self, content_ref: ContentRef) -> ContentObject:
        content_ref = _require_content_ref(content_ref)
        self.verify(content_ref)
        key = (content_ref.algorithm, content_ref.digest)
        created_at = self._created_at[key]
        return ContentObject(
            algorithm=content_ref.algorithm,
            digest=content_ref.digest,
            size_bytes=content_ref.size_bytes,
            media_type=content_ref.media_type,
            created_at=created_at,
        )

    def exists(self, content_ref: ContentRef) -> bool:
        content_ref = _require_content_ref(content_ref)
        key = (content_ref.algorithm, content_ref.digest)
        if key not in self._objects:
            return False
        self.verify(content_ref)
        return True

    def location(self, content_ref: ContentRef) -> ContentLocation:
        content_ref = _require_content_ref(content_ref)
        self.verify(content_ref)
        created_at = self._created_at[(content_ref.algorithm, content_ref.digest)]
        return ContentLocation(
            backend_id="memory-reference",
            locator=f"memory://sha256/{content_ref.digest}",
            content_digest=content_ref.digest,
            state=ReplicaState.AVAILABLE,
            size_bytes=content_ref.size_bytes,
            verified_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            created_at=created_at,
        )

    def verify(self, content_ref: ContentRef) -> bool:
        self.read(content_ref)
        return True

    def delete_replica(self, content_ref: ContentRef) -> None:
        """Delete one physical ephemeral replica without touching logical identity."""

        content_ref = _require_content_ref(content_ref)
        key = (content_ref.algorithm, content_ref.digest)
        self._objects.pop(key, None)
        self._created_at.pop(key, None)


class FilesystemObjectStorageBackend(ObjectStorageBackend):
    """Durable filesystem backend with atomic digest-addressed publication."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self._objects_container = self.root / "objects"
        self._objects_root = self._objects_container / "sha256"
        self._temporary_root = self.root / ".temporary"
        self.root.mkdir(parents=True, exist_ok=True)
        if not stat.S_ISDIR(self.root.lstat().st_mode):
            raise ObjectStorageIntegrityError("filesystem backend root is not a directory")
        self._fsync_directory(self.root.parent)
        self._ensure_storage_directory(self._objects_container, boundary=self.root)
        self._ensure_storage_directory(self._objects_root, boundary=self.root)
        self._ensure_storage_directory(self._temporary_root, boundary=self.root)

    def _ensure_storage_directory(self, directory: Path, *, boundary: Path) -> None:
        created = False
        try:
            os.mkdir(directory)
            created = True
        except FileExistsError:
            pass
        try:
            directory_state = directory.lstat()
        except OSError as exc:
            raise ObjectStorageIntegrityError(
                "digest shard directory is unavailable"
            ) from exc
        if not stat.S_ISDIR(directory_state.st_mode):
            raise ObjectStorageIntegrityError(
                "storage directory must not be a symlink or non-directory"
            )
        if not directory.resolve(strict=True).is_relative_to(boundary):
            raise ObjectStorageIntegrityError("storage directory escaped backend root")
        if created:
            self._fsync_directory(directory.parent)

    def _object_directory(
        self,
        content_ref: ContentRef,
        *,
        create_parent: bool,
    ) -> Path:
        content_ref = _require_content_ref(content_ref)
        first_shard = self._objects_root / content_ref.digest[:2]
        second_shard = first_shard / content_ref.digest[2:4]
        directory = second_shard / content_ref.digest
        if create_parent:
            self._ensure_storage_directory(first_shard, boundary=self._objects_root)
            self._ensure_storage_directory(second_shard, boundary=self._objects_root)
        resolved = directory.resolve(strict=False)
        if not resolved.is_relative_to(self._objects_root):
            raise ObjectStorageIntegrityError("digest-derived object path escaped backend root")
        return directory

    def _object_path(self, content_ref: ContentRef, *, create_parent: bool) -> Path:
        return self._object_directory(
            content_ref,
            create_parent=create_parent,
        ) / "content"

    def _metadata_path(self, content_ref: ContentRef, *, create_parent: bool) -> Path:
        return self._object_directory(
            content_ref,
            create_parent=create_parent,
        ) / "metadata.json"

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _metadata_record(content_ref: ContentRef, created_at: str) -> bytes:
        fields: dict[str, object] = {
            "algorithm": content_ref.algorithm,
            "created_at": created_at,
            "digest": content_ref.digest,
            "size_bytes": content_ref.size_bytes,
            "version": 1,
        }
        record = {
            **fields,
            "record_sha256": hashlib.sha256(_json(fields).encode()).hexdigest(),
        }
        return _json(record).encode()

    def _read_created_at(self, content_ref: ContentRef) -> str:
        metadata_path = self._metadata_path(content_ref, create_parent=False)
        try:
            with self._open_unverified(metadata_path) as reader:
                serialized = reader.read(65_537)
        except ObjectStorageNotFoundError as exc:
            raise ObjectStorageIntegrityError(
                "content object metadata is missing"
            ) from exc
        if len(serialized) > 65_536:
            raise ObjectStorageIntegrityError("content object metadata is unbounded")
        try:
            loaded: object = json.loads(serialized.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObjectStorageIntegrityError(
                "content object metadata is malformed"
            ) from exc
        if not isinstance(loaded, dict):
            raise ObjectStorageIntegrityError("content object metadata is malformed")
        record = cast(dict[str, object], loaded)
        if set(record) != {
            "algorithm",
            "created_at",
            "digest",
            "record_sha256",
            "size_bytes",
            "version",
        }:
            raise ObjectStorageIntegrityError("content object metadata is malformed")
        created_at = record["created_at"]
        record_sha256 = record["record_sha256"]
        fields: dict[str, object] = {
            "algorithm": record["algorithm"],
            "created_at": created_at,
            "digest": record["digest"],
            "size_bytes": record["size_bytes"],
            "version": record["version"],
        }
        if (
            fields["algorithm"] != content_ref.algorithm
            or fields["digest"] != content_ref.digest
            or fields["size_bytes"] != content_ref.size_bytes
            or fields["version"] != 1
            or not isinstance(created_at, str)
            or not isinstance(record_sha256, str)
            or _SHA256_PATTERN.fullmatch(record_sha256) is None
            or hashlib.sha256(_json(fields).encode()).hexdigest() != record_sha256
        ):
            raise ObjectStorageIntegrityError(
                "content object metadata failed integrity verification"
            )
        try:
            ContentObject(
                algorithm=content_ref.algorithm,
                digest=content_ref.digest,
                size_bytes=content_ref.size_bytes,
                media_type=content_ref.media_type,
                created_at=created_at,
            )
        except ArtifactContentError as exc:
            raise ObjectStorageIntegrityError(
                "content object metadata failed integrity verification"
            ) from exc
        return created_at

    @staticmethod
    def _remove_bundle(directory: Path) -> None:
        for name in ("content", "metadata.json"):
            try:
                (directory / name).unlink()
            except FileNotFoundError:
                pass
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass

    @staticmethod
    def _verify_reader(reader: BinaryIO, content_ref: ContentRef) -> None:
        digest = hashlib.sha256()
        size_bytes = 0
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size_bytes += len(chunk)
        if digest.hexdigest() != content_ref.digest or size_bytes != content_ref.size_bytes:
            raise ObjectStorageIntegrityError(
                "stored bytes failed digest or size verification"
            )

    def _open_unverified(self, path: Path) -> BinaryIO:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as exc:
            raise ObjectStorageNotFoundError("content object is not present") from exc
        except OSError as exc:
            raise ObjectStorageIntegrityError("content object locator is unsafe") from exc
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ObjectStorageIntegrityError(
                    "content object must be an immutable regular file"
                )
            return os.fdopen(descriptor, "rb")
        except Exception:
            os.close(descriptor)
            raise

    def put(
        self,
        source: ContentSource,
        *,
        media_type: str,
        expected_digest: str | None = None,
        expected_size: int | None = None,
    ) -> ContentRef:
        _validate_expectation_contract(expected_digest, expected_size)
        temporary_directory = Path(tempfile.mkdtemp(
            prefix=".put-",
            dir=self._temporary_root,
        ))
        temporary_path = temporary_directory / "content"
        published_directory: Path | None = None
        published_by_this_call = False
        try:
            digest = hashlib.sha256()
            size_bytes = 0
            with temporary_path.open("xb") as writer:
                for chunk in _iter_chunks(source):
                    writer.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            observed_digest = digest.hexdigest()
            _validate_expected(
                digest=observed_digest,
                size_bytes=size_bytes,
                expected_digest=expected_digest,
                expected_size=expected_size,
            )
            content_ref = ContentRef(
                algorithm="sha256",
                digest=observed_digest,
                size_bytes=size_bytes,
                media_type=media_type,
            )
            metadata_path = temporary_directory / "metadata.json"
            with metadata_path.open("xb") as writer:
                writer.write(
                    self._metadata_record(
                        content_ref,
                        datetime.now(timezone.utc).isoformat(),
                    )
                )
                writer.flush()
                os.fsync(writer.fileno())
            self._fsync_directory(temporary_directory)
            published_directory = self._object_directory(
                content_ref,
                create_parent=True,
            )
            try:
                os.rename(temporary_directory, published_directory)
                published_by_this_call = True
                self._fsync_directory(published_directory.parent)
            except OSError as exc:
                if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                    raise
            self.verify(content_ref)
            return content_ref
        except Exception:
            if published_by_this_call and published_directory is not None:
                try:
                    self._remove_bundle(published_directory)
                    self._fsync_directory(published_directory.parent)
                except FileNotFoundError:
                    pass
            raise
        finally:
            self._remove_bundle(temporary_directory)

    def open(self, content_ref: ContentRef) -> BinaryIO:
        content_ref = _require_content_ref(content_ref)
        self._read_created_at(content_ref)
        path = self._object_path(content_ref, create_parent=False)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".read-",
            dir=self._temporary_root,
        )
        snapshot_path = Path(temporary_name)
        reader_snapshot: BinaryIO | None = None
        try:
            digest = hashlib.sha256()
            size_bytes = 0
            with os.fdopen(descriptor, "wb") as snapshot:
                with self._open_unverified(path) as reader:
                    while True:
                        chunk = reader.read(1024 * 1024)
                        if not chunk:
                            break
                        snapshot.write(chunk)
                        digest.update(chunk)
                        size_bytes += len(chunk)
                snapshot.flush()
            if (
                digest.hexdigest() != content_ref.digest
                or size_bytes != content_ref.size_bytes
            ):
                raise ObjectStorageIntegrityError(
                    "stored bytes failed digest or size verification"
                )
            reader_snapshot = self._open_unverified(snapshot_path)
            snapshot_path.unlink()
            try:
                self._verify_reader(reader_snapshot, content_ref)
                reader_snapshot.seek(0)
                return reader_snapshot
            except Exception:
                reader_snapshot.close()
                raise
        finally:
            try:
                snapshot_path.unlink()
            except FileNotFoundError:
                pass

    def read(self, content_ref: ContentRef) -> bytes:
        with self.open(content_ref) as reader:
            return reader.read()

    def stat(self, content_ref: ContentRef) -> ContentObject:
        content_ref = _require_content_ref(content_ref)
        created_at = self._read_created_at(content_ref)
        path = self._object_path(content_ref, create_parent=False)
        with self._open_unverified(path) as reader:
            self._verify_reader(reader, content_ref)
        return ContentObject(
            algorithm=content_ref.algorithm,
            digest=content_ref.digest,
            size_bytes=content_ref.size_bytes,
            media_type=content_ref.media_type,
            created_at=created_at,
        )

    def exists(self, content_ref: ContentRef) -> bool:
        path = self._object_path(content_ref, create_parent=False)
        if not path.exists():
            return False
        self.verify(content_ref)
        return True

    def location(self, content_ref: ContentRef) -> ContentLocation:
        self.verify(content_ref)
        created_at = self._read_created_at(content_ref)
        return ContentLocation(
            backend_id="filesystem",
            locator=self._object_path(content_ref, create_parent=False).as_uri(),
            content_digest=content_ref.digest,
            state=ReplicaState.AVAILABLE,
            size_bytes=content_ref.size_bytes,
            verified_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            created_at=created_at,
        )

    def verify(self, content_ref: ContentRef) -> bool:
        content_ref = _require_content_ref(content_ref)
        self._read_created_at(content_ref)
        path = self._object_path(content_ref, create_parent=False)
        with self._open_unverified(path) as reader:
            self._verify_reader(reader, content_ref)
        return True

    def delete_replica(self, content_ref: ContentRef) -> None:
        """Delete one physical replica; Artifact and ContentRef state are untouched."""

        content_ref = _require_content_ref(content_ref)
        directory = self._object_directory(content_ref, create_parent=False)
        self._remove_bundle(directory)
        if directory.parent.exists():
            self._fsync_directory(directory.parent)
