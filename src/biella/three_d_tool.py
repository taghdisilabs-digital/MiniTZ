"""Project-scoped, provider-neutral 3D tool adapter contracts.

The public records contain no DCC SDK values.  Blender's ``bpy`` API is kept in
the private driver module executed by Blender itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable

from .artifact import (
    Artifact,
    ArtifactError,
    ArtifactRef,
    ArtifactService,
    ContentRef,
    SourceRef,
)
from .character_pack import (
    CharacterContractError,
    CharacterRigRef,
    CharacterSpecification,
)
from .animation_pack import (
    AnimationClip,
    AnimationContractError,
    BoneMapping,
    RetargetMapping,
    RetargetRequest,
)
from .environment_pack import (
    EnvironmentContractError,
    EnvironmentIntegrationManifest,
    PlacedAsset,
)
from .capability import CapabilityRef
from .call_ledger import ToolCallRef
from .execution import (
    NodeExecutionAttempt,
    NodeExecutionAuthorityError,
    NodeExecutionError,
    NodeExecutionService,
)
from .filesystem import (
    FilesystemAdapter,
    FilesystemError,
    FilesystemRootRef,
)
from .object_store import ObjectStorageBackend, ObjectStorageError
from .process import (
    ManagedProcessAdapter,
    NetworkPolicy,
    ProcessError,
    ProcessExecutionRequest,
    ProcessFailure,
    ProcessResourcePolicy,
    ProcessResult,
    ProcessStatus,
)
from .project import (
    ProjectAccess,
    ProjectIntegrityError,
    ProjectNotFoundError,
    ProjectRef,
    ProjectScopeError,
    ProjectStore,
)
from .run import ExecutionAttempt, RunAuthorityError, RunError, RunService
from .scheduler import (
    ResourceAllocationRef,
    Scheduler,
    SchedulerError,
)
from .resource import ResourceError, ResourceService
from .workspace import (
    WorkspaceError,
    WorkspaceRef,
    WorkspaceService,
    WorkspaceSnapshotRef,
)


_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_KEY = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_ROLE = re.compile(r"3d\.[a-z][a-z0-9_.-]{0,123}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){0,3}(?:[-+][A-Za-z0-9_.-]+)?")
_Scalar = str | int | float | bool
_OPERATION_ROLES: Mapping[ThreeDOperation, frozenset[str]]


class ThreeDError(Exception):
    """Base class for provider-neutral 3D tool failures."""


class ThreeDContractError(ThreeDError, ValueError):
    """A 3D identity, request, or result is malformed."""


class ThreeDScopeError(ThreeDError):
    """3D evidence crossed Project or Workspace scope."""


class ThreeDAuthorityError(ThreeDError, PermissionError):
    """The exact live Node attempt lacks 3D authority."""


class ThreeDConflictError(ThreeDError):
    """A durable 3D idempotency identity conflicts."""


class ThreeDIntegrityError(ThreeDError):
    """Persisted or tool-produced 3D evidence failed verification."""


class ThreeDOperation(str, Enum):
    INSPECT = "inspect"
    MODEL = "model"
    MESH_EDIT = "mesh_edit"
    TOPOLOGY = "topology"
    UV = "uv"
    MATERIAL = "material"
    RIG = "rig"
    SKIN = "skin"
    DEFORM = "deform"
    ANIMATE = "animate"
    RETARGET = "retarget"
    BAKE = "bake"
    ENVIRONMENT = "environment"
    SCENE = "scene"
    CONVERT = "convert"
    OPTIMIZE = "optimize"
    VALIDATE = "validate"
    PREVIEW = "preview"

    @property
    def capability_id(self) -> str:
        if self in {
            ThreeDOperation.RIG,
            ThreeDOperation.SKIN,
            ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
        }:
            return "3d.model"
        return f"3d.{self.value}"


class ThreeDReality(str, Enum):
    REAL = "REAL"
    REFERENCE = "REFERENCE"
    NOT_RUN = "NOT_RUN"


class ThreeDStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"


_OPERATION_ROLES = MappingProxyType(
    {
        ThreeDOperation.INSPECT: frozenset({"3d.inspection"}),
        ThreeDOperation.MODEL: frozenset({"3d.mesh", "3d.scene"}),
        ThreeDOperation.MESH_EDIT: frozenset({"3d.mesh", "3d.scene"}),
        ThreeDOperation.TOPOLOGY: frozenset({"3d.mesh", "3d.scene"}),
        ThreeDOperation.UV: frozenset({"3d.mesh", "3d.scene", "3d.uv-data"}),
        ThreeDOperation.MATERIAL: frozenset({"3d.material", "3d.scene"}),
        ThreeDOperation.RIG: frozenset({"3d.mesh", "3d.rig", "3d.scene"}),
        ThreeDOperation.SKIN: frozenset({"3d.mesh", "3d.rig", "3d.skin", "3d.scene"}),
        ThreeDOperation.DEFORM: frozenset({"3d.mesh", "3d.rig", "3d.skin", "3d.deformation", "3d.scene"}),
        ThreeDOperation.ANIMATE: frozenset({"3d.animation", "3d.rig", "3d.scene"}),
        ThreeDOperation.RETARGET: frozenset({"3d.animation", "3d.retarget-mapping", "3d.rig", "3d.scene"}),
        ThreeDOperation.BAKE: frozenset({"3d.animation", "3d.rig", "3d.scene"}),
        ThreeDOperation.ENVIRONMENT: frozenset({"3d.environment", "3d.environment-manifest", "3d.scene", "3d.collision", "3d.navigation", "3d.partition", "3d.lod"}),
        ThreeDOperation.SCENE: frozenset({"3d.scene"}),
        ThreeDOperation.CONVERT: frozenset({"3d.interchange-export"}),
        ThreeDOperation.OPTIMIZE: frozenset({"3d.mesh", "3d.scene"}),
        ThreeDOperation.VALIDATE: frozenset({"3d.validation"}),
        ThreeDOperation.PREVIEW: frozenset({"3d.preview"}),
    }
)
_KNOWN_ROLES = frozenset(
    role for roles in _OPERATION_ROLES.values() for role in roles
)

_OUTPUT_MEDIA = MappingProxyType(
    {
        ThreeDOperation.INSPECT: frozenset({(".json", "application/json")}),
        ThreeDOperation.MODEL: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.MESH_EDIT: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.TOPOLOGY: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.UV: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.MATERIAL: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.RIG: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.SKIN: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.DEFORM: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.ANIMATE: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.RETARGET: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.BAKE: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.ENVIRONMENT: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.SCENE: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.CONVERT: frozenset(
            {
                (".glb", "model/gltf-binary"),
                (".gltf", "model/gltf+json"),
            }
        ),
        ThreeDOperation.OPTIMIZE: frozenset({(".blend", "application/x-blender")}),
        ThreeDOperation.VALIDATE: frozenset({(".json", "application/json")}),
        ThreeDOperation.PREVIEW: frozenset({(".png", "image/png")}),
    }
)


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant {value} is forbidden")


def _strict_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key is forbidden")
        result[key] = value
    return result


def _strict_json_loads(value: str | bytes) -> object:
    return json.loads(
        value,
        object_pairs_hook=_strict_json_pairs,
        parse_constant=_reject_json_constant,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _text(value: object, name: str, maximum: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
        or len(value.encode()) > maximum
    ):
        raise ThreeDContractError(f"{name} is malformed or unbounded")
    return value


def _ref(value: object, name: str) -> str:
    if not isinstance(value, str) or _ABSOLUTE_REF.fullmatch(value) is None:
        raise ThreeDContractError(f"{name} must be a bounded absolute reference")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ThreeDContractError(f"{name} must be an exact sha256 digest")
    return value


def _relative(value: object, name: str) -> str:
    text = _text(value, name, 2048)
    candidate = PurePosixPath(text)
    if (
        text.startswith("/")
        or "\\" in text
        or tuple(candidate.parts) != tuple(text.split("/"))
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ThreeDContractError(f"{name} must be a canonical relative path")
    return text


def _operation_relative(value: object, name: str) -> str:
    text = _relative(value, name)
    if PurePosixPath(text).parts[0].startswith(".biella-three-d-"):
        raise ThreeDContractError(
            f"{name} overlaps the reserved 3D adapter control namespace"
        )
    return text


def _reason(value: object) -> str:
    source = value if isinstance(value, str) else "3D tool failed without a textual reason"
    bounded = "".join(character if ord(character) >= 32 else " " for character in source)
    bounded = " ".join(bounded.split())[:4096]
    return bounded or "3D tool failed without a textual reason"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _config(value: Mapping[str, _Scalar]) -> Mapping[str, _Scalar]:
    if not isinstance(value, Mapping) or len(value) > 64:
        raise ThreeDContractError("3D operation configuration is malformed or unbounded")
    copied: dict[str, _Scalar] = {}
    for key, item in value.items():
        if not isinstance(key, str) or _KEY.fullmatch(key) is None:
            raise ThreeDContractError("3D operation configuration key is malformed")
        if isinstance(item, bool):
            copied[key] = item
        elif isinstance(item, int):
            if abs(item) > 2**53:
                raise ThreeDContractError("3D integer configuration is unbounded")
            copied[key] = item
        elif isinstance(item, float):
            if item != item or item in {float("inf"), float("-inf")}:
                raise ThreeDContractError("3D float configuration is non-finite")
            copied[key] = item
        elif isinstance(item, str) and len(item.encode()) <= 4096 and "\x00" not in item:
            copied[key] = item
        else:
            raise ThreeDContractError("3D operation configuration value is malformed")
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


@dataclass(frozen=True, order=True)
class ThreeDPluginIdentity:
    """Exact adapter-local DCC plug-in identity."""

    name: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "3D plugin name", 256))
        if not isinstance(self.version, str) or _VERSION.fullmatch(self.version) is None:
            raise ThreeDContractError("3D plugin version is malformed")
        _sha(self.digest, "3D plugin digest")

    def payload(self) -> dict[str, str]:
        return {"digest": self.digest, "name": self.name, "version": self.version}


@dataclass(frozen=True)
class ThreeDToolIdentity:
    """Exact Project, DCC executable, plug-in, and runtime identity."""

    project_ref: ProjectRef
    adapter_ref: str
    tool_name: str
    tool_version: str
    executable_path: str
    executable_sha256: str
    driver_sha256: str
    plugins: tuple[ThreeDPluginIdentity, ...]
    runtime_ref: str
    sandbox_launcher_path: str | None = None
    sandbox_launcher_sha256: str | None = None
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("3D tool identity requires exact ProjectRef")
        object.__setattr__(self, "adapter_ref", _ref(self.adapter_ref, "3D adapter_ref"))
        object.__setattr__(self, "tool_name", _text(self.tool_name, "3D tool name", 256))
        object.__setattr__(self, "tool_version", _text(self.tool_version, "3D tool version", 512))
        executable = _text(self.executable_path, "3D executable path", 2048)
        if not executable.startswith("/") or PurePosixPath(executable).as_posix() != executable:
            raise ThreeDContractError("3D executable path must be exact and absolute")
        _sha(self.executable_sha256, "3D executable digest")
        _sha(self.driver_sha256, "3D driver digest")
        if (
            not isinstance(self.plugins, tuple)
            or len(self.plugins) > 128
            or len(set(self.plugins)) != len(self.plugins)
            or any(not isinstance(item, ThreeDPluginIdentity) for item in self.plugins)
        ):
            raise ThreeDContractError("3D plugin identities are duplicated or unbounded")
        object.__setattr__(self, "plugins", tuple(sorted(self.plugins)))
        object.__setattr__(self, "runtime_ref", _ref(self.runtime_ref, "3D runtime_ref"))
        if (self.sandbox_launcher_path is None) != (
            self.sandbox_launcher_sha256 is None
        ):
            raise ThreeDContractError(
                "3D sandbox launcher path and digest must be specified together"
            )
        if self.sandbox_launcher_path is not None:
            launcher = _text(
                self.sandbox_launcher_path,
                "3D sandbox launcher path",
                2048,
            )
            if (
                not launcher.startswith("/")
                or PurePosixPath(launcher).as_posix() != launcher
            ):
                raise ThreeDContractError(
                    "3D sandbox launcher path must be exact and absolute"
                )
            _sha(
                cast(str, self.sandbox_launcher_sha256),
                "3D sandbox launcher digest",
            )
        object.__setattr__(self, "semantic_digest", _digest(self.payload()))

    @property
    def process_executable_path(self) -> str:
        return (
            self.executable_path
            if self.sandbox_launcher_path is None
            else self.sandbox_launcher_path
        )

    @property
    def process_executable_sha256(self) -> str:
        return (
            self.executable_sha256
            if self.sandbox_launcher_sha256 is None
            else self.sandbox_launcher_sha256
        )

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "executable_path": self.executable_path,
            "executable_sha256": self.executable_sha256,
            "driver_sha256": self.driver_sha256,
            "plugins": [item.payload() for item in self.plugins],
            "project_ref": self.project_ref.value,
            "runtime_ref": self.runtime_ref,
            "sandbox_launcher_path": self.sandbox_launcher_path,
            "sandbox_launcher_sha256": self.sandbox_launcher_sha256,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
        }


@dataclass(frozen=True)
class ThreeDBoneSpec:
    """One provider-neutral rest-pose bone in a generic hierarchy."""

    name: str
    parent_name: str | None
    head: tuple[float, float, float]
    tail: tuple[float, float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "3D bone name", 256))
        if self.parent_name is not None:
            object.__setattr__(
                self,
                "parent_name",
                _text(self.parent_name, "3D bone parent name", 256),
            )
        for name in ("head", "tail"):
            value = getattr(self, name)
            if (
                not isinstance(value, tuple)
                or len(value) != 3
                or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in value)
            ):
                raise ThreeDContractError(f"3D bone {name} must be three finite coordinates")
            object.__setattr__(self, name, tuple(float(item) for item in value))
        if self.head == self.tail:
            raise ThreeDContractError("3D bone head and tail must differ")

    def payload(self) -> dict[str, object]:
        return {
            "head": list(self.head),
            "name": self.name,
            "parent_name": self.parent_name,
            "tail": list(self.tail),
        }


@dataclass(frozen=True)
class ThreeDSkinWeight:
    """One exact bone influence for a mesh vertex."""

    bone_name: str
    weight: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "bone_name", _text(self.bone_name, "3D skin bone name", 256))
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)) or not math.isfinite(float(self.weight)) or not 0.0 <= float(self.weight) <= 1.0:
            raise ThreeDContractError("3D skin weight must be finite and within [0,1]")
        object.__setattr__(self, "weight", float(self.weight))

    def payload(self) -> dict[str, object]:
        return {"bone_name": self.bone_name, "weight": self.weight}


@dataclass(frozen=True)
class ThreeDSkinBinding:
    """Exact normalized influences for one source-mesh vertex."""

    vertex_index: int
    weights: tuple[ThreeDSkinWeight, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.vertex_index, int) or isinstance(self.vertex_index, bool) or self.vertex_index < 0:
            raise ThreeDContractError("3D skin vertex index is malformed")
        if (
            not isinstance(self.weights, tuple)
            or not self.weights
            or len(self.weights) > 32
            or any(not isinstance(item, ThreeDSkinWeight) for item in self.weights)
            or len({item.bone_name for item in self.weights}) != len(self.weights)
            or abs(sum(item.weight for item in self.weights) - 1.0) > 1e-9
        ):
            raise ThreeDContractError("3D skin weights must be unique and normalized")

    def payload(self) -> dict[str, object]:
        return {
            "vertex_index": self.vertex_index,
            "weights": [item.payload() for item in self.weights],
        }


@dataclass(frozen=True)
class ThreeDSkeletonSpec:
    """Generic non-humanoid hierarchy, rest pose, and coordinate convention."""

    coordinate_system: str
    bones: tuple[ThreeDBoneSpec, ...]
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "coordinate_system", _text(self.coordinate_system, "3D skeleton coordinate system", 128))
        if (
            not isinstance(self.bones, tuple)
            or not self.bones
            or len(self.bones) > 256
            or any(not isinstance(item, ThreeDBoneSpec) for item in self.bones)
            or len({item.name for item in self.bones}) != len(self.bones)
        ):
            raise ThreeDContractError("3D skeleton bones are malformed or duplicated")
        names = {item.name for item in self.bones}
        if any(item.parent_name is not None and item.parent_name not in names for item in self.bones):
            raise ThreeDContractError("3D skeleton parent bone is unknown")
        parents = {item.name: item.parent_name for item in self.bones}
        for name in names:
            seen: set[str] = set()
            current: str | None = name
            while current is not None:
                if current in seen:
                    raise ThreeDContractError("3D skeleton hierarchy contains a cycle")
                seen.add(current)
                current = parents[current]
        object.__setattr__(self, "bones", tuple(self.bones))
        object.__setattr__(self, "semantic_digest", _digest(self.payload()))

    def validate_skin_bindings(self, bindings: tuple[ThreeDSkinBinding, ...]) -> None:
        if (
            not isinstance(bindings, tuple)
            or len(bindings) > 1_000_000
            or any(not isinstance(item, ThreeDSkinBinding) for item in bindings)
            or len({item.vertex_index for item in bindings}) != len(bindings)
        ):
            raise ThreeDContractError("3D skin bindings are malformed or duplicated")
        names = {item.name for item in self.bones}
        if any(weight.bone_name not in names for item in bindings for weight in item.weights):
            raise ThreeDContractError("3D skin binding references an unknown skeleton bone")

    def payload(self) -> dict[str, object]:
        return {
            "bones": [item.payload() for item in self.bones],
            "coordinate_system": self.coordinate_system,
        }


class ThreeDRootMotionPolicy(str, Enum):
    PRESERVE = "preserve"
    EXTRACT = "extract"
    REMOVE = "remove"


@dataclass(frozen=True)
class ThreeDPlacedAssetSpec:
    artifact_ref: ArtifactRef
    content_sha256: str
    binding_path: str
    location: tuple[float, float, float]
    rotation_euler: tuple[float, float, float]
    scale: tuple[float, float, float]
    asset_id: str
    material_ref: str
    variant: str
    parent_ref: str | None
    partition_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("environment asset requires ArtifactRef")
        object.__setattr__(self, "content_sha256", _animation_digest(self.content_sha256, "environment asset content"))
        object.__setattr__(self, "binding_path", _operation_relative(self.binding_path, "environment asset binding_path"))
        object.__setattr__(self, "location", _animation_vector(self.location, "environment asset location"))
        object.__setattr__(self, "rotation_euler", _animation_vector(self.rotation_euler, "environment asset rotation"))
        object.__setattr__(self, "scale", _animation_vector(self.scale, "environment asset scale", positive=True))
        object.__setattr__(self, "asset_id", _text(self.asset_id, "environment asset_id", 128))
        object.__setattr__(self, "material_ref", _ref(self.material_ref, "environment material_ref"))
        object.__setattr__(self, "variant", _text(self.variant, "environment variant", 128))
        if self.parent_ref is not None:
            object.__setattr__(self, "parent_ref", _ref(self.parent_ref, "environment parent_ref"))
        object.__setattr__(self, "partition_id", _text(self.partition_id, "environment partition_id", 128))

    def payload(self) -> dict[str, object]:
        return {"artifact_ref": self.artifact_ref.value, "asset_id": self.asset_id, "binding_path": self.binding_path, "content_sha256": self.content_sha256, "location": list(self.location), "material_ref": self.material_ref, "parent_ref": self.parent_ref, "partition_id": self.partition_id, "rotation_euler": list(self.rotation_euler), "scale": list(self.scale), "variant": self.variant}


@dataclass(frozen=True)
class ThreeDEnvironmentLayoutSpec:
    layout_id: str
    generator: str
    generator_version: str
    seed: int
    generator_config: Mapping[str, _Scalar]
    placed_assets: tuple[ThreeDPlacedAssetSpec, ...]
    material_names: tuple[str, ...]
    partitions: tuple[str, ...]
    lod_levels: int
    include_collision: bool
    include_navigation: bool
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "layout_id", _text(self.layout_id, "environment layout_id", 128))
        object.__setattr__(self, "generator", _text(self.generator, "environment generator", 128))
        object.__setattr__(self, "generator_version", _text(self.generator_version, "environment generator_version", 64))
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or not 0 <= self.seed <= 2**63 - 1:
            raise ThreeDContractError("environment generator seed is malformed")
        object.__setattr__(self, "generator_config", _config(self.generator_config))
        if not isinstance(self.placed_assets, tuple) or not self.placed_assets or len(self.placed_assets) > 64 or any(not isinstance(item, ThreeDPlacedAssetSpec) for item in self.placed_assets) or len({item.binding_path for item in self.placed_assets}) != len(self.placed_assets):
            raise ThreeDContractError("environment placed assets are malformed or duplicated")
        for field_name in ("material_names", "partitions"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or not value or len(value) > 64 or any(not isinstance(item, str) or not item or len(item) > 128 for item in value) or len(set(value)) != len(value):
                raise ThreeDContractError(f"environment {field_name} are malformed or duplicated")
        if any(item.partition_id not in self.partitions for item in self.placed_assets):
            raise ThreeDContractError("environment asset partition is not declared by its layout")
        if not isinstance(self.lod_levels, int) or isinstance(self.lod_levels, bool) or not 1 <= self.lod_levels <= 8:
            raise ThreeDContractError("environment lod_levels is malformed")
        if not isinstance(self.include_collision, bool) or not isinstance(self.include_navigation, bool):
            raise ThreeDContractError("environment collision and navigation flags must be boolean")
        object.__setattr__(self, "semantic_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {"generator": self.generator, "generator_config": dict(self.generator_config), "generator_version": self.generator_version, "include_collision": self.include_collision, "include_navigation": self.include_navigation, "layout_id": self.layout_id, "lod_levels": self.lod_levels, "material_names": list(self.material_names), "partitions": list(self.partitions), "placed_assets": [item.payload() for item in self.placed_assets], "seed": self.seed}


def _animation_digest(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or _SHA256.fullmatch(value) is None
    ):
        raise ThreeDContractError(f"{name} must be an exact SHA-256 digest")
    return value


def _animation_vector(value: object, name: str, *, positive: bool = False) -> tuple[float, float, float]:
    if (
        not isinstance(value, tuple)
        or len(value) != 3
        or any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or (positive and float(item) <= 0.0)
            for item in value
        )
    ):
        raise ThreeDContractError(f"{name} must be one finite 3D transform")
    return (float(value[0]), float(value[1]), float(value[2]))


@dataclass(frozen=True)
class ThreeDAnimationKeyframe:
    bone_name: str
    frame: float
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_euler: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bone_name", _text(self.bone_name, "animation bone_name", 128))
        if (
            isinstance(self.frame, bool)
            or not isinstance(self.frame, (int, float))
            or not math.isfinite(float(self.frame))
            or not 0.0 <= float(self.frame) <= 1_000_000.0
        ):
            raise ThreeDContractError("animation keyframe frame is malformed")
        object.__setattr__(self, "frame", float(self.frame))
        object.__setattr__(self, "translation", _animation_vector(self.translation, "animation translation"))
        object.__setattr__(self, "rotation_euler", _animation_vector(self.rotation_euler, "animation rotation_euler"))
        object.__setattr__(self, "scale", _animation_vector(self.scale, "animation scale", positive=True))

    def payload(self) -> dict[str, object]:
        return {
            "bone_name": self.bone_name,
            "frame": self.frame,
            "rotation_euler": list(self.rotation_euler),
            "scale": list(self.scale),
            "translation": list(self.translation),
        }


@dataclass(frozen=True)
class ThreeDAnimationClipSpec:
    clip_id: str
    source_skeleton_sha256: str
    keyframes: tuple[ThreeDAnimationKeyframe, ...]
    loop_tolerance: float = 0.0001
    blend_with_clip_id: str | None = None
    blend_factor: float = 0.0
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "clip_id", _text(self.clip_id, "animation clip_id", 128))
        object.__setattr__(self, "source_skeleton_sha256", _animation_digest(self.source_skeleton_sha256, "animation source skeleton"))
        if (
            not isinstance(self.keyframes, tuple)
            or not 1 <= len(self.keyframes) <= 100_000
            or any(not isinstance(item, ThreeDAnimationKeyframe) for item in self.keyframes)
            or len({(item.bone_name, item.frame) for item in self.keyframes}) != len(self.keyframes)
        ):
            raise ThreeDContractError("animation keyframes are malformed or duplicated")
        if (
            isinstance(self.loop_tolerance, bool)
            or not isinstance(self.loop_tolerance, (int, float))
            or not math.isfinite(float(self.loop_tolerance))
            or not 0.0 <= float(self.loop_tolerance) <= 1_000_000.0
            or isinstance(self.blend_factor, bool)
            or not isinstance(self.blend_factor, (int, float))
            or not math.isfinite(float(self.blend_factor))
            or not 0.0 <= float(self.blend_factor) <= 1.0
        ):
            raise ThreeDContractError("animation loop or blend value is malformed")
        if self.blend_with_clip_id is not None:
            object.__setattr__(self, "blend_with_clip_id", _text(self.blend_with_clip_id, "animation blend_with_clip_id", 128))
            if self.blend_with_clip_id == self.clip_id:
                raise ThreeDContractError("animation cannot blend a clip with itself")
        elif float(self.blend_factor) != 0.0:
            raise ThreeDContractError("animation blend factor requires an exact source clip")
        object.__setattr__(self, "loop_tolerance", float(self.loop_tolerance))
        object.__setattr__(self, "blend_factor", float(self.blend_factor))
        object.__setattr__(self, "semantic_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "blend_factor": self.blend_factor,
            "blend_with_clip_id": self.blend_with_clip_id,
            "clip_id": self.clip_id,
            "keyframes": [item.payload() for item in self.keyframes],
            "loop_tolerance": self.loop_tolerance,
            "source_skeleton_sha256": self.source_skeleton_sha256,
        }


@dataclass(frozen=True)
class ThreeDRetargetBoneMapping:
    source_bone_name: str
    target_bone_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_bone_name", _text(self.source_bone_name, "retarget source_bone_name", 128))
        object.__setattr__(self, "target_bone_name", _text(self.target_bone_name, "retarget target_bone_name", 128))

    def payload(self) -> dict[str, str]:
        return {"source_bone_name": self.source_bone_name, "target_bone_name": self.target_bone_name}


@dataclass(frozen=True)
class ThreeDRetargetSpec:
    source_skeleton_spec: ThreeDSkeletonSpec
    target_skeleton_sha256: str
    mappings: tuple[ThreeDRetargetBoneMapping, ...]
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_skeleton_spec, ThreeDSkeletonSpec):
            raise TypeError("retarget source skeleton specification is malformed")
        object.__setattr__(self, "target_skeleton_sha256", _animation_digest(self.target_skeleton_sha256, "retarget target skeleton"))
        if (
            not isinstance(self.mappings, tuple)
            or not self.mappings
            or len(self.mappings) > 256
            or any(not isinstance(item, ThreeDRetargetBoneMapping) for item in self.mappings)
            or len({item.source_bone_name for item in self.mappings}) != len(self.mappings)
            or len({item.target_bone_name for item in self.mappings}) != len(self.mappings)
        ):
            raise ThreeDContractError("retarget mappings are malformed or duplicated")
        object.__setattr__(self, "semantic_digest", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "mappings": [item.payload() for item in self.mappings],
            "source_skeleton_spec": self.source_skeleton_spec.payload(),
            "target_skeleton_sha256": self.target_skeleton_sha256,
        }


@dataclass(frozen=True)
class ThreeDValidationRequirements:
    """Project/Task-scoped criteria; no value is a global 3D policy."""

    require_mesh: bool = False
    require_manifold: bool = False
    reject_degenerate_faces: bool = False
    reject_duplicate_vertices: bool = False
    require_valid_normals: bool = False
    require_uv: bool = False
    maximum_faces: int | None = None
    minimum_dimension: float | None = None
    maximum_dimension: float | None = None
    required_unit_system: str | None = None
    require_skeleton: bool = False
    require_rig: bool = False
    require_skin: bool = False
    require_deformation: bool = False
    require_normalized_weights: bool = False
    maximum_weight_influences: int | None = None
    require_animation: bool = False
    require_loop: bool = False
    require_baked_animation: bool = False
    maximum_loop_error: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "require_mesh",
            "require_manifold",
            "reject_degenerate_faces",
            "reject_duplicate_vertices",
            "require_valid_normals",
            "require_uv",
            "require_skeleton",
            "require_rig",
            "require_skin",
            "require_deformation",
            "require_normalized_weights",
            "require_animation",
            "require_loop",
            "require_baked_animation",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ThreeDContractError(f"{name} must be boolean")
        if self.maximum_faces is not None and (
            not isinstance(self.maximum_faces, int)
            or isinstance(self.maximum_faces, bool)
            or self.maximum_faces < 0
            or self.maximum_faces > 2**53
        ):
            raise ThreeDContractError("Project maximum_faces is malformed")
        for value, name in (
            (self.minimum_dimension, "minimum_dimension"),
            (self.maximum_dimension, "maximum_dimension"),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 <= float(value) <= 1e15
            ):
                raise ThreeDContractError(f"Project {name} is malformed")
        if (
            self.minimum_dimension is not None
            and self.maximum_dimension is not None
            and self.minimum_dimension > self.maximum_dimension
        ):
            raise ThreeDContractError("Project dimension requirements conflict")
        if self.required_unit_system is not None:
            object.__setattr__(
                self,
                "required_unit_system",
                _text(self.required_unit_system, "required_unit_system", 64),
            )
        if self.maximum_weight_influences is not None and (
            not isinstance(self.maximum_weight_influences, int)
            or isinstance(self.maximum_weight_influences, bool)
            or not 1 <= self.maximum_weight_influences <= 32
        ):
            raise ThreeDContractError("maximum_weight_influences is malformed")
        if self.maximum_loop_error is not None and (
            isinstance(self.maximum_loop_error, bool)
            or not isinstance(self.maximum_loop_error, (int, float))
            or not math.isfinite(float(self.maximum_loop_error))
            or not 0.0 <= float(self.maximum_loop_error) <= 1_000_000.0
        ):
            raise ThreeDContractError("maximum_loop_error is malformed")

    def payload(self) -> dict[str, object]:
        return {
            "maximum_dimension": self.maximum_dimension,
            "maximum_faces": self.maximum_faces,
            "minimum_dimension": self.minimum_dimension,
            "reject_degenerate_faces": self.reject_degenerate_faces,
            "reject_duplicate_vertices": self.reject_duplicate_vertices,
            "require_mesh": self.require_mesh,
            "require_manifold": self.require_manifold,
            "require_uv": self.require_uv,
            "require_valid_normals": self.require_valid_normals,
            "required_unit_system": self.required_unit_system,
            "require_skeleton": self.require_skeleton,
            "require_rig": self.require_rig,
            "require_skin": self.require_skin,
            "require_deformation": self.require_deformation,
            "require_normalized_weights": self.require_normalized_weights,
            "maximum_weight_influences": self.maximum_weight_influences,
            "require_animation": self.require_animation,
            "require_loop": self.require_loop,
            "require_baked_animation": self.require_baked_animation,
            "maximum_loop_error": self.maximum_loop_error,
        }


@dataclass(frozen=True)
class ThreeDOperationRequest:
    """One exact semantic 3D operation against a captured Workspace."""

    operation: ThreeDOperation
    identity: ThreeDToolIdentity
    candidate_snapshot_ref: WorkspaceSnapshotRef
    control_root_ref: FilesystemRootRef
    working_directory: str
    source_artifact_refs: tuple[ArtifactRef, ...]
    source_path: str | None
    output_path: str
    output_role: str
    output_media_type: str
    operation_config: Mapping[str, _Scalar] = field(default_factory=dict)
    auxiliary_artifact_bindings: Mapping[str, ArtifactRef] = field(
        default_factory=dict
    )
    validation_requirements: ThreeDValidationRequirements = field(
        default_factory=ThreeDValidationRequirements
    )
    skeleton_spec: ThreeDSkeletonSpec | None = None
    skin_bindings: tuple[ThreeDSkinBinding, ...] = ()
    animation_clip_spec: ThreeDAnimationClipSpec | None = None
    retarget_spec: ThreeDRetargetSpec | None = None
    root_motion_policy: ThreeDRootMotionPolicy = ThreeDRootMotionPolicy.PRESERVE
    environment_spec: ThreeDEnvironmentLayoutSpec | None = None
    reference_output_artifact_ref: ArtifactRef | None = None
    resource_allocation_ref: ResourceAllocationRef | None = None
    request_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.operation, ThreeDOperation):
            raise ThreeDContractError("3D operation is malformed")
        if not isinstance(self.identity, ThreeDToolIdentity):
            raise TypeError("3D request requires exact ThreeDToolIdentity")
        if not isinstance(self.candidate_snapshot_ref, WorkspaceSnapshotRef):
            raise TypeError("3D request requires exact WorkspaceSnapshotRef")
        if not isinstance(self.control_root_ref, FilesystemRootRef):
            raise TypeError("3D request requires exact FilesystemRootRef")
        project = self.identity.project_ref
        if (
            self.candidate_snapshot_ref.project_ref != project
            or self.control_root_ref.project_ref != project
        ):
            raise ThreeDScopeError("3D Workspace identity crossed Project scope")
        object.__setattr__(
            self,
            "working_directory",
            _relative(self.working_directory, "3D working_directory"),
        )
        if (
            not isinstance(self.source_artifact_refs, tuple)
            or len(self.source_artifact_refs) > 128
            or len(set(self.source_artifact_refs)) != len(self.source_artifact_refs)
            or any(not isinstance(item, ArtifactRef) for item in self.source_artifact_refs)
        ):
            raise ThreeDContractError("3D source Artifacts are duplicated or unbounded")
        if any(item.project_ref != project for item in self.source_artifact_refs):
            raise ThreeDScopeError("3D source Artifact crossed Project scope")
        if self.operation in {ThreeDOperation.MODEL, ThreeDOperation.ENVIRONMENT}:
            if self.source_path is not None or self.source_artifact_refs:
                raise ThreeDContractError("3D model creation cannot claim an input source")
        else:
            if self.source_path is None or len(self.source_artifact_refs) != 1:
                raise ThreeDContractError(
                    "3D operation requires exactly one bound source path and Artifact"
                )
        if self.source_path is not None:
            object.__setattr__(
                self,
                "source_path",
                _operation_relative(self.source_path, "3D source_path"),
            )
        object.__setattr__(
            self,
            "output_path",
            _operation_relative(self.output_path, "3D output_path"),
        )
        if self.source_path == self.output_path:
            raise ThreeDContractError("3D operations cannot overwrite authoritative source")
        if not isinstance(self.output_role, str) or _ROLE.fullmatch(self.output_role) is None:
            raise ThreeDContractError("3D output role is malformed")
        if (
            self.output_role in _KNOWN_ROLES
            and self.output_role not in _OPERATION_ROLES[self.operation]
        ):
            raise ThreeDContractError(
                "3D output role cannot substitute for the operation's evidence class"
            )
        object.__setattr__(
            self,
            "output_media_type",
            _text(self.output_media_type, "3D output media type", 256),
        )
        object.__setattr__(self, "operation_config", _config(self.operation_config))
        if (
            not isinstance(self.auxiliary_artifact_bindings, Mapping)
            or len(self.auxiliary_artifact_bindings) > 64
        ):
            raise ThreeDContractError(
                "3D auxiliary Artifact bindings are malformed or unbounded"
            )
        bindings: dict[str, ArtifactRef] = {}
        for raw_path, artifact_ref in self.auxiliary_artifact_bindings.items():
            path = _operation_relative(raw_path, "3D auxiliary Artifact path")
            if (
                not isinstance(artifact_ref, ArtifactRef)
                or artifact_ref.project_ref != project
                or artifact_ref in self.source_artifact_refs
                or artifact_ref in bindings.values()
                or path == self.source_path
                or path == self.output_path
            ):
                raise ThreeDScopeError(
                    "3D auxiliary Artifact binding crossed scope or aliases a path"
                )
            bindings[path] = artifact_ref
        if self.operation is ThreeDOperation.MODEL and bindings:
            raise ThreeDContractError(
                "3D model creation cannot claim auxiliary input Artifacts"
            )
        texture_path = self.operation_config.get("texture_path")
        if texture_path is not None and (
            self.operation is not ThreeDOperation.MATERIAL
            or not isinstance(texture_path, str)
            or texture_path not in bindings
        ):
            raise ThreeDContractError(
                "3D texture_path requires an exact material Artifact binding"
            )
        object.__setattr__(
            self,
            "auxiliary_artifact_bindings",
            MappingProxyType(dict(sorted(bindings.items()))),
        )
        if not isinstance(self.validation_requirements, ThreeDValidationRequirements):
            raise TypeError("3D validation requirements are malformed")
        if self.skeleton_spec is not None and not isinstance(self.skeleton_spec, ThreeDSkeletonSpec):
            raise TypeError("3D skeleton specification is malformed")
        character_operations = {
            ThreeDOperation.RIG,
            ThreeDOperation.SKIN,
            ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
        }
        animation_operations = {
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
        }
        if self.operation in character_operations | animation_operations and self.skeleton_spec is None:
            raise ThreeDContractError("3D character operation requires an exact skeleton specification")
        if self.skin_bindings:
            if self.operation is not ThreeDOperation.SKIN or self.skeleton_spec is None:
                raise ThreeDContractError("3D skin bindings require a skinned operation and skeleton")
            self.skeleton_spec.validate_skin_bindings(self.skin_bindings)
        elif not isinstance(self.skin_bindings, tuple):
            raise ThreeDContractError("3D skin bindings are malformed")
        if not isinstance(self.root_motion_policy, ThreeDRootMotionPolicy):
            raise TypeError("3D root motion policy is malformed")
        if self.operation in animation_operations:
            if not isinstance(self.animation_clip_spec, ThreeDAnimationClipSpec):
                raise ThreeDContractError("3D animation operation requires an exact clip specification")
            assert self.skeleton_spec is not None
            if self.operation is ThreeDOperation.RETARGET:
                if not isinstance(self.retarget_spec, ThreeDRetargetSpec):
                    raise ThreeDContractError("3D retarget operation requires an exact mapping specification")
                if (
                    self.animation_clip_spec.source_skeleton_sha256
                    != self.retarget_spec.source_skeleton_spec.semantic_digest
                    or self.retarget_spec.target_skeleton_sha256
                    != self.skeleton_spec.semantic_digest
                ):
                    raise ThreeDContractError("3D retarget skeleton identities do not match the exact clip")
                source_names = {item.name for item in self.retarget_spec.source_skeleton_spec.bones}
                target_names = {item.name for item in self.skeleton_spec.bones}
                mapping = {item.source_bone_name: item.target_bone_name for item in self.retarget_spec.mappings}
                if (
                    any(item.bone_name not in source_names for item in self.animation_clip_spec.keyframes)
                    or any(source not in source_names or target not in target_names for source, target in mapping.items())
                    or any(item.bone_name not in mapping for item in self.animation_clip_spec.keyframes)
                ):
                    raise ThreeDContractError("3D retarget mapping does not cover exact animation bones")
            elif (
                self.retarget_spec is not None
                or self.animation_clip_spec.source_skeleton_sha256 != self.skeleton_spec.semantic_digest
                or any(item.bone_name not in {bone.name for bone in self.skeleton_spec.bones} for item in self.animation_clip_spec.keyframes)
            ):
                raise ThreeDContractError("3D animation clip does not match its exact skeleton")
        elif self.animation_clip_spec is not None or self.retarget_spec is not None:
            raise ThreeDContractError("3D animation specifications require an animation operation")
        if self.operation is ThreeDOperation.ENVIRONMENT:
            if not isinstance(self.environment_spec, ThreeDEnvironmentLayoutSpec):
                raise ThreeDContractError("environment operation requires an exact layout specification")
            if (
                tuple(item.binding_path for item in self.environment_spec.placed_assets)
                != tuple(self.auxiliary_artifact_bindings)
                or any(
                    self.auxiliary_artifact_bindings[item.binding_path] != item.artifact_ref
                    for item in self.environment_spec.placed_assets
                )
            ):
                raise ThreeDContractError("environment placed assets differ from exact Artifact bindings")
        elif self.environment_spec is not None:
            raise ThreeDContractError("environment layout specification requires an environment operation")
        if self.reference_output_artifact_ref is not None and (
            not isinstance(self.reference_output_artifact_ref, ArtifactRef)
            or self.reference_output_artifact_ref.project_ref != project
        ):
            raise ThreeDScopeError("3D reference output crossed Project scope")
        if self.resource_allocation_ref is not None and (
            not isinstance(self.resource_allocation_ref, ResourceAllocationRef)
            or self.resource_allocation_ref.project_ref != project
        ):
            raise ThreeDScopeError("3D ResourceAllocation crossed Project scope")
        object.__setattr__(self, "request_sha256", _digest(self.payload()))

    @property
    def project_ref(self) -> ProjectRef:
        return self.identity.project_ref

    @property
    def all_source_artifact_refs(self) -> tuple[ArtifactRef, ...]:
        return tuple(
            sorted(
                {
                    *self.source_artifact_refs,
                    *self.auxiliary_artifact_bindings.values(),
                },
                key=lambda item: item.value,
            )
        )

    def payload(self) -> dict[str, object]:
        return {
            "auxiliary_artifact_bindings": {
                path: artifact_ref.value
                for path, artifact_ref in self.auxiliary_artifact_bindings.items()
            },
            "candidate_snapshot_ref": self.candidate_snapshot_ref.value,
            "control_root_ref": self.control_root_ref.value,
            "identity_digest": self.identity.semantic_digest,
            "operation": self.operation.value,
            "operation_config": dict(self.operation_config),
            "output_media_type": self.output_media_type,
            "output_path": self.output_path,
            "output_role": self.output_role,
            "project_ref": self.project_ref.value,
            "reference_output_artifact_ref": (
                None
                if self.reference_output_artifact_ref is None
                else self.reference_output_artifact_ref.value
            ),
            "resource_allocation_ref": (
                None
                if self.resource_allocation_ref is None
                else self.resource_allocation_ref.value
            ),
            "skeleton_spec": None if self.skeleton_spec is None else self.skeleton_spec.payload(),
            "skin_bindings": [item.payload() for item in self.skin_bindings],
            "animation_clip_spec": None if self.animation_clip_spec is None else self.animation_clip_spec.payload(),
            "retarget_spec": None if self.retarget_spec is None else self.retarget_spec.payload(),
            "root_motion_policy": self.root_motion_policy.value,
            "environment_spec": None if self.environment_spec is None else self.environment_spec.payload(),
            "source_artifact_refs": [item.value for item in self.source_artifact_refs],
            "source_path": self.source_path,
            "validation_requirements": self.validation_requirements.payload(),
            "working_directory": self.working_directory,
        }


@dataclass(frozen=True)
class ThreeDOperationResult:
    project_ref: ProjectRef
    operation: ThreeDOperation
    request_sha256: str
    identity_digest: str
    adapter_ref: str
    reality: ThreeDReality
    status: ThreeDStatus
    node_attempt_id: str
    node_fence: int
    source_artifact_refs: tuple[ArtifactRef, ...]
    output_artifact_ref: ArtifactRef | None
    output_content_ref: ContentRef | None
    report_ref: ContentRef | None
    process_artifact_ref: ArtifactRef | None
    process_call_ref: str | None
    output_role: str | None
    output_path: str | None
    editable_source: bool
    preview_only: bool
    technical_valid: bool | None
    failure_reason: str | None
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("3D result requires exact ProjectRef")
        if not isinstance(self.operation, ThreeDOperation):
            raise ThreeDContractError("3D result operation is malformed")
        _sha(self.request_sha256, "3D request digest")
        _sha(self.identity_digest, "3D identity digest")
        object.__setattr__(self, "adapter_ref", _ref(self.adapter_ref, "3D adapter_ref"))
        if not isinstance(self.reality, ThreeDReality) or not isinstance(self.status, ThreeDStatus):
            raise ThreeDContractError("3D result classification is malformed")
        if not isinstance(self.node_attempt_id, str) or not self.node_attempt_id:
            raise ThreeDContractError("3D result Node attempt is malformed")
        if not isinstance(self.node_fence, int) or isinstance(self.node_fence, bool) or self.node_fence < 1:
            raise ThreeDContractError("3D result Node fence is malformed")
        if (
            not isinstance(self.source_artifact_refs, tuple)
            or len(set(self.source_artifact_refs)) != len(self.source_artifact_refs)
            or any(not isinstance(item, ArtifactRef) for item in self.source_artifact_refs)
        ):
            raise ThreeDContractError("3D result source Artifacts are malformed")
        if any(item.project_ref != self.project_ref for item in self.source_artifact_refs):
            raise ThreeDScopeError("3D result source Artifact crossed Project scope")
        for value in (self.output_artifact_ref, self.process_artifact_ref):
            if value is not None and value.project_ref != self.project_ref:
                raise ThreeDScopeError("3D result Artifact crossed Project scope")
        if self.output_role is not None and _ROLE.fullmatch(self.output_role) is None:
            raise ThreeDContractError("3D result output role is malformed")
        if (
            self.output_role is not None
            and self.output_role in _KNOWN_ROLES
            and self.output_role not in _OPERATION_ROLES[self.operation]
        ):
            raise ThreeDContractError(
                "3D result role cannot substitute for its operation evidence"
            )
        if self.output_path is not None:
            object.__setattr__(self, "output_path", _relative(self.output_path, "3D result output path"))
        if self.process_call_ref is not None and not self.process_call_ref.startswith(
            f"tool-call://{self.project_ref.value}/"
        ):
            raise ThreeDScopeError("3D process ToolCall crossed Project scope")
        if not all(isinstance(item, bool) for item in (self.editable_source, self.preview_only)):
            raise ThreeDContractError("3D source-proof classifications must be boolean")
        if self.preview_only and self.editable_source:
            raise ThreeDContractError("preview evidence cannot be editable source proof")
        if self.reality is ThreeDReality.REFERENCE and self.editable_source:
            raise ThreeDContractError(
                "REFERENCE evidence cannot claim editable REAL source proof"
            )
        if self.reality is ThreeDReality.REFERENCE and (
            self.process_artifact_ref is not None or self.process_call_ref is not None
        ):
            raise ThreeDContractError(
                "REFERENCE evidence cannot claim a REAL process execution"
            )
        if self.reality is ThreeDReality.REAL and (
            self.process_artifact_ref is None or self.process_call_ref is None
        ):
            raise ThreeDContractError(
                "REAL 3D evidence requires exact process execution evidence"
            )
        if (
            self.reality is not ThreeDReality.NOT_RUN
            and self.operation is ThreeDOperation.PREVIEW
            and not self.preview_only
        ):
            raise ThreeDContractError("3D preview must remain secondary evidence")
        if (
            self.reality is not ThreeDReality.NOT_RUN
            and self.operation is ThreeDOperation.VALIDATE
            and self.technical_valid is None
        ):
            raise ThreeDContractError("3D validation lacks explicit technical result")
        if (
            self.operation is not ThreeDOperation.VALIDATE
            and self.technical_valid is not None
        ):
            raise ThreeDContractError("technical validity belongs only to validation")
        if self.status is ThreeDStatus.SUCCEEDED and (
            self.output_artifact_ref is None
            or self.output_content_ref is None
            or self.report_ref is None
            or self.output_role is None
            or self.output_path is None
            or self.failure_reason is not None
        ):
            raise ThreeDContractError("successful 3D result lacks exact durable evidence")
        if (
            self.status is ThreeDStatus.SUCCEEDED
            and self.reality is ThreeDReality.REAL
            and self.operation
            in {
                ThreeDOperation.MODEL,
                ThreeDOperation.MESH_EDIT,
                ThreeDOperation.TOPOLOGY,
                ThreeDOperation.UV,
                ThreeDOperation.MATERIAL,
                ThreeDOperation.RIG,
                ThreeDOperation.SKIN,
                ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
                ThreeDOperation.SCENE,
                ThreeDOperation.OPTIMIZE,
            }
            and (
                not self.editable_source
                or self.output_path is None
                or not self.output_path.endswith(".blend")
            )
        ):
            raise ThreeDContractError(
                "successful REAL editable operation lacks native source proof"
            )
        if self.status is ThreeDStatus.FAILED and self.failure_reason is None:
            raise ThreeDContractError("failed 3D result lacks a real reason")
        if self.status is ThreeDStatus.NOT_RUN or self.reality is ThreeDReality.NOT_RUN:
            if self.status is not ThreeDStatus.NOT_RUN or self.reality is not ThreeDReality.NOT_RUN:
                raise ThreeDContractError("3D NOT_RUN classification differs")
            if (self.process_artifact_ref is None) != (
                self.process_call_ref is None
            ):
                raise ThreeDContractError(
                    "3D NOT_RUN process attempt evidence is incomplete"
                )
            if any(
                item is not None
                for item in (
                    self.output_artifact_ref,
                    self.output_content_ref,
                    self.output_role,
                    self.output_path,
                )
            ) or (
                self.report_ref is None
                or self.editable_source
                or self.preview_only
                or self.technical_valid is not None
                or self.failure_reason is None
            ):
                raise ThreeDContractError("3D NOT_RUN evidence is contradictory")
        if self.failure_reason is not None:
            object.__setattr__(self, "failure_reason", _text(self.failure_reason, "3D failure reason"))
        _text(self.observed_at, "3D observed_at", 128)
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "editable_source": self.editable_source,
            "failure_reason": self.failure_reason,
            "identity_digest": self.identity_digest,
            "node_attempt_id": self.node_attempt_id,
            "node_fence": self.node_fence,
            "observed_at": self.observed_at,
            "operation": self.operation.value,
            "output_artifact_ref": None if self.output_artifact_ref is None else self.output_artifact_ref.value,
            "output_content_ref": _content_payload(self.output_content_ref),
            "output_path": self.output_path,
            "output_role": self.output_role,
            "preview_only": self.preview_only,
            "process_artifact_ref": None if self.process_artifact_ref is None else self.process_artifact_ref.value,
            "process_call_ref": self.process_call_ref,
            "project_ref": self.project_ref.value,
            "reality": self.reality.value,
            "report_ref": _content_payload(self.report_ref),
            "request_sha256": self.request_sha256,
            "source_artifact_refs": [item.value for item in self.source_artifact_refs],
            "status": self.status.value,
            "technical_valid": self.technical_valid,
        }


@dataclass(frozen=True)
class _ThreeDPublication:
    snapshot_artifact_ref: ArtifactRef
    output_content_ref: ContentRef
    report_ref: ContentRef
    evidence_artifact_refs: tuple[ArtifactRef, ...]
    request_ref: ContentRef
    output_observed: bool
    status: ThreeDStatus


@dataclass(frozen=True)
class EnvironmentManifestPublication:
    """Immutable publication identity for a verified environment manifest."""

    manifest: EnvironmentIntegrationManifest
    manifest_artifact_ref: ArtifactRef
    manifest_content_ref: ContentRef

    def __post_init__(self) -> None:
        if (
            not isinstance(self.manifest, EnvironmentIntegrationManifest)
            or not isinstance(self.manifest_artifact_ref, ArtifactRef)
            or not isinstance(self.manifest_content_ref, ContentRef)
            or self.manifest.project_ref != self.manifest_artifact_ref.project_ref
        ):
            raise EnvironmentContractError("environment manifest publication identity is malformed")


@dataclass(frozen=True)
class RetargetRequestPublication:
    """Immutable Artifact identity for one exact versioned retarget request."""

    request: RetargetRequest
    request_artifact_ref: ArtifactRef
    request_content_ref: ContentRef

    def __post_init__(self) -> None:
        if (
            not isinstance(self.request, RetargetRequest)
            or not isinstance(self.request_artifact_ref, ArtifactRef)
            or not isinstance(self.request_content_ref, ContentRef)
            or self.request.project_ref != self.request_artifact_ref.project_ref
            or self.request_content_ref.digest != self.request.request_sha256
        ):
            raise AnimationContractError(
                "retarget request publication identity is malformed"
            )


@dataclass(frozen=True)
class ThreeDRuntimeDescription:
    project_ref: ProjectRef
    identity_digest: str
    adapter_ref: str
    reality: ThreeDReality
    available: bool
    tool_name: str
    tool_version: str
    executable_sha256: str
    driver_sha256: str
    embedded_python_version: str | None
    network_enforcement: str
    plugin_identities: tuple[ThreeDPluginIdentity, ...]
    runtime_ref: str
    resource_allocation_ref: ResourceAllocationRef | None
    process_call_ref: str | None
    unavailability_ref: ContentRef | None
    unavailable_reason: str | None
    observed_at: str
    record_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise TypeError("3D runtime description requires ProjectRef")
        _sha(self.identity_digest, "3D identity digest")
        object.__setattr__(self, "adapter_ref", _ref(self.adapter_ref, "3D adapter_ref"))
        if not isinstance(self.reality, ThreeDReality) or not isinstance(self.available, bool):
            raise ThreeDContractError("3D runtime classification is malformed")
        object.__setattr__(self, "tool_name", _text(self.tool_name, "3D tool name", 256))
        object.__setattr__(self, "tool_version", _text(self.tool_version, "3D tool version", 512))
        _sha(self.executable_sha256, "3D executable digest")
        _sha(self.driver_sha256, "3D driver digest")
        if self.embedded_python_version is not None:
            object.__setattr__(
                self,
                "embedded_python_version",
                _text(
                    self.embedded_python_version,
                    "3D embedded Python version",
                    128,
                ),
            )
        if self.network_enforcement not in {
            "INHERITED_NOT_ISOLATED",
            "SANDBOX_NETWORK_DENIED",
            "NOT_APPLICABLE",
            "NOT_RUN",
            "RECOVERY_NETWORK_STATE_UNOBSERVED",
        }:
            raise ThreeDContractError("3D network enforcement is malformed")
        if self.resource_allocation_ref is not None and (
            not isinstance(self.resource_allocation_ref, ResourceAllocationRef)
            or self.resource_allocation_ref.project_ref != self.project_ref
        ):
            raise ThreeDScopeError("3D runtime allocation crossed Project scope")
        if self.reality is ThreeDReality.NOT_RUN and self.available:
            raise ThreeDContractError("unavailable 3D runtime cannot be available")
        if self.reality is ThreeDReality.REAL and not self.available:
            raise ThreeDContractError("REAL 3D runtime must be available")
        if self.reality is ThreeDReality.REAL and (
            self.embedded_python_version is None
            or self.network_enforcement != "SANDBOX_NETWORK_DENIED"
            or self.resource_allocation_ref is None
            or self.process_call_ref is None
        ):
            raise ThreeDContractError(
                "REAL 3D runtime lacks exact execution environment evidence"
            )
        if self.reality is ThreeDReality.REFERENCE and (
            self.embedded_python_version is not None
            or self.network_enforcement != "NOT_APPLICABLE"
            or self.resource_allocation_ref is not None
            or self.process_call_ref is not None
        ):
            raise ThreeDContractError(
                "REFERENCE 3D runtime cannot claim execution environment evidence"
            )
        if self.reality is ThreeDReality.NOT_RUN and (
            self.embedded_python_version is not None
            or (
                self.process_call_ref is None
                and self.network_enforcement != "NOT_RUN"
            )
            or (
                self.process_call_ref is not None
                and self.network_enforcement
                not in {
                    "INHERITED_NOT_ISOLATED",
                    "RECOVERY_NETWORK_STATE_UNOBSERVED",
                }
            )
        ):
            raise ThreeDContractError(
                "NOT_RUN 3D runtime cannot claim executed environment evidence"
            )
        if self.available == (self.unavailable_reason is not None):
            raise ThreeDContractError("3D availability and reason differ")
        if self.unavailable_reason is not None:
            object.__setattr__(self, "unavailable_reason", _text(self.unavailable_reason, "3D unavailable reason"))
        object.__setattr__(self, "runtime_ref", _ref(self.runtime_ref, "3D runtime_ref"))
        if (
            not isinstance(self.plugin_identities, tuple)
            or len(set(self.plugin_identities)) != len(self.plugin_identities)
            or any(
                not isinstance(item, ThreeDPluginIdentity)
                for item in self.plugin_identities
            )
        ):
            raise ThreeDContractError("3D runtime plugin identities are malformed")
        if self.process_call_ref is not None and not self.process_call_ref.startswith(
            f"tool-call://{self.project_ref.value}/"
        ):
            raise ThreeDScopeError("3D runtime ToolCall crossed Project scope")
        if self.unavailability_ref is not None and not isinstance(
            self.unavailability_ref,
            ContentRef,
        ):
            raise ThreeDContractError(
                "3D runtime unavailability evidence is malformed"
            )
        if self.reality in {ThreeDReality.REAL, ThreeDReality.REFERENCE} and (
            self.unavailability_ref is not None
        ):
            raise ThreeDContractError(
                "available 3D runtime cannot claim unavailability evidence"
            )
        if self.reality is ThreeDReality.NOT_RUN and (
            (self.process_call_ref is None) != (self.unavailability_ref is not None)
        ):
            raise ThreeDContractError(
                "NOT_RUN 3D runtime lacks one exact unavailability evidence form"
            )
        _text(self.observed_at, "3D observed_at", 128)
        object.__setattr__(self, "record_sha256", _digest(self.payload()))

    def payload(self) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "available": self.available,
            "driver_sha256": self.driver_sha256,
            "embedded_python_version": self.embedded_python_version,
            "executable_sha256": self.executable_sha256,
            "identity_digest": self.identity_digest,
            "network_enforcement": self.network_enforcement,
            "observed_at": self.observed_at,
            "plugin_identities": [item.payload() for item in self.plugin_identities],
            "process_call_ref": self.process_call_ref,
            "project_ref": self.project_ref.value,
            "reality": self.reality.value,
            "resource_allocation_ref": (
                None
                if self.resource_allocation_ref is None
                else self.resource_allocation_ref.value
            ),
            "runtime_ref": self.runtime_ref,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "unavailability_ref": _content_payload(self.unavailability_ref),
            "unavailable_reason": self.unavailable_reason,
        }


@runtime_checkable
class ThreeDToolAdapter(Protocol):
    def inspectAsset(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def inspectScene(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def createAsset(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def modifyAsset(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def executeOperation(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def validate(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def export(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def preview(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult: ...
    def describeRuntime(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: ThreeDToolIdentity, *, control_root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str) -> ThreeDRuntimeDescription: ...
    def finalizeCharacterRigRef(self, access: ProjectAccess, result: ThreeDOperationResult, specification: CharacterSpecification) -> CharacterRigRef: ...
    def finalizeRetargetMapping(self, access: ProjectAccess, request: ThreeDOperationRequest, result: ThreeDOperationResult, source_rig_ref: CharacterRigRef, target_rig_ref: CharacterRigRef, *, mapping_id: str, mapping_version: str) -> RetargetMapping: ...
    def persistRetargetRequest(self, access: ProjectAccess, request: RetargetRequest) -> RetargetRequestPublication: ...
    def verifyRetargetRequestPublication(self, access: ProjectAccess, publication: RetargetRequestPublication) -> RetargetRequestPublication: ...
    def finalizeAnimationClip(self, access: ProjectAccess, request: ThreeDOperationRequest, result: ThreeDOperationResult, character_rig_ref: CharacterRigRef, *, clip_id: str, mapping: RetargetMapping | None = None) -> AnimationClip: ...
    def finalizeEnvironmentIntegrationManifest(self, access: ProjectAccess, request: ThreeDOperationRequest, result: ThreeDOperationResult, manifest: EnvironmentIntegrationManifest) -> EnvironmentManifestPublication: ...
    def verifyEnvironmentManifestPublication(self, access: ProjectAccess, publication: EnvironmentManifestPublication) -> EnvironmentManifestPublication: ...


class _MethodCheckedAdapter:
    _service: _ThreeDService

    """Shared method-to-operation guard for contract implementations."""

    @staticmethod
    def _require(request: ThreeDOperationRequest, allowed: tuple[ThreeDOperation, ...]) -> None:
        if request.operation not in allowed:
            raise ThreeDContractError("3D adapter method and request operation differ")

    def inspectAsset(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.INSPECT,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def inspectScene(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.INSPECT,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def createAsset(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.MODEL,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def modifyAsset(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.MESH_EDIT,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def executeOperation(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(
            request,
            (
                ThreeDOperation.TOPOLOGY,
                ThreeDOperation.UV,
                ThreeDOperation.MATERIAL,
                ThreeDOperation.RIG,
                ThreeDOperation.SKIN,
                ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
                ThreeDOperation.SCENE,
                ThreeDOperation.OPTIMIZE,
            ),
        )
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def validate(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.VALIDATE,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def export(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.CONVERT,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def preview(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        self._require(request, (ThreeDOperation.PREVIEW,))
        return self._invoke(access, attempt, request, idempotency_key=idempotency_key)

    def finalizeCharacterRigRef(
        self,
        access: ProjectAccess,
        result: ThreeDOperationResult,
        specification: CharacterSpecification,
    ) -> CharacterRigRef:
        return self._service.finalize_character_rig_ref(
            access,
            result,
            specification,
        )

    def finalizeRetargetMapping(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        source_rig_ref: CharacterRigRef,
        target_rig_ref: CharacterRigRef,
        *,
        mapping_id: str,
        mapping_version: str,
    ) -> RetargetMapping:
        return self._service.finalize_retarget_mapping(
            access, request, result, source_rig_ref, target_rig_ref,
            mapping_id=mapping_id, mapping_version=mapping_version,
        )

    def finalizeAnimationClip(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        character_rig_ref: CharacterRigRef,
        *,
        clip_id: str,
        mapping: RetargetMapping | None = None,
    ) -> AnimationClip:
        return self._service.finalize_animation_clip(
            access, request, result, character_rig_ref,
            clip_id=clip_id, mapping=mapping,
        )

    def persistRetargetRequest(
        self,
        access: ProjectAccess,
        request: RetargetRequest,
    ) -> RetargetRequestPublication:
        return self._service.persist_retarget_request(access, request)

    def verifyRetargetRequestPublication(
        self,
        access: ProjectAccess,
        publication: RetargetRequestPublication,
    ) -> RetargetRequestPublication:
        return self._service.verify_retarget_request_publication(
            access, publication
        )

    def finalizeEnvironmentIntegrationManifest(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        manifest: EnvironmentIntegrationManifest,
    ) -> EnvironmentManifestPublication:
        return self._service.finalize_environment_integration_manifest(
            access, request, result, manifest,
        )

    def verifyEnvironmentManifestPublication(
        self,
        access: ProjectAccess,
        publication: EnvironmentManifestPublication,
    ) -> EnvironmentManifestPublication:
        return self._service.verify_environment_manifest_publication(access, publication)

    def _invoke(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        raise ThreeDContractError("abstract 3D adapter invocation is unavailable")


class ReferenceThreeDToolAdapter(_MethodCheckedAdapter):
    """Reference contract implementation; it never claims real DCC execution."""

    def __init__(self, database_path: str | Path, object_store: ObjectStorageBackend) -> None:
        self._service = _ThreeDService(
            database_path,
            object_store,
            adapter_ref="adapter://3d/reference/v1",
            reality=ThreeDReality.REFERENCE,
        )

    def _invoke(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        return self._service.reference(
            access,
            attempt,
            request,
            idempotency_key=idempotency_key,
        )

    def describeRuntime(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: ThreeDToolIdentity, *, control_root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str) -> ThreeDRuntimeDescription:
        return self._service.describe_reference(
            access,
            attempt,
            identity,
            control_root_ref=control_root_ref,
            working_directory=working_directory,
            idempotency_key=idempotency_key,
        )


class BlenderThreeDToolAdapter(_MethodCheckedAdapter):
    """Real Blender adapter implemented below the provider-neutral protocol."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        process_adapter: ManagedProcessAdapter | None = None,
    ) -> None:
        self._service = _ThreeDService(
            database_path,
            object_store,
            adapter_ref="adapter://3d/blender/v1",
            reality=ThreeDReality.REAL,
            process_adapter=process_adapter,
        )

    def _invoke(self, access: ProjectAccess, attempt: NodeExecutionAttempt, request: ThreeDOperationRequest, *, idempotency_key: str) -> ThreeDOperationResult:
        return self._service.blender(
            access,
            attempt,
            request,
            idempotency_key=idempotency_key,
        )

    def describeRuntime(self, access: ProjectAccess, attempt: NodeExecutionAttempt, identity: ThreeDToolIdentity, *, control_root_ref: FilesystemRootRef, working_directory: str, idempotency_key: str) -> ThreeDRuntimeDescription:
        return self._service.describe_blender(
            access,
            attempt,
            identity,
            control_root_ref=control_root_ref,
            working_directory=working_directory,
            idempotency_key=idempotency_key,
        )


