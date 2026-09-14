"""MiniTZ's unified capability, resource, action, and evidence boundary.

The older ``biella`` modules provide the semantic contracts and domain packs.
This module is the MiniTZ-owned composition point: a capability is executable
only when its action contract, a current Resource observation, an implementation
binding, and an evidence-producing readback are all present.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, cast

from biella.animation_pack import animation_production_pack
from biella.audio_pack import audio_production_pack
from biella.capability import Capability, CapabilityRef
from biella.character_pack import character_production_pack
from biella.delivery_pack import delivery_production_pack
from biella.evidence_graph import EvidenceGraph, EvidenceKind, EvidenceRecord, derived_provenance
from biella.game_pack import game_production_pack
from biella.image_pack import image_production_pack
from biella.production_pack import ProductionPack
from biella.render_pack import render_production_pack
from biella.software_pack import software_production_pack
from biella.three_d_pack import three_d_production_pack
from biella.vfx_pack import vfx_production_pack
from biella.video_pack import video_production_pack
from biella.web_pack import web_production_pack


TASK_SCOPE_REF = "scope://minitz/capability-surface/v1"
SOURCE_IDENTITY = "source-library://minitz/main"
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_NAME = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_CAPABILITY_REF = re.compile(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+@[0-9]+\.[0-9]+\.[0-9]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SECRET_KEYS = frozenset({"api_key", "apikey", "password", "passwd", "secret", "token", "authorization"})
_SECRET_VALUE = re.compile(r"(?i)(?:bearer\s+|sk-(?:proj-|svcacct-)?|gh[pousr]_)[A-Za-z0-9_./+=:-]{12,}")


class CapabilitySurfaceError(ValueError):
    """A MiniTZ capability boundary contract is malformed."""


class CapabilityUnavailableError(CapabilitySurfaceError):
    """Execution was refused because current availability is not truthful Ready."""


class Availability(str, Enum):
    READY = "Ready"
    DEGRADED = "Degraded"
    UNAVAILABLE = "Unavailable"
    NEEDS_SETUP = "Needs Setup"
    NEEDS_ATTENTION = "Needs Attention"
    UPDATING = "Updating"
    RECOVERING = "Recovering"
    DISABLED = "Disabled"
    NOT_PRESENT = "Not Present"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _ref(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise CapabilitySurfaceError(f"{field_name} must be an absolute reference")
    return value


def _sha(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise CapabilitySurfaceError(f"{field_name} must be a SHA-256 digest")
    return value


def _capability_ref(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _CAPABILITY_REF.fullmatch(value) is None:
        raise CapabilitySurfaceError(f"{field_name} must be a versioned capability reference")
    return value


def _text(value: object, field_name: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise CapabilitySurfaceError(f"{field_name} is malformed or unbounded")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise CapabilitySurfaceError(f"{field_name} contains a control character")
    return value


def _safe_json(value: object, path: str = "value") -> object:
    """Bound and reject raw credentials before an executor can see the input."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise CapabilitySurfaceError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, str):
        bounded = _text(value, path, 4096)
        if _SECRET_VALUE.search(bounded):
            raise CapabilitySurfaceError(f"{path} contains a credential-like value")
        return bounded
    if isinstance(value, Mapping):
        if len(value) > 128:
            raise CapabilitySurfaceError(f"{path} is unbounded")
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _NAME.fullmatch(key):
                raise CapabilitySurfaceError(f"{path} has a malformed key")
            if key.lower() in _SECRET_KEYS:
                raise CapabilitySurfaceError(f"{path}.{key} contains a credential field")
            result[key] = _safe_json(item, f"{path}.{key}")
        return MappingProxyType(result)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        if len(value) > 128:
            raise CapabilitySurfaceError(f"{path} is unbounded")
        return tuple(_safe_json(item, f"{path}[{index}]") for index, item in enumerate(value))
    raise CapabilitySurfaceError(f"{path} is not JSON-compatible")


def _plain_json(value: object) -> object:
    """Convert the guarded immutable representation into evidence payload data."""
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain_json(item) for item in value]
    return value


