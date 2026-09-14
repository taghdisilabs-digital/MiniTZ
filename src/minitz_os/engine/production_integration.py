"""Exact, fenced ProductionIntegrationManifest publication for P3-04."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast
from uuid import uuid4

from .artifact import Artifact, ArtifactRef, ArtifactService, ContentRef
from .capability import CapabilityRef
from .checkpoint import CheckpointService, RunCheckpointRef
from .execution import NodeExecutionService
from .graph import GraphRef, GraphService, NodeRef
from .large_scale_pack import ProductionComponentReality, large_scale_graph_recipe
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef, ProjectScopeError, ProjectStore
from .run import ExecutionAttempt, RunRef, RunService
from .task import TaskRef
from .validation import (
    ValidationEvidenceState,
    ValidationResultRef,
    ValidationService,
    ValidationVerdict,
)


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_MANIFEST_ID_PATTERN = re.compile(r"pim_[0-9a-f]{32}")
_COMPONENT_ID_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_OUTPUT_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_CONFIG_KEY_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,2048}")
_IDEMPOTENCY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,255}")
_REQUIRED_CONFIGURATION_KEYS = {
    "production.art-direction",
    "production.performance",
    "production.quality",
}
_REQUIRED_VALIDATION_CAPABILITY_IDS = {
    "production.validation.character-deformation",
    "production.validation.performance",
    "production.validation.render",
    "production.validation.runtime",
    "production.validation.software-test",
}
_PACKAGE_IMPLEMENTATION_REF = "production-pack://large-scale-package/1.0.0"


class ProductionIntegrationError(Exception):
    """Base class for exact production-integration failures."""


class ProductionIntegrationContractError(ProductionIntegrationError, ValueError):
    """The requested manifest or publication is malformed."""


class ProductionIntegrationScopeError(ProductionIntegrationError):
    """A production manifest crossed Project scope."""


class ProductionIntegrationAuthorityError(ProductionIntegrationError, PermissionError):
    """Manifest publication lacks current fenced Run authority."""


class ProductionIntegrationConflictError(ProductionIntegrationError):
    """An immutable manifest or idempotency identity conflicts."""


class ProductionIntegrationNotFoundError(ProductionIntegrationError):
    """An exact manifest identity was not found."""


class ProductionIntegrationIntegrityError(ProductionIntegrationError):
    """Persisted production-integration evidence failed verification."""


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


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _timestamp(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ProductionIntegrationContractError(f"{name} must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProductionIntegrationContractError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductionIntegrationContractError(f"{name} must be timezone-aware")
    return value


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ProductionIntegrationContractError(f"{name} must be sha256")
    return value


def _artifact_payload(ref: ArtifactRef) -> dict[str, object]:
    return {
        "artifact_id": ref.artifact_id,
        "project_ref": ref.project_ref.value,
        "revision": ref.revision,
    }


def _graph_payload(ref: GraphRef) -> dict[str, object]:
    return {
        "graph_id": ref.graph_id,
        "project_ref": ref.project_ref.value,
        "revision": ref.revision,
    }


def _node_payload(ref: NodeRef) -> dict[str, object]:
    return {"graph_ref": _graph_payload(ref.graph_ref), "node_id": ref.node_id}


@dataclass(frozen=True, order=True)
class ProductionIntegrationManifestRef:
    """Exact immutable Project-scoped manifest identity."""

    project_ref: ProjectRef
    manifest_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("project_ref must be ProjectRef")
        if not isinstance(self.manifest_id, str) or _MANIFEST_ID_PATTERN.fullmatch(
            self.manifest_id
        ) is None:
            raise ProductionIntegrationContractError("Manifest identity is malformed")

    @classmethod
    def new(cls, project_ref: ProjectRef) -> "ProductionIntegrationManifestRef":
        return cls(project_ref, f"pim_{uuid4().hex}")

    @property
    def value(self) -> str:
        return f"production-integration-manifest://{self.project_ref.value}/{self.manifest_id}"


@dataclass(frozen=True)
class ProductionArtifactBinding:
    """Exact Artifact revision and verified immutable record digest."""

    role: str
    artifact_ref: ArtifactRef
    artifact_record_sha256: str

    def __post_init__(self) -> None:
        if self.role not in {"integration", "build", "package"}:
            raise ProductionIntegrationContractError("Production Artifact role is unsupported")
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")
        _digest(self.artifact_record_sha256, "artifact_record_sha256")

    def payload(self) -> dict[str, object]:
        return {
            "artifact_record_sha256": self.artifact_record_sha256,
            "artifact_ref": _artifact_payload(self.artifact_ref),
            "role": self.role,
        }


@dataclass(frozen=True)
class ProductionComponentBinding:
    """One exact domain component produced by one successful Graph Node."""

    component_id: str
    domain: str
    capability_ref: CapabilityRef
    reality: ProductionComponentReality
    producer_node_ref: NodeRef
    output_key: str
    artifact_ref: ArtifactRef
    artifact_record_sha256: str

    def __post_init__(self) -> None:
        domains = set(large_scale_graph_recipe().domains)
        if not isinstance(self.component_id, str) or _COMPONENT_ID_PATTERN.fullmatch(
            self.component_id
        ) is None:
            raise ProductionIntegrationContractError("component_id is malformed")
        if self.domain not in domains:
            raise ProductionIntegrationContractError("Component domain is unsupported")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        if not isinstance(self.reality, ProductionComponentReality):
            raise ProductionIntegrationContractError("Component reality is malformed")
        if not isinstance(self.producer_node_ref, NodeRef):
            raise TypeError("producer_node_ref must be NodeRef")
        if not isinstance(self.output_key, str) or _OUTPUT_KEY_PATTERN.fullmatch(
            self.output_key
        ) is None:
            raise ProductionIntegrationContractError("Component output_key is malformed")
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")
        if self.producer_node_ref.project_ref != self.artifact_ref.project_ref:
            raise ProductionIntegrationScopeError("Component Node and Artifact Projects differ")
        _digest(self.artifact_record_sha256, "artifact_record_sha256")

    def payload(self) -> dict[str, object]:
        return {
            "artifact_record_sha256": self.artifact_record_sha256,
            "artifact_ref": _artifact_payload(self.artifact_ref),
            "capability_ref": {
                "capability_id": self.capability_ref.capability_id,
                "version": self.capability_ref.version,
            },
            "component_id": self.component_id,
            "domain": self.domain,
            "output_key": self.output_key,
            "producer_node_ref": _node_payload(self.producer_node_ref),
            "reality": self.reality.value,
        }


@dataclass(frozen=True)
class ProductionValidationBinding:
    """Exact immutable validation result included in final integration."""

    result_ref: ValidationResultRef
    result_record_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.result_ref, ValidationResultRef):
            raise TypeError("result_ref must be ValidationResultRef")
        _digest(self.result_record_sha256, "result_record_sha256")

    def payload(self) -> dict[str, object]:
        return {
            "result_record_sha256": self.result_record_sha256,
            "result_ref": {
                "project_ref": self.result_ref.project_ref.value,
                "result_id": self.result_ref.result_id,
            },
        }


def _freeze_configurations(values: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(values, Mapping):
        raise ProductionIntegrationContractError("project_configuration_refs must be a mapping")
    copied = dict(values)
    if not _REQUIRED_CONFIGURATION_KEYS <= set(copied) or len(copied) > 32:
        raise ProductionIntegrationContractError(
            "Project quality, art-direction, and performance refs are required"
        )
    for key, value in copied.items():
        if not isinstance(key, str) or _CONFIG_KEY_PATTERN.fullmatch(key) is None:
            raise ProductionIntegrationContractError("Project configuration key is malformed")
        if not isinstance(value, str) or _REF_PATTERN.fullmatch(value) is None:
            raise ProductionIntegrationContractError("Project configuration must be an exact ref")
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True)
class ProductionIntegrationManifest:
    """Canonical exact integration state for one Project/Task/Run/Graph."""

    manifest_ref: ProductionIntegrationManifestRef
    task_ref: TaskRef
    task_digest: str
    run_ref: RunRef
    graph_ref: GraphRef
    graph_record_sha256: str
    components: tuple[ProductionComponentBinding, ...]
    integration: ProductionArtifactBinding
    build: ProductionArtifactBinding
    package: ProductionArtifactBinding
    validation_results: tuple[ProductionValidationBinding, ...]
    checkpoint_refs: tuple[RunCheckpointRef, ...]
    project_configuration_refs: Mapping[str, str]
    created_at: str = field(default_factory=_now_utc)
    semantic_digest: str = field(init=False)
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_ref, ProductionIntegrationManifestRef):
            raise TypeError("manifest_ref must be ProductionIntegrationManifestRef")
        if not isinstance(self.task_ref, TaskRef) or not isinstance(self.run_ref, RunRef):
            raise ProductionIntegrationContractError("Manifest requires exact TaskRef and RunRef")
        if not isinstance(self.graph_ref, GraphRef):
            raise TypeError("graph_ref must be GraphRef")
        project_ref = self.manifest_ref.project_ref
        if any(
            ref.project_ref != project_ref
            for ref in (self.task_ref, self.run_ref, self.graph_ref)
        ):
            raise ProductionIntegrationScopeError("Manifest identities crossed Project scope")
        _digest(self.task_digest, "task_digest")
        _digest(self.graph_record_sha256, "graph_record_sha256")
        if not isinstance(self.components, tuple) or not self.components or not all(
            isinstance(item, ProductionComponentBinding) for item in self.components
        ):
            raise ProductionIntegrationContractError("Manifest components are malformed")
        if len(self.components) > 128:
            raise ProductionIntegrationContractError("Manifest components are unbounded")
        components = tuple(sorted(self.components, key=lambda item: item.component_id))
        if len({item.component_id for item in components}) != len(components):
            raise ProductionIntegrationContractError("Manifest component IDs are duplicated")
        recipe = large_scale_graph_recipe()
        if (
            len(components) != len(recipe.domains)
            or len({item.domain for item in components}) != len(components)
            or {item.domain for item in components} != set(recipe.domains)
        ):
            raise ProductionIntegrationContractError("Manifest must cover every production domain")
        expected_realities = {
            item.domain: item.reality for item in recipe.branches
        }
        expected_realities["package"] = ProductionComponentReality.REAL
        expected_capabilities = {
            item.domain: item.capability_ref for item in recipe.branches
        }
        expected_capabilities["package"] = CapabilityRef(
            "production.package",
            "1.0.0",
        )
        if any(
            (
                expected_realities[item.domain]
                is ProductionComponentReality.REFERENCE
                and item.reality is not ProductionComponentReality.REFERENCE
            )
            or item.capability_ref != expected_capabilities[item.domain]
            for item in components
        ):
            raise ProductionIntegrationContractError(
                "Manifest component reality or capability classification differs"
            )
        if any(item.artifact_ref.project_ref != project_ref for item in components):
            raise ProductionIntegrationScopeError("Manifest component crossed Project scope")
        for value, role in (
            (self.integration, "integration"),
            (self.build, "build"),
            (self.package, "package"),
        ):
            if not isinstance(value, ProductionArtifactBinding) or value.role != role:
                raise ProductionIntegrationContractError(f"Manifest {role} binding is malformed")
            if value.artifact_ref.project_ref != project_ref:
                raise ProductionIntegrationScopeError("Manifest Artifact crossed Project scope")
        package_components = [item for item in components if item.domain == "package"]
        if not any(
            item.artifact_ref == self.package.artifact_ref
            and hmac.compare_digest(item.artifact_record_sha256, self.package.artifact_record_sha256)
            for item in package_components
        ):
            raise ProductionIntegrationContractError(
                "Package domain component must bind the exact final package Artifact"
            )
        if not isinstance(self.validation_results, tuple) or not self.validation_results or not all(
            isinstance(item, ProductionValidationBinding) for item in self.validation_results
        ):
            raise ProductionIntegrationContractError("Manifest validation results are malformed")
        validations = tuple(
            sorted(self.validation_results, key=lambda item: item.result_ref.result_id)
        )
        if len(validations) > 128 or len({item.result_ref for item in validations}) != len(
            validations
        ):
            raise ProductionIntegrationContractError("Manifest validation results are duplicated or unbounded")
        if any(item.result_ref.project_ref != project_ref for item in validations):
            raise ProductionIntegrationScopeError("Manifest validation crossed Project scope")
        if not isinstance(self.checkpoint_refs, tuple) or not self.checkpoint_refs or not all(
            isinstance(item, RunCheckpointRef) for item in self.checkpoint_refs
        ):
            raise ProductionIntegrationContractError("Manifest checkpoint refs are malformed")
        checkpoints = tuple(sorted(set(self.checkpoint_refs), key=lambda item: item.checkpoint_id))
        if len(checkpoints) > 64 or any(item.project_ref != project_ref for item in checkpoints):
            raise ProductionIntegrationScopeError("Manifest checkpoint crossed Project scope")
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "validation_results", validations)
        object.__setattr__(self, "checkpoint_refs", checkpoints)
        object.__setattr__(
            self,
            "project_configuration_refs",
            _freeze_configurations(self.project_configuration_refs),
        )
        _timestamp(self.created_at, "created_at")
        semantic = _sha256(self.semantic_payload())
        object.__setattr__(self, "semantic_digest", semantic)
        object.__setattr__(
            self,
            "record_sha256",
            _sha256(
                {
                    "created_at": self.created_at,
                    "manifest_ref": self.manifest_ref.value,
                    "semantic_digest": semantic,
                }
            ),
        )

    @property
    def project_ref(self) -> ProjectRef:
        return self.manifest_ref.project_ref

    @property
    def source_artifact_refs(self) -> tuple[ArtifactRef, ...]:
        refs = {
            *(item.artifact_ref for item in self.components),
            self.integration.artifact_ref,
            self.build.artifact_ref,
            self.package.artifact_ref,
        }
        return tuple(sorted(refs, key=lambda item: (item.artifact_id, item.revision)))

    def semantic_payload(self) -> dict[str, object]:
        return {
            "build": self.build.payload(),
            "checkpoint_refs": [
                {
                    "checkpoint_id": item.checkpoint_id,
                    "project_ref": item.project_ref.value,
                }
                for item in self.checkpoint_refs
            ],
            "components": [item.payload() for item in self.components],
            "graph_record_sha256": self.graph_record_sha256,
            "graph_ref": _graph_payload(self.graph_ref),
            "integration": self.integration.payload(),
            "manifest_ref": {
                "manifest_id": self.manifest_ref.manifest_id,
                "project_ref": self.project_ref.value,
            },
            "package": self.package.payload(),
            "project_configuration_refs": dict(self.project_configuration_refs),
            "run_ref": {
                "project_ref": self.run_ref.project_ref.value,
                "run_id": self.run_ref.run_id,
            },
            "task_digest": self.task_digest,
            "task_ref": {
                "project_ref": self.task_ref.project_ref.value,
                "revision": self.task_ref.revision,
                "task_id": self.task_ref.task_id,
            },
            "validation_results": [item.payload() for item in self.validation_results],
        }

    def payload(self) -> dict[str, object]:
        return {
            "created_at": self.created_at,
            "record_sha256": self.record_sha256,
            "semantic_digest": self.semantic_digest,
            **self.semantic_payload(),
        }

    def serialized(self) -> bytes:
        return _json(self.payload()).encode()


@dataclass(frozen=True)
class ProductionIntegrationPublication:
    """Fenced durable manifest record and its normal Artifact publication."""

    manifest: ProductionIntegrationManifest
    artifact: Artifact
    content_ref: ContentRef
    producer_attempt_id: str
    producer_fence: int
    created_at: str
    record_sha256: str

    def __post_init__(self) -> None:
        if self.artifact.project_ref != self.manifest.project_ref:
            raise ProductionIntegrationScopeError("Publication Artifact crossed Project scope")
        if self.artifact.content_ref != self.content_ref:
            raise ProductionIntegrationIntegrityError("Publication content identity differs")
        if self.artifact.producer_attempt_id != self.producer_attempt_id or self.artifact.producer_fence != self.producer_fence:
            raise ProductionIntegrationIntegrityError("Publication producer fence differs")
        _timestamp(self.created_at, "publication created_at")
        _digest(self.record_sha256, "publication record_sha256")


class ProductionIntegrationManifestService:
    """Publish and read exact manifests without a latest lookup or second scheduler."""

    def __init__(
        self,
        database_path: str | Path,
        object_storage: ObjectStorageBackend,
    ) -> None:
        if not isinstance(object_storage, ObjectStorageBackend):
            raise TypeError("object_storage must be ObjectStorageBackend")
        self.database_path = Path(database_path).resolve()
        self.object_storage = object_storage
        self.projects = ProjectStore(self.database_path)
        self.runs = RunService(self.database_path)
        self.graphs = GraphService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.validations = ValidationService(self.database_path)
        self.checkpoints = CheckpointService(self.database_path, object_storage)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS production_integration_manifests (
                    project_id TEXT NOT NULL,
                    manifest_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    graph_revision INTEGER NOT NULL,
                    graph_record_sha256 TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    manifest_record_sha256 TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL,
                    artifact_record_sha256 TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    content_size INTEGER NOT NULL,
                    content_media_type TEXT NOT NULL,
                    producer_attempt_id TEXT NOT NULL,
                    producer_fence INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, manifest_id),
                    UNIQUE (project_id, manifest_id, record_sha256),
                    FOREIGN KEY (project_id, task_id, task_revision, task_digest)
                        REFERENCES task_revisions(project_id, task_id, revision, canonical_digest)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, run_id)
                        REFERENCES runs(project_id, run_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, graph_id, graph_revision, graph_record_sha256)
                        REFERENCES graph_revisions(project_id, graph_id, revision, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT,
                    FOREIGN KEY (project_id, artifact_id, artifact_revision, artifact_record_sha256)
                        REFERENCES artifact_revisions(project_id, artifact_id, revision, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS production_integration_manifest_claims (
                    project_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    manifest_id TEXT NOT NULL,
                    manifest_record_sha256 TEXT NOT NULL,
                    publication_record_sha256 TEXT NOT NULL,
                    PRIMARY KEY (project_id, idempotency_key),
                    FOREIGN KEY (project_id, manifest_id, publication_record_sha256)
                        REFERENCES production_integration_manifests(project_id, manifest_id, record_sha256)
                        ON UPDATE RESTRICT ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS production_integration_manifests_no_update
                BEFORE UPDATE ON production_integration_manifests
                BEGIN SELECT RAISE(ABORT, 'ProductionIntegrationManifest is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS production_integration_manifests_no_delete
                BEFORE DELETE ON production_integration_manifests
                BEGIN SELECT RAISE(ABORT, 'ProductionIntegrationManifest cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS production_integration_manifest_claims_no_update
                BEFORE UPDATE ON production_integration_manifest_claims
                BEGIN SELECT RAISE(ABORT, 'ProductionIntegrationManifest claim is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS production_integration_manifest_claims_no_delete
                BEFORE DELETE ON production_integration_manifest_claims
                BEGIN SELECT RAISE(ABORT, 'ProductionIntegrationManifest claim cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    @staticmethod
    def _publication_sha256(
        manifest: ProductionIntegrationManifest,
        artifact: Artifact,
        producer_attempt: ExecutionAttempt,
        created_at: str,
    ) -> str:
        return _sha256(
            {
                "artifact_record_sha256": artifact.record_sha256,
                "created_at": created_at,
                "manifest_record_sha256": manifest.record_sha256,
                "producer_attempt_id": producer_attempt.attempt_id,
                "producer_fence": producer_attempt.fence,
            }
        )

    def _validate_manifest_dependencies(
        self,
        access: ProjectAccess,
        manifest: ProductionIntegrationManifest,
        *,
        require_current_context: bool = True,
    ) -> None:
        try:
            project = self.projects.get_project(access, manifest.project_ref)
        except ProjectScopeError as exc:
            raise ProductionIntegrationScopeError("Manifest Project scope mismatch") from exc
        if require_current_context:
            for key, reference in manifest.project_configuration_refs.items():
                if project.configuration_refs.get(key) != reference:
                    raise ProductionIntegrationContractError(
                        "Manifest Project configuration differs from durable Project data"
                    )
        graph = self.graphs.get_graph(access, manifest.graph_ref)
        if (
            graph.task_ref != manifest.task_ref
            or not hmac.compare_digest(graph.task_digest, manifest.task_digest)
            or graph.run_ref != manifest.run_ref
            or not hmac.compare_digest(graph.record_sha256, manifest.graph_record_sha256)
        ):
            raise ProductionIntegrationContractError(
                "Manifest does not bind the exact active Task/Run/Graph record"
            )
        if require_current_context:
            active = self.graphs.get_active_graph(access, manifest.run_ref)
            if graph.graph_ref != active.graph_ref:
                raise ProductionIntegrationContractError(
                    "Manifest Graph is not the active Run Graph"
                )
        artifacts: dict[ArtifactRef, Artifact] = {}
        records: tuple[tuple[ArtifactRef, str, str], ...] = (
            *(
                (
                    item.artifact_ref,
                    item.artifact_record_sha256,
                    (
                        "production.package.output"
                        if item.domain == "package"
                        else f"production.component.{item.domain}"
                    ),
                )
                for item in manifest.components
            ),
            (
                manifest.integration.artifact_ref,
                manifest.integration.artifact_record_sha256,
                "production.integration.output",
            ),
            (
                manifest.build.artifact_ref,
                manifest.build.artifact_record_sha256,
                "production.build.output",
            ),
            (
                manifest.package.artifact_ref,
                manifest.package.artifact_record_sha256,
                "production.package.output",
            ),
        )
        for artifact_ref, record_sha256, expected_role in records:
            artifact = artifacts.get(artifact_ref)
            if artifact is None:
                artifact = self.artifacts.get_artifact(access, artifact_ref)
            if not hmac.compare_digest(artifact.record_sha256, record_sha256):
                raise ProductionIntegrationContractError("Manifest Artifact record digest differs")
            if artifact.role != expected_role:
                raise ProductionIntegrationContractError(
                    "Manifest Artifact role differs from its ProductionPack contract"
                )
            if (
                artifact.producer_run_ref != manifest.run_ref
                or artifact.producer_attempt_id is None
                or artifact.producer_fence is None
            ):
                raise ProductionIntegrationContractError(
                    "Manifest Artifact lacks exact Run provenance"
                )
            artifacts.setdefault(artifact_ref, artifact)
        graph_nodes = {node.node_ref: node for node in graph.nodes}
        recipe_branches = {
            item.domain: item for item in large_scale_graph_recipe().branches
        }
        for component in manifest.components:
            if component.producer_node_ref.graph_ref != manifest.graph_ref:
                raise ProductionIntegrationContractError(
                    "Component producer is not revision-local to the manifest Graph"
                )
            node = graph_nodes.get(component.producer_node_ref)
            if (
                node is None
                or component.capability_ref not in node.required_capabilities
                or (
                    component.domain == "package"
                    and (
                        node.executor_kind != "PRODUCTION_PACKAGE"
                        or node.resource_hints.get("production.reality")
                        != ProductionComponentReality.REAL.value
                        or node.resource_hints.get("production.implementation_ref")
                        != _PACKAGE_IMPLEMENTATION_REF
                    )
                )
                or (
                    component.domain != "package"
                    and (
                        node.executor_kind
                        != "PRODUCTION_DOMAIN_"
                        + component.domain.upper().replace("-", "_")
                        or
                        node.resource_hints.get("production.domain")
                        != component.domain
                    )
                )
            ):
                raise ProductionIntegrationContractError(
                    "Component classification differs from its exact Graph Node"
                )
            node_reality = node.resource_hints.get("production.reality")
            node_implementation = node.resource_hints.get(
                "production.implementation_ref"
            )
            recipe_branch = recipe_branches.get(component.domain)
            if (
                node_reality not in {
                    ProductionComponentReality.REAL.value,
                    ProductionComponentReality.REFERENCE.value,
                }
                or not isinstance(node_implementation, str)
                or _REF_PATTERN.fullmatch(node_implementation) is None
                or component.reality.value != node_reality
                or (
                    node_reality == ProductionComponentReality.REAL.value
                    and (
                        component.domain == "package"
                        and node_implementation != _PACKAGE_IMPLEMENTATION_REF
                        or component.domain != "package"
                        and (
                            recipe_branch is None
                            or recipe_branch.reality
                            is not ProductionComponentReality.REAL
                            or node_implementation
                            != recipe_branch.implementation_ref
                        )
                    )
                )
                or (
                    node_reality == ProductionComponentReality.REFERENCE.value
                    and not node_implementation.startswith("reference://")
                )
            ):
                raise ProductionIntegrationContractError(
                    "Component reality differs from its exact Graph execution binding"
                )
            component_artifact = artifacts[component.artifact_ref]
            receipts = tuple(
                source
                for source in component_artifact.source_refs
                if source.source_kind == "production.implementation"
            )
            if (
                len(receipts) != 1
                or receipts[0].exact_revision != component.reality.value
                or receipts[0].locator != node_implementation
            ):
                raise ProductionIntegrationContractError(
                    "Component reality differs from its exact Artifact execution receipt"
                )
            execution = self.executions.get_node_execution(access, component.producer_node_ref)
            if (
                execution.status != "SUCCEEDED"
                or execution.run_ref != manifest.run_ref
                or execution.task_ref != manifest.task_ref
                or not hmac.compare_digest(execution.task_digest, manifest.task_digest)
                or execution.outputs.get(component.output_key) != component.artifact_ref.value
            ):
                raise ProductionIntegrationContractError(
                    "Component is not the exact successful producer Node output"
                )
        node_by_kind = {node.executor_kind: node for node in graph.nodes}
        for binding, executor_kind, output_key in (
            (manifest.integration, "PRODUCTION_INTEGRATE", "integration"),
            (manifest.build, "PRODUCTION_BUILD", "build"),
            (manifest.package, "PRODUCTION_PACKAGE", "package"),
        ):
            node = node_by_kind.get(executor_kind)
            if node is None:
                raise ProductionIntegrationContractError(
                    "Manifest Graph omits a required integration producer"
                )
            execution = self.executions.get_node_execution(access, node.node_ref)
            if (
                execution.status != "SUCCEEDED"
                or execution.run_ref != manifest.run_ref
                or execution.task_ref != manifest.task_ref
                or execution.outputs.get(output_key) != binding.artifact_ref.value
            ):
                raise ProductionIntegrationContractError(
                    f"Manifest {binding.role} is not the exact successful Graph output"
                )
        integration_sources = set(
            artifacts[manifest.integration.artifact_ref].source_artifact_refs
        )
        required_components = {
            item.artifact_ref for item in manifest.components if item.domain != "package"
        }
        if required_components != integration_sources:
            raise ProductionIntegrationContractError(
                "Integration Artifact provenance differs from exact components"
            )
        if {manifest.integration.artifact_ref} != set(
            artifacts[manifest.build.artifact_ref].source_artifact_refs
        ):
            raise ProductionIntegrationContractError(
                "Build provenance differs from exact integration"
            )
        validation_output_values: set[str] = set()
        for executor_kind in (
            "PRODUCTION_RUNTIME_VALIDATION",
            "PRODUCTION_PERFORMANCE_VALIDATION",
        ):
            node = node_by_kind.get(executor_kind)
            if node is None:
                raise ProductionIntegrationContractError(
                    "Manifest Graph omits a required validation producer"
                )
            execution = self.executions.get_node_execution(access, node.node_ref)
            output = execution.outputs.get("validation")
            if (
                execution.status != "SUCCEEDED"
                or execution.run_ref != manifest.run_ref
                or execution.task_ref != manifest.task_ref
                or output is None
            ):
                raise ProductionIntegrationContractError(
                    "Package validation input is not an exact successful Graph output"
                )
            validation_output_values.add(output)
        package_sources = set(
            artifacts[manifest.package.artifact_ref].source_artifact_refs
        )
        if {item.value for item in package_sources} != {
            manifest.build.artifact_ref.value,
            *validation_output_values,
        }:
            raise ProductionIntegrationContractError(
                "Package provenance differs from exact Graph inputs"
            )
        for validation_artifact_ref in package_sources - {
            manifest.build.artifact_ref
        }:
            validation_artifact = self.artifacts.get_artifact(
                access,
                validation_artifact_ref,
            )
            if (
                validation_artifact.role != "production.validation.result"
                or validation_artifact.producer_run_ref != manifest.run_ref
                or set(validation_artifact.source_artifact_refs)
                != {manifest.build.artifact_ref}
            ):
                raise ProductionIntegrationContractError(
                    "Validation Artifact role or provenance differs from exact build"
                )
        plan_ref = None
        bound_check_ids: set[str] = set()
        required_check_ids: set[str] = set()
        validation_capability_ids: set[str] = set()
        for validation_binding in manifest.validation_results:
            result = self.validations.get_result(
                access,
                validation_binding.result_ref,
            )
            if not hmac.compare_digest(
                result.record_sha256,
                validation_binding.result_record_sha256,
            ):
                raise ProductionIntegrationContractError("Validation result digest differs")
            if (
                result.verdict is not ValidationVerdict.PASS
                or result.evidence_state is not ValidationEvidenceState.CURRENT
            ):
                raise ProductionIntegrationContractError(
                    "Manifest validation is not a current PASS result"
                )
            plan = self.validations.get_plan(access, result.plan_ref)
            if plan_ref is None:
                plan_ref = plan.plan_ref
            elif plan.plan_ref != plan_ref:
                raise ProductionIntegrationContractError(
                    "Manifest validation results crossed exact plans"
                )
            if (
                plan.task_ref != manifest.task_ref
                or not hmac.compare_digest(plan.task_digest, manifest.task_digest)
                or plan.run_ref != manifest.run_ref
                or plan.graph_ref != manifest.graph_ref
                or not hmac.compare_digest(plan.graph_record_sha256, manifest.graph_record_sha256)
            ):
                raise ProductionIntegrationContractError(
                    "Validation result is not bound to the manifest Task/Run/Graph"
                )
            checks = {item.check_id: item for item in plan.checks}
            check = checks.get(result.check_id)
            if check is None or check.capability_ref != result.capability_ref:
                raise ProductionIntegrationContractError(
                    "Validation result differs from its exact planned check"
                )
            if manifest.build.artifact_ref.value not in {
                subject.subject_ref for subject in plan.subjects
            }:
                raise ProductionIntegrationContractError(
                    "Validation plan does not bind the exact build Artifact"
                )
            bound_check_ids.add(result.check_id)
            required_check_ids.update(
                item.check_id for item in plan.checks if item.required
            )
            validation_capability_ids.add(result.capability_ref.capability_id)
            if (
                result.capability_ref.capability_id
                == "production.validation.performance"
            ):
                maximum = check.parameters.get("max_build_size_bytes")
                build_artifact = artifacts[manifest.build.artifact_ref]
                measurements = {
                    measurement.name: measurement
                    for measurement in result.metrics
                }
                build_size = measurements.get("build.size_bytes")
                if (
                    check.parameters.get("budget_ref")
                    != manifest.project_configuration_refs["production.performance"]
                    or not isinstance(maximum, (int, float))
                    or isinstance(maximum, bool)
                    or float(maximum) <= 0
                    or build_artifact.content_ref is None
                    or build_size is None
                    or build_size.unit != "bytes"
                    or build_size.measurement_source_ref
                    != manifest.build.artifact_ref.value
                    or build_size.value
                    != float(build_artifact.content_ref.size_bytes)
                    or build_size.value > float(maximum)
                    or result.implementation_ref.startswith("reference-validator://")
                ):
                    raise ProductionIntegrationContractError(
                        "Performance validation does not measure the exact Project budget"
                    )
        if (
            required_check_ids - bound_check_ids
            or not _REQUIRED_VALIDATION_CAPABILITY_IDS
            <= validation_capability_ids
        ):
            raise ProductionIntegrationContractError(
                "Manifest validation coverage is incomplete"
            )
        for checkpoint_ref in manifest.checkpoint_refs:
            checkpoint = self.checkpoints.get_checkpoint(access, checkpoint_ref)
            if (
                checkpoint.run_ref != manifest.run_ref
                or checkpoint.task_ref != manifest.task_ref
                or not hmac.compare_digest(checkpoint.task_digest, manifest.task_digest)
                or checkpoint.graph_ref.graph_id != manifest.graph_ref.graph_id
                or checkpoint.graph_ref.revision > manifest.graph_ref.revision
            ):
                raise ProductionIntegrationContractError(
                    "Checkpoint is not compatible with the manifest Run history"
                )

    def publish(
        self,
        access: ProjectAccess,
        manifest: ProductionIntegrationManifest,
        *,
        producer_attempt: ExecutionAttempt,
        idempotency_key: str,
    ) -> ProductionIntegrationPublication:
        if not isinstance(manifest, ProductionIntegrationManifest):
            raise TypeError("manifest must be ProductionIntegrationManifest")
        if not isinstance(producer_attempt, ExecutionAttempt):
            raise TypeError("producer_attempt must be ExecutionAttempt")
        if not isinstance(idempotency_key, str) or _IDEMPOTENCY_PATTERN.fullmatch(
            idempotency_key
        ) is None:
            raise ProductionIntegrationContractError("idempotency_key is malformed")
        if producer_attempt.run_ref != manifest.run_ref:
            raise ProductionIntegrationAuthorityError("Producer attempt belongs to another Run")
        try:
            self.projects.get_project(access, manifest.project_ref)
        except ProjectScopeError as exc:
            raise ProductionIntegrationScopeError(
                "Manifest Project scope mismatch"
            ) from exc
        replay_connection = self._connect()
        try:
            replay = replay_connection.execute(
                """
                SELECT request_sha256,manifest_id,manifest_record_sha256,
                       publication_record_sha256
                FROM production_integration_manifest_claims
                WHERE project_id=? AND idempotency_key=?
                """,
                (manifest.project_ref.value, idempotency_key),
            ).fetchone()
        finally:
            replay_connection.close()
        if replay is not None:
            if (
                not hmac.compare_digest(
                    cast(str, replay["request_sha256"]),
                    manifest.record_sha256,
                )
                or replay["manifest_id"] != manifest.manifest_ref.manifest_id
                or not hmac.compare_digest(
                    cast(str, replay["manifest_record_sha256"]),
                    manifest.record_sha256,
                )
            ):
                raise ProductionIntegrationConflictError(
                    "Manifest idempotency key has different exact semantics"
                )
            publication = self.get(access, manifest.manifest_ref)
            if not hmac.compare_digest(
                publication.record_sha256,
                cast(str, replay["publication_record_sha256"]),
            ):
                raise ProductionIntegrationIntegrityError(
                    "Manifest replay claim differs from publication"
                )
            return publication
        self._validate_manifest_dependencies(access, manifest)
        payload = manifest.serialized()
        content_ref = ContentRef.from_bytes(
            payload,
            media_type="application/vnd.minitz.production-integration-manifest+json",
        )
        stored = self.object_storage.put(
            payload,
            media_type=content_ref.media_type,
            expected_digest=content_ref.digest,
            expected_size=content_ref.size_bytes,
        )
        if stored != content_ref:
            raise ProductionIntegrationIntegrityError("Object storage changed manifest content")

        connection = self._connect()
        published_ref: ProductionIntegrationManifestRef | None = None
        try:
            connection.execute("BEGIN IMMEDIATE")
            project = self.projects._fetch_project(
                connection,
                manifest.project_ref,
            )
            if any(
                project.configuration_refs.get(key) != reference
                for key, reference in manifest.project_configuration_refs.items()
            ):
                raise ProductionIntegrationConflictError(
                    "Project configuration changed during manifest publication"
                )
            run = self.runs._fetch_run(connection, producer_attempt.run_ref)
            if run.status == "RUNNING":
                try:
                    run = self.runs.assert_current_run_authority_in_transaction(
                        connection,
                        access,
                        producer_attempt,
                    )
                except Exception as exc:
                    raise ProductionIntegrationAuthorityError(
                        "Manifest publication requires current fenced Run authority"
                    ) from exc
            elif run.status == "SUCCEEDED":
                persisted_attempt = self.runs._fetch_attempt(
                    connection,
                    run,
                    producer_attempt.attempt_id,
                )
                if (
                    run.current_attempt_id != producer_attempt.attempt_id
                    or run.current_attempt_number != producer_attempt.attempt_number
                    or run.current_fence != producer_attempt.fence
                    or persisted_attempt.record_sha256 != producer_attempt.record_sha256
                    or persisted_attempt.completed_at is None
                    or persisted_attempt.terminal_outcome != "SUCCEEDED"
                ):
                    raise ProductionIntegrationAuthorityError(
                        "Terminal manifest closeout requires the exact final successful fence"
                    )
            else:
                raise ProductionIntegrationAuthorityError(
                    "Failed or cancelled Run cannot publish an integration manifest"
                )
            if (
                run.run_ref != manifest.run_ref
                or run.task_ref != manifest.task_ref
                or not hmac.compare_digest(run.task_digest, manifest.task_digest)
            ):
                raise ProductionIntegrationAuthorityError(
                    "Producer authority differs from manifest Task/Run"
                )
            head = connection.execute(
                """
                SELECT b.graph_id,b.graph_revision,b.graph_record_sha256
                FROM run_graph_heads AS h
                JOIN run_graph_bindings AS b
                  ON b.project_id=h.project_id AND b.run_id=h.run_id
                 AND b.graph_id=h.graph_id
                 AND b.graph_revision=h.current_graph_revision
                 AND b.record_sha256=h.current_binding_sha256
                WHERE h.project_id=? AND h.run_id=?
                """,
                (manifest.project_ref.value, manifest.run_ref.run_id),
            ).fetchone()
            if (
                head is None
                or head["graph_id"] != manifest.graph_ref.graph_id
                or head["graph_revision"] != manifest.graph_ref.revision
                or head["graph_record_sha256"] != manifest.graph_record_sha256
            ):
                raise ProductionIntegrationAuthorityError(
                    "Manifest Graph is not the current fenced Run Graph"
                )
            request_sha256 = manifest.record_sha256
            claim = connection.execute(
                """
                SELECT request_sha256,manifest_id,manifest_record_sha256
                FROM production_integration_manifest_claims
                WHERE project_id=? AND idempotency_key=?
                """,
                (manifest.project_ref.value, idempotency_key),
            ).fetchone()
            if claim is not None:
                if (
                    not hmac.compare_digest(cast(str, claim["request_sha256"]), request_sha256)
                    or claim["manifest_id"] != manifest.manifest_ref.manifest_id
                    or not hmac.compare_digest(
                        cast(str, claim["manifest_record_sha256"]),
                        manifest.record_sha256,
                    )
                ):
                    raise ProductionIntegrationConflictError(
                        "Manifest idempotency key has different exact semantics"
                    )
                published_ref = manifest.manifest_ref
                connection.commit()
            else:
                existing = connection.execute(
                    """
                    SELECT manifest_record_sha256,record_sha256
                    FROM production_integration_manifests
                    WHERE project_id=? AND manifest_id=?
                    """,
                    (manifest.project_ref.value, manifest.manifest_ref.manifest_id),
                ).fetchone()
                if existing is not None:
                    if not hmac.compare_digest(
                        cast(str, existing["manifest_record_sha256"]),
                        manifest.record_sha256,
                    ):
                        raise ProductionIntegrationConflictError(
                            "Manifest identity already has different exact content"
                        )
                    connection.execute(
                        """
                        INSERT INTO production_integration_manifest_claims
                        VALUES (?,?,?,?,?,?)
                        """,
                        (
                            manifest.project_ref.value,
                            idempotency_key,
                            request_sha256,
                            manifest.manifest_ref.manifest_id,
                            manifest.record_sha256,
                            existing["record_sha256"],
                        ),
                    )
                    published_ref = manifest.manifest_ref
                    connection.commit()
                else:
                    ArtifactService._verify_source_artifacts_in_transaction(
                        connection,
                        manifest.project_ref,
                        manifest.source_artifact_refs,
                    )
                    created_at = ArtifactService._database_now(connection)
                    artifact = Artifact(
                        ArtifactRef(manifest.project_ref, f"art_{uuid4().hex}", 1),
                        "production.integration.manifest",
                        content_ref,
                        (),
                        manifest.source_artifact_refs,
                        (),
                        "production.integration.manifest",
                        manifest.run_ref,
                        producer_attempt.attempt_id,
                        producer_attempt.fence,
                        {},
                        created_at,
                    )
                    ArtifactService._insert_artifact(connection, artifact)
                    ArtifactService._insert_source_bindings(connection, artifact)
                    ArtifactService._insert_derivation(connection, artifact)
                    ArtifactService._insert_initial_head(connection, artifact)
                    publication_sha256 = self._publication_sha256(
                        manifest,
                        artifact,
                        producer_attempt,
                        created_at,
                    )
                    connection.execute(
                        """
                        INSERT INTO production_integration_manifests VALUES (
                            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                        )
                        """,
                        (
                            manifest.project_ref.value,
                            manifest.manifest_ref.manifest_id,
                            manifest.task_ref.task_id,
                            manifest.task_ref.revision,
                            manifest.task_digest,
                            manifest.run_ref.run_id,
                            manifest.graph_ref.graph_id,
                            manifest.graph_ref.revision,
                            manifest.graph_record_sha256,
                            payload.decode(),
                            manifest.semantic_digest,
                            manifest.record_sha256,
                            artifact.artifact_id,
                            artifact.revision,
                            artifact.record_sha256,
                            content_ref.digest,
                            content_ref.size_bytes,
                            content_ref.media_type,
                            producer_attempt.attempt_id,
                            producer_attempt.fence,
                            created_at,
                            publication_sha256,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO production_integration_manifest_claims
                        VALUES (?,?,?,?,?,?)
                        """,
                        (
                            manifest.project_ref.value,
                            idempotency_key,
                            request_sha256,
                            manifest.manifest_ref.manifest_id,
                            manifest.record_sha256,
                            publication_sha256,
                        ),
                    )
                    published_ref = manifest.manifest_ref
                    connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ProductionIntegrationConflictError(
                "Manifest publication conflicts with immutable state"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        if published_ref is None:
            raise ProductionIntegrationIntegrityError("Manifest publication did not commit")
        return self.get(access, published_ref)

    def get(
        self,
        access: ProjectAccess,
        manifest_ref: ProductionIntegrationManifestRef,
    ) -> ProductionIntegrationPublication:
        if not isinstance(manifest_ref, ProductionIntegrationManifestRef):
            raise TypeError("manifest_ref must be ProductionIntegrationManifestRef")
        try:
            self.projects.get_project(access, manifest_ref.project_ref)
        except ProjectScopeError as exc:
            raise ProductionIntegrationScopeError("Manifest Project scope mismatch") from exc
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT * FROM production_integration_manifests
                WHERE project_id=? AND manifest_id=?
                """,
                (manifest_ref.project_ref.value, manifest_ref.manifest_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ProductionIntegrationNotFoundError(
                f"Manifest {manifest_ref.value} was not found"
            )
        try:
            decoded = cast(object, json.loads(cast(str, row["manifest_json"])))
            manifest = self._manifest_from_payload(decoded)
            content_ref = ContentRef(
                "sha256",
                cast(str, row["content_digest"]),
                cast(int, row["content_size"]),
                cast(str, row["content_media_type"]),
            )
            artifact_ref = ArtifactRef(
                manifest_ref.project_ref,
                cast(str, row["artifact_id"]),
                cast(int, row["artifact_revision"]),
            )
            artifact = self.artifacts.get_artifact(access, artifact_ref)
            created_at = cast(str, row["created_at"])
            publication_sha256 = _sha256(
                {
                    "artifact_record_sha256": artifact.record_sha256,
                    "created_at": created_at,
                    "manifest_record_sha256": manifest.record_sha256,
                    "producer_attempt_id": cast(str, row["producer_attempt_id"]),
                    "producer_fence": cast(int, row["producer_fence"]),
                }
            )
        except (KeyError, TypeError, ValueError, ProductionIntegrationError) as exc:
            raise ProductionIntegrationIntegrityError(
                "Persisted manifest is malformed"
            ) from exc
        if (
            manifest.manifest_ref != manifest_ref
            or row["task_id"] != manifest.task_ref.task_id
            or row["task_revision"] != manifest.task_ref.revision
            or not hmac.compare_digest(
                cast(str, row["task_digest"]),
                manifest.task_digest,
            )
            or row["run_id"] != manifest.run_ref.run_id
            or row["graph_id"] != manifest.graph_ref.graph_id
            or row["graph_revision"] != manifest.graph_ref.revision
            or not hmac.compare_digest(
                cast(str, row["graph_record_sha256"]),
                manifest.graph_record_sha256,
            )
            or not hmac.compare_digest(manifest.semantic_digest, cast(str, row["semantic_digest"]))
            or not hmac.compare_digest(manifest.record_sha256, cast(str, row["manifest_record_sha256"]))
            or artifact.record_sha256 != row["artifact_record_sha256"]
            or artifact.content_ref != content_ref
            or not hmac.compare_digest(publication_sha256, cast(str, row["record_sha256"]))
        ):
            raise ProductionIntegrationIntegrityError("Persisted manifest integrity verification failed")
        payload = self.object_storage.read(content_ref)
        if payload != manifest.serialized() or payload.decode() != row["manifest_json"]:
            raise ProductionIntegrationIntegrityError("Manifest content object differs from record")
        expected_sources = set(manifest.source_artifact_refs)
        if set(artifact.source_artifact_refs) != expected_sources:
            raise ProductionIntegrationIntegrityError("Manifest Artifact provenance differs")
        try:
            self._validate_manifest_dependencies(
                access,
                manifest,
                require_current_context=False,
            )
        except Exception as exc:
            raise ProductionIntegrationIntegrityError(
                "Manifest exact dependency readback failed"
            ) from exc
        return ProductionIntegrationPublication(
            manifest,
            artifact,
            content_ref,
            cast(str, row["producer_attempt_id"]),
            cast(int, row["producer_fence"]),
            created_at,
            publication_sha256,
        )

    @classmethod
    def _manifest_from_payload(cls, value: object) -> ProductionIntegrationManifest:
        if not isinstance(value, dict):
            raise ProductionIntegrationIntegrityError("Manifest payload is not an object")

        def project(payload: object) -> ProjectRef:
            if not isinstance(payload, str):
                raise ProductionIntegrationIntegrityError("Project ref is malformed")
            return ProjectRef(payload)

        def graph(payload: object) -> GraphRef:
            if not isinstance(payload, dict):
                raise ProductionIntegrationIntegrityError("Graph ref is malformed")
            return GraphRef(
                project(payload["project_ref"]),
                cast(str, payload["graph_id"]),
                cast(int, payload["revision"]),
            )

        def artifact(payload: object) -> ArtifactRef:
            if not isinstance(payload, dict):
                raise ProductionIntegrationIntegrityError("Artifact ref is malformed")
            return ArtifactRef(
                project(payload["project_ref"]),
                cast(str, payload["artifact_id"]),
                cast(int, payload["revision"]),
            )

        def artifact_binding(payload: object) -> ProductionArtifactBinding:
            if not isinstance(payload, dict):
                raise ProductionIntegrationIntegrityError("Artifact binding is malformed")
            return ProductionArtifactBinding(
                cast(str, payload["role"]),
                artifact(payload["artifact_ref"]),
                cast(str, payload["artifact_record_sha256"]),
            )

        manifest_data = value["manifest_ref"]
        task_data = value["task_ref"]
        run_data = value["run_ref"]
        if not all(isinstance(item, dict) for item in (manifest_data, task_data, run_data)):
            raise ProductionIntegrationIntegrityError("Manifest identity payload is malformed")
        components: list[ProductionComponentBinding] = []
        for item in cast(list[object], value["components"]):
            if not isinstance(item, dict) or not isinstance(item["capability_ref"], dict):
                raise ProductionIntegrationIntegrityError("Component payload is malformed")
            node_data = item["producer_node_ref"]
            if not isinstance(node_data, dict):
                raise ProductionIntegrationIntegrityError("Component Node payload is malformed")
            capability_data = cast(dict[str, object], item["capability_ref"])
            components.append(
                ProductionComponentBinding(
                    cast(str, item["component_id"]),
                    cast(str, item["domain"]),
                    CapabilityRef(
                        cast(str, capability_data["capability_id"]),
                        cast(str, capability_data["version"]),
                    ),
                    ProductionComponentReality(cast(str, item["reality"])),
                    NodeRef(graph(node_data["graph_ref"]), cast(str, node_data["node_id"])),
                    cast(str, item["output_key"]),
                    artifact(item["artifact_ref"]),
                    cast(str, item["artifact_record_sha256"]),
                )
            )
        validations: list[ProductionValidationBinding] = []
        for item in cast(list[object], value["validation_results"]):
            if not isinstance(item, dict) or not isinstance(item["result_ref"], dict):
                raise ProductionIntegrationIntegrityError("Validation payload is malformed")
            result_data = cast(dict[str, object], item["result_ref"])
            validations.append(
                ProductionValidationBinding(
                    ValidationResultRef(
                        project(result_data["project_ref"]),
                        cast(str, result_data["result_id"]),
                    ),
                    cast(str, item["result_record_sha256"]),
                )
            )
        checkpoints: list[RunCheckpointRef] = []
        for item in cast(list[object], value["checkpoint_refs"]):
            if not isinstance(item, dict):
                raise ProductionIntegrationIntegrityError("Checkpoint payload is malformed")
            checkpoints.append(
                RunCheckpointRef(
                    project(item["project_ref"]),
                    cast(str, item["checkpoint_id"]),
                )
            )
        manifest = ProductionIntegrationManifest(
            ProductionIntegrationManifestRef(
                project(cast(dict[str, object], manifest_data)["project_ref"]),
                cast(str, cast(dict[str, object], manifest_data)["manifest_id"]),
            ),
            TaskRef(
                project(cast(dict[str, object], task_data)["project_ref"]),
                cast(str, cast(dict[str, object], task_data)["task_id"]),
                cast(int, cast(dict[str, object], task_data)["revision"]),
            ),
            cast(str, value["task_digest"]),
            RunRef(
                project(cast(dict[str, object], run_data)["project_ref"]),
                cast(str, cast(dict[str, object], run_data)["run_id"]),
            ),
            graph(value["graph_ref"]),
            cast(str, value["graph_record_sha256"]),
            tuple(components),
            artifact_binding(value["integration"]),
            artifact_binding(value["build"]),
            artifact_binding(value["package"]),
            tuple(validations),
            tuple(checkpoints),
            cast(dict[str, str], value["project_configuration_refs"]),
            cast(str, value["created_at"]),
        )
        if (
            not hmac.compare_digest(manifest.semantic_digest, cast(str, value["semantic_digest"]))
            or not hmac.compare_digest(manifest.record_sha256, cast(str, value["record_sha256"]))
        ):
            raise ProductionIntegrationIntegrityError("Manifest embedded digest differs")
        return manifest