def _content_from_payload(value: object) -> ContentRef | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ThreeDIntegrityError("persisted 3D ContentRef is malformed")
    try:
        return ContentRef(
            cast(str, value["algorithm"]),
            cast(str, value["digest"]),
            cast(int, value["size_bytes"]),
            cast(str, value["media_type"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ThreeDIntegrityError("persisted 3D ContentRef is malformed") from exc


def _artifact_from_value(value: object, project_ref: ProjectRef) -> ArtifactRef | None:
    if value is None:
        return None
    prefix = f"artifact://{project_ref.value}/"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ThreeDScopeError("persisted 3D Artifact crossed Project scope")
    try:
        artifact_id, revision = value.removeprefix(prefix).rsplit("/", 1)
        return ArtifactRef(project_ref, artifact_id, int(revision))
    except (TypeError, ValueError) as exc:
        raise ThreeDIntegrityError("persisted 3D Artifact identity is malformed") from exc


class _ThreeDService:
    """Durable adapter-local execution, identity, and publication service."""

    _DRIVER = Path(__file__).with_name("_blender_three_d_driver.py").resolve()
    _DRIVER_EVIDENCE = "BIELLA_FIXED_DRIVER_V1"
    _RESULT_MARKER = b"BIELLA_3D_RESULT="

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        adapter_ref: str,
        reality: ThreeDReality,
        process_adapter: ManagedProcessAdapter | None = None,
    ) -> None:
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("3D adapter requires exact ObjectStorageBackend")
        self.database_path = Path(database_path).resolve()
        self.object_store = object_store
        self.adapter_ref = _ref(adapter_ref, "3D adapter_ref")
        self.reality = reality
        self.projects = ProjectStore(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
        self.executions = NodeExecutionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.scheduler = Scheduler(self.database_path)
        self.resources = ResourceService(self.database_path)
        self.filesystem = FilesystemAdapter(self.database_path, object_store)
        self.workspaces = WorkspaceService(
            self.database_path,
            object_store,
            self.filesystem,
        )
        self.process = (
            ManagedProcessAdapter(self.database_path, object_store)
            if process_adapter is None
            else process_adapter
        )
        if not isinstance(self.process, ManagedProcessAdapter):
            raise TypeError("3D real adapter requires ManagedProcessAdapter")
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS three_d_operation_claims (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS three_d_operation_results (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    REFERENCES three_d_operation_claims(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS three_d_operation_inflight (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    REFERENCES three_d_operation_claims(project_id,adapter_ref,node_attempt_id,node_fence,operation,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS three_d_output_claims (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  workspace_id TEXT NOT NULL,
                  directory_device INTEGER NOT NULL,
                  directory_inode INTEGER NOT NULL,
                  output_name TEXT NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  PRIMARY KEY(directory_device,directory_inode,output_name),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS three_d_output_physical_unique
                  ON three_d_output_claims(directory_device,directory_inode,output_name);
                CREATE TABLE IF NOT EXISTS three_d_output_publications (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  artifact_id TEXT NOT NULL,
                  artifact_revision INTEGER NOT NULL,
                  request_sha256 TEXT NOT NULL,
                  operation TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  artifact_record_sha256 TEXT NOT NULL,
                  publication_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,artifact_id,artifact_revision),
                  UNIQUE(project_id,adapter_ref,request_sha256),
                  FOREIGN KEY(project_id,artifact_id,artifact_revision,artifact_record_sha256)
                    REFERENCES artifact_revisions(project_id,artifact_id,revision,record_sha256)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS three_d_runtime_claims (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  semantic_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS three_d_runtime_descriptions (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  node_attempt_id TEXT NOT NULL,
                  node_fence INTEGER NOT NULL,
                  idempotency_key TEXT NOT NULL,
                  description_json TEXT NOT NULL,
                  record_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key),
                  FOREIGN KEY(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key)
                    REFERENCES three_d_runtime_claims(project_id,adapter_ref,node_attempt_id,node_fence,idempotency_key)
                    ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS three_d_retarget_mapping_records (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  result_record_sha256 TEXT NOT NULL,
                  mapping_id TEXT NOT NULL,
                  mapping_version TEXT NOT NULL,
                  mapping_semantic_sha256 TEXT NOT NULL,
                  artifact_id TEXT NOT NULL,
                  artifact_revision INTEGER NOT NULL,
                  content_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,result_record_sha256,mapping_id,mapping_version),
                  UNIQUE(project_id,adapter_ref,artifact_id,artifact_revision),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS three_d_retarget_mappings_no_update BEFORE UPDATE ON three_d_retarget_mapping_records
                  BEGIN SELECT RAISE(ABORT,'3D retarget mappings are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_retarget_mappings_no_delete BEFORE DELETE ON three_d_retarget_mapping_records
                  BEGIN SELECT RAISE(ABORT,'3D retarget mappings cannot be deleted'); END;
                CREATE TABLE IF NOT EXISTS three_d_retarget_request_records (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  request_id TEXT NOT NULL,
                  request_version TEXT NOT NULL,
                  request_semantic_sha256 TEXT NOT NULL,
                  artifact_id TEXT NOT NULL,
                  artifact_revision INTEGER NOT NULL,
                  content_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,request_id,request_version),
                  UNIQUE(project_id,adapter_ref,artifact_id,artifact_revision),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS three_d_retarget_requests_no_update BEFORE UPDATE ON three_d_retarget_request_records
                  BEGIN SELECT RAISE(ABORT,'3D retarget requests are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_retarget_requests_no_delete BEFORE DELETE ON three_d_retarget_request_records
                  BEGIN SELECT RAISE(ABORT,'3D retarget requests cannot be deleted'); END;
                CREATE TABLE IF NOT EXISTS three_d_environment_manifest_records (
                  project_id TEXT NOT NULL,
                  adapter_ref TEXT NOT NULL,
                  result_record_sha256 TEXT NOT NULL,
                  environment_id TEXT NOT NULL,
                  manifest_semantic_sha256 TEXT NOT NULL,
                  artifact_id TEXT NOT NULL,
                  artifact_revision INTEGER NOT NULL,
                  content_sha256 TEXT NOT NULL,
                  PRIMARY KEY(project_id,adapter_ref,result_record_sha256,environment_id),
                  UNIQUE(project_id,adapter_ref,artifact_id,artifact_revision),
                  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON UPDATE RESTRICT ON DELETE RESTRICT
                );
                CREATE TRIGGER IF NOT EXISTS three_d_environment_manifests_no_update BEFORE UPDATE ON three_d_environment_manifest_records
                  BEGIN SELECT RAISE(ABORT,'3D environment manifests are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_environment_manifests_no_delete BEFORE DELETE ON three_d_environment_manifest_records
                  BEGIN SELECT RAISE(ABORT,'3D environment manifests cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_claims_no_update BEFORE UPDATE ON three_d_operation_claims
                  BEGIN SELECT RAISE(ABORT,'3D claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_claims_no_delete BEFORE DELETE ON three_d_operation_claims
                  BEGIN SELECT RAISE(ABORT,'3D claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_results_no_update BEFORE UPDATE ON three_d_operation_results
                  BEGIN SELECT RAISE(ABORT,'3D results are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_results_no_delete BEFORE DELETE ON three_d_operation_results
                  BEGIN SELECT RAISE(ABORT,'3D results cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_output_claims_no_update BEFORE UPDATE ON three_d_output_claims
                  BEGIN SELECT RAISE(ABORT,'3D output claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_output_claims_no_delete BEFORE DELETE ON three_d_output_claims
                  BEGIN SELECT RAISE(ABORT,'3D output claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_publications_no_update BEFORE UPDATE ON three_d_output_publications
                  BEGIN SELECT RAISE(ABORT,'3D output publications are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_publications_no_delete BEFORE DELETE ON three_d_output_publications
                  BEGIN SELECT RAISE(ABORT,'3D output publications cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_runtime_claims_no_update BEFORE UPDATE ON three_d_runtime_claims
                  BEGIN SELECT RAISE(ABORT,'3D runtime claims are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_runtime_claims_no_delete BEFORE DELETE ON three_d_runtime_claims
                  BEGIN SELECT RAISE(ABORT,'3D runtime claims cannot be deleted'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_runtime_no_update BEFORE UPDATE ON three_d_runtime_descriptions
                  BEGIN SELECT RAISE(ABORT,'3D runtime descriptions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS three_d_runtime_no_delete BEFORE DELETE ON three_d_runtime_descriptions
                  BEGIN SELECT RAISE(ABORT,'3D runtime descriptions cannot be deleted'); END;
                """
            )
        finally:
            connection.close()

    def _now(self) -> str:
        connection = self._connect()
        try:
            value = connection.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')"
            ).fetchone()[0]
        finally:
            connection.close()
        if not isinstance(value, str):
            raise ThreeDIntegrityError("database timestamp is unavailable")
        return value

    def _authorize_project(self, access: ProjectAccess, project_ref: ProjectRef) -> None:
        try:
            self.projects.get_project(access, project_ref)
        except ProjectIntegrityError as exc:
            raise ThreeDIntegrityError("3D Project evidence failed verification") from exc
        except (ProjectNotFoundError, ProjectScopeError) as exc:
            raise ThreeDScopeError("3D Project scope mismatch") from exc

    def _authorize_attempt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        capability: CapabilityRef | None,
    ) -> Mapping[str, object]:
        if not isinstance(attempt, NodeExecutionAttempt):
            raise ThreeDAuthorityError("exact NodeExecutionAttempt is required")
        if attempt.node_ref.project_ref != access.project_ref:
            raise ThreeDScopeError("3D Node attempt crossed Project scope")
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            try:
                _, _, task, graph = self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
            except (NodeExecutionAuthorityError, NodeExecutionError) as exc:
                raise ThreeDAuthorityError(
                    "3D Node attempt is stale, expired, or differs from durable authority"
                ) from exc
            if task.canonical_digest != attempt.task_digest:
                raise ThreeDIntegrityError("3D Task digest changed")
            node = next(
                (item for item in graph.nodes if item.node_ref == attempt.node_ref),
                None,
            )
            if node is None:
                raise ThreeDIntegrityError("3D Node disappeared from exact Graph revision")
            if capability is None:
                if not any(item.capability_id.startswith("3d.") for item in node.required_capabilities):
                    raise ThreeDAuthorityError("Node has no 3D capability authority")
            elif capability not in node.required_capabilities:
                raise ThreeDAuthorityError("exact 3D capability is not authorized by Node")
            constraints = dict(task.constraints)
            connection.commit()
            return constraints
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _authorize_request(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        *,
        verify_source: bool,
    ) -> ArtifactRef:
        if request.project_ref != access.project_ref:
            raise ThreeDScopeError("3D request crossed Project scope")
        self._authorize_project(access, request.project_ref)
        task_constraints = self._authorize_attempt(
            access,
            attempt,
            CapabilityRef(request.operation.capability_id, "1.0.0"),
        )
        if request.identity.adapter_ref != self.adapter_ref:
            raise ThreeDIntegrityError("3D request tool identity differs from adapter")
        if request.operation is ThreeDOperation.VALIDATE:
            self._authorize_validation_criteria(request, task_constraints)
        try:
            snapshot = self.workspaces.get_snapshot(
                access,
                request.candidate_snapshot_ref,
            )
            workspace = self.workspaces.get_workspace(
                access,
                request.candidate_snapshot_ref.workspace_ref,
            )
        except WorkspaceError as exc:
            raise ThreeDIntegrityError("3D Workspace evidence failed verification") from exc
        if (
            workspace.candidate_root_ref != request.control_root_ref
            or workspace.relative_path != request.working_directory
            or workspace.task_ref != attempt.task_ref
            or workspace.run_ref != attempt.run_ref
            or workspace.graph_ref != attempt.node_ref.graph_ref
            or workspace.node_ref != attempt.node_ref
            or workspace.node_attempt_id != attempt.attempt_id
            or workspace.node_attempt_fence != attempt.fence
            or snapshot.workspace_generation > workspace.generation
            or workspace.status.value in {
                "CLEANED",
                "CANCELLED",
                "LOST_UNCAPTURED",
            }
        ):
            raise ThreeDScopeError("3D request differs from exact Workspace root")
        if self.reality is ThreeDReality.REAL and (
            workspace.resource_allocation_ref != request.resource_allocation_ref
        ):
            raise ThreeDAuthorityError(
                "REAL 3D Workspace differs from exact ResourceAllocation"
            )
        if self.reality is ThreeDReality.REAL:
            self._authorize_real_allocation(
                access,
                attempt,
                request.resource_allocation_ref,
                request.identity,
            )
        for artifact_ref in request.all_source_artifact_refs:
            artifact = self.artifacts.get_artifact(access, artifact_ref)
            if artifact.content_ref is None:
                raise ThreeDIntegrityError("3D source Artifact has no exact content")
            try:
                self.object_store.verify(artifact.content_ref)
            except ObjectStorageError as exc:
                raise ThreeDIntegrityError("3D source content failed verification") from exc
        if verify_source and request.source_path is not None:
            primary = self.artifacts.get_artifact(
                access,
                request.source_artifact_refs[0],
            )
            assert primary.content_ref is not None
            self._verify_workspace_file(
                access,
                request.control_root_ref,
                f"{request.working_directory}/{request.source_path}",
                primary.content_ref,
            )
            for path, artifact_ref in request.auxiliary_artifact_bindings.items():
                auxiliary = self.artifacts.get_artifact(access, artifact_ref)
                if auxiliary.content_ref is None:
                    raise ThreeDIntegrityError(
                        "3D auxiliary Artifact has no exact content"
                    )
                self._verify_workspace_file(
                    access,
                    request.control_root_ref,
                    f"{request.working_directory}/{path}",
                    auxiliary.content_ref,
                )
        return snapshot.artifact_ref

    @staticmethod
    def _authorize_validation_criteria(
        request: ThreeDOperationRequest,
        constraints: Mapping[str, object],
    ) -> None:
        supplied = request.validation_requirements

        def scoped(name: str) -> _Scalar | None:
            present = [
                constraints[key]
                for key in (
                    f"three_d.validation.{name}",
                    f"three_d.{name}",
                    name,
                )
                if key in constraints
            ]
            if len(present) > 1 and any(value != present[0] for value in present[1:]):
                raise ThreeDIntegrityError(
                    "3D Task contains conflicting scoped validation criteria"
                )
            return None if not present else cast(_Scalar, present[0])

        for name in (
            "require_mesh",
            "require_manifold",
            "reject_degenerate_faces",
            "reject_duplicate_vertices",
            "require_valid_normals",
            "require_uv",
        ):
            required = scoped(name)
            if required is None:
                continue
            if not isinstance(required, bool):
                raise ThreeDIntegrityError("3D Task boolean criterion is malformed")
            if required and getattr(supplied, name) is not True:
                raise ThreeDAuthorityError(
                    "3D validation request weakens an exact Task criterion"
                )
        maximum_faces = scoped("maximum_faces")
        if maximum_faces is not None:
            if not isinstance(maximum_faces, int) or isinstance(maximum_faces, bool):
                raise ThreeDIntegrityError("3D Task maximum_faces is malformed")
            if supplied.maximum_faces is None or supplied.maximum_faces > maximum_faces:
                raise ThreeDAuthorityError(
                    "3D validation request weakens the Task face limit"
                )
        minimum_dimension = scoped("minimum_dimension")
        if minimum_dimension is not None:
            if isinstance(minimum_dimension, bool) or not isinstance(
                minimum_dimension,
                (int, float),
            ):
                raise ThreeDIntegrityError("3D Task minimum_dimension is malformed")
            if (
                supplied.minimum_dimension is None
                or supplied.minimum_dimension < float(minimum_dimension)
            ):
                raise ThreeDAuthorityError(
                    "3D validation request weakens the Task minimum dimension"
                )
        maximum_dimension = scoped("maximum_dimension")
        if maximum_dimension is not None:
            if isinstance(maximum_dimension, bool) or not isinstance(
                maximum_dimension,
                (int, float),
            ):
                raise ThreeDIntegrityError("3D Task maximum_dimension is malformed")
            if (
                supplied.maximum_dimension is None
                or supplied.maximum_dimension > float(maximum_dimension)
            ):
                raise ThreeDAuthorityError(
                    "3D validation request weakens the Task maximum dimension"
                )
        required_units = scoped("required_unit_system")
        if required_units is not None and (
            not isinstance(required_units, str)
            or supplied.required_unit_system != required_units
        ):
            raise ThreeDAuthorityError(
                "3D validation request differs from the Task unit system"
            )

    def _authorize_real_allocation(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        allocation_ref: ResourceAllocationRef | None,
        identity: ThreeDToolIdentity,
    ) -> None:
        if allocation_ref is None:
            raise ThreeDAuthorityError(
                "REAL 3D execution requires an exact ResourceAllocation"
            )
        try:
            allocation = self.scheduler.get_allocation(
                access,
                allocation_ref,
            )
            if (
                allocation.status != "DISPATCHED"
                or allocation.node_ref != attempt.node_ref
                or allocation.run_ref != attempt.run_ref
                or allocation.run_attempt_id != attempt.run_attempt_id
                or allocation.run_attempt_fence != attempt.run_fence
                or allocation.node_attempt_id != attempt.attempt_id
                or allocation.node_attempt_fence != attempt.fence
                or not allocation.side_effect_targets
            ):
                raise ThreeDAuthorityError(
                    "REAL 3D ResourceAllocation or Workspace side effect is not exact"
                )
            connection = self._connect()
            try:
                connection.execute("BEGIN")
                _, _, _, graph = self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
                connection.commit()
            finally:
                connection.close()
            node = next(
                (item for item in graph.nodes if item.node_ref == attempt.node_ref),
                None,
            )
            expected_target = (
                None
                if node is None
                else node.resource_hints.get("side_effect_target")
            )
            if (
                not isinstance(expected_target, str)
                or allocation.side_effect_targets != (expected_target,)
            ):
                raise ThreeDAuthorityError(
                    "REAL 3D allocation differs from the Node side-effect target"
                )
        except ThreeDAuthorityError:
            raise
        except (
            NodeExecutionAuthorityError,
            NodeExecutionError,
            ResourceError,
            SchedulerError,
        ) as exc:
            raise ThreeDAuthorityError(
                "REAL 3D ResourceAllocation evidence failed verification"
            ) from exc

    def _authorize_observed_tool(
        self,
        access: ProjectAccess,
        allocation_ref: ResourceAllocationRef,
        identity: ThreeDToolIdentity,
    ) -> None:
        expected_tool_refs = {
            (
                f"tool://blender/{identity.tool_version}/"
                f"{identity.executable_sha256}"
            )
        }
        if identity.sandbox_launcher_sha256 is not None:
            expected_tool_refs.add(
                "tool://bubblewrap/exact/"
                f"{identity.sandbox_launcher_sha256}"
            )
        try:
            allocation = self.scheduler.get_allocation(access, allocation_ref)
            snapshots = tuple(
                self.resources.get_snapshot(access, item.snapshot_ref)
                for item in allocation.reservations
            )
        except (ResourceError, SchedulerError) as exc:
            raise ThreeDAuthorityError(
                "REAL Blender resource observation failed verification"
            ) from exc
        if not any(
            expected_tool_refs <= set(item.locality.installed_tool_refs)
            for item in snapshots
        ):
            raise ThreeDAuthorityError(
                "REAL Blender or sandbox identity was not observed on the allocated resource"
            )

    def _verify_workspace_file(
        self,
        access: ProjectAccess,
        root_ref: FilesystemRootRef,
        path: str,
        expected: ContentRef,
    ) -> None:
        root = self.filesystem.get_root(access, root_ref)
        try:
            descriptor, state = FilesystemAdapter._open_regular(root, path)
        except FilesystemError as exc:
            raise ThreeDIntegrityError("exact 3D Workspace source is unavailable") from exc
        digest = hashlib.sha256()
        size = 0
        try:
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        finally:
            os.close(descriptor)
        if state.st_size != size or expected.size_bytes != size or not hmac.compare_digest(expected.digest, digest.hexdigest()):
            raise ThreeDIntegrityError("3D Workspace source differs from exact Artifact")

    @staticmethod
    def _claim_values(
        attempt: NodeExecutionAttempt,
        adapter_ref: str,
        request: ThreeDOperationRequest,
        idempotency_key: str,
    ) -> tuple[object, ...]:
        if not isinstance(idempotency_key, str) or _KEY.fullmatch(idempotency_key) is None:
            raise ThreeDContractError("3D idempotency key is malformed")
        return (
            request.project_ref.value,
            adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            request.operation.value,
            idempotency_key,
        )

    def _output_target_identity(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> tuple[int, int, str]:
        descriptor, state, output_name = self._open_output_directory(
            access,
            request,
        )
        os.close(descriptor)
        return state.st_dev, state.st_ino, output_name

    def _open_output_directory(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> tuple[int, os.stat_result, str]:
        root = self.filesystem.get_root(access, request.control_root_ref)
        output = PurePosixPath(request.output_path)
        directory_relative = PurePosixPath(
            request.working_directory,
            output.parent,
        ).as_posix()
        try:
            parts = FilesystemAdapter._relative_parts(directory_relative)
            parent, leaf = FilesystemAdapter._parent_descriptor(root, parts)
            descriptor = parent
            if leaf is not None:
                try:
                    FilesystemAdapter._safe_state(
                        parent,
                        leaf,
                        allow_directory=True,
                    )
                    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                    flags |= getattr(os, "O_NOFOLLOW", 0)
                    descriptor = os.open(leaf, flags, dir_fd=parent)
                finally:
                    os.close(parent)
            try:
                FilesystemAdapter._assert_descriptor_beneath(root, descriptor)
                state = os.fstat(descriptor)
            except Exception:
                os.close(descriptor)
                raise
        except (FilesystemError, OSError) as exc:
            raise ThreeDScopeError(
                "3D output directory lacks a stable Workspace identity"
            ) from exc
        return descriptor, state, output.name

    def _verify_output_claim_identity(
        self,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        directory_device: int,
        directory_inode: int,
        output_name: str,
    ) -> None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT project_id,adapter_ref,workspace_id,request_sha256,"
                "node_attempt_id,node_fence FROM three_d_output_claims "
                "WHERE directory_device=? AND directory_inode=? AND output_name=?",
                (directory_device, directory_inode, output_name),
            ).fetchone()
        finally:
            connection.close()
        if (
            row is None
            or row["project_id"] != request.project_ref.value
            or row["adapter_ref"] != self.adapter_ref
            or row["workspace_id"]
            != request.candidate_snapshot_ref.workspace_ref.workspace_id
            or not hmac.compare_digest(
                cast(str, row["request_sha256"]),
                request.request_sha256,
            )
            or row["node_attempt_id"] != attempt.attempt_id
            or row["node_fence"] != attempt.fence
        ):
            raise ThreeDIntegrityError(
                "3D output directory identity changed after its exact claim"
            )

    def _verify_output_target_claim(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
    ) -> None:
        directory_device, directory_inode, output_name = (
            self._output_target_identity(access, request)
        )
        self._verify_output_claim_identity(
            attempt,
            request,
            directory_device,
            directory_inode,
            output_name,
        )

    def _pin_output_target(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        *,
        allow_existing: bool,
    ) -> tuple[int, str, bool]:
        descriptor, state, output_name = self._open_output_directory(
            access,
            request,
        )
        try:
            self._verify_output_claim_identity(
                attempt,
                request,
                state.st_dev,
                state.st_ino,
                output_name,
            )
            try:
                output_state = os.stat(
                    output_name,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return descriptor, output_name, False
            if not stat.S_ISREG(output_state.st_mode):
                raise ThreeDConflictError(
                    "3D output leaf is not an unclaimed regular-file slot"
                )
            if not allow_existing:
                raise ThreeDConflictError(
                    "3D output leaf already contains unclaimed bytes"
                )
            return descriptor, output_name, True
        except Exception:
            os.close(descriptor)
            raise

    def _preflight_output_target(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> None:
        descriptor, _, output_name = self._open_output_directory(access, request)
        try:
            try:
                os.stat(
                    output_name,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return
            raise ThreeDConflictError(
                "3D output leaf already contains unclaimed bytes"
            )
        finally:
            os.close(descriptor)

    def _claim(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        idempotency_key: str,
        *,
        require_output_absent: bool = False,
    ) -> ThreeDOperationResult | None:
        values = self._claim_values(attempt, self.adapter_ref, request, idempotency_key)
        run_attempt = self._run_attempt(access, attempt)
        if require_output_absent:
            self._preflight_output_target(access, request)
        directory_device, directory_inode, output_name = (
            self._output_target_identity(access, request)
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT request_sha256 FROM three_d_operation_claims WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            if row is None:
                try:
                    _, _, task, _ = self.executions._require_live_attempt(
                        connection,
                        access,
                        attempt,
                        allowed_statuses={"RUNNING"},
                    )
                    current_run = (
                        self.runs.assert_current_run_authority_in_transaction(
                            connection,
                            access,
                            run_attempt,
                        )
                    )
                except (
                    NodeExecutionAuthorityError,
                    NodeExecutionError,
                    RunAuthorityError,
                    RunError,
                ) as exc:
                    raise ThreeDAuthorityError(
                        "3D claim lost exact Node or Run authority"
                    ) from exc
                if (
                    task.canonical_digest != attempt.task_digest
                    or current_run.task_ref != attempt.task_ref
                    or current_run.task_digest != attempt.task_digest
                ):
                    raise ThreeDAuthorityError(
                        "3D claim Task authority changed"
                    )
                if require_output_absent:
                    self._preflight_output_target(access, request)
                connection.execute(
                    "INSERT INTO three_d_operation_claims VALUES (?,?,?,?,?,?,?)",
                    (*values, request.request_sha256),
                )
                connection.execute(
                    "INSERT INTO three_d_output_claims VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        request.project_ref.value,
                        self.adapter_ref,
                        request.candidate_snapshot_ref.workspace_ref.workspace_id,
                        directory_device,
                        directory_inode,
                        output_name,
                        request.request_sha256,
                        attempt.attempt_id,
                        attempt.fence,
                    ),
                )
                connection.execute(
                    "INSERT INTO three_d_operation_inflight VALUES (?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%f+00:00','now'))",
                    values,
                )
                connection.commit()
                return None
            if not hmac.compare_digest(cast(str, row["request_sha256"]), request.request_sha256):
                raise ThreeDConflictError("3D idempotency identity changed")
            output_claim = connection.execute(
                "SELECT project_id,adapter_ref,workspace_id,request_sha256,"
                "node_attempt_id,node_fence FROM three_d_output_claims "
                "WHERE directory_device=? AND directory_inode=? AND output_name=?",
                (
                    directory_device,
                    directory_inode,
                    output_name,
                ),
            ).fetchone()
            if (
                output_claim is None
                or output_claim["project_id"] != request.project_ref.value
                or output_claim["adapter_ref"] != self.adapter_ref
                or output_claim["workspace_id"]
                != request.candidate_snapshot_ref.workspace_ref.workspace_id
                or not hmac.compare_digest(
                    cast(str, output_claim["request_sha256"]),
                    request.request_sha256,
                )
                or output_claim["node_attempt_id"] != attempt.attempt_id
                or output_claim["node_fence"] != attempt.fence
            ):
                raise ThreeDIntegrityError("3D output path claim changed")
            result_row = connection.execute(
                "SELECT result_json,record_sha256 FROM three_d_operation_results WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            inflight = connection.execute(
                "SELECT started_at FROM three_d_operation_inflight "
                "WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? "
                "AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            connection.commit()
            if result_row is None:
                if inflight is None or not isinstance(inflight["started_at"], str):
                    raise ThreeDIntegrityError(
                        "incomplete 3D claim lost its durable inflight evidence"
                    )
                connection.execute("BEGIN IMMEDIATE")
                try:
                    _, _, task, _ = self.executions._require_live_attempt(
                        connection,
                        access,
                        attempt,
                        allowed_statuses={"RUNNING"},
                    )
                    current_run = (
                        self.runs.assert_current_run_authority_in_transaction(
                            connection,
                            access,
                            run_attempt,
                        )
                    )
                except (
                    NodeExecutionAuthorityError,
                    NodeExecutionError,
                    RunAuthorityError,
                    RunError,
                ) as exc:
                    raise ThreeDAuthorityError(
                        "incomplete 3D claim lost exact Node or Run authority"
                    ) from exc
                if (
                    task.canonical_digest != attempt.task_digest
                    or current_run.task_ref != attempt.task_ref
                    or current_run.task_digest != attempt.task_digest
                ):
                    raise ThreeDAuthorityError(
                        "incomplete 3D claim Task authority changed"
                    )
                connection.commit()
                return None
            if inflight is not None:
                raise ThreeDIntegrityError(
                    "terminal 3D result retained contradictory inflight evidence"
                )
            result = self._result_from_row(result_row)
            self._verify_replayed_result(access, attempt, request, result)
            return result
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ThreeDConflictError(
                "3D output path is already claimed by another exact operation"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _claim_state(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        idempotency_key: str,
        *,
        require_output_absent: bool = False,
    ) -> tuple[bool, ThreeDOperationResult | None]:
        """Distinguish absent, recoverable inflight, and terminal claims."""

        values = self._claim_values(
            attempt,
            self.adapter_ref,
            request,
            idempotency_key,
        )
        connection = self._connect()
        try:
            claim = connection.execute(
                "SELECT 1 FROM three_d_operation_claims WHERE project_id=? "
                "AND adapter_ref=? AND node_attempt_id=? AND node_fence=? "
                "AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
        finally:
            connection.close()
        if claim is None:
            return False, None
        result = self._claim(
            access,
            attempt,
            request,
            idempotency_key,
            require_output_absent=require_output_absent,
        )
        return True, result

    def _managed_process_state(
        self,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
    ) -> str:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT call_id FROM managed_process_claims WHERE project_id=? "
                "AND node_attempt_id=? AND idempotency_key=?",
                (
                    request.project_ref.value,
                    attempt.attempt_id,
                    f"three-d-blender-{request.request_sha256[:36]}",
                ),
            ).fetchone()
            if row is None:
                return "ABSENT"
            execution = connection.execute(
                "SELECT executable_sha256 FROM managed_process_executions "
                "WHERE project_id=? AND call_id=?",
                (request.project_ref.value, row["call_id"]),
            ).fetchone()
            prepared = connection.execute(
                "SELECT executable_sha256 FROM "
                "managed_process_prepared_executions "
                "WHERE project_id=? AND call_id=?",
                (request.project_ref.value, row["call_id"]),
            ).fetchone()
            result = connection.execute(
                "SELECT 1 FROM managed_process_results WHERE project_id=? "
                "AND call_id=?",
                (request.project_ref.value, row["call_id"]),
            ).fetchone()
        finally:
            connection.close()
        if (
            prepared is not None
            and prepared["executable_sha256"]
            != request.identity.process_executable_sha256
        ) or (
            execution is not None
            and execution["executable_sha256"]
            != request.identity.process_executable_sha256
        ):
            raise ThreeDIntegrityError(
                "durable managed Blender execution identity changed"
            )
        if result is not None:
            return "RESULT"
        if execution is not None:
            return "STARTED"
        if prepared is not None:
            return "PREPARED"
        return "CLAIMED"

    def _persist(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        idempotency_key: str,
        *,
        publication: _ThreeDPublication | None = None,
    ) -> ThreeDOperationResult:
        self._authorize_request(
            access,
            attempt,
            request,
            verify_source=False,
        )
        if publication is None:
            self._preflight_output_target(access, request)
        self._verify_output_target_claim(access, attempt, request)
        self._verify_candidate_result(
            access,
            attempt,
            request,
            result,
            publication,
        )
        values = self._claim_values(attempt, self.adapter_ref, request, idempotency_key)
        run_attempt = self._run_attempt(access, attempt)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _, _, task, _ = self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
                current_run = self.runs.assert_current_run_authority_in_transaction(
                    connection,
                    access,
                    run_attempt,
                )
            except (
                NodeExecutionAuthorityError,
                NodeExecutionError,
                RunAuthorityError,
                RunError,
            ) as exc:
                raise ThreeDAuthorityError(
                    "3D result lost exact Node or Run authority before publication"
                ) from exc
            if (
                task.canonical_digest != attempt.task_digest
                or current_run.task_ref != attempt.task_ref
                or current_run.task_digest != attempt.task_digest
            ):
                raise ThreeDAuthorityError("3D result Task authority changed")
            claim = connection.execute(
                "SELECT request_sha256 FROM three_d_operation_claims WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            if claim is None or not hmac.compare_digest(
                cast(str, claim["request_sha256"]),
                request.request_sha256,
            ):
                raise ThreeDIntegrityError("3D publication lost its exact claim")
            if publication is None:
                self._preflight_output_target(access, request)
            prior = connection.execute(
                "SELECT result_json,record_sha256 FROM three_d_operation_results WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                values,
            ).fetchone()
            if prior is None:
                if publication is not None:
                    published = self._insert_publication(
                        connection,
                        attempt,
                        request,
                        run_attempt,
                        publication,
                    )
                    if result.output_artifact_ref != published.artifact_ref:
                        raise ThreeDIntegrityError(
                            "3D result differs from atomic output publication"
                        )
                elif result.reality is ThreeDReality.REAL and result.output_artifact_ref is not None:
                    raise ThreeDIntegrityError(
                        "REAL 3D result lacks atomic publication material"
                    )
                connection.execute(
                    "INSERT INTO three_d_operation_results VALUES (?,?,?,?,?,?,?,?)",
                    (*values, _json(result.payload()), result.record_sha256),
                )
                connection.execute(
                    "DELETE FROM three_d_operation_inflight WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND operation=? AND idempotency_key=?",
                    values,
                )
                connection.commit()
                self._verify_replayed_result(access, attempt, request, result)
                return result
            connection.commit()
            persisted = self._result_from_row(prior)
            self._verify_replayed_result(access, attempt, request, persisted)
            return persisted
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _verify_candidate_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        publication: _ThreeDPublication | None,
    ) -> None:
        if publication is None:
            self._verify_replayed_result(access, attempt, request, result)
            return
        if (
            result.project_ref != request.project_ref
            or result.operation is not request.operation
            or result.request_sha256 != request.request_sha256
            or result.identity_digest != request.identity.semantic_digest
            or result.adapter_ref != self.adapter_ref
            or result.reality is not ThreeDReality.REAL
            or result.node_attempt_id != attempt.attempt_id
            or result.node_fence != attempt.fence
            or result.source_artifact_refs != request.all_source_artifact_refs
            or result.output_artifact_ref != self._output_artifact_ref(request)
            or result.output_content_ref != publication.output_content_ref
            or result.report_ref != publication.report_ref
            or result.process_artifact_ref is None
            or result.process_artifact_ref
            not in publication.evidence_artifact_refs
            or result.process_call_ref is None
            or result.output_role != request.output_role
            or result.output_path != request.output_path
            or result.preview_only
            != (request.operation is ThreeDOperation.PREVIEW)
        ):
            raise ThreeDIntegrityError(
                "candidate REAL 3D publication classification changed"
            )
        self.object_store.verify(publication.output_content_ref)
        self.object_store.verify(publication.report_ref)
        process = self.process.get_result(
            access,
            ToolCallRef(
                request.project_ref,
                result.process_call_ref.rsplit("/", 1)[-1],
            ),
        )
        self._verify_process_claim(
            attempt,
            f"three-d-blender-{request.request_sha256[:36]}",
            process,
        )
        driver_ref, driver_artifact_ref = self._staged_driver_evidence(
            access,
            attempt,
            request.identity,
            request.control_root_ref,
            request.working_directory,
        )
        staged_request_ref = self._staged_request_evidence(
            access,
            attempt,
            request,
        )
        (
            expected_process_request,
            _,
            driver_path,
            _,
        ) = self._operation_process_request(
            access,
            request,
            driver_ref,
            staged_request_ref,
            require_files=False,
        )
        process_request = json.loads(self.object_store.read(process.request_ref))
        if (
            process.artifact_ref != result.process_artifact_ref
            or process.tool_call_ref.value != result.process_call_ref
            or process.process_identity is None
            or process.process_identity.executable_sha256
            != request.identity.process_executable_sha256
            or process_request != expected_process_request.payload()
            or driver_artifact_ref not in publication.evidence_artifact_refs
            or publication.request_ref != staged_request_ref
        ):
            raise ThreeDIntegrityError(
                "candidate REAL 3D process identity changed"
            )
        try:
            report = self._driver_report(self.object_store.read(process.stdout_ref))
        except ThreeDIntegrityError:
            report = self._fallback_driver_report(request, process)
        report_bytes = _json(report).encode()
        if (
            publication.report_ref.media_type
            != "application/vnd.biella.3d-report+json"
            or publication.report_ref.digest
            != hashlib.sha256(report_bytes).hexdigest()
            or publication.report_ref.size_bytes != len(report_bytes)
        ):
            raise ThreeDIntegrityError(
                "candidate REAL 3D report differs from exact process"
            )
        if not self._accepted_driver_evidence(
            access,
            request,
            report,
            driver_path,
            driver_ref,
        ):
            raise ThreeDIntegrityError(
                "candidate REAL 3D lacks exact Blender driver evidence"
            )
        process_succeeded = (
            process.status is ProcessStatus.SUCCEEDED
            and not isinstance(report.get("error"), str)
        )
        if process_succeeded:
            self._verify_operation_report_schema(request, report)
            runtime = report.get("runtime")
            if (
                not isinstance(runtime, dict)
                or runtime.get("tool_name") != "Blender"
                or runtime.get("tool_version") != request.identity.tool_version
                or runtime.get("binary_path") != request.identity.executable_path
                or runtime.get("binary_sha256")
                != request.identity.executable_sha256
                or runtime.get("driver_path") != str(driver_path)
                or runtime.get("driver_sha256")
                != request.identity.driver_sha256
                or runtime.get("driver_size_bytes") != driver_ref.size_bytes
                or not isinstance(runtime.get("embedded_python"), str)
                or not runtime.get("embedded_python")
                or runtime.get("external_plugins")
                != [item.payload() for item in request.identity.plugins]
                or runtime.get("factory_startup") is not True
                or report.get("request_sha256") != request.request_sha256
                or report.get("operation") != request.operation.value
                or report.get("source_path") != request.source_path
                or report.get("output_path") != request.output_path
                or report.get("content_trust") != "UNTRUSTED_DATA"
                or report.get("input_content_bindings")
                != self._input_content_bindings(access, request)
                or report.get("used_auxiliary_paths")
                != list(request.auxiliary_artifact_bindings)
                or (
                    request.operation is ThreeDOperation.VALIDATE
                    and not isinstance(report.get("valid"), bool)
                )
            ):
                raise ThreeDIntegrityError(
                    "candidate Blender report identity changed"
                )
            output_subject_operation = request.operation in {
                ThreeDOperation.MODEL,
                ThreeDOperation.MESH_EDIT,
                ThreeDOperation.TOPOLOGY,
                ThreeDOperation.UV,
                ThreeDOperation.MATERIAL,
                ThreeDOperation.RIG,
                ThreeDOperation.SKIN,
                ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
                ThreeDOperation.SCENE,
                ThreeDOperation.CONVERT,
                ThreeDOperation.OPTIMIZE,
            }
            expected_subject = (
                publication.output_content_ref
                if output_subject_operation and publication.output_observed
                else self.artifacts.get_artifact(
                    access,
                    request.source_artifact_refs[0],
                ).content_ref
            )
            subject = report.get("inspection_subject")
            if (
                expected_subject is None
                or not isinstance(subject, dict)
                or subject.get("sha256") != expected_subject.digest
                or subject.get("size_bytes") != expected_subject.size_bytes
            ):
                raise ThreeDIntegrityError(
                    "candidate Blender inspection subject changed"
                )
            if publication.output_observed:
                if request.operation in {
                    ThreeDOperation.INSPECT,
                    ThreeDOperation.VALIDATE,
                }:
                    if publication.output_content_ref != publication.report_ref:
                        raise ThreeDIntegrityError(
                            "candidate Blender report output changed"
                        )
                else:
                    output = report.get("output")
                    if (
                        not isinstance(output, dict)
                        or output.get("sha256")
                        != publication.output_content_ref.digest
                        or output.get("size_bytes")
                        != publication.output_content_ref.size_bytes
                    ):
                        raise ThreeDIntegrityError(
                            "candidate Blender output identity changed"
                        )
        expected_technical: bool | None = None
        if request.operation is ThreeDOperation.VALIDATE:
            expected_technical = report.get("valid") is True and process_succeeded
        expected_status = (
            ThreeDStatus.SUCCEEDED
            if process_succeeded
            and (
                request.operation is not ThreeDOperation.VALIDATE
                or expected_technical
            )
            else ThreeDStatus.FAILED
        )
        expected_failure: str | None = None
        if expected_status is ThreeDStatus.FAILED:
            expected_failure = self._process_failure_reason(
                request,
                process,
                report,
            )
        if expected_status is ThreeDStatus.SUCCEEDED and not publication.output_observed:
            expected_status = ThreeDStatus.FAILED
            expected_failure = "Blender exited without the exact requested output"
        expected_editable = self._editable_classification(
            request,
            report,
            expected_status,
        )
        expected_media_type = (
            request.output_media_type
            if publication.output_observed
            else "application/vnd.biella.3d-report+json"
        )
        if (
            publication.status is not expected_status
            or result.status is not expected_status
            or result.technical_valid != expected_technical
            or result.failure_reason != expected_failure
            or result.editable_source != expected_editable
            or publication.output_content_ref.media_type != expected_media_type
        ):
            raise ThreeDIntegrityError(
                "candidate REAL 3D outcome differs from durable evidence"
            )

    @staticmethod
    def _result_from_row(row: Mapping[str, object]) -> ThreeDOperationResult:
        try:
            payload = json.loads(cast(str, row["result_json"]))
            if not isinstance(payload, dict):
                raise TypeError
            project_ref = ProjectRef(cast(str, payload["project_ref"]))
            sources = tuple(
                cast(ArtifactRef, _artifact_from_value(item, project_ref))
                for item in cast(list[object], payload["source_artifact_refs"])
            )
            result = ThreeDOperationResult(
                project_ref=project_ref,
                operation=ThreeDOperation(cast(str, payload["operation"])),
                request_sha256=cast(str, payload["request_sha256"]),
                identity_digest=cast(str, payload["identity_digest"]),
                adapter_ref=cast(str, payload["adapter_ref"]),
                reality=ThreeDReality(cast(str, payload["reality"])),
                status=ThreeDStatus(cast(str, payload["status"])),
                node_attempt_id=cast(str, payload["node_attempt_id"]),
                node_fence=cast(int, payload["node_fence"]),
                source_artifact_refs=sources,
                output_artifact_ref=_artifact_from_value(payload["output_artifact_ref"], project_ref),
                output_content_ref=_content_from_payload(payload["output_content_ref"]),
                report_ref=_content_from_payload(payload["report_ref"]),
                process_artifact_ref=_artifact_from_value(payload["process_artifact_ref"], project_ref),
                process_call_ref=cast(str | None, payload["process_call_ref"]),
                output_role=cast(str | None, payload["output_role"]),
                output_path=cast(str | None, payload["output_path"]),
                editable_source=cast(bool, payload["editable_source"]),
                preview_only=cast(bool, payload["preview_only"]),
                technical_valid=cast(bool | None, payload["technical_valid"]),
                failure_reason=cast(str | None, payload["failure_reason"]),
                observed_at=cast(str, payload["observed_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ThreeDIntegrityError("persisted 3D result is malformed") from exc
        if not hmac.compare_digest(result.record_sha256, cast(str, row["record_sha256"])):
            raise ThreeDIntegrityError("persisted 3D result digest changed")
        return result

    def _verify_replayed_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
    ) -> None:
        if (
            result.project_ref != request.project_ref
            or result.operation is not request.operation
            or result.request_sha256 != request.request_sha256
            or result.identity_digest != request.identity.semantic_digest
            or result.adapter_ref != self.adapter_ref
            or result.node_attempt_id != attempt.attempt_id
            or result.node_fence != attempt.fence
            or result.source_artifact_refs != request.all_source_artifact_refs
            or (
                self.reality is ThreeDReality.REAL
                and result.reality
                not in {ThreeDReality.REAL, ThreeDReality.NOT_RUN}
            )
            or (
                self.reality is ThreeDReality.REFERENCE
                and result.reality is not ThreeDReality.REFERENCE
            )
        ):
            raise ThreeDIntegrityError("persisted 3D result identity changed")
        try:
            if (
                result.reality in {
                    ThreeDReality.REFERENCE,
                    ThreeDReality.NOT_RUN,
                }
                or result.output_artifact_ref is None
            ):
                self._preflight_output_target(access, request)
            for content_ref in (result.output_content_ref, result.report_ref):
                if content_ref is not None:
                    self.object_store.verify(content_ref)

            connection = self._connect()
            try:
                process_claim = connection.execute(
                    "SELECT call_id FROM managed_process_claims "
                    "WHERE project_id=? AND node_attempt_id=? "
                    "AND idempotency_key=?",
                    (
                        request.project_ref.value,
                        attempt.attempt_id,
                        f"three-d-blender-{request.request_sha256[:36]}",
                    ),
                ).fetchone()
                publication_evidence = connection.execute(
                    "SELECT artifact_id,artifact_revision "
                    "FROM three_d_output_publications "
                    "WHERE project_id=? AND adapter_ref=? "
                    "AND request_sha256=?",
                    (
                        request.project_ref.value,
                        self.adapter_ref,
                        request.request_sha256,
                    ),
                ).fetchone()
            finally:
                connection.close()

            attempted_not_run = (
                result.reality is ThreeDReality.NOT_RUN
                and result.process_artifact_ref is not None
                and result.process_call_ref is not None
            )
            if result.reality is ThreeDReality.NOT_RUN and not attempted_not_run:
                unavailable_reason = result.failure_reason
                if unavailable_reason not in {
                    "exact Blender executable is unavailable",
                    "exact bubblewrap sandbox launcher is unavailable",
                }:
                    raise ThreeDIntegrityError(
                        "persisted NOT_RUN dependency reason changed"
                    )
                unavailable_bytes = _json(
                    self._unavailability_report(request, unavailable_reason)
                ).encode()
                if (
                    self.reality is not ThreeDReality.REAL
                    or result.status is not ThreeDStatus.NOT_RUN
                    or result.output_artifact_ref is not None
                    or result.output_content_ref is not None
                    or result.report_ref is None
                    or result.report_ref.media_type
                    != "application/vnd.biella.3d-unavailability+json"
                    or result.report_ref.digest
                    != hashlib.sha256(unavailable_bytes).hexdigest()
                    or result.report_ref.size_bytes != len(unavailable_bytes)
                    or process_claim is not None
                    or publication_evidence is not None
                    or result.output_role is not None
                    or result.output_path is not None
                    or result.editable_source
                    or result.preview_only
                    or result.technical_valid is not None
                    or result.failure_reason != unavailable_reason
                ):
                    raise ThreeDIntegrityError(
                        "persisted NOT_RUN 3D classification changed"
                    )
                return

            expected_preview = (
                result.reality is not ThreeDReality.NOT_RUN
                and request.operation is ThreeDOperation.PREVIEW
            )
            if result.preview_only != expected_preview:
                raise ThreeDIntegrityError(
                    "persisted 3D preview classification changed"
                )

            if result.reality is ThreeDReality.REFERENCE:
                if (
                    result.output_artifact_ref
                    != request.reference_output_artifact_ref
                    or result.output_artifact_ref is None
                    or result.process_artifact_ref is not None
                    or result.process_call_ref is not None
                    or process_claim is not None
                    or publication_evidence is not None
                    or result.output_role != request.output_role
                    or result.output_path != request.output_path
                    or result.editable_source
                ):
                    raise ThreeDIntegrityError(
                        "persisted REFERENCE 3D classification changed"
                    )
                reference = self.artifacts.get_artifact(
                    access,
                    result.output_artifact_ref,
                )
                if (
                    reference.role != request.output_role
                    or reference.content_ref is None
                    or reference.content_ref.media_type
                    != request.output_media_type
                    or _content_payload(reference.content_ref)
                    != _content_payload(result.output_content_ref)
                    or _content_payload(reference.content_ref)
                    != _content_payload(result.report_ref)
                    or not set(request.all_source_artifact_refs)
                    <= set(reference.source_artifact_refs)
                ):
                    raise ThreeDIntegrityError(
                        "persisted REFERENCE 3D evidence changed"
                    )
                reference_technical: bool | None = None
                reference_status = ThreeDStatus.SUCCEEDED
                reference_failure: str | None = None
                if request.operation is ThreeDOperation.VALIDATE:
                    reference_technical = self._reference_validation_result(
                        access,
                        request,
                        reference,
                    )
                    if not reference_technical:
                        reference_status = ThreeDStatus.FAILED
                        reference_failure = "reference technical validation failed"
                if (
                    result.status is not reference_status
                    or result.technical_valid != reference_technical
                    or result.failure_reason != reference_failure
                ):
                    raise ThreeDIntegrityError(
                        "persisted REFERENCE 3D outcome changed"
                    )
                return

            if (
                result.process_artifact_ref is None
                or result.process_call_ref is None
                or result.report_ref is None
                or result.report_ref.media_type
                != "application/vnd.biella.3d-report+json"
            ):
                raise ThreeDIntegrityError(
                    "persisted REAL 3D execution evidence is incomplete"
                )
            process_artifact = self.artifacts.get_artifact(
                access,
                result.process_artifact_ref,
            )
            if process_artifact.role != "process.execution.result":
                raise ThreeDIntegrityError(
                    "persisted 3D process evidence role changed"
                )
            if process_artifact.content_ref is not None:
                self.object_store.verify(process_artifact.content_ref)
            call_prefix = f"tool-call://{request.project_ref.value}/"
            process_result = self.process.get_result(
                access,
                ToolCallRef(
                    request.project_ref,
                    result.process_call_ref.removeprefix(call_prefix),
                ),
            )
            self._verify_process_claim(
                attempt,
                f"three-d-blender-{request.request_sha256[:36]}",
                process_result,
            )
            driver_ref, _ = self._staged_driver_evidence(
                access,
                attempt,
                request.identity,
                request.control_root_ref,
                request.working_directory,
            )
            staged_request_ref = self._staged_request_evidence(
                access,
                attempt,
                request,
            )
            (
                expected_process_request,
                workspace_path,
                driver_path,
                _,
            ) = self._operation_process_request(
                access,
                request,
                driver_ref,
                staged_request_ref,
                require_files=False,
            )
            process_request = json.loads(
                self.object_store.read(process_result.request_ref)
            )
            if (
                process_result.artifact_ref != result.process_artifact_ref
                or process_result.tool_call_ref.value != result.process_call_ref
                or process_request != expected_process_request.payload()
                or (
                    result.reality is ThreeDReality.REAL
                    and process_result.process_identity is None
                )
                or (
                    process_result.process_identity is None
                    and process_result.failure
                    not in {
                        ProcessFailure.EXECUTABLE_NOT_FOUND,
                        ProcessFailure.POLICY_DENIED,
                        ProcessFailure.SPAWN_FAILED,
                        ProcessFailure.RECOVERY_UNCERTAIN,
                    }
                )
                or (
                    process_result.process_identity is not None
                    and process_result.process_identity.executable_sha256
                    != request.identity.process_executable_sha256
                )
            ):
                raise ThreeDIntegrityError(
                    "persisted 3D process ToolCall identity changed"
                )
            stdout = self.object_store.read(process_result.stdout_ref)
            try:
                process_report = self._driver_report(stdout)
            except ThreeDIntegrityError:
                process_report = self._fallback_driver_report(
                    request,
                    process_result,
                )
            report_bytes = _json(process_report).encode()
            if (
                hashlib.sha256(report_bytes).hexdigest()
                != result.report_ref.digest
                or len(report_bytes) != result.report_ref.size_bytes
            ):
                raise ThreeDIntegrityError(
                    "persisted 3D report differs from its process stdout"
                )
            driver_accepted = (
                process_result.process_identity is not None
                and self._accepted_driver_evidence(
                    access,
                    request,
                    process_report,
                    driver_path,
                    driver_ref,
                )
            )
            if (
                result.reality is ThreeDReality.REAL
            ) != driver_accepted:
                raise ThreeDIntegrityError(
                    "persisted 3D reality lacks exact Blender driver evidence"
                )
            if attempted_not_run:
                if (
                    result.status is not ThreeDStatus.NOT_RUN
                    or result.output_artifact_ref is not None
                    or result.output_content_ref is not None
                    or result.output_role is not None
                    or result.output_path is not None
                    or result.editable_source
                    or result.preview_only
                    or result.technical_valid is not None
                    or result.failure_reason
                    != self._process_failure_reason(
                        request,
                        process_result,
                        process_report,
                    )
                    or process_claim is None
                    or publication_evidence is not None
                ):
                    raise ThreeDIntegrityError(
                        "persisted attempted NOT_RUN 3D outcome changed"
                    )
                return
            driver_reported_error = isinstance(process_report.get("error"), str)
            process_succeeded = (
                driver_accepted
                and process_result.status is ProcessStatus.SUCCEEDED
                and not driver_reported_error
            )
            if process_succeeded:
                self._verify_operation_report_schema(request, process_report)
                runtime = process_report.get("runtime")
                if (
                    not isinstance(runtime, dict)
                    or runtime.get("tool_name") != "Blender"
                    or runtime.get("tool_version") != request.identity.tool_version
                    or runtime.get("binary_path")
                    != request.identity.executable_path
                    or runtime.get("binary_sha256")
                    != request.identity.executable_sha256
                    or runtime.get("driver_path") != str(driver_path)
                    or runtime.get("driver_sha256")
                    != request.identity.driver_sha256
                    or runtime.get("driver_size_bytes")
                    != driver_ref.size_bytes
                    or not isinstance(runtime.get("embedded_python"), str)
                    or not runtime.get("embedded_python")
                    or runtime.get("external_plugins")
                    != [item.payload() for item in request.identity.plugins]
                    or runtime.get("factory_startup") is not True
                    or process_report.get("request_sha256")
                    != request.request_sha256
                    or process_report.get("operation") != request.operation.value
                    or process_report.get("source_path") != request.source_path
                    or process_report.get("output_path") != request.output_path
                    or process_report.get("content_trust") != "UNTRUSTED_DATA"
                    or process_report.get("input_content_bindings")
                    != self._input_content_bindings(access, request)
                    or process_report.get("used_auxiliary_paths")
                    != list(request.auxiliary_artifact_bindings)
                    or (
                        request.operation is ThreeDOperation.VALIDATE
                        and not isinstance(process_report.get("valid"), bool)
                    )
                ):
                    raise ThreeDIntegrityError(
                        "persisted Blender report identity changed"
                    )

            durable_output_ref = (
                None
                if publication_evidence is None
                else ArtifactRef(
                    request.project_ref,
                    cast(str, publication_evidence["artifact_id"]),
                    cast(int, publication_evidence["artifact_revision"]),
                )
            )
            if (
                process_claim is None
                or durable_output_ref
                not in {None, self._output_artifact_ref(request)}
                or result.output_artifact_ref != durable_output_ref
            ):
                raise ThreeDIntegrityError(
                    "persisted REAL 3D publication presence changed"
                )
            output: Artifact | None = None
            output_observed = False
            if durable_output_ref is not None:
                output = self.artifacts.get_artifact(
                    access,
                    durable_output_ref,
                )
                observed_locator = (
                    f"workspace://{request.candidate_snapshot_ref.workspace_ref.workspace_id}/"
                    f"{request.working_directory}/{request.output_path}"
                )
                fallback_locator = (
                    f"adapter-report://3d/{request.request_sha256}"
                )
                if (
                    len(output.source_refs) != 1
                    or output.source_refs[0].source_kind != "file.content"
                    or output.source_refs[0].locator
                    not in {observed_locator, fallback_locator}
                    or _content_payload(output.source_refs[0].content_ref)
                    != _content_payload(output.content_ref)
                ):
                    raise ThreeDIntegrityError(
                        "persisted REAL 3D output location changed"
                    )
                output_observed = (
                    output.source_refs[0].locator == observed_locator
                )
                expected_media_type = (
                    request.output_media_type
                    if output_observed
                    else "application/vnd.biella.3d-report+json"
                )
                required_sources = {
                    *result.source_artifact_refs,
                    result.process_artifact_ref,
                }
                expected_metadata = {
                    "media_type": expected_media_type,
                    "schema_ref": (
                        f"schema://biella/{request.output_role.replace('.', '-')}/1"
                    ),
                    "schema_version": "1.0.0",
                    "semantic_label": (
                        f"{request.operation.value}-{result.status.value.lower()}"
                    ),
                    "semantic_version": "1.0.0",
                }
                if (
                    output.role != request.output_role
                    or output.content_ref is None
                    or output.content_ref.media_type != expected_media_type
                    or _content_payload(output.content_ref)
                    != _content_payload(result.output_content_ref)
                    or not required_sources <= set(output.source_artifact_refs)
                    or result.report_ref not in output.source_content_refs
                    or output.derivation_type
                    != f"3d.{request.operation.value.replace('_', '-')}"
                    or dict(output.metadata) != expected_metadata
                    or output.producer_run_ref != attempt.run_ref
                    or output.producer_attempt_id != attempt.run_attempt_id
                    or output.producer_fence != attempt.run_fence
                ):
                    raise ThreeDIntegrityError(
                        "persisted REAL 3D output provenance changed"
                    )
                self._verify_output_publication(attempt, request, output)

            expected_technical: bool | None = None
            if request.operation is ThreeDOperation.VALIDATE:
                expected_technical = (
                    process_report.get("valid") is True and process_succeeded
                )
            expected_status = (
                ThreeDStatus.SUCCEEDED
                if process_succeeded
                and (
                    request.operation is not ThreeDOperation.VALIDATE
                    or expected_technical
                )
                else ThreeDStatus.FAILED
            )
            expected_failure: str | None = None
            if expected_status is ThreeDStatus.FAILED:
                expected_failure = self._process_failure_reason(
                    request,
                    process_result,
                    process_report,
                )
            if expected_status is ThreeDStatus.SUCCEEDED and not output_observed:
                expected_status = ThreeDStatus.FAILED
                expected_failure = (
                    "Blender exited without the exact requested output"
                )
            expected_publication = (
                expected_status is ThreeDStatus.SUCCEEDED
                or request.operation is ThreeDOperation.VALIDATE
            )
            expected_editable = self._editable_classification(
                request,
                process_report,
                expected_status,
            )
            if (
                (result.output_artifact_ref is not None) != expected_publication
                or (result.output_content_ref is not None) != expected_publication
                or result.output_role
                != (request.output_role if expected_publication else None)
                or result.output_path
                != (request.output_path if expected_publication else None)
                or result.status is not expected_status
                or result.technical_valid != expected_technical
                or result.failure_reason != expected_failure
                or result.editable_source != expected_editable
            ):
                raise ThreeDIntegrityError(
                    "persisted REAL 3D outcome classification changed"
                )

            output_subject_operation = request.operation in {
                ThreeDOperation.MODEL,
                ThreeDOperation.MESH_EDIT,
                ThreeDOperation.TOPOLOGY,
                ThreeDOperation.UV,
                ThreeDOperation.MATERIAL,
                ThreeDOperation.RIG,
                ThreeDOperation.SKIN,
                ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
                ThreeDOperation.SCENE,
                ThreeDOperation.CONVERT,
                ThreeDOperation.OPTIMIZE,
            }
            if process_succeeded and (
                not output_subject_operation or output_observed
            ):
                expected_subject = (
                    result.output_content_ref
                    if output_subject_operation
                    else self.artifacts.get_artifact(
                        access,
                        request.source_artifact_refs[0],
                    ).content_ref
                )
                subject_identity = process_report.get("inspection_subject")
                if (
                    expected_subject is None
                    or not isinstance(subject_identity, dict)
                    or subject_identity.get("sha256")
                    != expected_subject.digest
                    or subject_identity.get("size_bytes")
                    != expected_subject.size_bytes
                ):
                    raise ThreeDIntegrityError(
                        "persisted Blender inspection subject changed"
                    )
                if request.operation in {
                    ThreeDOperation.INSPECT,
                    ThreeDOperation.VALIDATE,
                }:
                    if output_observed and (
                        result.output_content_ref is None
                        or result.output_content_ref.digest
                        != result.report_ref.digest
                        or result.output_content_ref.size_bytes
                        != result.report_ref.size_bytes
                    ):
                        raise ThreeDIntegrityError(
                            "persisted Blender report output changed"
                        )
                else:
                    output_identity = process_report.get("output")
                    if (
                        result.output_content_ref is None
                        or not isinstance(output_identity, dict)
                        or output_identity.get("sha256")
                        != result.output_content_ref.digest
                        or output_identity.get("size_bytes")
                        != result.output_content_ref.size_bytes
                    ):
                        raise ThreeDIntegrityError(
                            "persisted Blender output identity changed"
                        )
        except (
            ArtifactError,
            ObjectStorageError,
            ProcessError,
            OSError,
            ValueError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise ThreeDIntegrityError(
                "persisted 3D result evidence failed verification"
            ) from exc

    def _verify_output_publication(
        self,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        artifact: Artifact,
    ) -> None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM three_d_output_publications "
                "WHERE project_id=? AND adapter_ref=? AND artifact_id=? "
                "AND artifact_revision=?",
                (
                    request.project_ref.value,
                    self.adapter_ref,
                    artifact.artifact_ref.artifact_id,
                    artifact.artifact_ref.revision,
                ),
            ).fetchone()
        finally:
            connection.close()
        payload = {
            "adapter_ref": self.adapter_ref,
            "artifact_record_sha256": artifact.record_sha256,
            "artifact_ref": artifact.artifact_ref.value,
            "node_attempt_id": attempt.attempt_id,
            "node_fence": attempt.fence,
            "operation": request.operation.value,
            "project_ref": request.project_ref.value,
            "request_sha256": request.request_sha256,
        }
        if (
            row is None
            or row["request_sha256"] != request.request_sha256
            or row["operation"] != request.operation.value
            or row["node_attempt_id"] != attempt.attempt_id
            or row["node_fence"] != attempt.fence
            or row["artifact_record_sha256"] != artifact.record_sha256
            or not hmac.compare_digest(
                cast(str, row["publication_sha256"]),
                _digest(payload),
            )
        ):
            raise ThreeDIntegrityError("persisted 3D publication identity changed")

    def _run_attempt(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
    ) -> ExecutionAttempt:
        result = next(
            (
                item
                for item in self.runs.list_attempts(access, attempt.run_ref)
                if item.attempt_id == attempt.run_attempt_id
                and item.fence == attempt.run_fence
            ),
            None,
        )
        if result is None:
            raise ThreeDAuthorityError("exact 3D Run authority is unavailable")
        return result

    def _output_artifact_ref(self, request: ThreeDOperationRequest) -> ArtifactRef:
        identity = _digest(
            {
                "adapter_ref": self.adapter_ref,
                "output_index": 0,
                "project_ref": request.project_ref.value,
                "request_sha256": request.request_sha256,
            }
        )
        return ArtifactRef(request.project_ref, f"art_{identity[:32]}", 1)

    def _insert_publication(
        self,
        connection: sqlite3.Connection,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        run_attempt: ExecutionAttempt,
        publication: _ThreeDPublication,
    ) -> Artifact:
        artifact_ref = self._output_artifact_ref(request)
        sources = tuple(
            sorted(
                {
                    publication.snapshot_artifact_ref,
                    *request.all_source_artifact_refs,
                    *publication.evidence_artifact_refs,
                },
                key=lambda item: item.value,
            )
        )
        self.artifacts._verify_source_artifacts_in_transaction(
            connection,
            request.project_ref,
            sources,
        )
        source_contents: list[ContentRef] = [
            publication.request_ref,
            publication.report_ref,
        ]
        for artifact_ref_value in request.all_source_artifact_refs:
            source = self.artifacts._fetch_artifact(connection, artifact_ref_value)
            if source.content_ref is not None:
                source_contents.append(source.content_ref)
        source_ref = SourceRef.file(
            request.project_ref,
            locator=(
                (
                    f"workspace://{request.candidate_snapshot_ref.workspace_ref.workspace_id}/"
                    f"{request.working_directory}/{request.output_path}"
                )
                if publication.output_observed
                else f"adapter-report://3d/{request.request_sha256}"
            ),
            content_ref=publication.output_content_ref,
        )
        artifact = Artifact(
            artifact_ref=artifact_ref,
            role=request.output_role,
            content_ref=publication.output_content_ref,
            source_refs=(source_ref,),
            source_artifact_refs=sources,
            source_content_refs=tuple(source_contents),
            derivation_type=f"3d.{request.operation.value.replace('_', '-')}",
            producer_run_ref=run_attempt.run_ref,
            producer_attempt_id=run_attempt.attempt_id,
            producer_fence=run_attempt.fence,
            metadata={
                "media_type": (
                    request.output_media_type
                    if publication.output_observed
                    else "application/vnd.biella.3d-report+json"
                ),
                "schema_ref": f"schema://biella/{request.output_role.replace('.', '-')}/1",
                "schema_version": "1.0.0",
                "semantic_label": (
                    f"{request.operation.value}-{publication.status.value.lower()}"
                ),
                "semantic_version": "1.0.0",
            },
            created_at=self.artifacts._database_now(connection),
        )
        existing = connection.execute(
            "SELECT * FROM three_d_output_publications WHERE project_id=? AND adapter_ref=? AND artifact_id=? AND artifact_revision=?",
            (
                request.project_ref.value,
                self.adapter_ref,
                artifact_ref.artifact_id,
                artifact_ref.revision,
            ),
        ).fetchone()
        if existing is None:
            self.artifacts._insert_artifact(connection, artifact)
            self.artifacts._insert_source_bindings(connection, artifact)
            self.artifacts._insert_derivation(connection, artifact)
            self.artifacts._insert_initial_head(connection, artifact)
            payload = {
                "adapter_ref": self.adapter_ref,
                "artifact_record_sha256": artifact.record_sha256,
                "artifact_ref": artifact_ref.value,
                "node_attempt_id": attempt.attempt_id,
                "node_fence": attempt.fence,
                "operation": request.operation.value,
                "project_ref": request.project_ref.value,
                "request_sha256": request.request_sha256,
            }
            connection.execute(
                "INSERT INTO three_d_output_publications VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    request.project_ref.value,
                    self.adapter_ref,
                    artifact_ref.artifact_id,
                    artifact_ref.revision,
                    request.request_sha256,
                    request.operation.value,
                    attempt.attempt_id,
                    attempt.fence,
                    artifact.record_sha256,
                    _digest(payload),
                ),
            )
            return artifact
        persisted = self.artifacts._fetch_artifact(connection, artifact_ref)
        payload = {
            "adapter_ref": self.adapter_ref,
            "artifact_record_sha256": persisted.record_sha256,
            "artifact_ref": artifact_ref.value,
            "node_attempt_id": cast(str, existing["node_attempt_id"]),
            "node_fence": cast(int, existing["node_fence"]),
            "operation": cast(str, existing["operation"]),
            "project_ref": request.project_ref.value,
            "request_sha256": cast(str, existing["request_sha256"]),
        }
        if (
            persisted.artifact_ref != artifact.artifact_ref
            or persisted.semantic_digest != artifact.semantic_digest
            or existing["request_sha256"] != request.request_sha256
            or existing["operation"] != request.operation.value
            or existing["node_attempt_id"] != attempt.attempt_id
            or existing["node_fence"] != attempt.fence
            or existing["artifact_record_sha256"] != persisted.record_sha256
            or not hmac.compare_digest(
                cast(str, existing["publication_sha256"]),
                _digest(payload),
            )
        ):
            raise ThreeDIntegrityError("3D output publication identity changed")
        return persisted

    @staticmethod
    def _driver_report(stdout: bytes) -> dict[str, object]:
        candidates = [
            line[len(_ThreeDService._RESULT_MARKER) :]
            for line in stdout.splitlines()
            if line.startswith(_ThreeDService._RESULT_MARKER)
        ]
        if len(candidates) != 1:
            raise ThreeDIntegrityError(
                "Blender produced other than one bounded structured report"
        )
        try:
            value = _strict_json_loads(candidates[-1])
            serialized = _json(value).encode()
        except (
            TypeError,
            ValueError,
            RecursionError,
            json.JSONDecodeError,
        ) as exc:
            raise ThreeDIntegrityError("Blender structured report is malformed") from exc
        if (
            not isinstance(value, dict)
            or type(value.get("schema_version")) is not int
            or value.get("schema_version") != 1
        ):
            raise ThreeDIntegrityError("Blender structured report schema changed")
        if len(serialized) > 4 * 1024 * 1024:
            raise ThreeDIntegrityError("Blender structured report is unbounded")
        return cast(dict[str, object], value)

    @staticmethod
    def _fallback_driver_report(
        request: ThreeDOperationRequest,
        process: ProcessResult,
    ) -> dict[str, object]:
        return {
            "error": "Blender produced no accepted structured report",
            "exit_code": process.exit_code,
            "identity_digest": request.identity.semantic_digest,
            "operation": request.operation.value,
            "output_path": request.output_path,
            "process_failure": (
                None if process.failure is None else process.failure.value
            ),
            "process_status": process.status.value,
            "request_sha256": request.request_sha256,
            "schema_version": 1,
            "signal_number": process.signal_number,
            "tool_call_ref": process.tool_call_ref.value,
            "valid": False,
        }

    def _accepted_driver_evidence(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        report: Mapping[str, object],
        driver_path: Path,
        driver_ref: ContentRef,
    ) -> bool:
        runtime = report.get("runtime")
        return (
            report.get("driver_evidence") == self._DRIVER_EVIDENCE
            and report.get("request_sha256") == request.request_sha256
            and report.get("operation") == request.operation.value
            and report.get("source_path") == request.source_path
            and report.get("output_path") == request.output_path
            and report.get("content_trust") == "UNTRUSTED_DATA"
            and report.get("input_content_bindings")
            == self._input_content_bindings(access, request)
            and report.get("declared_auxiliary_paths")
            == list(request.auxiliary_artifact_bindings)
            and isinstance(runtime, dict)
            and request.identity.tool_name == "Blender"
            and runtime.get("tool_name") == "Blender"
            and runtime.get("tool_version") == request.identity.tool_version
            and runtime.get("binary_path") == request.identity.executable_path
            and runtime.get("binary_sha256")
            == request.identity.executable_sha256
            and runtime.get("driver_path") == str(driver_path)
            and runtime.get("driver_sha256") == request.identity.driver_sha256
            and runtime.get("driver_size_bytes") == driver_ref.size_bytes
            and isinstance(runtime.get("embedded_python"), str)
            and bool(runtime.get("embedded_python"))
            and runtime.get("external_plugins")
            == [item.payload() for item in request.identity.plugins]
            and runtime.get("factory_startup") is True
        )

    @staticmethod
    def _process_failure_reason(
        request: ThreeDOperationRequest,
        process: ProcessResult,
        report: Mapping[str, object],
    ) -> str:
        if process.failure is not None:
            details = [f"managed Blender process {process.failure.value}"]
            if process.exit_code is not None:
                details.append(f"exit_code={process.exit_code}")
            if process.signal_number is not None:
                details.append(f"signal={process.signal_number}")
            return _reason("; ".join(details))
        reported = report.get("error")
        if isinstance(reported, str):
            return _reason(reported)
        if (
            request.operation is ThreeDOperation.VALIDATE
            and report.get("valid") is not True
        ):
            return "Blender technical validation rejected the exact output"
        return "Blender operation failed without an exact tool reason"

    @staticmethod
    def _native_reopen_proven(
        request: ThreeDOperationRequest,
        report: Mapping[str, object],
    ) -> bool:
        if request.operation not in {
            ThreeDOperation.MODEL,
            ThreeDOperation.MESH_EDIT,
            ThreeDOperation.TOPOLOGY,
            ThreeDOperation.UV,
            ThreeDOperation.MATERIAL,
            ThreeDOperation.RIG,
            ThreeDOperation.SKIN,
            ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
            ThreeDOperation.SCENE,
            ThreeDOperation.OPTIMIZE,
        }:
            return False
        inspection = report.get("inspection")
        return (
            request.output_path.endswith(".blend")
            and isinstance(inspection, dict)
            and inspection.get("bounded") is True
            and type(inspection.get("schema_version")) is int
            and inspection.get("schema_version") == 1
            and inspection.get("source_format") == "BLEND"
        )

    @classmethod
    def _editable_classification(
        cls,
        request: ThreeDOperationRequest,
        report: Mapping[str, object],
        status: ThreeDStatus,
    ) -> bool:
        return (
            status is ThreeDStatus.SUCCEEDED
            and cls._native_reopen_proven(request, report)
        )

    @classmethod
    def _verify_operation_report_schema(
        cls,
        request: ThreeDOperationRequest,
        report: Mapping[str, object],
    ) -> None:
        inspection = report.get("inspection")
        if (
            not isinstance(inspection, dict)
            or inspection.get("bounded") is not True
            or type(inspection.get("schema_version")) is not int
            or inspection.get("schema_version") != 1
            or not isinstance(inspection.get("source_format"), str)
        ):
            raise ThreeDIntegrityError(
                "Blender report lacks a bounded reopen inspection"
            )
        if request.operation in {
            ThreeDOperation.MODEL,
            ThreeDOperation.MESH_EDIT,
            ThreeDOperation.TOPOLOGY,
            ThreeDOperation.UV,
            ThreeDOperation.MATERIAL,
            ThreeDOperation.RIG,
            ThreeDOperation.SKIN,
            ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
            ThreeDOperation.SCENE,
            ThreeDOperation.OPTIMIZE,
        } and not cls._native_reopen_proven(request, report):
            raise ThreeDIntegrityError(
                "editable Blender output lacks native reopen proof"
            )
        if request.operation in {
            ThreeDOperation.RIG,
            ThreeDOperation.SKIN,
            ThreeDOperation.DEFORM,
        }:
            character_identity = report.get("character_identity")
            character_inspection = inspection.get("skin")
            deformation = inspection.get("deformation")
            if (
                request.skeleton_spec is None
                or not isinstance(character_identity, dict)
                or character_identity.get("skeleton_sha256")
                != request.skeleton_spec.semantic_digest
                or not isinstance(character_inspection, dict)
                or not isinstance(deformation, dict)
                or int(inspection.get("skeleton_count", 0)) != 1
                or int(inspection.get("bone_count", 0))
                != len(request.skeleton_spec.bones)
            ):
                raise ThreeDIntegrityError(
                    "character Blender output lacks exact mesh and skeleton evidence"
                )
            if request.operation is ThreeDOperation.RIG and int(
                character_inspection.get("rigged_mesh_count", 0)
            ) < 1:
                raise ThreeDIntegrityError("character rig output lacks an armature modifier")
            if request.operation is ThreeDOperation.SKIN and (
                int(character_inspection.get("skinned_mesh_count", 0)) < 1
                or int(character_inspection.get("vertices_without_weights", 0)) != 0
                or int(character_inspection.get("unknown_weight_groups", 0)) != 0
                or int(character_inspection.get("nonfinite_weights", 0)) != 0
                or int(character_inspection.get("nonnormalized_vertices", 0)) != 0
            ):
                raise ThreeDIntegrityError("character skin output lacks valid weight evidence")
            if request.operation is ThreeDOperation.DEFORM and (
                int(deformation.get("posed_bones", 0)) < 1
                or int(deformation.get("deformed_mesh_count", 0)) < 1
            ):
                raise ThreeDIntegrityError("character deformation output lacks pose evidence")
        if request.operation in {
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
        }:
            animation_identity = report.get("animation_identity")
            animation = inspection.get("animation")
            if (
                request.animation_clip_spec is None
                or request.skeleton_spec is None
                or not isinstance(animation_identity, dict)
                or animation_identity.get("clip_sha256")
                != request.animation_clip_spec.semantic_digest
                or animation_identity.get("source_skeleton_sha256")
                != request.animation_clip_spec.source_skeleton_sha256
                or animation_identity.get("target_skeleton_sha256")
                != request.skeleton_spec.semantic_digest
                or animation_identity.get("root_motion_policy")
                != request.root_motion_policy.value
                or not isinstance(animation, dict)
                or int(animation.get("action_count", 0)) < 1
                or not isinstance(animation.get("actions"), list)
                or not any(
                    isinstance(item, dict)
                    and item.get("clip_sha256") == request.animation_clip_spec.semantic_digest
                    and item.get("fcurve_count", 0) > 0
                    and item.get("keyframe_count", 0) > 0
                    for item in animation["actions"]
                )
            ):
                raise ThreeDIntegrityError("animation output lacks exact Action and keyframe evidence")
            if request.operation is ThreeDOperation.RETARGET and (
                request.retarget_spec is None
                or animation_identity.get("retarget_sha256")
                != request.retarget_spec.semantic_digest
                or int(inspection.get("skeleton_count", 0)) < 2
                or int(inspection.get("bone_count", 0))
                < len(request.retarget_spec.source_skeleton_spec.bones)
                + len(request.skeleton_spec.bones)
            ):
                raise ThreeDIntegrityError("retarget output lacks exact mapping evidence")
            if request.operation is ThreeDOperation.BAKE and not any(
                isinstance(item, dict)
                and item.get("clip_sha256") == request.animation_clip_spec.semantic_digest
                and item.get("baked") is True
                for item in animation["actions"]
            ):
                raise ThreeDIntegrityError("baked animation output lacks exact bake evidence")
        if request.operation is ThreeDOperation.ENVIRONMENT:
            environment_identity = report.get("environment_identity")
            if (
                request.environment_spec is None
                or not isinstance(environment_identity, dict)
                or environment_identity.get("layout_sha256")
                != request.environment_spec.semantic_digest
                or environment_identity.get("seed") != request.environment_spec.seed
            ):
                raise ThreeDIntegrityError("environment output lacks exact layout evidence")
        if request.operation is ThreeDOperation.CONVERT:
            expected_export = PurePosixPath(request.output_path).suffix.lower()
            source_inspection = report.get("source_inspection")
            exporter = next(
                (
                    item
                    for item in request.identity.plugins
                    if item.name == "glTF 2.0 format"
                ),
                None,
            )
            export_yup = bool(
                request.operation_config.get("export_yup", True)
            )
            export_evidence = report.get("export")
            settings = (
                export_evidence.get("settings")
                if isinstance(export_evidence, dict)
                else None
            )
            expected_format = (
                "GLB" if expected_export == ".glb" else "GLTF_EMBEDDED"
            )
            exact_export_evidence = (
                exporter is not None
                and isinstance(source_inspection, dict)
                and isinstance(export_evidence, dict)
                and set(export_evidence)
                == {
                    "axis_conversion",
                    "exporter",
                    "operator",
                    "settings",
                    "settings_count",
                    "settings_schema",
                    "settings_sha256",
                    "source_units",
                    "target_format",
                    "target_meters_per_unit",
                }
                and isinstance(settings, dict)
                and 90 <= len(settings) <= 256
                and all(isinstance(key, str) for key in settings)
                and export_evidence.get("settings_count") == len(settings)
                and export_evidence.get("settings_schema")
                == "BLENDER_RNA_EFFECTIVE_OUTPUT_V1"
                and export_evidence.get("settings_sha256") == _digest(settings)
                and settings.get("export_apply") is True
                and settings.get("export_format") == expected_format
                and settings.get("export_yup") is export_yup
                and settings.get("export_use_gltfpack") is False
                and settings.get("export_draco_mesh_compression_enable") is False
                and not {
                    "check_existing",
                    "export_loglevel",
                    "filepath",
                    "filter_glob",
                    "ui_tab",
                    "will_save_settings",
                }
                & set(settings)
                and export_evidence.get("axis_conversion")
                == (
                    "BLENDER_Z_UP_TO_GLTF_Y_UP"
                    if export_yup
                    else "PRESERVE_BLENDER_Z_UP"
                )
                and export_evidence.get("exporter") == exporter.payload()
                and export_evidence.get("operator") == "EXPORT_SCENE_OT_gltf"
                and export_evidence.get("source_units")
                == {
                    "scale_length": source_inspection.get("unit_scale"),
                    "system": source_inspection.get("unit_system"),
                }
                and export_evidence.get("target_format")
                == expected_export.removeprefix(".").upper()
                and export_evidence.get("target_meters_per_unit") == 1.0
            )
            if (
                inspection.get("source_format") != "GLTF"
                or report.get("export_format")
                != expected_export.removeprefix(".").upper()
                or not exact_export_evidence
            ):
                raise ThreeDIntegrityError(
                    "Blender interchange output lacks exact exporter, settings, conversion, or reopen proof"
                )
        if request.operation is ThreeDOperation.PREVIEW and (
            report.get("preview_engine") != "CYCLES_CPU"
        ):
            raise ThreeDIntegrityError(
                "Blender preview lacks exact render observation"
            )

    def _execute_blender_process(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        process_request: ProcessExecutionRequest,
        driver_path: Path,
        driver_ref: ContentRef,
        *,
        recovering_claim: bool,
        process_state: str,
    ) -> tuple[ProcessResult, dict[str, object], bool]:
        if process_state not in {
            "ABSENT",
            "CLAIMED",
            "PREPARED",
            "STARTED",
            "RESULT",
        }:
            raise ThreeDIntegrityError(
                "managed Blender process state is unsupported"
            )
        durable_process = process_state in {"STARTED", "RESULT"}
        target_descriptor, output_name, target_exists = (
            self._pin_output_target(
                access,
                attempt,
                request,
                allow_existing=durable_process,
            )
        )
        try:
            process_result: ProcessResult | None = None
            if process_state != "ABSENT":
                process_result = self.process.execute(
                    access,
                    attempt,
                    process_request,
                    idempotency_key=(
                        f"three-d-blender-{request.request_sha256[:36]}"
                    ),
                )
                if process_result.status is not ProcessStatus.SUCCEEDED:
                    stdout = self.object_store.read(process_result.stdout_ref)
                    try:
                        report = self._driver_report(stdout)
                    except ThreeDIntegrityError:
                        report = self._fallback_driver_report(
                            request,
                            process_result,
                        )
                    return process_result, report, False
            self._prepare_staging_output(
                access,
                request,
                allow_existing_tree=recovering_claim,
                allow_existing_leaf=process_state != "ABSENT",
            )
            if process_result is None:
                process_result = self.process.execute(
                    access,
                    attempt,
                    process_request,
                    idempotency_key=(
                        f"three-d-blender-{request.request_sha256[:36]}"
                    ),
                )
            self._verify_output_target_claim(access, attempt, request)
            stdout = self.object_store.read(process_result.stdout_ref)
            try:
                report = self._driver_report(stdout)
            except ThreeDIntegrityError:
                report = self._fallback_driver_report(request, process_result)
            driver_accepted = self._accepted_driver_evidence(
                access,
                request,
                report,
                driver_path,
                driver_ref,
            )
            process_succeeded = (
                driver_accepted
                and process_result.status is ProcessStatus.SUCCEEDED
                and not isinstance(report.get("error"), str)
            )
            if process_succeeded:
                if report.get("used_auxiliary_paths") != list(
                    request.auxiliary_artifact_bindings
                ):
                    raise ThreeDIntegrityError(
                        "Blender report auxiliary provenance changed"
                    )
                self._verify_operation_report_schema(request, report)
                if (
                    request.operation is ThreeDOperation.VALIDATE
                    and not isinstance(report.get("valid"), bool)
                ):
                    raise ThreeDIntegrityError(
                        "Blender validation report lacks exact boolean validity"
                    )
                output_ready = self._publish_staged_output(
                    access,
                    request,
                    report,
                    target_descriptor,
                    output_name,
                    target_exists=target_exists,
                )
                self._verify_output_target_claim(access, attempt, request)
            else:
                output_ready = False
            return process_result, report, output_ready
        finally:
            os.close(target_descriptor)

    def _input_content_bindings(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> dict[str, dict[str, object]]:
        return {
            path: cast(dict[str, object], _content_payload(content_ref))
            for path, content_ref in self._input_content_refs(
                access,
                request,
            ).items()
        }

    def _input_content_refs(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> dict[str, ContentRef]:
        bindings: dict[str, ArtifactRef] = dict(
            request.auxiliary_artifact_bindings
        )
        if request.source_path is not None:
            bindings[request.source_path] = request.source_artifact_refs[0]
        result: dict[str, ContentRef] = {}
        for path, artifact_ref in sorted(bindings.items()):
            artifact = self.artifacts.get_artifact(access, artifact_ref)
            if artifact.content_ref is None:
                raise ThreeDIntegrityError(
                    "3D exact input Artifact has no content identity"
                )
            self.object_store.verify(artifact.content_ref)
            result[path] = artifact.content_ref
        return result

    def _request_content(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> ContentRef:
        driver_request = {
            "auxiliary_paths": list(request.auxiliary_artifact_bindings),
            "identity": request.identity.payload(),
            "input_content_bindings": self._input_content_bindings(
                access,
                request,
            ),
            "operation": request.operation.value,
            "operation_config": dict(request.operation_config),
            "output_path": request.output_path,
            "request": request.payload(),
            "request_sha256": request.request_sha256,
            "schema_version": 1,
            "source_path": request.source_path,
            "staging_output_path": self._staging_output_path(request),
            "validation_requirements": request.validation_requirements.payload(),
        }
        return self.object_store.put(
            _json(driver_request).encode(),
            media_type="application/vnd.biella.3d-operation+json",
        )

    @staticmethod
    def _staging_output_path(request: ThreeDOperationRequest) -> str:
        return PurePosixPath(
            f".biella-three-d-stage-{request.request_sha256}",
            request.output_path,
        ).as_posix()

    @staticmethod
    def _staging_root_name(request: ThreeDOperationRequest) -> str:
        return f".biella-three-d-stage-{request.request_sha256}"

    def _open_working_directory(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> int:
        root = self.filesystem.get_root(access, request.control_root_ref)
        try:
            parts = FilesystemAdapter._relative_parts(request.working_directory)
            parent, leaf = FilesystemAdapter._parent_descriptor(root, parts)
            descriptor = parent
            if leaf is not None:
                try:
                    FilesystemAdapter._safe_state(
                        parent,
                        leaf,
                        allow_directory=True,
                    )
                    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                    flags |= getattr(os, "O_NOFOLLOW", 0)
                    descriptor = os.open(leaf, flags, dir_fd=parent)
                finally:
                    os.close(parent)
            try:
                FilesystemAdapter._assert_descriptor_beneath(root, descriptor)
            except Exception:
                os.close(descriptor)
                raise
            return descriptor
        except (FilesystemError, OSError) as exc:
            raise ThreeDScopeError(
                "3D working directory lacks a stable Workspace identity"
            ) from exc

    def _preflight_staging_root(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> None:
        descriptor = self._open_working_directory(access, request)
        try:
            try:
                os.stat(
                    self._staging_root_name(request),
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return
            raise ThreeDConflictError(
                "private 3D staging root already contains unclaimed state"
            )
        finally:
            os.close(descriptor)

    def _open_staging_directory(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
    ) -> tuple[int, str]:
        descriptor = self._open_working_directory(access, request)
        try:
            directory_parts = (
                self._staging_root_name(request),
                *PurePosixPath(request.output_path).parent.parts,
            )
            for part in directory_parts:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                flags |= getattr(os, "O_NOFOLLOW", 0)
                child = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor, PurePosixPath(request.output_path).name
        except OSError as exc:
            os.close(descriptor)
            raise ThreeDScopeError(
                "private 3D staging directory lacks a stable Workspace identity"
            ) from exc

    def _prepare_staging_output(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        *,
        allow_existing_tree: bool,
        allow_existing_leaf: bool,
    ) -> None:
        descriptor = self._open_working_directory(access, request)
        try:
            root_name = self._staging_root_name(request)
            try:
                root_state = os.stat(
                    root_name,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                os.mkdir(root_name, mode=0o700, dir_fd=descriptor)
            else:
                if (
                    not stat.S_ISDIR(root_state.st_mode)
                    or not allow_existing_tree
                ):
                    raise ThreeDConflictError(
                        "private 3D staging root contains unclaimed state"
                    )
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            child = os.open(root_name, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            for part in PurePosixPath(request.output_path).parent.parts:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    if not allow_existing_tree:
                        raise ThreeDConflictError(
                            "private 3D staging tree contains unclaimed state"
                        )
                child = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            leaf = PurePosixPath(request.output_path).name
            try:
                state = os.stat(leaf, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return
            if (
                not stat.S_ISREG(state.st_mode)
                or not allow_existing_leaf
            ):
                raise ThreeDConflictError(
                    "private 3D staging leaf contains unclaimed bytes"
                )
        finally:
            os.close(descriptor)

    @staticmethod
    def _descriptor_identity(descriptor: int) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        return digest.hexdigest(), size

    @staticmethod
    def _expected_output_identity(
        request: ThreeDOperationRequest,
        report: Mapping[str, object],
    ) -> tuple[str, int]:
        if request.operation in {
            ThreeDOperation.INSPECT,
            ThreeDOperation.VALIDATE,
        }:
            payload = _json(report).encode()
            return hashlib.sha256(payload).hexdigest(), len(payload)
        output = report.get("output")
        if (
            not isinstance(output, dict)
            or not isinstance(output.get("sha256"), str)
            or not isinstance(output.get("size_bytes"), int)
            or isinstance(output.get("size_bytes"), bool)
        ):
            raise ThreeDIntegrityError(
                "Blender report lacks exact staged output identity"
            )
        return cast(str, output["sha256"]), cast(int, output["size_bytes"])

    def _publish_staged_output(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        report: Mapping[str, object],
        target_descriptor: int,
        output_name: str,
        *,
        target_exists: bool,
    ) -> bool:
        expected = self._expected_output_identity(request, report)
        staging_descriptor, staging_leaf = self._open_staging_directory(
            access,
            request,
        )
        source: int | None = None
        try:
            flags = os.O_RDONLY | os.O_CLOEXEC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                source = os.open(staging_leaf, flags, dir_fd=staging_descriptor)
            except FileNotFoundError:
                source = None
            if source is not None:
                source_state = os.fstat(source)
                if (
                    not stat.S_ISREG(source_state.st_mode)
                    or self._descriptor_identity(source) != expected
                ):
                    raise ThreeDIntegrityError(
                        "private Blender output differs from its exact report"
                    )
            if target_exists:
                target_flags = os.O_RDONLY | os.O_CLOEXEC
                target_flags |= getattr(os, "O_NOFOLLOW", 0)
                target = os.open(
                    output_name,
                    target_flags,
                    dir_fd=target_descriptor,
                )
                try:
                    if (
                        not stat.S_ISREG(os.fstat(target).st_mode)
                        or self._descriptor_identity(target) != expected
                    ):
                        raise ThreeDIntegrityError(
                            "recovered Blender output differs from its exact report"
                        )
                finally:
                    os.close(target)
                if source is not None:
                    os.unlink(staging_leaf, dir_fd=staging_descriptor)
                return True
            if source is None:
                return False
            try:
                os.link(
                    staging_leaf,
                    output_name,
                    src_dir_fd=staging_descriptor,
                    dst_dir_fd=target_descriptor,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise ThreeDConflictError(
                    "3D output leaf was occupied before atomic publication"
                ) from exc
            published = os.open(
                output_name,
                flags,
                dir_fd=target_descriptor,
            )
            try:
                if (
                    os.fstat(published).st_ino != os.fstat(source).st_ino
                    or self._descriptor_identity(published) != expected
                ):
                    raise ThreeDIntegrityError(
                        "atomic Blender output publication identity changed"
                    )
            finally:
                os.close(published)
            os.fsync(target_descriptor)
            os.unlink(staging_leaf, dir_fd=staging_descriptor)
            return True
        finally:
            if source is not None:
                os.close(source)
            os.close(staging_descriptor)

    def _staged_request_evidence(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
    ) -> ContentRef:
        expected_ref = self._request_content(access, request)
        relative = (
            f"{request.working_directory}/.biella-three-d-"
            f"{request.request_sha256[:32]}.json"
        )
        idempotency_key = f"three-d-request-{request.request_sha256[:36]}"
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT call_id FROM filesystem_operation_claims "
                "WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?",
                (
                    request.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ThreeDIntegrityError(
                "staged Blender request lost immutable filesystem evidence"
            )
        try:
            operation = self.filesystem.get_operation(
                access,
                ToolCallRef(request.project_ref, cast(str, row["call_id"])),
            )
            self.object_store.verify(operation.output_ref)
        except (FilesystemError, ObjectStorageError) as exc:
            raise ThreeDIntegrityError(
                "staged Blender request evidence failed verification"
            ) from exc
        expected_payload = {
            "content_ref": expected_ref.value,
            "mode": 0o600,
            "operation": "write",
            "path": relative,
            "root_ref": request.control_root_ref.value,
            "schema_version": 2,
        }
        if (
            operation.operation != "write"
            or dict(operation.payload) != expected_payload
            or operation.output_ref != expected_ref
        ):
            raise ThreeDIntegrityError(
                "staged Blender request content identity changed"
            )
        return operation.output_ref

    def _operation_process_request(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        driver_ref: ContentRef,
        request_ref: ContentRef,
        *,
        require_files: bool = True,
    ) -> tuple[ProcessExecutionRequest, Path, Path, Path]:
        root = self.filesystem.get_root(access, request.control_root_ref)
        workspace_path = Path(
            root.canonical_path,
            request.working_directory,
        )
        if require_files:
            workspace_path = workspace_path.resolve(strict=True)
        driver_path = Path(
            workspace_path,
            f".biella-three-d-driver-{request.identity.driver_sha256[:32]}.py",
        )
        request_path = Path(
            workspace_path,
            f".biella-three-d-{request.request_sha256[:32]}.json",
        )
        if require_files:
            driver_path = driver_path.resolve(strict=True)
            request_path = request_path.resolve(strict=True)
        blender_argv = (
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python",
            str(driver_path),
            "--",
            "--workspace-root",
            str(workspace_path),
            "--request",
            str(request_path),
        )
        descriptor_refs = {
            "driver": driver_ref,
            "request": request_ref,
        }
        descriptor_targets = {
            "driver": driver_path,
            "request": request_path,
        }
        for index, (relative, content_ref) in enumerate(
            self._input_content_refs(access, request).items()
        ):
            key = f"input-{index}"
            descriptor_refs[key] = content_ref
            descriptor_targets[key] = Path(workspace_path, relative)
        process_request = ProcessExecutionRequest(
            project_ref=request.project_ref,
            working_root_ref=request.control_root_ref,
            working_directory=request.working_directory,
            executable=request.identity.process_executable_path,
            expected_executable_sha256=(
                request.identity.process_executable_sha256
            ),
            argv=self._sandbox_argv(
                request.identity,
                workspace_path,
                blender_argv,
                descriptor_targets,
                {
                    "staging": Path(
                        workspace_path,
                        self._staging_root_name(request),
                    )
                },
                (Path(workspace_path, request.output_path).parent,),
            ),
            descriptor_content_refs=descriptor_refs,
            descriptor_directory_paths={
                "staging": self._staging_root_name(request)
            },
            timeout_seconds=300.0,
            termination_grace_seconds=5.0,
            stdout_limit_bytes=8 * 1024 * 1024,
            stderr_limit_bytes=8 * 1024 * 1024,
            network_policy=NetworkPolicy.INHERIT,
            resource_policy=ProcessResourcePolicy(
                cpu_seconds=300,
                memory_bytes=8 * 1024 * 1024 * 1024,
                file_size_bytes=512 * 1024 * 1024,
                process_count=64,
            ),
            resource_allocation_ref=request.resource_allocation_ref,
            shell=False,
        )
        return process_request, workspace_path, driver_path, request_path

    @classmethod
    def _sandbox_argv(
        cls,
        identity: ThreeDToolIdentity,
        workspace_path: Path,
        blender_argv: tuple[str, ...],
        descriptor_targets: Mapping[str, Path],
        writable_directory_targets: Mapping[str, Path],
        virtual_directories: tuple[Path, ...],
    ) -> tuple[str, ...]:
        if (
            identity.sandbox_launcher_path is None
            or identity.sandbox_launcher_sha256 is None
            or PurePosixPath(identity.sandbox_launcher_path).name != "bwrap"
        ):
            raise ThreeDContractError(
                "REAL Blender execution requires exact bubblewrap identity"
            )
        workspace = PurePosixPath(str(workspace_path))
        if not workspace.is_absolute() or workspace == PurePosixPath("/"):
            raise ThreeDContractError(
                "Blender sandbox Workspace path must be exact and absolute"
            )
        reserved = tuple(
            PurePosixPath(item)
            for item in ("/usr", "/etc", "/proc", "/dev", "/lib", "/lib64")
        )
        if any(workspace == item or workspace.is_relative_to(item) for item in reserved):
            raise ThreeDContractError(
                "Blender sandbox Workspace overlaps its read-only runtime"
            )
        descriptor_paths = tuple(
            PurePosixPath(str(target)) for target in descriptor_targets.values()
        )
        writable_paths = tuple(
            PurePosixPath(str(target))
            for target in writable_directory_targets.values()
        )
        if (
            len(set(descriptor_paths)) != len(descriptor_paths)
            or len(set(writable_paths)) != len(writable_paths)
            or any(path == workspace for path in (*descriptor_paths, *writable_paths))
            or any(
                left.is_relative_to(right) or right.is_relative_to(left)
                for index, left in enumerate(descriptor_paths)
                for right in descriptor_paths[index + 1 :]
            )
            or any(
                left.is_relative_to(right) or right.is_relative_to(left)
                for index, left in enumerate(writable_paths)
                for right in writable_paths[index + 1 :]
            )
            or any(
                descriptor.is_relative_to(writable)
                or writable.is_relative_to(descriptor)
                for descriptor in descriptor_paths
                for writable in writable_paths
            )
        ):
            raise ThreeDContractError(
                "Blender sandbox descriptor targets overlap"
            )
        arguments: list[str] = [
            "--unshare-all",
            "--unshare-user",
            "--disable-userns",
            "--assert-userns-disabled",
            "--die-with-parent",
            "--new-session",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/home",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "XDG_CONFIG_HOME",
            "/tmp/config",
            "--setenv",
            "XDG_CACHE_HOME",
            "/tmp/cache",
            "--setenv",
            "XDG_DATA_HOME",
            "/tmp/data",
            "--setenv",
            "PATH",
            "/usr/bin",
            "--setenv",
            "LD_LIBRARY_PATH",
            "/usr/lib/x86_64-linux-gnu/lapack:/usr/lib/x86_64-linux-gnu/blas",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/lib64",
            "/lib64",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/etc",
            "--symlink",
            "/proc/mounts",
            "/etc/mtab",
            "--dir",
            "/tmp/home",
            "--dir",
            "/tmp/config",
            "--dir",
            "/tmp/cache",
            "--dir",
            "/tmp/data",
        ]
        existing = {
            PurePosixPath("/"),
            PurePosixPath("/tmp"),
            *reserved,
        }
        for parent in reversed(workspace.parents):
            if parent not in existing:
                arguments.extend(("--dir", parent.as_posix()))
        arguments.extend(("--tmpfs", workspace.as_posix()))
        required_directories: set[PurePosixPath] = set()
        for target in (
            *descriptor_targets.values(),
            *writable_directory_targets.values(),
            *virtual_directories,
        ):
            target_path = PurePosixPath(str(target))
            if not target_path.is_relative_to(workspace):
                raise ThreeDContractError(
                    "Blender sandbox descriptor target crossed Workspace scope"
                )
            required_directories.update(
                parent
                for parent in target_path.parents
                if parent != workspace and parent.is_relative_to(workspace)
            )
        required_directories.update(
            PurePosixPath(str(directory))
            for directory in virtual_directories
            if PurePosixPath(str(directory)) != workspace
        )
        required_directories.update(
            PurePosixPath(str(directory))
            for directory in writable_directory_targets.values()
        )
        for directory in sorted(
            required_directories,
            key=lambda item: (len(item.parts), item.as_posix()),
        ):
            arguments.extend(("--dir", directory.as_posix()))
        for key, target in sorted(descriptor_targets.items()):
            target_path = PurePosixPath(str(target))
            arguments.extend(
                (
                    "--perms",
                    "0400",
                    "--ro-bind-data",
                    f"@biella-content-fd:{key}",
                    target_path.as_posix(),
                )
            )
        arguments.extend(("--remount-ro", workspace.as_posix()))
        for key, target in sorted(writable_directory_targets.items()):
            target_path = PurePosixPath(str(target))
            arguments.extend(
                (
                    "--bind-fd",
                    f"@biella-directory-fd:{key}",
                    target_path.as_posix(),
                )
            )
        arguments.extend(
            (
                "--chdir",
                workspace.as_posix(),
                identity.executable_path,
                *blender_argv,
            )
        )
        return tuple(arguments)

    def _verify_process_claim(
        self,
        attempt: NodeExecutionAttempt,
        idempotency_key: str,
        process: ProcessResult,
    ) -> None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM managed_process_claims WHERE project_id=? "
                "AND node_attempt_id=? AND idempotency_key=?",
                (
                    attempt.node_ref.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                ),
            ).fetchone()
        finally:
            connection.close()
        claim = {
            "call_ref": process.tool_call_ref.value,
            "idempotency_key": idempotency_key,
            "node_attempt_id": attempt.attempt_id,
            "project_ref": attempt.node_ref.project_ref.value,
            "request_ref": process.request_ref.value,
        }
        if (
            row is None
            or row["call_id"] != process.tool_call_ref.call_id
            or row["request_digest"] != process.request_ref.digest
            or row["request_size"] != process.request_ref.size_bytes
            or row["request_media_type"] != process.request_ref.media_type
            or not hmac.compare_digest(
                cast(str, row["claim_sha256"]),
                _digest(claim),
            )
        ):
            raise ThreeDIntegrityError(
                "managed Blender process claim identity changed"
            )

    def _stage_driver(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
    ) -> tuple[Path, ContentRef, ArtifactRef]:
        driver_bytes = self._DRIVER.read_bytes()
        driver_ref = self.object_store.put(
            driver_bytes,
            media_type="text/x-python",
        )
        if not hmac.compare_digest(driver_ref.digest, identity.driver_sha256):
            raise ThreeDIntegrityError("fixed Blender driver content changed")
        relative, staging_identity = self._driver_staging_identity(
            identity,
            control_root_ref,
            working_directory,
        )
        written = self.filesystem.write(
            access,
            attempt,
            root_ref=control_root_ref,
            path=relative,
            content_ref=driver_ref,
            idempotency_key=f"three-d-driver-{staging_identity[:36]}",
            mode=0o400,
        )
        if written.output_ref != driver_ref:
            raise ThreeDIntegrityError("staged Blender driver content changed")
        driver_path = self._restore_staged_control_file(
            access,
            control_root_ref,
            relative,
            driver_ref,
            mode=0o400,
        )
        return driver_path, driver_ref, written.artifact_ref

    def _restore_staged_control_file(
        self,
        access: ProjectAccess,
        root_ref: FilesystemRootRef,
        relative_path: str,
        content_ref: ContentRef,
        *,
        mode: int,
    ) -> Path:
        """Materialize rebuildable private control bytes from exact evidence."""

        try:
            root = self.filesystem._require_root(
                access,
                root_ref,
                writable=True,
            )
            restored = self.filesystem._atomic_write(
                root,
                relative_path,
                content_ref,
                mode=mode,
                cancelled=None,
            )
            path = Path(root.canonical_path, relative_path).resolve(strict=True)
        except (FilesystemError, OSError) as exc:
            raise ThreeDIntegrityError(
                "private Blender control file could not be restored from exact evidence"
            ) from exc
        if restored != content_ref or not path.is_file():
            raise ThreeDIntegrityError(
                "private Blender control file restoration changed identity"
            )
        return path

    @staticmethod
    def _driver_staging_identity(
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
    ) -> tuple[str, str]:
        relative = (
            f"{working_directory}/.biella-three-d-driver-"
            f"{identity.driver_sha256[:32]}.py"
        )
        return relative, _digest(
            {
                "control_root_ref": control_root_ref.value,
                "driver_sha256": identity.driver_sha256,
                "working_directory": working_directory,
            }
        )

    def _staged_driver_evidence(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
    ) -> tuple[ContentRef, ArtifactRef]:
        relative, staging_identity = self._driver_staging_identity(
            identity,
            control_root_ref,
            working_directory,
        )
        idempotency_key = f"three-d-driver-{staging_identity[:36]}"
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT call_id FROM filesystem_operation_claims "
                "WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?",
                (
                    identity.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ThreeDIntegrityError(
                "staged Blender driver lost immutable filesystem evidence"
            )
        try:
            operation = self.filesystem.get_operation(
                access,
                ToolCallRef(identity.project_ref, cast(str, row["call_id"])),
            )
            self.object_store.verify(operation.output_ref)
        except (FilesystemError, ObjectStorageError) as exc:
            raise ThreeDIntegrityError(
                "staged Blender driver evidence failed verification"
            ) from exc
        expected_payload = {
            "content_ref": operation.output_ref.value,
            "mode": 0o400,
            "operation": "write",
            "path": relative,
            "root_ref": control_root_ref.value,
            "schema_version": 2,
        }
        if (
            operation.operation != "write"
            or dict(operation.payload) != expected_payload
            or operation.output_ref.algorithm != "sha256"
            or operation.output_ref.digest != identity.driver_sha256
            or operation.output_ref.media_type != "text/x-python"
            or operation.output_ref.size_bytes <= 0
        ):
            raise ThreeDIntegrityError(
                "staged Blender driver content identity changed"
            )
        return operation.output_ref, operation.artifact_ref

    def _unavailable_result(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        idempotency_key: str,
        reason: str,
    ) -> ThreeDOperationResult:
        report_ref = self.object_store.put(
            _json(self._unavailability_report(request, reason)).encode(),
            media_type="application/vnd.biella.3d-unavailability+json",
        )
        result = ThreeDOperationResult(
            project_ref=request.project_ref,
            operation=request.operation,
            request_sha256=request.request_sha256,
            identity_digest=request.identity.semantic_digest,
            adapter_ref=self.adapter_ref,
            reality=ThreeDReality.NOT_RUN,
            status=ThreeDStatus.NOT_RUN,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            source_artifact_refs=request.all_source_artifact_refs,
            output_artifact_ref=None,
            output_content_ref=None,
            report_ref=report_ref,
            process_artifact_ref=None,
            process_call_ref=None,
            output_role=None,
            output_path=None,
            editable_source=False,
            preview_only=False,
            technical_valid=None,
            failure_reason=reason,
            observed_at=self._now(),
        )
        return self._persist(access, attempt, request, result, idempotency_key)

    def _unavailability_report(
        self,
        request: ThreeDOperationRequest,
        reason: str,
    ) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "available": False,
            "executable_path": request.identity.executable_path,
            "executable_sha256": request.identity.executable_sha256,
            "identity_digest": request.identity.semantic_digest,
            "operation": request.operation.value,
            "output_path": request.output_path,
            "project_ref": request.project_ref.value,
            "reality": ThreeDReality.NOT_RUN.value,
            "reason": reason,
            "request_sha256": request.request_sha256,
            "schema_version": 1,
        }

    def _reference_validation_result(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        artifact: Artifact,
    ) -> bool:
        if artifact.content_ref is None or not request.source_artifact_refs:
            raise ThreeDIntegrityError(
                "reference validation lacks exact report or subject"
            )
        subject = self.artifacts.get_artifact(
            access,
            request.source_artifact_refs[0],
        )
        if subject.content_ref is None:
            raise ThreeDIntegrityError(
                "reference validation subject lacks exact content"
        )
        try:
            report = _strict_json_loads(
                self.object_store.read(artifact.content_ref)
            )
        except (
            ObjectStorageError,
            ValueError,
            RecursionError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise ThreeDIntegrityError(
                "reference validation report is malformed"
            ) from exc
        if (
            not isinstance(report, dict)
            or type(report.get("schema_version")) is not int
            or report.get("schema_version") != 1
            or not isinstance(report.get("valid"), bool)
        ):
            raise ThreeDIntegrityError(
                "reference validation lacks explicit validity"
            )
        expected = {
            "operation": ThreeDOperation.VALIDATE.value,
            "schema_version": 1,
            "source_artifact_refs": [
                item.value for item in request.all_source_artifact_refs
            ],
            "subject_content_ref": _content_payload(subject.content_ref),
            "valid": report["valid"],
            "validation_requirements": (
                request.validation_requirements.payload()
            ),
        }
        if report != expected:
            raise ThreeDIntegrityError(
                "reference validation report differs from exact request"
            )
        return cast(bool, report["valid"])

    def reference(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        *,
        idempotency_key: str,
    ) -> ThreeDOperationResult:
        reference_ref = request.reference_output_artifact_ref
        if reference_ref is None:
            raise ThreeDContractError(
                "reference 3D operation requires exact evidence Artifact"
            )
        snapshot_artifact_ref = self._authorize_request(
            access,
            attempt,
            request,
            verify_source=False,
        )
        artifact = self.artifacts.get_artifact(access, reference_ref)
        if (
            artifact.role != request.output_role
            or artifact.content_ref is None
            or artifact.content_ref.media_type != request.output_media_type
        ):
            raise ThreeDIntegrityError("reference 3D evidence role or content changed")
        required_sources = {snapshot_artifact_ref, *request.all_source_artifact_refs}
        if not required_sources <= set(artifact.source_artifact_refs):
            raise ThreeDIntegrityError("reference 3D evidence lacks exact source provenance")
        try:
            self.object_store.verify(artifact.content_ref)
        except ObjectStorageError as exc:
            raise ThreeDIntegrityError(
                "reference 3D evidence failed verification"
            ) from exc
        claimed, terminal = self._claim_state(
            access,
            attempt,
            request,
            idempotency_key,
            require_output_absent=True,
        )
        if terminal is not None:
            return terminal
        if not claimed:
            self._preflight_output_target(access, request)
        technical_valid: bool | None = None
        status = ThreeDStatus.SUCCEEDED
        failure_reason: str | None = None
        if request.operation is ThreeDOperation.VALIDATE:
            technical_valid = self._reference_validation_result(
                access,
                request,
                artifact,
            )
            if not technical_valid:
                status = ThreeDStatus.FAILED
                failure_reason = "reference technical validation failed"
        prior = self._claim(
            access,
            attempt,
            request,
            idempotency_key,
            require_output_absent=True,
        )
        if prior is not None:
            return prior
        result = ThreeDOperationResult(
            project_ref=request.project_ref,
            operation=request.operation,
            request_sha256=request.request_sha256,
            identity_digest=request.identity.semantic_digest,
            adapter_ref=self.adapter_ref,
            reality=ThreeDReality.REFERENCE,
            status=status,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            source_artifact_refs=request.all_source_artifact_refs,
            output_artifact_ref=reference_ref,
            output_content_ref=artifact.content_ref,
            report_ref=artifact.content_ref,
            process_artifact_ref=None,
            process_call_ref=None,
            output_role=request.output_role,
            output_path=request.output_path,
            editable_source=False,
            preview_only=request.operation is ThreeDOperation.PREVIEW,
            technical_valid=technical_valid,
            failure_reason=failure_reason,
            observed_at=self._now(),
        )
        return self._persist(access, attempt, request, result, idempotency_key)

    def blender(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        request: ThreeDOperationRequest,
        *,
        idempotency_key: str,
    ) -> ThreeDOperationResult:
        if (
            PurePosixPath(request.output_path).suffix.lower(),
            request.output_media_type,
        ) not in _OUTPUT_MEDIA[request.operation]:
            raise ThreeDContractError(
                "Blender output suffix and media type differ from the operation"
            )
        if request.reference_output_artifact_ref is not None:
            raise ThreeDContractError(
                "REAL 3D operation cannot consume reference output"
            )
        snapshot_artifact_ref = self._authorize_request(
            access,
            attempt,
            request,
            verify_source=False,
        )
        claimed, terminal = self._claim_state(
            access,
            attempt,
            request,
            idempotency_key,
        )
        if terminal is not None:
            return terminal
        process_state = self._managed_process_state(
            attempt,
            request,
        )
        if not claimed and process_state != "ABSENT":
            raise ThreeDIntegrityError(
                "managed Blender process evidence lacks its 3D operation claim"
            )
        has_process_claim = claimed and process_state != "ABSENT"
        if not has_process_claim:
            self._authorize_request(
                access,
                attempt,
                request,
                verify_source=request.source_path is not None,
            )
            if not claimed:
                self._preflight_output_target(access, request)
                self._preflight_staging_root(access, request)
            if (
                request.identity.sandbox_launcher_path is None
                or request.identity.sandbox_launcher_sha256 is None
            ):
                raise ThreeDContractError(
                    "REAL Blender execution requires exact bubblewrap identity"
                )
            executable = Path(request.identity.executable_path)
            launcher = Path(request.identity.sandbox_launcher_path)
            if (
                not request.identity.executable_path.startswith("/")
                or not executable.is_file()
                or not launcher.is_file()
            ):
                if not claimed:
                    prior = self._claim(
                        access,
                        attempt,
                        request,
                        idempotency_key,
                    )
                    if prior is not None:
                        return prior
                return self._unavailable_result(
                    access,
                    attempt,
                    request,
                    idempotency_key,
                    (
                        "exact Blender executable is unavailable"
                        if not executable.is_file()
                        else "exact bubblewrap sandbox launcher is unavailable"
                    ),
                )
            if (
                str(executable.resolve(strict=True))
                != request.identity.executable_path
                or str(launcher.resolve(strict=True))
                != request.identity.sandbox_launcher_path
            ):
                raise ThreeDIntegrityError(
                    "REAL Blender or sandbox launcher path is not canonical"
                )
            if request.resource_allocation_ref is None:
                raise ThreeDAuthorityError(
                    "REAL Blender execution requires one exact allocation"
                )
            self._authorize_observed_tool(
                access,
                request.resource_allocation_ref,
                request.identity,
            )
            executable_digest = _file_sha256(executable)
            driver_digest = _file_sha256(self._DRIVER)
            if (
                not hmac.compare_digest(
                    executable_digest,
                    request.identity.executable_sha256,
                )
                or not hmac.compare_digest(
                    driver_digest,
                    request.identity.driver_sha256,
                )
                or not hmac.compare_digest(
                    _file_sha256(launcher),
                    request.identity.sandbox_launcher_sha256,
                )
            ):
                raise ThreeDIntegrityError(
                    "Blender, sandbox launcher, or fixed driver identity changed"
                )
            if not claimed:
                prior = self._claim(
                    access,
                    attempt,
                    request,
                    idempotency_key,
                )
                if prior is not None:
                    return prior
            driver_path, driver_ref, driver_artifact_ref = self._stage_driver(
                access,
                attempt,
                request.identity,
                request.control_root_ref,
                request.working_directory,
            )
            request_ref = self._request_content(access, request)
        else:
            driver_ref, driver_artifact_ref = self._staged_driver_evidence(
                access,
                attempt,
                request.identity,
                request.control_root_ref,
                request.working_directory,
            )
            request_ref = self._staged_request_evidence(
                access,
                attempt,
                request,
            )
            _, _, driver_path, _ = self._operation_process_request(
                access,
                request,
                driver_ref,
                request_ref,
                require_files=False,
            )
        request_file = (
            f"{request.working_directory}/.biella-three-d-"
            f"{request.request_sha256[:32]}.json"
        )
        if has_process_claim:
            written_ref = request_ref
        else:
            written_ref = self.filesystem.write(
                access,
                attempt,
                root_ref=request.control_root_ref,
                path=request_file,
                content_ref=request_ref,
                idempotency_key=(
                    f"three-d-request-{request.request_sha256[:36]}"
                ),
                mode=0o600,
            ).output_ref
            self._restore_staged_control_file(
                access,
                request.control_root_ref,
                request_file,
                request_ref,
                mode=0o600,
            )
        (
            process_request,
            _,
            expected_driver_path,
            _,
        ) = self._operation_process_request(
            access,
            request,
            driver_ref,
            request_ref,
            require_files=not has_process_claim,
        )
        if driver_path != expected_driver_path or written_ref != request_ref:
            raise ThreeDIntegrityError(
                "staged Blender driver or operation request identity changed"
            )
        process_result, report, output_ready = self._execute_blender_process(
            access,
            attempt,
            request,
            process_request,
            driver_path,
            driver_ref,
            recovering_claim=claimed,
            process_state=process_state,
        )
        driver_reported_error = isinstance(report.get("error"), str)
        report_ref = self.object_store.put(
            _json(report).encode(),
            media_type="application/vnd.biella.3d-report+json",
        )
        if (
            process_result.process_identity is not None
            and not hmac.compare_digest(
                process_result.process_identity.executable_sha256,
                request.identity.process_executable_sha256,
            )
        ):
            raise ThreeDIntegrityError("managed Blender executable identity changed")
        driver_accepted = (
            process_result.process_identity is not None
            and self._accepted_driver_evidence(
                access,
                request,
                report,
                driver_path,
                driver_ref,
            )
        )
        if not driver_accepted:
            if (
                process_result.process_identity is None
                and process_result.failure not in {
                ProcessFailure.EXECUTABLE_NOT_FOUND,
                ProcessFailure.POLICY_DENIED,
                ProcessFailure.SPAWN_FAILED,
                ProcessFailure.RECOVERY_UNCERTAIN,
                }
            ):
                raise ThreeDIntegrityError(
                    "managed Blender process lacks an exact start identity"
                )
            not_started = ThreeDOperationResult(
                project_ref=request.project_ref,
                operation=request.operation,
                request_sha256=request.request_sha256,
                identity_digest=request.identity.semantic_digest,
                adapter_ref=self.adapter_ref,
                reality=ThreeDReality.NOT_RUN,
                status=ThreeDStatus.NOT_RUN,
                node_attempt_id=attempt.attempt_id,
                node_fence=attempt.fence,
                source_artifact_refs=request.all_source_artifact_refs,
                output_artifact_ref=None,
                output_content_ref=None,
                report_ref=report_ref,
                process_artifact_ref=process_result.artifact_ref,
                process_call_ref=process_result.tool_call_ref.value,
                output_role=None,
                output_path=None,
                editable_source=False,
                preview_only=False,
                technical_valid=None,
                failure_reason=self._process_failure_reason(
                    request,
                    process_result,
                    report,
                ),
                observed_at=self._now(),
            )
            return self._persist(
                access,
                attempt,
                request,
                not_started,
                idempotency_key,
            )
        process_succeeded = (
            driver_accepted
            and process_result.status is ProcessStatus.SUCCEEDED
            and not driver_reported_error
        )
        technical_valid: bool | None = None
        if request.operation is ThreeDOperation.VALIDATE:
            technical_valid = report.get("valid") is True and process_succeeded
        status = (
            ThreeDStatus.SUCCEEDED
            if process_succeeded
            and (request.operation is not ThreeDOperation.VALIDATE or technical_valid)
            else ThreeDStatus.FAILED
        )
        failure_reason = None
        if status is ThreeDStatus.FAILED:
            failure_reason = self._process_failure_reason(
                request,
                process_result,
                report,
            )
        output_ref: ContentRef | None = None
        output_filesystem_artifact: ArtifactRef | None = None
        output_observed = False
        output_relative = f"{request.working_directory}/{request.output_path}"
        try:
            if not output_ready:
                raise FilesystemError(
                    "Blender produced no private output for atomic publication"
                )
            output_read = self.filesystem.read(
                access,
                attempt,
                root_ref=request.control_root_ref,
                path=output_relative,
                media_type=request.output_media_type,
                idempotency_key=f"three-d-output-{request.request_sha256[:36]}",
            )
            output_ref = output_read.output_ref
            output_filesystem_artifact = output_read.artifact_ref
            output_observed = True
        except FilesystemError:
            if status is ThreeDStatus.SUCCEEDED:
                status = ThreeDStatus.FAILED
                failure_reason = "Blender exited without the exact requested output"
            if request.operation is ThreeDOperation.VALIDATE:
                output_ref = report_ref
        output_subject_operation = request.operation in {
            ThreeDOperation.MODEL,
            ThreeDOperation.MESH_EDIT,
            ThreeDOperation.TOPOLOGY,
            ThreeDOperation.UV,
            ThreeDOperation.MATERIAL,
            ThreeDOperation.RIG,
            ThreeDOperation.SKIN,
            ThreeDOperation.DEFORM,
            ThreeDOperation.ANIMATE,
            ThreeDOperation.RETARGET,
            ThreeDOperation.BAKE,
            ThreeDOperation.ENVIRONMENT,
            ThreeDOperation.SCENE,
            ThreeDOperation.CONVERT,
            ThreeDOperation.OPTIMIZE,
        }
        if process_succeeded and (
            not output_subject_operation or output_observed
        ):
            subject_identity = report.get("inspection_subject")
            expected_subject = (
                output_ref
                if output_subject_operation
                else self.artifacts.get_artifact(
                    access,
                    request.source_artifact_refs[0],
                ).content_ref
            )
            if (
                expected_subject is None
                or not isinstance(subject_identity, dict)
                or subject_identity.get("sha256") != expected_subject.digest
                or subject_identity.get("size_bytes") != expected_subject.size_bytes
            ):
                raise ThreeDIntegrityError(
                    "Blender inspection subject differs from exact source or output"
                )
            if request.operation in {ThreeDOperation.INSPECT, ThreeDOperation.VALIDATE}:
                if (
                    output_observed
                    and (
                        output_ref is None
                        or output_ref.digest != report_ref.digest
                        or output_ref.size_bytes != report_ref.size_bytes
                    )
                ):
                    raise ThreeDIntegrityError(
                        "Blender report file differs from structured stdout evidence"
                    )
            else:
                output_identity = report.get("output")
                if (
                    output_ref is None
                    or not isinstance(output_identity, dict)
                    or output_identity.get("sha256") != output_ref.digest
                    or output_identity.get("size_bytes") != output_ref.size_bytes
                ):
                    raise ThreeDIntegrityError(
                        "Blender output differs from exact structured report"
                    )
        if process_result.process_identity is not None and not hmac.compare_digest(
            process_result.process_identity.executable_sha256,
            request.identity.process_executable_sha256,
        ):
            raise ThreeDIntegrityError("managed Blender executable identity changed")
        publication_sources = [process_result.artifact_ref, driver_artifact_ref]
        if output_filesystem_artifact is not None:
            publication_sources.append(output_filesystem_artifact)
        should_publish = (
            status is ThreeDStatus.SUCCEEDED
            or request.operation is ThreeDOperation.VALIDATE
        )
        published: ArtifactRef | None = None
        publication: _ThreeDPublication | None = None
        if should_publish:
            if output_ref is None:
                raise ThreeDIntegrityError("3D publication lacks exact output evidence")
            published = self._output_artifact_ref(request)
            publication = _ThreeDPublication(
                snapshot_artifact_ref=snapshot_artifact_ref,
                output_content_ref=output_ref,
                report_ref=report_ref,
                evidence_artifact_refs=tuple(publication_sources),
                request_ref=written_ref,
                output_observed=output_observed,
                status=status,
            )
        editable_source = self._editable_classification(
            request,
            report,
            status,
        )
        result = ThreeDOperationResult(
            project_ref=request.project_ref,
            operation=request.operation,
            request_sha256=request.request_sha256,
            identity_digest=request.identity.semantic_digest,
            adapter_ref=self.adapter_ref,
            reality=ThreeDReality.REAL,
            status=status,
            node_attempt_id=attempt.attempt_id,
            node_fence=attempt.fence,
            source_artifact_refs=request.all_source_artifact_refs,
            output_artifact_ref=published,
            output_content_ref=output_ref if published is not None else None,
            report_ref=report_ref,
            process_artifact_ref=process_result.artifact_ref,
            process_call_ref=process_result.tool_call_ref.value,
            output_role=request.output_role if published is not None else None,
            output_path=request.output_path if published is not None else None,
            editable_source=editable_source,
            preview_only=request.operation is ThreeDOperation.PREVIEW,
            technical_valid=technical_valid,
            failure_reason=failure_reason,
            observed_at=self._now(),
        )
        return self._persist(
            access,
            attempt,
            request,
            result,
            idempotency_key,
            publication=publication,
        )

    def _authorize_runtime(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
    ) -> tuple[str, ResourceAllocationRef | None]:
        self._authorize_project(access, identity.project_ref)
        self._authorize_attempt(access, attempt, None)
        if identity.project_ref != access.project_ref or control_root_ref.project_ref != access.project_ref:
            raise ThreeDScopeError("3D runtime description crossed Project scope")
        if identity.adapter_ref != self.adapter_ref:
            raise ThreeDIntegrityError("3D runtime identity differs from adapter")
        relative = _relative(working_directory, "3D working_directory")
        self.filesystem.get_root(access, control_root_ref)
        connection = self._connect()
        try:
            workspace_ids = tuple(
                cast(str, row["workspace_id"])
                for row in connection.execute(
                    "SELECT workspace_id FROM workspace_identities "
                    "WHERE project_id=?",
                    (access.project_ref.value,),
                ).fetchall()
            )
        finally:
            connection.close()
        matches = []
        for workspace_id in workspace_ids:
            try:
                workspace = self.workspaces.get_workspace(
                    access,
                    WorkspaceRef(access.project_ref, workspace_id),
                )
            except WorkspaceError as exc:
                raise ThreeDIntegrityError(
                    "3D runtime Workspace evidence failed verification"
                ) from exc
            if (
                workspace.candidate_root_ref == control_root_ref
                and workspace.relative_path == relative
                and workspace.task_ref == attempt.task_ref
                and workspace.run_ref == attempt.run_ref
                and workspace.graph_ref == attempt.node_ref.graph_ref
                and workspace.node_ref == attempt.node_ref
                and workspace.node_attempt_id == attempt.attempt_id
                and workspace.node_attempt_fence == attempt.fence
                and workspace.status.value
                not in {"CLEANED", "CANCELLED", "LOST_UNCAPTURED"}
            ):
                matches.append(workspace)
        if len(matches) != 1:
            raise ThreeDAuthorityError(
                "3D runtime requires one exact live attempt-bound Workspace"
            )
        allocation_ref = matches[0].resource_allocation_ref
        if self.reality is ThreeDReality.REAL:
            self._authorize_real_allocation(
                access,
                attempt,
                allocation_ref,
                identity,
            )
        return relative, allocation_ref

    def _runtime_process_request(
        self,
        access: ProjectAccess,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        allocation_ref: ResourceAllocationRef,
        idempotency_key: str,
        driver_ref: ContentRef,
        runtime_request_ref: ContentRef,
    ) -> tuple[ProcessExecutionRequest, Path, Path, str]:
        root = self.filesystem.get_root(access, control_root_ref)
        workspace_path = Path(root.canonical_path, working_directory)
        driver_path = Path(
            workspace_path,
            f".biella-three-d-driver-{identity.driver_sha256[:32]}.py",
        )
        runtime_semantic = self._runtime_semantic(
            identity,
            control_root_ref,
            working_directory,
            allocation_ref,
        )
        runtime_execution_sha = self._runtime_execution_sha(
            runtime_semantic,
            idempotency_key,
        )
        request_path = Path(
            workspace_path,
            f".biella-three-d-runtime-{runtime_execution_sha[:32]}.json",
        )
        blender_argv = (
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python",
            str(driver_path),
            "--",
            "--workspace-root",
            str(workspace_path),
            "--request",
            str(request_path),
        )
        return (
            ProcessExecutionRequest(
                project_ref=identity.project_ref,
                working_root_ref=control_root_ref,
                working_directory=working_directory,
                executable=identity.process_executable_path,
                expected_executable_sha256=(
                    identity.process_executable_sha256
                ),
                argv=self._sandbox_argv(
                    identity,
                    workspace_path,
                    blender_argv,
                    {
                        "driver": driver_path,
                        "request": request_path,
                    },
                    {},
                    (),
                ),
                descriptor_content_refs={
                    "driver": driver_ref,
                    "request": runtime_request_ref,
                },
                timeout_seconds=30.0,
                network_policy=NetworkPolicy.INHERIT,
                resource_policy=ProcessResourcePolicy(
                    cpu_seconds=30,
                    memory_bytes=4 * 1024 * 1024 * 1024,
                    file_size_bytes=64 * 1024 * 1024,
                    process_count=32,
                ),
                resource_allocation_ref=allocation_ref,
                shell=False,
            ),
            workspace_path,
            driver_path,
            runtime_execution_sha,
        )

    @staticmethod
    def _runtime_failure_reason(process: ProcessResult) -> str:
        if process.failure is None:
            return "managed Blender runtime process did not start"
        details = [f"managed Blender runtime process {process.failure.value}"]
        if process.exit_code is not None:
            details.append(f"exit_code={process.exit_code}")
        if process.signal_number is not None:
            details.append(f"signal={process.signal_number}")
        return _reason("; ".join(details))

    @staticmethod
    def _runtime_process_key(runtime_execution_sha: str) -> str:
        return f"three-d-runtime-{runtime_execution_sha[:36]}"

    @staticmethod
    def _runtime_request_key(runtime_execution_sha: str) -> str:
        return f"three-d-runtime-request-{runtime_execution_sha[:36]}"

    @staticmethod
    def _runtime_request_path(
        working_directory: str,
        runtime_execution_sha: str,
    ) -> str:
        return (
            f"{working_directory}/.biella-three-d-runtime-"
            f"{runtime_execution_sha[:32]}.json"
        )

    def _runtime_request_content(
        self,
        identity: ThreeDToolIdentity,
        runtime_semantic: str,
        runtime_execution_sha: str,
    ) -> ContentRef:
        payload = {
            "auxiliary_paths": [],
            "identity": identity.payload(),
            "operation": "describe_runtime",
            "operation_config": {},
            "request_sha256": identity.semantic_digest,
            "runtime_execution_sha256": runtime_execution_sha,
            "runtime_semantic_sha256": runtime_semantic,
            "schema_version": 1,
            "validation_requirements": {},
        }
        return self.object_store.put(
            _json(payload).encode(),
            media_type="application/vnd.biella.3d-runtime-probe+json",
        )

    def _runtime_process_state(
        self,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        process_key: str,
        expected_request: ProcessExecutionRequest | None,
    ) -> str:
        connection = self._connect()
        try:
            claim = connection.execute(
                "SELECT * FROM managed_process_claims WHERE project_id=? "
                "AND node_attempt_id=? AND idempotency_key=?",
                (
                    attempt.node_ref.project_ref.value,
                    attempt.attempt_id,
                    process_key,
                ),
            ).fetchone()
            if claim is None:
                return "ABSENT"
            if expected_request is None:
                return "PRESENT"
            serialized = _json(expected_request.payload()).encode()
            expected_ref = ContentRef(
                "sha256",
                hashlib.sha256(serialized).hexdigest(),
                len(serialized),
                "application/vnd.biella.process-request+json",
            )
            call_ref = ToolCallRef(
                attempt.node_ref.project_ref,
                cast(str, claim["call_id"]),
            )
            expected_claim = {
                "call_ref": call_ref.value,
                "idempotency_key": process_key,
                "node_attempt_id": attempt.attempt_id,
                "project_ref": attempt.node_ref.project_ref.value,
                "request_ref": expected_ref.value,
            }
            if (
                claim["request_digest"] != expected_ref.digest
                or claim["request_size"] != expected_ref.size_bytes
                or claim["request_media_type"] != expected_ref.media_type
                or not hmac.compare_digest(
                    cast(str, claim["claim_sha256"]),
                    _digest(expected_claim),
                )
            ):
                raise ThreeDIntegrityError(
                    "managed Blender runtime claim identity changed"
                )
            execution = connection.execute(
                "SELECT executable_sha256 FROM managed_process_executions "
                "WHERE project_id=? AND call_id=?",
                (
                    attempt.node_ref.project_ref.value,
                    call_ref.call_id,
                ),
            ).fetchone()
            prepared = connection.execute(
                "SELECT executable_sha256 FROM "
                "managed_process_prepared_executions "
                "WHERE project_id=? AND call_id=?",
                (
                    attempt.node_ref.project_ref.value,
                    call_ref.call_id,
                ),
            ).fetchone()
            result = connection.execute(
                "SELECT 1 FROM managed_process_results WHERE project_id=? "
                "AND call_id=?",
                (
                    attempt.node_ref.project_ref.value,
                    call_ref.call_id,
                ),
            ).fetchone()
        finally:
            connection.close()
        if (
            prepared is not None
            and prepared["executable_sha256"]
            != identity.process_executable_sha256
        ) or (
            execution is not None
            and execution["executable_sha256"]
            != identity.process_executable_sha256
        ):
            raise ThreeDIntegrityError(
                "managed Blender runtime execution identity changed"
            )
        if result is not None:
            return "RESULT"
        if execution is not None:
            return "STARTED"
        if prepared is not None:
            return "PREPARED"
        return "CLAIMED"

    def _staged_runtime_request_evidence(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        runtime_semantic: str,
        runtime_execution_sha: str,
    ) -> ContentRef:
        expected_ref = self._runtime_request_content(
            identity,
            runtime_semantic,
            runtime_execution_sha,
        )
        relative = self._runtime_request_path(
            working_directory,
            runtime_execution_sha,
        )
        idempotency_key = self._runtime_request_key(
            runtime_execution_sha
        )
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT call_id FROM filesystem_operation_claims "
                "WHERE project_id=? AND node_attempt_id=? "
                "AND idempotency_key=?",
                (
                    identity.project_ref.value,
                    attempt.attempt_id,
                    idempotency_key,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ThreeDIntegrityError(
                "staged runtime request lost immutable filesystem evidence"
            )
        try:
            operation = self.filesystem.get_operation(
                access,
                ToolCallRef(
                    identity.project_ref,
                    cast(str, row["call_id"]),
                ),
            )
            self.object_store.verify(operation.output_ref)
        except (FilesystemError, ObjectStorageError) as exc:
            raise ThreeDIntegrityError(
                "staged runtime request evidence failed verification"
            ) from exc
        expected_payload = {
            "content_ref": expected_ref.value,
            "mode": 0o600,
            "operation": "write",
            "path": relative,
            "root_ref": control_root_ref.value,
            "schema_version": 2,
        }
        if (
            operation.operation != "write"
            or dict(operation.payload) != expected_payload
            or operation.output_ref != expected_ref
        ):
            raise ThreeDIntegrityError(
                "staged runtime request content identity changed"
            )
        return operation.output_ref

    def _runtime_description_from_process(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        allocation_ref: ResourceAllocationRef,
        process_key: str,
        expected_request: ProcessExecutionRequest,
        driver_path: Path,
        driver_ref: ContentRef,
        runtime_request_ref: ContentRef,
        process: ProcessResult,
    ) -> ThreeDRuntimeDescription:
        self._verify_process_claim(attempt, process_key, process)
        try:
            self.object_store.verify(runtime_request_ref)
            process_request = _strict_json_loads(
                self.object_store.read(process.request_ref)
            )
        except (
            ObjectStorageError,
            TypeError,
            ValueError,
            RecursionError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise ThreeDIntegrityError(
                "managed Blender runtime request evidence changed"
            ) from exc
        if process_request != expected_request.payload():
            raise ThreeDIntegrityError(
                "managed Blender runtime process request changed"
            )
        if process.status is not ProcessStatus.SUCCEEDED:
            if process.failure is None or (
                process.process_identity is not None
                and process.process_identity.executable_sha256
                != identity.process_executable_sha256
            ):
                raise ThreeDIntegrityError(
                    "failed Blender runtime process identity changed"
                )
            return ThreeDRuntimeDescription(
                project_ref=identity.project_ref,
                identity_digest=identity.semantic_digest,
                adapter_ref=self.adapter_ref,
                reality=ThreeDReality.NOT_RUN,
                available=False,
                tool_name=identity.tool_name,
                tool_version=identity.tool_version,
                executable_sha256=identity.executable_sha256,
                driver_sha256=identity.driver_sha256,
                embedded_python_version=None,
                network_enforcement=process.network_enforcement,
                plugin_identities=identity.plugins,
                runtime_ref=identity.runtime_ref,
                resource_allocation_ref=allocation_ref,
                process_call_ref=process.tool_call_ref.value,
                unavailability_ref=None,
                unavailable_reason=self._runtime_failure_reason(process),
                observed_at=process.completed_at,
            )
        if (
            process.process_identity is None
            or process.failure is not None
            or process.process_identity.executable_sha256
            != identity.process_executable_sha256
        ):
            raise ThreeDIntegrityError(
                "successful Blender runtime lacks exact process identity"
            )
        report = self._driver_report(
            self.object_store.read(process.stdout_ref)
        )
        runtime = report.get("runtime")
        if (
            report.get("driver_evidence") != self._DRIVER_EVIDENCE
            or report.get("request_sha256") != identity.semantic_digest
            or report.get("operation") != "describe_runtime"
            or report.get("content_trust") != "UNTRUSTED_DATA"
            or not isinstance(runtime, dict)
            or identity.tool_name != "Blender"
            or runtime.get("tool_name") != "Blender"
            or runtime.get("tool_version") != identity.tool_version
            or runtime.get("binary_path") != identity.executable_path
            or runtime.get("binary_sha256")
            != identity.executable_sha256
            or runtime.get("driver_path") != str(driver_path)
            or runtime.get("driver_sha256") != identity.driver_sha256
            or runtime.get("driver_size_bytes") != driver_ref.size_bytes
            or runtime.get("external_plugins")
            != [item.payload() for item in identity.plugins]
            or runtime.get("factory_startup") is not True
            or not isinstance(runtime.get("embedded_python"), str)
        ):
            raise ThreeDIntegrityError(
                "Blender runtime version probe failed exact verification"
            )
        return ThreeDRuntimeDescription(
            project_ref=identity.project_ref,
            identity_digest=identity.semantic_digest,
            adapter_ref=self.adapter_ref,
            reality=ThreeDReality.REAL,
            available=True,
            tool_name=identity.tool_name,
            tool_version=identity.tool_version,
            executable_sha256=identity.executable_sha256,
            driver_sha256=identity.driver_sha256,
            embedded_python_version=cast(str, runtime["embedded_python"]),
            network_enforcement="SANDBOX_NETWORK_DENIED",
            plugin_identities=identity.plugins,
            runtime_ref=identity.runtime_ref,
            resource_allocation_ref=allocation_ref,
            process_call_ref=process.tool_call_ref.value,
            unavailability_ref=None,
            unavailable_reason=None,
            observed_at=process.completed_at,
        )

    def _runtime_unavailability_report(
        self,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        allocation_ref: ResourceAllocationRef | None,
        reason: str,
    ) -> dict[str, object]:
        return {
            "adapter_ref": self.adapter_ref,
            "available": False,
            "control_root_ref": control_root_ref.value,
            "executable_path": identity.executable_path,
            "executable_sha256": identity.executable_sha256,
            "identity_digest": identity.semantic_digest,
            "project_ref": identity.project_ref.value,
            "reality": ThreeDReality.NOT_RUN.value,
            "reason": reason,
            "resource_allocation_ref": (
                None if allocation_ref is None else allocation_ref.value
            ),
            "schema_version": 1,
            "working_directory": working_directory,
        }

    def _verify_runtime_description(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        expected_allocation_ref: ResourceAllocationRef | None,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        description: ThreeDRuntimeDescription,
        idempotency_key: str,
    ) -> None:
        if (
            description.project_ref != identity.project_ref
            or description.adapter_ref != self.adapter_ref
            or description.identity_digest != identity.semantic_digest
            or description.tool_name != identity.tool_name
            or description.tool_version != identity.tool_version
            or description.executable_sha256 != identity.executable_sha256
            or description.driver_sha256 != identity.driver_sha256
            or description.plugin_identities != identity.plugins
            or description.runtime_ref != identity.runtime_ref
            or description.resource_allocation_ref != expected_allocation_ref
            or (
                self.reality is ThreeDReality.REFERENCE
                and description.reality is not ThreeDReality.REFERENCE
            )
            or (
                self.reality is ThreeDReality.REAL
                and description.reality
                not in {ThreeDReality.REAL, ThreeDReality.NOT_RUN}
            )
        ):
            raise ThreeDIntegrityError(
                "persisted 3D runtime description identity changed"
            )
        if description.reality is ThreeDReality.REFERENCE:
            if (
                not description.available
                or description.unavailable_reason is not None
            ):
                raise ThreeDIntegrityError(
                    "persisted REFERENCE 3D availability changed"
                )
            return
        runtime_semantic = self._runtime_semantic(
            identity,
            control_root_ref,
            working_directory,
            expected_allocation_ref,
        )
        runtime_execution_sha = self._runtime_execution_sha(
            runtime_semantic,
            idempotency_key,
        )
        process_key = self._runtime_process_key(runtime_execution_sha)
        if expected_allocation_ref is None:
            raise ThreeDIntegrityError(
                "non-reference runtime lacks exact allocation evidence"
            )
        state = self._runtime_process_state(
            attempt,
            identity,
            process_key,
            None,
        )
        if description.process_call_ref is not None:
            prefix = f"tool-call://{identity.project_ref.value}/"
            if not description.process_call_ref.startswith(prefix):
                raise ThreeDIntegrityError(
                    "runtime process call crossed Project scope"
                )
            try:
                process = self.process.get_result(
                    access,
                    ToolCallRef(
                        identity.project_ref,
                        description.process_call_ref.removeprefix(prefix),
                    ),
                )
                driver_ref, _ = self._staged_driver_evidence(
                    access,
                    attempt,
                    identity,
                    control_root_ref,
                    working_directory,
                )
                runtime_request_ref = (
                    self._staged_runtime_request_evidence(
                        access,
                        attempt,
                        identity,
                        control_root_ref,
                        working_directory,
                        runtime_semantic,
                        runtime_execution_sha,
                    )
                )
                (
                    expected_request,
                    _,
                    driver_path,
                    expected_execution_sha,
                ) = self._runtime_process_request(
                    access,
                    identity,
                    control_root_ref,
                    working_directory,
                    expected_allocation_ref,
                    idempotency_key,
                    driver_ref,
                    runtime_request_ref,
                )
                state = self._runtime_process_state(
                    attempt,
                    identity,
                    process_key,
                    expected_request,
                )
                if (
                    expected_execution_sha != runtime_execution_sha
                    or state != "RESULT"
                ):
                    raise ThreeDIntegrityError(
                        "attempted runtime lacks exact terminal process evidence"
                    )
                expected = self._runtime_description_from_process(
                    access,
                    attempt,
                    identity,
                    expected_allocation_ref,
                    process_key,
                    expected_request,
                    driver_path,
                    driver_ref,
                    runtime_request_ref,
                    process,
                )
            except (ProcessError, WorkspaceError) as exc:
                raise ThreeDIntegrityError(
                    "attempted runtime evidence changed"
                ) from exc
            if description != expected:
                raise ThreeDIntegrityError(
                    "persisted attempted runtime description changed"
                )
            return
        if description.reality is not ThreeDReality.NOT_RUN or state != "ABSENT":
            raise ThreeDIntegrityError(
                "unattempted runtime contradicts managed process evidence"
            )
        reason = description.unavailable_reason
        if reason not in {
            "exact Blender executable is unavailable",
            "exact bubblewrap sandbox launcher is unavailable",
        }:
            raise ThreeDIntegrityError(
                "unattempted runtime reason is not an exact dependency"
            )
        unavailable_bytes = _json(
            self._runtime_unavailability_report(
                identity,
                control_root_ref,
                working_directory,
                expected_allocation_ref,
                reason,
            )
        ).encode()
        if description.unavailability_ref is not None:
            self.object_store.verify(description.unavailability_ref)
        if (
            description.available
            or description.unavailable_reason != reason
            or description.unavailability_ref is None
            or description.unavailability_ref.media_type
            != "application/vnd.biella.3d-unavailability+json"
            or description.unavailability_ref.digest
            != hashlib.sha256(unavailable_bytes).hexdigest()
            or description.unavailability_ref.size_bytes
            != len(unavailable_bytes)
        ):
            raise ThreeDIntegrityError(
                "persisted NOT_RUN 3D availability changed"
            )

    def _runtime_claim(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        resource_allocation_ref: ResourceAllocationRef | None,
        idempotency_key: str,
    ) -> tuple[bool, ThreeDRuntimeDescription | None]:
        if not isinstance(idempotency_key, str) or _KEY.fullmatch(idempotency_key) is None:
            raise ThreeDContractError("3D runtime idempotency key is malformed")
        semantic = self._runtime_semantic(
            identity,
            control_root_ref,
            working_directory,
            resource_allocation_ref,
        )
        run_attempt = self._run_attempt(access, attempt)
        values = (
            identity.project_ref.value,
            self.adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            idempotency_key,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT semantic_sha256 FROM three_d_runtime_claims WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                values,
            ).fetchone()
            if row is None:
                try:
                    _, _, task, _ = self.executions._require_live_attempt(
                        connection,
                        access,
                        attempt,
                        allowed_statuses={"RUNNING"},
                    )
                    current_run = (
                        self.runs.assert_current_run_authority_in_transaction(
                            connection,
                            access,
                            run_attempt,
                        )
                    )
                except (
                    NodeExecutionAuthorityError,
                    NodeExecutionError,
                    RunAuthorityError,
                    RunError,
                ) as exc:
                    raise ThreeDAuthorityError(
                        "3D runtime claim lost exact Node or Run authority"
                    ) from exc
                if (
                    task.canonical_digest != attempt.task_digest
                    or current_run.task_ref != attempt.task_ref
                    or current_run.task_digest != attempt.task_digest
                ):
                    raise ThreeDAuthorityError(
                        "3D runtime claim Task authority changed"
                    )
                connection.execute(
                    "INSERT INTO three_d_runtime_claims VALUES (?,?,?,?,?,?)",
                    (*values, semantic),
                )
                connection.commit()
                return False, None
            if not hmac.compare_digest(cast(str, row["semantic_sha256"]), semantic):
                raise ThreeDConflictError("3D runtime idempotency identity changed")
            result = connection.execute(
                "SELECT description_json,record_sha256 FROM three_d_runtime_descriptions WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? AND node_fence=? AND idempotency_key=?",
                values,
            ).fetchone()
            connection.commit()
            if result is None:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    _, _, task, _ = self.executions._require_live_attempt(
                        connection,
                        access,
                        attempt,
                        allowed_statuses={"RUNNING"},
                    )
                    current_run = (
                        self.runs.assert_current_run_authority_in_transaction(
                            connection,
                            access,
                            run_attempt,
                        )
                    )
                except (
                    NodeExecutionAuthorityError,
                    NodeExecutionError,
                    RunAuthorityError,
                    RunError,
                ) as exc:
                    raise ThreeDAuthorityError(
                        "incomplete 3D runtime claim lost Node or Run authority"
                    ) from exc
                if (
                    task.canonical_digest != attempt.task_digest
                    or current_run.task_ref != attempt.task_ref
                    or current_run.task_digest != attempt.task_digest
                ):
                    raise ThreeDAuthorityError(
                        "incomplete 3D runtime Task authority changed"
                    )
                connection.commit()
                return True, None
            description = self._runtime_from_row(result)
            self._verify_runtime_description(
                access,
                attempt,
                identity,
                resource_allocation_ref,
                control_root_ref,
                working_directory,
                description,
                idempotency_key,
            )
            return True, description
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _runtime_semantic(
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        resource_allocation_ref: ResourceAllocationRef | None,
    ) -> str:
        return _digest(
            {
                "control_root_ref": control_root_ref.value,
                "identity_digest": identity.semantic_digest,
                "resource_allocation_ref": (
                    None
                    if resource_allocation_ref is None
                    else resource_allocation_ref.value
                ),
                "working_directory": working_directory,
            }
        )

    @staticmethod
    def _runtime_execution_sha(
        runtime_semantic: str,
        idempotency_key: str,
    ) -> str:
        if not isinstance(idempotency_key, str) or _KEY.fullmatch(
            idempotency_key
        ) is None:
            raise ThreeDContractError(
                "3D runtime idempotency key is malformed"
            )
        return _digest(
            {
                "idempotency_key": idempotency_key,
                "runtime_semantic": runtime_semantic,
            }
        )

    def _persist_runtime(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        description: ThreeDRuntimeDescription,
        idempotency_key: str,
    ) -> ThreeDRuntimeDescription:
        _, authorized_allocation_ref = self._authorize_runtime(
            access,
            attempt,
            identity,
            control_root_ref,
            working_directory,
        )
        expected_allocation_ref = (
            authorized_allocation_ref
            if self.reality is ThreeDReality.REAL
            else None
        )
        self._verify_runtime_description(
            access,
            attempt,
            identity,
            expected_allocation_ref,
            control_root_ref,
            working_directory,
            description,
            idempotency_key,
        )
        semantic = self._runtime_semantic(
            identity,
            control_root_ref,
            working_directory,
            expected_allocation_ref,
        )
        values = (
            description.project_ref.value,
            self.adapter_ref,
            attempt.attempt_id,
            attempt.fence,
            idempotency_key,
        )
        run_attempt = self._run_attempt(access, attempt)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                _, _, task, _ = self.executions._require_live_attempt(
                    connection,
                    access,
                    attempt,
                    allowed_statuses={"RUNNING"},
                )
                current_run = self.runs.assert_current_run_authority_in_transaction(
                    connection,
                    access,
                    run_attempt,
                )
            except (
                NodeExecutionAuthorityError,
                NodeExecutionError,
                RunAuthorityError,
                RunError,
            ) as exc:
                raise ThreeDAuthorityError(
                    "3D runtime lost exact Node or Run authority before persistence"
                ) from exc
            if (
                task.canonical_digest != attempt.task_digest
                or current_run.task_ref != attempt.task_ref
                or current_run.task_digest != attempt.task_digest
            ):
                raise ThreeDAuthorityError(
                    "3D runtime Task authority changed before persistence"
                )
            claim = connection.execute(
                "SELECT semantic_sha256 FROM three_d_runtime_claims "
                "WHERE project_id=? AND adapter_ref=? AND node_attempt_id=? "
                "AND node_fence=? AND idempotency_key=?",
                values,
            ).fetchone()
            if claim is None or not hmac.compare_digest(
                cast(str, claim["semantic_sha256"]),
                semantic,
            ):
                raise ThreeDIntegrityError(
                    "3D runtime persistence lost its exact claim"
                )
            prior = connection.execute(
                "SELECT description_json,record_sha256 "
                "FROM three_d_runtime_descriptions WHERE project_id=? "
                "AND adapter_ref=? AND node_attempt_id=? AND node_fence=? "
                "AND idempotency_key=?",
                values,
            ).fetchone()
            if prior is not None:
                connection.commit()
                persisted = self._runtime_from_row(prior)
                self._verify_runtime_description(
                    access,
                    attempt,
                    identity,
                    expected_allocation_ref,
                    control_root_ref,
                    working_directory,
                    persisted,
                    idempotency_key,
                )
                return persisted
            connection.execute(
                "INSERT INTO three_d_runtime_descriptions VALUES (?,?,?,?,?,?,?)",
                (*values, _json(description.payload()), description.record_sha256),
            )
            connection.commit()
            self._verify_runtime_description(
                access,
                attempt,
                identity,
                expected_allocation_ref,
                control_root_ref,
                working_directory,
                description,
                idempotency_key,
            )
            return description
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ThreeDConflictError("3D runtime description conflicts") from exc
        finally:
            connection.close()

    @staticmethod
    def _runtime_from_row(row: Mapping[str, object]) -> ThreeDRuntimeDescription:
        try:
            payload = json.loads(cast(str, row["description_json"]))
            if not isinstance(payload, dict):
                raise TypeError
            project_ref = ProjectRef(cast(str, payload["project_ref"]))
            plugins = tuple(
                ThreeDPluginIdentity(
                    cast(str, item["name"]),
                    cast(str, item["version"]),
                    cast(str, item["digest"]),
                )
                for item in cast(list[dict[str, object]], payload["plugin_identities"])
            )
            allocation_value = payload["resource_allocation_ref"]
            allocation_ref = None
            if allocation_value is not None:
                prefix = f"resource-allocation://{project_ref.value}/"
                if not isinstance(allocation_value, str) or not allocation_value.startswith(
                    prefix
                ):
                    raise ValueError
                allocation_ref = ResourceAllocationRef(
                    project_ref,
                    allocation_value.removeprefix(prefix),
                )
            description = ThreeDRuntimeDescription(
                project_ref=project_ref,
                identity_digest=cast(str, payload["identity_digest"]),
                adapter_ref=cast(str, payload["adapter_ref"]),
                reality=ThreeDReality(cast(str, payload["reality"])),
                available=cast(bool, payload["available"]),
                tool_name=cast(str, payload["tool_name"]),
                tool_version=cast(str, payload["tool_version"]),
                executable_sha256=cast(str, payload["executable_sha256"]),
                driver_sha256=cast(str, payload["driver_sha256"]),
                embedded_python_version=cast(
                    str | None,
                    payload["embedded_python_version"],
                ),
                network_enforcement=cast(str, payload["network_enforcement"]),
                plugin_identities=plugins,
                runtime_ref=cast(str, payload["runtime_ref"]),
                resource_allocation_ref=allocation_ref,
                process_call_ref=cast(str | None, payload["process_call_ref"]),
                unavailability_ref=_content_from_payload(
                    payload["unavailability_ref"]
                ),
                unavailable_reason=cast(str | None, payload["unavailable_reason"]),
                observed_at=cast(str, payload["observed_at"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ThreeDIntegrityError("persisted 3D runtime description is malformed") from exc
        if not hmac.compare_digest(description.record_sha256, cast(str, row["record_sha256"])):
            raise ThreeDIntegrityError("persisted 3D runtime description digest changed")
        return description

    def finalize_character_rig_ref(
        self,
        access: ProjectAccess,
        result: ThreeDOperationResult,
        specification: CharacterSpecification,
    ) -> CharacterRigRef:
        """Finalize the durable REAL character handoff consumed by P3-07."""

        if not isinstance(result, ThreeDOperationResult) or not isinstance(
            specification,
            CharacterSpecification,
        ):
            raise CharacterContractError(
                "character handoff requires exact result and specification records"
            )
        if (
            self.reality is not ThreeDReality.REAL
            or result.reality is not ThreeDReality.REAL
            or result.status is not ThreeDStatus.SUCCEEDED
            or result.operation
            not in {
                ThreeDOperation.RIG,
                ThreeDOperation.SKIN,
                ThreeDOperation.DEFORM,
            }
            or not result.editable_source
            or result.preview_only
            or result.project_ref != access.project_ref
            or specification.project_ref != access.project_ref
            or result.output_artifact_ref is None
            or result.output_content_ref is None
            or result.report_ref is None
            or result.process_call_ref is None
        ):
            raise CharacterContractError(
                "character handoff requires one successful REAL editable character result"
            )
        assert result.output_artifact_ref is not None
        assert result.output_content_ref is not None
        assert result.report_ref is not None
        assert result.process_call_ref is not None
        output_artifact_ref = result.output_artifact_ref
        output_content_ref = result.output_content_ref
        report_ref = result.report_ref
        process_call_ref = result.process_call_ref
        try:
            self._authorize_project(access, result.project_ref)
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT result_json,record_sha256 FROM three_d_operation_results "
                    "WHERE project_id=? AND adapter_ref=?",
                    (result.project_ref.value, self.adapter_ref),
                ).fetchall()
            finally:
                connection.close()
            persisted = next(
                (
                    self._result_from_row(row)
                    for row in rows
                    if hmac.compare_digest(
                        self._result_from_row(row).record_sha256,
                        result.record_sha256,
                    )
                    and self._result_from_row(row).request_sha256
                    == result.request_sha256
                ),
                None,
            )
            if persisted != result:
                raise CharacterContractError(
                    "character result is forged, stale, or not durably persisted"
                )
            output = self.artifacts.get_artifact(access, output_artifact_ref)
            if (
                output.content_ref is None
                or _content_payload(output.content_ref)
                != _content_payload(output_content_ref)
                or output.derivation_type
                != f"3d.{result.operation.value.replace('_', '-')}"
            ):
                raise CharacterContractError(
                    "character result artifact identity differs from its durable result"
                )
            self.object_store.verify(output_content_ref)
            self.object_store.verify(report_ref)
            process = self.process.get_result(
                access,
                ToolCallRef(
                    result.project_ref,
                    process_call_ref.rsplit("/", 1)[-1],
                ),
            )
            report = self._driver_report(self.object_store.read(process.stdout_ref))
            report_bytes = _json(report).encode()
            if (
                hashlib.sha256(report_bytes).hexdigest() != report_ref.digest
                or len(report_bytes) != report_ref.size_bytes
                or process.status is not ProcessStatus.SUCCEEDED
                or process.process_identity is None
            ):
                raise CharacterContractError(
                    "character result lacks exact successful driver evidence"
                )
            character = report.get("character_identity")
            runtime = report.get("runtime")
            if (
                not isinstance(character, dict)
                or character.get("mesh_sha256") != output_content_ref.digest
                or character.get("skeleton_sha256")
                != specification.skeleton_content_sha256
                or not isinstance(runtime, dict)
                or not isinstance(runtime.get("driver_sha256"), str)
                or _SHA256.fullmatch(cast(str, runtime["driver_sha256"])) is None
            ):
                raise CharacterContractError(
                    "character result mesh, skeleton, or script identity changed"
                )

            def contains_exact_source(
                reference: str,
                digest: str,
            ) -> bool:
                pending = [output_artifact_ref]
                seen: set[ArtifactRef] = set()
                while pending:
                    current = pending.pop()
                    if current in seen:
                        continue
                    seen.add(current)
                    artifact = self.artifacts.get_artifact(access, current)
                    if (
                        artifact.artifact_ref.value == reference
                        and artifact.content_ref is not None
                        and artifact.content_ref.digest == digest
                    ):
                        return True
                    pending.extend(artifact.source_artifact_refs)
                    if len(seen) > 256:
                        raise CharacterContractError(
                            "character artifact lineage is unbounded"
                        )
                return False

            if not contains_exact_source(
                specification.character_artifact_ref,
                specification.character_content_sha256,
            ) or not contains_exact_source(
                specification.mesh_ref,
                specification.mesh_content_sha256,
            ):
                raise CharacterContractError(
                    "character specification does not match result artifact lineage"
                )
            handoff = CharacterRigRef(
                project_ref=result.project_ref,
                character_id=specification.character_id,
                character_artifact_ref=specification.character_artifact_ref,
                character_content_sha256=specification.character_content_sha256,
                mesh_ref=specification.mesh_ref,
                mesh_content_sha256=specification.mesh_content_sha256,
                skeleton_ref=specification.skeleton_ref,
                skeleton_content_sha256=specification.skeleton_content_sha256,
                rig_id=f"rig-{result.request_sha256[:32]}",
                rig_artifact_ref=output_artifact_ref.value,
                rig_content_sha256=output_content_ref.digest,
                scale=specification.scale,
                coordinate_system=specification.coordinate_system,
                coordinate_convention_ref=specification.coordinate_convention_ref,
                rest_pose_ref=specification.rest_pose_ref,
                provenance_ref=specification.provenance_ref,
                tool_provenance_ref=(
                    f"tool-provenance://three-d/{result.identity_digest}"
                ),
                script_provenance_ref=(
                    "script-provenance://blender-driver/"
                    f"{runtime['driver_sha256']}"
                ),
                target_metadata=specification.target_metadata,
            )
            handoff.require_specification(specification)
            return handoff
        except CharacterContractError:
            raise
        except (
            ArtifactError,
            ObjectStorageError,
            ProcessError,
            ThreeDError,
            ValueError,
        ) as exc:
            raise CharacterContractError(
                "character handoff evidence failed verification"
            ) from exc

    @staticmethod
    def _environment_manifest_payload(
        manifest: EnvironmentIntegrationManifest,
    ) -> dict[str, object]:
        specification = manifest.specification
        terrain = manifest.terrain
        return {
            "collision_ref": manifest.collision_ref,
            "content_sha256": manifest.content_sha256,
            "derivation_ref": manifest.derivation_ref,
            "material_ref": manifest.material_ref,
            "navigation_ref": manifest.navigation_ref,
            "partition_ref": manifest.partition_ref,
            "placed_assets": [
                {
                    "asset_id": item.asset_id,
                    "content_sha256": item.content_sha256,
                    "material_ref": item.material_ref,
                    "parent_ref": item.parent_ref,
                    "partition_id": item.partition_id,
                    "project_ref": item.project_ref.value,
                    "source_ref": item.source_ref,
                    "transform": list(item.transform),
                    "variant": item.variant,
                }
                for item in manifest.placed_assets
            ],
            "project_ref": manifest.project_ref.value,
            "prop_ref": manifest.prop_ref,
            "runtime_ref": manifest.runtime_ref,
            "specification": {
                "asset_library_refs": list(specification.asset_library_refs),
                "content_sha256": specification.content_sha256,
                "coordinates": dict(specification.coordinates),
                "environment_id": specification.environment_id,
                "gameplay_navigation": dict(specification.gameplay_navigation),
                "layout": dict(specification.layout),
                "output_acceptance_refs": list(specification.output_acceptance_refs),
                "partition": dict(specification.partition),
                "performance": dict(specification.performance),
                "project_ref": specification.project_ref.value,
                "representation_tags": list(specification.representation_tags),
                "source_ref": specification.source_ref,
                "target_tool_engine": dict(specification.target_tool_engine),
                "units": specification.units,
                "visual": dict(specification.visual),
            },
            "structure_ref": manifest.structure_ref,
            "terrain": {
                "config": dict(terrain.config),
                "content_sha256": terrain.content_sha256,
                "generator_ref": terrain.generator_ref,
                "generator_version": terrain.generator_version,
                "project_ref": terrain.project_ref.value,
                "seed": terrain.seed,
                "terrain_id": terrain.terrain_id,
                "terrain_ref": terrain.terrain_ref,
            },
            "tool_ref": manifest.tool_ref,
            "vegetation_ref": manifest.vegetation_ref,
        }

    def _verified_environment_handoff(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
    ) -> tuple[Mapping[str, object], ArtifactRef, ContentRef]:
        if (
            not isinstance(request, ThreeDOperationRequest)
            or not isinstance(result, ThreeDOperationResult)
            or self.reality is not ThreeDReality.REAL
            or result.reality is not ThreeDReality.REAL
            or result.status is not ThreeDStatus.SUCCEEDED
            or result.operation is not ThreeDOperation.ENVIRONMENT
            or request.operation is not ThreeDOperation.ENVIRONMENT
            or request.request_sha256 != result.request_sha256
            or request.identity.semantic_digest != result.identity_digest
            or request.project_ref != access.project_ref
            or result.project_ref != access.project_ref
            or not result.editable_source
            or result.preview_only
            or result.output_artifact_ref is None
            or result.output_content_ref is None
            or result.report_ref is None
            or result.process_call_ref is None
            or request.environment_spec is None
        ):
            raise EnvironmentContractError("environment handoff requires one exact successful REAL editable result")
        try:
            self._authorize_project(access, result.project_ref)
            output = self.artifacts.get_artifact(access, result.output_artifact_ref)
            if (
                output.content_ref is None
                or _content_payload(output.content_ref) != _content_payload(result.output_content_ref)
                or output.derivation_type != "3d.environment"
            ):
                raise EnvironmentContractError("environment artifact identity differs from durable result")
            self.object_store.verify(result.output_content_ref)
            self.object_store.verify(result.report_ref)
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT result_json,record_sha256 FROM three_d_operation_results WHERE project_id=? AND adapter_ref=?",
                    (access.project_ref.value, self.adapter_ref),
                ).fetchall()
            finally:
                connection.close()
            if not any(
                self._result_from_row(candidate) == result
                and hmac.compare_digest(cast(str, candidate["record_sha256"]), result.record_sha256)
                for candidate in row
            ):
                raise EnvironmentContractError("environment result is forged, stale, or not durably persisted")
            process = self.process.get_result(
                access,
                ToolCallRef(result.project_ref, result.process_call_ref.rsplit("/", 1)[-1]),
            )
            report = self._driver_report(self.object_store.read(process.stdout_ref))
            report_bytes = _json(report).encode()
            if (
                hashlib.sha256(report_bytes).hexdigest() != result.report_ref.digest
                or len(report_bytes) != result.report_ref.size_bytes
                or process.status is not ProcessStatus.SUCCEEDED
                or process.process_identity is None
            ):
                raise EnvironmentContractError("environment result lacks exact successful driver evidence")
            self._verify_operation_report_schema(request, report)
            return report, result.output_artifact_ref, result.output_content_ref
        except EnvironmentContractError:
            raise
        except (ArtifactError, ObjectStorageError, ProcessError, ThreeDError, ValueError) as exc:
            raise EnvironmentContractError("environment handoff evidence failed verification") from exc

    def verify_environment_manifest_publication(
        self,
        access: ProjectAccess,
        publication: EnvironmentManifestPublication,
    ) -> EnvironmentManifestPublication:
        if (
            not isinstance(publication, EnvironmentManifestPublication)
            or publication.manifest.project_ref != access.project_ref
            or publication.manifest_artifact_ref.project_ref != access.project_ref
        ):
            raise EnvironmentContractError("environment manifest publication crossed Project scope")
        try:
            artifact = self.artifacts.get_artifact(access, publication.manifest_artifact_ref)
            if (
                artifact.role != "3d.environment-manifest"
                or artifact.derivation_type != "3d.environment-manifest"
                or artifact.content_ref is None
                or _content_payload(artifact.content_ref) != _content_payload(publication.manifest_content_ref)
            ):
                raise EnvironmentContractError("environment manifest artifact identity changed")
            self.object_store.verify(publication.manifest_content_ref)
            expected = _json(self._environment_manifest_payload(publication.manifest)).encode()
            if self.object_store.read(publication.manifest_content_ref) != expected:
                raise EnvironmentContractError("environment manifest artifact bytes changed")
            return publication
        except EnvironmentContractError:
            raise
        except (ArtifactError, ObjectStorageError, ValueError) as exc:
            raise EnvironmentContractError("environment manifest publication failed verification") from exc

    def finalize_environment_integration_manifest(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        manifest: EnvironmentIntegrationManifest,
    ) -> EnvironmentManifestPublication:
        report, output_ref, output_content = self._verified_environment_handoff(access, request, result)
        if not isinstance(manifest, EnvironmentIntegrationManifest) or manifest.project_ref != access.project_ref:
            raise EnvironmentContractError("environment manifest is malformed or out of project scope")
        assert request.environment_spec is not None
        layout = request.environment_spec
        runtime_ref = "runtime://biella/" + _digest(cast(Mapping[str, object], report["runtime"]))
        expected_derivation = f"derivation://three-d/environment/{result.record_sha256}"
        expected_assets = tuple(layout.placed_assets)
        if (
            manifest.specification.source_ref != output_ref.value
            or manifest.specification.content_sha256 != output_content.digest
            or manifest.content_sha256 != output_content.digest
            or tuple(manifest.specification.asset_library_refs) != tuple(sorted(item.artifact_ref.value for item in expected_assets))
            or manifest.terrain.generator_ref != f"generator://three-d/{layout.generator}"
            or manifest.terrain.generator_version != layout.generator_version
            or manifest.terrain.seed != layout.seed
            or manifest.terrain.config != {key: str(value) for key, value in layout.generator_config.items()}
            or manifest.terrain.terrain_ref != output_ref.value
            or manifest.terrain.content_sha256 != output_content.digest
            or len(manifest.placed_assets) != len(expected_assets)
            or manifest.tool_ref != request.identity.adapter_ref
            or manifest.runtime_ref != runtime_ref
            or manifest.derivation_ref != expected_derivation
            or any(value != output_ref.value for value in (
                manifest.structure_ref, manifest.prop_ref, manifest.vegetation_ref,
                manifest.material_ref, manifest.collision_ref, manifest.navigation_ref,
                manifest.partition_ref,
            ))
        ):
            raise EnvironmentContractError("environment manifest differs from exact result evidence")
        environment_identity = report.get("environment_identity")
        reported_assets = None if not isinstance(environment_identity, dict) else environment_identity.get("placed_assets")
        if not isinstance(reported_assets, list) or len(reported_assets) != len(expected_assets):
            raise EnvironmentContractError("environment result lacks exact placed asset evidence")
        observed_assets: list[PlacedAsset] = []
        for expected, evidence in zip(expected_assets, reported_assets, strict=True):
            if (
                not isinstance(evidence, dict)
                or evidence.get("artifact_ref") != expected.artifact_ref.value
                or evidence.get("content_sha256") != expected.content_sha256
                or evidence.get("asset_id") != expected.asset_id
                or evidence.get("location") != list(expected.location)
                or evidence.get("rotation_euler") != list(expected.rotation_euler)
                or evidence.get("scale") != list(expected.scale)
                or evidence.get("material_ref") != expected.material_ref
                or evidence.get("variant") != expected.variant
                or evidence.get("parent_ref") != expected.parent_ref
                or evidence.get("partition_id") != expected.partition_id
                or not isinstance(evidence.get("transform"), list)
            ):
                raise EnvironmentContractError("environment placed asset evidence differs from its exact request")
            try:
                observed_assets.append(PlacedAsset(
                    project_ref=access.project_ref, asset_id=expected.asset_id,
                    source_ref=expected.artifact_ref.value, content_sha256=expected.content_sha256,
                    transform=tuple(float(cast(str | float | int, value)) for value in cast(list[object], evidence["transform"])),
                    material_ref=expected.material_ref, variant=expected.variant,
                    parent_ref=expected.parent_ref, partition_id=expected.partition_id,
                ))
            except (TypeError, ValueError) as exc:
                raise EnvironmentContractError("environment placed asset transform is malformed") from exc
        manifest.require_placed_assets(tuple(observed_assets))
        payload = self._environment_manifest_payload(manifest)
        raw = _json(payload).encode()
        content = self.object_store.put(raw, media_type="application/vnd.biella.environment-manifest+json")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT artifact_id,artifact_revision,manifest_semantic_sha256,content_sha256 FROM three_d_environment_manifest_records WHERE project_id=? AND adapter_ref=? AND result_record_sha256=? AND environment_id=?",
                (access.project_ref.value, self.adapter_ref, result.record_sha256, manifest.specification.environment_id),
            ).fetchone()
        finally:
            connection.close()
        if row is not None:
            if not hmac.compare_digest(cast(str, row["manifest_semantic_sha256"]), content.digest):
                raise EnvironmentContractError("environment manifest finalization conflicts with durable bytes")
            artifact = self.artifacts.get_artifact(access, ArtifactRef(access.project_ref, cast(str, row["artifact_id"]), cast(int, row["artifact_revision"])))
            if artifact.content_ref is None or artifact.content_ref.digest != cast(str, row["content_sha256"]):
                raise EnvironmentContractError("environment manifest artifact identity changed")
            self.object_store.verify(artifact.content_ref)
            if self.object_store.read(artifact.content_ref) != raw:
                raise EnvironmentContractError("environment manifest artifact bytes changed")
            return self.verify_environment_manifest_publication(
                access, EnvironmentManifestPublication(manifest, artifact.artifact_ref, artifact.content_ref),
            )
        artifact = self.artifacts.create_artifact(
            access, project_ref=access.project_ref, role="3d.environment-manifest", content_ref=content,
            source_refs=(), source_artifact_refs=(output_ref, *tuple(item.artifact_ref for item in layout.placed_assets)),
            source_content_refs=(output_content,), derivation_type="3d.environment-manifest",
            metadata={"media_type": "application/vnd.biella.environment-manifest+json", "schema_ref": "schema://biella/environment-manifest/v1", "schema_version": "1.0.0", "semantic_label": "environment-manifest", "semantic_version": "1.0.0"},
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO three_d_environment_manifest_records VALUES (?,?,?,?,?,?,?,?)",
                    (access.project_ref.value, self.adapter_ref, result.record_sha256, manifest.specification.environment_id, content.digest, artifact.artifact_ref.artifact_id, artifact.artifact_ref.revision, content.digest),
                )
                connection.commit()
                return self.verify_environment_manifest_publication(
                    access, EnvironmentManifestPublication(manifest, artifact.artifact_ref, content),
                )
            except sqlite3.IntegrityError:
                connection.rollback()
                return self.finalize_environment_integration_manifest(access, request, result, manifest)
        finally:
            connection.close()

    def _verified_animation_handoff(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
    ) -> tuple[Mapping[str, object], ArtifactRef, ContentRef, ContentRef]:
        if (
            not isinstance(request, ThreeDOperationRequest)
            or not isinstance(result, ThreeDOperationResult)
            or self.reality is not ThreeDReality.REAL
            or result.reality is not ThreeDReality.REAL
            or result.status is not ThreeDStatus.SUCCEEDED
            or result.operation not in {ThreeDOperation.ANIMATE, ThreeDOperation.RETARGET, ThreeDOperation.BAKE}
            or request.operation is not result.operation
            or request.request_sha256 != result.request_sha256
            or request.identity.semantic_digest != result.identity_digest
            or request.project_ref != access.project_ref
            or result.project_ref != access.project_ref
            or not result.editable_source
            or result.preview_only
            or result.output_artifact_ref is None
            or result.output_content_ref is None
            or result.report_ref is None
            or result.process_call_ref is None
            or request.animation_clip_spec is None
            or request.skeleton_spec is None
        ):
            raise AnimationContractError("animation handoff requires one exact successful REAL editable result")
        output_ref = result.output_artifact_ref
        output_content = result.output_content_ref
        report_ref = result.report_ref
        try:
            self._authorize_project(access, result.project_ref)
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT result_json,record_sha256 FROM three_d_operation_results WHERE project_id=? AND adapter_ref=?",
                    (result.project_ref.value, self.adapter_ref),
                ).fetchall()
            finally:
                connection.close()
            persisted: ThreeDOperationResult | None = None
            for row in rows:
                candidate = self._result_from_row(row)
                if (
                    hmac.compare_digest(candidate.record_sha256, result.record_sha256)
                    and candidate.request_sha256 == result.request_sha256
                ):
                    persisted = candidate
                    break
            if persisted != result:
                raise AnimationContractError("animation result is forged, stale, or not durably persisted")
            output = self.artifacts.get_artifact(access, output_ref)
            if (
                output.content_ref is None
                or _content_payload(output.content_ref) != _content_payload(output_content)
                or output.derivation_type != f"3d.{result.operation.value.replace('_', '-')}"
            ):
                raise AnimationContractError("animation artifact identity differs from durable result")
            self.object_store.verify(output_content)
            self.object_store.verify(report_ref)
            process = self.process.get_result(
                access,
                ToolCallRef(result.project_ref, result.process_call_ref.rsplit("/", 1)[-1]),
            )
            report = self._driver_report(self.object_store.read(process.stdout_ref))
            report_bytes = _json(report).encode()
            if (
                hashlib.sha256(report_bytes).hexdigest() != report_ref.digest
                or len(report_bytes) != report_ref.size_bytes
                or process.status is not ProcessStatus.SUCCEEDED
                or process.process_identity is None
            ):
                raise AnimationContractError("animation result lacks exact successful driver evidence")
            self._verify_operation_report_schema(request, report)
            identity = report.get("animation_identity")
            if (
                not isinstance(identity, dict)
                or identity.get("clip_sha256") != request.animation_clip_spec.semantic_digest
                or identity.get("source_skeleton_sha256") != request.animation_clip_spec.source_skeleton_sha256
                or identity.get("target_skeleton_sha256") != request.skeleton_spec.semantic_digest
                or identity.get("root_motion_policy") != request.root_motion_policy.value
            ):
                raise AnimationContractError("animation report identity changed")
            return report, output_ref, output_content, report_ref
        except AnimationContractError:
            raise
        except (ArtifactError, ObjectStorageError, ProcessError, ThreeDError, ValueError) as exc:
            raise AnimationContractError("animation handoff evidence failed verification") from exc

    @staticmethod
    def _rig_identity_payload(rig: CharacterRigRef) -> dict[str, object]:
        return {
            "character_artifact_ref": rig.character_artifact_ref,
            "character_content_sha256": rig.character_content_sha256,
            "character_id": rig.character_id,
            "coordinate_convention_ref": rig.coordinate_convention_ref,
            "coordinate_system": dict(rig.coordinate_system),
            "mesh_content_sha256": rig.mesh_content_sha256,
            "mesh_ref": rig.mesh_ref,
            "project_ref": rig.project_ref.value,
            "provenance_ref": rig.provenance_ref,
            "rest_pose_ref": rig.rest_pose_ref,
            "rig_artifact_ref": rig.rig_artifact_ref,
            "rig_content_sha256": rig.rig_content_sha256,
            "rig_id": rig.rig_id,
            "scale": list(rig.scale),
            "script_provenance_ref": rig.script_provenance_ref,
            "skeleton_content_sha256": rig.skeleton_content_sha256,
            "skeleton_ref": rig.skeleton_ref,
            "target_metadata": dict(rig.target_metadata),
            "tool_provenance_ref": rig.tool_provenance_ref,
        }

    @staticmethod
    def _rig_from_payload(payload: object) -> CharacterRigRef:
        if not isinstance(payload, dict):
            raise AnimationContractError("persisted mapping rig identity is malformed")
        try:
            scale = cast(list[float], payload["scale"])
            return CharacterRigRef(
                project_ref=ProjectRef(cast(str, payload["project_ref"])),
                character_id=cast(str, payload["character_id"]),
                character_artifact_ref=cast(str, payload["character_artifact_ref"]),
                character_content_sha256=cast(str, payload["character_content_sha256"]),
                mesh_ref=cast(str, payload["mesh_ref"]),
                mesh_content_sha256=cast(str, payload["mesh_content_sha256"]),
                skeleton_ref=cast(str, payload["skeleton_ref"]),
                skeleton_content_sha256=cast(str, payload["skeleton_content_sha256"]),
                rig_id=cast(str, payload["rig_id"]),
                rig_artifact_ref=cast(str, payload["rig_artifact_ref"]),
                rig_content_sha256=cast(str, payload["rig_content_sha256"]),
                scale=(float(scale[0]), float(scale[1]), float(scale[2])),
                coordinate_system=cast(dict[str, str], payload["coordinate_system"]),
                coordinate_convention_ref=cast(str, payload["coordinate_convention_ref"]),
                rest_pose_ref=cast(str, payload["rest_pose_ref"]),
                provenance_ref=cast(str, payload["provenance_ref"]),
                tool_provenance_ref=cast(str, payload["tool_provenance_ref"]),
                script_provenance_ref=cast(str, payload["script_provenance_ref"]),
                target_metadata=cast(dict[str, str], payload["target_metadata"]),
            )
        except (CharacterContractError, KeyError, TypeError, ValueError) as exc:
            raise AnimationContractError("persisted mapping rig identity is malformed") from exc

    @classmethod
    def _mapping_payload(
        cls,
        mapping_id: str,
        mapping_version: str,
        source_rig_ref: CharacterRigRef,
        target_rig_ref: CharacterRigRef,
        mappings: tuple[BoneMapping, ...],
    ) -> dict[str, object]:
        return {
            "bone_mappings": [
                {"source_bone": item.source_bone, "target_bone": item.target_bone}
                for item in mappings
            ],
            "mapping_id": mapping_id,
            "mapping_version": mapping_version,
            "source_rig_ref": cls._rig_identity_payload(source_rig_ref),
            "target_rig_ref": cls._rig_identity_payload(target_rig_ref),
        }

    @staticmethod
    def _artifact_ref_from_value(access: ProjectAccess, value: str) -> ArtifactRef:
        prefix = f"artifact://{access.project_ref.value}/"
        if not isinstance(value, str) or not value.startswith(prefix):
            raise AnimationContractError("mapping artifact reference is malformed")
        parts = value.removeprefix(prefix).split("/")
        if len(parts) != 2 or not parts[1].isdigit():
            raise AnimationContractError("mapping artifact reference is malformed")
        try:
            return ArtifactRef(access.project_ref, parts[0], int(parts[1]))
        except (TypeError, ValueError) as exc:
            raise AnimationContractError("mapping artifact reference is malformed") from exc

    def _require_animation_rig(
        self,
        access: ProjectAccess,
        rig: CharacterRigRef,
        skeleton_digest: str,
    ) -> ArtifactRef:
        if (
            not isinstance(rig, CharacterRigRef)
            or rig.project_ref != access.project_ref
            or rig.skeleton_content_sha256 != skeleton_digest
            or not rig.rig_artifact_ref.startswith(f"artifact://{access.project_ref.value}/")
        ):
            raise AnimationContractError("character rig is stale, forged, or out of project scope")
        artifact_ref = self._artifact_ref_from_value(access, rig.rig_artifact_ref)
        try:
            artifact = self.artifacts.get_artifact(access, artifact_ref)
        except ArtifactError as exc:
            raise AnimationContractError("character rig artifact is not durable") from exc
        if artifact.content_ref is None or artifact.content_ref.digest != rig.rig_content_sha256:
            raise AnimationContractError("character rig artifact content changed")
        return artifact_ref

    def _animation_lineage_contains(
        self,
        access: ProjectAccess,
        output_ref: ArtifactRef,
        expected_ref: ArtifactRef,
        expected_digest: str,
    ) -> bool:
        pending = [output_ref]
        seen: set[ArtifactRef] = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            artifact = self.artifacts.get_artifact(access, current)
            if artifact.artifact_ref == expected_ref and artifact.content_ref is not None and artifact.content_ref.digest == expected_digest:
                return True
            pending.extend(artifact.source_artifact_refs)
            if len(seen) > 256:
                raise AnimationContractError("animation artifact lineage is unbounded")
        return False

    def _mapping_from_artifact(
        self,
        access: ProjectAccess,
        mapping_ref: str,
        content_sha256: str,
    ) -> RetargetMapping:
        artifact_ref = self._artifact_ref_from_value(access, mapping_ref)
        try:
            artifact = self.artifacts.get_artifact(access, artifact_ref)
            if (
                artifact.role != "3d.retarget-mapping"
                or artifact.derivation_type != "3d.retarget-mapping"
                or artifact.content_ref is None
                or artifact.content_ref.digest != content_sha256
            ):
                raise AnimationContractError("retarget mapping artifact identity changed")
            self.object_store.verify(artifact.content_ref)
            raw = self.object_store.read(artifact.content_ref)
            if hashlib.sha256(raw).hexdigest() != content_sha256:
                raise AnimationContractError("retarget mapping bytes changed")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict) or _json(payload).encode() != raw:
                raise AnimationContractError("retarget mapping bytes are not canonical")
            pairs = payload.get("bone_mappings")
            if not isinstance(pairs, list):
                raise AnimationContractError("retarget mapping pairs are malformed")
            mapping = RetargetMapping(
                project_ref=access.project_ref,
                mapping_id=cast(str, payload["mapping_id"]),
                mapping_version=cast(str, payload["mapping_version"]),
                source_rig_ref=self._rig_from_payload(payload["source_rig_ref"]),
                target_rig_ref=self._rig_from_payload(payload["target_rig_ref"]),
                bone_mappings=tuple(
                    BoneMapping(cast(str, item["source_bone"]), cast(str, item["target_bone"]))
                    for item in pairs
                    if isinstance(item, dict)
                ),
                mapping_ref=artifact_ref.value,
                content_sha256=artifact.content_ref.digest,
            )
            if len(mapping.bone_mappings) != len(pairs):
                raise AnimationContractError("retarget mapping pairs are malformed")
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT mapping_semantic_sha256,content_sha256 FROM three_d_retarget_mapping_records "
                    "WHERE project_id=? AND adapter_ref=? AND artifact_id=? AND artifact_revision=?",
                    (access.project_ref.value, self.adapter_ref, artifact_ref.artifact_id, artifact_ref.revision),
                ).fetchone()
            finally:
                connection.close()
            if (
                row is None
                or not hmac.compare_digest(cast(str, row["mapping_semantic_sha256"]), content_sha256)
                or not hmac.compare_digest(cast(str, row["content_sha256"]), content_sha256)
            ):
                raise AnimationContractError("retarget mapping artifact lacks durable record")
            return mapping
        except AnimationContractError:
            raise
        except (ArtifactError, ObjectStorageError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AnimationContractError("retarget mapping artifact failed verification") from exc

    def _persist_mapping_artifact(
        self,
        access: ProjectAccess,
        result: ThreeDOperationResult,
        output_ref: ArtifactRef,
        output_content: ContentRef,
        source_artifact: ArtifactRef,
        target_artifact: ArtifactRef,
        mapping_id: str,
        mapping_version: str,
        source_rig_ref: CharacterRigRef,
        target_rig_ref: CharacterRigRef,
        pairs: tuple[BoneMapping, ...],
    ) -> RetargetMapping:
        payload = self._mapping_payload(mapping_id, mapping_version, source_rig_ref, target_rig_ref, pairs)
        raw = _json(payload).encode()
        content = self.object_store.put(raw, media_type="application/vnd.biella.retarget-mapping+json")
        mapping_digest = content.digest
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT artifact_id,artifact_revision,content_sha256,mapping_semantic_sha256 FROM three_d_retarget_mapping_records "
                "WHERE project_id=? AND adapter_ref=? AND result_record_sha256=? AND mapping_id=? AND mapping_version=?",
                (access.project_ref.value, self.adapter_ref, result.record_sha256, mapping_id, mapping_version),
            ).fetchone()
        finally:
            connection.close()
        if row is not None:
            if not hmac.compare_digest(cast(str, row["mapping_semantic_sha256"]), mapping_digest):
                raise AnimationContractError("retarget mapping finalization conflicts with durable bytes")
            artifact_ref = ArtifactRef(access.project_ref, cast(str, row["artifact_id"]), cast(int, row["artifact_revision"]))
            return self._mapping_from_artifact(access, artifact_ref.value, cast(str, row["content_sha256"]))
        artifact = self.artifacts.create_artifact(
            access,
            project_ref=access.project_ref,
            role="3d.retarget-mapping",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=(output_ref, source_artifact, target_artifact),
            source_content_refs=(output_content,),
            derivation_type="3d.retarget-mapping",
            metadata={
                "media_type": "application/vnd.biella.retarget-mapping+json",
                "schema_ref": "schema://biella/retarget-mapping/v1",
                "schema_version": "1.0.0",
                "semantic_label": "retarget-mapping",
                "semantic_version": "1.0.0",
            },
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO three_d_retarget_mapping_records VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        access.project_ref.value, self.adapter_ref, result.record_sha256,
                        mapping_id, mapping_version, mapping_digest, artifact.artifact_ref.artifact_id,
                        artifact.artifact_ref.revision, content.digest,
                    ),
                )
                connection.commit()
                return self._mapping_from_artifact(access, artifact.artifact_ref.value, content.digest)
            except sqlite3.IntegrityError:
                connection.rollback()
                row = connection.execute(
                    "SELECT artifact_id,artifact_revision,content_sha256,mapping_semantic_sha256 FROM three_d_retarget_mapping_records "
                    "WHERE project_id=? AND adapter_ref=? AND result_record_sha256=? AND mapping_id=? AND mapping_version=?",
                    (access.project_ref.value, self.adapter_ref, result.record_sha256, mapping_id, mapping_version),
                ).fetchone()
                if row is None or not hmac.compare_digest(cast(str, row["mapping_semantic_sha256"]), mapping_digest):
                    raise AnimationContractError("retarget mapping persistence conflicts")
                winner = ArtifactRef(access.project_ref, cast(str, row["artifact_id"]), cast(int, row["artifact_revision"]))
                return self._mapping_from_artifact(access, winner.value, cast(str, row["content_sha256"]))
        finally:
            connection.close()

    def _retarget_request_sources(
        self,
        access: ProjectAccess,
        request: RetargetRequest,
    ) -> tuple[Artifact, ...]:
        expected = (
            (request.clip.source_artifact_ref, request.clip.content_sha256),
            (request.mapping.mapping_ref, request.mapping.content_sha256),
            (request.source_rig_ref.rig_artifact_ref, request.source_rig_ref.rig_content_sha256),
            (request.target_rig_ref.rig_artifact_ref, request.target_rig_ref.rig_content_sha256),
        )
        sources: dict[ArtifactRef, Artifact] = {}
        for value, digest in expected:
            artifact_ref = self._artifact_ref_from_value(access, value)
            try:
                artifact = self.artifacts.get_artifact(access, artifact_ref)
            except ArtifactError as exc:
                raise AnimationContractError(
                    "retarget request source Artifact is not durable"
                ) from exc
            if artifact.content_ref is None or artifact.content_ref.digest != digest:
                raise AnimationContractError(
                    "retarget request source content identity changed"
                )
            self.object_store.verify(artifact.content_ref)
            prior = sources.get(artifact_ref)
            if prior is not None and prior.content_ref != artifact.content_ref:
                raise AnimationContractError(
                    "retarget request aliases conflicting source identities"
                )
            sources[artifact_ref] = artifact
        return tuple(sorted(sources.values(), key=lambda item: item.artifact_ref.value))

    def verify_retarget_request_publication(
        self,
        access: ProjectAccess,
        publication: RetargetRequestPublication,
    ) -> RetargetRequestPublication:
        if (
            not isinstance(publication, RetargetRequestPublication)
            or publication.request.project_ref != access.project_ref
            or publication.request_artifact_ref.project_ref != access.project_ref
        ):
            raise AnimationContractError(
                "retarget request publication crossed Project scope"
            )
        request = publication.request
        try:
            artifact = self.artifacts.get_artifact(
                access, publication.request_artifact_ref
            )
            raw = request.canonical_bytes()
            if (
                artifact.role != "3d.retarget-request"
                or artifact.derivation_type != "3d.retarget-request"
                or artifact.content_ref is None
                or artifact.content_ref != publication.request_content_ref
                or artifact.content_ref.digest != request.request_sha256
                or hashlib.sha256(raw).hexdigest() != request.request_sha256
            ):
                raise AnimationContractError(
                    "retarget request Artifact identity changed"
                )
            self.object_store.verify(artifact.content_ref)
            if self.object_store.read(artifact.content_ref) != raw:
                raise AnimationContractError("retarget request canonical bytes changed")
            expected_sources = self._retarget_request_sources(access, request)
            if set(artifact.source_artifact_refs) != {
                item.artifact_ref for item in expected_sources
            }:
                raise AnimationContractError("retarget request lineage changed")
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT request_semantic_sha256,artifact_id,artifact_revision,content_sha256 "
                    "FROM three_d_retarget_request_records WHERE project_id=? AND adapter_ref=? "
                    "AND request_id=? AND request_version=?",
                    (
                        access.project_ref.value,
                        self.adapter_ref,
                        request.request_id,
                        request.request_version,
                    ),
                ).fetchone()
            finally:
                connection.close()
            if (
                row is None
                or not hmac.compare_digest(cast(str, row["request_semantic_sha256"]), request.request_sha256)
                or cast(str, row["artifact_id"]) != publication.request_artifact_ref.artifact_id
                or cast(int, row["artifact_revision"]) != publication.request_artifact_ref.revision
                or not hmac.compare_digest(cast(str, row["content_sha256"]), request.request_sha256)
            ):
                raise AnimationContractError(
                    "retarget request Artifact lacks its immutable durable record"
                )
            return publication
        except AnimationContractError:
            raise
        except (ArtifactError, ObjectStorageError, TypeError, ValueError) as exc:
            raise AnimationContractError(
                "retarget request publication failed verification"
            ) from exc

    def _retarget_request_publication_from_row(
        self,
        access: ProjectAccess,
        request: RetargetRequest,
        row: sqlite3.Row,
    ) -> RetargetRequestPublication:
        artifact_ref = ArtifactRef(
            access.project_ref,
            cast(str, row["artifact_id"]),
            cast(int, row["artifact_revision"]),
        )
        try:
            artifact = self.artifacts.get_artifact(access, artifact_ref)
        except ArtifactError as exc:
            raise AnimationContractError(
                "retarget request durable Artifact is unavailable"
            ) from exc
        if artifact.content_ref is None:
            raise AnimationContractError("retarget request durable content is unavailable")
        return self.verify_retarget_request_publication(
            access,
            RetargetRequestPublication(request, artifact_ref, artifact.content_ref),
        )

    def persist_retarget_request(
        self,
        access: ProjectAccess,
        request: RetargetRequest,
    ) -> RetargetRequestPublication:
        if not isinstance(request, RetargetRequest) or request.project_ref != access.project_ref:
            raise AnimationContractError(
                "retarget request persistence requires one exact Project request"
            )
        raw = request.canonical_bytes()
        if hashlib.sha256(raw).hexdigest() != request.request_sha256:
            raise AnimationContractError("retarget request semantic identity changed")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT request_semantic_sha256,artifact_id,artifact_revision,content_sha256 "
                "FROM three_d_retarget_request_records WHERE project_id=? AND adapter_ref=? "
                "AND request_id=? AND request_version=?",
                (access.project_ref.value, self.adapter_ref, request.request_id, request.request_version),
            ).fetchone()
        finally:
            connection.close()
        if row is not None:
            if not hmac.compare_digest(cast(str, row["request_semantic_sha256"]), request.request_sha256):
                raise AnimationContractError(
                    "retarget request ID and version conflict with durable bytes"
                )
            return self._retarget_request_publication_from_row(access, request, row)
        sources = self._retarget_request_sources(access, request)
        content = self.object_store.put(
            raw, media_type="application/vnd.biella.retarget-request+json"
        )
        if content.digest != request.request_sha256:
            raise AnimationContractError("retarget request storage identity changed")
        artifact = self.artifacts.create_artifact(
            access,
            project_ref=access.project_ref,
            role="3d.retarget-request",
            content_ref=content,
            source_refs=(),
            source_artifact_refs=tuple(item.artifact_ref for item in sources),
            source_content_refs=tuple(cast(ContentRef, item.content_ref) for item in sources),
            derivation_type="3d.retarget-request",
            metadata={
                "media_type": "application/vnd.biella.retarget-request+json",
                "schema_ref": "schema://biella/retarget-request/v1",
                "schema_version": "1.0.0",
                "semantic_label": "retarget-request",
                "semantic_version": request.request_version,
            },
        )
        winner: sqlite3.Row | None = None
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO three_d_retarget_request_records VALUES (?,?,?,?,?,?,?,?)",
                    (
                        access.project_ref.value,
                        self.adapter_ref,
                        request.request_id,
                        request.request_version,
                        request.request_sha256,
                        artifact.artifact_ref.artifact_id,
                        artifact.artifact_ref.revision,
                        content.digest,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError:
                connection.rollback()
                winner = connection.execute(
                    "SELECT request_semantic_sha256,artifact_id,artifact_revision,content_sha256 "
                    "FROM three_d_retarget_request_records WHERE project_id=? AND adapter_ref=? "
                    "AND request_id=? AND request_version=?",
                    (access.project_ref.value, self.adapter_ref, request.request_id, request.request_version),
                ).fetchone()
                if (
                    winner is None
                    or not hmac.compare_digest(
                        cast(str, winner["request_semantic_sha256"]), request.request_sha256
                    )
                ):
                    raise AnimationContractError(
                        "retarget request persistence conflicts"
                    )
        finally:
            connection.close()
        if winner is not None:
            return self._retarget_request_publication_from_row(access, request, winner)
        return self.verify_retarget_request_publication(
            access,
            RetargetRequestPublication(request, artifact.artifact_ref, content),
        )

    def finalize_retarget_mapping(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        source_rig_ref: CharacterRigRef,
        target_rig_ref: CharacterRigRef,
        *,
        mapping_id: str,
        mapping_version: str,
    ) -> RetargetMapping:
        report, output_ref, output_content, _ = self._verified_animation_handoff(access, request, result)
        if request.operation is not ThreeDOperation.RETARGET or request.retarget_spec is None:
            raise AnimationContractError("retarget mapping requires an exact RETARGET request")
        assert request.skeleton_spec is not None
        source_artifact = self._require_animation_rig(access, source_rig_ref, request.retarget_spec.source_skeleton_spec.semantic_digest)
        target_artifact = self._require_animation_rig(access, target_rig_ref, request.skeleton_spec.semantic_digest)
        if not self._animation_lineage_contains(access, output_ref, source_artifact, source_rig_ref.rig_content_sha256):
            raise AnimationContractError("retarget result lineage does not contain its exact source rig")
        identity = report.get("animation_identity")
        if not isinstance(identity, dict) or identity.get("retarget_sha256") != request.retarget_spec.semantic_digest:
            raise AnimationContractError("retarget mapping report identity changed")
        try:
            return self._persist_mapping_artifact(
                access, result, output_ref, output_content, source_artifact, target_artifact,
                mapping_id, mapping_version, source_rig_ref, target_rig_ref,
                tuple(BoneMapping(item.source_bone_name, item.target_bone_name) for item in request.retarget_spec.mappings),
            )
        except AnimationContractError:
            raise
        except (TypeError, ValueError) as exc:
            raise AnimationContractError("retarget mapping finalization is malformed") from exc

    def finalize_animation_clip(
        self,
        access: ProjectAccess,
        request: ThreeDOperationRequest,
        result: ThreeDOperationResult,
        character_rig_ref: CharacterRigRef,
        *,
        clip_id: str,
        mapping: RetargetMapping | None = None,
    ) -> AnimationClip:
        report, output_ref, output_content, report_ref = self._verified_animation_handoff(access, request, result)
        assert request.animation_clip_spec is not None
        assert request.skeleton_spec is not None
        rig_artifact = self._require_animation_rig(access, character_rig_ref, request.skeleton_spec.semantic_digest)
        if request.operation is ThreeDOperation.RETARGET:
            resolved = (
                self._mapping_from_artifact(access, mapping.mapping_ref, mapping.content_sha256)
                if isinstance(mapping, RetargetMapping)
                else None
            )
            if (
                not isinstance(mapping, RetargetMapping)
                or resolved != mapping
                or request.retarget_spec is None
                or mapping.project_ref != access.project_ref
                or mapping.source_rig_ref.skeleton_content_sha256 != request.retarget_spec.source_skeleton_spec.semantic_digest
                or mapping.target_rig_ref != character_rig_ref
                or tuple((item.source_bone, item.target_bone) for item in mapping.bone_mappings)
                != tuple((item.source_bone_name, item.target_bone_name) for item in request.retarget_spec.mappings)
            ):
                raise AnimationContractError("retarget animation clip requires its exact finalized mapping")
        elif mapping is not None and mapping.target_rig_ref != character_rig_ref:
            raise AnimationContractError("animation mapping is stale or mismatched")
        if request.operation is not ThreeDOperation.RETARGET and not self._animation_lineage_contains(access, output_ref, rig_artifact, character_rig_ref.rig_content_sha256):
            raise AnimationContractError("animation result lineage does not contain its exact character rig")
        inspection = report.get("inspection")
        if not isinstance(inspection, dict):
            raise AnimationContractError("animation report inspection is malformed")
        animation = inspection.get("animation")
        if not isinstance(animation, dict) or not isinstance(animation.get("actions"), list):
            raise AnimationContractError("animation report lacks action inspection")
        action = next(
            (item for item in animation["actions"] if isinstance(item, dict) and item.get("clip_sha256") == request.animation_clip_spec.semantic_digest),
            None,
        )
        frame_rate = animation.get("frame_rate")
        if (
            not isinstance(action, dict)
            or isinstance(frame_rate, bool)
            or not isinstance(frame_rate, (int, float))
            or not math.isfinite(float(frame_rate))
            or float(frame_rate) <= 0.0
            or any(not isinstance(action.get(name), (int, float)) for name in ("start_frame", "end_frame", "fcurve_count", "keyframe_count", "loop_error"))
        ):
            raise AnimationContractError("animation timing or channel inspection is malformed")
        start_frame = float(cast(float | int, action["start_frame"]))
        end_frame = float(cast(float | int, action["end_frame"]))
        if not end_frame > start_frame:
            raise AnimationContractError("animation action timing is stale or empty")
        start_time = start_frame / float(frame_rate)
        end_time = end_frame / float(frame_rate)
        try:
            return AnimationClip(
                project_ref=access.project_ref,
                clip_id=clip_id,
                source_artifact_ref=output_ref.value,
                content_sha256=output_content.digest,
                character_rig_ref=character_rig_ref,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=end_time - start_time,
                frame_rate=float(frame_rate),
                time_unit="seconds",
                channel_summary={"fcurves": int(cast(int | float, action["fcurve_count"])), "keyframes": int(cast(int | float, action["keyframe_count"]))},
                root_motion_metadata={"policy": request.root_motion_policy.value},
                loop_metadata={"loop_error": str(action["loop_error"]), "tolerance": str(request.animation_clip_spec.loop_tolerance)},
                coordinate_system={"skeleton": request.skeleton_spec.coordinate_system},
                coordinate_convention_ref=character_rig_ref.coordinate_convention_ref,
                tool_provenance_ref=f"tool-provenance://three-d/{result.identity_digest}",
                runtime_ref=f"runtime://three-d/{result.identity_digest}",
                content_ref=f"content://sha256/{output_content.digest}",
            )
        except AnimationContractError:
            raise
        except (TypeError, ValueError) as exc:
            raise AnimationContractError("animation clip finalization is malformed") from exc

    def describe_reference(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        *,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        idempotency_key: str,
    ) -> ThreeDRuntimeDescription:
        relative, _ = self._authorize_runtime(
            access,
            attempt,
            identity,
            control_root_ref,
            working_directory,
        )
        _, prior = self._runtime_claim(
            access,
            attempt,
            identity,
            control_root_ref,
            relative,
            None,
            idempotency_key,
        )
        if prior is not None:
            return prior
        description = ThreeDRuntimeDescription(
            project_ref=identity.project_ref,
            identity_digest=identity.semantic_digest,
            adapter_ref=self.adapter_ref,
            reality=ThreeDReality.REFERENCE,
            available=True,
            tool_name=identity.tool_name,
            tool_version=identity.tool_version,
            executable_sha256=identity.executable_sha256,
            driver_sha256=identity.driver_sha256,
            embedded_python_version=None,
            network_enforcement="NOT_APPLICABLE",
            plugin_identities=identity.plugins,
            runtime_ref=identity.runtime_ref,
            resource_allocation_ref=None,
            process_call_ref=None,
            unavailability_ref=None,
            unavailable_reason=None,
            observed_at=self._now(),
        )
        return self._persist_runtime(
            access,
            attempt,
            identity,
            control_root_ref,
            relative,
            description,
            idempotency_key,
        )

    def describe_blender(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        identity: ThreeDToolIdentity,
        *,
        control_root_ref: FilesystemRootRef,
        working_directory: str,
        idempotency_key: str,
    ) -> ThreeDRuntimeDescription:
        relative, allocation_ref = self._authorize_runtime(
            access,
            attempt,
            identity,
            control_root_ref,
            working_directory,
        )
        _, prior = self._runtime_claim(
            access,
            attempt,
            identity,
            control_root_ref,
            relative,
            allocation_ref,
            idempotency_key,
        )
        if prior is not None:
            return prior
        if allocation_ref is None:
            raise ThreeDAuthorityError(
                "REAL Blender runtime probe requires one exact active allocation"
            )
        runtime_semantic = self._runtime_semantic(
            identity,
            control_root_ref,
            relative,
            allocation_ref,
        )
        runtime_execution_sha = self._runtime_execution_sha(
            runtime_semantic,
            idempotency_key,
        )
        process_key = self._runtime_process_key(runtime_execution_sha)
        process_state = self._runtime_process_state(
            attempt,
            identity,
            process_key,
            None,
        )
        staged_driver_path: Path | None = None
        if process_state == "ABSENT":
            if (
                identity.sandbox_launcher_path is None
                or identity.sandbox_launcher_sha256 is None
            ):
                raise ThreeDContractError(
                    "REAL Blender runtime requires exact bubblewrap identity"
                )
            executable = Path(identity.executable_path)
            launcher = Path(identity.sandbox_launcher_path)
            if not executable.is_file() or not launcher.is_file():
                reason = (
                    "exact Blender executable is unavailable"
                    if not executable.is_file()
                    else "exact bubblewrap sandbox launcher is unavailable"
                )
                unavailability_ref = self.object_store.put(
                    _json(
                        self._runtime_unavailability_report(
                            identity,
                            control_root_ref,
                            relative,
                            allocation_ref,
                            reason,
                        )
                    ).encode(),
                    media_type=(
                        "application/vnd.biella.3d-unavailability+json"
                    ),
                )
                description = ThreeDRuntimeDescription(
                    project_ref=identity.project_ref,
                    identity_digest=identity.semantic_digest,
                    adapter_ref=self.adapter_ref,
                    reality=ThreeDReality.NOT_RUN,
                    available=False,
                    tool_name=identity.tool_name,
                    tool_version=identity.tool_version,
                    executable_sha256=identity.executable_sha256,
                    driver_sha256=identity.driver_sha256,
                    embedded_python_version=None,
                    network_enforcement="NOT_RUN",
                    plugin_identities=identity.plugins,
                    runtime_ref=identity.runtime_ref,
                    resource_allocation_ref=allocation_ref,
                    process_call_ref=None,
                    unavailability_ref=unavailability_ref,
                    unavailable_reason=reason,
                    observed_at=self._now(),
                )
                return self._persist_runtime(
                    access,
                    attempt,
                    identity,
                    control_root_ref,
                    relative,
                    description,
                    idempotency_key,
                )
            if str(executable.resolve(strict=True)) != (
                identity.executable_path
            ) or str(launcher.resolve(strict=True)) != (
                identity.sandbox_launcher_path
            ):
                raise ThreeDIntegrityError(
                    "REAL Blender or sandbox launcher path is not canonical"
                )
            self._authorize_observed_tool(access, allocation_ref, identity)
            if (
                not hmac.compare_digest(
                    _file_sha256(executable),
                    identity.executable_sha256,
                )
                or not hmac.compare_digest(
                    _file_sha256(self._DRIVER),
                    identity.driver_sha256,
                )
                or not hmac.compare_digest(
                    _file_sha256(launcher),
                    identity.sandbox_launcher_sha256,
                )
            ):
                raise ThreeDIntegrityError(
                    "Blender, sandbox launcher, or fixed driver identity changed"
                )
            staged_driver_path, driver_ref, _ = self._stage_driver(
                access,
                attempt,
                identity,
                control_root_ref,
                relative,
            )
            runtime_request_ref = self._runtime_request_content(
                identity,
                runtime_semantic,
                runtime_execution_sha,
            )
            written = self.filesystem.write(
                access,
                attempt,
                root_ref=control_root_ref,
                path=self._runtime_request_path(
                    relative,
                    runtime_execution_sha,
                ),
                content_ref=runtime_request_ref,
                idempotency_key=self._runtime_request_key(
                    runtime_execution_sha
                ),
                mode=0o600,
            )
            if written.output_ref != runtime_request_ref:
                raise ThreeDIntegrityError(
                    "staged Blender runtime probe identity changed"
                )
            self._restore_staged_control_file(
                access,
                control_root_ref,
                self._runtime_request_path(
                    relative,
                    runtime_execution_sha,
                ),
                runtime_request_ref,
                mode=0o600,
            )
        else:
            driver_ref, _ = self._staged_driver_evidence(
                access,
                attempt,
                identity,
                control_root_ref,
                relative,
            )
            runtime_request_ref = self._staged_runtime_request_evidence(
                access,
                attempt,
                identity,
                control_root_ref,
                relative,
                runtime_semantic,
                runtime_execution_sha,
            )
        (
            process_request,
            _,
            driver_path,
            expected_execution_sha,
        ) = self._runtime_process_request(
            access,
            identity,
            control_root_ref,
            relative,
            allocation_ref,
            idempotency_key,
            driver_ref,
            runtime_request_ref,
        )
        if (
            expected_execution_sha != runtime_execution_sha
            or (
                process_state == "ABSENT"
                and (
                    staged_driver_path is None
                    or staged_driver_path != driver_path
                )
            )
        ):
            raise ThreeDIntegrityError(
                "Blender runtime execution identity changed"
            )
        process_state = self._runtime_process_state(
            attempt,
            identity,
            process_key,
            process_request,
        )
        process = self.process.execute(
            access,
            attempt,
            process_request,
            idempotency_key=process_key,
        )
        description = self._runtime_description_from_process(
            access,
            attempt,
            identity,
            allocation_ref,
            process_key,
            process_request,
            driver_path,
            driver_ref,
            runtime_request_ref,
            process,
        )
        return self._persist_runtime(
            access,
            attempt,
            identity,
            control_root_ref,
            relative,
            description,
            idempotency_key,
        )
