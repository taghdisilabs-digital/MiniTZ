"""Provider-neutral, fail-closed image production contracts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

from .capability import Capability, CapabilityRef
from .production_pack import (
    GraphRecipeRegistration,
    GraphRecipeStepRegistration,
    ProductionPack,
    ProductionPackRef,
    ValidatorRegistration,
)
from .project import ProjectRef

if TYPE_CHECKING:
    from .execution import NodeExecutionAttempt
    from .project import ProjectAccess


IMAGE_CAPABILITIES = (
    "inspect", "generate", "edit", "inpaint", "outpaint", "mask", "compose",
    "crop", "resize", "convert", "enhance", "upscale", "color", "channel",
    "texture", "texture_pack", "thumbnail", "validate",
)
IMAGE_ARTIFACT_ROLES = (
    "image.source", "image.prompt", "image.generated", "image.edited", "image.mask", "image.layer",
    "image.composite", "image.texture", "image.normal", "image.roughness", "image.metallic",
    "image.ao", "image.displacement", "image.alpha", "image.packed", "image.preview",
    "image.validation-evidence",
)
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")
_ROLE = re.compile(r"[a-z][a-z0-9_.-]{0,63}")


class ImageContractError(ValueError):
    """The provider-neutral image contract is malformed or incompatible."""


def _ref(value: object, field: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ImageContractError(f"{field} is invalid")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ImageContractError(f"{field} is invalid")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ImageContractError(f"{field} is invalid")
    return value


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ImageContractError(f"{field} is invalid")
    return value


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ImageContractError(f"{field} is not finite")
    return float(value)


def _mapping(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ImageContractError(f"{field} is invalid")
    copied: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise ImageContractError(f"{field} is invalid")
        if item.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
            raise ImageContractError(f"{field} is not finite")
        copied[key] = item
    return MappingProxyType(dict(sorted(copied.items())))


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _attempt(value: object, fence: object) -> tuple[str, int]:
    if not isinstance(value, str) or _ATTEMPT.fullmatch(value) is None or not isinstance(fence, int) or isinstance(fence, bool) or fence < 1:
        raise ImageContractError("producer attempt/fence is invalid")
    return value, fence


def _project_artifact_ref(project_ref: ProjectRef, value: object, field: str) -> str:
    checked = _ref(value, field)
    if not checked.startswith(f"artifact://{project_ref.value}/"):
        raise ImageContractError(f"{field} crossed Project scope")
    return checked


@dataclass(frozen=True)
class ImageArtifactContentRef:
    """Exact Project-scoped Artifact and Content identity."""

    project_ref: ProjectRef
    artifact_ref: str
    content_ref: str
    content_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef):
            raise ImageContractError("artifact project is invalid")
        _ref(self.artifact_ref, "artifact_ref")
        _ref(self.content_ref, "content_ref")
        _sha(self.content_sha256, "content_sha256")

    def payload(self) -> dict[str, str]:
        return {"artifact_ref": self.artifact_ref, "content_ref": self.content_ref, "content_sha256": self.content_sha256}


@dataclass(frozen=True)
class ImageOperation:
    operation: str
    recipe_ref: str
    recipe_sha256: str
    parameters: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.operation not in IMAGE_CAPABILITIES:
            raise ImageContractError("image operation is unsupported")
        _ref(self.recipe_ref, "recipe_ref")
        _sha(self.recipe_sha256, "recipe_sha256")
        object.__setattr__(self, "parameters", _mapping(self.parameters, "operation parameters"))

    @property
    def generative(self) -> bool:
        return self.operation in {"generate", "inpaint", "outpaint"}

    def payload(self) -> dict[str, object]:
        return {"operation": self.operation, "recipe_ref": self.recipe_ref, "recipe_sha256": self.recipe_sha256, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class ImageInspectionRef:
    project_ref: ProjectRef
    source: ImageArtifactContentRef
    width: int
    height: int
    format: str
    channels: tuple[str, ...]
    bit_depth: int
    profile_ref: str
    alpha_mode: str
    validator_ref: str
    inspection_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, source: ImageArtifactContentRef, width: int, height: int, format: str, channels: Sequence[str], bit_depth: int, profile_ref: str, alpha_mode: str, validator_ref: str) -> "ImageInspectionRef":
        payload = cls._payload(project_ref, source, width, height, format, channels, bit_depth, profile_ref, alpha_mode, validator_ref)
        return cls(project_ref, source, width, height, format, tuple(channels), bit_depth, profile_ref, alpha_mode, validator_ref, _digest(payload))

    @staticmethod
    def _payload(project_ref: ProjectRef, source: ImageArtifactContentRef, width: int, height: int, format: str, channels: Sequence[str], bit_depth: int, profile_ref: str, alpha_mode: str, validator_ref: str) -> dict[str, object]:
        if not isinstance(project_ref, ProjectRef) or not isinstance(source, ImageArtifactContentRef) or source.project_ref != project_ref:
            raise ImageContractError("inspection project/source is incompatible")
        return {"project_ref": project_ref.value, "source": source.payload(), "width": _positive_int(width, "width"), "height": _positive_int(height, "height"), "format": _text(format, "format"), "channels": _channels(channels), "bit_depth": _positive_int(bit_depth, "bit_depth"), "profile_ref": _ref(profile_ref, "profile_ref"), "alpha_mode": _text(alpha_mode, "alpha_mode"), "validator_ref": _ref(validator_ref, "validator_ref")}

    def __post_init__(self) -> None:
        if self.inspection_digest != _digest(self._payload(self.project_ref, self.source, self.width, self.height, self.format, self.channels, self.bit_depth, self.profile_ref, self.alpha_mode, self.validator_ref)):
            raise ImageContractError("inspection_digest does not match exact inspection")


def _channels(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ImageContractError("channels are invalid")
    channels = tuple(value)
    if not channels or len(channels) > 32 or len(set(channels)) != len(channels) or not all(isinstance(item, str) and item for item in channels):
        raise ImageContractError("channels are invalid")
    return channels


@dataclass(frozen=True)
class ImageSpecification:
    project_ref: ProjectRef
    image_id: str
    sources: tuple[ImageArtifactContentRef, ...]
    references: tuple[ImageArtifactContentRef, ...]
    operation: ImageOperation
    width: int
    height: int
    format: str
    channels: tuple[str, ...]
    bit_depth: int
    profile_ref: str
    alpha_mode: str
    metadata_policy: Mapping[str, str]
    model_ref: str
    model_version: str
    runtime_ref: str
    seed: int
    config: Mapping[str, str]
    prompt_artifact_ref: str | None
    prompt_content_ref: str | None
    prompt_content_sha256: str | None
    validator_ref: str
    output_contract: Mapping[str, str]
    canonical_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, image_id: str, sources: Sequence[ImageArtifactContentRef], references: Sequence[ImageArtifactContentRef], operation: ImageOperation, width: int, height: int, format: str, channels: Sequence[str], bit_depth: int, profile_ref: str, alpha_mode: str, metadata_policy: Mapping[str, str], model_ref: str, model_version: str, runtime_ref: str, seed: int, config: Mapping[str, str], prompt_artifact_ref: str | None, prompt_content_ref: str | None, prompt_content_sha256: str | None, validator_ref: str, output_contract: Mapping[str, str]) -> "ImageSpecification":
        payload = cls._payload(project_ref, image_id, sources, references, operation, width, height, format, channels, bit_depth, profile_ref, alpha_mode, metadata_policy, model_ref, model_version, runtime_ref, seed, config, prompt_artifact_ref, prompt_content_ref, prompt_content_sha256, validator_ref, output_contract)
        return cls(project_ref, image_id, tuple(sources), tuple(references), operation, width, height, format, tuple(channels), bit_depth, profile_ref, alpha_mode, metadata_policy, model_ref, model_version, runtime_ref, seed, config, prompt_artifact_ref, prompt_content_ref, prompt_content_sha256, validator_ref, output_contract, _digest(payload))

    @staticmethod
    def _payload(project_ref: ProjectRef, image_id: str, sources: Sequence[ImageArtifactContentRef], references: Sequence[ImageArtifactContentRef], operation: ImageOperation, width: int, height: int, format: str, channels: Sequence[str], bit_depth: int, profile_ref: str, alpha_mode: str, metadata_policy: Mapping[str, str], model_ref: str, model_version: str, runtime_ref: str, seed: int, config: Mapping[str, str], prompt_artifact_ref: str | None, prompt_content_ref: str | None, prompt_content_sha256: str | None, validator_ref: str, output_contract: Mapping[str, str]) -> dict[str, object]:
        if not isinstance(project_ref, ProjectRef) or not isinstance(image_id, str) or not image_id:
            raise ImageContractError("project/image identity is invalid")
        source_values, reference_values = tuple(sources), tuple(references)
        if not source_values or not all(isinstance(item, ImageArtifactContentRef) and item.project_ref == project_ref for item in (*source_values, *reference_values)):
            raise ImageContractError("source/reference project is incompatible")
        if not isinstance(operation, ImageOperation):
            raise ImageContractError("operation is invalid")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise ImageContractError("seed is invalid")
        prompt = None
        if prompt_artifact_ref is not None or prompt_content_ref is not None or prompt_content_sha256 is not None:
            if prompt_artifact_ref is None or prompt_content_ref is None or prompt_content_sha256 is None:
                raise ImageContractError("prompt identity is incomplete")
            prompt = {"artifact_ref": _project_artifact_ref(project_ref, prompt_artifact_ref, "prompt_artifact_ref"), "content_ref": _ref(prompt_content_ref, "prompt_content_ref"), "content_sha256": _sha(prompt_content_sha256, "prompt_content_sha256")}
        if operation.generative and prompt is None:
            raise ImageContractError("generative operation requires prompt ContentRef")
        return {"project_ref": project_ref.value, "image_id": image_id, "sources": [item.payload() for item in source_values], "references": [item.payload() for item in reference_values], "operation": operation.payload(), "width": _positive_int(width, "width"), "height": _positive_int(height, "height"), "format": _text(format, "format"), "channels": _channels(channels), "bit_depth": _positive_int(bit_depth, "bit_depth"), "profile_ref": _ref(profile_ref, "profile_ref"), "alpha_mode": _text(alpha_mode, "alpha_mode"), "metadata_policy": dict(_mapping(metadata_policy, "metadata_policy")), "model_ref": _ref(model_ref, "model_ref"), "model_version": _text(model_version, "model_version"), "runtime_ref": _ref(runtime_ref, "runtime_ref"), "seed": seed, "config": dict(_mapping(config, "config")), "prompt": prompt, "validator_ref": _ref(validator_ref, "validator_ref"), "output_contract": dict(_mapping(output_contract, "output_contract"))}

    def __post_init__(self) -> None:
        payload = self._payload(self.project_ref, self.image_id, self.sources, self.references, self.operation, self.width, self.height, self.format, self.channels, self.bit_depth, self.profile_ref, self.alpha_mode, self.metadata_policy, self.model_ref, self.model_version, self.runtime_ref, self.seed, self.config, self.prompt_artifact_ref, self.prompt_content_ref, self.prompt_content_sha256, self.validator_ref, self.output_contract)
        if _sha(self.canonical_digest, "canonical_digest") != _digest(payload):
            raise ImageContractError("canonical_digest does not match exact image specification")
        for field in ("metadata_policy", "config", "output_contract"):
            object.__setattr__(self, field, _mapping(getattr(self, field), field))
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "references", tuple(self.references))
        object.__setattr__(self, "channels", _channels(self.channels))


@dataclass(frozen=True)
class ImageOutputRef:
    project_ref: ProjectRef
    specification_digest: str
    output: ImageArtifactContentRef
    producer_attempt_id: str
    producer_fence: int
    derivation: str
    output_digest: str

    @classmethod
    def create(cls, project_ref: ProjectRef, specification: ImageSpecification, output: ImageArtifactContentRef, producer_attempt_id: str, producer_fence: int, derivation: str) -> "ImageOutputRef":
        if not isinstance(specification, ImageSpecification) or specification.project_ref != project_ref or not isinstance(output, ImageArtifactContentRef) or output.project_ref != project_ref:
            raise ImageContractError("output project/specification is incompatible")
        attempt, fence = _attempt(producer_attempt_id, producer_fence)
        checked_derivation = _text(derivation, "derivation")
        payload = {"project_ref": project_ref.value, "specification_digest": specification.canonical_digest, "output": output.payload(), "producer_attempt_id": attempt, "producer_fence": fence, "derivation": checked_derivation}
        return cls(project_ref, specification.canonical_digest, output, attempt, fence, checked_derivation, _digest(payload))

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.output, ImageArtifactContentRef) or self.output.project_ref != self.project_ref:
            raise ImageContractError("output project is incompatible")
        attempt, fence = _attempt(self.producer_attempt_id, self.producer_fence)
        payload = {"project_ref": self.project_ref.value, "specification_digest": _sha(self.specification_digest, "specification_digest"), "output": self.output.payload(), "producer_attempt_id": attempt, "producer_fence": fence, "derivation": _text(self.derivation, "derivation")}
        if _sha(self.output_digest, "output_digest") != _digest(payload):
            raise ImageContractError("output_digest does not match exact output")


@dataclass(frozen=True)
class ChannelPacking:
    packing_id: str
    channels: Mapping[str, str]

    def __post_init__(self) -> None:
        _text(self.packing_id, "packing_id")
        values = _mapping(self.channels, "packing")
        if not values or len(set(values.values())) != len(values):
            raise ImageContractError("packing channels are duplicated or empty")
        object.__setattr__(self, "channels", values)


@dataclass(frozen=True)
class NormalConvention:
    space: str
    convention: str

    def __post_init__(self) -> None:
        _text(self.space, "normal space")
        _text(self.convention, "normal convention")


@dataclass(frozen=True)
class TextureSpecification:
    project_ref: ProjectRef
    image_specification: ImageSpecification
    representation_tags: tuple[str, ...]
    packing: ChannelPacking
    normal_convention: NormalConvention
    output_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.image_specification, ImageSpecification) or self.image_specification.project_ref != self.project_ref:
            raise ImageContractError("texture project/specification is incompatible")
        if not isinstance(self.packing, ChannelPacking) or not isinstance(self.normal_convention, NormalConvention):
            raise ImageContractError("texture convention is invalid")
        tags = tuple(self.representation_tags)
        roles = tuple(self.output_roles)
        if not tags or not all(isinstance(item, str) and item for item in tags) or not roles or not all(isinstance(item, str) and _ROLE.fullmatch(item) for item in roles):
            raise ImageContractError("texture tags or output roles are invalid")
        object.__setattr__(self, "representation_tags", tags)
        object.__setattr__(self, "output_roles", roles)


@dataclass(frozen=True)
class TextureMaterialBinding:
    project_ref: ProjectRef
    texture_specification: TextureSpecification
    material: ImageArtifactContentRef
    texture_roles: Mapping[str, str]
    semantics: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.project_ref, ProjectRef) or not isinstance(self.texture_specification, TextureSpecification) or not isinstance(self.material, ImageArtifactContentRef) or self.texture_specification.project_ref != self.project_ref or self.material.project_ref != self.project_ref:
            raise ImageContractError("material binding project is incompatible")
        roles, semantics = _mapping(self.texture_roles, "texture_roles"), _mapping(self.semantics, "semantics")
        if not roles or set(roles) != set(semantics) or any(value not in {"color", "data"} for value in semantics.values()):
            raise ImageContractError("material binding color/data semantics are invalid")
        object.__setattr__(self, "texture_roles", roles)
        object.__setattr__(self, "semantics", semantics)


class ImageToolAdapter(Protocol):
    project_ref: ProjectRef
    tool_ref: str
    runtime_ref: str
    determinism: str

    def inspect(self, source: ImageArtifactContentRef, validator_ref: str) -> ImageInspectionRef: ...
    def execute(self, specification: ImageSpecification, producer_attempt_id: str, producer_fence: int) -> ImageOutputRef: ...


class ImageModelAdapter(Protocol):
    project_ref: ProjectRef
    model_ref: str
    runtime_ref: str
    determinism: str

    def generate(self, access: "ProjectAccess", attempt: "NodeExecutionAttempt", specification: ImageSpecification) -> ImageOutputRef: ...


def image_production_pack() -> ProductionPack:
    capabilities = tuple(Capability(CapabilityRef(f"image.{name}", "1.0.0"), f"Bounded image {name}", {}, {"result": f"minitz://contracts/image-{name}/v1"}, (), "2026-09-01T00:00:00+00:00") for name in IMAGE_CAPABILITIES)
    refs = {capability.name: capability.capability_ref for capability in capabilities}
    steps = tuple(GraphRecipeStepRegistration(name, refs[name], () if index == 0 else (IMAGE_CAPABILITIES[index - 1],)) for index, name in enumerate(IMAGE_CAPABILITIES))
    return ProductionPack(ProductionPackRef("image", "1.0.0"), capabilities, (GraphRecipeRegistration("pack-recipe://image/production@1.0.0", steps),), tuple(ValidatorRegistration(f"pack-validator://image/{name}@1.0.0", refs[name], f"validation-check://artifact-role/{IMAGE_ARTIFACT_ROLES[index % len(IMAGE_ARTIFACT_ROLES)]}/v1") for index, name in enumerate(IMAGE_CAPABILITIES)), IMAGE_ARTIFACT_ROLES, {capability.capability_ref.value: ("adapter://image/provider-neutral/v1",) for capability in capabilities}, {capability.capability_ref.value: "resource-profile://image/project-configured/v1" for capability in capabilities}, "2026-09-01T00:00:00+00:00")
