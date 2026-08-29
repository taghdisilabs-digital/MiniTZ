"""Durable provider-neutral browser automation adapters."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import base64
import hashlib
import hmac
import http.client
from io import BytesIO
import json
import math
from pathlib import Path
import posixpath
import re
import sqlite3
import ssl
import threading
import tempfile
import time
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4
import zipfile

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .call_ledger import CallAuthorityError, CallConflictError, CallLedgerService, ToolCall, ToolCallRef
from .capability import Capability, CapabilityRef, CapabilityRegistry
from .execution import NodeExecutionAttempt, NodeExecutionService
from .filesystem import (
    FilesystemAdapter,
    FilesystemError,
    FilesystemRootRef,
)
from .graph import GraphService, NodeRef
from .http_adapter import HttpAdapter, HttpDestination, HttpDestinationRef, HttpTlsPolicy
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import (
    ProjectAccess,
    ProjectIntegrityError,
    ProjectNotFoundError,
    ProjectRef,
    ProjectScopeError,
    ProjectStore,
)
from .routing import (
    CapabilityImplementation,
    CapabilityImplementationRef,
    CapabilityImplementationRegistry,
    ImplementationKind,
    RoutingNotFoundError,
)
from .resource import ResourceFitRequest
from .run import ExecutionAttempt, RunRef, RunService
from .task import TaskRef, TaskRevisionService


_SESSION_ID = re.compile(r"bsess_[0-9a-f]{32}")
_PAGE_ID = re.compile(r"bpage_[0-9a-f]{32}")
_ACTION_ID = re.compile(r"bact_[0-9a-f]{32}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1000}")
_SECRET_REF = re.compile(r"secret://[^\s\x00-\x1f]{1,1000}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SELECTOR = re.compile(r"[^\x00-\x1f]{1,4096}")
_SAFE_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,254}")
_DOM_PROPERTY = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]{0,127}")
_EVENT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}")
_RESULT_MEDIA = "application/vnd.biella.browser-result+json"
_RECEIPT_MEDIA = "application/vnd.biella.browser-receipt+json"
_PNG_MEDIA = "image/png"
_CAPABILITY_NAMES = (
    "browser.click",
    "browser.download",
    "browser.evaluate",
    "browser.extract",
    "browser.inspect",
    "browser.navigate",
    "browser.open",
    "browser.screenshot",
    "browser.select",
    "browser.submit",
    "browser.type",
    "browser.upload",
    "browser.wait-for-condition",
)
_ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"


class BrowserAdapterError(Exception):
    """Base class for browser adapter failures."""


class BrowserContractError(BrowserAdapterError, ValueError):
    """A browser contract or provider payload is malformed."""


class BrowserScopeError(BrowserAdapterError):
    """A browser request crossed Project scope."""


class BrowserAuthorityError(BrowserAdapterError):
    """Task, Node, side-effect, egress, or session authority is absent."""


class BrowserConflictError(BrowserAdapterError):
    """An immutable browser session or action identity conflicts."""


class BrowserNotFoundError(BrowserAdapterError):
    """Required browser runtime or durable evidence is unavailable."""


class BrowserIntegrityError(BrowserAdapterError):
    """Durable browser evidence failed verification."""


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise BrowserContractError("browser evidence is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _text(value: object, name: str, maximum: int = 64 * 1024) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode()) > maximum
        or any(ord(character) < 32 and character not in "\t\n" for character in value)
    ):
        raise BrowserContractError(f"{name} is malformed or unbounded")
    return value


def _timestamp(value: object, name: str) -> str:
    text = _text(value, name, 128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BrowserContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BrowserContractError(f"{name} must be timezone-aware")
    return text


def _ref(value: object, name: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise BrowserContractError(f"{name} is malformed")
    return value


def _refs(values: Sequence[str], name: str, *, empty: bool = True) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise BrowserContractError(f"{name} must be a sequence")
    copied = tuple(values)
    if (not empty and not copied) or len(copied) > 256 or len(set(copied)) != len(copied):
        raise BrowserContractError(f"{name} is empty, duplicated, or unbounded")
    for value in copied:
        _ref(value, name)
    return tuple(sorted(copied))


def _mapping(value: Mapping[str, object], name: str, maximum: int = 256) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or len(value) > maximum:
        raise BrowserContractError(f"{name} is malformed or unbounded")
    copied: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or _KEY.fullmatch(key) is None:
            raise BrowserContractError(f"{name} key is malformed")
        _json(item)
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _content_payload(value: ContentRef | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "algorithm": value.algorithm,
        "digest": value.digest,
        "media_type": value.media_type,
        "size_bytes": value.size_bytes,
    }


def _object_ref(value: ContentRef | ArtifactRef | ToolCallRef | None) -> str | None:
    return None if value is None else value.value


def _safe_path(value: object, name: str) -> str:
    text = _text(value, name, 8192)
    if not text.startswith("/") or "?" in text or "#" in text or "\\" in text:
        raise BrowserContractError(f"{name} must be a canonical absolute path without query or fragment")
    decoded = unquote(text)
    if any(part in {".", ".."} for part in decoded.split("/")):
        raise BrowserContractError(f"{name} contains traversal")
    normalized = posixpath.normpath(decoded)
    if decoded.endswith("/") and normalized != "/":
        normalized += "/"
    canonical = quote(normalized, safe="/:@-._~!$&'()*+,;=")
    if canonical != text:
        raise BrowserContractError(f"{name} is not canonical")
    return canonical


def _path_allowed(path: str, prefixes: Sequence[str]) -> bool:
    decoded = unquote(path)
    return any(
        prefix == "/"
        or decoded == unquote(prefix).rstrip("/")
        or decoded.startswith(unquote(prefix).rstrip("/") + "/")
        for prefix in prefixes
    )


def _safe_url(value: object) -> str:
    text = _text(value, "browser page URL", 8192)
    if text == "about:blank":
        return text
    parsed = urlsplit(text)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise BrowserContractError("browser page URL must be an exact safe http(s) URL without credentials, query, or fragment")
    host = parsed.hostname.lower()
    if not host or any(ord(character) > 127 for character in host):
        raise BrowserContractError("browser page URL host is malformed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise BrowserContractError("browser page URL port is malformed") from exc
    default = 443 if parsed.scheme == "https" else 80
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != default:
        authority = f"{authority}:{port}"
    return f"{parsed.scheme}://{authority}{_safe_path(parsed.path or '/', 'browser page path')}"


def _artifact_ref_payload(value: ArtifactRef | None) -> str | None:
    return None if value is None else value.value


class BrowserActionType(str, Enum):
    NAVIGATE = "navigate"
    INSPECT = "inspect"
    EXTRACT = "extract"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SCREENSHOT = "screenshot"
    EVALUATE = "evaluate"
    WAIT_FOR_CONDITION = "wait_for_condition"
    SUBMIT = "submit"

    @property
    def capability_name(self) -> str:
        return f"browser.{self.value.replace('_', '-')}"


class BrowserSideEffect(str, Enum):
    READ_ONLY = "READ_ONLY"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"


class BrowserSessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    LOST = "LOST"
    CLOSED = "CLOSED"


class BrowserWaitConditionType(str, Enum):
    SELECTOR = "selector"
    URL = "url"
    DOM_PROPERTY = "dom_property"
    NETWORK_IDLE = "network_idle"
    EVENT = "event"


class BrowserExecutionFailure(str, Enum):
    AUTHORITY_DENIED = "AUTHORITY_DENIED"
    EGRESS_DENIED = "EGRESS_DENIED"
    EXTERNAL_SIDE_EFFECT_DENIED = "EXTERNAL_SIDE_EFFECT_DENIED"
    SESSION_LOST = "SESSION_LOST"
    STALE_GENERATION = "STALE_GENERATION"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    DOWNLOAD_INTERRUPTED = "DOWNLOAD_INTERRUPTED"
    DOWNLOAD_INTEGRITY_FAILED = "DOWNLOAD_INTEGRITY_FAILED"
    UPLOAD_DENIED = "UPLOAD_DENIED"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    CONTENT_INTEGRITY_FAILED = "CONTENT_INTEGRITY_FAILED"
    POSTCONDITION_FAILED = "POSTCONDITION_FAILED"


@dataclass(frozen=True)
class BrowserWaitCondition:
    condition_type: BrowserWaitConditionType
    selector: str | None = None
    url: str | None = None
    property_name: str | None = None
    expected: str | int | float | bool | None = None
    idle_ms: int | None = None
    event_name: str | None = None
    condition_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.condition_type, BrowserWaitConditionType):
            raise BrowserContractError("browser wait condition type is malformed")
        if self.selector is not None and _SELECTOR.fullmatch(self.selector) is None:
            raise BrowserContractError("browser wait selector is malformed")
        if self.url is not None:
            object.__setattr__(self, "url", _safe_url(self.url))
        if self.property_name is not None and _DOM_PROPERTY.fullmatch(self.property_name) is None:
            raise BrowserContractError("browser wait DOM property is malformed")
        if isinstance(self.expected, float) and not math.isfinite(self.expected):
            raise BrowserContractError("browser wait expected value is malformed")
        if self.idle_ms is not None and (
            not isinstance(self.idle_ms, int)
            or isinstance(self.idle_ms, bool)
            or not 0 <= self.idle_ms <= 60_000
        ):
            raise BrowserContractError("browser network-idle interval is malformed")
        if self.event_name is not None and _EVENT_NAME.fullmatch(self.event_name) is None:
            raise BrowserContractError("browser wait event name is malformed")
        valid = {
            BrowserWaitConditionType.SELECTOR: self.selector is not None and all(
                value is None for value in (self.url, self.property_name, self.idle_ms, self.event_name)
            ),
            BrowserWaitConditionType.URL: self.url is not None and all(
                value is None for value in (self.selector, self.property_name, self.idle_ms, self.event_name)
            ),
            BrowserWaitConditionType.DOM_PROPERTY: self.selector is not None
            and self.property_name is not None
            and all(value is None for value in (self.url, self.idle_ms, self.event_name)),
            BrowserWaitConditionType.NETWORK_IDLE: self.idle_ms is not None
            and all(value is None for value in (self.selector, self.url, self.property_name, self.event_name)),
            BrowserWaitConditionType.EVENT: self.event_name is not None
            and all(value is None for value in (self.selector, self.url, self.property_name, self.idle_ms)),
        }
        if not valid[self.condition_type]:
            raise BrowserContractError("browser wait condition fields do not match its type")
        object.__setattr__(self, "condition_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "condition_type": self.condition_type.value,
            "event_name": self.event_name,
            "expected": self.expected,
            "idle_ms": self.idle_ms,
            "property_name": self.property_name,
            "selector": self.selector,
            "url": self.url,
        }


@dataclass(frozen=True)
class BrowserFilesystemUploadSource:
    root_ref: FilesystemRootRef
    relative_path: str
    media_type: str
    source_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.root_ref, FilesystemRootRef):
            raise BrowserContractError("browser upload source requires FilesystemRootRef")
        path = _text(self.relative_path, "browser upload relative path", 4096)
        if path.startswith("/") or "\\" in path or any(part in {"", ".", ".."} for part in path.split("/")):
            raise BrowserContractError("browser upload source path is not a canonical relative path")
        _text(self.media_type, "browser upload media type", 256)
        object.__setattr__(self, "source_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "media_type": self.media_type,
            "relative_path": self.relative_path,
            "root_ref": self.root_ref.value,
        }


@dataclass(frozen=True, order=True)
class BrowserSessionRef:
    project_ref: ProjectRef
    session_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or _SESSION_ID.fullmatch(self.session_id) is None:
            raise BrowserContractError("browser session identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> BrowserSessionRef:
        return cls(project_ref, f"bsess_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"browser-session://{self.project_ref.value}/{self.session_id}"


@dataclass(frozen=True, order=True)
class BrowserActionRef:
    project_ref: ProjectRef
    action_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or _ACTION_ID.fullmatch(self.action_id) is None:
            raise BrowserContractError("browser action identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> BrowserActionRef:
        return cls(project_ref, f"bact_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"browser-action://{self.project_ref.value}/{self.action_id}"


@dataclass(frozen=True)
class BrowserExecutionBinding:
    project_ref: ProjectRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    node_ref: NodeRef
    node_attempt_id: str
    node_fence: int
    data_policy_ref: str | None
    egress_policy_ref: str | None
    binding_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        refs = (self.task_ref.project_ref, self.run_ref.project_ref, self.node_ref.project_ref)
        if not isinstance(self.project_ref, ProjectRef) or any(value != self.project_ref for value in refs):
            raise BrowserScopeError("browser execution binding crossed Project scope")
        if _SHA256.fullmatch(self.task_digest) is None:
            raise BrowserContractError("browser Task digest is malformed")
        _text(self.node_attempt_id, "browser Node attempt ID", 256)
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise BrowserContractError("browser Node fence is malformed")
        if self.data_policy_ref is not None:
            _ref(self.data_policy_ref, "browser data policy ref")
        if self.egress_policy_ref is not None:
            _ref(self.egress_policy_ref, "browser egress policy ref")
        object.__setattr__(self, "binding_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "data_policy_ref": self.data_policy_ref,
            "egress_policy_ref": self.egress_policy_ref,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "node_ref": self.node_ref.value,
            "project_ref": self.project_ref.value,
            "run_ref": f"run://{self.project_ref.value}/{self.run_ref.run_id}",
            "task_digest": self.task_digest,
            "task_ref": f"task://{self.project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}",
        }


@dataclass(frozen=True)
class BrowserSessionSpec:
    session_ref: BrowserSessionRef
    binding: BrowserExecutionBinding
    capability_ref: CapabilityRef
    controller_destination_ref: HttpDestinationRef | None
    allowed_destination_refs: tuple[HttpDestinationRef, ...]
    browser_name: str
    resource_refs: tuple[str, ...]
    egress_enforcer_ref: str
    timeout_seconds: float = 60.0
    spec_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.binding.project_ref
        if self.session_ref.project_ref != project or self.capability_ref != CapabilityRef("browser.open", "1.0.0"):
            raise BrowserScopeError("browser session spec crossed Project scope or lacks browser.open capability")
        if self.controller_destination_ref is not None and self.controller_destination_ref.project_ref != project:
            raise BrowserScopeError("browser controller destination crossed Project scope")
        if not isinstance(self.allowed_destination_refs, tuple) or not self.allowed_destination_refs:
            raise BrowserContractError("browser session requires bounded allowed destinations")
        if any(item.project_ref != project for item in self.allowed_destination_refs) or len(set(self.allowed_destination_refs)) != len(self.allowed_destination_refs):
            raise BrowserScopeError("browser destination allowlist crossed Project scope or is duplicated")
        object.__setattr__(self, "allowed_destination_refs", tuple(sorted(self.allowed_destination_refs)))
        _text(self.browser_name, "browser name", 128)
        object.__setattr__(self, "resource_refs", _refs(self.resource_refs, "browser Resource refs"))
        _ref(self.egress_enforcer_ref, "browser egress enforcer ref")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not 0 < float(self.timeout_seconds) <= 3600:
            raise BrowserContractError("browser session timeout is malformed")
        object.__setattr__(self, "spec_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "allowed_destination_refs": [item.value for item in self.allowed_destination_refs],
            "binding": self.binding.payload(),
            "browser_name": self.browser_name,
            "capability_ref": self.capability_ref.value,
            "controller_destination_ref": None if self.controller_destination_ref is None else self.controller_destination_ref.value,
            "egress_enforcer_ref": self.egress_enforcer_ref,
            "resource_refs": list(self.resource_refs),
            "session_ref": self.session_ref.value,
            "timeout_seconds": float(self.timeout_seconds),
        }


@dataclass(frozen=True)
class BrowserSessionIdentity:
    session_ref: BrowserSessionRef
    adapter_ref: str
    implementation_ref: str
    browser_name: str
    browser_version: str
    runtime_version: str
    provider_session_id: str
    resource_refs: tuple[str, ...]
    allowed_destination_refs: tuple[HttpDestinationRef, ...]
    egress_enforcer_ref: str
    generation: int
    reality: str
    created_at: str = field(default_factory=_now)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.session_ref.project_ref
        _ref(self.adapter_ref, "browser adapter ref")
        _ref(self.implementation_ref, "browser implementation ref")
        _text(self.browser_name, "browser name", 128)
        _text(self.browser_version, "browser version", 1024)
        _text(self.runtime_version, "browser runtime version", 1024)
        _text(self.provider_session_id, "provider session ID", 1024)
        object.__setattr__(self, "resource_refs", _refs(self.resource_refs, "browser Resource refs"))
        if not isinstance(self.allowed_destination_refs, tuple) or not self.allowed_destination_refs:
            raise BrowserContractError("browser identity requires allowed destinations")
        if any(item.project_ref != project for item in self.allowed_destination_refs):
            raise BrowserScopeError("browser identity destination crossed Project scope")
        object.__setattr__(self, "allowed_destination_refs", tuple(sorted(self.allowed_destination_refs)))
        _ref(self.egress_enforcer_ref, "browser egress enforcer ref")
        if not isinstance(self.generation, int) or isinstance(self.generation, bool) or self.generation < 1:
            raise BrowserContractError("browser generation is malformed")
        if self.reality not in {"REAL", "REFERENCE"}:
            raise BrowserContractError("browser reality must be REAL or REFERENCE")
        _timestamp(self.created_at, "browser session created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "allowed_destination_refs": [item.value for item in self.allowed_destination_refs],
            "browser_name": self.browser_name,
            "browser_version": self.browser_version,
            "created_at": self.created_at,
            "egress_enforcer_ref": self.egress_enforcer_ref,
            "generation": self.generation,
            "implementation_ref": self.implementation_ref,
            "provider_session_id": self.provider_session_id,
            "reality": self.reality,
            "resource_refs": list(self.resource_refs),
            "runtime_version": self.runtime_version,
            "session_ref": self.session_ref.value,
        }


@dataclass(frozen=True)
class BrowserPageRef:
    session_ref: BrowserSessionRef
    page_id: str
    generation: int
    current_url: str
    observed_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if _PAGE_ID.fullmatch(self.page_id) is None or not isinstance(self.generation, int) or self.generation < 1:
            raise BrowserContractError("browser page identity is malformed")
        object.__setattr__(self, "current_url", _safe_url(self.current_url))
        _timestamp(self.observed_at, "browser page observed_at")

    @property
    def project_ref(self) -> ProjectRef:
        return self.session_ref.project_ref

    @property
    def value(self) -> str:
        return f"browser-page://{self.project_ref.value}/{self.session_ref.session_id}/{self.generation}/{self.page_id}"

    def payload(self) -> dict[str, object]:
        return {
            "current_url": self.current_url,
            "generation": self.generation,
            "observed_at": self.observed_at,
            "page_ref": self.value,
            "session_ref": self.session_ref.value,
        }


@dataclass(frozen=True)
class BrowserAction:
    action_ref: BrowserActionRef
    binding: BrowserExecutionBinding
    session_identity: BrowserSessionIdentity
    page_ref: BrowserPageRef | None
    capability_ref: CapabilityRef
    action_type: BrowserActionType
    target: str | None
    value_ref: ContentRef | ArtifactRef | BrowserFilesystemUploadSource | None
    secret_ref: str | None
    destination_ref: HttpDestinationRef | None
    side_effect: BrowserSideEffect
    timeout_seconds: float
    maximum_output_bytes: int = 16 * 1024 * 1024
    expected_output_sha256: str | None = None
    expected_filename: str | None = None
    precondition: Mapping[str, object] = field(default_factory=dict)
    postcondition: Mapping[str, object] = field(default_factory=dict)
    wait_condition: BrowserWaitCondition | None = None
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.binding.project_ref
        if self.action_ref.project_ref != project or self.session_identity.session_ref.project_ref != project:
            raise BrowserScopeError("browser action crossed Project scope")
        if self.page_ref is not None and self.page_ref.project_ref != project:
            raise BrowserScopeError("browser page crossed Project scope")
        if self.page_ref is not None and (
            self.page_ref.session_ref != self.session_identity.session_ref
            or self.page_ref.generation != self.session_identity.generation
        ):
            raise BrowserAuthorityError("browser page and session generation differ")
        if self.capability_ref != CapabilityRef(self.action_type.capability_name, "1.0.0"):
            raise BrowserAuthorityError("browser action Capability is not exact")
        if self.target is not None and _SELECTOR.fullmatch(self.target) is None:
            raise BrowserContractError("browser action target is malformed or unbounded")
        if self.action_type in {BrowserActionType.NAVIGATE, BrowserActionType.DOWNLOAD}:
            if self.target is None:
                raise BrowserContractError("browser navigation/download requires a target path")
            object.__setattr__(self, "target", _safe_path(self.target, "browser action target path"))
        if self.action_type not in {BrowserActionType.NAVIGATE, BrowserActionType.INSPECT} and self.page_ref is None:
            raise BrowserContractError("browser action requires an exact page generation")
        if self.value_ref is not None and isinstance(self.value_ref, ArtifactRef) and self.value_ref.project_ref != project:
            raise BrowserScopeError("browser value Artifact crossed Project scope")
        if isinstance(self.value_ref, BrowserFilesystemUploadSource) and self.value_ref.root_ref.project_ref != project:
            raise BrowserScopeError("browser upload FilesystemRoot crossed Project scope")
        if self.secret_ref is not None and _SECRET_REF.fullmatch(self.secret_ref) is None:
            raise BrowserContractError("browser secret ref is malformed")
        if self.value_ref is not None and self.secret_ref is not None:
            raise BrowserContractError("browser action cannot bind both ordinary and secret value")
        if self.secret_ref is not None and self.action_type is not BrowserActionType.TYPE:
            raise BrowserAuthorityError("browser secrets are only valid for transient typing")
        if self.action_type is BrowserActionType.UPLOAD and not isinstance(
            self.value_ref,
            (ContentRef, ArtifactRef, BrowserFilesystemUploadSource),
        ):
            raise BrowserAuthorityError("browser upload requires an authorized Artifact, ContentRef, or FilesystemRoot source")
        if isinstance(self.value_ref, BrowserFilesystemUploadSource) and self.action_type is not BrowserActionType.UPLOAD:
            raise BrowserAuthorityError("browser FilesystemRoot source is valid only for upload")
        destination_required = {
            BrowserActionType.NAVIGATE,
            BrowserActionType.DOWNLOAD,
            BrowserActionType.UPLOAD,
            BrowserActionType.SUBMIT,
        }
        if self.action_type in destination_required and self.destination_ref is None:
            raise BrowserAuthorityError("browser action requires an exact destination")
        if self.destination_ref is not None and self.destination_ref.project_ref != project:
            raise BrowserScopeError("browser action destination crossed Project scope")
        external = {
            BrowserActionType.CLICK,
            BrowserActionType.TYPE,
            BrowserActionType.SELECT,
            BrowserActionType.UPLOAD,
            BrowserActionType.SUBMIT,
        }
        required_side_effect = BrowserSideEffect.EXTERNAL_SIDE_EFFECT if self.action_type in external else BrowserSideEffect.READ_ONLY
        if self.side_effect is not required_side_effect:
            raise BrowserAuthorityError("browser action side-effect class is not fail-closed")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not 0 < float(self.timeout_seconds) <= 3600:
            raise BrowserContractError("browser action timeout is malformed")
        if not isinstance(self.maximum_output_bytes, int) or isinstance(self.maximum_output_bytes, bool) or not 0 <= self.maximum_output_bytes <= 2**31:
            raise BrowserContractError("browser output bound is malformed")
        if self.expected_output_sha256 is not None and _SHA256.fullmatch(self.expected_output_sha256) is None:
            raise BrowserContractError("browser expected digest is malformed")
        if self.expected_filename is not None and _SAFE_FILENAME.fullmatch(self.expected_filename) is None:
            raise BrowserContractError("browser expected filename is unsafe")
        if self.action_type is BrowserActionType.DOWNLOAD and self.expected_filename is None:
            raise BrowserContractError("browser download requires an exact expected filename")
        object.__setattr__(self, "precondition", _mapping(self.precondition, "browser precondition"))
        object.__setattr__(self, "postcondition", _mapping(self.postcondition, "browser postcondition"))
        if self.wait_condition is not None and not isinstance(self.wait_condition, BrowserWaitCondition):
            raise BrowserContractError("browser wait condition is malformed")
        if self.action_type is BrowserActionType.WAIT_FOR_CONDITION:
            if (self.target is None) == (self.wait_condition is None):
                raise BrowserContractError("browser wait requires exactly one selector target or structured condition")
        elif self.wait_condition is not None:
            raise BrowserContractError("browser wait condition is valid only for wait_for_condition")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "action_ref": self.action_ref.value,
            "action_type": self.action_type.value,
            "binding": self.binding.payload(),
            "capability_ref": self.capability_ref.value,
            "destination_ref": None if self.destination_ref is None else self.destination_ref.value,
            "expected_filename": self.expected_filename,
            "expected_output_sha256": self.expected_output_sha256,
            "maximum_output_bytes": self.maximum_output_bytes,
            "page_ref": None if self.page_ref is None else self.page_ref.payload(),
            "postcondition": dict(self.postcondition),
            "precondition": dict(self.precondition),
            "secret_ref": self.secret_ref,
            "session_identity": self.session_identity.payload(),
            "side_effect": self.side_effect.value,
            "target": self.target,
            "timeout_seconds": float(self.timeout_seconds),
            "value_ref": self.value_ref.payload() if isinstance(self.value_ref, BrowserFilesystemUploadSource) else _object_ref(self.value_ref),
            "wait_condition": None if self.wait_condition is None else self.wait_condition.payload(),
        }


def _action_wait_condition(action: BrowserAction) -> BrowserWaitCondition:
    if action.wait_condition is not None:
        return action.wait_condition
    assert action.target is not None
    return BrowserWaitCondition(BrowserWaitConditionType.SELECTOR, selector=action.target)


@dataclass(frozen=True)
class BrowserSessionState:
    identity: BrowserSessionIdentity
    status: BrowserSessionStatus
    page_ref: BrowserPageRef | None
    tool_call_ref: ToolCallRef
    receipt_artifact_ref: ArtifactRef
    cause: str | None
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.identity.session_ref.project_ref
        if self.tool_call_ref.project_ref != project or self.receipt_artifact_ref.project_ref != project:
            raise BrowserScopeError("browser session evidence crossed Project scope")
        if self.page_ref is not None and (
            self.page_ref.session_ref != self.identity.session_ref
            or self.page_ref.generation != self.identity.generation
        ):
            raise BrowserIntegrityError("browser session page generation differs")
        if self.cause is not None:
            _text(self.cause, "browser session state cause", 2048)
        _timestamp(self.observed_at, "browser session observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "cause": self.cause,
            "identity": self.identity.payload(),
            "observed_at": self.observed_at,
            "page_ref": None if self.page_ref is None else self.page_ref.payload(),
            "receipt_artifact_ref": self.receipt_artifact_ref.value,
            "status": self.status.value,
            "tool_call_ref": self.tool_call_ref.value,
        }


@dataclass(frozen=True)
class BrowserActionResult:
    action_ref: BrowserActionRef
    action_type: BrowserActionType
    session_identity: BrowserSessionIdentity
    page_ref: BrowserPageRef | None
    output_ref: ContentRef | None
    output_artifact_ref: ArtifactRef | None
    receipt_artifact_ref: ArtifactRef
    tool_call_ref: ToolCallRef
    failure: BrowserExecutionFailure | None
    failure_reason: str | None
    side_effect: BrowserSideEffect
    provider_trace_id: str | None
    provider_metadata: Mapping[str, object]
    latency_ms: float
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.action_ref.project_ref
        if not isinstance(self.action_type, BrowserActionType):
            raise BrowserContractError("browser result action type is malformed")
        if (
            self.session_identity.session_ref.project_ref != project
            or self.receipt_artifact_ref.project_ref != project
            or self.tool_call_ref.project_ref != project
            or (self.output_artifact_ref is not None and self.output_artifact_ref.project_ref != project)
        ):
            raise BrowserScopeError("browser result evidence crossed Project scope")
        if self.page_ref is not None and self.page_ref.project_ref != project:
            raise BrowserScopeError("browser result page crossed Project scope")
        if (self.output_ref is None) != (self.output_artifact_ref is None):
            raise BrowserIntegrityError("browser output ContentRef and Artifact differ")
        if self.failure is None and self.output_ref is None:
            raise BrowserIntegrityError("successful browser action lacks durable output")
        if self.failure is not None and self.output_ref is not None:
            raise BrowserIntegrityError("failed browser action cannot publish output")
        if (self.failure is None) != (self.failure_reason is None):
            raise BrowserIntegrityError("browser failure and reason must be present together")
        if self.failure_reason is not None:
            _text(self.failure_reason, "browser failure reason", 2048)
        if self.provider_trace_id is not None:
            _text(self.provider_trace_id, "browser provider trace ID", 1024)
        object.__setattr__(self, "provider_metadata", _mapping(self.provider_metadata, "browser provider metadata"))
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)) or not math.isfinite(float(self.latency_ms)) or self.latency_ms < 0:
            raise BrowserContractError("browser action latency is malformed")
        _timestamp(self.completed_at, "browser action completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def succeeded(self) -> bool:
        return self.failure is None

    def payload(self) -> dict[str, object]:
        return {
            "action_ref": self.action_ref.value,
            "action_type": self.action_type.value,
            "completed_at": self.completed_at,
            "failure": None if self.failure is None else self.failure.value,
            "failure_reason": self.failure_reason,
            "latency_ms": float(self.latency_ms),
            "output_artifact_ref": _artifact_ref_payload(self.output_artifact_ref),
            "output_ref": _content_payload(self.output_ref),
            "page_ref": None if self.page_ref is None else self.page_ref.payload(),
            "provider_trace_id": self.provider_trace_id,
            "provider_metadata": dict(self.provider_metadata),
            "receipt_artifact_ref": self.receipt_artifact_ref.value,
            "session_identity": self.session_identity.payload(),
            "side_effect": self.side_effect.value,
            "tool_call_ref": self.tool_call_ref.value,
        }


@dataclass(frozen=True)
class BrowserCancellationReceipt:
    action_ref: BrowserActionRef
    accepted: bool
    idempotency_key: str
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool) or _KEY.fullmatch(self.idempotency_key) is None:
            raise BrowserContractError("browser cancellation receipt is malformed")
        _timestamp(self.observed_at, "browser cancellation observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "action_ref": self.action_ref.value,
            "idempotency_key": self.idempotency_key,
            "observed_at": self.observed_at,
        }


@runtime_checkable
class BrowserAdapter(Protocol):
    def create_session(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        spec: BrowserSessionSpec,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> BrowserSessionState: ...

    def navigate(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def inspect(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def perform_action(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def extract(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def capture_screenshot(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def upload(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def download(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def wait_for_condition(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult: ...

    def cancel(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action_ref: BrowserActionRef, *, idempotency_key: str) -> BrowserCancellationReceipt: ...

    def close_session(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: BrowserSessionIdentity, *, idempotency_key: str) -> BrowserSessionState: ...

    def inspect_session(self, access: ProjectAccess, session_ref: BrowserSessionRef) -> BrowserSessionState: ...


@dataclass(frozen=True)
class _BackendSession:
    provider_session_id: str
    browser_name: str
    browser_version: str
    runtime_version: str
    provider_trace_id: str | None = None


@dataclass(frozen=True)
class _BackendResult:
    content: bytes
    media_type: str
    current_url: str
    provider_trace_id: str | None = None
    provider_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _ResolvedBrowserValue:
    content_ref: ContentRef
    content: bytes | None


class _BackendFailure(Exception):
    def __init__(self, failure: BrowserExecutionFailure, reason: str) -> None:
        super().__init__(reason)
        self.failure = failure
        self.reason = reason


@dataclass
class _ActiveAction:
    cancellation: threading.Event


class _BaseBrowserAdapter:
    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        http_adapter: HttpAdapter,
        *,
        adapter_ref: str,
        implementation_ref: str,
        reality: str,
    ) -> None:
        self.database_path = Path(database_path)
        self.object_store = object_store
        if not isinstance(http_adapter, HttpAdapter):
            raise BrowserContractError("browser adapter requires the accepted HTTP destination registry")
        self.http = http_adapter
        self.adapter_ref = _ref(adapter_ref, "browser adapter ref")
        self.implementation_ref = _ref(implementation_ref, "browser implementation ref")
        if reality not in {"REAL", "REFERENCE"}:
            raise BrowserContractError("browser adapter reality is malformed")
        self.reality = reality
        self.projects = ProjectStore(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.runs = RunService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.calls = CallLedgerService(self.database_path)
        self.filesystem = FilesystemAdapter(self.database_path, object_store)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.implementations = CapabilityImplementationRegistry(self.database_path)
        self._active: dict[str, _ActiveAction] = {}
        self._runtime_secrets: dict[str, set[bytes]] = {}
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS browser_session_generations (
                  project_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  identity_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,session_id,generation),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS browser_session_claims (
                  project_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  spec_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,idempotency_key),
                  FOREIGN KEY(project_id,session_id,generation) REFERENCES browser_session_generations(project_id,session_id,generation) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS browser_session_states (
                  project_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  sequence INTEGER NOT NULL,
                  state_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,session_id,generation,sequence),
                  FOREIGN KEY(project_id,session_id,generation) REFERENCES browser_session_generations(project_id,session_id,generation) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS browser_session_heads (
                  project_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  sequence INTEGER NOT NULL,
                  state_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,session_id),
                  FOREIGN KEY(project_id,session_id,generation,sequence) REFERENCES browser_session_states(project_id,session_id,generation,sequence) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS browser_action_claims (
                  project_id TEXT NOT NULL,
                  action_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  tool_call_id TEXT NOT NULL,
                  PRIMARY KEY(project_id,action_id),
                  UNIQUE(project_id,tool_call_id),
                  FOREIGN KEY(project_id,tool_call_id) REFERENCES calls(project_id,call_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS browser_action_results (
                  project_id TEXT NOT NULL,
                  action_id TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,action_id),
                  FOREIGN KEY(project_id,action_id) REFERENCES browser_action_claims(project_id,action_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS browser_cancellations (
                  project_id TEXT NOT NULL,
                  action_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  receipt_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,action_id,idempotency_key),
                  FOREIGN KEY(project_id,action_id) REFERENCES browser_action_claims(project_id,action_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS browser_session_generations_no_update BEFORE UPDATE ON browser_session_generations BEGIN SELECT RAISE(ABORT,'browser session generation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_generations_no_delete BEFORE DELETE ON browser_session_generations BEGIN SELECT RAISE(ABORT,'browser session generation cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_claims_no_update BEFORE UPDATE ON browser_session_claims BEGIN SELECT RAISE(ABORT,'browser session claim is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_claims_no_delete BEFORE DELETE ON browser_session_claims BEGIN SELECT RAISE(ABORT,'browser session claim cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_states_no_update BEFORE UPDATE ON browser_session_states BEGIN SELECT RAISE(ABORT,'browser session state history is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_states_no_delete BEFORE DELETE ON browser_session_states BEGIN SELECT RAISE(ABORT,'browser session state history cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_heads_no_delete BEFORE DELETE ON browser_session_heads BEGIN SELECT RAISE(ABORT,'browser session head cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS browser_session_heads_monotonic BEFORE UPDATE ON browser_session_heads
                  WHEN NEW.generation < OLD.generation OR (NEW.generation = OLD.generation AND NEW.sequence <= OLD.sequence)
                  BEGIN SELECT RAISE(ABORT,'browser session head must advance monotonically'); END;
                CREATE TRIGGER IF NOT EXISTS browser_action_claims_no_update BEFORE UPDATE ON browser_action_claims BEGIN SELECT RAISE(ABORT,'browser action claim is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS browser_action_claims_no_delete BEFORE DELETE ON browser_action_claims BEGIN SELECT RAISE(ABORT,'browser action claim cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS browser_action_results_no_update BEFORE UPDATE ON browser_action_results BEGIN SELECT RAISE(ABORT,'browser action result is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS browser_action_results_no_delete BEFORE DELETE ON browser_action_results BEGIN SELECT RAISE(ABORT,'browser action result cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS browser_cancellations_no_update BEFORE UPDATE ON browser_cancellations BEGIN SELECT RAISE(ABORT,'browser cancellation is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS browser_cancellations_no_delete BEFORE DELETE ON browser_cancellations BEGIN SELECT RAISE(ABORT,'browser cancellation cannot be deleted'); END;
                """
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def capability_ref(action: BrowserActionType | None = None) -> CapabilityRef:
        return CapabilityRef("browser.open" if action is None else action.capability_name, "1.0.0")

    def register_capabilities(self, access: ProjectAccess) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for name in _CAPABILITY_NAMES:
            capability_ref = CapabilityRef(name, "1.0.0")
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    f"Provider-neutral {name} browser operation",
                    input_contract={"request": f"schema://biella/{name.replace('.', '-')}-request/1"},
                    output_contract={"result": f"schema://biella/{name.replace('.', '-')}-result/1"},
                    side_effects=("external.side-effect",) if name in {"browser.click", "browser.select", "browser.submit", "browser.type", "browser.upload"} else (),
                )
            )
            implementation_ref = CapabilityImplementationRef(
                access.project_ref,
                f"cimpl_{hashlib.sha256(f'{self.implementation_ref}:{name}'.encode()).hexdigest()[:32]}",
            )
            try:
                implementation = self.implementations.get(access, implementation_ref)
            except RoutingNotFoundError:
                implementation = self.implementations.register(
                    access,
                    CapabilityImplementation(
                        implementation_ref,
                        capability.capability_ref,
                        "1.0.0",
                        ImplementationKind.RUNTIME,
                        self.implementation_ref,
                        self.adapter_ref,
                        features=("session-generation-fence", "durable-artifacts", "tool-call-ledger"),
                        input_features=("structured-action", "artifact-upload", "secret-ref"),
                        output_features=("content-ref", "artifact", "receipt"),
                        side_effect_authority="EXTERNAL_WRITE" if name in {"browser.click", "browser.select", "browser.submit", "browser.type", "browser.upload"} else "READ_ONLY",
                        remote_egress=True,
                        resource_kinds=("managed.browser",) if self.reality == "REAL" else ("cpu.reference",),
                        resource_fit=ResourceFitRequest(),
                        metadata={"adapter_reality": self.reality.lower(), "browser_capability": name},
                    ),
                    idempotency_key=f"browser-impl-{hashlib.sha256(f'{self.implementation_ref}:{name}'.encode()).hexdigest()[:24]}",
                )
            registered[capability_ref] = implementation
        return MappingProxyType(registered)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        if not isinstance(access, ProjectAccess):
            raise BrowserAuthorityError("ProjectAccess is required")
        if access.project_ref != project_ref:
            raise BrowserScopeError("browser access crossed Project scope")
        try:
            self.projects.get_project(access, project_ref)
        except ProjectScopeError as exc:
            raise BrowserScopeError("browser Project authorization failed") from exc
        except (ProjectNotFoundError, ProjectIntegrityError) as exc:
            raise BrowserAuthorityError("browser Project authorization failed") from exc

    def _run_attempt(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        value = next(
            (
                item
                for item in self.runs.list_attempts(access, attempt.run_ref)
                if item.attempt_id == attempt.run_attempt_id and item.fence == attempt.run_fence
            ),
            None,
        )
        if value is None:
            raise BrowserAuthorityError("exact browser Run authority is unavailable")
        return value

    def _require_live_node(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> None:
        execution = self.executions.get_node_execution(access, attempt.node_ref)
        if (
            execution.status not in {"RUNNING", "WAITING_EXTERNAL"}
            or execution.current_attempt_id != attempt.attempt_id
            or execution.current_fence != attempt.fence
            or execution.current_run_attempt_id != attempt.run_attempt_id
            or execution.current_run_fence != attempt.run_fence
        ):
            raise BrowserAuthorityError("late or stale browser Node authority was rejected")

    def _require_binding(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        binding: BrowserExecutionBinding,
        capability_ref: CapabilityRef,
        side_effect: BrowserSideEffect,
    ) -> None:
        self._authorize(access, binding.project_ref)
        if (
            attempt.task_ref != binding.task_ref
            or attempt.task_digest != binding.task_digest
            or attempt.run_ref != binding.run_ref
            or attempt.node_ref != binding.node_ref
            or attempt.attempt_id != binding.node_attempt_id
            or attempt.fence != binding.node_fence
        ):
            raise BrowserAuthorityError("browser request and exact Node attempt differ")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or capability_ref not in node.required_capabilities:
            raise BrowserAuthorityError("browser Capability is absent from exact Node")
        task = self.tasks.get_task(access, binding.task_ref)
        if task.canonical_digest != binding.task_digest or capability_ref not in task.required_capabilities:
            raise BrowserAuthorityError("browser Capability is absent from exact Task")
        if task.data_policy_ref != binding.data_policy_ref or task.egress_policy_ref != binding.egress_policy_ref:
            raise BrowserAuthorityError("browser policy binding differs from exact Task")
        levels = {"READ_ONLY": 0, "CANDIDATE_WRITE": 1, "PROJECT_WRITE": 2, "EXTERNAL_SIDE_EFFECT": 3}
        required = 3 if side_effect is BrowserSideEffect.EXTERNAL_SIDE_EFFECT else 0
        if levels[task.side_effect_authority] < required or levels[node.side_effect_requirement] < required:
            raise BrowserAuthorityError("browser action exceeds Task or Node side-effect authority")
        self._run_attempt(access, attempt)
        self._require_live_node(access, attempt)

    def _destination(self, access: ProjectAccess, binding: BrowserExecutionBinding, destination_ref: HttpDestinationRef) -> HttpDestination:
        try:
            destination = self.http.get_destination(access, destination_ref)
        except Exception as exc:
            raise BrowserAuthorityError("browser destination is not registered") from exc
        if destination.data_policy_ref != binding.data_policy_ref or destination.egress_policy_ref != binding.egress_policy_ref:
            raise BrowserAuthorityError("browser destination policy differs from exact Task")
        return destination

    def _require_spec_destinations(self, access: ProjectAccess, spec: BrowserSessionSpec) -> tuple[HttpDestination | None, tuple[HttpDestination, ...]]:
        destinations = tuple(self._destination(access, spec.binding, item) for item in spec.allowed_destination_refs)
        controller = None if spec.controller_destination_ref is None else self._destination(access, spec.binding, spec.controller_destination_ref)
        return controller, destinations

    def _implementation(self, access: ProjectAccess, capability_ref: CapabilityRef) -> CapabilityImplementation:
        name = capability_ref.capability_id
        implementation_ref = CapabilityImplementationRef(
            access.project_ref,
            f"cimpl_{hashlib.sha256(f'{self.implementation_ref}:{name}'.encode()).hexdigest()[:32]}",
        )
        try:
            return self.implementations.get(access, implementation_ref)
        except RoutingNotFoundError as exc:
            raise BrowserAuthorityError("browser implementation is not registered") from exc

    def _start_tool(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        capability_ref: CapabilityRef,
        identity_key: str,
        inputs: Sequence[ContentRef | ArtifactRef],
    ) -> ToolCall:
        implementation = self._implementation(access, capability_ref)
        key = hashlib.sha256(f"{attempt.record_sha256}\0{identity_key}".encode()).hexdigest()[:46]
        try:
            return self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=f"browser-start-{key}",
                capability_ref=capability_ref,
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id=f"tool://biella/{capability_ref.capability_id.replace('.', '/')}",
                implementation_id=implementation.implementation_ref.value,
                runtime_id=self.implementation_ref,
                input_refs=inputs,
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise BrowserAuthorityError("browser ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise BrowserConflictError("browser ToolCall identity conflicts") from exc

    def _publish_artifact(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        role: str,
        content_ref: ContentRef,
        source_artifact_refs: Sequence[ArtifactRef] = (),
        source_content_refs: Sequence[ContentRef] = (),
        semantic_label: str,
    ) -> Artifact:
        return self.artifacts.publish_from_run(
            access,
            producer_attempt=self._run_attempt(access, attempt),
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=role,
            content_ref=content_ref,
            source_refs=(),
            source_artifact_refs=source_artifact_refs,
            source_content_refs=source_content_refs,
            derivation_type="browser.automation",
            metadata={
                "media_type": content_ref.media_type,
                "schema_ref": f"schema://biella/{semantic_label}/1",
                "schema_version": "1.0.0",
                "semantic_label": semantic_label,
            },
        )

    @staticmethod
    def _session_ref_from_value(value: object, project_ref: ProjectRef) -> BrowserSessionRef:
        prefix = f"browser-session://{project_ref.value}/"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise BrowserScopeError("persisted browser session crossed Project scope")
        return BrowserSessionRef(project_ref, value.removeprefix(prefix))

    @staticmethod
    def _destination_ref_from_value(value: object, project_ref: ProjectRef) -> HttpDestinationRef:
        prefix = f"http-destination://{project_ref.value}/"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise BrowserScopeError("persisted browser destination crossed Project scope")
        return HttpDestinationRef(project_ref, value.removeprefix(prefix))

    @staticmethod
    def _artifact_ref_from_value(value: object, project_ref: ProjectRef) -> ArtifactRef:
        prefix = f"artifact://{project_ref.value}/"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise BrowserScopeError("persisted browser Artifact crossed Project scope")
        try:
            artifact_id, revision = value.removeprefix(prefix).rsplit("/", 1)
            return ArtifactRef(project_ref, artifact_id, int(revision))
        except (TypeError, ValueError) as exc:
            raise BrowserIntegrityError("persisted browser Artifact is malformed") from exc

    @staticmethod
    def _tool_ref_from_value(value: object, project_ref: ProjectRef) -> ToolCallRef:
        prefix = f"tool-call://{project_ref.value}/"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise BrowserScopeError("persisted browser ToolCall crossed Project scope")
        return ToolCallRef(project_ref, value.removeprefix(prefix))

    def _identity_from_payload(self, value: object, project_ref: ProjectRef) -> BrowserSessionIdentity:
        if not isinstance(value, dict):
            raise BrowserIntegrityError("persisted browser identity is malformed")
        try:
            return BrowserSessionIdentity(
                self._session_ref_from_value(value["session_ref"], project_ref),
                cast(str, value["adapter_ref"]),
                cast(str, value["implementation_ref"]),
                cast(str, value["browser_name"]),
                cast(str, value["browser_version"]),
                cast(str, value["runtime_version"]),
                cast(str, value["provider_session_id"]),
                tuple(cast(list[str], value["resource_refs"])),
                tuple(self._destination_ref_from_value(item, project_ref) for item in cast(list[object], value["allowed_destination_refs"])),
                cast(str, value["egress_enforcer_ref"]),
                cast(int, value["generation"]),
                cast(str, value["reality"]),
                cast(str, value["created_at"]),
            )
        except (KeyError, TypeError, ValueError, BrowserAdapterError) as exc:
            if isinstance(exc, (BrowserScopeError, BrowserIntegrityError)):
                raise
            raise BrowserIntegrityError("persisted browser identity is malformed") from exc

    def _page_from_payload(self, value: object, identity: BrowserSessionIdentity) -> BrowserPageRef | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise BrowserIntegrityError("persisted browser page is malformed")
        try:
            page_value = cast(str, value["page_ref"])
            prefix = f"browser-page://{identity.session_ref.project_ref.value}/{identity.session_ref.session_id}/{identity.generation}/"
            if not page_value.startswith(prefix):
                raise BrowserScopeError("persisted browser page crossed session generation")
            return BrowserPageRef(
                identity.session_ref,
                page_value.removeprefix(prefix),
                cast(int, value["generation"]),
                cast(str, value["current_url"]),
                cast(str, value["observed_at"]),
            )
        except (KeyError, TypeError, ValueError, BrowserAdapterError) as exc:
            if isinstance(exc, (BrowserScopeError, BrowserIntegrityError)):
                raise
            raise BrowserIntegrityError("persisted browser page is malformed") from exc

    def _state_from_payload(self, value: object, project_ref: ProjectRef) -> BrowserSessionState:
        if not isinstance(value, dict):
            raise BrowserIntegrityError("persisted browser session state is malformed")
        try:
            identity = self._identity_from_payload(value["identity"], project_ref)
            return BrowserSessionState(
                identity,
                BrowserSessionStatus(cast(str, value["status"])),
                self._page_from_payload(value["page_ref"], identity),
                self._tool_ref_from_value(value["tool_call_ref"], project_ref),
                self._artifact_ref_from_value(value["receipt_artifact_ref"], project_ref),
                cast(str | None, value["cause"]),
                cast(str, value["observed_at"]),
            )
        except (KeyError, TypeError, ValueError, BrowserAdapterError) as exc:
            if isinstance(exc, (BrowserScopeError, BrowserIntegrityError)):
                raise
            raise BrowserIntegrityError("persisted browser session state is malformed") from exc

    def inspect_session(self, access: ProjectAccess, session_ref: BrowserSessionRef) -> BrowserSessionState:
        self._authorize(access, session_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT s.state_json,s.record_sha256,h.state_sha256,
                          g.identity_json,g.record_sha256 AS identity_record_sha256
                   FROM browser_session_heads h
                   JOIN browser_session_states s ON s.project_id=h.project_id AND s.session_id=h.session_id AND s.generation=h.generation AND s.sequence=h.sequence
                   JOIN browser_session_generations g ON g.project_id=h.project_id AND g.session_id=h.session_id AND g.generation=h.generation
                   WHERE h.project_id=? AND h.session_id=?""",
                (access.project_ref.value, session_ref.session_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise BrowserNotFoundError("browser session is unavailable")
        try:
            payload = json.loads(cast(str, row["state_json"]))
        except json.JSONDecodeError as exc:
            raise BrowserIntegrityError("browser session state JSON is malformed") from exc
        state = self._state_from_payload(payload, access.project_ref)
        try:
            identity_payload = json.loads(cast(str, row["identity_json"]))
        except json.JSONDecodeError as exc:
            raise BrowserIntegrityError("browser session generation identity JSON is malformed") from exc
        persisted_identity = self._identity_from_payload(identity_payload, access.project_ref)
        if (
            state.identity.session_ref != session_ref
            or persisted_identity != state.identity
            or not hmac.compare_digest(persisted_identity.record_sha256, cast(str, row["identity_record_sha256"]))
            or not hmac.compare_digest(state.record_sha256, cast(str, row["record_sha256"]))
            or not hmac.compare_digest(state.record_sha256, cast(str, row["state_sha256"]))
        ):
            raise BrowserIntegrityError("browser session state evidence changed")
        receipt = self.artifacts.get_artifact(access, state.receipt_artifact_ref)
        if receipt.content_ref is None:
            raise BrowserIntegrityError("browser session receipt lacks content")
        try:
            self.object_store.verify(receipt.content_ref)
            receipt_payload = json.loads(self.object_store.read(receipt.content_ref))
        except (ObjectStorageError, json.JSONDecodeError) as exc:
            raise BrowserIntegrityError("browser session receipt content changed") from exc
        expected_receipt = {
            "cause": state.cause,
            "identity": state.identity.payload(),
            "observed_at": state.observed_at,
            "page_ref": None if state.page_ref is None else state.page_ref.payload(),
            "status": state.status.value,
            "tool_call_ref": state.tool_call_ref.value,
        }
        if receipt_payload != expected_receipt:
            raise BrowserIntegrityError("browser session state and receipt manifest differ")
        call = self.calls.get_tool_call(access, state.tool_call_ref)
        if (
            call.status != "SUCCEEDED"
            or call.capability_ref != CapabilityRef("browser.open", "1.0.0")
            or set(call.output_refs) != {state.receipt_artifact_ref, receipt.content_ref}
        ):
            raise BrowserIntegrityError("browser session state and ToolCall evidence differ")
        return state

    def _persist_state(self, access: ProjectAccess, state: BrowserSessionState, *, new_generation: bool) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            head = connection.execute(
                "SELECT generation,sequence FROM browser_session_heads WHERE project_id=? AND session_id=?",
                (access.project_ref.value, state.identity.session_ref.session_id),
            ).fetchone()
            if new_generation:
                sequence = 1
                if head is not None and cast(int, head["generation"]) >= state.identity.generation:
                    raise BrowserConflictError("browser session generation did not advance")
                connection.execute(
                    "INSERT INTO browser_session_generations VALUES (?,?,?,?,?)",
                    (
                        access.project_ref.value,
                        state.identity.session_ref.session_id,
                        state.identity.generation,
                        _json(state.identity.payload()),
                        state.identity.record_sha256,
                    ),
                )
            else:
                if head is None or cast(int, head["generation"]) != state.identity.generation:
                    raise BrowserAuthorityError("browser session generation is no longer current")
                sequence = cast(int, head["sequence"]) + 1
            connection.execute(
                "INSERT INTO browser_session_states VALUES (?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    state.identity.session_ref.session_id,
                    state.identity.generation,
                    sequence,
                    _json(state.payload()),
                    state.record_sha256,
                ),
            )
            if head is None:
                connection.execute(
                    "INSERT INTO browser_session_heads VALUES (?,?,?,?,?)",
                    (access.project_ref.value, state.identity.session_ref.session_id, state.identity.generation, sequence, state.record_sha256),
                )
            else:
                connection.execute(
                    "UPDATE browser_session_heads SET generation=?,sequence=?,state_sha256=? WHERE project_id=? AND session_id=?",
                    (state.identity.generation, sequence, state.record_sha256, access.project_ref.value, state.identity.session_ref.session_id),
                )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise BrowserConflictError("browser session state persistence conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _session_receipt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: BrowserSessionIdentity,
        page_ref: BrowserPageRef | None,
        status: BrowserSessionStatus,
        tool: ToolCall,
        cause: str | None,
    ) -> tuple[BrowserSessionState, ContentRef]:
        observed_at = _now()
        payload = {
            "cause": cause,
            "identity": identity.payload(),
            "observed_at": observed_at,
            "page_ref": None if page_ref is None else page_ref.payload(),
            "status": status.value,
            "tool_call_ref": tool.call_ref.value,
        }
        content_ref = self.object_store.put(_json(payload).encode(), media_type=_RECEIPT_MEDIA)
        receipt = self._publish_artifact(
            access,
            attempt,
            role="browser.session.receipt",
            content_ref=content_ref,
            source_content_refs=(),
            semantic_label="browser-session-receipt",
        )
        state = BrowserSessionState(identity, status, page_ref, tool.call_ref, receipt.artifact_ref, cause, observed_at)
        return state, content_ref

    def create_session(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        spec: BrowserSessionSpec,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> BrowserSessionState:
        if _KEY.fullmatch(idempotency_key) is None or not isinstance(secret_values, Mapping):
            raise BrowserContractError("browser session idempotency or secrets are malformed")
        self._require_binding(access, attempt, spec.binding, spec.capability_ref, BrowserSideEffect.READ_ONLY)
        controller, destinations = self._require_spec_destinations(access, spec)
        connection = self._connect()
        try:
            prior = connection.execute(
                "SELECT session_id,generation,spec_sha256 FROM browser_session_claims WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
        finally:
            connection.close()
        if prior is not None:
            if prior["session_id"] != spec.session_ref.session_id or not hmac.compare_digest(cast(str, prior["spec_sha256"]), spec.spec_sha256):
                raise BrowserConflictError("browser session idempotency conflicts")
            return self.inspect_session(access, spec.session_ref)
        generation = 1
        try:
            current = self.inspect_session(access, spec.session_ref)
        except BrowserNotFoundError:
            current = None
        if current is not None:
            if current.status is not BrowserSessionStatus.LOST:
                raise BrowserConflictError("browser session can only replace a lost generation")
            generation = current.identity.generation + 1
        tool = self._start_tool(access, attempt, spec.capability_ref, f"session-{spec.session_ref.session_id}-{generation}", ())
        if tool.status != "RUNNING":
            raise BrowserIntegrityError("terminal browser open ToolCall lacks a session claim")
        try:
            backend = self._create_backend_session(spec, controller, destinations, secret_values)
        except _BackendFailure as exc:
            failure_ref = self.object_store.put(
                _json({"failure": exc.failure.value, "reason": exc.reason, "session_ref": spec.session_ref.value}).encode(),
                media_type=_RECEIPT_MEDIA,
            )
            failure_artifact = self._publish_artifact(
                access,
                attempt,
                role="browser.session.failure",
                content_ref=failure_ref,
                semantic_label="browser-session-failure",
            )
            self.calls.finish_tool_call(
                access,
                attempt,
                tool.call_ref,
                idempotency_key=f"browser-session-failed-{spec.session_ref.session_id[:32]}",
                status="FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category=exc.failure.value,
                failure_reason=exc.reason,
                failure_evidence_refs=(failure_ref, failure_artifact.artifact_ref),
            )
            raise BrowserNotFoundError(f"browser session creation failed: {exc.failure.value}") from exc
        identity = BrowserSessionIdentity(
            spec.session_ref,
            self.adapter_ref,
            self.implementation_ref,
            backend.browser_name,
            backend.browser_version,
            backend.runtime_version,
            backend.provider_session_id,
            spec.resource_refs,
            spec.allowed_destination_refs,
            spec.egress_enforcer_ref,
            generation,
            self.reality,
        )
        page_id = f"bpage_{hashlib.sha256(f'{spec.session_ref.value}:{generation}'.encode()).hexdigest()[:32]}"
        page_ref = BrowserPageRef(spec.session_ref, page_id, generation, "about:blank")
        state, receipt_ref = self._session_receipt(
            access,
            attempt,
            identity,
            page_ref,
            BrowserSessionStatus.ACTIVE,
            tool,
            None,
        )
        terminal = self.calls.finish_tool_call(
            access,
            attempt,
            tool.call_ref,
            idempotency_key=f"browser-session-open-{spec.session_ref.session_id[:32]}-{generation}",
            status="SUCCEEDED",
            output_refs=(receipt_ref, state.receipt_artifact_ref),
            usage=None,
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        if terminal.call_ref != state.tool_call_ref:
            raise BrowserIntegrityError("browser session ToolCall identity changed")
        self._persist_state(access, state, new_generation=True)
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO browser_session_claims VALUES (?,?,?,?,?)",
                (access.project_ref.value, idempotency_key, spec.session_ref.session_id, generation, spec.spec_sha256),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise BrowserConflictError("browser session claim conflicts") from exc
        finally:
            connection.close()
        return state

    def record_session_loss(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: BrowserSessionIdentity,
        *,
        cause: str,
        idempotency_key: str,
    ) -> BrowserSessionState:
        if _KEY.fullmatch(idempotency_key) is None:
            raise BrowserContractError("browser loss idempotency key is malformed")
        _text(cause, "browser session loss cause", 2048)
        current = self.inspect_session(access, identity.session_ref)
        if current.identity != identity:
            raise BrowserAuthorityError("stale browser generation cannot record current loss")
        if current.status is BrowserSessionStatus.LOST:
            return current
        if current.status is not BrowserSessionStatus.ACTIVE:
            raise BrowserConflictError("closed browser session cannot become lost")
        self._require_binding(access, attempt, BrowserExecutionBinding(
            identity.session_ref.project_ref,
            attempt.task_ref,
            attempt.task_digest,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            self.tasks.get_task(access, attempt.task_ref).data_policy_ref,
            self.tasks.get_task(access, attempt.task_ref).egress_policy_ref,
        ), self.capability_ref(), BrowserSideEffect.READ_ONLY)
        tool = self._start_tool(access, attempt, self.capability_ref(), f"session-loss-{identity.session_ref.session_id}-{identity.generation}-{idempotency_key}", ())
        state, receipt_ref = self._session_receipt(access, attempt, identity, current.page_ref, BrowserSessionStatus.LOST, tool, cause)
        self.calls.finish_tool_call(
            access,
            attempt,
            tool.call_ref,
            idempotency_key=f"browser-session-loss-{hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]}",
            status="SUCCEEDED",
            output_refs=(receipt_ref, state.receipt_artifact_ref),
            usage=None,
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self._persist_state(access, state, new_generation=False)
        return state

    def close_session(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: BrowserSessionIdentity,
        *,
        idempotency_key: str,
    ) -> BrowserSessionState:
        if _KEY.fullmatch(idempotency_key) is None:
            raise BrowserContractError("browser close idempotency key is malformed")
        current = self.inspect_session(access, identity.session_ref)
        if current.identity != identity:
            raise BrowserAuthorityError("stale browser generation cannot close replacement session")
        if current.status is BrowserSessionStatus.CLOSED:
            return current
        if current.status is not BrowserSessionStatus.ACTIVE:
            raise BrowserAuthorityError("lost browser session cannot be closed as active")
        task = self.tasks.get_task(access, attempt.task_ref)
        binding = BrowserExecutionBinding(
            access.project_ref,
            attempt.task_ref,
            attempt.task_digest,
            attempt.run_ref,
            attempt.node_ref,
            attempt.attempt_id,
            attempt.fence,
            task.data_policy_ref,
            task.egress_policy_ref,
        )
        self._require_binding(access, attempt, binding, self.capability_ref(), BrowserSideEffect.READ_ONLY)
        tool = self._start_tool(access, attempt, self.capability_ref(), f"session-close-{identity.session_ref.session_id}-{identity.generation}", ())
        try:
            self._close_backend_session(identity)
        except _BackendFailure as exc:
            if exc.failure is not BrowserExecutionFailure.SESSION_LOST:
                raise BrowserNotFoundError(f"browser close failed: {exc.failure.value}") from exc
        state, receipt_ref = self._session_receipt(access, attempt, identity, current.page_ref, BrowserSessionStatus.CLOSED, tool, None)
        self.calls.finish_tool_call(
            access,
            attempt,
            tool.call_ref,
            idempotency_key=f"browser-session-close-{identity.session_ref.session_id[:32]}-{identity.generation}",
            status="SUCCEEDED",
            output_refs=(receipt_ref, state.receipt_artifact_ref),
            usage=None,
            cost=None,
            failure_category=None,
            failure_reason=None,
            failure_evidence_refs=(),
        )
        self._persist_state(access, state, new_generation=False)
        return state

    def _require_current_session(self, access: ProjectAccess, identity: BrowserSessionIdentity) -> BrowserSessionState:
        current = self.inspect_session(access, identity.session_ref)
        if current.identity.record_sha256 != identity.record_sha256 or current.identity.generation != identity.generation:
            raise BrowserAuthorityError("late or stale browser session generation was rejected")
        if current.status is not BrowserSessionStatus.ACTIVE:
            raise BrowserAuthorityError("browser session generation is not active")
        return current

    def _url_destination(self, access: ProjectAccess, binding: BrowserExecutionBinding, identity: BrowserSessionIdentity, url: str) -> HttpDestination:
        safe = _safe_url(url)
        if safe == "about:blank":
            raise BrowserAuthorityError("about:blank has no browser egress authority")
        parsed = urlsplit(safe)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or "/"
        for destination_ref in identity.allowed_destination_refs:
            destination = self._destination(access, binding, destination_ref)
            if destination.origin == origin and _path_allowed(path, destination.allowed_path_prefixes):
                return destination
            redirect_prefixes = destination.redirect_path_allowlist.get(origin)
            if redirect_prefixes is not None and _path_allowed(path, redirect_prefixes):
                return destination
        raise BrowserAuthorityError("browser URL is outside the exact destination allowlist")

    def _require_action(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction) -> BrowserSessionState:
        self._require_binding(access, attempt, action.binding, action.capability_ref, action.side_effect)
        current = self._require_current_session(access, action.session_identity)
        if action.destination_ref is not None:
            if action.destination_ref not in action.session_identity.allowed_destination_refs:
                raise BrowserAuthorityError("browser action destination is outside session authority")
            action_destination = self._destination(access, action.binding, action.destination_ref)
            if action.action_type in {BrowserActionType.NAVIGATE, BrowserActionType.DOWNLOAD}:
                assert action.target is not None
                if not _path_allowed(action.target, action_destination.allowed_path_prefixes):
                    raise BrowserAuthorityError("browser action path is outside exact destination authority")
        page_destination: HttpDestination | None = None
        if action.page_ref is not None and action.page_ref.current_url != "about:blank":
            page_destination = self._url_destination(access, action.binding, action.session_identity, action.page_ref.current_url)
        if action.action_type in {BrowserActionType.UPLOAD, BrowserActionType.SUBMIT}:
            if page_destination is None or action.destination_ref != page_destination.destination_ref:
                raise BrowserAuthorityError("browser mutation destination does not match the current authorized page origin")
        if action.precondition:
            supported = {"url", "generation"}
            if set(action.precondition).difference(supported):
                raise BrowserContractError("browser precondition contains unsupported keys")
            if "url" in action.precondition and action.page_ref is not None and action.precondition["url"] != action.page_ref.current_url:
                raise BrowserAuthorityError("browser URL precondition failed")
            if "generation" in action.precondition and action.precondition["generation"] != action.session_identity.generation:
                raise BrowserAuthorityError("browser generation precondition failed")
        if action.postcondition:
            supported = {"url", "generation"}
            if set(action.postcondition).difference(supported):
                raise BrowserContractError("browser postcondition contains unsupported keys")
            if "url" in action.postcondition:
                _safe_url(action.postcondition["url"])
            if "generation" in action.postcondition and (
                not isinstance(action.postcondition["generation"], int)
                or isinstance(action.postcondition["generation"], bool)
                or action.postcondition["generation"] < 1
            ):
                raise BrowserContractError("browser generation postcondition is malformed")
        return current

    def _require_backend_page(self, action: BrowserAction) -> None:
        raise BrowserContractError("browser backend page verification is unavailable")

    def _read_value(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        action: BrowserAction,
    ) -> tuple[_ResolvedBrowserValue | None, tuple[ContentRef, ...], tuple[ArtifactRef, ...]]:
        value_ref = action.value_ref
        if value_ref is None:
            return None, (), ()
        if isinstance(value_ref, BrowserFilesystemUploadSource):
            try:
                operation = self.filesystem.read(
                    access,
                    attempt,
                    root_ref=value_ref.root_ref,
                    path=value_ref.relative_path,
                    media_type=value_ref.media_type,
                    idempotency_key=f"browser-upload-{action.action_ref.action_id[:40]}",
                )
                self.object_store.verify(operation.output_ref)
                content = None if action.action_type is BrowserActionType.UPLOAD else self.object_store.read(operation.output_ref)
                return _ResolvedBrowserValue(operation.output_ref, content), (), (operation.artifact_ref,)
            except (FilesystemError, ObjectStorageError) as exc:
                raise BrowserAuthorityError("browser FilesystemRoot upload source was rejected") from exc
        if isinstance(value_ref, ContentRef):
            try:
                self.object_store.verify(value_ref)
                content = None if action.action_type is BrowserActionType.UPLOAD else self.object_store.read(value_ref)
                return _ResolvedBrowserValue(value_ref, content), (value_ref,), ()
            except ObjectStorageError as exc:
                raise BrowserIntegrityError("browser value ContentRef failed verification") from exc
        artifact = self.artifacts.get_artifact(access, value_ref)
        if artifact.content_ref is None:
            raise BrowserIntegrityError("browser value Artifact has no content")
        try:
            self.object_store.verify(artifact.content_ref)
            content = None if action.action_type is BrowserActionType.UPLOAD else self.object_store.read(artifact.content_ref)
            return _ResolvedBrowserValue(artifact.content_ref, content), (artifact.content_ref,), (artifact.artifact_ref,)
        except ObjectStorageError as exc:
            raise BrowserIntegrityError("browser value Artifact content failed verification") from exc

    def _claim_action(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, tool: ToolCall) -> bool:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM browser_action_claims WHERE project_id=? AND action_id=?",
                (access.project_ref.value, action.action_ref.action_id),
            ).fetchone()
            if prior is not None:
                if (
                    prior["session_id"] != action.session_identity.session_ref.session_id
                    or cast(int, prior["generation"]) != action.session_identity.generation
                    or prior["request_sha256"] != action.request_sha256
                    or prior["node_attempt_id"] != attempt.attempt_id
                    or cast(int, prior["node_fence"]) != attempt.fence
                    or prior["tool_call_id"] != tool.call_ref.call_id
                ):
                    raise BrowserConflictError("browser action identity conflicts")
                connection.commit()
                return False
            connection.execute(
                "INSERT INTO browser_action_claims VALUES (?,?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    action.action_ref.action_id,
                    action.session_identity.session_ref.session_id,
                    action.session_identity.generation,
                    action.request_sha256,
                    attempt.attempt_id,
                    attempt.fence,
                    tool.call_ref.call_id,
                ),
            )
            connection.commit()
            return True
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise BrowserConflictError("browser action claim conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _replay_action_if_exists(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        action: BrowserAction,
    ) -> BrowserActionResult | None:
        connection = self._connect()
        try:
            claim = connection.execute(
                "SELECT * FROM browser_action_claims WHERE project_id=? AND action_id=?",
                (access.project_ref.value, action.action_ref.action_id),
            ).fetchone()
        finally:
            connection.close()
        if claim is None:
            return None
        if (
            claim["session_id"] != action.session_identity.session_ref.session_id
            or cast(int, claim["generation"]) != action.session_identity.generation
            or claim["request_sha256"] != action.request_sha256
            or claim["node_attempt_id"] != attempt.attempt_id
            or cast(int, claim["node_fence"]) != attempt.fence
        ):
            raise BrowserConflictError("browser action identity conflicts")
        try:
            return self.get_result(access, action.action_ref)
        except BrowserNotFoundError as exc:
            raise BrowserConflictError("browser action is already claimed and incomplete") from exc

    def _cancelled(self, action_ref: BrowserActionRef) -> bool:
        connection = self._connect()
        try:
            return connection.execute(
                "SELECT 1 FROM browser_cancellations WHERE project_id=? AND action_id=? LIMIT 1",
                (action_ref.project_ref.value, action_ref.action_id),
            ).fetchone() is not None
        finally:
            connection.close()

    def _publish_action_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        action: BrowserAction,
        tool: ToolCall,
        backend: _BackendResult | None,
        failure: BrowserExecutionFailure | None,
        failure_reason: str | None,
        latency_ms: float,
        idempotency_key: str,
        source_contents: tuple[ContentRef, ...],
        source_artifacts: tuple[ArtifactRef, ...],
    ) -> BrowserActionResult:
        self._require_live_node(access, attempt)
        self._require_current_session(access, action.session_identity)
        output_ref: ContentRef | None = None
        output_artifact: Artifact | None = None
        page_ref = action.page_ref
        provider_trace_id: str | None = None
        provider_metadata: Mapping[str, object] = MappingProxyType({})
        if backend is not None:
            provider_trace_id = backend.provider_trace_id
            provider_metadata = backend.provider_metadata
            try:
                safe_url = _safe_url(backend.current_url)
                if safe_url != "about:blank":
                    self._url_destination(access, action.binding, action.session_identity, safe_url)
                page_id = action.page_ref.page_id if action.page_ref is not None else f"bpage_{uuid4().hex}"
                page_ref = BrowserPageRef(action.session_identity.session_ref, page_id, action.session_identity.generation, safe_url)
            except BrowserAdapterError:
                failure = BrowserExecutionFailure.EGRESS_DENIED
                failure_reason = "browser provider returned a URL outside exact destination authority"
                backend = None
        if failure is None and backend is not None and action.postcondition:
            assert page_ref is not None
            if (
                ("url" in action.postcondition and action.postcondition["url"] != page_ref.current_url)
                or (
                    "generation" in action.postcondition
                    and action.postcondition["generation"] != page_ref.generation
                )
            ):
                failure = BrowserExecutionFailure.POSTCONDITION_FAILED
                failure_reason = "browser provider result did not satisfy the exact postcondition"
                backend = None
        if failure is None and backend is not None:
            if len(backend.content) > action.maximum_output_bytes:
                failure = BrowserExecutionFailure.OUTPUT_LIMIT
                failure_reason = "browser provider output exceeded the exact bound"
            elif action.expected_output_sha256 is not None and hashlib.sha256(backend.content).hexdigest() != action.expected_output_sha256:
                failure = (
                    BrowserExecutionFailure.DOWNLOAD_INTEGRITY_FAILED
                    if action.action_type is BrowserActionType.DOWNLOAD
                    else BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED
                )
                failure_reason = "browser provider output digest differed from the exact expected digest"
        if failure is None and backend is not None:
            action_label = action.action_type.value.replace("_", "-")
            output_ref = self.object_store.put(backend.content, media_type=backend.media_type)
            output_artifact = self._publish_artifact(
                access,
                attempt,
                role=f"browser.{action_label}.output",
                content_ref=output_ref,
                source_artifact_refs=source_artifacts,
                source_content_refs=source_contents,
                semantic_label=f"browser-{action_label}-result",
            )
        completed_at = _now()
        receipt_basis = {
            "action_ref": action.action_ref.value,
            "action_type": action.action_type.value,
            "completed_at": completed_at,
            "failure": None if failure is None else failure.value,
            "failure_reason": failure_reason,
            "latency_ms": float(latency_ms),
            "output_artifact_ref": None if output_artifact is None else output_artifact.artifact_ref.value,
            "output_ref": _content_payload(output_ref),
            "page_ref": None if page_ref is None else page_ref.payload(),
            "provider_trace_id": provider_trace_id,
            "provider_metadata": dict(provider_metadata),
            "request_sha256": action.request_sha256,
            "session_identity": action.session_identity.payload(),
            "side_effect": action.side_effect.value,
            "tool_call_ref": tool.call_ref.value,
        }
        receipt_ref = self.object_store.put(_json(receipt_basis).encode(), media_type=_RECEIPT_MEDIA)
        receipt_artifact = self._publish_artifact(
            access,
            attempt,
            role=f"browser.{action.action_type.value.replace('_', '-')}.receipt",
            content_ref=receipt_ref,
            source_artifact_refs=tuple((*source_artifacts, *((output_artifact.artifact_ref,) if output_artifact is not None else ()))),
            source_content_refs=tuple((*source_contents, *((output_ref,) if output_ref is not None else ()))),
            semantic_label="browser-action-receipt",
        )
        finish_key = hashlib.sha256(f"{attempt.record_sha256}\0{idempotency_key}".encode()).hexdigest()[:44]
        try:
            terminal = self.calls.finish_tool_call(
                access,
                attempt,
                tool.call_ref,
                idempotency_key=f"browser-finish-{finish_key}",
                status="SUCCEEDED" if failure is None else ("TIMED_OUT" if failure is BrowserExecutionFailure.TIMEOUT else "CANCELLED" if failure is BrowserExecutionFailure.CANCELLED else "FAILED"),
                output_refs=(output_ref, output_artifact.artifact_ref, receipt_ref, receipt_artifact.artifact_ref) if output_ref is not None and output_artifact is not None else (),
                usage=None,
                cost=None,
                failure_category=None if failure is None else failure.value,
                failure_reason=None if failure is None else f"Browser action failed: {failure.value}",
                failure_evidence_refs=() if failure is None else (receipt_ref, receipt_artifact.artifact_ref),
            )
        except CallAuthorityError as exc:
            raise BrowserAuthorityError("late or stale browser result was rejected") from exc
        except CallConflictError as exc:
            raise BrowserConflictError("browser completion conflicts") from exc
        result = BrowserActionResult(
            action.action_ref,
            action.action_type,
            action.session_identity,
            page_ref,
            output_ref,
            None if output_artifact is None else output_artifact.artifact_ref,
            receipt_artifact.artifact_ref,
            terminal.call_ref,
            failure,
            failure_reason,
            action.side_effect,
            provider_trace_id,
            provider_metadata,
            latency_ms,
            completed_at,
        )
        result_payload = {"evidence": result.payload(), "request_sha256": action.request_sha256}
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO browser_action_results VALUES (?,?,?,?)",
                (access.project_ref.value, action.action_ref.action_id, _json(result_payload), _digest(result_payload)),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise BrowserConflictError("browser result persistence conflicts") from exc
        finally:
            connection.close()
        return result

    def _execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        action: BrowserAction,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> BrowserActionResult:
        if _KEY.fullmatch(idempotency_key) is None or not isinstance(secret_values, Mapping):
            raise BrowserContractError("browser action idempotency or secrets are malformed")
        self._require_action(access, attempt, action)
        replay = self._replay_action_if_exists(access, attempt, action)
        if replay is not None:
            return replay
        if action.page_ref is not None:
            self._require_backend_page(action)
        value, source_contents, source_artifacts = self._read_value(access, attempt, action)
        inputs: tuple[ContentRef | ArtifactRef, ...] = tuple((*source_contents, *source_artifacts))
        tool = self._start_tool(access, attempt, action.capability_ref, f"action-{action.action_ref.action_id}", inputs)
        first = self._claim_action(access, attempt, action, tool)
        if not first:
            if tool.status == "RUNNING":
                raise BrowserConflictError("browser action is already claimed and incomplete")
            return self.get_result(access, action.action_ref)
        secret_value: str | None = None
        if action.secret_ref is not None:
            candidate = secret_values.get(action.secret_ref)
            if not isinstance(candidate, str) or not candidate:
                raise BrowserAuthorityError("browser secret value is unavailable")
            secret_value = candidate
            self._runtime_secrets.setdefault(action.session_identity.provider_session_id, set()).add(candidate.encode())
        active = _ActiveAction(threading.Event())
        self._active[action.action_ref.value] = active
        if self._cancelled(action.action_ref):
            active.cancellation.set()
        started = time.monotonic()
        backend: _BackendResult | None = None
        failure: BrowserExecutionFailure | None = None
        failure_reason: str | None = None
        try:
            try:
                backend = self._invoke_backend(action, value, secret_value, active)
                if active.cancellation.is_set():
                    raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
                if any(secret in backend.content for secret in self._runtime_secrets.get(action.session_identity.provider_session_id, set())):
                    raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "secret appeared in browser output")
            except _BackendFailure as exc:
                failure = exc.failure
                failure_reason = exc.reason
            return self._publish_action_result(
                access,
                attempt,
                action,
                tool,
                backend,
                failure,
                failure_reason,
                (time.monotonic() - started) * 1000,
                idempotency_key,
                source_contents,
                source_artifacts,
            )
        finally:
            self._active.pop(action.action_ref.value, None)

    def navigate(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.NAVIGATE:
            raise BrowserContractError("navigate requires a NAVIGATE action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def inspect(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.INSPECT:
            raise BrowserContractError("inspect requires an INSPECT action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def perform_action(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type not in {BrowserActionType.CLICK, BrowserActionType.TYPE, BrowserActionType.SELECT, BrowserActionType.EVALUATE, BrowserActionType.SUBMIT}:
            raise BrowserContractError("perform_action requires click/type/select/evaluate/submit")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def extract(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.EXTRACT:
            raise BrowserContractError("extract requires an EXTRACT action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def capture_screenshot(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.SCREENSHOT:
            raise BrowserContractError("capture_screenshot requires a SCREENSHOT action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def upload(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.UPLOAD:
            raise BrowserContractError("upload requires an UPLOAD action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def download(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.DOWNLOAD:
            raise BrowserContractError("download requires a DOWNLOAD action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    def wait_for_condition(self, access: ProjectAccess, attempt: NodeExecutionAttempt, action: BrowserAction, *, secret_values: Mapping[str, str], idempotency_key: str) -> BrowserActionResult:
        if action.action_type is not BrowserActionType.WAIT_FOR_CONDITION:
            raise BrowserContractError("wait_for_condition requires a WAIT action")
        return self._execute(access, attempt, action, secret_values=secret_values, idempotency_key=idempotency_key)

    @staticmethod
    def _content_ref_from_payload(value: object) -> ContentRef | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise BrowserIntegrityError("persisted browser ContentRef is malformed")
        try:
            return ContentRef(
                cast(str, value["algorithm"]),
                cast(str, value["digest"]),
                cast(int, value["size_bytes"]),
                cast(str, value["media_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BrowserIntegrityError("persisted browser ContentRef is malformed") from exc

    @staticmethod
    def _action_ref_from_value(value: object, project_ref: ProjectRef) -> BrowserActionRef:
        prefix = f"browser-action://{project_ref.value}/"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise BrowserScopeError("persisted browser action crossed Project scope")
        return BrowserActionRef(project_ref, value.removeprefix(prefix))

    def _result_from_payload(self, value: object, project_ref: ProjectRef) -> tuple[BrowserActionResult, str]:
        if not isinstance(value, dict) or not isinstance(value.get("evidence"), dict):
            raise BrowserIntegrityError("persisted browser result is malformed")
        evidence = cast(dict[str, object], value["evidence"])
        try:
            identity = self._identity_from_payload(evidence["session_identity"], project_ref)
            output_artifact = None if evidence["output_artifact_ref"] is None else self._artifact_ref_from_value(evidence["output_artifact_ref"], project_ref)
            result = BrowserActionResult(
                self._action_ref_from_value(evidence["action_ref"], project_ref),
                BrowserActionType(cast(str, evidence["action_type"])),
                identity,
                self._page_from_payload(evidence["page_ref"], identity),
                self._content_ref_from_payload(evidence["output_ref"]),
                output_artifact,
                self._artifact_ref_from_value(evidence["receipt_artifact_ref"], project_ref),
                self._tool_ref_from_value(evidence["tool_call_ref"], project_ref),
                None if evidence["failure"] is None else BrowserExecutionFailure(cast(str, evidence["failure"])),
                cast(str | None, evidence["failure_reason"]),
                BrowserSideEffect(cast(str, evidence["side_effect"])),
                cast(str | None, evidence["provider_trace_id"]),
                cast(dict[str, object], evidence["provider_metadata"]),
                cast(float, evidence["latency_ms"]),
                cast(str, evidence["completed_at"]),
            )
            request_sha256 = cast(str, value["request_sha256"])
            if _SHA256.fullmatch(request_sha256) is None:
                raise BrowserIntegrityError("persisted browser request digest is malformed")
            return result, request_sha256
        except (KeyError, TypeError, ValueError, BrowserAdapterError) as exc:
            if isinstance(exc, (BrowserScopeError, BrowserIntegrityError)):
                raise
            raise BrowserIntegrityError("persisted browser result is malformed") from exc

    def get_result(self, access: ProjectAccess, action_ref: BrowserActionRef) -> BrowserActionResult:
        self._authorize(access, action_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT result_json,record_sha256 FROM browser_action_results WHERE project_id=? AND action_id=?",
                (access.project_ref.value, action_ref.action_id),
            ).fetchone()
            claim = connection.execute(
                """SELECT c.*,g.identity_json,g.record_sha256 AS identity_record_sha256
                   FROM browser_action_claims c
                   JOIN browser_session_generations g
                     ON g.project_id=c.project_id AND g.session_id=c.session_id AND g.generation=c.generation
                   WHERE c.project_id=? AND c.action_id=?""",
                (access.project_ref.value, action_ref.action_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None or claim is None:
            raise BrowserNotFoundError("browser action result is unavailable")
        try:
            payload = json.loads(cast(str, row["result_json"]))
        except json.JSONDecodeError as exc:
            raise BrowserIntegrityError("browser result JSON is malformed") from exc
        result, request_sha256 = self._result_from_payload(payload, access.project_ref)
        try:
            persisted_identity_payload = json.loads(cast(str, claim["identity_json"]))
        except json.JSONDecodeError as exc:
            raise BrowserIntegrityError("browser action generation identity is malformed") from exc
        persisted_identity = self._identity_from_payload(persisted_identity_payload, access.project_ref)
        if (
            result.action_ref != action_ref
            or request_sha256 != claim["request_sha256"]
            or claim["session_id"] != result.session_identity.session_ref.session_id
            or cast(int, claim["generation"]) != result.session_identity.generation
            or claim["tool_call_id"] != result.tool_call_ref.call_id
            or persisted_identity != result.session_identity
            or not hmac.compare_digest(persisted_identity.record_sha256, cast(str, claim["identity_record_sha256"]))
            or not hmac.compare_digest(_digest(payload), cast(str, row["record_sha256"]))
        ):
            raise BrowserIntegrityError("browser action result evidence changed")
        call = self.calls.get_tool_call(access, result.tool_call_ref)
        expected_status = "SUCCEEDED" if result.succeeded else "TIMED_OUT" if result.failure is BrowserExecutionFailure.TIMEOUT else "CANCELLED" if result.failure is BrowserExecutionFailure.CANCELLED else "FAILED"
        if (
            call.status != expected_status
            or call.node_attempt_id != claim["node_attempt_id"]
            or call.node_fence != cast(int, claim["node_fence"])
            or call.capability_ref != CapabilityRef(result.action_type.capability_name, "1.0.0")
        ):
            raise BrowserIntegrityError("browser result and ToolCall state differ")
        receipt = self.artifacts.get_artifact(access, result.receipt_artifact_ref)
        if receipt.content_ref is None:
            raise BrowserIntegrityError("browser action receipt lacks content")
        try:
            self.object_store.verify(receipt.content_ref)
            receipt_payload = json.loads(self.object_store.read(receipt.content_ref))
        except (ObjectStorageError, json.JSONDecodeError) as exc:
            raise BrowserIntegrityError("browser action receipt content changed") from exc
        expected_receipt = {
            "action_ref": result.action_ref.value,
            "action_type": result.action_type.value,
            "completed_at": result.completed_at,
            "failure": None if result.failure is None else result.failure.value,
            "failure_reason": result.failure_reason,
            "latency_ms": float(result.latency_ms),
            "output_artifact_ref": _artifact_ref_payload(result.output_artifact_ref),
            "output_ref": _content_payload(result.output_ref),
            "page_ref": None if result.page_ref is None else result.page_ref.payload(),
            "provider_trace_id": result.provider_trace_id,
            "provider_metadata": dict(result.provider_metadata),
            "request_sha256": request_sha256,
            "session_identity": result.session_identity.payload(),
            "side_effect": result.side_effect.value,
            "tool_call_ref": result.tool_call_ref.value,
        }
        if receipt_payload != expected_receipt:
            raise BrowserIntegrityError("browser result and receipt manifest differ")
        receipt_outputs = {receipt.content_ref, result.receipt_artifact_ref}
        if result.succeeded:
            assert result.output_ref is not None and result.output_artifact_ref is not None
            try:
                self.object_store.verify(result.output_ref)
            except ObjectStorageError as exc:
                raise BrowserIntegrityError("browser output ContentRef changed") from exc
            output_artifact = self.artifacts.get_artifact(access, result.output_artifact_ref)
            if output_artifact.content_ref != result.output_ref:
                raise BrowserIntegrityError("browser output Artifact and ContentRef differ")
            expected_outputs = {*receipt_outputs, result.output_ref, result.output_artifact_ref}
            if set(call.output_refs) != expected_outputs or call.failure_evidence_refs:
                raise BrowserIntegrityError("browser success evidence differs from ToolCall")
        elif set(call.failure_evidence_refs) != receipt_outputs or call.output_refs:
            raise BrowserIntegrityError("browser failure evidence differs from ToolCall")
        return result

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        action_ref: BrowserActionRef,
        *,
        idempotency_key: str,
    ) -> BrowserCancellationReceipt:
        if _KEY.fullmatch(idempotency_key) is None:
            raise BrowserContractError("browser cancellation idempotency key is malformed")
        self._authorize(access, action_ref.project_ref)
        self._run_attempt(access, attempt)
        receipt = BrowserCancellationReceipt(action_ref, True, idempotency_key, _now())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim = connection.execute(
                "SELECT node_attempt_id,node_fence FROM browser_action_claims WHERE project_id=? AND action_id=?",
                (access.project_ref.value, action_ref.action_id),
            ).fetchone()
            if claim is None:
                raise BrowserNotFoundError("browser action claim is unavailable for cancellation")
            if claim["node_attempt_id"] != attempt.attempt_id or cast(int, claim["node_fence"]) != attempt.fence:
                raise BrowserAuthorityError("browser cancellation crossed Node attempt ownership")
            prior = connection.execute(
                "SELECT receipt_json,record_sha256 FROM browser_cancellations WHERE project_id=? AND action_id=? AND idempotency_key=?",
                (access.project_ref.value, action_ref.action_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                payload = json.loads(cast(str, prior["receipt_json"]))
                value = BrowserCancellationReceipt(action_ref, cast(bool, payload["accepted"]), cast(str, payload["idempotency_key"]), cast(str, payload["observed_at"]))
                if not hmac.compare_digest(value.record_sha256, cast(str, prior["record_sha256"])):
                    raise BrowserIntegrityError("browser cancellation evidence changed")
                connection.commit()
                return value
            connection.execute(
                "INSERT INTO browser_cancellations VALUES (?,?,?,?,?)",
                (access.project_ref.value, action_ref.action_id, idempotency_key, _json(receipt.payload()), receipt.record_sha256),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        active = self._active.get(action_ref.value)
        if active is not None:
            active.cancellation.set()
            self._cancel_backend_action(action_ref, active)
        return receipt

    def _create_backend_session(
        self,
        spec: BrowserSessionSpec,
        controller: HttpDestination | None,
        destinations: tuple[HttpDestination, ...],
        secret_values: Mapping[str, str],
    ) -> _BackendSession:
        raise BrowserContractError("browser backend session implementation is unavailable")

    def _invoke_backend(
        self,
        action: BrowserAction,
        value: _ResolvedBrowserValue | None,
        secret_value: str | None,
        active: _ActiveAction,
    ) -> _BackendResult:
        raise BrowserContractError("browser backend action implementation is unavailable")

    def _close_backend_session(self, identity: BrowserSessionIdentity) -> None:
        return

    def _cancel_backend_action(self, action_ref: BrowserActionRef, active: _ActiveAction) -> None:
        return


class ReferenceBrowserAdapter(_BaseBrowserAdapter):
    """Deterministic REFERENCE browser used for contract and failure qualification."""

    _SCREENSHOT = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        http_adapter: HttpAdapter,
        *,
        downloads: Mapping[str, bytes] = MappingProxyType({}),
        interrupted_downloads: Sequence[str] = (),
        latency_seconds: float = 0.0,
    ) -> None:
        if not isinstance(downloads, Mapping) or len(downloads) > 256:
            raise BrowserContractError("reference browser downloads are malformed or unbounded")
        copied: dict[str, bytes] = {}
        for path, payload in downloads.items():
            copied[_safe_path(path, "reference download path")] = bytes(payload)
        self.downloads = MappingProxyType(copied)
        self.interrupted_downloads = frozenset(_safe_path(item, "interrupted download path") for item in interrupted_downloads)
        if isinstance(latency_seconds, bool) or not isinstance(latency_seconds, (int, float)) or latency_seconds < 0:
            raise BrowserContractError("reference browser latency is malformed")
        self.latency_seconds = float(latency_seconds)
        self._sessions: dict[str, dict[str, object]] = {}
        self._session_lock = threading.Condition()
        super().__init__(
            database_path,
            object_store,
            http_adapter,
            adapter_ref="adapter://biella/browser/reference-v1",
            implementation_ref="runtime://biella/browser/reference-v1",
            reality="REFERENCE",
        )

    def _create_backend_session(
        self,
        spec: BrowserSessionSpec,
        controller: HttpDestination | None,
        destinations: tuple[HttpDestination, ...],
        secret_values: Mapping[str, str],
    ) -> _BackendSession:
        if secret_values:
            raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "reference browser forbids controller credentials")
        runtime_session_id = f"reference-{uuid4().hex}"
        with self._session_lock:
            self._sessions[runtime_session_id] = {
                "url": "about:blank",
                "destinations": {item.destination_ref.value: item for item in destinations},
                "values": {},
                "events": {"ready"},
            }
        return _BackendSession(runtime_session_id, spec.browser_name, "reference-1.0.0", "reference-runtime-1.0.0", runtime_session_id)

    def _wait(self, action: BrowserAction, active: _ActiveAction) -> None:
        deadline = time.monotonic() + float(action.timeout_seconds)
        remaining = self.latency_seconds
        while remaining > 0:
            if active.cancellation.is_set():
                raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
            if time.monotonic() >= deadline:
                raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "timeout")
            interval = min(0.01, remaining, max(0.0, deadline - time.monotonic()))
            if interval <= 0:
                raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "timeout")
            time.sleep(interval)
            remaining -= interval

    def _invoke_backend(
        self,
        action: BrowserAction,
        value: _ResolvedBrowserValue | None,
        secret_value: str | None,
        active: _ActiveAction,
    ) -> _BackendResult:
        self._wait(action, active)
        runtime_session_id = action.session_identity.provider_session_id
        with self._session_lock:
            session = self._sessions.get(runtime_session_id)
            if session is None:
                raise _BackendFailure(BrowserExecutionFailure.SESSION_LOST, "reference session is lost")
            url = cast(str, session["url"])
            destinations = cast(dict[str, HttpDestination], session["destinations"])
            values = cast(dict[str, str], session["values"])
            if action.action_type is BrowserActionType.NAVIGATE:
                assert action.destination_ref is not None and action.target is not None
                destination = destinations.get(action.destination_ref.value)
                if destination is None:
                    raise _BackendFailure(BrowserExecutionFailure.EGRESS_DENIED, "reference destination is denied")
                url = f"{destination.origin}{action.target}"
                session["url"] = url
                content = _json({"navigated": True, "url": url}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.INSPECT:
                content = _json({"title": "Reference Browser", "url": url, "dom": {"bounded": True}}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.EXTRACT:
                if action.target == "#missing":
                    raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "reference target is absent")
                content = _json({"selector": action.target, "text": "reference extraction", "url": url}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.CLICK:
                if action.target == "#missing":
                    raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "reference target is absent")
                content = _json({"clicked": action.target, "external_side_effect": True}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.TYPE:
                if action.target == "#missing":
                    raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "reference target is absent")
                typed = secret_value if secret_value is not None else None if value is None or value.content is None else value.content.decode()
                if typed is None:
                    raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "reference type value is absent")
                values[cast(str, action.target)] = typed
                content = _json({"typed": True, "selector": action.target, "characters": len(typed)}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.SELECT:
                if action.target == "#missing" or value is None or value.content is None:
                    raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "reference select target/value is absent")
                values[cast(str, action.target)] = value.content.decode()
                content = _json({"selected": True, "selector": action.target}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.UPLOAD:
                if action.target == "#missing" or value is None:
                    raise _BackendFailure(BrowserExecutionFailure.UPLOAD_DENIED, "reference upload target/value is absent")
                content = _json({"uploaded": True, "sha256": value.content_ref.digest, "size_bytes": value.content_ref.size_bytes}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.DOWNLOAD:
                assert action.target is not None
                if action.target in self.interrupted_downloads:
                    raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTERRUPTED, "reference download was interrupted")
                payload = self.downloads.get(action.target)
                if payload is None:
                    raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "reference download is absent")
                content = payload
                media = "application/octet-stream"
            elif action.action_type is BrowserActionType.SCREENSHOT:
                content = self._SCREENSHOT
                media = _PNG_MEDIA
            elif action.action_type is BrowserActionType.EVALUATE:
                if value is None or value.content is None:
                    raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "bounded evaluation request is absent")
                try:
                    request = json.loads(value.content)
                except json.JSONDecodeError as exc:
                    raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "bounded evaluation request is malformed") from exc
                if request == {"operation": "title"}:
                    content = _json({"value": "Reference Browser"}).encode()
                elif isinstance(request, dict) and request.get("operation") == "text" and isinstance(request.get("selector"), str):
                    content = _json({"value": "reference extraction"}).encode()
                else:
                    raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "arbitrary browser evaluation is denied")
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.WAIT_FOR_CONDITION:
                condition = _action_wait_condition(action)
                events = cast(set[str], session["events"])
                met = False
                if condition.condition_type is BrowserWaitConditionType.SELECTOR:
                    met = condition.selector != "#missing"
                elif condition.condition_type is BrowserWaitConditionType.URL:
                    met = condition.url == url
                elif condition.condition_type is BrowserWaitConditionType.DOM_PROPERTY:
                    met = condition.property_name == "value" and values.get(cast(str, condition.selector)) == condition.expected
                elif condition.condition_type is BrowserWaitConditionType.NETWORK_IDLE:
                    met = True
                elif condition.condition_type is BrowserWaitConditionType.EVENT:
                    met = condition.event_name in events
                if not met:
                    raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "reference condition timed out")
                content = _json({"condition": condition.condition_type.value, "condition_met": True}).encode()
                media = _RESULT_MEDIA
            elif action.action_type is BrowserActionType.SUBMIT:
                if action.target == "#missing":
                    raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "reference submit target is absent")
                content = _json({"submitted": True, "external_side_effect": True}).encode()
                media = _RESULT_MEDIA
            else:
                raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "reference browser action is unsupported")
        metadata: Mapping[str, object] = MappingProxyType({})
        if action.action_type is BrowserActionType.SCREENSHOT:
            metadata = MappingProxyType(
                {"viewport": {"device_scale_factor": 1.0, "height": 1, "width": 1}}
            )
        return _BackendResult(content, media, url, f"reference-action-{action.action_ref.action_id}", metadata)

    def _require_backend_page(self, action: BrowserAction) -> None:
        assert action.page_ref is not None
        with self._session_lock:
            session = self._sessions.get(action.session_identity.provider_session_id)
            if session is None:
                raise BrowserNotFoundError("reference browser session is unavailable")
            current_url = cast(str, session["url"])
        if current_url != action.page_ref.current_url:
            raise BrowserAuthorityError("browser page reference is stale relative to the provider session")

    def _close_backend_session(self, identity: BrowserSessionIdentity) -> None:
        with self._session_lock:
            if self._sessions.pop(identity.provider_session_id, None) is None:
                raise _BackendFailure(BrowserExecutionFailure.SESSION_LOST, "reference session is already lost")
        self._runtime_secrets.pop(identity.provider_session_id, None)

    def crash_session(self, identity: BrowserSessionIdentity) -> None:
        """Simulate provider loss without rewriting durable Biella evidence."""
        with self._session_lock:
            self._sessions.pop(identity.provider_session_id, None)
        self._runtime_secrets.pop(identity.provider_session_id, None)


class WebDriverBrowserAdapter(_BaseBrowserAdapter):
    """REAL W3C WebDriver implementation with no Selenium SDK types in contracts."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        http_adapter: HttpAdapter,
    ) -> None:
        self._controllers: dict[str, tuple[HttpDestination, str | None, str | None]] = {}
        self._destinations: dict[str, dict[str, HttpDestination]] = {}
        self._controller_lock = threading.Condition()
        super().__init__(
            database_path,
            object_store,
            http_adapter,
            adapter_ref="adapter://biella/browser/w3c-webdriver-v1",
            implementation_ref="runtime://biella/browser/w3c-webdriver-v1",
            reality="REAL",
        )

    @staticmethod
    def _connection(destination: HttpDestination, timeout: float) -> http.client.HTTPConnection:
        parsed = urlsplit(destination.origin)
        host = cast(str, parsed.hostname)
        if parsed.scheme == "https":
            if destination.tls_policy is not HttpTlsPolicy.REQUIRE_VERIFIED_TLS:
                raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "WebDriver TLS policy is not verified")
            return http.client.HTTPSConnection(host, parsed.port or 443, timeout=timeout, context=ssl.create_default_context())
        if destination.tls_policy is not HttpTlsPolicy.ALLOW_PLAINTEXT:
            raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "WebDriver plaintext policy is not explicit")
        return http.client.HTTPConnection(host, parsed.port or 80, timeout=timeout)

    @staticmethod
    def _controller_path_allowed(destination: HttpDestination, path: str) -> bool:
        return _path_allowed(path, destination.allowed_path_prefixes)

    @staticmethod
    def _response_value(raw: bytes, status: int) -> object:
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver response is not JSON") from exc
        if not isinstance(envelope, dict) or "value" not in envelope:
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver response envelope is malformed")
        value = envelope["value"]
        if status >= 400 or (isinstance(value, dict) and isinstance(value.get("error"), str)):
            error = value.get("error") if isinstance(value, dict) else None
            if error in {"no such element", "stale element reference"}:
                failure = BrowserExecutionFailure.TARGET_NOT_FOUND
            elif error in {"invalid session id", "session not created"}:
                failure = BrowserExecutionFailure.SESSION_LOST
            elif error in {"script timeout", "timeout"}:
                failure = BrowserExecutionFailure.TIMEOUT
            else:
                failure = BrowserExecutionFailure.PROVIDER_ERROR
            raise _BackendFailure(failure, f"WebDriver error: {error or status}")
        return value

    def _command(
        self,
        destination: HttpDestination,
        method: str,
        path: str,
        payload: object | None,
        timeout: float,
        auth_header: str | None,
        auth_value: str | None,
    ) -> object:
        if not self._controller_path_allowed(destination, path):
            raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "WebDriver command path is denied")
        body = None if payload is None else _json(payload).encode()
        headers = {"accept": "application/json"}
        if body is not None:
            headers["content-type"] = "application/json"
            headers["content-length"] = str(len(body))
        if auth_header is not None and auth_value is not None:
            headers[auth_header] = auth_value
        connection = self._connection(destination, timeout)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            raw = response.read(64 * 1024 * 1024 + 1)
            if len(raw) > 64 * 1024 * 1024:
                raise _BackendFailure(BrowserExecutionFailure.OUTPUT_LIMIT, "WebDriver response exceeded bound")
        except TimeoutError as exc:
            raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "WebDriver command timed out") from exc
        except (OSError, http.client.HTTPException) as exc:
            raise _BackendFailure(BrowserExecutionFailure.SESSION_LOST, "WebDriver transport is unavailable") from exc
        finally:
            connection.close()
        return self._response_value(raw, status)

    def _upload_content(
        self,
        action: BrowserAction,
        content_ref: ContentRef,
        filename: str,
        active: _ActiveAction,
    ) -> str:
        controller, auth_header, auth_value, _ = self._controller(action.session_identity)
        path = f"/session/{action.session_identity.provider_session_id}/se/file"
        if not self._controller_path_allowed(controller, path):
            raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "WebDriver upload path is denied")
        deadline = time.monotonic() + float(action.timeout_seconds)
        with tempfile.TemporaryFile() as archive_file:
            transferred = 0
            try:
                with self.object_store.open(content_ref) as source:
                    with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                        with archive.open(filename, "w", force_zip64=True) as member:
                            while True:
                                if active.cancellation.is_set():
                                    raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
                                if time.monotonic() >= deadline:
                                    raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "WebDriver upload staging timed out")
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                transferred += len(chunk)
                                member.write(chunk)
            except ObjectStorageError as exc:
                raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "WebDriver upload source changed") from exc
            if transferred != content_ref.size_bytes:
                raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "WebDriver upload source size changed")
            archive_file.flush()
            archive_file.seek(0, 2)
            archive_size = archive_file.tell()
            prefix = b'{"file":"'
            suffix = b'"}'
            encoded_size = 4 * ((archive_size + 2) // 3)
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "content-length": str(len(prefix) + encoded_size + len(suffix)),
            }
            if auth_header is not None and auth_value is not None:
                headers[auth_header] = auth_value

            def body_chunks() -> Iterator[bytes]:
                yield prefix
                archive_file.seek(0)
                while True:
                    if active.cancellation.is_set():
                        raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
                    if time.monotonic() >= deadline:
                        raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "WebDriver upload transfer timed out")
                    chunk = archive_file.read(3 * 256 * 1024)
                    if not chunk:
                        break
                    yield base64.b64encode(chunk)
                yield suffix

            connection = self._connection(controller, max(0.1, deadline - time.monotonic()))
            try:
                connection.putrequest("POST", path)
                for name, header_value in headers.items():
                    connection.putheader(name, header_value)
                connection.endheaders()
                for chunk in body_chunks():
                    connection.send(chunk)
                response = connection.getresponse()
                status = response.status
                raw = response.read(64 * 1024 * 1024 + 1)
                if len(raw) > 64 * 1024 * 1024:
                    raise _BackendFailure(BrowserExecutionFailure.OUTPUT_LIMIT, "WebDriver response exceeded bound")
            except _BackendFailure:
                raise
            except TimeoutError as exc:
                raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "WebDriver upload timed out") from exc
            except (OSError, http.client.HTTPException) as exc:
                raise _BackendFailure(BrowserExecutionFailure.SESSION_LOST, "WebDriver upload transport is unavailable") from exc
            finally:
                connection.close()
        remote_path = self._response_value(raw, status)
        if not isinstance(remote_path, str) or not remote_path:
            raise _BackendFailure(BrowserExecutionFailure.UPLOAD_DENIED, "WebDriver upload staging failed")
        return remote_path

    def _create_backend_session(
        self,
        spec: BrowserSessionSpec,
        controller: HttpDestination | None,
        destinations: tuple[HttpDestination, ...],
        secret_values: Mapping[str, str],
    ) -> _BackendSession:
        if spec.controller_destination_ref is None:
            raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "REAL browser requires a controller destination")
        if controller is None:
            raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "REAL browser controller destination is unavailable")
        if any(item.allowed_path_prefixes != ("/",) for item in destinations):
            raise _BackendFailure(
                BrowserExecutionFailure.AUTHORITY_DENIED,
                "REAL browser host containment requires full-origin destination paths",
            )
        auth_value: str | None = None
        if controller.auth_profile_ref is not None:
            candidate = secret_values.get(controller.auth_profile_ref)
            if not isinstance(candidate, str) or not candidate:
                raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "WebDriver controller credential is absent")
            auth_value = candidate
        hosts = sorted({cast(str, urlsplit(item.origin).hostname) for item in destinations})
        host_rules = "MAP * ~NOTFOUND" + "".join(f", EXCLUDE {host}" for host in hosts)
        capabilities = {
            "capabilities": {
                "alwaysMatch": {
                    "browserName": spec.browser_name,
                    "goog:chromeOptions": {
                        "args": [
                            "--headless=new",
                            "--no-sandbox",
                            "--window-size=1280,720",
                            "--disable-background-networking",
                            "--disable-sync",
                            "--no-first-run",
                            f"--host-resolver-rules={host_rules}",
                        ]
                    },
                    "se:downloadsEnabled": True,
                }
            }
        }
        value = self._command(
            controller,
            "POST",
            "/session",
            capabilities,
            spec.timeout_seconds,
            controller.auth_header_name,
            auth_value,
        )
        if not isinstance(value, dict):
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver session response is malformed")
        provider_session_id = value.get("sessionId")
        reported = value.get("capabilities")
        if not isinstance(provider_session_id, str) or not provider_session_id or not isinstance(reported, dict):
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver session identity is absent")
        browser_name = reported.get("browserName")
        browser_version = reported.get("browserVersion")
        chrome = reported.get("chrome")
        runtime_version = chrome.get("chromedriverVersion") if isinstance(chrome, dict) else None
        if not all(isinstance(item, str) and item for item in (browser_name, browser_version, runtime_version)):
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver runtime version identity is absent")
        with self._controller_lock:
            self._controllers[provider_session_id] = (controller, controller.auth_header_name, auth_value)
            self._destinations[provider_session_id] = {item.destination_ref.value: item for item in destinations}
        return _BackendSession(provider_session_id, cast(str, browser_name), cast(str, browser_version), cast(str, runtime_version), provider_session_id)

    def _controller(self, identity: BrowserSessionIdentity) -> tuple[HttpDestination, str | None, str | None, dict[str, HttpDestination]]:
        with self._controller_lock:
            controller = self._controllers.get(identity.provider_session_id)
            destinations = self._destinations.get(identity.provider_session_id)
        if controller is None or destinations is None:
            raise _BackendFailure(BrowserExecutionFailure.SESSION_LOST, "WebDriver runtime session is not attached to this adapter generation")
        return (*controller, destinations)

    def _wd(
        self,
        identity: BrowserSessionIdentity,
        method: str,
        suffix: str,
        payload: object | None,
        timeout: float,
    ) -> object:
        controller, auth_header, auth_value, _ = self._controller(identity)
        return self._command(
            controller,
            method,
            f"/session/{identity.provider_session_id}{suffix}",
            payload,
            timeout,
            auth_header,
            auth_value,
        )

    def _find(self, action: BrowserAction, selector: str) -> str:
        value = self._wd(
            action.session_identity,
            "POST",
            "/element",
            {"using": "css selector", "value": selector},
            action.timeout_seconds,
        )
        if not isinstance(value, dict) or not isinstance(value.get(_ELEMENT_KEY), str):
            raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "WebDriver target is absent")
        return cast(str, value[_ELEMENT_KEY])

    def _current_url(self, action: BrowserAction) -> str:
        value = self._wd(action.session_identity, "GET", "/url", None, action.timeout_seconds)
        if not isinstance(value, str):
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver current URL is malformed")
        try:
            return _safe_url(value)
        except BrowserAdapterError as exc:
            raise _BackendFailure(BrowserExecutionFailure.EGRESS_DENIED, "WebDriver current URL is unsafe") from exc

    def _require_backend_page(self, action: BrowserAction) -> None:
        assert action.page_ref is not None
        try:
            if action.page_ref.current_url == "about:blank":
                initial = self._wd(action.session_identity, "GET", "/url", None, action.timeout_seconds)
                if initial in {"about:blank", "data:,"}:
                    current_url = "about:blank"
                else:
                    current_url = _safe_url(initial)
            else:
                current_url = self._current_url(action)
        except _BackendFailure as exc:
            if exc.failure is BrowserExecutionFailure.SESSION_LOST:
                raise BrowserNotFoundError("WebDriver session is unavailable") from exc
            raise BrowserAuthorityError("WebDriver page authority could not be verified") from exc
        except BrowserAdapterError as exc:
            raise BrowserAuthorityError("WebDriver page authority could not be verified") from exc
        if current_url != action.page_ref.current_url:
            raise BrowserAuthorityError("browser page reference is stale relative to the provider session")

    @staticmethod
    def _json_output(value: object) -> bytes:
        return _json(value).encode()

    @staticmethod
    def _unzip_download(encoded: str, expected_name: str, maximum_bytes: int) -> bytes:
        try:
            raw = base64.b64decode(encoded, validate=True)
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                names = archive.namelist()
                if names != [expected_name]:
                    raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTEGRITY_FAILED, "managed download archive identity differs")
                info = archive.getinfo(expected_name)
                if info.is_dir() or info.file_size > maximum_bytes or info.compress_size > maximum_bytes:
                    raise _BackendFailure(BrowserExecutionFailure.OUTPUT_LIMIT, "managed download exceeds bound")
                if posixpath.basename(info.filename) != info.filename or _SAFE_FILENAME.fullmatch(info.filename) is None:
                    raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTEGRITY_FAILED, "managed download filename is unsafe")
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTERRUPTED, "managed download is incomplete")
                return payload
        except (ValueError, zipfile.BadZipFile, KeyError) as exc:
            raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTEGRITY_FAILED, "managed download archive is malformed") from exc

    def _invoke_backend(
        self,
        action: BrowserAction,
        value: _ResolvedBrowserValue | None,
        secret_value: str | None,
        active: _ActiveAction,
    ) -> _BackendResult:
        if active.cancellation.is_set():
            raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
        provider_trace = action.session_identity.provider_session_id
        _, _, _, destinations = self._controller(action.session_identity)
        current_url = "about:blank" if action.page_ref is None else action.page_ref.current_url
        result: bytes
        media_type = _RESULT_MEDIA
        provider_metadata: Mapping[str, object] = MappingProxyType({})
        if action.action_type is BrowserActionType.NAVIGATE:
            assert action.destination_ref is not None and action.target is not None
            destination = destinations.get(action.destination_ref.value)
            if destination is None:
                raise _BackendFailure(BrowserExecutionFailure.EGRESS_DENIED, "WebDriver navigation destination is denied")
            target_url = f"{destination.origin}{action.target}"
            self._wd(action.session_identity, "POST", "/url", {"url": target_url}, action.timeout_seconds)
            current_url = self._current_url(action)
            result = self._json_output({"navigated": True, "url": current_url})
        elif action.action_type is BrowserActionType.INSPECT:
            limit = min(action.maximum_output_bytes // 2, 2 * 1024 * 1024)
            value_result = self._wd(
                action.session_identity,
                "POST",
                "/execute/sync",
                {
                    "script": "return {title: document.title, url: location.origin + location.pathname, html: document.documentElement.outerHTML.slice(0, arguments[0])};",
                    "args": [limit],
                },
                action.timeout_seconds,
            )
            result = self._json_output(value_result)
            current_url = self._current_url(action)
        elif action.action_type is BrowserActionType.EXTRACT:
            assert action.target is not None
            value_result = self._wd(
                action.session_identity,
                "POST",
                "/execute/sync",
                {
                    "script": "const e=document.querySelector(arguments[0]); if(!e){return null;} return {selector:arguments[0], text:(e.textContent||'').slice(0,arguments[1])};",
                    "args": [action.target, min(action.maximum_output_bytes // 2, 4 * 1024 * 1024)],
                },
                action.timeout_seconds,
            )
            if value_result is None:
                raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "WebDriver extract target is absent")
            result = self._json_output(value_result)
        elif action.action_type is BrowserActionType.CLICK:
            assert action.target is not None
            element = self._find(action, action.target)
            self._wd(action.session_identity, "POST", f"/element/{element}/click", {}, action.timeout_seconds)
            current_url = self._current_url(action)
            result = self._json_output({"clicked": action.target, "external_side_effect": True})
        elif action.action_type is BrowserActionType.TYPE:
            assert action.target is not None
            text = secret_value if secret_value is not None else None if value is None or value.content is None else value.content.decode()
            if text is None:
                raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "WebDriver type value is absent")
            element = self._find(action, action.target)
            self._wd(action.session_identity, "POST", f"/element/{element}/clear", {}, action.timeout_seconds)
            self._wd(action.session_identity, "POST", f"/element/{element}/value", {"text": text}, action.timeout_seconds)
            result = self._json_output({"typed": True, "selector": action.target, "characters": len(text)})
        elif action.action_type is BrowserActionType.SELECT:
            assert action.target is not None
            if value is None or value.content is None:
                raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "WebDriver select value is absent")
            selection = value.content.decode()
            selected = self._wd(
                action.session_identity,
                "POST",
                "/execute/sync",
                {
                    "script": "const e=document.querySelector(arguments[0]); if(!e){return false;} e.value=arguments[1]; e.dispatchEvent(new Event('change',{bubbles:true})); return e.value===arguments[1];",
                    "args": [action.target, selection],
                },
                action.timeout_seconds,
            )
            if selected is not True:
                raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "WebDriver select target/value is absent")
            result = self._json_output({"selected": True, "selector": action.target})
        elif action.action_type is BrowserActionType.UPLOAD:
            assert action.target is not None and value is not None
            filename = action.expected_filename or "upload.bin"
            remote_path = self._upload_content(action, value.content_ref, filename, active)
            element = self._find(action, action.target)
            self._wd(action.session_identity, "POST", f"/element/{element}/value", {"text": remote_path}, action.timeout_seconds)
            result = self._json_output({"uploaded": True, "sha256": value.content_ref.digest, "size_bytes": value.content_ref.size_bytes})
        elif action.action_type is BrowserActionType.DOWNLOAD:
            assert action.destination_ref is not None and action.target is not None and action.expected_filename is not None
            destination = destinations.get(action.destination_ref.value)
            if destination is None:
                raise _BackendFailure(BrowserExecutionFailure.EGRESS_DENIED, "WebDriver download destination is denied")
            self._wd(action.session_identity, "POST", "/url", {"url": f"{destination.origin}{action.target}"}, action.timeout_seconds)
            deadline = time.monotonic() + float(action.timeout_seconds)
            names: list[str] = []
            while time.monotonic() < deadline:
                if active.cancellation.is_set():
                    raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
                listing = self._wd(action.session_identity, "GET", "/se/files", None, max(0.1, deadline - time.monotonic()))
                raw_names = listing.get("names") if isinstance(listing, dict) else None
                if isinstance(raw_names, list) and all(isinstance(item, str) for item in raw_names):
                    names = cast(list[str], raw_names)
                if action.expected_filename in names:
                    break
                time.sleep(0.05)
            if action.expected_filename not in names:
                raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTERRUPTED, "managed download did not complete before timeout")
            downloaded = self._wd(
                action.session_identity,
                "POST",
                "/se/files",
                {"name": action.expected_filename},
                max(0.1, deadline - time.monotonic()),
            )
            encoded = downloaded.get("contents") if isinstance(downloaded, dict) else None
            if not isinstance(encoded, str):
                raise _BackendFailure(BrowserExecutionFailure.DOWNLOAD_INTEGRITY_FAILED, "managed download payload is absent")
            result = self._unzip_download(encoded, action.expected_filename, action.maximum_output_bytes)
            self._wd(action.session_identity, "DELETE", "/se/files", None, max(0.1, deadline - time.monotonic()))
            media_type = "application/octet-stream"
            current_url = self._current_url(action)
        elif action.action_type is BrowserActionType.SCREENSHOT:
            rectangle = self._wd(action.session_identity, "GET", "/window/rect", None, action.timeout_seconds)
            if not isinstance(rectangle, dict):
                raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver viewport is absent")
            width = rectangle.get("width")
            height = rectangle.get("height")
            if (
                not isinstance(width, int)
                or isinstance(width, bool)
                or width < 1
                or not isinstance(height, int)
                or isinstance(height, bool)
                or height < 1
            ):
                raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver viewport is malformed")
            encoded = self._wd(action.session_identity, "GET", "/screenshot", None, action.timeout_seconds)
            if not isinstance(encoded, str):
                raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver screenshot is absent")
            try:
                result = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver screenshot is malformed") from exc
            media_type = _PNG_MEDIA
            provider_metadata = MappingProxyType(
                {"viewport": {"device_scale_factor": 1.0, "height": height, "width": width}}
            )
        elif action.action_type is BrowserActionType.EVALUATE:
            if value is None or value.content is None:
                raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "bounded evaluation request is absent")
            try:
                request = json.loads(value.content)
            except json.JSONDecodeError as exc:
                raise _BackendFailure(BrowserExecutionFailure.CONTENT_INTEGRITY_FAILED, "bounded evaluation request is malformed") from exc
            if request == {"operation": "title"}:
                evaluated = self._wd(action.session_identity, "GET", "/title", None, action.timeout_seconds)
            elif isinstance(request, dict) and request.get("operation") == "text" and isinstance(request.get("selector"), str):
                evaluated = self._wd(
                    action.session_identity,
                    "POST",
                    "/execute/sync",
                    {"script": "const e=document.querySelector(arguments[0]); return e ? (e.textContent||'').slice(0,arguments[1]) : null;", "args": [request["selector"], action.maximum_output_bytes // 2]},
                    action.timeout_seconds,
                )
            else:
                raise _BackendFailure(BrowserExecutionFailure.AUTHORITY_DENIED, "arbitrary browser JavaScript is denied")
            result = self._json_output({"value": evaluated})
        elif action.action_type is BrowserActionType.WAIT_FOR_CONDITION:
            condition = _action_wait_condition(action)
            deadline = time.monotonic() + float(action.timeout_seconds)
            found = False
            event_initialized = False
            last_resource_count: int | None = None
            idle_since = time.monotonic()
            while time.monotonic() < deadline:
                if active.cancellation.is_set():
                    raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
                try:
                    if condition.condition_type is BrowserWaitConditionType.SELECTOR:
                        assert condition.selector is not None
                        self._find(action, condition.selector)
                        found = True
                    elif condition.condition_type is BrowserWaitConditionType.URL:
                        found = self._current_url(action) == condition.url
                    elif condition.condition_type is BrowserWaitConditionType.DOM_PROPERTY:
                        observed = self._wd(
                            action.session_identity,
                            "POST",
                            "/execute/sync",
                            {
                                "script": "const e=document.querySelector(arguments[0]); return e ? e[arguments[1]] : null;",
                                "args": [condition.selector, condition.property_name],
                            },
                            max(0.1, deadline - time.monotonic()),
                        )
                        found = observed == condition.expected
                    elif condition.condition_type is BrowserWaitConditionType.NETWORK_IDLE:
                        state = self._wd(
                            action.session_identity,
                            "POST",
                            "/execute/sync",
                            {
                                "script": "return {ready:document.readyState==='complete',resources:performance.getEntriesByType('resource').length};",
                                "args": [],
                            },
                            max(0.1, deadline - time.monotonic()),
                        )
                        ready = state.get("ready") if isinstance(state, dict) else None
                        resources = state.get("resources") if isinstance(state, dict) else None
                        if ready is True and isinstance(resources, int) and not isinstance(resources, bool):
                            if resources != last_resource_count:
                                last_resource_count = resources
                                idle_since = time.monotonic()
                            found = (time.monotonic() - idle_since) * 1000 >= cast(int, condition.idle_ms)
                    elif condition.condition_type is BrowserWaitConditionType.EVENT:
                        if not event_initialized:
                            self._wd(
                                action.session_identity,
                                "POST",
                                "/execute/sync",
                                {
                                    "script": "window.__biellaObservedEvents=window.__biellaObservedEvents||{}; const n=arguments[0]; if(!window.__biellaObservedEvents[n]){window.addEventListener(n,()=>{window.__biellaObservedEvents[n]=true;},{once:true});} return true;",
                                    "args": [condition.event_name],
                                },
                                max(0.1, deadline - time.monotonic()),
                            )
                            event_initialized = True
                        found = self._wd(
                            action.session_identity,
                            "POST",
                            "/execute/sync",
                            {
                                "script": "return window.__biellaObservedEvents?.[arguments[0]]===true;",
                                "args": [condition.event_name],
                            },
                            max(0.1, deadline - time.monotonic()),
                        ) is True
                    if found:
                        break
                except _BackendFailure as exc:
                    if condition.condition_type is not BrowserWaitConditionType.SELECTOR or exc.failure is not BrowserExecutionFailure.TARGET_NOT_FOUND:
                        raise
                time.sleep(0.05)
            if not found:
                raise _BackendFailure(BrowserExecutionFailure.TIMEOUT, "browser condition timed out")
            current_url = self._current_url(action)
            result = self._json_output({"condition": condition.condition_type.value, "condition_met": True})
        elif action.action_type is BrowserActionType.SUBMIT:
            assert action.target is not None
            submitted = self._wd(
                action.session_identity,
                "POST",
                "/execute/sync",
                {
                    "script": "const e=document.querySelector(arguments[0]); if(!e){return false;} const f=e.form||e; if(typeof f.requestSubmit!=='function'){return false;} f.requestSubmit(); return true;",
                    "args": [action.target],
                },
                action.timeout_seconds,
            )
            if submitted is not True:
                raise _BackendFailure(BrowserExecutionFailure.TARGET_NOT_FOUND, "WebDriver submit target is absent")
            current_url = self._current_url(action)
            result = self._json_output({"submitted": True, "external_side_effect": True})
        else:
            raise _BackendFailure(BrowserExecutionFailure.PROVIDER_ERROR, "WebDriver action is unsupported")
        if active.cancellation.is_set():
            raise _BackendFailure(BrowserExecutionFailure.CANCELLED, "cancelled")
        return _BackendResult(result, media_type, current_url, provider_trace, provider_metadata)

    def _close_backend_session(self, identity: BrowserSessionIdentity) -> None:
        try:
            self._wd(identity, "DELETE", "", None, 30.0)
        finally:
            with self._controller_lock:
                self._controllers.pop(identity.provider_session_id, None)
                self._destinations.pop(identity.provider_session_id, None)
            self._runtime_secrets.pop(identity.provider_session_id, None)