def _tuple_refs(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or len(values) > 64:
        raise CapabilitySurfaceError(f"{field_name} is malformed")
    result = tuple(_ref(item, field_name) for item in values)
    if len(set(result)) != len(result):
        raise CapabilitySurfaceError(f"{field_name} is duplicated")
    return tuple(sorted(result))


@dataclass(frozen=True)
class ResourceContract:
    """One replaceable runtime resource and its latest observed truth."""

    resource_ref: str
    resource_kind: str
    availability: Availability
    evidence_refs: tuple[str, ...]
    evidence_sha256: str
    implementation_refs: tuple[str, ...] = ()
    observed_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        _ref(self.resource_ref, "resource_ref")
        _text(self.resource_kind, "resource_kind", 128)
        if not isinstance(self.availability, Availability):
            raise TypeError("availability must be Availability")
        object.__setattr__(self, "evidence_refs", _tuple_refs(self.evidence_refs, "evidence_refs"))
        if not self.evidence_refs:
            raise CapabilitySurfaceError("a resource requires current evidence")
        _sha(self.evidence_sha256, "evidence_sha256")
        object.__setattr__(self, "implementation_refs", _tuple_refs(self.implementation_refs, "implementation_refs"))
        _text(self.observed_at, "observed_at", 128)

    def to_payload(self) -> dict[str, object]:
        return {
            "resource_ref": self.resource_ref,
            "resource_kind": self.resource_kind,
            "availability": self.availability.value,
            "evidence_refs": list(self.evidence_refs),
            "evidence_sha256": self.evidence_sha256,
            "implementation_refs": list(self.implementation_refs),
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class ActionContract:
    """The only route by which a MiniTZ capability may be invoked."""

    action_ref: str
    capability_ref: CapabilityRef
    input_contract: Mapping[str, str]
    output_contract: Mapping[str, str]
    side_effects: tuple[str, ...]
    resource_profile_ref: str
    implementation_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _ref(self.action_ref, "action_ref")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        object.__setattr__(self, "input_contract", MappingProxyType(dict(self.input_contract)))
        object.__setattr__(self, "output_contract", MappingProxyType(dict(self.output_contract)))
        object.__setattr__(self, "side_effects", tuple(sorted(self.side_effects)))
        _ref(self.resource_profile_ref, "resource_profile_ref")
        object.__setattr__(self, "implementation_refs", _tuple_refs(self.implementation_refs, "implementation_refs"))
        object.__setattr__(self, "evidence_refs", _tuple_refs(self.evidence_refs, "evidence_refs"))


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability: Capability
    action: ActionContract
    adapter_refs: tuple[str, ...]
    pack_ref: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.capability, Capability) or self.action.capability_ref != self.capability.capability_ref:
            raise CapabilitySurfaceError("action and semantic capability identities differ")
        object.__setattr__(self, "adapter_refs", _tuple_refs(self.adapter_refs, "adapter_refs"))
        _text(self.pack_ref, "pack_ref", 256)
        object.__setattr__(self, "evidence_refs", _tuple_refs(self.evidence_refs, "evidence_refs"))

    @property
    def capability_ref(self) -> CapabilityRef:
        return self.capability.capability_ref


@dataclass(frozen=True)
class CapabilityStatus:
    capability_ref: str
    availability: Availability
    resource_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    implementation_refs: tuple[str, ...]
    reason: str
    observed_at: str

    def to_payload(self) -> dict[str, object]:
        return {
            "capability_ref": self.capability_ref,
            "availability": self.availability.value,
            "resource_refs": list(self.resource_refs),
            "evidence_refs": list(self.evidence_refs),
            "implementation_refs": list(self.implementation_refs),
            "reason": self.reason,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class ActionRequest:
    capability_ref: str
    action_ref: str
    inputs: Mapping[str, object]
    resource_ref: str

    def __post_init__(self) -> None:
        _capability_ref(self.capability_ref, "capability_ref")
        _ref(self.action_ref, "action_ref")
        _ref(self.resource_ref, "resource_ref")
        safe = _safe_json(self.inputs, "inputs")
        if not isinstance(safe, Mapping):
            raise CapabilitySurfaceError("inputs must be a mapping")
        object.__setattr__(self, "inputs", safe)


@dataclass(frozen=True)
class ActionResult:
    capability_ref: str
    action_ref: str
    resource_ref: str
    implementation_ref: str
    readback: Mapping[str, object]
    evidence_ref: str
    evidence_sha256: str
    evidence_record: EvidenceRecord


Executor = Callable[[Mapping[str, object]], Mapping[str, object]]


def _native_capability(capability_id: str, description: str) -> Capability:
    return Capability(
        CapabilityRef(capability_id, "1.0.0"),
        description,
        {"request": "schema://minitz/capability-request/v1"},
        {"result": "schema://minitz/capability-result/v1"},
        (),
        "2026-09-14T00:00:00+00:00",
    )


_PACK_FACTORIES: tuple[Callable[[], ProductionPack], ...] = (
    software_production_pack,
    web_production_pack,
    game_production_pack,
    three_d_production_pack,
    character_production_pack,
    animation_production_pack,
    render_production_pack,
    image_production_pack,
    audio_production_pack,
    video_production_pack,
    vfx_production_pack,
    delivery_production_pack,
)

_SYSTEM_CAPABILITIES = (
    ("filesystem.read", "Read an exact filesystem object through a MiniTZ resource."),
    ("filesystem.write", "Write an exact filesystem object through a MiniTZ resource."),
    ("process.execute", "Execute a bounded process through a MiniTZ resource."),
    ("network.request", "Perform a bounded network request through a MiniTZ resource."),
    ("model.infer", "Invoke a model through a MiniTZ resource and retain readback."),
    ("storage.read", "Read managed storage through a MiniTZ resource."),
    ("storage.write", "Write managed storage through a MiniTZ resource."),
    ("api.request", "Call a declared API through a MiniTZ resource."),
    ("system.integration", "Compose a capability, resource, action, and evidence contract."),
    ("evidence.record", "Record exact execution readback and provenance evidence."),
)


class CapabilitySurface:
    """Canonical in-process MiniTZ capability registry and action gateway."""

    def __init__(self, *, include_builtin: bool = True) -> None:
        self._descriptors: dict[str, CapabilityDescriptor] = {}
        self._resources: dict[str, ResourceContract] = {}
        self._executors: dict[str, tuple[Executor, str]] = {}
        if include_builtin:
            self._load_builtin()

    def _add_descriptor(
        self,
        capability: Capability,
        *,
        adapter_refs: Sequence[str],
        pack_ref: str,
        resource_profile_ref: str,
        evidence_refs: Sequence[str],
    ) -> None:
        key = capability.capability_ref.value
        if key in self._descriptors:
            raise CapabilitySurfaceError(f"duplicate capability surface identity: {key}")
        action_ref = f"action://minitz/{capability.capability_ref.value}/execute"
        implementation_refs = tuple(adapter_refs) or (f"implementation://minitz/{capability.capability_id}/v1",)
        action = ActionContract(
            action_ref=action_ref,
            capability_ref=capability.capability_ref,
            input_contract=capability.input_contract,
            output_contract=capability.output_contract,
            side_effects=capability.side_effects,
            resource_profile_ref=resource_profile_ref,
            implementation_refs=implementation_refs,
            evidence_refs=tuple(evidence_refs),
        )
        self._descriptors[key] = CapabilityDescriptor(
            capability=capability,
            action=action,
            adapter_refs=tuple(adapter_refs),
            pack_ref=pack_ref,
            evidence_refs=tuple(evidence_refs),
        )

    def _load_builtin(self) -> None:
        for factory in _PACK_FACTORIES:
            pack = factory()
            pack_evidence = f"evidence://minitz/production-pack/{pack.pack_ref.value}/{pack.semantic_digest}"
            validators_by_capability: dict[str, list[str]] = {}
            for validator in pack.validators:
                validators_by_capability.setdefault(validator.capability_ref.value, []).append(validator.validator_ref)
            for capability in pack.capability_definitions:
                refs = (pack_evidence, *validators_by_capability.get(capability.capability_ref.value, ()))
                self._add_descriptor(
                    capability,
                    adapter_refs=pack.adapter_bindings[capability.capability_ref.value],
                    pack_ref=pack.pack_ref.value,
                    resource_profile_ref=pack.resource_profiles[capability.capability_ref.value],
                    evidence_refs=refs,
                )
        for capability_id, description in _SYSTEM_CAPABILITIES:
            capability = _native_capability(capability_id, description)
            self._add_descriptor(
                capability,
                adapter_refs=(f"adapter://minitz/{capability.namespace}/v1",),
                pack_ref="minitz-native@1.0.0",
                resource_profile_ref=f"resource-profile://minitz/{capability.namespace}/configured/v1",
                evidence_refs=(f"evidence://minitz/native/{capability_id}/v1",),
            )

    def descriptors(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))

    def get(self, capability_ref: str) -> CapabilityDescriptor:
        try:
            return self._descriptors[capability_ref]
        except KeyError as exc:
            raise CapabilitySurfaceError(f"capability is not registered: {capability_ref}") from exc

    def get_action(self, action_ref: str) -> CapabilityDescriptor:
        for descriptor in self._descriptors.values():
            if descriptor.action.action_ref == action_ref:
                return descriptor
        raise CapabilitySurfaceError(f"action is not registered: {action_ref}")

    def register_resource(self, resource: ResourceContract) -> ResourceContract:
        if not isinstance(resource, ResourceContract):
            raise TypeError("resource must be ResourceContract")
        prior = self._resources.get(resource.resource_ref)
        if prior is not None and prior != resource:
            raise CapabilitySurfaceError("resource identity already has different observation")
        self._resources[resource.resource_ref] = resource
        return resource

    def register_executor(self, action_ref: str, executor: Executor, *, implementation_ref: str) -> None:
        descriptor = self.get_action(action_ref)
        if not callable(executor):
            raise TypeError("executor must be callable")
        _ref(implementation_ref, "implementation_ref")
        if implementation_ref not in descriptor.action.implementation_refs:
            raise CapabilitySurfaceError("executor implementation is not bound by the action contract")
        self._executors[action_ref] = (executor, implementation_ref)

    def status(self, capability_ref: str) -> CapabilityStatus:
        descriptor = self.get(capability_ref)
        resources = tuple(sorted(self._resources.values(), key=lambda item: item.resource_ref))
        bound = tuple(item for item in resources if descriptor.action.resource_profile_ref in item.implementation_refs or not item.implementation_refs)
        evidence = tuple(sorted(set(descriptor.evidence_refs + descriptor.action.evidence_refs + tuple(ref for item in bound for ref in item.evidence_refs))))
        implementations = tuple(sorted(set(descriptor.action.implementation_refs + tuple(ref for item in bound for ref in item.implementation_refs))))
        if not bound:
            availability = Availability.NEEDS_SETUP
            reason = "No current Resource observation is bound to this action."
        elif any(item.availability is Availability.DISABLED for item in bound):
            availability = Availability.DISABLED
            reason = "A bound Resource is explicitly disabled."
        elif any(item.availability is not Availability.READY for item in bound):
            availability = next(item.availability for item in bound if item.availability is not Availability.READY)
            reason = "A bound Resource is not currently Ready."
        elif descriptor.action.action_ref not in self._executors:
            availability = Availability.NEEDS_SETUP
            reason = "Resource is Ready but no contract-bound executor is installed."
        else:
            availability = Availability.READY
            reason = "Resource, executor, action contract, and evidence are present."
        return CapabilityStatus(
            capability_ref=capability_ref,
            availability=availability,
            resource_refs=tuple(item.resource_ref for item in bound),
            evidence_refs=evidence,
            implementation_refs=implementations,
            reason=reason,
            observed_at=_now(),
        )

    def statuses(self) -> tuple[CapabilityStatus, ...]:
        return tuple(self.status(item.capability_ref.value) for item in self.descriptors())

    def execute(self, request: ActionRequest) -> ActionResult:
        descriptor = self.get_action(request.action_ref)
        if descriptor.capability_ref.value != request.capability_ref:
            raise CapabilitySurfaceError("action request capability and action identities differ")
        resource = self._resources.get(request.resource_ref)
        if resource is None:
            raise CapabilityUnavailableError("requested Resource has no current observation")
        if resource.implementation_refs and descriptor.action.resource_profile_ref not in resource.implementation_refs:
            raise CapabilityUnavailableError("requested Resource is not bound to the action resource profile")
        if resource.availability is not Availability.READY:
            raise CapabilityUnavailableError(f"Resource availability is {resource.availability.value}")
        executor_entry = self._executors.get(request.action_ref)
        if executor_entry is None:
            raise CapabilityUnavailableError("action has no contract-bound executor")
        executor, implementation_ref = executor_entry
        result = _plain_json(_safe_json(executor(request.inputs), "readback"))
        if not isinstance(result, Mapping):
            raise CapabilitySurfaceError("executor readback must be a mapping")
        readback = cast(Mapping[str, object], result)
        evidence_ref = f"evidence://minitz/action/{hashlib.sha256((request.action_ref + request.resource_ref + json.dumps(dict(readback), sort_keys=True)).encode()).hexdigest()}"
        record = EvidenceGraph.record(
            record_kind=EvidenceKind.CALL,
            exact_ref=evidence_ref,
            project_ref="project://minitz/system",
            task_ref="task://minitz/capability-surface/v1",
            payload={
                "action_ref": request.action_ref,
                "capability_ref": request.capability_ref,
                "resource_ref": request.resource_ref,
                "resource_evidence_refs": list(resource.evidence_refs),
                "implementation_ref": implementation_ref,
                "readback": dict(readback),
            },
            provenance=derived_provenance(
                source_identity=SOURCE_IDENTITY,
                source_revision_or_observation="capability-surface-runtime",
                source_sha256_or_private_receipt=descriptor.capability.contract_sha256,
                origin_kind="minitz.capability.action",
                observed_at_or_unknown=_now(),
                extraction_or_derivation_ref="derivation://minitz/capability-action/v1",
                scope_ref=TASK_SCOPE_REF,
            ),
        )
        return ActionResult(
            capability_ref=request.capability_ref,
            action_ref=request.action_ref,
            resource_ref=request.resource_ref,
            implementation_ref=implementation_ref,
            readback=readback,
            evidence_ref=record.exact_ref,
            evidence_sha256=record.record_sha256,
            evidence_record=record,
        )

    def snapshot(self) -> dict[str, object]:
        descriptors = self.descriptors()
        statuses = self.statuses()
        payload = {
            "schema": "minitz.capability-surface/v1",
            "source_identity": SOURCE_IDENTITY,
            "scope_ref": TASK_SCOPE_REF,
            "capability_count": len(descriptors),
            "action_count": len(descriptors),
            "status_counts": {state.value: sum(item.availability is state for item in statuses) for state in Availability},
            "capabilities": [
                {
                    "capability_ref": item.capability_ref.value,
                    "action_ref": item.action.action_ref,
                    "pack_ref": item.pack_ref,
                    "adapter_refs": list(item.adapter_refs),
                    "resource_profile_ref": item.action.resource_profile_ref,
                    "evidence_refs": list(item.evidence_refs),
                    "availability": self.status(item.capability_ref.value).availability.value,
                }
                for item in descriptors
            ],
        }
        payload["surface_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return payload


__all__ = [
    "ActionContract",
    "ActionRequest",
    "ActionResult",
    "Availability",
    "CapabilityDescriptor",
    "CapabilityStatus",
    "CapabilitySurface",
    "CapabilitySurfaceError",
    "CapabilityUnavailableError",
    "ResourceContract",
    "SOURCE_IDENTITY",
    "TASK_SCOPE_REF",
]
