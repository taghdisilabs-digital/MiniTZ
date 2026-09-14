"""Task-scoped authenticated browser and owner-attention boundaries.

This module is deliberately provider-neutral.  A provider may be Playwright,
WebDriver, Browser-Use, or a local reference implementation; MiniTZ owns the
session identity, profile isolation, action policy, pause/resume boundary, and
verification record.  Credentials are represented only by secret references.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
from types import MappingProxyType
from typing import Protocol, cast
from urllib.parse import urlsplit
from uuid import uuid4


_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1000}")
_SECRET_REF = re.compile(r"secret://[^\s\x00-\x1f]{1,1000}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SESSION_REF = re.compile(r"browser-session://[^\s\x00-\x1f]{1,512}")
_PROFILE_REF = re.compile(r"browser-profile://[^\s\x00-\x1f]{1,512}")
_ACTION_REF = re.compile(r"browser-action://[^\s\x00-\x1f]{1,512}")
_BOUNDARY_REF = re.compile(r"human-boundary://[^\s\x00-\x1f]{1,512}")
_SECRET_VALUE = re.compile(r"(?i)(?:bearer\s+|sk-(?:proj-|svcacct-)?|gh[pousr]_)[A-Za-z0-9_./+=:-]{12,}")
_FINANCIAL_WORDS = frozenset({
    "billing", "checkout", "invoice", "payment", "payments", "payout", "payouts",
    "bank", "banking", "credit-card", "creditcard", "financial", "wire-transfer",
})
_OWNER_PROFILE_DENY = frozenset({"patrick", "patrick-profile", "owner-chrome", "foreground"})


class HumanBrowserError(Exception):
    """Base class for task-scoped human browser failures."""


class HumanBrowserContractError(HumanBrowserError, ValueError):
    """An input crossed the authenticated human browser contract."""


class HumanBrowserPolicyError(HumanBrowserError):
    """The requested action is outside current task policy."""


class HumanBoundaryRequiredError(HumanBrowserError):
    """Execution reached a boundary that requires the owner."""


class HumanBrowserNotFoundError(HumanBrowserError):
    """A durable task-local session or action is absent."""


class HumanBrowserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class HumanActionStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class HumanBoundaryReason(str, Enum):
    CAPTCHA = "CAPTCHA"
    TWO_FACTOR = "TWO_FACTOR"
    RECOVERY = "RECOVERY"
    CONSENT = "CONSENT"
    IDENTITY_CONFIRMATION = "IDENTITY_CONFIRMATION"
    OTHER = "OTHER"


class HumanActionType(str, Enum):
    NAVIGATE = "navigate"
    OBSERVE = "observe"
    FILL = "fill"
    CLICK = "click"
    SUBMIT = "submit"
    WAIT = "wait"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _text(value: object, field_name: str, limit: int = 1024) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise HumanBrowserContractError(f"{field_name} is malformed")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise HumanBrowserContractError(f"{field_name} contains a control character")
    if _SECRET_VALUE.search(value):
        raise HumanBrowserContractError(f"{field_name} contains a credential-like value")
    return value


def _ref(value: object, field_name: str, pattern: re.Pattern[str] = _REF) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise HumanBrowserContractError(f"{field_name} is malformed")
    return value


def _secret_ref(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SECRET_REF.fullmatch(value) is None:
        raise HumanBrowserContractError(f"{field_name} must be a secret reference")
    return value


def _sha(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise HumanBrowserContractError(f"{field_name} must be a SHA-256 digest")
    return value


def _safe(value: object, path: str = "value") -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise HumanBrowserContractError(f"{path} is not finite")
        return value
    if isinstance(value, str):
        return _text(value, path, 4096)
    if isinstance(value, Mapping):
        if len(value) > 64:
            raise HumanBrowserContractError(f"{path} is unbounded")
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", key):
                raise HumanBrowserContractError(f"{path} has an invalid key")
            if key.lower() in {"password", "passwd", "secret", "token", "api_key", "authorization", "cookie"}:
                raise HumanBrowserContractError(f"{path}.{key} is a credential field")
            result[key] = _safe(item, f"{path}.{key}")
        return MappingProxyType(result)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        if len(value) > 64:
            raise HumanBrowserContractError(f"{path} is unbounded")
        return tuple(_safe(item, f"{path}[{index}]") for index, item in enumerate(value))
    raise HumanBrowserContractError(f"{path} is not safe JSON")


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise HumanBrowserContractError("URL must be an HTTP(S) origin")
    return f"{parts.scheme}://{parts.hostname.lower()}" + (f":{parts.port}" if parts.port else "")


def _is_financial(value: str) -> bool:
    parts = urlsplit(value)
    words = set(re.split(r"[^a-z0-9]+", (parts.hostname or "").lower()))
    words.update(re.split(r"[^a-z0-9]+", parts.path.lower()))
    return bool(words & _FINANCIAL_WORDS)


@dataclass(frozen=True)
class HumanBrowserSession:
    session_ref: str
    task_ref: str
    run_ref: str
    profile_ref: str
    profile_path: str
    allowed_origins: tuple[str, ...]
    credential_refs: tuple[str, ...]
    browser_name: str
    status: HumanBrowserStatus
    foreground_browser: bool
    provider_session_ref: str
    sequence: int
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _ref(self.session_ref, "session_ref", _SESSION_REF)
        _ref(self.task_ref, "task_ref")
        _ref(self.run_ref, "run_ref")
        _ref(self.profile_ref, "profile_ref", _PROFILE_REF)
        _text(self.profile_path, "profile_path", 4096)
        origins = tuple(sorted({_origin(item) for item in self.allowed_origins}))
        if not origins:
            raise HumanBrowserContractError("at least one allowed origin is required")
        object.__setattr__(self, "allowed_origins", origins)
        refs = tuple(sorted({_secret_ref(item, "credential_ref") for item in self.credential_refs}))
        object.__setattr__(self, "credential_refs", refs)
        _text(self.browser_name, "browser_name", 128)
        if not isinstance(self.status, HumanBrowserStatus):
            raise HumanBrowserContractError("session status is malformed")
        if self.foreground_browser:
            raise HumanBrowserPolicyError("foreground browser control is forbidden")
        _text(self.provider_session_ref, "provider_session_ref", 512)
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise HumanBrowserContractError("session sequence is malformed")
        _text(self.observed_at, "observed_at", 128)
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "allowed_origins": list(self.allowed_origins),
            "browser_name": self.browser_name,
            "credential_refs": list(self.credential_refs),
            "foreground_browser": False,
            "profile_ref": self.profile_ref,
            "provider_session_ref": self.provider_session_ref,
            "run_ref": self.run_ref,
            "sequence": self.sequence,
            "session_ref": self.session_ref,
            "status": self.status.value,
            "task_ref": self.task_ref,
        }


@dataclass(frozen=True)
class HumanBrowserAction:
    action_ref: str
    session_ref: str
    action_type: HumanActionType
    target: str | None = None
    label: str | None = None
    url: str | None = None
    value_ref: str | None = None
    context: Mapping[str, object] = field(default_factory=dict)
    external_side_effect: bool = False

    def __post_init__(self) -> None:
        _ref(self.action_ref, "action_ref", _ACTION_REF)
        _ref(self.session_ref, "session_ref", _SESSION_REF)
        if not isinstance(self.action_type, HumanActionType):
            raise HumanBrowserContractError("action type is malformed")
        if self.target is not None:
            _text(self.target, "target", 4096)
            if self.target.startswith("coordinate:"):
                raise HumanBrowserPolicyError("coordinate-only browser actions are forbidden")
        if self.label is not None:
            _text(self.label, "label", 512)
        if self.url is not None:
            _origin(self.url)
        if self.value_ref is not None:
            _secret_ref(self.value_ref, "value_ref")
        object.__setattr__(self, "context", _safe(self.context, "context"))
        if self.action_type in {HumanActionType.FILL, HumanActionType.CLICK, HumanActionType.SUBMIT} and not (self.target or self.label):
            raise HumanBrowserContractError("contextual actions require a target or accessible label")

    def payload(self) -> dict[str, object]:
        return {
            "action_ref": self.action_ref,
            "action_type": self.action_type.value,
            "context": _plain(self.context),
            "external_side_effect": self.external_side_effect,
            "label": self.label,
            "session_ref": self.session_ref,
            "target": self.target,
            "url": self.url,
            "value_ref": self.value_ref,
        }


@dataclass(frozen=True)
class HumanBrowserActionResult:
    action: HumanBrowserAction
    status: HumanActionStatus
    verified: bool
    readback: Mapping[str, object]
    evidence_ref: str
    evidence_sha256: str
    boundary_ref: str | None = None
    observed_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not isinstance(self.status, HumanActionStatus) or (self.status is HumanActionStatus.SUCCEEDED) != self.verified:
            raise HumanBrowserContractError("action result status and verification disagree")
        object.__setattr__(self, "readback", _safe(self.readback, "readback"))
        _ref(self.evidence_ref, "evidence_ref")
        _sha(self.evidence_sha256, "evidence_sha256")
        if self.boundary_ref is not None:
            _ref(self.boundary_ref, "boundary_ref", _BOUNDARY_REF)


@dataclass(frozen=True)
class HumanBoundaryRequest:
    boundary_ref: str
    session_ref: str
    reason: HumanBoundaryReason
    prompt_ref: str
    status: str
    attention_audio_ref: str
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _ref(self.boundary_ref, "boundary_ref", _BOUNDARY_REF)
        _ref(self.session_ref, "session_ref", _SESSION_REF)
        if not isinstance(self.reason, HumanBoundaryReason):
            raise HumanBrowserContractError("human boundary reason is malformed")
        _ref(self.prompt_ref, "prompt_ref")
        if self.status not in {"OPEN", "RESUMED"}:
            raise HumanBrowserContractError("human boundary status is malformed")
        _ref(self.attention_audio_ref, "attention_audio_ref")
        _text(self.observed_at, "observed_at", 128)
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"attention_audio_ref": self.attention_audio_ref, "boundary_ref": self.boundary_ref, "prompt_ref": self.prompt_ref, "reason": self.reason.value, "session_ref": self.session_ref, "status": self.status}


@dataclass(frozen=True)
class OwnerAttentionReceipt:
    attention_ref: str
    audio_path: str
    audio_sha256: str
    reason: str
    locale: str
    foreground_browser_touched: bool
    expires_at: str

    def __post_init__(self) -> None:
        _ref(self.attention_ref, "attention_ref")
        _text(self.audio_path, "audio_path", 4096)
        _sha(self.audio_sha256, "audio_sha256")
        _text(self.reason, "reason", 512)
        _text(self.locale, "locale", 32)
        if self.foreground_browser_touched:
            raise HumanBrowserPolicyError("owner attention may not touch the foreground browser")
        _text(self.expires_at, "expires_at", 128)


@dataclass(frozen=True)
class VerifiedFileReceipt:
    operation: str
    path: str
    content_sha256: str
    evidence_ref: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        if self.operation not in {"upload", "download"}:
            raise HumanBrowserContractError("file operation is malformed")
        _text(self.path, "path", 4096)
        _sha(self.content_sha256, "content_sha256")
        _ref(self.evidence_ref, "evidence_ref")
        _sha(self.evidence_sha256, "evidence_sha256")


class HumanBrowserProvider(Protocol):
    """Replaceable browser provider; it never receives raw credential values."""

    def open(self, session: HumanBrowserSession, *, resume: bool) -> str: ...

    def execute(self, session: HumanBrowserSession, action: HumanBrowserAction) -> Mapping[str, object]: ...


class ReferenceHumanBrowserProvider:
    """Deterministic provider for qualification and local task tests."""

    def open(self, session: HumanBrowserSession, *, resume: bool) -> str:
        return session.provider_session_ref if resume else f"reference-human-{uuid4().hex}"

    def execute(self, session: HumanBrowserSession, action: HumanBrowserAction) -> Mapping[str, object]:
        if action.action_type is HumanActionType.NAVIGATE:
            return {"verified": True, "url": action.url, "interaction": "navigation"}
        if action.action_type is HumanActionType.OBSERVE:
            return {"verified": True, "interaction": "accessibility-or-dom-observation"}
        if action.action_type is HumanActionType.FILL:
            return {"verified": True, "field": action.label or action.target, "value_ref": action.value_ref, "interaction": "contextual-fill"}
        return {"verified": True, "target": action.label or action.target, "interaction": action.action_type.value}


class OwnerAttentionAudio:
    """Small provider-independent WAV cue stored outside browser state."""

    def __init__(self, root: str | Path, *, ttl_seconds: int = 900) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 86_400:
            raise HumanBrowserContractError("owner attention TTL is malformed")
        self.ttl_seconds = ttl_seconds

    def request(self, *, reason: str, locale: str = "en", message: str = "") -> OwnerAttentionReceipt:
        reason_value = _text(reason, "attention reason", 512)
        locale_value = _text(locale, "attention locale", 32)
        _text(message or "attention", "attention message", 1024)
        attention_ref = f"attention://minitz/{uuid4().hex}"
        path = self.root / f"{hashlib.sha256(attention_ref.encode()).hexdigest()}.wav"
        payload = self._wav()
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        digest = hashlib.sha256(payload).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
        return OwnerAttentionReceipt(attention_ref, str(path), digest, reason_value, locale_value, False, expires.isoformat(timespec="microseconds"))

    @staticmethod
    def _wav() -> bytes:
        sample_rate = 8_000
        samples = bytearray()
        for index in range(sample_rate // 4):
            amplitude = 10_000 if (index // 80) % 2 == 0 else -10_000
            samples.extend(struct.pack("<h", amplitude))
        body = bytes(samples)
        return b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16) + b"data" + struct.pack("<I", len(body)) + body

    def evict_expired(self) -> int:
        now = datetime.now(timezone.utc)
        removed = 0
        for item in self.root.glob("*.wav"):
            if datetime.fromtimestamp(item.stat().st_mtime, timezone.utc) + timedelta(seconds=self.ttl_seconds) < now:
                item.unlink()
                removed += 1
        return removed


class HumanBrowserService:
    """Durable task/run-bound authenticated human browser workflow."""

    def __init__(self, database_path: str | Path, profile_root: str | Path, attention_audio: OwnerAttentionAudio, *, provider: HumanBrowserProvider | None = None, allow_financial: bool = False) -> None:
        self.database_path = str(database_path)
        self.profile_root = Path(profile_root).resolve()
        self.profile_root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.profile_root, 0o700)
        self.attention_audio = attention_audio
        self.provider = provider or ReferenceHumanBrowserProvider()
        self.allow_financial = allow_financial
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS human_browser_sessions (
              session_ref TEXT PRIMARY KEY, task_ref TEXT NOT NULL, run_ref TEXT NOT NULL,
              profile_ref TEXT NOT NULL, profile_path TEXT NOT NULL, allowed_origins_json TEXT NOT NULL,
              credential_refs_json TEXT NOT NULL, browser_name TEXT NOT NULL, status TEXT NOT NULL,
              provider_session_ref TEXT NOT NULL, sequence INTEGER NOT NULL, observed_at TEXT NOT NULL,
              record_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS human_browser_actions (
              action_ref TEXT PRIMARY KEY, session_ref TEXT NOT NULL, status TEXT NOT NULL,
              verified INTEGER NOT NULL, payload_json TEXT NOT NULL, evidence_ref TEXT NOT NULL,
              evidence_sha256 TEXT NOT NULL, boundary_ref TEXT, observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS human_browser_boundaries (
              boundary_ref TEXT PRIMARY KEY, session_ref TEXT NOT NULL, reason TEXT NOT NULL,
              prompt_ref TEXT NOT NULL, status TEXT NOT NULL, attention_audio_ref TEXT NOT NULL,
              observed_at TEXT NOT NULL, record_sha256 TEXT NOT NULL
            );
            """)
            connection.commit()
        finally:
            connection.close()

    def open_session(self, *, task_ref: str, run_ref: str, profile_ref: str, allowed_origins: Sequence[str], credential_refs: Sequence[str] = (), browser_name: str = "chromium", session_ref: str | None = None, owner_profile: str | None = None, foreground_browser: bool = False) -> HumanBrowserSession:
        if owner_profile is not None and any(item in owner_profile.lower() for item in _OWNER_PROFILE_DENY):
            raise HumanBrowserPolicyError("owner or Patrick foreground profile is forbidden")
        if foreground_browser:
            raise HumanBrowserPolicyError("foreground browser control is forbidden")
        _ref(task_ref, "task_ref")
        _ref(run_ref, "run_ref")
        profile = _ref(profile_ref, "profile_ref", _PROFILE_REF)
        origins = tuple(sorted({_origin(item) for item in allowed_origins}))
        if not origins:
            raise HumanBrowserContractError("at least one allowed origin is required")
        refs = tuple(sorted({_secret_ref(item, "credential_ref") for item in credential_refs}))
        session = session_ref or f"browser-session://minitz/{uuid4().hex}"
        _ref(session, "session_ref", _SESSION_REF)
        profile_path = self.profile_root / hashlib.sha256(profile.encode()).hexdigest()
        profile_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = self._connect()
        try:
            prior = connection.execute("SELECT * FROM human_browser_sessions WHERE session_ref=?", (session,)).fetchone()
            if prior is not None:
                existing = self._session_from_row(prior)
                if (existing.task_ref, existing.run_ref, existing.profile_ref, existing.allowed_origins, existing.credential_refs) != (task_ref, run_ref, profile, origins, refs):
                    raise HumanBrowserPolicyError("session identity is bound to a different Task/Run/profile")
                if existing.status is HumanBrowserStatus.CLOSED:
                    raise HumanBrowserPolicyError("closed session cannot be resumed")
                provider_ref = self.provider.open(existing, resume=True)
                resumed = self._replace_session(existing, status=HumanBrowserStatus.ACTIVE, provider_session_ref=provider_ref, sequence=existing.sequence + 1)
                self._store_session(connection, resumed)
                connection.commit()
                return resumed
            profile_owner = connection.execute(
                "SELECT task_ref,run_ref FROM human_browser_sessions WHERE profile_ref=? LIMIT 1",
                (profile,),
            ).fetchone()
            if profile_owner is not None and (profile_owner["task_ref"], profile_owner["run_ref"]) != (task_ref, run_ref):
                raise HumanBrowserPolicyError("persistent browser profile is already bound to another Task/Run")
            provisional = HumanBrowserSession(session, task_ref, run_ref, profile, str(profile_path), origins, refs, browser_name, HumanBrowserStatus.ACTIVE, False, f"pending-{uuid4().hex}", 1, _now())
            provider_ref = self.provider.open(provisional, resume=False)
            created = self._replace_session(provisional, provider_session_ref=_text(provider_ref, "provider session ref", 512))
            self._store_session(connection, created)
            connection.commit()
            return created
        finally:
            connection.close()

    def resume_session(self, session_ref: str) -> HumanBrowserSession:
        session = self.get_session(session_ref)
        if session.status is HumanBrowserStatus.CLOSED:
            raise HumanBrowserPolicyError("closed session cannot be resumed")
        provider_ref = self.provider.open(session, resume=True)
        updated = self._replace_session(session, status=HumanBrowserStatus.ACTIVE, provider_session_ref=provider_ref, sequence=session.sequence + 1)
        connection = self._connect()
        try:
            self._store_session(connection, updated)
            connection.commit()
        finally:
            connection.close()
        return updated

    def get_session(self, session_ref: str) -> HumanBrowserSession:
        _ref(session_ref, "session_ref", _SESSION_REF)
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM human_browser_sessions WHERE session_ref=?", (session_ref,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise HumanBrowserNotFoundError("browser session is not durable")
        return self._session_from_row(row)

    def execute(self, action: HumanBrowserAction) -> HumanBrowserActionResult:
        session = self.get_session(action.session_ref)
        if session.status is HumanBrowserStatus.PAUSED:
            raise HumanBoundaryRequiredError("human boundary is open; resume the same session first")
        if session.status in {HumanBrowserStatus.CLOSED, HumanBrowserStatus.FAILED}:
            raise HumanBrowserPolicyError("session is not executable")
        if action.url is not None:
            origin = _origin(action.url)
            if origin not in session.allowed_origins:
                raise HumanBrowserPolicyError("navigation crossed the session origin allowlist")
            if _is_financial(action.url) and not self.allow_financial:
                raise HumanBrowserPolicyError("financial surface is denied without explicit owner authorization")
        if action.external_side_effect and action.action_type is HumanActionType.SUBMIT and action.url and _is_financial(action.url) and not self.allow_financial:
            raise HumanBrowserPolicyError("financial side effect is denied")
        output = self.provider.execute(session, action)
        safe_output = _safe(output, "provider readback")
        if not isinstance(safe_output, Mapping):
            raise HumanBrowserContractError("provider readback must be a mapping")
        result_map = cast(Mapping[str, object], safe_output)
        boundary_reason = result_map.get("human_boundary")
        if boundary_reason is not None:
            try:
                reason = HumanBoundaryReason(str(boundary_reason))
            except ValueError:
                reason = HumanBoundaryReason.OTHER
            boundary = self.pause_for_human(action.session_ref, reason=reason, prompt_ref=f"prompt://minitz/{uuid4().hex}")
            return self._record_action(action, HumanActionStatus.NEEDS_HUMAN, False, result_map, boundary.boundary_ref)
        verified = result_map.get("verified") is True
        status = HumanActionStatus.SUCCEEDED if verified else HumanActionStatus.FAILED
        return self._record_action(action, status, verified, result_map, None)

    def pause_for_human(self, session_ref: str, *, reason: HumanBoundaryReason, prompt_ref: str) -> HumanBoundaryRequest:
        session = self.get_session(session_ref)
        if session.status is HumanBrowserStatus.CLOSED:
            raise HumanBrowserPolicyError("closed session cannot pause")
        _ref(prompt_ref, "prompt_ref")
        attention = self.attention_audio.request(reason=reason.value, message=prompt_ref)
        boundary_ref = f"human-boundary://minitz/{uuid4().hex}"
        request = HumanBoundaryRequest(boundary_ref, session_ref, reason, prompt_ref, "OPEN", attention.attention_ref, _now())
        connection = self._connect()
        try:
            updated = self._replace_session(session, status=HumanBrowserStatus.PAUSED, sequence=session.sequence + 1)
            self._store_session(connection, updated)
            connection.execute("INSERT INTO human_browser_boundaries VALUES (?,?,?,?,?,?,?,?)", (request.boundary_ref, request.session_ref, request.reason.value, request.prompt_ref, request.status, request.attention_audio_ref, request.observed_at, request.record_sha256))
            connection.commit()
        finally:
            connection.close()
        return request

    def resume_after_human(self, boundary_ref: str) -> HumanBrowserSession:
        _ref(boundary_ref, "boundary_ref", _BOUNDARY_REF)
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM human_browser_boundaries WHERE boundary_ref=?", (boundary_ref,)).fetchone()
            if row is None:
                raise HumanBrowserNotFoundError("human boundary is not durable")
            if row["status"] != "OPEN":
                raise HumanBrowserPolicyError("human boundary is already resumed")
            session = self._session_from_row(connection.execute("SELECT * FROM human_browser_sessions WHERE session_ref=?", (row["session_ref"],)).fetchone())
            resumed = self._replace_session(session, status=HumanBrowserStatus.ACTIVE, sequence=session.sequence + 1)
            self._store_session(connection, resumed)
            connection.execute("UPDATE human_browser_boundaries SET status='RESUMED' WHERE boundary_ref=?", (boundary_ref,))
            connection.commit()
            return resumed
        finally:
            connection.close()

    def upload(self, session_ref: str, source_path: str | Path, send: Callable[[bytes], Mapping[str, object]]) -> VerifiedFileReceipt:
        session = self.get_session(session_ref)
        if session.status is HumanBrowserStatus.PAUSED:
            raise HumanBoundaryRequiredError("human boundary is open")
        path = Path(source_path).resolve()
        if not path.is_file():
            raise HumanBrowserNotFoundError("upload source is absent")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        remote = _safe(send(payload), "upload readback")
        if not isinstance(remote, Mapping) or remote.get("verified") is not True or remote.get("content_sha256") != digest:
            raise HumanBrowserError("upload result was not verified")
        return self._file_receipt("upload", path, digest, session)

    def download(self, session_ref: str, target_path: str | Path, fetch: Callable[[], bytes], *, expected_sha256: str) -> VerifiedFileReceipt:
        session = self.get_session(session_ref)
        _sha(expected_sha256, "expected_sha256")
        path = Path(target_path).resolve()
        if path.exists():
            raise HumanBrowserPolicyError("download target already exists")
        payload = fetch()
        if not isinstance(payload, bytes):
            raise HumanBrowserContractError("download provider must return bytes")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected_sha256:
            raise HumanBrowserError("download content digest did not verify")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.partial")
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return self._file_receipt("download", path, digest, session)

    def _file_receipt(self, operation: str, path: Path, digest: str, session: HumanBrowserSession) -> VerifiedFileReceipt:
        evidence_ref = f"evidence://minitz/browser-file/{uuid4().hex}"
        payload = {"operation": operation, "path": str(path), "session_ref": session.session_ref, "content_sha256": digest}
        return VerifiedFileReceipt(operation, str(path), digest, evidence_ref, _digest(payload))

    def _record_action(self, action: HumanBrowserAction, status: HumanActionStatus, verified: bool, readback: Mapping[str, object], boundary_ref: str | None) -> HumanBrowserActionResult:
        evidence_ref = f"evidence://minitz/browser-action/{action.action_ref.rsplit('/', 1)[-1]}"
        evidence_sha = _digest({"action": action.payload(), "readback": _plain(readback), "status": status.value})
        result = HumanBrowserActionResult(action, status, verified, readback, evidence_ref, evidence_sha, boundary_ref)
        connection = self._connect()
        try:
            connection.execute("INSERT OR REPLACE INTO human_browser_actions VALUES (?,?,?,?,?,?,?,?,?)", (action.action_ref, action.session_ref, status.value, int(verified), json.dumps({"action": action.payload(), "readback": _plain(readback)}, sort_keys=True), evidence_ref, evidence_sha, boundary_ref, result.observed_at))
            connection.commit()
        finally:
            connection.close()
        return result

    @staticmethod
    def _replace_session(
        session: HumanBrowserSession,
        *,
        status: HumanBrowserStatus | None = None,
        provider_session_ref: str | None = None,
        sequence: int | None = None,
    ) -> HumanBrowserSession:
        return HumanBrowserSession(
            session.session_ref,
            session.task_ref,
            session.run_ref,
            session.profile_ref,
            session.profile_path,
            session.allowed_origins,
            session.credential_refs,
            session.browser_name,
            session.status if status is None else status,
            False,
            session.provider_session_ref if provider_session_ref is None else provider_session_ref,
            session.sequence if sequence is None else sequence,
            _now(),
        )

    @staticmethod
    def _store_session(connection: sqlite3.Connection, session: HumanBrowserSession) -> None:
        connection.execute("INSERT OR REPLACE INTO human_browser_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (session.session_ref, session.task_ref, session.run_ref, session.profile_ref, session.profile_path, json.dumps(list(session.allowed_origins)), json.dumps(list(session.credential_refs)), session.browser_name, session.status.value, session.provider_session_ref, session.sequence, session.observed_at, session.record_sha256))

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> HumanBrowserSession:
        return HumanBrowserSession(row["session_ref"], row["task_ref"], row["run_ref"], row["profile_ref"], row["profile_path"], tuple(json.loads(row["allowed_origins_json"])), tuple(json.loads(row["credential_refs_json"])), row["browser_name"], HumanBrowserStatus(row["status"]), False, row["provider_session_ref"], int(row["sequence"]), row["observed_at"])


# Explicit aliases keep the contract discoverable to callers using either the
# task language (authenticated browser) or the implementation language.
AuthenticatedBrowserService = HumanBrowserService
OwnerAttentionService = OwnerAttentionAudio


__all__ = [
    "AuthenticatedBrowserService", "HumanActionStatus", "HumanActionType", "HumanBoundaryReason", "HumanBoundaryRequest",
    "HumanBrowserAction", "HumanBrowserActionResult", "HumanBrowserContractError", "HumanBrowserError", "HumanBrowserNotFoundError",
    "HumanBrowserPolicyError", "HumanBrowserProvider", "HumanBrowserService", "HumanBrowserSession", "HumanBrowserStatus",
    "HumanBoundaryRequiredError", "OwnerAttentionAudio", "OwnerAttentionReceipt", "OwnerAttentionService", "ReferenceHumanBrowserProvider",
    "VerifiedFileReceipt",
]
