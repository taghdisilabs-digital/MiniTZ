"""Provider-neutral, Project-scoped ModelCall and ToolCall accounting."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from typing import TypeAlias, cast
from uuid import uuid4

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .capability import CapabilityRef
from .event import Event, EventError, EventLedger, EventRef
from .execution import (
    NodeExecutionAttempt,
    NodeExecutionAuthorityError,
    NodeExecutionError,
    NodeExecutionService,
)
from .graph import Graph, GraphError, GraphRef, Node, NodeRef
from .project import ProjectAccess, ProjectError, ProjectRef, ProjectScopeError, ProjectStore
from .run import RunError, RunRef
from .task import TaskError, TaskRef


_MODEL_CALL_ID = re.compile(r"mcall_[0-9a-f]{32}")
_TOOL_CALL_ID = re.compile(r"tcall_[0-9a-f]{32}")
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_CATEGORY = re.compile(r"[A-Z][A-Z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CURRENCY = re.compile(r"[A-Z]{3}")
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?")
_PURPOSES = {"INITIAL", "INTENTIONAL_REPEAT", "INFRASTRUCTURE_RETRY", "REPAIR_REPLAN"}
_TERMINAL = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}
_USAGE_SOURCES = {"PROVIDER_REPORTED", "ADAPTER_DERIVED"}
_SECRET_PATTERNS = (
    re.compile(
        r"(?:authorization\s*:|bearer\s+|api[_-]?key|client[_-]?secret|"
        r"access[_-]?token|refresh[_-]?token|sk-[A-Za-z0-9_-]{4,})",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?:^|[?&;,\s])(?:access[_-]?key|token|password|credential|"
        r"private[_-]?key|secret)"
        r"\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
)


class CallError(Exception):
    """Base class for durable call-ledger failures."""


class CallContractError(CallError, ValueError):
    """A call contract or request is malformed."""


class CallScopeError(CallError):
    """A call operation crossed exact Project scope."""


class CallAuthorityError(CallError, PermissionError):
    """A call operation lacks live Node execution authority."""


class CallNotFoundError(CallError):
    """The exact call does not exist."""


class CallConflictError(CallError):
    """A call request conflicts with immutable durable state."""


class CallIntegrityError(CallError):
    """Durable call evidence failed verification."""


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _validate_timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise CallContractError(f"{name} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CallContractError(f"{name} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CallContractError(f"{name} must be timezone-aware")
    return value


def _validate_key(value: object, name: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise CallContractError(f"{name} is malformed")
    _reject_secret(value, name)
    return value


def _validate_ref(value: object, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or _ABSOLUTE_REF.fullmatch(value) is None:
        raise CallContractError(f"{name} must be an exact provider-neutral reference")
    _reject_secret(value, name)
    return value


def _reject_secret(value: str, name: str) -> None:
    if any(pattern.search(value) is not None for pattern in _SECRET_PATTERNS):
        raise CallContractError(f"{name} contains credential-like material")


CallObjectRef: TypeAlias = ArtifactRef | ContentRef


def _freeze_objects(
    values: Sequence[CallObjectRef],
    project_ref: ProjectRef,
    name: str,
) -> tuple[CallObjectRef, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise CallContractError(f"{name} must be a sequence of exact refs")
    copied = tuple(values)
    if len(copied) > 128 or not all(
        isinstance(item, (ArtifactRef, ContentRef)) for item in copied
    ):
        raise CallContractError(f"{name} is malformed or unbounded")
    if any(
        isinstance(item, ArtifactRef) and item.project_ref != project_ref
        for item in copied
    ):
        raise CallScopeError(f"{name} crossed Project scope")
    if len({item.value for item in copied}) != len(copied):
        raise CallContractError(f"{name} contains duplicates")
    for item in copied:
        if isinstance(item, ContentRef):
            _reject_secret(item.media_type, f"{name} media_type")
    return tuple(sorted(copied, key=lambda item: item.value))


@dataclass(frozen=True, order=True)
class ModelCallRef:
    project_ref: ProjectRef
    call_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise CallContractError("ModelCallRef requires ProjectRef")
        if not isinstance(self.call_id, str) or _MODEL_CALL_ID.fullmatch(self.call_id) is None:
            raise CallContractError("ModelCall identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> ModelCallRef:
        return cls(project_ref, f"mcall_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"model-call://{self.project_ref.value}/{self.call_id}"


@dataclass(frozen=True, order=True)
class ToolCallRef:
    project_ref: ProjectRef
    call_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise CallContractError("ToolCallRef requires ProjectRef")
        if not isinstance(self.call_id, str) or _TOOL_CALL_ID.fullmatch(self.call_id) is None:
            raise CallContractError("ToolCall identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> ToolCallRef:
        return cls(project_ref, f"tcall_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"tool-call://{self.project_ref.value}/{self.call_id}"


@dataclass(frozen=True, order=True)
class UsageMetric:
    value: int | None
    source: str | None

    def __post_init__(self) -> None:
        if (self.value is None) != (self.source is None):
            raise CallContractError("usage value and source must both be known or unknown")
        if self.value is not None and (
            not isinstance(self.value, int)
            or isinstance(self.value, bool)
            or self.value < 0
        ):
            raise CallContractError("usage value must be a non-negative integer")
        if self.source is not None and self.source not in _USAGE_SOURCES:
            raise CallContractError("usage measurement source is unsupported")

    def payload(self) -> dict[str, object]:
        return {"source": self.source, "value": self.value}


@dataclass(frozen=True)
class CallUsage:
    input_tokens: UsageMetric
    output_tokens: UsageMetric
    reasoning_tokens: UsageMetric
    cached_input_tokens: UsageMetric
    cache_write_tokens: UsageMetric

    def __post_init__(self) -> None:
        if not all(isinstance(item, UsageMetric) for item in self.metrics):
            raise CallContractError("CallUsage fields require UsageMetric")

    @classmethod
    def unknown(cls) -> CallUsage:
        unknown = UsageMetric(None, None)
        return cls(unknown, unknown, unknown, unknown, unknown)

    @property
    def metrics(self) -> tuple[UsageMetric, ...]:
        return (
            self.input_tokens,
            self.output_tokens,
            self.reasoning_tokens,
            self.cached_input_tokens,
            self.cache_write_tokens,
        )

    def payload(self) -> dict[str, object]:
        return {
            "cache_write_tokens": self.cache_write_tokens.payload(),
            "cached_input_tokens": self.cached_input_tokens.payload(),
            "input_tokens": self.input_tokens.payload(),
            "output_tokens": self.output_tokens.payload(),
            "reasoning_tokens": self.reasoning_tokens.payload(),
        }


@dataclass(frozen=True, order=True)
class CallCost:
    amount_decimal: str
    currency: str
    source: str
    pricing_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_decimal, str) or _AMOUNT.fullmatch(self.amount_decimal) is None:
            raise CallContractError("cost amount must be an exact non-negative decimal")
        try:
            amount = Decimal(self.amount_decimal)
        except InvalidOperation as exc:
            raise CallContractError("cost amount is malformed") from exc
        if not amount.is_finite() or amount < 0:
            raise CallContractError("cost amount must be finite and non-negative")
        if not isinstance(self.currency, str) or _CURRENCY.fullmatch(self.currency) is None:
            raise CallContractError("cost currency is malformed")
        if self.source not in _USAGE_SOURCES:
            raise CallContractError("cost measurement source is unsupported")
        _validate_ref(self.pricing_identity, "pricing_identity")

    def payload(self) -> dict[str, object]:
        return {
            "amount_decimal": self.amount_decimal,
            "currency": self.currency,
            "pricing_identity": self.pricing_identity,
            "source": self.source,
        }


@dataclass(frozen=True)
class CallState:
    call_id: str
    version: int
    status: str
    output_refs: tuple[CallObjectRef, ...]
    failure_evidence_refs: tuple[CallObjectRef, ...]
    usage: CallUsage | None
    cost: CallCost | None
    failure_category: str | None
    failure_reason: str | None
    idempotency_key: str
    request_sha256: str
    recorded_at: str
    completed_at: str | None
    status_event_ref: EventRef
    status_event_record_sha256: str
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise CallContractError("call state version must be positive")
        if self.status != "RUNNING" and self.status not in _TERMINAL:
            raise CallContractError("call status is malformed")
        if not isinstance(self.output_refs, tuple) or not isinstance(
            self.failure_evidence_refs,
            tuple,
        ):
            raise CallContractError("call state refs must be tuples")
        if self.usage is not None and not isinstance(self.usage, CallUsage):
            raise CallContractError("usage must be CallUsage or unknown")
        if self.cost is not None and not isinstance(self.cost, CallCost):
            raise CallContractError("cost must be CallCost or unknown")
        _validate_key(self.idempotency_key, "idempotency_key")
        if not isinstance(self.request_sha256, str) or _SHA256.fullmatch(self.request_sha256) is None:
            raise CallIntegrityError("call state request digest is malformed")
        _validate_timestamp(self.recorded_at, "recorded_at")
        if not isinstance(self.status_event_ref, EventRef):
            raise CallIntegrityError("call state EventRef is malformed")
        if (
            not isinstance(self.status_event_record_sha256, str)
            or _SHA256.fullmatch(self.status_event_record_sha256) is None
        ):
            raise CallIntegrityError("call state Event digest is malformed")
        if self.status == "RUNNING":
            if (
                self.version != 1
                or self.output_refs
                or self.failure_evidence_refs
                or self.usage is not None
                or self.cost is not None
                or self.failure_category is not None
                or self.failure_reason is not None
                or self.completed_at is not None
            ):
                raise CallContractError("running call state contains terminal evidence")
        else:
            _validate_timestamp(self.completed_at, "completed_at")
            if self.version != 2:
                raise CallContractError("terminal call state must be version two")
            if self.status == "SUCCEEDED":
                if self.failure_category is not None or self.failure_reason is not None:
                    raise CallContractError("successful call cannot contain failure")
            elif (
                not isinstance(self.failure_category, str)
                or _CATEGORY.fullmatch(self.failure_category) is None
                or not isinstance(self.failure_reason, str)
                or not self.failure_reason
                or len(self.failure_reason.encode()) > 2048
            ):
                raise CallContractError("terminal failure evidence is malformed")
            if self.failure_category is not None:
                _reject_secret(self.failure_category, "failure_category")
            if self.failure_reason is not None:
                _reject_secret(self.failure_reason, "failure_reason")
        semantic = _sha256(self.payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256({"recorded_at": self.recorded_at, "semantic_digest": semantic}),
        )

    def payload(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "completed_at": self.completed_at,
            "cost": None if self.cost is None else self.cost.payload(),
            "failure_category": self.failure_category,
            "failure_evidence_refs": [item.value for item in self.failure_evidence_refs],
            "failure_reason": self.failure_reason,
            "idempotency_key": self.idempotency_key,
            "output_refs": [item.value for item in self.output_refs],
            "request_sha256": self.request_sha256,
            "status": self.status,
            "status_event_record_sha256": self.status_event_record_sha256,
            "status_event_ref": self.status_event_ref.value,
            "usage": None if self.usage is None else self.usage.payload(),
            "version": self.version,
        }


def _common_call_payload(
    call_ref: ModelCallRef | ToolCallRef,
    attempt: NodeExecutionAttempt,
    capability_ref: CapabilityRef,
    purpose: str,
    retry_of: ModelCallRef | ToolCallRef | None,
    runtime_id: str,
    input_refs: tuple[CallObjectRef, ...],
    input_provenance_sha256: str,
    provider_trace_id: str | None,
    event_ref: EventRef,
    event_record_sha256: str,
) -> dict[str, object]:
    return {
        "call_ref": call_ref.value,
        "capability_ref": capability_ref.value,
        "event_record_sha256": event_record_sha256,
        "event_ref": event_ref.value,
        "input_provenance_sha256": input_provenance_sha256,
        "input_refs": [item.value for item in input_refs],
        "node_attempt_record_sha256": attempt.record_sha256,
        "purpose": purpose,
        "provider_trace_id": provider_trace_id,
        "retry_of": None if retry_of is None else retry_of.value,
        "runtime_id": runtime_id,
    }


@dataclass(frozen=True)
class ModelCall:
    call_ref: ModelCallRef
    attempt: NodeExecutionAttempt
    capability_ref: CapabilityRef
    purpose: str
    retry_of: ModelCallRef | None
    provider_id: str
    model_id: str
    deployment_id: str | None
    runtime_id: str
    input_refs: tuple[CallObjectRef, ...]
    input_provenance_sha256: str
    provider_trace_id: str | None
    event_ref: EventRef
    event_record_sha256: str
    created_at: str
    state: CallState
    identity_sha256: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.call_ref, ModelCallRef):
            raise CallContractError("ModelCallRef is required")
        _validate_call_common(self)
        for value, name in (
            (self.provider_id, "provider_id"),
            (self.model_id, "model_id"),
            (self.deployment_id, "deployment_id"),
        ):
            _validate_ref(value, name, optional=name == "deployment_id")
        payload = _common_call_payload(
            self.call_ref,
            self.attempt,
            self.capability_ref,
            self.purpose,
            self.retry_of,
            self.runtime_id,
            self.input_refs,
            self.input_provenance_sha256,
            self.provider_trace_id,
            self.event_ref,
            self.event_record_sha256,
        )
        payload.update(
            {
                "deployment_id": self.deployment_id,
                "kind": "MODEL",
                "model_id": self.model_id,
                "provider_id": self.provider_id,
            }
        )
        identity = _sha256(payload)
        object.__setattr__(self, "identity_sha256", identity)
        object.__setattr__(self, "record_sha256", _sha256({"created_at": self.created_at, "identity_sha256": identity}))

    @property
    def project_ref(self) -> ProjectRef:
        return self.call_ref.project_ref

    @property
    def model_call_id(self) -> str:
        return self.call_ref.call_id

    @property
    def task_ref(self) -> TaskRef:
        return self.attempt.task_ref

    @property
    def run_ref(self) -> RunRef:
        return self.attempt.run_ref

    @property
    def graph_ref(self) -> GraphRef:
        return self.attempt.node_ref.graph_ref

    @property
    def node_ref(self) -> NodeRef:
        return self.attempt.node_ref

    @property
    def node_attempt_id(self) -> str:
        return self.attempt.attempt_id

    @property
    def node_fence(self) -> int:
        return self.attempt.fence

    @property
    def run_attempt_id(self) -> str:
        return self.attempt.run_attempt_id

    @property
    def run_fence(self) -> int:
        return self.attempt.run_fence

    @property
    def status(self) -> str:
        return self.state.status

    @property
    def output_refs(self) -> tuple[CallObjectRef, ...]:
        return self.state.output_refs

    @property
    def usage(self) -> CallUsage | None:
        return self.state.usage

    @property
    def cost(self) -> CallCost | None:
        return self.state.cost

    @property
    def completed_at(self) -> str | None:
        return self.state.completed_at

    @property
    def failure_category(self) -> str | None:
        return self.state.failure_category

    @property
    def failure_reason(self) -> str | None:
        return self.state.failure_reason

    @property
    def failure_evidence_refs(self) -> tuple[CallObjectRef, ...]:
        return self.state.failure_evidence_refs


@dataclass(frozen=True)
class ToolCall:
    call_ref: ToolCallRef
    attempt: NodeExecutionAttempt
    capability_ref: CapabilityRef
    purpose: str
    retry_of: ToolCallRef | None
    parent_model_call_ref: ModelCallRef | None
    tool_id: str
    implementation_id: str
    runtime_id: str
    input_refs: tuple[CallObjectRef, ...]
    input_provenance_sha256: str
    provider_trace_id: str | None
    event_ref: EventRef
    event_record_sha256: str
    created_at: str
    state: CallState
    identity_sha256: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.call_ref, ToolCallRef):
            raise CallContractError("ToolCallRef is required")
        _validate_call_common(self)
        _validate_ref(self.tool_id, "tool_id")
        _validate_ref(self.implementation_id, "implementation_id")
        if self.parent_model_call_ref is not None and (
            not isinstance(self.parent_model_call_ref, ModelCallRef)
            or self.parent_model_call_ref.project_ref != self.call_ref.project_ref
        ):
            raise CallScopeError("ToolCall parent crossed Project scope")
        payload = _common_call_payload(
            self.call_ref,
            self.attempt,
            self.capability_ref,
            self.purpose,
            self.retry_of,
            self.runtime_id,
            self.input_refs,
            self.input_provenance_sha256,
            self.provider_trace_id,
            self.event_ref,
            self.event_record_sha256,
        )
        payload.update(
            {
                "implementation_id": self.implementation_id,
                "kind": "TOOL",
                "parent_model_call_ref": None if self.parent_model_call_ref is None else self.parent_model_call_ref.value,
                "tool_id": self.tool_id,
            }
        )
        identity = _sha256(payload)
        object.__setattr__(self, "identity_sha256", identity)
        object.__setattr__(self, "record_sha256", _sha256({"created_at": self.created_at, "identity_sha256": identity}))

    @property
    def project_ref(self) -> ProjectRef:
        return self.call_ref.project_ref

    @property
    def tool_call_id(self) -> str:
        return self.call_ref.call_id

    @property
    def task_ref(self) -> TaskRef:
        return self.attempt.task_ref

    @property
    def run_ref(self) -> RunRef:
        return self.attempt.run_ref

    @property
    def graph_ref(self) -> GraphRef:
        return self.attempt.node_ref.graph_ref

    @property
    def node_ref(self) -> NodeRef:
        return self.attempt.node_ref

    @property
    def status(self) -> str:
        return self.state.status

    @property
    def node_attempt_id(self) -> str:
        return self.attempt.attempt_id

    @property
    def node_fence(self) -> int:
        return self.attempt.fence

    @property
    def run_attempt_id(self) -> str:
        return self.attempt.run_attempt_id

    @property
    def run_fence(self) -> int:
        return self.attempt.run_fence

    @property
    def output_refs(self) -> tuple[CallObjectRef, ...]:
        return self.state.output_refs

    @property
    def usage(self) -> CallUsage | None:
        return self.state.usage

    @property
    def cost(self) -> CallCost | None:
        return self.state.cost

    @property
    def completed_at(self) -> str | None:
        return self.state.completed_at

    @property
    def failure_category(self) -> str | None:
        return self.state.failure_category

    @property
    def failure_reason(self) -> str | None:
        return self.state.failure_reason

    @property
    def failure_evidence_refs(self) -> tuple[CallObjectRef, ...]:
        return self.state.failure_evidence_refs


CallRecord: TypeAlias = ModelCall | ToolCall


def _validate_call_common(call: ModelCall | ToolCall) -> None:
    if not isinstance(call.attempt, NodeExecutionAttempt):
        raise CallContractError("NodeExecutionAttempt is required")
    if call.call_ref.project_ref != call.attempt.node_ref.project_ref:
        raise CallScopeError("call and Node attempt Project differ")
    if not isinstance(call.capability_ref, CapabilityRef):
        raise CallContractError("CapabilityRef is required")
    if call.purpose not in _PURPOSES:
        raise CallContractError("call purpose is malformed")
    if (call.purpose == "INITIAL") != (call.retry_of is None):
        raise CallContractError("call purpose and predecessor differ")
    _validate_ref(call.runtime_id, "runtime_id")
    if call.provider_trace_id is not None:
        if not isinstance(call.provider_trace_id, str) or not call.provider_trace_id or len(call.provider_trace_id.encode()) > 512:
            raise CallContractError("provider trace identity is malformed")
        _reject_secret(call.provider_trace_id, "provider_trace_id")
    if not isinstance(call.event_ref, EventRef) or call.event_ref.project_ref != call.call_ref.project_ref:
        raise CallScopeError("call Event crossed Project scope")
    for digest, name in (
        (call.input_provenance_sha256, "input_provenance_sha256"),
        (call.event_record_sha256, "event_record_sha256"),
    ):
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise CallIntegrityError(f"{name} is malformed")
    _validate_timestamp(call.created_at, "created_at")
    if not isinstance(call.state, CallState) or call.state.call_id != call.call_ref.call_id:
        raise CallIntegrityError("call state identity differs")
    if call.state.status_event_ref.project_ref != call.call_ref.project_ref:
        raise CallScopeError("call state Event crossed Project scope")


def _content_payload(content_ref: ContentRef) -> dict[str, object]:
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _head_sha256(call_ref: ModelCallRef | ToolCallRef, state: CallState) -> str:
    return _sha256(
        {
            "call_ref": call_ref.value,
            "current_record_sha256": state.record_sha256,
            "current_version": state.version,
            "updated_at": state.recorded_at,
        }
    )


class CallLedgerService:
    """Append-only provider-neutral accounting for exact model and tool calls."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.events = EventLedger(self.database_path)
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
                CREATE UNIQUE INDEX IF NOT EXISTS events_exact_call_event_ref
                    ON events(project_id, event_id, record_sha256);
                CREATE UNIQUE INDEX IF NOT EXISTS node_attempts_exact_call_authority
                    ON node_execution_attempts(
                        project_id, graph_id, graph_revision, node_id,
                        attempt_id, record_sha256
                    );

                CREATE TABLE IF NOT EXISTS calls (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    call_kind TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    node_record_sha256 TEXT NOT NULL,
                    node_attempt_id TEXT NOT NULL,
                    node_attempt_record_sha256 TEXT NOT NULL,
                    node_attempt_number INTEGER NOT NULL,
                    node_fence INTEGER NOT NULL,
                    node_owner_ref TEXT NOT NULL,
                    run_attempt_id TEXT NOT NULL,
                    run_fence INTEGER NOT NULL,
                    capability_id TEXT NOT NULL,
                    capability_version TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    retry_call_id TEXT,
                    parent_model_call_id TEXT,
                    provider_id TEXT,
                    model_id TEXT,
                    deployment_id TEXT,
                    tool_id TEXT,
                    implementation_id TEXT,
                    runtime_id TEXT NOT NULL,
                    provider_trace_id TEXT,
                    event_id TEXT NOT NULL,
                    event_record_sha256 TEXT NOT NULL,
                    input_provenance_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    start_idempotency_key TEXT NOT NULL,
                    start_request_sha256 TEXT NOT NULL,
                    identity_sha256 TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, call_id),
                    UNIQUE (project_id, call_id, record_sha256),
                    UNIQUE (
                        project_id, graph_id, graph_revision, node_id,
                        node_attempt_id, start_idempotency_key
                    ),
                    UNIQUE (project_id, event_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(
                            project_id, task_id, revision, canonical_digest
                        ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id)
                        REFERENCES runs(project_id, run_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, graph_id, graph_revision,
                        node_id, node_record_sha256
                    ) REFERENCES graph_nodes(
                        project_id, graph_id, graph_revision,
                        node_id, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, graph_id, graph_revision, node_id,
                        node_attempt_id, node_attempt_record_sha256
                    ) REFERENCES node_execution_attempts(
                        project_id, graph_id, graph_revision, node_id,
                        attempt_id, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, event_id, event_record_sha256)
                        REFERENCES events(project_id, event_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, retry_call_id)
                        REFERENCES calls(project_id, call_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, parent_model_call_id)
                        REFERENCES calls(project_id, call_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    CHECK (call_kind IN ('MODEL', 'TOOL')),
                    CHECK (
                        (call_kind = 'MODEL' AND provider_id IS NOT NULL
                            AND model_id IS NOT NULL AND tool_id IS NULL
                            AND implementation_id IS NULL
                            AND parent_model_call_id IS NULL)
                        OR
                        (call_kind = 'TOOL' AND provider_id IS NULL
                            AND model_id IS NULL AND deployment_id IS NULL
                            AND tool_id IS NOT NULL
                            AND implementation_id IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS call_objects (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    binding_kind TEXT NOT NULL,
                    object_ref TEXT NOT NULL,
                    object_kind TEXT NOT NULL,
                    content_ref_json TEXT,
                    artifact_id TEXT,
                    artifact_revision INTEGER,
                    artifact_record_sha256 TEXT,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, call_id, binding_kind, object_ref),
                    FOREIGN KEY (project_id, call_id)
                        REFERENCES calls(project_id, call_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, artifact_id,
                        artifact_revision, artifact_record_sha256
                    ) REFERENCES artifact_revisions(
                        project_id, artifact_id, revision, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    CHECK (binding_kind IN ('INPUT', 'OUTPUT', 'FAILURE')),
                    CHECK (
                        (object_kind = 'content' AND content_ref_json IS NOT NULL
                            AND artifact_id IS NULL AND artifact_revision IS NULL
                            AND artifact_record_sha256 IS NULL)
                        OR
                        (object_kind = 'artifact' AND content_ref_json IS NULL
                            AND artifact_id IS NOT NULL
                            AND artifact_revision IS NOT NULL
                            AND artifact_record_sha256 IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS call_status_versions (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    usage_json TEXT,
                    cost_json TEXT,
                    failure_category TEXT,
                    failure_reason TEXT,
                    idempotency_key TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    completed_at TEXT,
                    status_event_id TEXT NOT NULL,
                    status_event_record_sha256 TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, call_id, state_version),
                    UNIQUE (project_id, call_id, state_version, record_sha256),
                    UNIQUE (project_id, call_id, idempotency_key),
                    FOREIGN KEY (project_id, call_id)
                        REFERENCES calls(project_id, call_id)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (
                        project_id, status_event_id, status_event_record_sha256
                    ) REFERENCES events(project_id, event_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    CHECK (
                        (state_version = 1 AND status = 'RUNNING'
                            AND completed_at IS NULL)
                        OR
                        (state_version = 2
                            AND status IN ('SUCCEEDED', 'FAILED', 'TIMED_OUT', 'CANCELLED')
                            AND completed_at IS NOT NULL)
                    )
                );

                CREATE TABLE IF NOT EXISTS call_status_heads (
                    project_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    current_record_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, call_id),
                    FOREIGN KEY (
                        project_id, call_id,
                        current_version, current_record_sha256
                    ) REFERENCES call_status_versions(
                        project_id, call_id, state_version, record_sha256
                    ) ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS calls_no_update BEFORE UPDATE ON calls
                BEGIN SELECT RAISE(ABORT, 'Calls are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS calls_no_delete BEFORE DELETE ON calls
                BEGIN SELECT RAISE(ABORT, 'Calls cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS call_objects_no_update BEFORE UPDATE ON call_objects
                BEGIN SELECT RAISE(ABORT, 'Call objects are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS call_objects_no_delete BEFORE DELETE ON call_objects
                BEGIN SELECT RAISE(ABORT, 'Call objects cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS call_status_versions_no_update BEFORE UPDATE ON call_status_versions
                BEGIN SELECT RAISE(ABORT, 'Call states are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS call_status_versions_no_delete BEFORE DELETE ON call_status_versions
                BEGIN SELECT RAISE(ABORT, 'Call states cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS call_status_heads_no_delete BEFORE DELETE ON call_status_heads
                BEGIN SELECT RAISE(ABORT, 'Call state heads cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS call_status_heads_monotonic
                BEFORE UPDATE ON call_status_heads
                WHEN NEW.current_version != OLD.current_version + 1
                  OR NEW.current_version != 2
                  OR NEW.project_id != OLD.project_id
                  OR NEW.call_id != OLD.call_id
                BEGIN SELECT RAISE(ABORT, 'Call state head must advance once to terminal'); END;
                """
            )
        finally:
            connection.close()

    def start_model_call(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        idempotency_key: str,
        capability_ref: CapabilityRef,
        purpose: str,
        retry_of: ModelCallRef | None,
        provider_id: str,
        model_id: str,
        deployment_id: str | None,
        runtime_id: str,
        input_refs: Sequence[CallObjectRef],
        provider_trace_id: str | None,
    ) -> ModelCall:
        return cast(
            ModelCall,
            self._start_call(
                requesting_access,
                attempt,
                call_kind="MODEL",
                idempotency_key=idempotency_key,
                capability_ref=capability_ref,
                purpose=purpose,
                retry_of=retry_of,
                parent_model_call_ref=None,
                provider_id=provider_id,
                model_id=model_id,
                deployment_id=deployment_id,
                tool_id=None,
                implementation_id=None,
                runtime_id=runtime_id,
                input_refs=input_refs,
                provider_trace_id=provider_trace_id,
            ),
        )

    def start_tool_call(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        idempotency_key: str,
        capability_ref: CapabilityRef,
        purpose: str,
        retry_of: ToolCallRef | None,
        parent_model_call_ref: ModelCallRef | None,
        tool_id: str,
        implementation_id: str,
        runtime_id: str,
        input_refs: Sequence[CallObjectRef],
        provider_trace_id: str | None,
    ) -> ToolCall:
        return cast(
            ToolCall,
            self._start_call(
                requesting_access,
                attempt,
                call_kind="TOOL",
                idempotency_key=idempotency_key,
                capability_ref=capability_ref,
                purpose=purpose,
                retry_of=retry_of,
                parent_model_call_ref=parent_model_call_ref,
                provider_id=None,
                model_id=None,
                deployment_id=None,
                tool_id=tool_id,
                implementation_id=implementation_id,
                runtime_id=runtime_id,
                input_refs=input_refs,
                provider_trace_id=provider_trace_id,
            ),
        )

    def finish_model_call(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        call_ref: ModelCallRef,
        *,
        idempotency_key: str,
        status: str,
        output_refs: Sequence[CallObjectRef],
        usage: CallUsage | None,
        cost: CallCost | None,
        failure_category: str | None,
        failure_reason: str | None,
        failure_evidence_refs: Sequence[CallObjectRef],
    ) -> ModelCall:
        return cast(
            ModelCall,
            self._finish_call(
                requesting_access,
                attempt,
                call_ref,
                idempotency_key=idempotency_key,
                status=status,
                output_refs=output_refs,
                usage=usage,
                cost=cost,
                failure_category=failure_category,
                failure_reason=failure_reason,
                failure_evidence_refs=failure_evidence_refs,
            ),
        )

    def finish_tool_call(
        self,
        requesting_access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        call_ref: ToolCallRef,
        *,
        idempotency_key: str,
        status: str,
        output_refs: Sequence[CallObjectRef],
        usage: CallUsage | None,
        cost: CallCost | None,
        failure_category: str | None,
        failure_reason: str | None,
        failure_evidence_refs: Sequence[CallObjectRef],
    ) -> ToolCall:
        return cast(
            ToolCall,
            self._finish_call(
                requesting_access,
                attempt,
                call_ref,
                idempotency_key=idempotency_key,
                status=status,
                output_refs=output_refs,
                usage=usage,
                cost=cost,
                failure_category=failure_category,
                failure_reason=failure_reason,
                failure_evidence_refs=failure_evidence_refs,
            ),
        )

    def get_model_call(
        self,
        requesting_access: ProjectAccess,
        call_ref: ModelCallRef,
    ) -> ModelCall:
        return cast(ModelCall, self._get_call(requesting_access, call_ref, "MODEL"))

    def get_tool_call(
        self,
        requesting_access: ProjectAccess,
        call_ref: ToolCallRef,
    ) -> ToolCall:
        return cast(ToolCall, self._get_call(requesting_access, call_ref, "TOOL"))

    def get_execution_dimensions(
        self,
        requesting_access: ProjectAccess,
        call_ref: ModelCallRef | ToolCallRef,
    ) -> Mapping[str, str]:
        """Return provider-neutral dimensions for provenance and independence checks."""
        if isinstance(call_ref, ModelCallRef):
            model_call = self.get_model_call(requesting_access, call_ref)
            dimensions = {
                "implementation": f"model://{model_call.provider_id}/{model_call.model_id}",
                "model": model_call.model_id,
                "provider": model_call.provider_id,
                "runtime": model_call.runtime_id,
                "strategy": f"capability://{model_call.capability_ref.capability_id}/{model_call.capability_ref.version}",
            }
            if model_call.deployment_id is not None:
                dimensions["deployment"] = model_call.deployment_id
            return dimensions
        if isinstance(call_ref, ToolCallRef):
            tool_call = self.get_tool_call(requesting_access, call_ref)
            return {
                "implementation": tool_call.implementation_id,
                "runtime": tool_call.runtime_id,
                "strategy": f"capability://{tool_call.capability_ref.capability_id}/{tool_call.capability_ref.version}",
                "tool": tool_call.tool_id,
            }
        raise TypeError("call_ref must be ModelCallRef or ToolCallRef")

    def get_model_call_for_event(
        self,
        requesting_access: ProjectAccess,
        event_ref: EventRef,
    ) -> ModelCall:
        return cast(
            ModelCall,
            self._get_call_for_event(requesting_access, event_ref, "MODEL"),
        )

    def get_tool_call_for_event(
        self,
        requesting_access: ProjectAccess,
        event_ref: EventRef,
    ) -> ToolCall:
        return cast(
            ToolCall,
            self._get_call_for_event(requesting_access, event_ref, "TOOL"),
        )

    def _start_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        *,
        call_kind: str,
        idempotency_key: str,
        capability_ref: CapabilityRef,
        purpose: str,
        retry_of: ModelCallRef | ToolCallRef | None,
        parent_model_call_ref: ModelCallRef | None,
        provider_id: str | None,
        model_id: str | None,
        deployment_id: str | None,
        tool_id: str | None,
        implementation_id: str | None,
        runtime_id: str,
        input_refs: Sequence[CallObjectRef],
        provider_trace_id: str | None,
    ) -> CallRecord:
        _validate_key(idempotency_key, "idempotency_key")
        if not isinstance(attempt, NodeExecutionAttempt):
            raise CallAuthorityError("NodeExecutionAttempt is required")
        if not isinstance(capability_ref, CapabilityRef):
            raise CallContractError("CapabilityRef is required")
        if purpose not in _PURPOSES:
            raise CallContractError("call purpose is malformed")
        if (purpose == "INITIAL") != (retry_of is None):
            raise CallContractError("call purpose and predecessor differ")
        if call_kind == "MODEL":
            _validate_ref(provider_id, "provider_id")
            _validate_ref(model_id, "model_id")
            _validate_ref(deployment_id, "deployment_id", optional=True)
            if not isinstance(retry_of, (ModelCallRef, type(None))):
                raise CallContractError("ModelCall retry predecessor has wrong kind")
        elif call_kind == "TOOL":
            _validate_ref(tool_id, "tool_id")
            _validate_ref(implementation_id, "implementation_id")
            if not isinstance(retry_of, (ToolCallRef, type(None))):
                raise CallContractError("ToolCall retry predecessor has wrong kind")
        else:
            raise CallContractError("call kind is malformed")
        _validate_ref(runtime_id, "runtime_id")
        if provider_trace_id is not None:
            if not isinstance(provider_trace_id, str) or not provider_trace_id or len(provider_trace_id.encode()) > 512:
                raise CallContractError("provider trace identity is malformed")
            _reject_secret(provider_trace_id, "provider_trace_id")
        if retry_of is not None and retry_of.project_ref != attempt.node_ref.project_ref:
            raise CallScopeError("Call retry predecessor crossed Project scope")
        if (
            parent_model_call_ref is not None
            and parent_model_call_ref.project_ref != attempt.node_ref.project_ref
        ):
            raise CallScopeError("Tool parent crossed Project scope")
        inputs = _freeze_objects(input_refs, attempt.node_ref.project_ref, "input_refs")
        request = {
            "attempt_record_sha256": attempt.record_sha256,
            "call_kind": call_kind,
            "capability_ref": capability_ref.value,
            "deployment_id": deployment_id,
            "implementation_id": implementation_id,
            "input_refs": [self._object_request_payload(item) for item in inputs],
            "model_id": model_id,
            "parent_model_call_ref": None if parent_model_call_ref is None else parent_model_call_ref.value,
            "provider_id": provider_id,
            "provider_trace_id": provider_trace_id,
            "purpose": purpose,
            "retry_of": None if retry_of is None else retry_of.value,
            "runtime_id": runtime_id,
            "tool_id": tool_id,
        }
        request_sha256 = _sha256(request)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize_in_transaction(connection, access, attempt.node_ref.project_ref)
            prior_row = connection.execute(
                """
                SELECT * FROM calls
                WHERE project_id = ? AND graph_id = ? AND graph_revision = ?
                  AND node_id = ? AND node_attempt_id = ?
                  AND start_idempotency_key = ?
                """,
                (
                    attempt.node_ref.project_ref.value,
                    attempt.node_ref.graph_ref.graph_id,
                    attempt.node_ref.graph_ref.revision,
                    attempt.node_ref.node_id,
                    attempt.attempt_id,
                    idempotency_key,
                ),
            ).fetchone()
            if prior_row is not None:
                prior = self._call_from_row(connection, cast(sqlite3.Row, prior_row))
                if prior_row["start_request_sha256"] != request_sha256:
                    raise CallConflictError("Call idempotency key has conflicting semantics")
                connection.commit()
                return prior
            try:
                _, run, task, graph = self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise CallAuthorityError("Call requires current live Node authority") from exc
            node = next(
                (item for item in graph.nodes if item.node_ref == attempt.node_ref),
                None,
            )
            if node is None or capability_ref not in node.required_capabilities:
                raise CallAuthorityError("Call capability is not authorized by exact Node")
            evidence = self._verify_objects(connection, access, inputs)
            if retry_of is not None:
                predecessor = self._fetch_call(connection, retry_of)
                if (
                    predecessor.call_ref.project_ref != attempt.node_ref.project_ref
                    or predecessor.attempt != attempt
                    or predecessor.state.status not in _TERMINAL
                    or predecessor.capability_ref != capability_ref
                    or (call_kind == "MODEL") != isinstance(predecessor, ModelCall)
                ):
                    raise CallAuthorityError("Retry predecessor is not exact and terminal")
            if parent_model_call_ref is not None:
                parent = self._fetch_call(connection, parent_model_call_ref)
                if not isinstance(parent, ModelCall) or parent.attempt != attempt or parent.status != "RUNNING":
                    raise CallAuthorityError("Tool parent is not an active exact ModelCall")
            call_ref: ModelCallRef | ToolCallRef
            if call_kind == "MODEL":
                call_ref = ModelCallRef.new(attempt.node_ref.project_ref)
            else:
                call_ref = ToolCallRef.new(attempt.node_ref.project_ref)
            run_attempt = self.executions.runs._fetch_attempt(
                connection,
                run,
                attempt.run_attempt_id,
            )
            event = self.events.append_event_in_transaction(
                connection,
                access,
                project_ref=attempt.node_ref.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=graph.graph_ref,
                node_ref=attempt.node_ref,
                event_type=f"{call_kind}_CALL",
                idempotency_key=f"call-{_sha256({'attempt': attempt.record_sha256, 'key': idempotency_key})[:48]}",
                actor_ref=attempt.owner_ref,
                object_refs=inputs,
                metadata={
                    "call_ref": call_ref.value,
                    "capability_ref": capability_ref.value,
                    "node_attempt_id": attempt.attempt_id,
                    "node_fence": attempt.fence,
                    "request_sha256": request_sha256,
                    "run_attempt_id": attempt.run_attempt_id,
                    "run_fence": attempt.run_fence,
                    "status": "RUNNING",
                },
                payload_ref=None,
                authority_attempt=run_attempt,
            )
            input_provenance = _sha256({"objects": evidence})
            initial_state = CallState(
                call_ref.call_id,
                1,
                "RUNNING",
                (),
                (),
                None,
                None,
                None,
                None,
                idempotency_key,
                request_sha256,
                event.created_at,
                None,
                event.event_ref,
                event.record_sha256,
            )
            call = self._build_call(
                call_ref=call_ref,
                attempt=attempt,
                capability_ref=capability_ref,
                purpose=purpose,
                retry_of=retry_of,
                parent_model_call_ref=parent_model_call_ref,
                provider_id=provider_id,
                model_id=model_id,
                deployment_id=deployment_id,
                tool_id=tool_id,
                implementation_id=implementation_id,
                runtime_id=runtime_id,
                input_refs=inputs,
                input_provenance_sha256=input_provenance,
                provider_trace_id=provider_trace_id,
                event=event,
                state=initial_state,
            )
            self._insert_call(connection, call, idempotency_key, request_sha256)
            self._insert_objects(connection, call.call_ref, "INPUT", inputs, evidence)
            self._insert_state(connection, call.call_ref, initial_state)
            connection.execute(
                "INSERT INTO call_status_heads VALUES (?, ?, ?, ?, ?, ?)",
                (
                    call.project_ref.value,
                    call.call_ref.call_id,
                    1,
                    initial_state.record_sha256,
                    initial_state.recorded_at,
                    _head_sha256(call.call_ref, initial_state),
                ),
            )
            connection.commit()
            return call
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise CallConflictError("Call identity or status conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _finish_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        call_ref: ModelCallRef | ToolCallRef,
        *,
        idempotency_key: str,
        status: str,
        output_refs: Sequence[CallObjectRef],
        usage: CallUsage | None,
        cost: CallCost | None,
        failure_category: str | None,
        failure_reason: str | None,
        failure_evidence_refs: Sequence[CallObjectRef],
    ) -> CallRecord:
        _validate_key(idempotency_key, "idempotency_key")
        if not isinstance(attempt, NodeExecutionAttempt):
            raise CallAuthorityError("NodeExecutionAttempt is required")
        if not isinstance(call_ref, (ModelCallRef, ToolCallRef)):
            raise CallContractError("exact call reference is required")
        outputs = _freeze_objects(output_refs, call_ref.project_ref, "output_refs")
        failures = _freeze_objects(
            failure_evidence_refs,
            call_ref.project_ref,
            "failure_evidence_refs",
        )
        if usage is not None and not isinstance(usage, CallUsage):
            raise CallContractError("usage must be CallUsage or unknown")
        if cost is not None and not isinstance(cost, CallCost):
            raise CallContractError("cost must be CallCost or unknown")
        request = {
            "call_ref": call_ref.value,
            "cost": None if cost is None else cost.payload(),
            "failure_category": failure_category,
            "failure_evidence_refs": [self._object_request_payload(item) for item in failures],
            "failure_reason": failure_reason,
            "output_refs": [self._object_request_payload(item) for item in outputs],
            "status": status,
            "usage": None if usage is None else usage.payload(),
        }
        request_sha256 = _sha256(request)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._authorize_in_transaction(connection, access, call_ref.project_ref)
            current = self._fetch_call(connection, call_ref)
            if current.attempt != attempt:
                raise CallAuthorityError("Call belongs to another Node attempt")
            if current.status != "RUNNING":
                row = connection.execute(
                    """
                    SELECT request_sha256 FROM call_status_versions
                    WHERE project_id = ? AND call_id = ? AND idempotency_key = ?
                    """,
                    (call_ref.project_ref.value, call_ref.call_id, idempotency_key),
                ).fetchone()
                if row is not None and hmac.compare_digest(cast(str, row["request_sha256"]), request_sha256):
                    connection.commit()
                    return current
                raise CallConflictError("Terminal call cannot regress or be rewritten")
            try:
                _, run, task, graph = self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise CallAuthorityError("Call completion requires current live Node authority") from exc
            output_evidence = self._verify_objects(connection, access, outputs)
            failure_evidence = self._verify_objects(connection, access, failures)
            run_attempt = self.executions.runs._fetch_attempt(
                connection,
                run,
                attempt.run_attempt_id,
            )
            event_objects = tuple(
                sorted(
                    {item.value: item for item in (*outputs, *failures)}.values(),
                    key=lambda item: item.value,
                )
            )
            call_kind = "MODEL" if isinstance(current, ModelCall) else "TOOL"
            terminal_event = self.events.append_event_in_transaction(
                connection,
                access,
                project_ref=call_ref.project_ref,
                task_ref=task.task_ref,
                run_ref=run.run_ref,
                graph_ref=graph.graph_ref,
                node_ref=attempt.node_ref,
                event_type=f"{call_kind}_CALL_TERMINAL",
                idempotency_key=f"call-terminal-{_sha256({'call': call_ref.value, 'key': idempotency_key})[:39]}",
                actor_ref=attempt.owner_ref,
                object_refs=event_objects,
                metadata={
                    "call_ref": call_ref.value,
                    "node_attempt_id": attempt.attempt_id,
                    "node_fence": attempt.fence,
                    "request_sha256": request_sha256,
                    "run_attempt_id": attempt.run_attempt_id,
                    "run_fence": attempt.run_fence,
                    "status": status,
                },
                payload_ref=None,
                authority_attempt=run_attempt,
            )
            now = terminal_event.created_at
            terminal = CallState(
                call_ref.call_id,
                2,
                status,
                outputs,
                failures,
                usage,
                cost,
                failure_category,
                failure_reason,
                idempotency_key,
                request_sha256,
                now,
                now,
                terminal_event.event_ref,
                terminal_event.record_sha256,
            )
            self._insert_objects(connection, call_ref, "OUTPUT", outputs, output_evidence)
            self._insert_objects(connection, call_ref, "FAILURE", failures, failure_evidence)
            self._insert_state(connection, call_ref, terminal)
            updated = connection.execute(
                """
                UPDATE call_status_heads SET
                    current_version = ?, current_record_sha256 = ?,
                    updated_at = ?, record_sha256 = ?
                WHERE project_id = ? AND call_id = ?
                  AND current_version = ? AND current_record_sha256 = ?
                  AND updated_at = ? AND record_sha256 = ?
                """,
                (
                    terminal.version,
                    terminal.record_sha256,
                    terminal.recorded_at,
                    _head_sha256(call_ref, terminal),
                    call_ref.project_ref.value,
                    call_ref.call_id,
                    current.state.version,
                    current.state.record_sha256,
                    current.state.recorded_at,
                    _head_sha256(call_ref, current.state),
                ),
            )
            if updated.rowcount != 1:
                raise CallConflictError("Call state changed concurrently")
            connection.commit()
            return self._with_state(current, terminal)
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise CallConflictError("Call completion conflicts") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _get_call(
        self,
        access: ProjectAccess,
        call_ref: ModelCallRef | ToolCallRef,
        expected_kind: str,
    ) -> CallRecord:
        if not isinstance(call_ref, (ModelCallRef, ToolCallRef)):
            raise CallContractError("exact call reference is required")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize_in_transaction(connection, access, call_ref.project_ref)
            call = self._fetch_call(connection, call_ref)
            if (expected_kind == "MODEL") != isinstance(call, ModelCall):
                raise CallNotFoundError("Call kind differs")
            connection.commit()
            return call
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _get_call_for_event(
        self,
        access: ProjectAccess,
        event_ref: EventRef,
        expected_kind: str,
    ) -> CallRecord:
        if not isinstance(event_ref, EventRef):
            raise CallContractError("EventRef is required")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            self._authorize_in_transaction(connection, access, event_ref.project_ref)
            row = connection.execute(
                "SELECT * FROM calls WHERE project_id = ? AND event_id = ? AND call_kind = ?",
                (event_ref.project_ref.value, event_ref.event_id, expected_kind),
            ).fetchone()
            if row is None:
                raise CallNotFoundError("Event does not identify requested call kind")
            call = self._call_from_row(connection, cast(sqlite3.Row, row))
            connection.commit()
            return call
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch_call(
        self,
        connection: sqlite3.Connection,
        call_ref: ModelCallRef | ToolCallRef,
    ) -> CallRecord:
        row = connection.execute(
            "SELECT * FROM calls WHERE project_id = ? AND call_id = ?",
            (call_ref.project_ref.value, call_ref.call_id),
        ).fetchone()
        if row is None:
            raise CallNotFoundError("Call not found")
        call = self._call_from_row(connection, cast(sqlite3.Row, row))
        if call.call_ref != call_ref:
            raise CallNotFoundError("Call kind or identity differs")
        return call

    def _call_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        visited_call_ids: frozenset[str] = frozenset(),
    ) -> CallRecord:
        try:
            project_ref = ProjectRef(cast(str, row["project_id"]))
            call_id = cast(str, row["call_id"])
            visit_key = f"{project_ref.value}/{call_id}"
            if len(visited_call_ids) >= 256:
                raise CallIntegrityError("Call relationship graph is unbounded")
            if visit_key in visited_call_ids:
                raise CallIntegrityError("Call relationship graph contains a cycle")
            relationship_visits = visited_call_ids | {visit_key}
            graph_ref = GraphRef(
                project_ref,
                cast(str, row["graph_id"]),
                cast(int, row["graph_revision"]),
            )
            node_ref = NodeRef(graph_ref, cast(str, row["node_id"]))
            attempt = self.executions._fetch_attempt(
                connection,
                node_ref,
                cast(str, row["node_attempt_id"]),
            )
            if (
                attempt.task_ref != TaskRef(
                    project_ref,
                    cast(str, row["task_id"]),
                    cast(int, row["task_revision"]),
                )
                or attempt.task_digest != row["task_digest"]
                or attempt.run_ref != RunRef(project_ref, cast(str, row["run_id"]))
                or attempt.record_sha256 != row["node_attempt_record_sha256"]
                or attempt.attempt_number != row["node_attempt_number"]
                or attempt.fence != row["node_fence"]
                or attempt.owner_ref != row["node_owner_ref"]
                or attempt.run_attempt_id != row["run_attempt_id"]
                or attempt.run_fence != row["run_fence"]
            ):
                raise CallIntegrityError("Call execution attribution differs")
            graph = self.executions.graphs._fetch_graph(connection, graph_ref)
            node = next((item for item in graph.nodes if item.node_ref == node_ref), None)
            if node is None or node.record_sha256 != row["node_record_sha256"]:
                raise CallIntegrityError("Call exact Node evidence differs")
            capability_ref = CapabilityRef(
                cast(str, row["capability_id"]),
                cast(str, row["capability_version"]),
            )
            if capability_ref not in node.required_capabilities:
                raise CallIntegrityError("Call capability is absent from exact Node")
            kind = cast(str, row["call_kind"])
            call_ref: ModelCallRef | ToolCallRef
            if kind == "MODEL":
                call_ref = ModelCallRef(project_ref, cast(str, row["call_id"]))
            elif kind == "TOOL":
                call_ref = ToolCallRef(project_ref, cast(str, row["call_id"]))
            else:
                raise CallIntegrityError("Persisted call kind is malformed")
            run_events = self.events._fetch_verified_run_events(
                connection,
                attempt.run_ref,
            )
            event_by_id = {item.event_ref.event_id: item for item in run_events}
            inputs, input_evidence = self._objects_from_rows(connection, project_ref, cast(str, row["call_id"]), "INPUT")
            output_refs, _ = self._objects_from_rows(connection, project_ref, cast(str, row["call_id"]), "OUTPUT")
            failure_refs, _ = self._objects_from_rows(connection, project_ref, cast(str, row["call_id"]), "FAILURE")
            if not hmac.compare_digest(
                _sha256({"objects": input_evidence}),
                cast(str, row["input_provenance_sha256"]),
            ):
                raise CallIntegrityError("Call input provenance differs")
            states = self._states_from_rows(
                connection,
                project_ref,
                cast(str, row["call_id"]),
                output_refs,
                failure_refs,
                call_ref,
                kind,
                event_by_id,
                attempt,
            )
            head = connection.execute(
                "SELECT * FROM call_status_heads WHERE project_id = ? AND call_id = ?",
                (project_ref.value, cast(str, row["call_id"])),
            ).fetchone()
            if head is None or (
                head["current_version"] != states[-1].version
                or head["current_record_sha256"] != states[-1].record_sha256
                or head["updated_at"] != states[-1].recorded_at
            ):
                raise CallIntegrityError("Call state history does not match durable head")
            if not hmac.compare_digest(
                _head_sha256(call_ref, states[-1]),
                cast(str, head["record_sha256"]),
            ):
                raise CallIntegrityError("Call state head digest differs")
            event_ref = EventRef(project_ref, cast(str, row["event_id"]))
            event = event_by_id.get(event_ref.event_id)
            if event is None or (
                event.record_sha256 != row["event_record_sha256"]
                or event.event_type != f"{kind}_CALL"
                or event.task_ref != attempt.task_ref
                or event.run_ref != attempt.run_ref
                or event.graph_ref != graph_ref
                or event.node_ref != node_ref
                or event.actor_ref != attempt.owner_ref
                or event.object_refs != tuple(item.value for item in inputs)
                or event.metadata.get("call_ref") != call_ref.value
                or event.metadata.get("capability_ref") != capability_ref.value
                or event.metadata.get("node_attempt_id") != attempt.attempt_id
                or event.metadata.get("node_fence") != attempt.fence
                or event.metadata.get("request_sha256") != row["start_request_sha256"]
                or event.metadata.get("run_attempt_id") != attempt.run_attempt_id
                or event.metadata.get("run_fence") != attempt.run_fence
                or event.metadata.get("status") != "RUNNING"
                or states[0].status_event_ref != event.event_ref
                or states[0].status_event_record_sha256 != event.record_sha256
            ):
                raise CallIntegrityError("Call Event attribution differs")
            retry_call_id = cast(str | None, row["retry_call_id"])
            if kind == "MODEL":
                retry_ref: ModelCallRef | ToolCallRef | None = None if retry_call_id is None else ModelCallRef(project_ref, retry_call_id)
            else:
                retry_ref = None if retry_call_id is None else ToolCallRef(project_ref, retry_call_id)
            parent_id = cast(str | None, row["parent_model_call_id"])
            parent_ref = None if parent_id is None else ModelCallRef(project_ref, parent_id)
            call = self._build_call(
                call_ref=call_ref,
                attempt=attempt,
                capability_ref=capability_ref,
                purpose=cast(str, row["purpose"]),
                retry_of=retry_ref,
                parent_model_call_ref=parent_ref,
                provider_id=cast(str | None, row["provider_id"]),
                model_id=cast(str | None, row["model_id"]),
                deployment_id=cast(str | None, row["deployment_id"]),
                tool_id=cast(str | None, row["tool_id"]),
                implementation_id=cast(str | None, row["implementation_id"]),
                runtime_id=cast(str, row["runtime_id"]),
                input_refs=inputs,
                input_provenance_sha256=cast(str, row["input_provenance_sha256"]),
                provider_trace_id=cast(str | None, row["provider_trace_id"]),
                event=event,
                state=states[-1],
            )
            self._verify_call_relationships(
                connection,
                call,
                relationship_visits,
            )
        except CallError:
            raise
        except (ArtifactError, EventError, GraphError, NodeExecutionError, ProjectError, RunError, TaskError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise CallIntegrityError("Persisted call evidence is malformed") from exc
        if (
            row["identity_sha256"] != call.identity_sha256
            or row["record_sha256"] != call.record_sha256
            or row["created_at"] != call.created_at
            or row["start_request_sha256"] != states[0].request_sha256
            or row["start_idempotency_key"] != states[0].idempotency_key
            or row["start_request_sha256"] != self._start_request_sha256(call)
        ):
            raise CallIntegrityError("Persisted call identity digest differs")
        if len(states) == 2 and (
            states[1].request_sha256 != self._terminal_request_sha256(
                call.call_ref,
                states[1],
            )
        ):
            raise CallIntegrityError("Persisted terminal call semantics differ")
        return call

    def _build_call(
        self,
        *,
        call_ref: ModelCallRef | ToolCallRef,
        attempt: NodeExecutionAttempt,
        capability_ref: CapabilityRef,
        purpose: str,
        retry_of: ModelCallRef | ToolCallRef | None,
        parent_model_call_ref: ModelCallRef | None,
        provider_id: str | None,
        model_id: str | None,
        deployment_id: str | None,
        tool_id: str | None,
        implementation_id: str | None,
        runtime_id: str,
        input_refs: tuple[CallObjectRef, ...],
        input_provenance_sha256: str,
        provider_trace_id: str | None,
        event: Event,
        state: CallState,
    ) -> CallRecord:
        if isinstance(call_ref, ModelCallRef):
            if not isinstance(retry_of, (ModelCallRef, type(None))) or provider_id is None or model_id is None:
                raise CallIntegrityError("ModelCall persisted identity is malformed")
            return ModelCall(
                call_ref,
                attempt,
                capability_ref,
                purpose,
                retry_of,
                provider_id,
                model_id,
                deployment_id,
                runtime_id,
                input_refs,
                input_provenance_sha256,
                provider_trace_id,
                event.event_ref,
                event.record_sha256,
                event.created_at,
                state,
            )
        if not isinstance(retry_of, (ToolCallRef, type(None))) or tool_id is None or implementation_id is None:
            raise CallIntegrityError("ToolCall persisted identity is malformed")
        return ToolCall(
            call_ref,
            attempt,
            capability_ref,
            purpose,
            retry_of,
            parent_model_call_ref,
            tool_id,
            implementation_id,
            runtime_id,
            input_refs,
            input_provenance_sha256,
            provider_trace_id,
            event.event_ref,
            event.record_sha256,
            event.created_at,
            state,
        )

    @staticmethod
    def _with_state(call: CallRecord, state: CallState) -> CallRecord:
        if isinstance(call, ModelCall):
            return ModelCall(
                call.call_ref,
                call.attempt,
                call.capability_ref,
                call.purpose,
                call.retry_of,
                call.provider_id,
                call.model_id,
                call.deployment_id,
                call.runtime_id,
                call.input_refs,
                call.input_provenance_sha256,
                call.provider_trace_id,
                call.event_ref,
                call.event_record_sha256,
                call.created_at,
                state,
            )
        return ToolCall(
            call.call_ref,
            call.attempt,
            call.capability_ref,
            call.purpose,
            call.retry_of,
            call.parent_model_call_ref,
            call.tool_id,
            call.implementation_id,
            call.runtime_id,
            call.input_refs,
            call.input_provenance_sha256,
            call.provider_trace_id,
            call.event_ref,
            call.event_record_sha256,
            call.created_at,
            state,
        )

    def _start_request_sha256(self, call: CallRecord) -> str:
        if isinstance(call, ModelCall):
            call_kind = "MODEL"
            deployment_id = call.deployment_id
            implementation_id = None
            model_id = call.model_id
            parent_model_call_ref = None
            provider_id = call.provider_id
            tool_id = None
        else:
            call_kind = "TOOL"
            deployment_id = None
            implementation_id = call.implementation_id
            model_id = None
            parent_model_call_ref = (
                None
                if call.parent_model_call_ref is None
                else call.parent_model_call_ref.value
            )
            provider_id = None
            tool_id = call.tool_id
        return _sha256(
            {
                "attempt_record_sha256": call.attempt.record_sha256,
                "call_kind": call_kind,
                "capability_ref": call.capability_ref.value,
                "deployment_id": deployment_id,
                "implementation_id": implementation_id,
                "input_refs": [
                    self._object_request_payload(item) for item in call.input_refs
                ],
                "model_id": model_id,
                "parent_model_call_ref": parent_model_call_ref,
                "provider_id": provider_id,
                "provider_trace_id": call.provider_trace_id,
                "purpose": call.purpose,
                "retry_of": None if call.retry_of is None else call.retry_of.value,
                "runtime_id": call.runtime_id,
                "tool_id": tool_id,
            }
        )

    def _terminal_request_sha256(
        self,
        call_ref: ModelCallRef | ToolCallRef,
        state: CallState,
    ) -> str:
        return _sha256(
            {
                "call_ref": call_ref.value,
                "cost": None if state.cost is None else state.cost.payload(),
                "failure_category": state.failure_category,
                "failure_evidence_refs": [
                    self._object_request_payload(item)
                    for item in state.failure_evidence_refs
                ],
                "failure_reason": state.failure_reason,
                "output_refs": [
                    self._object_request_payload(item) for item in state.output_refs
                ],
                "status": state.status,
                "usage": None if state.usage is None else state.usage.payload(),
            }
        )

    def _verify_call_relationships(
        self,
        connection: sqlite3.Connection,
        call: CallRecord,
        visited_call_ids: frozenset[str],
    ) -> None:
        if call.retry_of is not None:
            predecessor_row = connection.execute(
                "SELECT * FROM calls WHERE project_id = ? AND call_id = ?",
                (call.project_ref.value, call.retry_of.call_id),
            ).fetchone()
            if predecessor_row is None:
                raise CallIntegrityError("Call retry predecessor is missing or cyclic")
            predecessor = self._call_from_row(
                connection,
                cast(sqlite3.Row, predecessor_row),
                visited_call_ids,
            )
            if (
                predecessor.call_ref != call.retry_of
                or predecessor.attempt != call.attempt
                or predecessor.capability_ref != call.capability_ref
                or predecessor.status not in _TERMINAL
                or isinstance(predecessor, ModelCall) != isinstance(call, ModelCall)
            ):
                raise CallIntegrityError("Call retry predecessor relationship differs")
        if isinstance(call, ToolCall) and call.parent_model_call_ref is not None:
            parent_row = connection.execute(
                "SELECT * FROM calls WHERE project_id = ? AND call_id = ?",
                (call.project_ref.value, call.parent_model_call_ref.call_id),
            ).fetchone()
            if parent_row is None:
                raise CallIntegrityError("ToolCall parent is missing")
            parent = self._call_from_row(
                connection,
                cast(sqlite3.Row, parent_row),
                visited_call_ids,
            )
            if (
                not isinstance(parent, ModelCall)
                or parent.call_ref != call.parent_model_call_ref
                or parent.attempt != call.attempt
            ):
                raise CallIntegrityError("ToolCall parent relationship differs")

    def _insert_call(
        self,
        connection: sqlite3.Connection,
        call: CallRecord,
        idempotency_key: str,
        request_sha256: str,
    ) -> None:
        is_model = isinstance(call, ModelCall)
        if is_model:
            model_call = cast(ModelCall, call)
            parent_call_id = None
            provider_id = model_call.provider_id
            model_id = model_call.model_id
            deployment_id = model_call.deployment_id
            tool_id = None
            implementation_id = None
        else:
            tool_call = cast(ToolCall, call)
            parent_call_id = (
                None
                if tool_call.parent_model_call_ref is None
                else tool_call.parent_model_call_ref.call_id
            )
            provider_id = None
            model_id = None
            deployment_id = None
            tool_id = tool_call.tool_id
            implementation_id = tool_call.implementation_id
        connection.execute(
            """
            INSERT INTO calls VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                call.project_ref.value,
                call.call_ref.call_id,
                "MODEL" if is_model else "TOOL",
                call.task_ref.task_id,
                call.task_ref.revision,
                call.attempt.task_digest,
                call.run_ref.run_id,
                call.graph_ref.graph_id,
                call.graph_ref.revision,
                call.node_ref.node_id,
                next(
                    item.record_sha256
                    for item in self.executions.graphs._fetch_graph(connection, call.graph_ref).nodes
                    if item.node_ref == call.node_ref
                ),
                call.attempt.attempt_id,
                call.attempt.record_sha256,
                call.attempt.attempt_number,
                call.attempt.fence,
                call.attempt.owner_ref,
                call.attempt.run_attempt_id,
                call.attempt.run_fence,
                call.capability_ref.capability_id,
                call.capability_ref.version,
                call.purpose,
                None if call.retry_of is None else call.retry_of.call_id,
                parent_call_id,
                provider_id,
                model_id,
                deployment_id,
                tool_id,
                implementation_id,
                call.runtime_id,
                call.provider_trace_id,
                call.event_ref.event_id,
                call.event_record_sha256,
                call.input_provenance_sha256,
                call.created_at,
                idempotency_key,
                request_sha256,
                call.identity_sha256,
                call.record_sha256,
            ),
        )

    def _insert_state(
        self,
        connection: sqlite3.Connection,
        call_ref: ModelCallRef | ToolCallRef,
        state: CallState,
    ) -> None:
        connection.execute(
            """
            INSERT INTO call_status_versions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                call_ref.project_ref.value,
                call_ref.call_id,
                state.version,
                state.status,
                None if state.usage is None else _json(state.usage.payload()),
                None if state.cost is None else _json(state.cost.payload()),
                state.failure_category,
                state.failure_reason,
                state.idempotency_key,
                state.request_sha256,
                state.recorded_at,
                state.completed_at,
                state.status_event_ref.event_id,
                state.status_event_record_sha256,
                state.semantic_digest,
                state.record_sha256,
            ),
        )

    def _insert_objects(
        self,
        connection: sqlite3.Connection,
        call_ref: ModelCallRef | ToolCallRef,
        binding_kind: str,
        objects: tuple[CallObjectRef, ...],
        evidence: Sequence[dict[str, object]],
    ) -> None:
        for item, item_evidence in zip(objects, evidence, strict=True):
            artifact = item if isinstance(item, ArtifactRef) else None
            artifact_sha = cast(str | None, item_evidence.get("artifact_record_sha256"))
            record_sha = _sha256(
                {
                    "binding_kind": binding_kind,
                    "call_ref": call_ref.value,
                    "evidence": item_evidence,
                }
            )
            connection.execute(
                """
                INSERT INTO call_objects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_ref.project_ref.value,
                    call_ref.call_id,
                    binding_kind,
                    item.value,
                    "artifact" if artifact is not None else "content",
                    None if artifact is not None else _json(_content_payload(cast(ContentRef, item))),
                    None if artifact is None else artifact.artifact_id,
                    None if artifact is None else artifact.revision,
                    artifact_sha,
                    record_sha,
                ),
            )

    def _states_from_rows(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
        call_id: str,
        output_refs: tuple[CallObjectRef, ...],
        failure_refs: tuple[CallObjectRef, ...],
        call_ref: ModelCallRef | ToolCallRef,
        call_kind: str,
        event_by_id: Mapping[str, Event],
        attempt: NodeExecutionAttempt,
    ) -> tuple[CallState, ...]:
        rows = connection.execute(
            """
            SELECT * FROM call_status_versions
            WHERE project_id = ? AND call_id = ? ORDER BY state_version
            """,
            (project_ref.value, call_id),
        ).fetchall()
        if tuple(row["state_version"] for row in rows) not in ((1,), (1, 2)):
            raise CallIntegrityError("Call state history is not gap-free")
        if len(rows) == 1 and (output_refs or failure_refs):
            raise CallIntegrityError("Running call has uncommitted terminal object bindings")
        states: list[CallState] = []
        try:
            for row in rows:
                version = cast(int, row["state_version"])
                state = CallState(
                    call_id,
                    version,
                    cast(str, row["status"]),
                    () if version == 1 else output_refs,
                    () if version == 1 else failure_refs,
                    self._parse_usage(cast(str | None, row["usage_json"])),
                    self._parse_cost(cast(str | None, row["cost_json"])),
                    cast(str | None, row["failure_category"]),
                    cast(str | None, row["failure_reason"]),
                    cast(str, row["idempotency_key"]),
                    cast(str, row["request_sha256"]),
                    cast(str, row["recorded_at"]),
                    cast(str | None, row["completed_at"]),
                    EventRef(project_ref, cast(str, row["status_event_id"])),
                    cast(str, row["status_event_record_sha256"]),
                )
                if (
                    row["semantic_digest"] != state.semantic_digest
                    or row["record_sha256"] != state.record_sha256
                ):
                    raise CallIntegrityError("Call state digest differs")
                status_event = event_by_id.get(state.status_event_ref.event_id)
                expected_type = (
                    f"{call_kind}_CALL"
                    if version == 1
                    else f"{call_kind}_CALL_TERMINAL"
                )
                expected_objects = (
                    None
                    if version == 1
                    else tuple(
                        sorted(
                            {item.value for item in (*output_refs, *failure_refs)}
                        )
                    )
                )
                if status_event is None or (
                    status_event.record_sha256 != state.status_event_record_sha256
                    or status_event.event_type != expected_type
                    or status_event.task_ref != attempt.task_ref
                    or status_event.run_ref != attempt.run_ref
                    or status_event.graph_ref != attempt.node_ref.graph_ref
                    or status_event.node_ref != attempt.node_ref
                    or status_event.actor_ref != attempt.owner_ref
                    or status_event.metadata.get("call_ref") != call_ref.value
                    or status_event.metadata.get("node_attempt_id") != attempt.attempt_id
                    or status_event.metadata.get("node_fence") != attempt.fence
                    or status_event.metadata.get("request_sha256") != state.request_sha256
                    or status_event.metadata.get("run_attempt_id") != attempt.run_attempt_id
                    or status_event.metadata.get("run_fence") != attempt.run_fence
                    or status_event.metadata.get("status") != state.status
                    or (
                        expected_objects is not None
                        and status_event.object_refs != expected_objects
                    )
                ):
                    raise CallIntegrityError("Call status Event attribution differs")
                states.append(state)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise CallIntegrityError("Persisted call state is malformed") from exc
        return tuple(states)

    def _objects_from_rows(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
        call_id: str,
        binding_kind: str,
    ) -> tuple[tuple[CallObjectRef, ...], tuple[dict[str, object], ...]]:
        rows = connection.execute(
            """
            SELECT * FROM call_objects
            WHERE project_id = ? AND call_id = ? AND binding_kind = ?
            ORDER BY object_ref
            """,
            (project_ref.value, call_id, binding_kind),
        ).fetchall()
        objects: list[CallObjectRef] = []
        evidence: list[dict[str, object]] = []
        try:
            for row in rows:
                if row["object_kind"] == "content":
                    payload = cast(dict[str, object], json.loads(cast(str, row["content_ref_json"])))
                    item: CallObjectRef = ContentRef(
                        cast(str, payload["algorithm"]),
                        cast(str, payload["digest"]),
                        cast(int, payload["size_bytes"]),
                        cast(str, payload["media_type"]),
                    )
                    item_evidence = self._object_request_payload(item)
                elif row["object_kind"] == "artifact":
                    item = ArtifactRef(
                        project_ref,
                        cast(str, row["artifact_id"]),
                        cast(int, row["artifact_revision"]),
                    )
                    artifact = self.artifacts._fetch_artifact(connection, item)
                    if artifact.record_sha256 != row["artifact_record_sha256"]:
                        raise CallIntegrityError("Call Artifact evidence differs")
                    item_evidence = {
                        "artifact_record_sha256": artifact.record_sha256,
                        "ref": item.value,
                    }
                else:
                    raise CallIntegrityError("Call object kind is malformed")
                if item.value != row["object_ref"]:
                    raise CallIntegrityError("Call object identity differs")
                expected = _sha256(
                    {
                        "binding_kind": binding_kind,
                        "call_ref": f"{'model-call' if call_id.startswith('mcall_') else 'tool-call'}://{project_ref.value}/{call_id}",
                        "evidence": item_evidence,
                    }
                )
                if not hmac.compare_digest(expected, cast(str, row["record_sha256"])):
                    raise CallIntegrityError("Call object record digest differs")
                objects.append(item)
                evidence.append(item_evidence)
        except (ArtifactError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise CallIntegrityError("Persisted call object is malformed") from exc
        return tuple(objects), tuple(evidence)

    def _verify_objects(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        values: tuple[CallObjectRef, ...],
    ) -> tuple[dict[str, object], ...]:
        evidence: list[dict[str, object]] = []
        for item in values:
            if isinstance(item, ArtifactRef):
                if item.project_ref != access.project_ref:
                    raise CallScopeError("Call Artifact crossed Project scope")
                try:
                    artifact = self.artifacts._fetch_artifact(connection, item)
                except ArtifactError as exc:
                    raise CallContractError("Call ArtifactRef is not exact") from exc
                evidence.append(
                    {
                        "artifact_record_sha256": artifact.record_sha256,
                        "ref": item.value,
                    }
                )
            else:
                evidence.append(self._object_request_payload(item))
        return tuple(evidence)

    @staticmethod
    def _object_request_payload(item: CallObjectRef) -> dict[str, object]:
        if isinstance(item, ArtifactRef):
            return {"ref": item.value}
        if isinstance(item, ContentRef):
            return {"content_ref": _content_payload(item), "ref": item.value}
        raise CallContractError("Call object must be exact ArtifactRef or ContentRef")

    @staticmethod
    def _parse_usage(value: str | None) -> CallUsage | None:
        if value is None:
            return None
        payload = cast(dict[str, dict[str, object]], json.loads(value))

        def metric(name: str) -> UsageMetric:
            item = payload[name]
            return UsageMetric(
                cast(int | None, item["value"]),
                cast(str | None, item["source"]),
            )

        return CallUsage(
            metric("input_tokens"),
            metric("output_tokens"),
            metric("reasoning_tokens"),
            metric("cached_input_tokens"),
            metric("cache_write_tokens"),
        )

    @staticmethod
    def _parse_cost(value: str | None) -> CallCost | None:
        if value is None:
            return None
        payload = cast(dict[str, object], json.loads(value))
        return CallCost(
            cast(str, payload["amount_decimal"]),
            cast(str, payload["currency"]),
            cast(str, payload["source"]),
            cast(str, payload["pricing_identity"]),
        )

    @staticmethod
    def _authorize_in_transaction(
        connection: sqlite3.Connection,
        access: ProjectAccess,
        project_ref: ProjectRef,
    ) -> None:
        try:
            authorized = ProjectStore._authorize(connection, access)
        except ProjectScopeError as exc:
            raise CallScopeError("Call Project scope mismatch") from exc
        if authorized != project_ref:
            raise CallScopeError("Call Project scope mismatch")

    @staticmethod
    def _database_now(connection: sqlite3.Connection) -> str:
        value = connection.execute(
            "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
        ).fetchone()[0]
        if not isinstance(value, str):
            raise CallIntegrityError("Durable database time is unavailable")
        return _validate_timestamp(value, "database_now")
