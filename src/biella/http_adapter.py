"""Project-scoped provider-neutral HTTP/API execution contracts and adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import posixpath
import re
import socket
import sqlite3
import ssl
import tempfile
import threading
import time
from types import MappingProxyType
from typing import BinaryIO, Protocol, cast, runtime_checkable
from urllib.parse import quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .call_ledger import (
    CallAuthorityError,
    CallConflictError,
    CallLedgerService,
    ToolCall,
    ToolCallRef,
)
from .capability import Capability, CapabilityRef, CapabilityRegistry
from .execution import NodeExecutionAttempt
from .graph import GraphService, NodeRef
from .object_store import (
    ObjectStorageBackend,
    ObjectStorageError,
    ObjectStorageIntegrityError,
)
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
from .run import ExecutionAttempt, RunRef, RunService
from .task import TaskRef, TaskRevisionService


_DESTINATION_ID = re.compile(r"hdst_[0-9a-f]{32}")
_EXECUTION_ID = re.compile(r"hexec_[0-9a-f]{32}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_REF = re.compile(r"[a-z][a-z0-9+.-]{1,63}://[^\s\x00-\x1f]{1,1000}")
_SECRET_REF = re.compile(r"secret://[^\s\x00-\x1f]{1,1000}")
_HEADER_NAME = re.compile(r"[a-z0-9!#$%&'*+.^_`|~-]{1,128}")
_METHOD = re.compile(r"[A-Z][A-Z0-9_-]{0,31}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SENSITIVE_NAME = re.compile(
    r"(?:authorization|cookie|password|secret|token|credential|api.?key|private.?key|signature)",
    re.IGNORECASE,
)
_OPERATIONS = ("execute", "cancel", "describe")
_REQUEST_MEDIA_TYPE = "application/vnd.biella.http-execution-request+json"
_RECEIPT_MEDIA_TYPE = "application/vnd.biella.http-execution-receipt+json"
_SAFE_RESPONSE_HEADERS = frozenset(
    {"cache-control", "content-encoding", "content-language", "content-length", "content-type", "etag", "last-modified"}
)
_FORBIDDEN_REQUEST_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
_AUTH_HEADER_NAMES = frozenset({"authorization", "cookie", "proxy-authorization", "x-api-key"})


class HttpAdapterError(Exception):
    """Base class for HTTP adapter failures."""


class HttpContractError(HttpAdapterError, ValueError):
    """An HTTP destination or request is malformed."""


class HttpScopeError(HttpAdapterError):
    """An HTTP request crossed Project scope."""


class HttpAuthorityError(HttpAdapterError):
    """Task, Node, policy, or credential authority is absent."""


class HttpConflictError(HttpAdapterError):
    """An HTTP idempotency or execution identity conflicts."""


class HttpNotFoundError(HttpAdapterError):
    """Required destination or evidence is unavailable."""


class HttpIntegrityError(HttpAdapterError):
    """Durable HTTP evidence failed verification."""


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise HttpContractError("HTTP payload is not canonical JSON") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _text(value: object, name: str, maximum: int = 64 * 1024) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode()) > maximum
        or any(ord(character) < 32 and character not in "\t" for character in value)
    ):
        raise HttpContractError(f"{name} is malformed or unbounded")
    return value


def _timestamp(value: object, name: str) -> str:
    text = _text(value, name, 128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HttpContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HttpContractError(f"{name} must be timezone-aware")
    return text


def _content_payload(content_ref: ContentRef | None) -> dict[str, object] | None:
    if content_ref is None:
        return None
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _canonical_origin(value: object) -> str:
    text = _text(value, "HTTP origin", 2048)
    parsed = urlsplit(text)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise HttpContractError("HTTP origin must be an exact http(s) origin without credentials or path")
    try:
        port = parsed.port
    except ValueError as exc:
        raise HttpContractError("HTTP origin port is malformed") from exc
    host = parsed.hostname.lower()
    if not host or len(host) > 253 or any(ord(character) > 127 for character in host):
        raise HttpContractError("HTTP origin host is malformed")
    default = 443 if parsed.scheme == "https" else 80
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != default:
        authority = f"{authority}:{port}"
    canonical = f"{parsed.scheme}://{authority}"
    if text.rstrip("/") != canonical:
        raise HttpContractError("HTTP origin is not canonical")
    return canonical


def _canonical_path(value: object, name: str, *, allow_root: bool = True) -> str:
    text = _text(value, name, 8192)
    if not text.startswith("/") or "?" in text or "#" in text or "\\" in text:
        raise HttpContractError(f"{name} must be a canonical absolute URL path")
    try:
        decoded = unquote(text, errors="strict")
    except UnicodeError as exc:
        raise HttpContractError(f"{name} percent encoding is malformed") from exc
    if any(part in {".", ".."} for part in decoded.split("/")):
        raise HttpContractError(f"{name} contains a traversal segment")
    normalized = posixpath.normpath(decoded)
    if decoded.endswith("/") and normalized != "/":
        normalized += "/"
    canonical = quote(normalized, safe="/:@-._~!$&'()*+,;=")
    if canonical != text or (not allow_root and canonical == "/"):
        raise HttpContractError(f"{name} is not canonical")
    return canonical


def _path_allowed(path: str, prefixes: Sequence[str]) -> bool:
    decoded = unquote(path)
    return any(
        decoded == unquote(prefix).rstrip("/")
        or decoded.startswith(unquote(prefix).rstrip("/") + "/")
        or prefix == "/"
        for prefix in prefixes
    )


def _header_mapping(value: Mapping[str, str], *, secret: bool) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > 256:
        raise HttpContractError("HTTP header mapping is malformed or unbounded")
    result: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str):
            raise HttpContractError("HTTP header name is malformed")
        name = raw_name.lower()
        if _HEADER_NAME.fullmatch(name) is None or name in _FORBIDDEN_REQUEST_HEADERS:
            raise HttpContractError("HTTP header name is forbidden or malformed")
        if secret:
            if name not in _AUTH_HEADER_NAMES and _SENSITIVE_NAME.search(name) is None:
                raise HttpContractError("secret header ref requires an explicitly sensitive header name")
            if not isinstance(raw_value, str) or _SECRET_REF.fullmatch(raw_value) is None:
                raise HttpContractError("HTTP secret header ref is malformed")
        else:
            if _SENSITIVE_NAME.search(name) is not None:
                raise HttpContractError("sensitive HTTP header requires a secret ref")
            _text(raw_value, "HTTP header value", 8192)
            if "\r" in raw_value or "\n" in raw_value:
                raise HttpContractError("HTTP header value contains a line break")
        if name in result:
            raise HttpContractError("HTTP header names are duplicated case-insensitively")
        result[name] = raw_value
    return MappingProxyType(dict(sorted(result.items())))


def _response_header_mapping(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or len(value) > len(_SAFE_RESPONSE_HEADERS):
        raise HttpContractError("HTTP response header mapping is malformed or unbounded")
    result: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str):
            raise HttpContractError("HTTP response header name is malformed")
        name = raw_name.lower()
        if name not in _SAFE_RESPONSE_HEADERS or _HEADER_NAME.fullmatch(name) is None:
            raise HttpContractError("HTTP result persisted a non-safe response header")
        _text(raw_value, "HTTP response header value", 8192)
        if "\r" in raw_value or "\n" in raw_value:
            raise HttpContractError("HTTP response header value contains a line break")
        result[name] = raw_value
    return MappingProxyType(dict(sorted(result.items())))


class HttpRedirectPolicy(str, Enum):
    NONE = "NONE"
    SAME_ORIGIN = "SAME_ORIGIN"
    ALLOWLIST = "ALLOWLIST"


class HttpTlsPolicy(str, Enum):
    REQUIRE_VERIFIED_TLS = "REQUIRE_VERIFIED_TLS"
    ALLOW_PLAINTEXT = "ALLOW_PLAINTEXT"


class HttpExecutionFailure(str, Enum):
    EGRESS_DENIED = "EGRESS_DENIED"
    AUTH_FAILED = "AUTH_FAILED"
    DNS_CONNECT_FAILED = "DNS_CONNECT_FAILED"
    TLS_FAILED = "TLS_FAILED"
    TIMEOUT = "TIMEOUT"
    REDIRECT_DENIED = "REDIRECT_DENIED"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    HTTP_ERROR = "HTTP_ERROR"
    CANCELLED = "CANCELLED"
    CONTENT_INTEGRITY_FAILED = "CONTENT_INTEGRITY_FAILED"


@dataclass(frozen=True, order=True)
class HttpDestinationRef:
    project_ref: ProjectRef
    destination_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.destination_id, str):
            raise HttpContractError("HTTP destination identity is malformed")
        if _DESTINATION_ID.fullmatch(self.destination_id) is None:
            raise HttpContractError("HTTP destination identity is malformed")

    @property
    def value(self) -> str:
        return f"http-destination://{self.project_ref.value}/{self.destination_id}"


@dataclass(frozen=True, order=True)
class HttpExecutionRef:
    project_ref: ProjectRef
    execution_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.execution_id, str):
            raise HttpContractError("HTTP execution identity is malformed")
        if _EXECUTION_ID.fullmatch(self.execution_id) is None:
            raise HttpContractError("HTTP execution identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> HttpExecutionRef:
        return cls(project_ref, f"hexec_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"http-execution://{self.project_ref.value}/{self.execution_id}"


@dataclass(frozen=True)
class HttpDestination:
    destination_ref: HttpDestinationRef
    origin: str
    allowed_path_prefixes: tuple[str, ...]
    auth_profile_ref: str | None
    auth_header_name: str | None
    data_policy_ref: str
    egress_policy_ref: str
    tls_policy: HttpTlsPolicy
    redirect_path_allowlist: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    created_at: str | None = None
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.destination_ref, HttpDestinationRef):
            raise HttpContractError("HTTP destination requires an exact ref")
        object.__setattr__(self, "origin", _canonical_origin(self.origin))
        if not isinstance(self.allowed_path_prefixes, tuple) or not 1 <= len(self.allowed_path_prefixes) <= 256:
            raise HttpContractError("HTTP destination path allowlist is malformed or empty")
        prefixes = tuple(sorted({_canonical_path(item, "HTTP allowed path prefix") for item in self.allowed_path_prefixes}))
        object.__setattr__(self, "allowed_path_prefixes", prefixes)
        if self.auth_profile_ref is None:
            if self.auth_header_name is not None:
                raise HttpContractError("HTTP auth header requires an auth profile ref")
        else:
            if _SECRET_REF.fullmatch(self.auth_profile_ref) is None:
                raise HttpContractError("HTTP auth profile ref is malformed")
            if not isinstance(self.auth_header_name, str) or _HEADER_NAME.fullmatch(self.auth_header_name.lower()) is None:
                raise HttpContractError("HTTP auth header name is malformed")
            auth_name = self.auth_header_name.lower()
            if auth_name not in _AUTH_HEADER_NAMES and _SENSITIVE_NAME.search(auth_name) is None:
                raise HttpContractError("HTTP auth profile must target a sensitive header")
            object.__setattr__(self, "auth_header_name", auth_name)
        for value, name in ((self.data_policy_ref, "data policy ref"), (self.egress_policy_ref, "egress policy ref")):
            if not isinstance(value, str) or _REF.fullmatch(value) is None:
                raise HttpContractError(f"HTTP destination {name} is malformed")
        if not isinstance(self.tls_policy, HttpTlsPolicy):
            raise HttpContractError("HTTP TLS policy is malformed")
        if self.tls_policy is HttpTlsPolicy.REQUIRE_VERIFIED_TLS and not self.origin.startswith("https://"):
            raise HttpContractError("verified TLS policy requires an https origin")
        if self.origin.startswith("https://") and self.tls_policy is HttpTlsPolicy.ALLOW_PLAINTEXT:
            raise HttpContractError("https origin must retain verified TLS policy")
        if not isinstance(self.redirect_path_allowlist, Mapping) or len(self.redirect_path_allowlist) > 64:
            raise HttpContractError("HTTP redirect allowlist is malformed or unbounded")
        redirects: dict[str, tuple[str, ...]] = {}
        for raw_origin, raw_prefixes in self.redirect_path_allowlist.items():
            origin = _canonical_origin(raw_origin)
            if not isinstance(raw_prefixes, tuple) or not raw_prefixes:
                raise HttpContractError("HTTP redirect path allowlist is malformed")
            if self.origin.startswith("https://") and origin.startswith("http://"):
                raise HttpContractError("HTTP redirect allowlist cannot downgrade verified TLS")
            redirects[origin] = tuple(sorted({_canonical_path(item, "HTTP redirect path prefix") for item in raw_prefixes}))
        object.__setattr__(self, "redirect_path_allowlist", MappingProxyType(dict(sorted(redirects.items()))))
        if self.created_at is not None:
            _timestamp(self.created_at, "HTTP destination created_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @classmethod
    def create(
        cls,
        project_ref: ProjectRef,
        *,
        origin: str,
        allowed_path_prefixes: tuple[str, ...],
        auth_profile_ref: str | None,
        auth_header_name: str | None,
        data_policy_ref: str,
        egress_policy_ref: str,
        tls_policy: HttpTlsPolicy,
        redirect_path_allowlist: Mapping[str, tuple[str, ...]] = MappingProxyType({}),
    ) -> HttpDestination:
        return cls(
            HttpDestinationRef(project_ref, f"hdst_{uuid4().hex}"),
            origin,
            allowed_path_prefixes,
            auth_profile_ref,
            auth_header_name,
            data_policy_ref,
            egress_policy_ref,
            tls_policy,
            redirect_path_allowlist,
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.destination_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "allowed_path_prefixes": list(self.allowed_path_prefixes),
            "auth_header_name": self.auth_header_name,
            "auth_profile_ref": self.auth_profile_ref,
            "created_at": self.created_at,
            "data_policy_ref": self.data_policy_ref,
            "destination_ref": self.destination_ref.value,
            "egress_policy_ref": self.egress_policy_ref,
            "origin": self.origin,
            "redirect_path_allowlist": {key: list(value) for key, value in self.redirect_path_allowlist.items()},
            "tls_policy": self.tls_policy.value,
        }


@dataclass(frozen=True)
class HttpExecutionRequest:
    project_ref: ProjectRef
    execution_ref: HttpExecutionRef
    destination_ref: HttpDestinationRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    node_ref: NodeRef
    node_attempt_id: str
    node_fence: int
    data_policy_ref: str
    egress_policy_ref: str
    method: str
    path: str
    query: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    secret_header_refs: Mapping[str, str] = field(default_factory=dict)
    body_ref: ContentRef | None = None
    redirect_policy: HttpRedirectPolicy = HttpRedirectPolicy.NONE
    max_redirects: int = 0
    max_response_bytes: int = 16 * 1024 * 1024
    timeout_seconds: float = 60.0
    expected_response_sha256: str | None = None
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise HttpContractError("HTTP request requires exact ProjectRef")
        refs = (
            self.execution_ref.project_ref,
            self.destination_ref.project_ref,
            self.task_ref.project_ref,
            self.run_ref.project_ref,
            self.node_ref.project_ref,
        )
        if any(item != self.project_ref for item in refs):
            raise HttpScopeError("HTTP request binding crossed Project scope")
        if _SHA256.fullmatch(self.task_digest) is None:
            raise HttpContractError("HTTP request Task digest is malformed")
        _text(self.node_attempt_id, "HTTP node attempt ID", 256)
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise HttpContractError("HTTP node fence is malformed")
        for value, name in ((self.data_policy_ref, "data policy ref"), (self.egress_policy_ref, "egress policy ref")):
            if not isinstance(value, str) or _REF.fullmatch(value) is None:
                raise HttpContractError(f"HTTP request {name} is malformed")
        if not isinstance(self.method, str) or _METHOD.fullmatch(self.method) is None:
            raise HttpContractError("HTTP method is malformed")
        object.__setattr__(self, "path", _canonical_path(self.path, "HTTP request path"))
        if not isinstance(self.query, Mapping) or len(self.query) > 256:
            raise HttpContractError("HTTP query mapping is malformed or unbounded")
        query: dict[str, str] = {}
        for key, value in self.query.items():
            _text(key, "HTTP query name", 512)
            _text(value, "HTTP query value", 8192)
            if _SENSITIVE_NAME.search(key) is not None:
                raise HttpContractError("secret-looking HTTP query parameter is forbidden")
            query[key] = value
        object.__setattr__(self, "query", MappingProxyType(dict(sorted(query.items()))))
        normal_headers = _header_mapping(self.headers, secret=False)
        secret_headers = _header_mapping(self.secret_header_refs, secret=True)
        if set(normal_headers).intersection(secret_headers):
            raise HttpContractError("HTTP normal and secret headers overlap")
        object.__setattr__(self, "headers", normal_headers)
        object.__setattr__(self, "secret_header_refs", secret_headers)
        if self.body_ref is not None and not isinstance(self.body_ref, ContentRef):
            raise HttpContractError("HTTP body_ref must be ContentRef")
        if not isinstance(self.redirect_policy, HttpRedirectPolicy):
            raise HttpContractError("HTTP redirect policy is malformed")
        if (
            not isinstance(self.max_redirects, int)
            or isinstance(self.max_redirects, bool)
            or not 0 <= self.max_redirects <= 16
            or (self.redirect_policy is HttpRedirectPolicy.NONE and self.max_redirects != 0)
            or (self.redirect_policy is not HttpRedirectPolicy.NONE and self.max_redirects < 1)
        ):
            raise HttpContractError("HTTP redirect bound is incompatible with redirect policy")
        if not isinstance(self.max_response_bytes, int) or isinstance(self.max_response_bytes, bool) or not 0 <= self.max_response_bytes <= 2**63 - 1:
            raise HttpContractError("HTTP response size cap is malformed")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not 0 < float(self.timeout_seconds) <= 86_400:
            raise HttpContractError("HTTP timeout is malformed")
        if self.expected_response_sha256 is not None and _SHA256.fullmatch(self.expected_response_sha256) is None:
            raise HttpContractError("HTTP expected response digest is malformed")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "body_ref": _content_payload(self.body_ref),
            "data_policy_ref": self.data_policy_ref,
            "destination_ref": self.destination_ref.value,
            "egress_policy_ref": self.egress_policy_ref,
            "execution_ref": self.execution_ref.value,
            "expected_response_sha256": self.expected_response_sha256,
            "headers": dict(self.headers),
            "max_redirects": self.max_redirects,
            "max_response_bytes": self.max_response_bytes,
            "method": self.method,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "node_ref": self.node_ref.value,
            "path": self.path,
            "project_ref": self.project_ref.value,
            "query": dict(self.query),
            "redirect_policy": self.redirect_policy.value,
            "run_ref": f"run://{self.project_ref.value}/{self.run_ref.run_id}",
            "secret_header_refs": dict(self.secret_header_refs),
            "task_digest": self.task_digest,
            "task_ref": f"task://{self.project_ref.value}/{self.task_ref.task_id}/{self.task_ref.revision}",
            "timeout_seconds": float(self.timeout_seconds),
        }


@dataclass(frozen=True)
class HttpExecutionResult:
    execution_ref: HttpExecutionRef
    destination_ref: HttpDestinationRef
    method: str
    origin: str
    path: str
    status_code: int | None
    response_headers: Mapping[str, str]
    response_ref: ContentRef | None
    response_artifact_ref: ArtifactRef | None
    bytes_sent: int
    bytes_received: int
    latency_ms: float
    redirect_chain: tuple[str, ...]
    transport_success: bool
    semantic_success: None
    failure: HttpExecutionFailure | None
    tool_call_ref: ToolCallRef
    receipt_artifact_ref: ArtifactRef
    completed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        project = self.execution_ref.project_ref
        if self.destination_ref.project_ref != project or self.tool_call_ref.project_ref != project or self.receipt_artifact_ref.project_ref != project:
            raise HttpScopeError("HTTP result evidence crossed Project scope")
        if self.response_artifact_ref is not None and self.response_artifact_ref.project_ref != project:
            raise HttpScopeError("HTTP response Artifact crossed Project scope")
        if _METHOD.fullmatch(self.method) is None:
            raise HttpContractError("HTTP result method is malformed")
        object.__setattr__(self, "origin", _canonical_origin(self.origin))
        object.__setattr__(self, "path", _canonical_path(self.path, "HTTP result path"))
        if self.status_code is not None and (not isinstance(self.status_code, int) or not 100 <= self.status_code <= 999):
            raise HttpContractError("HTTP result status is malformed")
        headers = _response_header_mapping(self.response_headers)
        object.__setattr__(self, "response_headers", headers)
        if (self.response_ref is None) != (self.response_artifact_ref is None):
            raise HttpIntegrityError("HTTP response ContentRef and Artifact differ")
        for value, name in ((self.bytes_sent, "bytes_sent"), (self.bytes_received, "bytes_received")):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise HttpContractError(f"HTTP result {name} is malformed")
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, (int, float)) or float(self.latency_ms) < 0:
            raise HttpContractError("HTTP result latency is malformed")
        if not isinstance(self.redirect_chain, tuple) or len(self.redirect_chain) > 16:
            raise HttpContractError("HTTP redirect evidence is malformed")
        for target in self.redirect_chain:
            parsed = urlsplit(_text(target, "HTTP redirect evidence", 8192))
            _canonical_origin(f"{parsed.scheme}://{parsed.netloc}")
            _canonical_path(parsed.path or "/", "HTTP redirect evidence path")
            if parsed.query or parsed.fragment or parsed.username is not None:
                raise HttpContractError("HTTP redirect evidence contains unsafe URL material")
        if not isinstance(self.transport_success, bool) or self.semantic_success is not None:
            raise HttpContractError("HTTP transport/semantic classification is malformed")
        if self.transport_success and self.status_code is None:
            raise HttpIntegrityError("successful HTTP transport lacks status")
        if not self.transport_success and self.failure is None:
            raise HttpIntegrityError("failed HTTP transport lacks failure classification")
        if self.failure is not None and not isinstance(self.failure, HttpExecutionFailure):
            raise HttpContractError("HTTP failure classification is malformed")
        _timestamp(self.completed_at, "HTTP result completed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.execution_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {
            "bytes_received": self.bytes_received,
            "bytes_sent": self.bytes_sent,
            "completed_at": self.completed_at,
            "destination_ref": self.destination_ref.value,
            "execution_ref": self.execution_ref.value,
            "failure": None if self.failure is None else self.failure.value,
            "latency_ms": float(self.latency_ms),
            "method": self.method,
            "origin": self.origin,
            "path": self.path,
            "receipt_artifact_ref": self.receipt_artifact_ref.value,
            "redirect_chain": list(self.redirect_chain),
            "response_artifact_ref": None if self.response_artifact_ref is None else self.response_artifact_ref.value,
            "response_headers": dict(self.response_headers),
            "response_ref": _content_payload(self.response_ref),
            "semantic_success": None,
            "status_code": self.status_code,
            "tool_call_ref": self.tool_call_ref.value,
            "transport_success": self.transport_success,
        }


@dataclass(frozen=True)
class HttpCancellationReceipt:
    execution_ref: HttpExecutionRef
    accepted: bool
    idempotency_key: str
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool) or _KEY.fullmatch(self.idempotency_key) is None:
            raise HttpContractError("HTTP cancellation receipt is malformed")
        _timestamp(self.observed_at, "HTTP cancellation observed_at")
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "execution_ref": self.execution_ref.value,
            "idempotency_key": self.idempotency_key,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class HttpAdapterDescriptor:
    implementation_id: str
    transport_kind: str
    runtime_version: str
    verified_tls: bool
    streaming_upload: bool
    streaming_download: bool
    cancellation: bool
    observed_at: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.implementation_id, "implementation_id"),
            (self.transport_kind, "transport_kind"),
            (self.runtime_version, "runtime_version"),
        ):
            _text(value, f"HTTP descriptor {name}", 1024)
        if not all(isinstance(value, bool) for value in (self.verified_tls, self.streaming_upload, self.streaming_download, self.cancellation)):
            raise HttpContractError("HTTP descriptor feature claim is malformed")
        _timestamp(self.observed_at, "HTTP descriptor observed_at")


@runtime_checkable
class HttpAdapter(Protocol):
    """Provider-neutral HTTP transport contract."""

    def register_destination(
        self,
        access: ProjectAccess,
        destination: HttpDestination,
        *,
        idempotency_key: str,
    ) -> HttpDestination: ...

    def get_destination(self, access: ProjectAccess, destination_ref: HttpDestinationRef) -> HttpDestination: ...

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: HttpExecutionRequest,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> HttpExecutionResult: ...

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        execution_ref: HttpExecutionRef,
        *,
        idempotency_key: str,
    ) -> HttpCancellationReceipt: ...

    def describe(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> HttpAdapterDescriptor: ...


@dataclass
class _ActiveExecution:
    cancellation: threading.Event
    connection: http.client.HTTPConnection | None = None


@dataclass
class _TransferObservation:
    origin: str
    path: str
    status_code: int | None = None
    response_headers: Mapping[str, str] = field(default_factory=dict)
    response_ref: ContentRef | None = None
    bytes_sent: int = 0
    bytes_received: int = 0
    redirect_chain: list[str] = field(default_factory=list)


class _TransferError(Exception):
    def __init__(self, failure: HttpExecutionFailure, observation: _TransferObservation) -> None:
        super().__init__(failure.value)
        self.failure = failure
        self.observation = observation


@dataclass(frozen=True)
class _StartedExecution:
    call: ToolCall
    request_ref: ContentRef
    first_claim: bool


class StdlibHttpAdapter:
    """Real streaming HTTP/1.1 adapter using Python's verified stdlib transport."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        supported_data_policy_refs: Sequence[str] = (),
        supported_egress_policy_refs: Sequence[str] = (),
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("object_store must implement ObjectStorageBackend")
        self.database_path = Path(database_path)
        self.object_store = object_store
        for values, name in (
            (supported_data_policy_refs, "supported data policy refs"),
            (supported_egress_policy_refs, "supported egress policy refs"),
        ):
            if isinstance(values, (str, bytes)) or len(values) > 256:
                raise HttpContractError(f"HTTP {name} are malformed or unbounded")
            if any(not isinstance(value, str) or _REF.fullmatch(value) is None for value in values):
                raise HttpContractError(f"HTTP {name} contain a malformed ref")
        self.supported_data_policy_refs = tuple(sorted(set(supported_data_policy_refs)))
        self.supported_egress_policy_refs = tuple(sorted(set(supported_egress_policy_refs)))
        self.projects = ProjectStore(database_path)
        self.graphs = GraphService(database_path)
        self.tasks = TaskRevisionService(database_path)
        self.runs = RunService(database_path)
        self.calls = CallLedgerService(database_path)
        self.artifacts = ArtifactService(database_path)
        self.capabilities = CapabilityRegistry(database_path)
        self.implementations = CapabilityImplementationRegistry(database_path)
        self._active: dict[str, _ActiveExecution] = {}
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
                CREATE TABLE IF NOT EXISTS http_destinations (
                    project_id TEXT NOT NULL,
                    destination_id TEXT NOT NULL,
                    destination_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,destination_id)
                );
                CREATE TABLE IF NOT EXISTS http_destination_claims (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    destination_id TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS http_execution_claims (
                    project_id TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    request_size INTEGER NOT NULL,
                    request_media_type TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    claim_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,node_attempt_id,idempotency_key),
                    UNIQUE (project_id,execution_id),
                    UNIQUE (project_id,call_id),
                    FOREIGN KEY (project_id,call_id) REFERENCES calls(project_id,call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS http_execution_results (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,call_id),
                    UNIQUE (project_id,execution_id),
                    FOREIGN KEY (project_id,call_id) REFERENCES calls(project_id,call_id)
                      ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS http_cancellations (
                    project_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id,execution_id,idempotency_key)
                );
                CREATE TRIGGER IF NOT EXISTS http_destinations_no_update BEFORE UPDATE ON http_destinations
                  BEGIN SELECT RAISE(ABORT,'HTTP destinations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS http_destinations_no_delete BEFORE DELETE ON http_destinations
                  BEGIN SELECT RAISE(ABORT,'HTTP destinations cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS http_destination_claims_no_update BEFORE UPDATE ON http_destination_claims
                  BEGIN SELECT RAISE(ABORT,'HTTP destination claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS http_destination_claims_no_delete BEFORE DELETE ON http_destination_claims
                  BEGIN SELECT RAISE(ABORT,'HTTP destination claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS http_execution_claims_no_update BEFORE UPDATE ON http_execution_claims
                  BEGIN SELECT RAISE(ABORT,'HTTP execution claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS http_execution_claims_no_delete BEFORE DELETE ON http_execution_claims
                  BEGIN SELECT RAISE(ABORT,'HTTP execution claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS http_execution_results_no_update BEFORE UPDATE ON http_execution_results
                  BEGIN SELECT RAISE(ABORT,'HTTP execution results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS http_execution_results_no_delete BEFORE DELETE ON http_execution_results
                  BEGIN SELECT RAISE(ABORT,'HTTP execution results cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS http_cancellations_no_update BEFORE UPDATE ON http_cancellations
                  BEGIN SELECT RAISE(ABORT,'HTTP cancellations are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS http_cancellations_no_delete BEFORE DELETE ON http_cancellations
                  BEGIN SELECT RAISE(ABORT,'HTTP cancellations cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def capability_ref(operation: str) -> CapabilityRef:
        if operation not in _OPERATIONS:
            raise HttpContractError("HTTP operation is unsupported")
        return CapabilityRef(f"http.{operation}", "1.0.0")

    @staticmethod
    def _implementation_ref(project_ref: ProjectRef, operation: str) -> CapabilityImplementationRef:
        identity = hashlib.sha256(f"{project_ref.value}\x00http.{operation}\x001.0.0".encode()).hexdigest()[:32]
        return CapabilityImplementationRef(project_ref, f"cimpl_{identity}")

    def register_capabilities(self, access: ProjectAccess) -> Mapping[CapabilityRef, CapabilityImplementation]:
        self._authorize(access, access.project_ref)
        registered: dict[CapabilityRef, CapabilityImplementation] = {}
        for operation in _OPERATIONS:
            capability_ref = self.capability_ref(operation)
            side_effect = "EXTERNAL_WRITE" if operation in {"execute", "cancel"} else "READ_ONLY"
            capability = self.capabilities.register(
                Capability(
                    capability_ref,
                    f"Controlled provider-neutral HTTP {operation}",
                    input_contract={"request": "schema://biella/http-execution-request/1"},
                    output_contract={"result": "schema://biella/http-execution-result/1"},
                    side_effects=(f"http.{operation}",) if operation != "describe" else (),
                )
            )
            implementation_ref = self._implementation_ref(access.project_ref, operation)
            try:
                implementation = self.implementations.get(access, implementation_ref)
            except RoutingNotFoundError:
                implementation = self.implementations.register(
                    access,
                    CapabilityImplementation(
                        implementation_ref,
                        capability.capability_ref,
                        "1.0.0",
                        ImplementationKind.TOOL,
                        "adapter://biella/http",
                        "runtime://python/http.client",
                        tool_ref=f"tool://biella/http/{operation}",
                        features=("policy-before-transfer", "streaming", "verified-tls", "bounded-response"),
                        input_features=("destination-ref", "content-ref", "secret-ref", "egress-policy-ref"),
                        output_features=("artifact", "content-ref", "tool-call", "transport-result"),
                        side_effect_authority=side_effect,
                        resource_kinds=("network.egress",),
                        remote_egress=operation == "execute",
                        supported_data_policy_refs=self.supported_data_policy_refs,
                        supported_egress_policy_refs=self.supported_egress_policy_refs,
                        metadata={"adapter_contract": "http-v1"},
                    ),
                    idempotency_key=f"http-{operation}-implementation",
                )
            registered[capability_ref] = implementation
        return MappingProxyType(registered)

    def _authorize(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise HttpIntegrityError("Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise HttpScopeError("HTTP Project scope mismatch") from exc

    @staticmethod
    def _key(value: str) -> str:
        if not isinstance(value, str) or _KEY.fullmatch(value) is None:
            raise HttpContractError("HTTP idempotency key is malformed")
        return value

    def _database_now(self) -> str:
        connection = self._connect()
        try:
            value = connection.execute("SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')").fetchone()[0]
            if not isinstance(value, str):
                raise HttpIntegrityError("durable database time is unavailable")
            return value
        finally:
            connection.close()

    def _run_attempt(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        result = next(
            (
                item
                for item in self.runs.list_attempts(access, attempt.run_ref)
                if item.attempt_id == attempt.run_attempt_id and item.fence == attempt.run_fence
            ),
            None,
        )
        if result is None:
            raise HttpAuthorityError("exact Run execution authority is unavailable")
        return result

    def _require_operation_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        operation: str,
    ) -> None:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise HttpAuthorityError("NodeExecutionAttempt is required")
        if attempt.node_ref.project_ref != access.project_ref:
            raise HttpScopeError("HTTP Node attempt crossed Project scope")
        graph = self.graphs.get_graph(access, attempt.node_ref.graph_ref)
        node = next((item for item in graph.nodes if item.node_ref == attempt.node_ref), None)
        if node is None or self.capability_ref(operation) not in node.required_capabilities:
            raise HttpAuthorityError("HTTP capability is not authorized by exact Node")
        task = self.tasks.get_task(access, attempt.task_ref)
        if task.canonical_digest != attempt.task_digest:
            raise HttpIntegrityError("HTTP Node attempt Task digest changed")
        levels = {"READ_ONLY": 0, "CANDIDATE_WRITE": 1, "PROJECT_WRITE": 2, "EXTERNAL_SIDE_EFFECT": 3}
        required = 3 if operation in {"execute", "cancel"} else 0
        if levels[task.side_effect_authority] < required or levels[node.side_effect_requirement] < required:
            raise HttpAuthorityError("HTTP operation exceeds Task or Node side-effect authority")

    @staticmethod
    def _destination_ref(value: object, project_ref: ProjectRef) -> HttpDestinationRef:
        if not isinstance(value, str):
            raise HttpIntegrityError("persisted HTTP destination ref is malformed")
        prefix = f"http-destination://{project_ref.value}/"
        if not value.startswith(prefix):
            raise HttpScopeError("persisted HTTP destination crossed Project scope")
        return HttpDestinationRef(project_ref, value.removeprefix(prefix))

    @staticmethod
    def _execution_ref(value: object, project_ref: ProjectRef) -> HttpExecutionRef:
        if not isinstance(value, str):
            raise HttpIntegrityError("persisted HTTP execution ref is malformed")
        prefix = f"http-execution://{project_ref.value}/"
        if not value.startswith(prefix):
            raise HttpScopeError("persisted HTTP execution crossed Project scope")
        return HttpExecutionRef(project_ref, value.removeprefix(prefix))

    @staticmethod
    def _artifact_ref(value: object, project_ref: ProjectRef) -> ArtifactRef | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise HttpIntegrityError("persisted HTTP ArtifactRef is malformed")
        prefix = f"artifact://{project_ref.value}/"
        if not value.startswith(prefix):
            raise HttpScopeError("persisted HTTP Artifact crossed Project scope")
        parts = value.removeprefix(prefix).split("/")
        if len(parts) != 2:
            raise HttpIntegrityError("persisted HTTP ArtifactRef is malformed")
        try:
            return ArtifactRef(project_ref, parts[0], int(parts[1]))
        except (TypeError, ValueError) as exc:
            raise HttpIntegrityError("persisted HTTP ArtifactRef is malformed") from exc

    @staticmethod
    def _tool_call_ref(value: object, project_ref: ProjectRef) -> ToolCallRef:
        if not isinstance(value, str):
            raise HttpIntegrityError("persisted HTTP ToolCallRef is malformed")
        prefix = f"tool-call://{project_ref.value}/"
        if not value.startswith(prefix):
            raise HttpScopeError("persisted HTTP ToolCall crossed Project scope")
        try:
            return ToolCallRef(project_ref, value.removeprefix(prefix))
        except (TypeError, ValueError) as exc:
            raise HttpIntegrityError("persisted HTTP ToolCallRef is malformed") from exc

    @staticmethod
    def _content_ref(value: object) -> ContentRef | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise HttpIntegrityError("persisted HTTP ContentRef is malformed")
        try:
            return ContentRef(
                cast(str, value["algorithm"]),
                cast(str, value["digest"]),
                cast(int, value["size_bytes"]),
                cast(str, value["media_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HttpIntegrityError("persisted HTTP ContentRef is malformed") from exc

    def _destination_from_payload(self, payload: object, project_ref: ProjectRef) -> HttpDestination:
        if not isinstance(payload, dict):
            raise HttpIntegrityError("persisted HTTP destination is malformed")
        try:
            redirects = cast(dict[str, list[str]], payload["redirect_path_allowlist"])
            return HttpDestination(
                self._destination_ref(payload["destination_ref"], project_ref),
                cast(str, payload["origin"]),
                tuple(cast(list[str], payload["allowed_path_prefixes"])),
                cast(str | None, payload["auth_profile_ref"]),
                cast(str | None, payload["auth_header_name"]),
                cast(str, payload["data_policy_ref"]),
                cast(str, payload["egress_policy_ref"]),
                HttpTlsPolicy(cast(str, payload["tls_policy"])),
                {key: tuple(value) for key, value in redirects.items()},
                cast(str | None, payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError, HttpAdapterError) as exc:
            if isinstance(exc, HttpIntegrityError):
                raise
            raise HttpIntegrityError("persisted HTTP destination is malformed") from exc

    def register_destination(
        self,
        access: ProjectAccess,
        destination: HttpDestination,
        *,
        idempotency_key: str,
    ) -> HttpDestination:
        self._key(idempotency_key)
        if not isinstance(destination, HttpDestination):
            raise HttpContractError("exact HttpDestination is required")
        self._authorize(access, destination.project_ref)
        if (
            destination.data_policy_ref not in self.supported_data_policy_refs
            or destination.egress_policy_ref not in self.supported_egress_policy_refs
        ):
            raise HttpAuthorityError("HTTP destination policy is not supported by this adapter configuration")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM http_destination_claims WHERE project_id=? AND idempotency_key=?",
                (access.project_ref.value, idempotency_key),
            ).fetchone()
            if prior is not None:
                row = connection.execute(
                    "SELECT * FROM http_destinations WHERE project_id=? AND destination_id=?",
                    (access.project_ref.value, cast(str, prior["destination_id"])),
                ).fetchone()
                if row is None:
                    raise HttpIntegrityError("HTTP destination claim lost its destination")
                try:
                    existing = self._destination_from_payload(
                        json.loads(cast(str, row["destination_json"])),
                        access.project_ref,
                    )
                except json.JSONDecodeError as exc:
                    raise HttpIntegrityError("HTTP destination JSON is malformed") from exc
                candidate_payload = destination.payload()
                candidate_payload["created_at"] = existing.created_at
                request_sha = _digest({"destination": candidate_payload, "idempotency_key": idempotency_key})
                if (
                    prior["destination_id"] != destination.destination_ref.destination_id
                    or existing.payload() != candidate_payload
                    or not hmac.compare_digest(cast(str, prior["request_sha256"]), request_sha)
                    or not hmac.compare_digest(cast(str, row["record_sha256"]), existing.record_sha256)
                ):
                    raise HttpConflictError("HTTP destination idempotency identity changed")
                connection.commit()
                return existing
            now = self._database_now()
            persisted = destination if destination.created_at is not None else HttpDestination(
                destination.destination_ref,
                destination.origin,
                destination.allowed_path_prefixes,
                destination.auth_profile_ref,
                destination.auth_header_name,
                destination.data_policy_ref,
                destination.egress_policy_ref,
                destination.tls_policy,
                destination.redirect_path_allowlist,
                now,
            )
            request_sha = _digest({"destination": persisted.payload(), "idempotency_key": idempotency_key})
            connection.execute(
                "INSERT INTO http_destinations VALUES (?,?,?,?)",
                (
                    access.project_ref.value,
                    persisted.destination_ref.destination_id,
                    _json(persisted.payload()),
                    persisted.record_sha256,
                ),
            )
            connection.execute(
                "INSERT INTO http_destination_claims VALUES (?,?,?,?)",
                (access.project_ref.value, idempotency_key, persisted.destination_ref.destination_id, request_sha),
            )
            connection.commit()
            return persisted
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise HttpConflictError("HTTP destination registration conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_destination(self, access: ProjectAccess, destination_ref: HttpDestinationRef) -> HttpDestination:
        if not isinstance(destination_ref, HttpDestinationRef):
            raise HttpContractError("exact HttpDestinationRef is required")
        self._authorize(access, destination_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM http_destinations WHERE project_id=? AND destination_id=?",
                (access.project_ref.value, destination_ref.destination_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise HttpNotFoundError("HTTP destination is unavailable")
        try:
            destination = self._destination_from_payload(json.loads(cast(str, row["destination_json"])), access.project_ref)
        except json.JSONDecodeError as exc:
            raise HttpIntegrityError("HTTP destination JSON is malformed") from exc
        if destination.destination_ref != destination_ref or not hmac.compare_digest(cast(str, row["record_sha256"]), destination.record_sha256):
            raise HttpIntegrityError("HTTP destination evidence changed")
        return destination

    def describe(self, access: ProjectAccess, attempt: NodeExecutionAttempt) -> HttpAdapterDescriptor:
        self._require_operation_authority(access, attempt, "describe")
        implementation = self.implementations.get(access, self._implementation_ref(access.project_ref, "describe"))
        return HttpAdapterDescriptor(
            implementation.implementation_ref.value,
            "stdlib.http.client",
            ssl.OPENSSL_VERSION,
            True,
            True,
            True,
            True,
            self._database_now(),
        )

    def _validate_binding(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: HttpExecutionRequest,
        destination: HttpDestination,
    ) -> None:
        task = self.tasks.get_task(access, attempt.task_ref)
        if (
            request.project_ref != access.project_ref
            or request.task_ref != attempt.task_ref
            or request.task_digest != attempt.task_digest
            or request.run_ref != attempt.run_ref
            or request.node_ref != attempt.node_ref
            or request.node_attempt_id != attempt.attempt_id
            or request.node_fence != attempt.fence
            or request.destination_ref != destination.destination_ref
        ):
            raise HttpAuthorityError("HTTP request Task/Run/NodeAttempt binding is not exact")
        if (
            task.data_policy_ref is None
            or task.egress_policy_ref is None
            or request.data_policy_ref != task.data_policy_ref
            or request.egress_policy_ref != task.egress_policy_ref
            or destination.data_policy_ref != task.data_policy_ref
            or destination.egress_policy_ref != task.egress_policy_ref
        ):
            raise HttpAuthorityError("HTTP data or egress policy binding is not exact")
        if not _path_allowed(request.path, destination.allowed_path_prefixes):
            raise HttpAuthorityError("HTTP request path is denied by destination policy")

    def _start_execution(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: HttpExecutionRequest,
        *,
        idempotency_key: str,
    ) -> _StartedExecution:
        self._key(idempotency_key)
        self._require_operation_authority(access, attempt, "execute")
        request_ref = self.object_store.put(_json(request.payload()).encode(), media_type=_REQUEST_MEDIA_TYPE)
        implementation_ref = self._implementation_ref(access.project_ref, "execute")
        try:
            implementation = self.implementations.get(access, implementation_ref)
        except RoutingNotFoundError as exc:
            raise HttpAuthorityError("HTTP implementation is not registered") from exc
        call_key = _digest({"attempt": attempt.record_sha256, "idempotency_key": idempotency_key})
        try:
            call = self.calls.start_tool_call(
                access,
                attempt,
                idempotency_key=f"http-start-{call_key[:46]}",
                capability_ref=self.capability_ref("execute"),
                purpose="INITIAL",
                retry_of=None,
                parent_model_call_ref=None,
                tool_id=cast(str, implementation.tool_ref),
                implementation_id=implementation.implementation_ref.value,
                runtime_id=implementation.runtime_ref,
                input_refs=(request_ref,) if request.body_ref is None else (request_ref, request.body_ref),
                provider_trace_id=None,
            )
        except CallAuthorityError as exc:
            raise HttpAuthorityError("HTTP ToolCall authority was rejected") from exc
        except CallConflictError as exc:
            raise HttpConflictError("HTTP ToolCall idempotency conflicts") from exc
        claim = {
            "call_ref": call.call_ref.value,
            "execution_ref": request.execution_ref.value,
            "idempotency_key": idempotency_key,
            "node_attempt_id": attempt.attempt_id,
            "project_ref": access.project_ref.value,
            "request_ref": request_ref.value,
        }
        claim_sha = _digest(claim)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT * FROM http_execution_claims WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?",
                (access.project_ref.value, attempt.attempt_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (
                    prior["execution_id"] != request.execution_ref.execution_id
                    or prior["request_digest"] != request_ref.digest
                    or prior["request_size"] != request_ref.size_bytes
                    or prior["request_media_type"] != request_ref.media_type
                    or prior["call_id"] != call.call_ref.call_id
                    or not hmac.compare_digest(cast(str, prior["claim_sha256"]), claim_sha)
                ):
                    raise HttpConflictError("HTTP execution idempotency identity changed")
                connection.commit()
                return _StartedExecution(call, request_ref, False)
            if call.status != "RUNNING":
                raise HttpIntegrityError("terminal HTTP ToolCall lost its immutable claim")
            connection.execute(
                "INSERT INTO http_execution_claims VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    access.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                    request.execution_ref.execution_id,
                    request_ref.digest,
                    request_ref.size_bytes,
                    request_ref.media_type,
                    call.call_ref.call_id,
                    claim_sha,
                ),
            )
            connection.commit()
            return _StartedExecution(call, request_ref, True)
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise HttpConflictError("HTTP execution claim conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _cancelled(self, execution_ref: HttpExecutionRef) -> bool:
        connection = self._connect()
        try:
            return connection.execute(
                "SELECT 1 FROM http_cancellations WHERE project_id=? AND execution_id=? LIMIT 1",
                (execution_ref.project_ref.value, execution_ref.execution_id),
            ).fetchone() is not None
        finally:
            connection.close()

    @staticmethod
    def _remaining(deadline: float, active: _ActiveExecution, observation: _TransferObservation) -> float:
        if active.cancellation.is_set():
            raise _TransferError(HttpExecutionFailure.CANCELLED, observation)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _TransferError(HttpExecutionFailure.TIMEOUT, observation)
        return remaining

    @staticmethod
    def _target(url: str) -> tuple[str, str, str]:
        parsed = urlsplit(url)
        if parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise HttpContractError("HTTP target contains credentials or fragment")
        origin = _canonical_origin(f"{parsed.scheme}://{parsed.netloc}")
        path = _canonical_path(parsed.path or "/", "HTTP target path")
        if len(parsed.query.encode()) > 16 * 1024 or any(ord(character) < 32 for character in parsed.query):
            raise HttpContractError("HTTP target query is malformed or unbounded")
        request_target = path if not parsed.query else f"{path}?{parsed.query}"
        return origin, path, request_target

    @staticmethod
    def _connection(origin: str, timeout: float) -> http.client.HTTPConnection:
        parsed = urlsplit(origin)
        host = cast(str, parsed.hostname)
        port = parsed.port
        if parsed.scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl.create_default_context())
        return http.client.HTTPConnection(host, port, timeout=timeout)

    @staticmethod
    def _safe_response_headers(response: http.client.HTTPResponse) -> Mapping[str, str]:
        result: dict[str, str] = {}
        for name, value in response.getheaders():
            lowered = name.lower()
            if lowered in _SAFE_RESPONSE_HEADERS and lowered not in result:
                if "\r" in value or "\n" in value or len(value.encode()) > 8192:
                    raise HttpIntegrityError("HTTP response safe header is malformed")
                result[lowered] = value
        return MappingProxyType(dict(sorted(result.items())))

    def _authorize_redirect(
        self,
        destination: HttpDestination,
        request: HttpExecutionRequest,
        prior_origin: str,
        target_origin: str,
        target_path: str,
    ) -> bool:
        if request.redirect_policy is HttpRedirectPolicy.NONE:
            return False
        if request.redirect_policy is HttpRedirectPolicy.SAME_ORIGIN:
            return target_origin == destination.origin and _path_allowed(target_path, destination.allowed_path_prefixes)
        if target_origin == destination.origin:
            return _path_allowed(target_path, destination.allowed_path_prefixes)
        prefixes = destination.redirect_path_allowlist.get(target_origin)
        if prefixes is None or not _path_allowed(target_path, prefixes):
            return False
        if prior_origin.startswith("https://") and target_origin.startswith("http://"):
            return False
        return True

    def _send_body(
        self,
        connection: http.client.HTTPConnection,
        reader: BinaryIO,
        content_ref: ContentRef,
        deadline: float,
        active: _ActiveExecution,
        observation: _TransferObservation,
    ) -> None:
        sent = 0
        while True:
            remaining = self._remaining(deadline, active, observation)
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = reader.read(64 * 1024)
            if not chunk:
                break
            connection.send(chunk)
            sent += len(chunk)
            observation.bytes_sent += len(chunk)
        if sent != content_ref.size_bytes:
            raise _TransferError(HttpExecutionFailure.CONTENT_INTEGRITY_FAILED, observation)

    def _transfer(
        self,
        destination: HttpDestination,
        request: HttpExecutionRequest,
        secret_headers: Mapping[str, str],
        active: _ActiveExecution,
    ) -> _TransferObservation:
        query = urlencode(list(request.query.items()))
        current_url = urlunsplit((*urlsplit(destination.origin)[:2], request.path, query, ""))
        current_method = request.method
        send_body = request.body_ref is not None
        deadline = time.monotonic() + float(request.timeout_seconds)
        observation = _TransferObservation(destination.origin, request.path)
        for redirect_index in range(request.max_redirects + 1):
            origin, path, target = self._target(current_url)
            observation.origin = origin
            observation.path = path
            remaining = self._remaining(deadline, active, observation)
            connection = self._connection(origin, remaining)
            active.connection = connection
            try:
                connection.putrequest(current_method, target, skip_accept_encoding=True)
                connection.putheader("accept-encoding", "identity")
                for name, value in request.headers.items():
                    connection.putheader(name, value)
                include_secrets = origin == destination.origin
                if include_secrets:
                    for name, value in secret_headers.items():
                        connection.putheader(name, value)
                if send_body and request.body_ref is not None:
                    connection.putheader("content-length", str(request.body_ref.size_bytes))
                    if "content-type" not in request.headers:
                        connection.putheader("content-type", request.body_ref.media_type)
                connection.endheaders()
                if send_body and request.body_ref is not None:
                    with self.object_store.open(request.body_ref) as reader:
                        self._send_body(connection, reader, request.body_ref, deadline, active, observation)
                remaining = self._remaining(deadline, active, observation)
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                response = connection.getresponse()
                observation.status_code = response.status
                observation.response_headers = self._safe_response_headers(response)
                location = response.getheader("location")
                if response.status in {301, 302, 303, 307, 308} and location is not None:
                    if redirect_index >= request.max_redirects:
                        raise _TransferError(HttpExecutionFailure.REDIRECT_DENIED, observation)
                    next_url = urljoin(current_url, location)
                    next_origin, next_path, _ = self._target(next_url)
                    if not self._authorize_redirect(destination, request, origin, next_origin, next_path):
                        raise _TransferError(HttpExecutionFailure.REDIRECT_DENIED, observation)
                    observation.redirect_chain.append(f"{next_origin}{next_path}")
                    if response.status == 303:
                        current_method = "GET"
                        send_body = False
                    elif response.status in {301, 302} and current_method not in {"GET", "HEAD"}:
                        raise _TransferError(HttpExecutionFailure.REDIRECT_DENIED, observation)
                    current_url = next_url
                    continue
                with tempfile.TemporaryFile() as output:
                    while True:
                        remaining = self._remaining(deadline, active, observation)
                        if connection.sock is not None:
                            connection.sock.settimeout(remaining)
                        chunk = response.read(min(64 * 1024, request.max_response_bytes - observation.bytes_received + 1))
                        if not chunk:
                            break
                        observation.bytes_received += len(chunk)
                        if observation.bytes_received > request.max_response_bytes:
                            raise _TransferError(HttpExecutionFailure.OUTPUT_LIMIT, observation)
                        output.write(chunk)
                    output.flush()
                    output.seek(0)
                    media_type = observation.response_headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip()
                    try:
                        observation.response_ref = self.object_store.put(
                            output,
                            media_type=media_type or "application/octet-stream",
                            expected_digest=request.expected_response_sha256,
                            expected_size=observation.bytes_received,
                        )
                    except ObjectStorageIntegrityError as exc:
                        raise _TransferError(HttpExecutionFailure.CONTENT_INTEGRITY_FAILED, observation) from exc
                return observation
            except _TransferError:
                raise
            except ssl.SSLCertVerificationError as exc:
                raise _TransferError(HttpExecutionFailure.TLS_FAILED, observation) from exc
            except ssl.SSLError as exc:
                raise _TransferError(HttpExecutionFailure.TLS_FAILED, observation) from exc
            except (TimeoutError, socket.timeout) as exc:
                failure = HttpExecutionFailure.CANCELLED if active.cancellation.is_set() else HttpExecutionFailure.TIMEOUT
                raise _TransferError(failure, observation) from exc
            except socket.gaierror as exc:
                raise _TransferError(HttpExecutionFailure.DNS_CONNECT_FAILED, observation) from exc
            except ObjectStorageError as exc:
                raise _TransferError(HttpExecutionFailure.CONTENT_INTEGRITY_FAILED, observation) from exc
            except (ConnectionError, OSError, http.client.HTTPException) as exc:
                failure = HttpExecutionFailure.CANCELLED if active.cancellation.is_set() else HttpExecutionFailure.DNS_CONNECT_FAILED
                raise _TransferError(failure, observation) from exc
            finally:
                active.connection = None
                connection.close()
        raise _TransferError(HttpExecutionFailure.REDIRECT_DENIED, observation)

    def _publish_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: HttpExecutionRequest,
        destination: HttpDestination,
        started: _StartedExecution,
        observation: _TransferObservation,
        *,
        transport_success: bool,
        failure: HttpExecutionFailure | None,
        latency_ms: float,
        idempotency_key: str,
    ) -> HttpExecutionResult:
        response_artifact: Artifact | None = None
        if observation.response_ref is not None:
            response_artifact = self.artifacts.publish_from_run(
                access,
                producer_attempt=self._run_attempt(access, attempt),
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role="http.response",
                content_ref=observation.response_ref,
                source_refs=(),
                source_artifact_refs=(),
                source_content_refs=() if request.body_ref is None else (request.body_ref,),
                derivation_type="http.execute",
                metadata={
                    "media_type": observation.response_ref.media_type,
                    "schema_ref": "schema://biella/http-response/1",
                    "schema_version": "1.0.0",
                    "semantic_label": f"http-status-{observation.status_code}",
                },
            )
        completed_at = self._database_now()
        basis = {
            "bytes_received": observation.bytes_received,
            "bytes_sent": observation.bytes_sent,
            "completed_at": completed_at,
            "destination_ref": destination.destination_ref.value,
            "execution_ref": request.execution_ref.value,
            "failure": None if failure is None else failure.value,
            "latency_ms": float(latency_ms),
            "method": request.method,
            "origin": observation.origin,
            "path": observation.path,
            "redirect_chain": list(observation.redirect_chain),
            "response_artifact_ref": None if response_artifact is None else response_artifact.artifact_ref.value,
            "response_headers": dict(observation.response_headers),
            "response_ref": _content_payload(observation.response_ref),
            "semantic_success": None,
            "status_code": observation.status_code,
            "transport_success": transport_success,
        }
        manifest_ref = self.object_store.put(_json(basis).encode(), media_type=_RECEIPT_MEDIA_TYPE)
        receipt_artifact = self.artifacts.publish_from_run(
            access,
            producer_attempt=self._run_attempt(access, attempt),
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role="http.execution.receipt",
            content_ref=manifest_ref,
            source_refs=(),
            source_artifact_refs=() if response_artifact is None else (response_artifact.artifact_ref,),
            source_content_refs=tuple(
                item
                for item in (started.request_ref, request.body_ref, observation.response_ref)
                if item is not None
            ),
            derivation_type="http.execute",
            metadata={
                "media_type": manifest_ref.media_type,
                "schema_ref": "schema://biella/http-execution-result/1",
                "schema_version": "1.0.0",
            },
        )
        call_key = _digest({"attempt": attempt.record_sha256, "idempotency_key": idempotency_key})
        call_status = "SUCCEEDED" if transport_success else "FAILED"
        outputs: tuple[ContentRef | ArtifactRef, ...] = ()
        failure_evidence: tuple[ContentRef | ArtifactRef, ...] = ()
        if transport_success:
            outputs = tuple(
                item
                for item in (
                    observation.response_ref,
                    None if response_artifact is None else response_artifact.artifact_ref,
                    manifest_ref,
                    receipt_artifact.artifact_ref,
                )
                if item is not None
            )
        else:
            failure_evidence = (manifest_ref, receipt_artifact.artifact_ref)
        try:
            call = self.calls.finish_tool_call(
                access,
                attempt,
                started.call.call_ref,
                idempotency_key=f"http-finish-{call_key[:45]}",
                status=call_status,
                output_refs=outputs,
                usage=None,
                cost=None,
                failure_category=None if transport_success or failure is None else failure.value,
                failure_reason=None if transport_success or failure is None else f"HTTP transport failed: {failure.value}",
                failure_evidence_refs=failure_evidence,
            )
        except CallAuthorityError as exc:
            raise HttpAuthorityError("HTTP completion authority was rejected") from exc
        except CallConflictError as exc:
            raise HttpConflictError("HTTP completion conflicts") from exc
        result = HttpExecutionResult(
            request.execution_ref,
            destination.destination_ref,
            request.method,
            observation.origin,
            observation.path,
            observation.status_code,
            observation.response_headers,
            observation.response_ref,
            None if response_artifact is None else response_artifact.artifact_ref,
            observation.bytes_sent,
            observation.bytes_received,
            latency_ms,
            tuple(observation.redirect_chain),
            transport_success,
            None,
            failure,
            call.call_ref,
            receipt_artifact.artifact_ref,
            completed_at,
        )
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO http_execution_results VALUES (?,?,?,?,?)",
                (
                    access.project_ref.value,
                    result.tool_call_ref.call_id,
                    result.execution_ref.execution_id,
                    _json(result.payload()),
                    result.record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise HttpConflictError("HTTP result persistence conflicts") from exc
        finally:
            connection.close()
        return result

    def execute(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: HttpExecutionRequest,
        *,
        secret_values: Mapping[str, str],
        idempotency_key: str,
    ) -> HttpExecutionResult:
        if not isinstance(request, HttpExecutionRequest):
            raise HttpContractError("exact HttpExecutionRequest is required")
        self._authorize(access, request.project_ref)
        destination = self.get_destination(access, request.destination_ref)
        started = self._start_execution(access, attempt, request, idempotency_key=idempotency_key)
        if not started.first_claim:
            current = self.calls.get_tool_call(access, started.call.call_ref)
            if current.status in {"SUCCEEDED", "FAILED"}:
                return self.get_result(access, request.execution_ref)
            raise HttpConflictError("HTTP execution is already claimed and incomplete")
        started_at = time.monotonic()
        observation = _TransferObservation(destination.origin, request.path)
        failure: HttpExecutionFailure | None = None
        transport_success = False
        active = _ActiveExecution(threading.Event())
        try:
            try:
                self._validate_binding(access, attempt, request, destination)
            except HttpAuthorityError:
                failure = HttpExecutionFailure.EGRESS_DENIED
                return self._publish_result(
                    access,
                    attempt,
                    request,
                    destination,
                    started,
                    observation,
                    transport_success=False,
                    failure=failure,
                    latency_ms=(time.monotonic() - started_at) * 1000,
                    idempotency_key=idempotency_key,
                )
            expected_secret_refs = set(request.secret_header_refs.values())
            if destination.auth_profile_ref is not None:
                expected_secret_refs.add(destination.auth_profile_ref)
            if set(secret_values) != expected_secret_refs:
                failure = HttpExecutionFailure.AUTH_FAILED
                return self._publish_result(
                    access,
                    attempt,
                    request,
                    destination,
                    started,
                    observation,
                    transport_success=False,
                    failure=failure,
                    latency_ms=(time.monotonic() - started_at) * 1000,
                    idempotency_key=idempotency_key,
                )
            secret_headers: dict[str, str] = {}
            try:
                for name, secret_ref in request.secret_header_refs.items():
                    value = _text(secret_values[secret_ref], "HTTP secret header value", 64 * 1024)
                    if "\r" in value or "\n" in value:
                        raise HttpAuthorityError("HTTP secret header value contains a line break")
                    secret_headers[name] = value
                if destination.auth_profile_ref is not None and destination.auth_header_name is not None:
                    if destination.auth_header_name in secret_headers:
                        raise HttpAuthorityError("HTTP destination and request auth headers overlap")
                    secret_headers[destination.auth_header_name] = _text(
                        secret_values[destination.auth_profile_ref],
                        "HTTP auth profile value",
                        64 * 1024,
                    )
            except HttpAdapterError:
                failure = HttpExecutionFailure.AUTH_FAILED
                return self._publish_result(
                    access,
                    attempt,
                    request,
                    destination,
                    started,
                    observation,
                    transport_success=False,
                    failure=failure,
                    latency_ms=(time.monotonic() - started_at) * 1000,
                    idempotency_key=idempotency_key,
                )
            if request.execution_ref.value in self._active:
                raise HttpConflictError("HTTP execution identity is already active")
            self._active[request.execution_ref.value] = active
            if self._cancelled(request.execution_ref):
                active.cancellation.set()
            try:
                observation = self._transfer(destination, request, MappingProxyType(secret_headers), active)
                transport_success = True
                if observation.status_code in {401, 403} and secret_headers:
                    failure = HttpExecutionFailure.AUTH_FAILED
                elif observation.status_code is not None and observation.status_code >= 400:
                    failure = HttpExecutionFailure.HTTP_ERROR
            except _TransferError as exc:
                observation = exc.observation
                failure = exc.failure
            return self._publish_result(
                access,
                attempt,
                request,
                destination,
                started,
                observation,
                transport_success=transport_success,
                failure=failure,
                latency_ms=(time.monotonic() - started_at) * 1000,
                idempotency_key=idempotency_key,
            )
        finally:
            if active.connection is not None:
                active.connection.close()
            self._active.pop(request.execution_ref.value, None)

    def cancel(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        execution_ref: HttpExecutionRef,
        *,
        idempotency_key: str,
    ) -> HttpCancellationReceipt:
        self._key(idempotency_key)
        if not isinstance(execution_ref, HttpExecutionRef):
            raise HttpContractError("exact HttpExecutionRef is required")
        self._authorize(access, execution_ref.project_ref)
        self._require_operation_authority(access, attempt, "cancel")
        now = self._database_now()
        receipt = HttpCancellationReceipt(execution_ref, True, idempotency_key, now)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim = connection.execute(
                "SELECT * FROM http_execution_claims WHERE project_id=? AND execution_id=?",
                (access.project_ref.value, execution_ref.execution_id),
            ).fetchone()
            if claim is None:
                raise HttpNotFoundError("HTTP execution claim is unavailable for cancellation")
            if claim["node_attempt_id"] != attempt.attempt_id:
                raise HttpAuthorityError("HTTP cancellation crossed Node attempt ownership")
            prior = connection.execute(
                "SELECT * FROM http_cancellations WHERE project_id=? AND execution_id=? AND idempotency_key=?",
                (access.project_ref.value, execution_ref.execution_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                try:
                    prior_receipt = HttpCancellationReceipt(
                        self._execution_ref(json.loads(cast(str, prior["receipt_json"]))["execution_ref"], access.project_ref),
                        cast(bool, json.loads(cast(str, prior["receipt_json"]))["accepted"]),
                        cast(str, json.loads(cast(str, prior["receipt_json"]))["idempotency_key"]),
                        cast(str, json.loads(cast(str, prior["receipt_json"]))["observed_at"]),
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError, HttpAdapterError) as exc:
                    raise HttpIntegrityError("HTTP cancellation evidence is malformed") from exc
                if not hmac.compare_digest(cast(str, prior["record_sha256"]), prior_receipt.record_sha256):
                    raise HttpIntegrityError("HTTP cancellation evidence changed")
                connection.commit()
                return prior_receipt
            connection.execute(
                "INSERT INTO http_cancellations VALUES (?,?,?,?,?)",
                (
                    access.project_ref.value,
                    execution_ref.execution_id,
                    idempotency_key,
                    _json(receipt.payload()),
                    receipt.record_sha256,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise HttpConflictError("HTTP cancellation conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        active = self._active.get(execution_ref.value)
        if active is not None:
            active.cancellation.set()
            if active.connection is not None:
                active.connection.close()
        return receipt

    def _result_from_payload(self, payload: object, project_ref: ProjectRef) -> HttpExecutionResult:
        if not isinstance(payload, dict):
            raise HttpIntegrityError("persisted HTTP result is malformed")
        try:
            receipt_ref = self._artifact_ref(payload["receipt_artifact_ref"], project_ref)
            if receipt_ref is None:
                raise HttpIntegrityError("persisted HTTP receipt Artifact is missing")
            return HttpExecutionResult(
                self._execution_ref(payload["execution_ref"], project_ref),
                self._destination_ref(payload["destination_ref"], project_ref),
                cast(str, payload["method"]),
                cast(str, payload["origin"]),
                cast(str, payload["path"]),
                cast(int | None, payload["status_code"]),
                cast(dict[str, str], payload["response_headers"]),
                self._content_ref(payload["response_ref"]),
                self._artifact_ref(payload["response_artifact_ref"], project_ref),
                cast(int, payload["bytes_sent"]),
                cast(int, payload["bytes_received"]),
                cast(float, payload["latency_ms"]),
                tuple(cast(list[str], payload["redirect_chain"])),
                cast(bool, payload["transport_success"]),
                None,
                None if payload["failure"] is None else HttpExecutionFailure(cast(str, payload["failure"])),
                self._tool_call_ref(payload["tool_call_ref"], project_ref),
                receipt_ref,
                cast(str, payload["completed_at"]),
            )
        except (KeyError, TypeError, ValueError, HttpAdapterError) as exc:
            if isinstance(exc, HttpIntegrityError):
                raise
            raise HttpIntegrityError("persisted HTTP result is malformed") from exc

    def get_result(self, access: ProjectAccess, execution_ref: HttpExecutionRef) -> HttpExecutionResult:
        if not isinstance(execution_ref, HttpExecutionRef):
            raise HttpContractError("exact HttpExecutionRef is required")
        self._authorize(access, execution_ref.project_ref)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM http_execution_results WHERE project_id=? AND execution_id=?",
                (access.project_ref.value, execution_ref.execution_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise HttpNotFoundError("HTTP execution result is unavailable")
        try:
            result = self._result_from_payload(json.loads(cast(str, row["result_json"])), access.project_ref)
        except json.JSONDecodeError as exc:
            raise HttpIntegrityError("HTTP result JSON is malformed") from exc
        if result.execution_ref != execution_ref or not hmac.compare_digest(cast(str, row["record_sha256"]), result.record_sha256):
            raise HttpIntegrityError("HTTP result evidence changed")
        call = self.calls.get_tool_call(access, result.tool_call_ref)
        expected_status = "SUCCEEDED" if result.transport_success else "FAILED"
        if call.status != expected_status:
            raise HttpIntegrityError("HTTP result and ToolCall status differ")
        receipt = self.artifacts.get_artifact(access, result.receipt_artifact_ref)
        if receipt.content_ref is None:
            raise HttpIntegrityError("HTTP receipt Artifact lacks content")
        receipt_refs = {receipt.content_ref, result.receipt_artifact_ref}
        if result.transport_success:
            expected_outputs = set(receipt_refs)
            if result.response_ref is not None:
                expected_outputs.add(result.response_ref)
            if result.response_artifact_ref is not None:
                expected_outputs.add(result.response_artifact_ref)
            if set(call.output_refs) != expected_outputs or call.failure_evidence_refs:
                raise HttpIntegrityError("HTTP result and successful ToolCall evidence differ")
        elif set(call.failure_evidence_refs) != receipt_refs or call.output_refs:
            raise HttpIntegrityError("HTTP result and failed ToolCall evidence differ")
        try:
            manifest = json.loads(self.object_store.read(receipt.content_ref))
            if not isinstance(manifest, dict):
                raise HttpIntegrityError("HTTP receipt manifest is malformed")
            expected_manifest = dict(result.payload())
            expected_manifest.pop("tool_call_ref")
            expected_manifest.pop("receipt_artifact_ref")
            if manifest != expected_manifest:
                raise HttpIntegrityError("HTTP result and receipt manifest differ")
            self.object_store.verify(receipt.content_ref)
            if result.response_ref is not None:
                self.object_store.verify(result.response_ref)
        except (ObjectStorageError, json.JSONDecodeError) as exc:
            raise HttpIntegrityError("HTTP ContentRef evidence failed verification") from exc
        if result.response_artifact_ref is not None:
            response_artifact = self.artifacts.get_artifact(access, result.response_artifact_ref)
            if response_artifact.content_ref != result.response_ref:
                raise HttpIntegrityError("HTTP response Artifact and ContentRef differ")
        return result
