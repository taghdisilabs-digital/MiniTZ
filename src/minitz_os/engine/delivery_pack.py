"""Provider-neutral, fail-closed packaging and delivery contracts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import PurePosixPath
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

from .artifact import ArtifactRef, ContentRef
from .capability import Capability, CapabilityRef
from .graph import GraphRef, NodeRef
from .production_pack import GraphRecipeRegistration, GraphRecipeStepRegistration, ProductionPack, ProductionPackRef, ValidatorRegistration
from .project import ProjectRef
from .run import RunRef
from .task import TaskRef

if TYPE_CHECKING:
    from .execution import NodeExecutionAttempt
    from .project import ProjectAccess


DELIVERY_CAPABILITIES = ("package.assemble", "package.manifest", "package.archive", "package.compress", "package.installable", "package.sign", "package.verify", "publish.upload", "publish.deploy", "publish.release", "publish.distribute", "publish.verify", "delivery.copy", "delivery.sync", "delivery.verify")
DELIVERY_ARTIFACT_ROLES = ("delivery.package", "delivery.manifest", "delivery.archive", "delivery.signature", "delivery.receipt", "delivery.validation-evidence")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
_IDEMPOTENCY = re.compile(r"[A-Za-z0-9_.:-]{1,192}")
_STATES = {"UPLOADED", "VERIFIED", "RELEASED", "FAILED", "OUTCOME_UNKNOWN"}


class DeliveryContractError(ValueError):
    pass


def _ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise DeliveryContractError(f"{field} is invalid")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise DeliveryContractError(f"{field} is invalid")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise DeliveryContractError(f"{field} is invalid")
    return value


def _map(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise DeliveryContractError(f"{field} is invalid")
    copied: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise DeliveryContractError(f"{field} is invalid")
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise DeliveryContractError(f"{field} is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise DeliveryContractError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DeliveryContractError(f"{field} is invalid")
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _safe_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024 or "\\" in value or value.startswith("/") or "//" in value:
        raise DeliveryContractError(f"{field} path is unsafe")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DeliveryContractError(f"{field} path is unsafe")
    normalized = PurePosixPath(value).as_posix()
    if normalized != value:
        raise DeliveryContractError(f"{field} path is unsafe")
    return normalized


@dataclass(frozen=True)
class DeliveryArtifactContentRef:
    artifact_ref: ArtifactRef
    content_ref: ContentRef

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_ref, ArtifactRef) or not isinstance(self.content_ref, ContentRef):
            raise DeliveryContractError("source Artifact/Content identity is invalid")

    @property
    def project_ref(self) -> ProjectRef:
        return self.artifact_ref.project_ref

    def payload(self) -> dict[str, object]:
        return {"artifact_ref": self.artifact_ref.value, "content_ref": self.content_ref.value, "content_sha256": self.content_ref.digest, "size_bytes": self.content_ref.size_bytes}


@dataclass(frozen=True)
class PackageEntry:
    path: str
    content_sha256: str
    size_bytes: int
    media_type: str
    permission: str
    link_policy: str
    link_target: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _safe_path(self.path, "package entry"))
        _sha(self.content_sha256, "package entry digest")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            raise DeliveryContractError("package entry size is invalid")
        _text(self.media_type, "package entry media_type")
        if not isinstance(self.permission, str) or re.fullmatch(r"0[0-7]{3}", self.permission) is None:
            raise DeliveryContractError("package entry permission is invalid")
        if self.link_policy not in {"forbid", "preserve"}:
            raise DeliveryContractError("package entry link policy is invalid")
        if self.link_policy == "forbid" and self.link_target is not None:
            raise DeliveryContractError("package entry symlink is not explicitly allowed")
        if self.link_policy == "preserve":
            if self.link_target is None:
                raise DeliveryContractError("package entry symlink target is required")
            object.__setattr__(self, "link_target", _safe_path(self.link_target, "package entry link"))

    def payload(self) -> dict[str, object]:
        return {"path": self.path, "content_sha256": self.content_sha256, "size_bytes": self.size_bytes, "media_type": self.media_type, "permission": self.permission, "link_policy": self.link_policy, "link_target": self.link_target}


@dataclass(frozen=True)
class PackageManifest:
    project_ref: ProjectRef
    package_id: str
    task_ref: TaskRef
    run_ref: RunRef
    graph_ref: GraphRef
    package_type: str
    target_ref: str
    sources: tuple[DeliveryArtifactContentRef, ...]
    entries: tuple[PackageEntry, ...]
    source_version_ref: str
    build_version_ref: str
    toolchains: Mapping[str, str]
    config_sha256: str
    signing_metadata_ref: str | None
    created_at: str
    manifest_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, package_id: str, task_ref: TaskRef, run_ref: RunRef, graph_ref: GraphRef, package_type: str, target_ref: str, sources: Sequence[DeliveryArtifactContentRef], entries: Sequence[PackageEntry], source_version_ref: str, build_version_ref: str, toolchains: Mapping[str, str], config_sha256: str, signing_metadata_ref: str | None, created_at: str) -> "PackageManifest":
        payload = cls._payload(project_ref, package_id, task_ref, run_ref, graph_ref, package_type, target_ref, sources, entries, source_version_ref, build_version_ref, toolchains, config_sha256, signing_metadata_ref, created_at)
        return cls(project_ref, package_id, task_ref, run_ref, graph_ref, package_type, target_ref, tuple(sources), tuple(entries), source_version_ref, build_version_ref, toolchains, config_sha256, signing_metadata_ref, created_at, _digest(payload))

    @staticmethod
    def _payload(project_ref: ProjectRef, package_id: str, task_ref: TaskRef, run_ref: RunRef, graph_ref: GraphRef, package_type: str, target_ref: str, sources: Sequence[DeliveryArtifactContentRef], entries: Sequence[PackageEntry], source_version_ref: str, build_version_ref: str, toolchains: Mapping[str, str], config_sha256: str, signing_metadata_ref: str | None, created_at: str) -> dict[str, object]:
        if not isinstance(project_ref, ProjectRef) or not isinstance(package_id, str) or not package_id:
            raise DeliveryContractError("package Project/id is invalid")
        if not isinstance(task_ref, TaskRef) or not isinstance(run_ref, RunRef) or not isinstance(graph_ref, GraphRef) or task_ref.project_ref != project_ref or run_ref.project_ref != project_ref or graph_ref.project_ref != project_ref:
            raise DeliveryContractError("package Task/Run/Graph crossed Project scope")
        source_values, entry_values = tuple(sources), tuple(entries)
        if not source_values or not entry_values or not all(isinstance(item, DeliveryArtifactContentRef) and item.project_ref == project_ref for item in source_values) or not all(isinstance(item, PackageEntry) for item in entry_values):
            raise DeliveryContractError("package sources/entries are invalid")
        if len({item.path for item in entry_values}) != len(entry_values) or len({item.path.casefold() for item in entry_values}) != len(entry_values):
            raise DeliveryContractError("package entries are duplicate")
        source_digests = {item.content_ref.digest for item in source_values}
        if any(item.content_sha256 not in source_digests for item in entry_values):
            raise DeliveryContractError("package entry digest is not an explicitly included source")
        return {"project_ref": project_ref.value, "package_id": package_id, "task_ref": f"task://{task_ref.project_ref.value}/{task_ref.task_id}/{task_ref.revision}", "run_ref": f"run://{run_ref.project_ref.value}/{run_ref.run_id}", "graph_ref": graph_ref.value, "package_type": _text(package_type, "package_type"), "target_ref": _ref(target_ref, "target_ref"), "sources": [item.payload() for item in source_values], "entries": [item.payload() for item in entry_values], "source_version_ref": _ref(source_version_ref, "source_version_ref"), "build_version_ref": _ref(build_version_ref, "build_version_ref"), "toolchains": dict(_map(toolchains, "toolchains")), "config_sha256": _sha(config_sha256, "config_sha256"), "signing_metadata_ref": None if signing_metadata_ref is None else _ref(signing_metadata_ref, "signing_metadata_ref"), "created_at": _timestamp(created_at, "created_at")}

    def __post_init__(self) -> None:
        payload = self._payload(self.project_ref, self.package_id, self.task_ref, self.run_ref, self.graph_ref, self.package_type, self.target_ref, self.sources, self.entries, self.source_version_ref, self.build_version_ref, self.toolchains, self.config_sha256, self.signing_metadata_ref, self.created_at)
        if _sha(self.manifest_digest, "manifest_digest") != _digest(payload):
            raise DeliveryContractError("manifest_digest does not match exact package manifest")
        object.__setattr__(self, "toolchains", _map(self.toolchains, "toolchains"))


@dataclass(frozen=True)
class PublishDestination:
    project_ref: ProjectRef | None
    global_scope_authorized: bool
    adapter_ref: str
    destination_type: str
    endpoint_ref: str
    auth_secret_ref: str
    allowed_targets: tuple[str, ...]
    data_policy_ref: str

    def __post_init__(self) -> None:
        if self.project_ref is None:
            if not self.global_scope_authorized:
                raise DeliveryContractError("global publish destination requires explicit authorization")
        elif not isinstance(self.project_ref, ProjectRef) or self.global_scope_authorized:
            raise DeliveryContractError("publish destination Project/global scope is invalid")
        _ref(self.adapter_ref, "adapter_ref")
        _text(self.destination_type, "destination_type")
        _ref(self.endpoint_ref, "endpoint_ref")
        if not isinstance(self.auth_secret_ref, str) or not self.auth_secret_ref.startswith("secret://"):
            raise DeliveryContractError("publish auth must be a secret reference, not secret bytes")
        _ref(self.auth_secret_ref, "auth_secret_ref")
        targets = tuple(self.allowed_targets)
        if not targets or len(set(targets)) != len(targets):
            raise DeliveryContractError("publish allowed targets are invalid")
        object.__setattr__(self, "allowed_targets", tuple(_ref(item, "allowed_target") for item in targets))
        _ref(self.data_policy_ref, "data_policy_ref")

    def payload(self) -> dict[str, object]:
        return {"project_ref": None if self.project_ref is None else self.project_ref.value, "global_scope_authorized": self.global_scope_authorized, "adapter_ref": self.adapter_ref, "destination_type": self.destination_type, "endpoint_ref": self.endpoint_ref, "auth_secret_ref": self.auth_secret_ref, "allowed_targets": list(self.allowed_targets), "data_policy_ref": self.data_policy_ref}


@dataclass(frozen=True)
class PublishRequest:
    manifest: PackageManifest
    destination: PublishDestination
    target_ref: str
    release_ref: str
    mode: str
    overwrite: bool
    verification_ref: str
    task_ref: TaskRef
    run_ref: RunRef
    node_ref: NodeRef
    idempotency_key: str
    request_digest: str

    @classmethod
    def create(cls, manifest: PackageManifest, destination: PublishDestination, target_ref: str, release_ref: str, mode: str, overwrite: bool, verification_ref: str, task_ref: TaskRef, run_ref: RunRef, node_ref: NodeRef, idempotency_key: str) -> "PublishRequest":
        payload = cls._payload(manifest, destination, target_ref, release_ref, mode, overwrite, verification_ref, task_ref, run_ref, node_ref, idempotency_key)
        return cls(manifest, destination, target_ref, release_ref, mode, overwrite, verification_ref, task_ref, run_ref, node_ref, idempotency_key, _digest(payload))

    @staticmethod
    def _payload(manifest: PackageManifest, destination: PublishDestination, target_ref: str, release_ref: str, mode: str, overwrite: bool, verification_ref: str, task_ref: TaskRef, run_ref: RunRef, node_ref: NodeRef, idempotency_key: str) -> dict[str, object]:
        if not isinstance(manifest, PackageManifest) or not isinstance(destination, PublishDestination) or not isinstance(task_ref, TaskRef) or not isinstance(run_ref, RunRef) or not isinstance(node_ref, NodeRef):
            raise DeliveryContractError("publish request identity is invalid")
        project_ref = manifest.project_ref
        if task_ref != manifest.task_ref or run_ref != manifest.run_ref or node_ref.graph_ref != manifest.graph_ref or node_ref.project_ref != project_ref or (destination.project_ref is not None and destination.project_ref != project_ref):
            raise DeliveryContractError("publish request crossed Project/Task/Run/Graph scope")
        checked_target = _ref(target_ref, "target_ref")
        if checked_target not in destination.allowed_targets:
            raise DeliveryContractError("publish target is not allowed by destination")
        if mode not in {"upload", "deploy", "release", "distribute", "copy", "sync"} or not isinstance(overwrite, bool):
            raise DeliveryContractError("publish mode/overwrite is invalid")
        if not isinstance(idempotency_key, str) or _IDEMPOTENCY.fullmatch(idempotency_key) is None:
            raise DeliveryContractError("publish idempotency key is invalid")
        return {"manifest_digest": manifest.manifest_digest, "destination": destination.payload(), "target_ref": checked_target, "release_ref": _ref(release_ref, "release_ref"), "mode": mode, "overwrite": overwrite, "verification_ref": _ref(verification_ref, "verification_ref"), "task_ref": f"task://{task_ref.project_ref.value}/{task_ref.task_id}/{task_ref.revision}", "run_ref": f"run://{run_ref.project_ref.value}/{run_ref.run_id}", "node_ref": node_ref.value, "idempotency_key": idempotency_key}

    def __post_init__(self) -> None:
        payload = self._payload(self.manifest, self.destination, self.target_ref, self.release_ref, self.mode, self.overwrite, self.verification_ref, self.task_ref, self.run_ref, self.node_ref, self.idempotency_key)
        if _sha(self.request_digest, "request_digest") != _digest(payload):
            raise DeliveryContractError("request_digest does not match exact publish request")


@dataclass(frozen=True)
class PublishReceipt:
    request_digest: str
    state: str
    remote_identity: str | None
    remote_version: str | None
    upload_sha256: str | None
    verification_evidence_ref: str | None
    recorded_at: str
    failure_ref: str | None
    receipt_digest: str

    @classmethod
    def create(cls, request: PublishRequest, state: str, remote_identity: str | None, remote_version: str | None, upload_sha256: str | None, verification_evidence_ref: str | None, recorded_at: str, failure_ref: str | None) -> "PublishReceipt":
        if not isinstance(request, PublishRequest):
            raise DeliveryContractError("receipt request is invalid")
        payload = cls._payload(request.request_digest, state, remote_identity, remote_version, upload_sha256, verification_evidence_ref, recorded_at, failure_ref)
        return cls(request.request_digest, state, remote_identity, remote_version, upload_sha256, verification_evidence_ref, recorded_at, failure_ref, _digest(payload))

    @staticmethod
    def _payload(request_digest: str, state: str, remote_identity: str | None, remote_version: str | None, upload_sha256: str | None, verification_evidence_ref: str | None, recorded_at: str, failure_ref: str | None) -> dict[str, object]:
        _sha(request_digest, "request_digest")
        if state not in _STATES:
            raise DeliveryContractError("publish receipt state is invalid")
        successful = state in {"UPLOADED", "VERIFIED", "RELEASED"}
        verified = state in {"VERIFIED", "RELEASED"}
        if successful:
            if remote_identity is None or remote_version is None or upload_sha256 is None:
                raise DeliveryContractError("successful publish receipt is incomplete")
            _ref(remote_identity, "remote_identity"); _text(remote_version, "remote_version"); _sha(upload_sha256, "upload_sha256")
        elif any(value is not None for value in (remote_identity, remote_version, upload_sha256)):
            raise DeliveryContractError("failed/unknown receipt cannot fabricate remote success")
        if verified:
            if verification_evidence_ref is None:
                raise DeliveryContractError("verified/released receipt requires verification evidence")
            _ref(verification_evidence_ref, "verification_evidence_ref")
        elif verification_evidence_ref is not None:
            raise DeliveryContractError("unverified receipt cannot fabricate verification")
        if state == "FAILED":
            if failure_ref is None:
                raise DeliveryContractError("failed receipt requires failure evidence")
            _ref(failure_ref, "failure_ref")
        elif failure_ref is not None:
            raise DeliveryContractError("nonfailed receipt cannot carry failure evidence")
        return {"request_digest": request_digest, "state": state, "remote_identity": remote_identity, "remote_version": remote_version, "upload_sha256": upload_sha256, "verification_evidence_ref": verification_evidence_ref, "recorded_at": _timestamp(recorded_at, "recorded_at"), "failure_ref": failure_ref}

    def __post_init__(self) -> None:
        payload = self._payload(self.request_digest, self.state, self.remote_identity, self.remote_version, self.upload_sha256, self.verification_evidence_ref, self.recorded_at, self.failure_ref)
        if _sha(self.receipt_digest, "receipt_digest") != _digest(payload):
            raise DeliveryContractError("receipt_digest does not match exact publish receipt")


class DeliveryToolAdapter(Protocol):
    project_ref: ProjectRef
    tool_ref: str
    runtime_ref: str

    def assemble(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", manifest: PackageManifest) -> DeliveryArtifactContentRef: ...


class PublishAdapter(Protocol):
    project_ref: ProjectRef | None
    adapter_ref: str

    def publish(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", request: PublishRequest) -> PublishReceipt: ...


def delivery_production_pack() -> ProductionPack:
    capabilities = tuple(Capability(CapabilityRef(name, "1.0.0"), f"Bounded delivery {name}", {}, {"result": f"minitz://contracts/{name.replace('.', '-')}/v1"}, (), "2026-09-01T00:00:00+00:00") for name in DELIVERY_CAPABILITIES)
    refs = {item.capability_id: item.capability_ref for item in capabilities}
    steps = tuple(GraphRecipeStepRegistration(name.replace(".", "-"), refs[name], () if index == 0 else (DELIVERY_CAPABILITIES[index - 1].replace(".", "-"),)) for index, name in enumerate(DELIVERY_CAPABILITIES))
    return ProductionPack(ProductionPackRef("delivery", "1.0.0"), capabilities, (GraphRecipeRegistration("pack-recipe://delivery/production@1.0.0", steps),), tuple(ValidatorRegistration(f"pack-validator://delivery/{name.replace('.', '-')}@1.0.0", refs[name], f"validation-check://artifact-role/{DELIVERY_ARTIFACT_ROLES[index % len(DELIVERY_ARTIFACT_ROLES)]}/v1") for index, name in enumerate(DELIVERY_CAPABILITIES)), DELIVERY_ARTIFACT_ROLES, {item.capability_ref.value: ("adapter://delivery/provider-neutral/v1",) for item in capabilities}, {item.capability_ref.value: "resource-profile://delivery/project-configured/v1" for item in capabilities}, "2026-09-01T00:00:00+00:00")
