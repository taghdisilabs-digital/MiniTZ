#!/usr/bin/env python3
"""Install Biella's first knowledge provisioning root outside the runtime API."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
from uuid import uuid4

from minitz_os.engine import KnowledgeService


_ROOT_ID_PATTERN = re.compile(r"kpr_[0-9a-f]{32}")
_ROOT_TOKEN_PATTERN = re.compile(r"kproot_[0-9a-f]{64}")


@dataclass(frozen=True)
class DeploymentCredential:
    root_id: str
    token: str
    created_at: str


@dataclass(frozen=True)
class OpenedCredential:
    credential: DeploymentCredential
    descriptor: int
    device: int
    inode: int


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(
        directory,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_database(database: Path) -> None:
    for path in (database, database.with_name(f"{database.name}-wal")):
        if path.exists():
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    _fsync_directory(database.parent)


def _validate_credential(value: object) -> DeploymentCredential:
    if not isinstance(value, dict) or set(value) != {"created_at", "root_id", "token"}:
        raise RuntimeError("deployment credential is malformed")
    root_id = value.get("root_id")
    token = value.get("token")
    created_at = value.get("created_at")
    if not isinstance(root_id, str) or _ROOT_ID_PATTERN.fullmatch(root_id) is None:
        raise RuntimeError("deployment root identity is malformed")
    if not isinstance(token, str) or _ROOT_TOKEN_PATTERN.fullmatch(token) is None:
        raise RuntimeError("deployment root token is malformed")
    if not isinstance(created_at, str):
        raise RuntimeError("deployment root timestamp is malformed")
    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise RuntimeError("deployment root timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("deployment root timestamp is not timezone-aware")
    return DeploymentCredential(root_id, token, created_at)


def _open_credential(
    directory_descriptor: int,
    name: str,
) -> OpenedCredential:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory_descriptor,
        )
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise RuntimeError("deployment credential is not a safe regular file") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise RuntimeError(
                "deployment credential must be a mode-0600 regular file"
            )
        payload = os.read(descriptor, 16385)
        if len(payload) > 16384 or os.read(descriptor, 1):
            raise RuntimeError("deployment credential is unbounded")
        raw: object = json.loads(payload.decode("utf-8"))
        credential = _validate_credential(raw)
        return OpenedCredential(
            credential,
            descriptor,
            metadata.st_dev,
            metadata.st_ino,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        os.close(descriptor)
        raise RuntimeError("deployment credential is unreadable") from exc
    except Exception:
        os.close(descriptor)
        raise


def _try_open_credential(
    directory_descriptor: int,
    name: str,
) -> OpenedCredential | None:
    try:
        return _open_credential(directory_descriptor, name)
    except FileNotFoundError:
        return None


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise RuntimeError("deployment credential write did not advance")
        remaining = remaining[written:]


def _new_pending_credential(
    directory_descriptor: int,
    name: str,
) -> OpenedCredential:
    credential = DeploymentCredential(
        root_id=f"kpr_{uuid4().hex}",
        token=f"kproot_{secrets.token_hex(32)}",
        created_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
    )
    descriptor = os.open(
        name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=directory_descriptor,
    )
    try:
        payload = (
            json.dumps(
                {
                    "created_at": credential.created_at,
                    "root_id": credential.root_id,
                    "token": credential.token,
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return OpenedCredential(
            credential,
            descriptor,
            metadata.st_dev,
            metadata.st_ino,
        )
    except Exception:
        os.close(descriptor)
        raise


def _verify_binding(
    directory_descriptor: int,
    name: str,
    opened: OpenedCredential,
) -> None:
    try:
        metadata = os.stat(
            name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise RuntimeError("deployment credential disappeared") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_dev != opened.device
        or metadata.st_ino != opened.inode
    ):
        raise RuntimeError("deployment credential path was replaced")


def _stage_credential(
    directory_descriptor: int,
    name: str,
) -> OpenedCredential:
    pending_name = f".{name}.pending"
    try:
        pending = _try_open_credential(directory_descriptor, pending_name)
    except RuntimeError:
        os.unlink(pending_name, dir_fd=directory_descriptor)
        os.fsync(directory_descriptor)
        pending = None
    if pending is None:
        pending = _new_pending_credential(directory_descriptor, pending_name)
        os.fsync(directory_descriptor)
    try:
        os.link(
            pending_name,
            name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        os.close(pending.descriptor)
        raise RuntimeError("deployment credential publication raced") from exc
    os.fsync(directory_descriptor)
    published = _open_credential(directory_descriptor, name)
    if (
        published.credential != pending.credential
        or published.device != pending.device
        or published.inode != pending.inode
    ):
        os.close(pending.descriptor)
        os.close(published.descriptor)
        raise RuntimeError("published deployment credential differs from staging")
    os.close(pending.descriptor)
    return published


def _verify_pending(
    directory_descriptor: int,
    name: str,
    opened: OpenedCredential,
) -> bool:
    pending_name = f".{name}.pending"
    pending = _try_open_credential(directory_descriptor, pending_name)
    if pending is None:
        return False
    try:
        if (
            pending.credential != opened.credential
            or pending.device != opened.device
            or pending.inode != opened.inode
        ):
            raise RuntimeError("pending and published credentials differ")
        return True
    finally:
        os.close(pending.descriptor)


def _cleanup_pending(
    directory_descriptor: int,
    name: str,
    opened: OpenedCredential,
) -> None:
    if not _verify_pending(directory_descriptor, name, opened):
        return
    os.unlink(f".{name}.pending", dir_fd=directory_descriptor)
    os.fsync(directory_descriptor)


def provision(database_path: Path, credential_output: Path) -> tuple[str, str]:
    """Create or reconcile one deployment root and its durable credential."""

    database = database_path.resolve()
    KnowledgeService(database)
    connection = sqlite3.connect(database, timeout=30.0)
    output_name = credential_output.name
    if not output_name or output_name in {".", ".."}:
        connection.close()
        raise RuntimeError("credential output basename is malformed")
    try:
        output_parent = credential_output.parent.resolve(strict=True)
        directory_descriptor = os.open(
            output_parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
        )
    except OSError as exc:
        connection.close()
        raise RuntimeError("credential output parent is unavailable") from exc
    directory_metadata = os.fstat(directory_descriptor)
    if (
        directory_metadata.st_uid != os.geteuid()
        or stat.S_IMODE(directory_metadata.st_mode) & 0o022
    ):
        os.close(directory_descriptor)
        connection.close()
        raise RuntimeError(
            "credential output parent must be owner-controlled and not group-writable"
        )
    opened_credential: OpenedCredential | None = None
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA synchronous = FULL")
        checkpoint = connection.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        if checkpoint is None or checkpoint[0] != 0:
            raise RuntimeError("knowledge database checkpoint is busy")
        _fsync_database(database)
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            "SELECT * FROM knowledge_provisioning_roots ORDER BY root_id"
        ).fetchall()
        if len(rows) > 1:
            raise RuntimeError("multiple knowledge provisioning roots exist")
        opened_credential = _try_open_credential(
            directory_descriptor,
            output_name,
        )
        if opened_credential is not None:
            has_pending = _verify_pending(
                directory_descriptor,
                output_name,
                opened_credential,
            )
            if not rows and not has_pending:
                raise RuntimeError(
                    "uncommitted deployment credential lacks its durable staging link"
                )
            credential_was_staged = True
        else:
            if rows:
                raise RuntimeError(
                    "database root exists but its exact deployment credential is unavailable"
                )
            opened_credential = _stage_credential(
                directory_descriptor,
                output_name,
            )
            credential_was_staged = False
        credential = opened_credential.credential
        _verify_binding(
            directory_descriptor,
            output_name,
            opened_credential,
        )
        token_sha256 = hashlib.sha256(credential.token.encode()).hexdigest()
        record_sha256 = _canonical_sha256(
            {
                "created_at": credential.created_at,
                "root_id": credential.root_id,
                "token_sha256": token_sha256,
            }
        )
        if rows:
            row = rows[0]
            if (
                row[0] != credential.root_id
                or row[1] != token_sha256
                or row[2] != credential.created_at
                or row[3] != record_sha256
            ):
                raise RuntimeError(
                    "database root and deployment credential do not match"
                )
            status = "PRESENT"
        else:
            connection.execute(
                "INSERT INTO knowledge_provisioning_roots VALUES (?, ?, ?, ?)",
                (
                    credential.root_id,
                    token_sha256,
                    credential.created_at,
                    record_sha256,
                ),
            )
            status = "RECOVERED" if credential_was_staged else "PROVISIONED"
        _verify_binding(
            directory_descriptor,
            output_name,
            opened_credential,
        )
        connection.commit()
        checkpoint = connection.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        if checkpoint is None or checkpoint[0] != 0:
            raise RuntimeError("knowledge root commit checkpoint is busy")
        _fsync_database(database)
        _verify_binding(
            directory_descriptor,
            output_name,
            opened_credential,
        )
        _cleanup_pending(
            directory_descriptor,
            output_name,
            opened_credential,
        )
        return credential.root_id, status
    except Exception:
        connection.rollback()
        raise
    finally:
        if opened_credential is not None:
            os.close(opened_credential.descriptor)
        connection.close()
        os.close(directory_descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install one immutable Biella knowledge provisioning root.",
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--credential-output", required=True, type=Path)
    arguments = parser.parse_args()
    root_id, status = provision(arguments.database, arguments.credential_output)
    print(json.dumps({"root_id": root_id, "status": status}))


if __name__ == "__main__":
    main()
