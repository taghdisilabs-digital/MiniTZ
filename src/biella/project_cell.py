"""Provider-neutral isolated Project cell execution bridge contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence


_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{4,}"),
    re.compile(r"(?i)\b(?:token|secret|password|api[_-]?key|private[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_ENGINE_SOURCE_ROOT = Path("/root/biella/repos/biella-engine")


class ProjectCellContractError(ValueError):
    """A Project cell, checkpoint, blocker, or provider packet is malformed."""


def _text(value: object, name: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum or "\x00" in value:
        raise ProjectCellContractError(f"{name} is empty or unbounded")
    return value.strip()


def _project_id(value: object) -> str:
    text = _text(value, "project_id", 64)
    if _PROJECT_ID.fullmatch(text) is None:
        raise ProjectCellContractError("project_id is malformed")
    return text


def _path(value: object, name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    text = _text(value, name, 4096)
    path = Path(text)
    if not path.is_absolute():
        raise ProjectCellContractError(f"{name} must be an absolute path")
    return str(path.resolve(strict=False))


def _strings(values: Sequence[str], name: str, maximum: int = 128) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or len(values) > maximum:
        raise ProjectCellContractError(f"{name} is malformed or unbounded")
    return tuple(_text(item, name, 4096) for item in values)


def _mapping(value: Mapping[str, Any], name: str, maximum: int = 128) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or len(value) > maximum:
        raise ProjectCellContractError(f"{name} is malformed or unbounded")
    copied = dict(value)
    for key in copied:
        _text(key, f"{name} key", 128)
    return MappingProxyType(copied)


def _walk_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        result: list[str] = []
        for key, item in value.items():
            result.extend(_walk_strings(key)); result.extend(_walk_strings(item))
        return tuple(result)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        result = []
        for item in value:
            result.extend(_walk_strings(item))
        return tuple(result)
    return ()


def _reject_credentials(value: object) -> None:
    if any(pattern.search(text) for text in _walk_strings(value) for pattern in _SECRET_PATTERNS):
        raise ProjectCellContractError("remote/provider context contains credential material")


@dataclass(frozen=True)
class ProjectCellManifest:
    project_id: str
    project_name: str
    project_type: str
    workspace_root: str
    repository_root: str | None
    canonical_artifact_root: str
    project_memory_namespace: str
    run_memory_namespace: str
    cache_root: str
    historical_evidence_root: str | None
    deployment_targets: tuple[str, ...]
    execution_nodes: tuple[str, ...]
    provider_permissions: Mapping[str, Any]
    acceptance_authority: str
    source_registry: str | None = None
    asset_registry: str | None = None
    deployment_manifest: str | None = None
    browser_execution_profile: str | None = None
    local_model_registry: str | None = None
    governing_contract_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", _project_id(self.project_id))
        object.__setattr__(self, "project_name", _text(self.project_name, "project_name", 256))
        object.__setattr__(self, "project_type", _text(self.project_type, "project_type", 128))
        workspace = _path(self.workspace_root, "workspace_root")
        repository = _path(self.repository_root, "repository_root", nullable=True)
        artifacts = _path(self.canonical_artifact_root, "canonical_artifact_root")
        cache = _path(self.cache_root, "cache_root")
        history = _path(self.historical_evidence_root, "historical_evidence_root", nullable=True)
        assert workspace and artifacts and cache
        workspace_path = Path(workspace)
        if workspace_path == _ENGINE_SOURCE_ROOT or _ENGINE_SOURCE_ROOT in workspace_path.parents:
            raise ProjectCellContractError("workspace_root must not be the Biella Engine source root")
        if artifacts == cache:
            raise ProjectCellContractError("cache_root must not be canonical_artifact_root")
        object.__setattr__(self, "workspace_root", workspace)
        object.__setattr__(self, "repository_root", repository)
        object.__setattr__(self, "canonical_artifact_root", artifacts)
        object.__setattr__(self, "cache_root", cache)
        object.__setattr__(self, "historical_evidence_root", history)
        object.__setattr__(self, "project_memory_namespace", _text(self.project_memory_namespace, "project_memory_namespace", 512))
        object.__setattr__(self, "run_memory_namespace", _text(self.run_memory_namespace, "run_memory_namespace", 512))
        targets = _strings(self.deployment_targets, "deployment_targets")
        if not targets:
            raise ProjectCellContractError("deployment_targets must be explicit or UNKNOWN")
        object.__setattr__(self, "deployment_targets", targets)
        object.__setattr__(self, "execution_nodes", _strings(self.execution_nodes, "execution_nodes"))
        object.__setattr__(self, "provider_permissions", _mapping(self.provider_permissions, "provider_permissions"))
        object.__setattr__(self, "acceptance_authority", _text(self.acceptance_authority, "acceptance_authority", 256))
        for field_name in (
            "source_registry", "asset_registry", "deployment_manifest",
            "browser_execution_profile", "local_model_registry", "governing_contract_sha256",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _text(value, field_name, 4096))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "biella.project_cell_manifest/v1",
            "project_id": self.project_id, "project_name": self.project_name,
            "project_type": self.project_type, "workspace_root": self.workspace_root,
            "repository_root": self.repository_root,
            "canonical_artifact_root": self.canonical_artifact_root,
            "project_memory_namespace": self.project_memory_namespace,
            "run_memory_namespace": self.run_memory_namespace, "cache_root": self.cache_root,
            "historical_evidence_root": self.historical_evidence_root,
            "deployment_targets": list(self.deployment_targets),
            "execution_nodes": list(self.execution_nodes),
            "provider_permissions": dict(self.provider_permissions),
            "acceptance_authority": self.acceptance_authority,
            "source_registry": self.source_registry, "asset_registry": self.asset_registry,
            "deployment_manifest": self.deployment_manifest,
            "browser_execution_profile": self.browser_execution_profile,
            "local_model_registry": self.local_model_registry,
            "governing_contract_sha256": self.governing_contract_sha256,
        }


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    project_id: str
    run_id: str
    objective: str
    acceptance_contract: Mapping[str, Any]
    current_checkpoint_id: str | None
    allowed_scope: Mapping[str, Any]
    forbidden_scope: Mapping[str, Any]
    target_routes: tuple[str, ...] = ()
    target_files: tuple[str, ...] = ()
    governing_sources: tuple[str, ...] = ()
    current_runtime_facts: Mapping[str, Any] = field(default_factory=dict)
    known_good_state: Mapping[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    desired_outputs: tuple[str, ...] = ()
    deployment_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _text(self.task_id, "task_id", 256))
        object.__setattr__(self, "project_id", _project_id(self.project_id))
        object.__setattr__(self, "run_id", _text(self.run_id, "run_id", 256))
        object.__setattr__(self, "objective", _text(self.objective, "objective", 8192))
        object.__setattr__(self, "acceptance_contract", _mapping(self.acceptance_contract, "acceptance_contract"))
        if self.current_checkpoint_id is not None:
            object.__setattr__(self, "current_checkpoint_id", _text(self.current_checkpoint_id, "current_checkpoint_id", 256))
        object.__setattr__(self, "allowed_scope", _mapping(self.allowed_scope, "allowed_scope"))
        object.__setattr__(self, "forbidden_scope", _mapping(self.forbidden_scope, "forbidden_scope"))
        for field_name in ("target_routes", "target_files", "governing_sources", "blockers", "dependencies", "desired_outputs"):
            object.__setattr__(self, field_name, _strings(getattr(self, field_name), field_name))
        object.__setattr__(self, "current_runtime_facts", _mapping(self.current_runtime_facts, "current_runtime_facts"))
        object.__setattr__(self, "known_good_state", _mapping(self.known_good_state, "known_good_state"))
        if not isinstance(self.deployment_required, bool):
            raise ProjectCellContractError("deployment_required must be boolean")
        _reject_credentials(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "biella.task_envelope/v1", "task_id": self.task_id,
            "project_id": self.project_id, "run_id": self.run_id,
            "objective": self.objective, "acceptance_contract": dict(self.acceptance_contract),
            "current_checkpoint_id": self.current_checkpoint_id,
            "allowed_scope": dict(self.allowed_scope), "forbidden_scope": dict(self.forbidden_scope),
            "target_routes": list(self.target_routes), "target_files": list(self.target_files),
            "governing_sources": list(self.governing_sources),
            "current_runtime_facts": dict(self.current_runtime_facts),
            "known_good_state": dict(self.known_good_state), "blockers": list(self.blockers),
            "dependencies": list(self.dependencies), "desired_outputs": list(self.desired_outputs),
            "deployment_required": self.deployment_required,
        }


@dataclass(frozen=True)
class RemoteAssistanceRequest:
    request_id: str
    project_id: str
    run_id: str
    task_id: str
    checkpoint_id: str
    request_type: str
    question_or_action: str
    required_output: Mapping[str, Any]
    current_verified_facts: tuple[str, ...]
    relevant_files_or_snippets: tuple[str, ...]
    blockers: tuple[str, ...]
    constraints: tuple[str, ...]
    do_not_assume: tuple[str, ...]
    online_capabilities_allowed: tuple[str, ...]
    return_format: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("request_id", "run_id", "task_id", "checkpoint_id", "request_type"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name, 256))
        object.__setattr__(self, "project_id", _project_id(self.project_id))
        object.__setattr__(self, "question_or_action", _text(self.question_or_action, "question_or_action", 16384))
        object.__setattr__(self, "required_output", _mapping(self.required_output, "required_output"))
        for field_name in (
            "current_verified_facts", "relevant_files_or_snippets", "blockers", "constraints",
            "do_not_assume", "online_capabilities_allowed",
        ):
            object.__setattr__(self, field_name, _strings(getattr(self, field_name), field_name))
        object.__setattr__(self, "return_format", _mapping(self.return_format, "return_format"))
        _reject_credentials(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "biella.remote_assistance_request/v1",
            "request_id": self.request_id, "project_id": self.project_id,
            "run_id": self.run_id, "task_id": self.task_id,
            "checkpoint_id": self.checkpoint_id, "request_type": self.request_type,
            "question_or_action": self.question_or_action,
            "required_output": dict(self.required_output),
            "current_verified_facts": list(self.current_verified_facts),
            "relevant_files_or_snippets": list(self.relevant_files_or_snippets),
            "blockers": list(self.blockers), "constraints": list(self.constraints),
            "do_not_assume": list(self.do_not_assume),
            "online_capabilities_allowed": list(self.online_capabilities_allowed),
            "return_format": dict(self.return_format),
        }


_REMOTE_STATUSES = {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED"}
_REMOTE_CLASSES = {"FACT", "RECOMMENDATION", "GENERATED_DRAFT", "ACTION_RESULT", "UNVERIFIED"}


@dataclass(frozen=True)
class RemoteAssistanceResponse:
    response_id: str
    request_id: str
    project_id: str
    run_id: str
    task_id: str
    status: str
    findings: tuple[Mapping[str, Any], ...]
    actions_performed: tuple[str, ...]
    artifacts: tuple[str, ...]
    citations_or_sources: tuple[str, ...]
    unresolved: tuple[str, ...]
    suggested_next_actions: tuple[str, ...]
    confidence_or_verification_state: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("response_id", "request_id", "run_id", "task_id"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name, 256))
        object.__setattr__(self, "project_id", _project_id(self.project_id))
        status = _text(self.status, "status", 32).upper()
        if status not in _REMOTE_STATUSES:
            raise ProjectCellContractError("remote response status is unsupported")
        object.__setattr__(self, "status", status)
        findings = tuple(self.findings)
        if len(findings) > 128:
            raise ProjectCellContractError("remote findings are unbounded")
        for finding in findings:
            if not isinstance(finding, Mapping) or finding.get("classification") not in _REMOTE_CLASSES:
                raise ProjectCellContractError("remote finding classification is invalid")
        object.__setattr__(self, "findings", findings)
        for field_name in ("actions_performed", "artifacts", "citations_or_sources", "unresolved", "suggested_next_actions"):
            object.__setattr__(self, field_name, _strings(getattr(self, field_name), field_name))
        object.__setattr__(self, "confidence_or_verification_state", _mapping(self.confidence_or_verification_state, "confidence_or_verification_state"))
        _reject_credentials(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "biella.remote_assistance_response/v1",
            "response_id": self.response_id, "request_id": self.request_id,
            "project_id": self.project_id, "run_id": self.run_id, "task_id": self.task_id,
            "status": self.status, "findings": [dict(item) for item in self.findings],
            "actions_performed": list(self.actions_performed), "artifacts": list(self.artifacts),
            "citations_or_sources": list(self.citations_or_sources), "unresolved": list(self.unresolved),
            "suggested_next_actions": list(self.suggested_next_actions),
            "confidence_or_verification_state": dict(self.confidence_or_verification_state),
        }


_BLOCKER_CATEGORIES = {
    "LOCAL_RUNTIME", "BUILD", "DEPENDENCY", "EXTERNAL_SERVICE", "ONLINE_INFORMATION",
    "CONTENT_GAP", "ASSET_GAP", "DEPLOYMENT", "UNKNOWN_REQUIREMENT", "TOOL_CAPABILITY",
}
_BLOCKER_STATUSES = {"OPEN", "DELEGATED", "RESOLVED", "UNVERIFIED"}


@dataclass(frozen=True)
class BlockerRecord:
    blocker_id: str
    project_id: str
    task_id: str
    category: str
    description: str
    observed_evidence: tuple[str, ...]
    blocks: tuple[str, ...]
    independent_work_remaining: tuple[str, ...]
    suggested_provider: str | None
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocker_id", _text(self.blocker_id, "blocker_id", 256))
        object.__setattr__(self, "project_id", _project_id(self.project_id))
        object.__setattr__(self, "task_id", _text(self.task_id, "task_id", 256))
        category = _text(self.category, "category", 64).upper()
        status = _text(self.status, "status", 32).upper()
        if category not in _BLOCKER_CATEGORIES or status not in _BLOCKER_STATUSES:
            raise ProjectCellContractError("blocker category or status is unsupported")
        object.__setattr__(self, "category", category); object.__setattr__(self, "status", status)
        object.__setattr__(self, "description", _text(self.description, "description", 8192))
        for field_name in ("observed_evidence", "blocks", "independent_work_remaining"):
            object.__setattr__(self, field_name, _strings(getattr(self, field_name), field_name))
        if self.suggested_provider is not None:
            object.__setattr__(self, "suggested_provider", _text(self.suggested_provider, "suggested_provider", 256))
        _reject_credentials(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "biella.project_cell_blocker/v1",
            "blocker_id": self.blocker_id, "project_id": self.project_id,
            "task_id": self.task_id, "category": self.category,
            "description": self.description, "observed_evidence": list(self.observed_evidence),
            "blocks": list(self.blocks), "independent_work_remaining": list(self.independent_work_remaining),
            "suggested_provider": self.suggested_provider, "status": self.status,
        }


@dataclass(frozen=True)
class ProjectCellCheckpoint:
    checkpoint_id: str
    project_id: str
    run_id: str
    task_id: str
    timestamp: str
    phase: str
    objective: str
    repo_state: Mapping[str, Any]
    runtime_state: Mapping[str, Any]
    completed: tuple[str, ...]
    in_progress: tuple[str, ...]
    blocked: tuple[str, ...]
    pending: tuple[str, ...]
    artifacts: tuple[Mapping[str, Any], ...]
    decisions: tuple[str, ...]
    remote_assistance: Mapping[str, Any]
    next_actions: tuple[str, ...]
    do_not_repeat: tuple[str, ...]
    do_not_touch: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("checkpoint_id", "run_id", "task_id", "timestamp", "phase"):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name, 256))
        object.__setattr__(self, "project_id", _project_id(self.project_id))
        object.__setattr__(self, "objective", _text(self.objective, "objective", 8192))
        object.__setattr__(self, "repo_state", _mapping(self.repo_state, "repo_state"))
        object.__setattr__(self, "runtime_state", _mapping(self.runtime_state, "runtime_state"))
        for field_name in ("completed", "in_progress", "blocked", "pending", "decisions", "next_actions", "do_not_repeat", "do_not_touch"):
            object.__setattr__(self, field_name, _strings(getattr(self, field_name), field_name))
        artifacts = tuple(self.artifacts)
        if len(artifacts) > 256 or not all(isinstance(item, Mapping) for item in artifacts):
            raise ProjectCellContractError("artifacts are malformed or unbounded")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "remote_assistance", _mapping(self.remote_assistance, "remote_assistance"))
        _reject_credentials(self.to_payload())

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "biella.project_cell_checkpoint/v1",
            "checkpoint_id": self.checkpoint_id, "project_id": self.project_id,
            "run_id": self.run_id, "task_id": self.task_id, "timestamp": self.timestamp,
            "phase": self.phase, "objective": self.objective,
            "repo_state": dict(self.repo_state), "runtime_state": dict(self.runtime_state),
            "completed": list(self.completed), "in_progress": list(self.in_progress),
            "blocked": list(self.blocked), "pending": list(self.pending),
            "artifacts": [dict(item) for item in self.artifacts], "decisions": list(self.decisions),
            "remote_assistance": dict(self.remote_assistance), "next_actions": list(self.next_actions),
            "do_not_repeat": list(self.do_not_repeat), "do_not_touch": list(self.do_not_touch),
        }
