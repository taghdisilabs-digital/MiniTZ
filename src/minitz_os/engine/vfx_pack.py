from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Protocol, TypeAlias, cast

from .capability import Capability, CapabilityRef
from .production_pack import GraphRecipeRegistration, GraphRecipeStepRegistration, ProductionPack, ProductionPackRef, ValidatorRegistration
from .project import ProjectRef

_NAMES = ("inspect", "particles", "smoke", "fire", "fluid", "cloth", "hair", "rigidbody", "softbody", "destruction", "volumetric", "procedural", "simulate", "bake", "resume", "export", "preview", "validate", "composite_prepare")
_ROLES = ("vfx.simulation", "vfx.cache", "vfx.checkpoint", "vfx.bake", "vfx.export", "vfx.preview", "vfx.validation")
_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"natt_[0-9a-f]{32}")


class SimulationContractError(ValueError):
    pass


def _ref(value: object, name: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise SimulationContractError(f"{name} is invalid")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise SimulationContractError(f"{name} is invalid")
    return value


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationContractError(f"{name} is invalid")
    number = float(value)
    if not math.isfinite(number):
        raise SimulationContractError(f"{name} is not finite")
    return number


def _map(value: object, name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise SimulationContractError(f"{name} is invalid")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str):
            raise SimulationContractError(f"{name} is invalid")
        result[key] = item
    return MappingProxyType(dict(sorted(result.items())))


def _refs(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SimulationContractError(f"{name} is invalid")
    return tuple(_ref(item, name) for item in value)


def _shas(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SimulationContractError(f"{name} is invalid")
    return tuple(_sha(item, name) for item in value)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _attempt(value: object, fence: object, name: str) -> tuple[str, int]:
    if not isinstance(value, str) or _ATTEMPT.fullmatch(value) is None or not isinstance(fence, int) or isinstance(fence, bool) or fence < 1:
        raise SimulationContractError(f"{name} producer authority is invalid")
    return value, fence


class SimulationAdapter(Protocol):
    project_ref: ProjectRef
    tool_ref: str
    runtime_ref: str

    def simulate(self, specification: "SimulationSpecification", checkpoint: "SimulationCheckpointRef | None" = None) -> "SimulationBakeRef": ...


@dataclass(frozen=True)
class SimulationSpecification:
    project_ref: ProjectRef
    simulation_id: str
    scene_ref: str
    scene_sha256: str
    geometry_ref: str
    geometry_sha256: str
    animation_ref: str
    animation_sha256: str
    simulation_type: str
    config_version: str
    config: Mapping[str, str]
    material_parameters: Mapping[str, str]
    frame_start: int
    frame_end: int
    time_start: float
    time_end: float
    timestep: float
    substeps: int
    collision: Mapping[str, str]
    forces: Mapping[str, str]
    output_refs: tuple[str, ...]
    cache_policy: Mapping[str, str]
    renderer_target: Mapping[str, str]
    validation: Mapping[str, str]
    resources: Mapping[str, str]
    seed: int
    generator_ref: str
    tool_ref: str
    tool_version: str
    determinism: str
    canonical_digest: str
    runtime_ref: str = ""
    solver_ref: str = ""
    output_content_sha256s: tuple[str, ...] = ()

    @classmethod
    def create(
        cls, project_ref: ProjectRef, simulation_id: str, scene_ref: str, scene_sha256: str,
        geometry_ref: str, geometry_sha256: str, animation_ref: str, animation_sha256: str,
        simulation_type: str, config_version: str, config: Mapping[str, str],
        material_parameters: Mapping[str, str], frame_start: int, frame_end: int,
        time_start: float, time_end: float, timestep: float, substeps: int,
        collision: Mapping[str, str], forces: Mapping[str, str], output_refs: Sequence[str],
        output_content_sha256s: Sequence[str], cache_policy: Mapping[str, str],
        renderer_target: Mapping[str, str], validation: Mapping[str, str],
        resources: Mapping[str, str], seed: int, generator_ref: str, tool_ref: str,
        runtime_ref: str, solver_ref: str, tool_version: str, determinism: str,
    ) -> "SimulationSpecification":
        digest = cls._expected_digest(project_ref, simulation_id, scene_ref, scene_sha256, geometry_ref, geometry_sha256, animation_ref, animation_sha256, simulation_type, config_version, config, material_parameters, frame_start, frame_end, time_start, time_end, timestep, substeps, collision, forces, output_refs, output_content_sha256s, cache_policy, renderer_target, validation, resources, seed, generator_ref, tool_ref, runtime_ref, solver_ref, tool_version, determinism)
        return cls(project_ref, simulation_id, scene_ref, scene_sha256, geometry_ref, geometry_sha256, animation_ref, animation_sha256, simulation_type, config_version, config, material_parameters, frame_start, frame_end, time_start, time_end, timestep, substeps, collision, forces, tuple(output_refs), cache_policy, renderer_target, validation, resources, seed, generator_ref, tool_ref, tool_version, determinism, digest, runtime_ref, solver_ref, tuple(output_content_sha256s))

    @staticmethod
    def _expected_digest(
        project_ref: ProjectRef, simulation_id: str, scene_ref: str, scene_sha256: str,
        geometry_ref: str, geometry_sha256: str, animation_ref: str, animation_sha256: str,
        simulation_type: str, config_version: str, config: Mapping[str, str], material_parameters: Mapping[str, str],
        frame_start: int, frame_end: int, time_start: float, time_end: float, timestep: float,
        substeps: int, collision: Mapping[str, str], forces: Mapping[str, str], output_refs: Sequence[str],
        output_content_sha256s: Sequence[str], cache_policy: Mapping[str, str], renderer_target: Mapping[str, str],
        validation: Mapping[str, str], resources: Mapping[str, str], seed: int, generator_ref: str,
        tool_ref: str, runtime_ref: str, solver_ref: str, tool_version: str, determinism: str,
    ) -> str:
        if not isinstance(project_ref, ProjectRef) or not isinstance(simulation_id, str) or not simulation_id:
            raise SimulationContractError("project_ref or simulation_id is invalid")
        if not isinstance(frame_start, int) or isinstance(frame_start, bool) or not isinstance(frame_end, int) or isinstance(frame_end, bool) or frame_end < frame_start:
            raise SimulationContractError("frame range is invalid")
        if not isinstance(substeps, int) or isinstance(substeps, bool) or substeps < 1:
            raise SimulationContractError("substeps is invalid")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise SimulationContractError("seed is invalid")
        start, end, step = _finite(time_start, "time_start"), _finite(time_end, "time_end"), _finite(timestep, "timestep")
        if end < start or step <= 0:
            raise SimulationContractError("time range or timestep is invalid")
        if any(not isinstance(value, str) or not value for value in (simulation_type, config_version, tool_version)) or determinism not in {"deterministic", "nondeterministic"}:
            raise SimulationContractError("simulation version is invalid")
        outputs, output_contents = _refs(output_refs, "output_refs"), _shas(output_content_sha256s, "output_content_sha256s")
        if not outputs or len(outputs) != len(output_contents):
            raise SimulationContractError("output identities are incomplete")
        return _digest({
            "project_ref": project_ref.value, "simulation_id": simulation_id,
            "scene_ref": _ref(scene_ref, "scene_ref"), "scene_sha256": _sha(scene_sha256, "scene_sha256"),
            "geometry_ref": _ref(geometry_ref, "geometry_ref"), "geometry_sha256": _sha(geometry_sha256, "geometry_sha256"),
            "animation_ref": _ref(animation_ref, "animation_ref"), "animation_sha256": _sha(animation_sha256, "animation_sha256"),
            "simulation_type": simulation_type, "config_version": config_version,
            "config": dict(_map(config, "config")), "material_parameters": dict(_map(material_parameters, "material_parameters")),
            "frame_start": frame_start, "frame_end": frame_end, "time_start": start, "time_end": end,
            "timestep": step, "substeps": substeps, "collision": dict(_map(collision, "collision")),
            "forces": dict(_map(forces, "forces")), "output_refs": list(outputs),
            "output_content_sha256s": list(output_contents), "cache_policy": dict(_map(cache_policy, "cache_policy")),
            "renderer_target": dict(_map(renderer_target, "renderer_target")), "validation": dict(_map(validation, "validation")),
            "resources": dict(_map(resources, "resources")), "seed": seed,
            "generator_ref": _ref(generator_ref, "generator_ref"), "tool_ref": _ref(tool_ref, "tool_ref"),
            "runtime_ref": _ref(runtime_ref, "runtime_ref"), "solver_ref": _ref(solver_ref, "solver_ref"),
            "tool_version": tool_version, "determinism": determinism,
        })

    def __post_init__(self) -> None:
        expected = self._expected_digest(self.project_ref, self.simulation_id, self.scene_ref, self.scene_sha256, self.geometry_ref, self.geometry_sha256, self.animation_ref, self.animation_sha256, self.simulation_type, self.config_version, self.config, self.material_parameters, self.frame_start, self.frame_end, self.time_start, self.time_end, self.timestep, self.substeps, self.collision, self.forces, self.output_refs, self.output_content_sha256s, self.cache_policy, self.renderer_target, self.validation, self.resources, self.seed, self.generator_ref, self.tool_ref, self.runtime_ref, self.solver_ref, self.tool_version, self.determinism)
        if _sha(self.canonical_digest, "canonical_digest") != expected:
            raise SimulationContractError("canonical_digest does not match exact specification")
        for name in ("config", "material_parameters", "collision", "forces", "cache_policy", "renderer_target", "validation", "resources"):
            object.__setattr__(self, name, _map(getattr(self, name), name))
        object.__setattr__(self, "output_refs", _refs(self.output_refs, "output_refs"))
        object.__setattr__(self, "output_content_sha256s", _shas(self.output_content_sha256s, "output_content_sha256s"))


CheckpointValues: TypeAlias = tuple[ProjectRef, SimulationSpecification, str, str, int, float, str, str, str, str, str, str, str, str, int]


@dataclass(frozen=True)
class SimulationCheckpointRef:
    project_ref: ProjectRef
    specification: SimulationSpecification
    scene_ref: str
    scene_sha256: str
    frame: int
    time: float
    solver_ref: str
    runtime_ref: str
    content_sha256: str
    verified_at: str
    artifact_ref: str = ""
    predecessor_artifact_ref: str = ""
    predecessor_content_sha256: str = ""
    producer_attempt_id: str = ""
    producer_fence: int = 0
    checkpoint_digest: str = ""

    @classmethod
    def create(cls, project_ref: ProjectRef, specification: SimulationSpecification, frame: int, time: float, artifact_ref: str, content_sha256: str, predecessor_artifact_ref: str, predecessor_content_sha256: str, producer_attempt_id: str, producer_fence: int, verified_at: str) -> "SimulationCheckpointRef":
        values = cls._validated(project_ref, specification, specification.scene_ref, specification.scene_sha256, frame, time, specification.solver_ref, specification.runtime_ref, content_sha256, verified_at, artifact_ref, predecessor_artifact_ref, predecessor_content_sha256, producer_attempt_id, producer_fence)
        return cls(*values, _digest(cls._payload(*values)))

    @staticmethod
    def _validated(project_ref: ProjectRef, specification: SimulationSpecification, scene_ref: str, scene_sha256: str, frame: int, time: float, solver_ref: str, runtime_ref: str, content_sha256: str, verified_at: str, artifact_ref: str, predecessor_artifact_ref: str, predecessor_content_sha256: str, producer_attempt_id: str, producer_fence: int) -> CheckpointValues:
        if not isinstance(project_ref, ProjectRef) or not isinstance(specification, SimulationSpecification) or specification.project_ref != project_ref:
            raise SimulationContractError("checkpoint project/specification is invalid")
        if scene_ref != specification.scene_ref or scene_sha256 != specification.scene_sha256 or solver_ref != specification.solver_ref or runtime_ref != specification.runtime_ref:
            raise SimulationContractError("checkpoint identity is incompatible")
        if not isinstance(frame, int) or isinstance(frame, bool) or frame < specification.frame_start or frame > specification.frame_end or not isinstance(verified_at, str) or not verified_at:
            raise SimulationContractError("checkpoint frame or verification is invalid")
        attempt, fence = _attempt(producer_attempt_id, producer_fence, "checkpoint")
        return (project_ref, specification, _ref(scene_ref, "scene_ref"), _sha(scene_sha256, "scene_sha256"), frame, _finite(time, "checkpoint time"), _ref(solver_ref, "solver_ref"), _ref(runtime_ref, "runtime_ref"), _sha(content_sha256, "content_sha256"), verified_at, _ref(artifact_ref, "artifact_ref"), _ref(predecessor_artifact_ref, "predecessor_artifact_ref"), _sha(predecessor_content_sha256, "predecessor_content_sha256"), attempt, fence)

    @staticmethod
    def _payload(*values: object) -> dict[str, object]:
        project, specification, scene_ref, scene_sha, frame, time, solver, runtime, content, verified, artifact, predecessor, predecessor_content, attempt, fence = values
        if not isinstance(project, ProjectRef) or not isinstance(specification, SimulationSpecification):
            raise SimulationContractError("checkpoint identity is invalid")
        return {"project_ref": project.value, "specification_digest": specification.canonical_digest, "scene_ref": scene_ref, "scene_sha256": scene_sha, "frame": frame, "time": time, "solver_ref": solver, "runtime_ref": runtime, "content_sha256": content, "verified_at": verified, "artifact_ref": artifact, "predecessor_artifact_ref": predecessor, "predecessor_content_sha256": predecessor_content, "producer_attempt_id": attempt, "producer_fence": fence}

    def __post_init__(self) -> None:
        values = self._validated(self.project_ref, self.specification, self.scene_ref, self.scene_sha256, self.frame, self.time, self.solver_ref, self.runtime_ref, self.content_sha256, self.verified_at, self.artifact_ref, self.predecessor_artifact_ref, self.predecessor_content_sha256, self.producer_attempt_id, self.producer_fence)
        if _sha(self.checkpoint_digest, "checkpoint_digest") != _digest(self._payload(*values)):
            raise SimulationContractError("checkpoint_digest does not match exact checkpoint")


BakeValues: TypeAlias = tuple[ProjectRef, SimulationSpecification, str, str, str, int, int, str, tuple[str, ...], tuple[str, ...], tuple[SimulationCheckpointRef, ...], str, int]


@dataclass(frozen=True)
class SimulationBakeRef:
    project_ref: ProjectRef
    specification: SimulationSpecification
    tool_ref: str
    scene_ref: str
    scene_sha256: str
    frame_start: int
    frame_end: int
    settings_sha256: str
    format: str
    artifact_refs: tuple[str, ...]
    complete: bool
    artifact_content_sha256s: tuple[str, ...] = ()
    checkpoints: tuple[SimulationCheckpointRef, ...] = ()
    producer_attempt_id: str = ""
    producer_fence: int = 0
    bake_digest: str = ""

    @classmethod
    def create(cls, project_ref: ProjectRef, specification: SimulationSpecification, format: str, artifact_refs: Sequence[str], artifact_content_sha256s: Sequence[str], checkpoints: Sequence[SimulationCheckpointRef], producer_attempt_id: str, producer_fence: int) -> "SimulationBakeRef":
        values = cls._validated(project_ref, specification, specification.tool_ref, specification.scene_ref, specification.scene_sha256, specification.frame_start, specification.frame_end, format, artifact_refs, artifact_content_sha256s, checkpoints, producer_attempt_id, producer_fence)
        settings = _digest({"specification": specification.canonical_digest, "checkpoints": [checkpoint.checkpoint_digest for checkpoint in values[10]]})
        digest = _digest(cls._payload(*values, settings))
        return cls(values[0], values[1], values[2], values[3], values[4], values[5], values[6], settings, values[7], values[8], True, values[9], values[10], values[11], values[12], digest)

    @staticmethod
    def _validated(project_ref: ProjectRef, specification: SimulationSpecification, tool_ref: str, scene_ref: str, scene_sha256: str, frame_start: int, frame_end: int, format: str, artifact_refs: Sequence[str], artifact_content_sha256s: Sequence[str], checkpoints: Sequence[SimulationCheckpointRef], producer_attempt_id: str, producer_fence: int) -> BakeValues:
        if not isinstance(project_ref, ProjectRef) or not isinstance(specification, SimulationSpecification) or specification.project_ref != project_ref or tool_ref != specification.tool_ref or scene_ref != specification.scene_ref or scene_sha256 != specification.scene_sha256 or frame_start != specification.frame_start or frame_end != specification.frame_end:
            raise SimulationContractError("bake identity is incompatible")
        if not isinstance(format, str) or not format:
            raise SimulationContractError("bake format is invalid")
        refs, contents = _refs(artifact_refs, "artifact_refs"), _shas(artifact_content_sha256s, "artifact_content_sha256s")
        if not refs or len(refs) != len(contents):
            raise SimulationContractError("bake output identities are incomplete")
        chain = tuple(checkpoints)
        if not all(isinstance(item, SimulationCheckpointRef) for item in chain):
            raise SimulationContractError("bake checkpoint chain is incompatible")
        if tuple(item.frame for item in chain) != tuple(range(specification.frame_start, specification.frame_end + 1)):
            raise SimulationContractError("bake checkpoint coverage is incomplete")
        predecessor_ref, predecessor_content = specification.scene_ref, specification.scene_sha256
        for checkpoint in chain:
            if not isinstance(checkpoint, SimulationCheckpointRef) or checkpoint.specification != specification or checkpoint.predecessor_artifact_ref != predecessor_ref or checkpoint.predecessor_content_sha256 != predecessor_content:
                raise SimulationContractError("bake checkpoint chain is incompatible")
            predecessor_ref, predecessor_content = checkpoint.artifact_ref, checkpoint.content_sha256
        attempt, fence = _attempt(producer_attempt_id, producer_fence, "bake")
        return (project_ref, specification, _ref(tool_ref, "tool_ref"), _ref(scene_ref, "scene_ref"), _sha(scene_sha256, "scene_sha256"), frame_start, frame_end, format, refs, contents, chain, attempt, fence)

    @staticmethod
    def _payload(*values: object) -> dict[str, object]:
        project, specification, tool, scene, scene_sha, frame_start, frame_end, format, refs, contents, checkpoints, attempt, fence, settings = values
        if not isinstance(project, ProjectRef) or not isinstance(specification, SimulationSpecification):
            raise SimulationContractError("bake identity is invalid")
        output_refs = cast(tuple[str, ...], refs)
        output_contents = cast(tuple[str, ...], contents)
        chain = cast(tuple[SimulationCheckpointRef, ...], checkpoints)
        return {"project_ref": project.value, "specification_digest": specification.canonical_digest, "tool_ref": tool, "scene_ref": scene, "scene_sha256": scene_sha, "frame_start": frame_start, "frame_end": frame_end, "settings_sha256": settings, "format": format, "artifact_refs": list(output_refs), "artifact_content_sha256s": list(output_contents), "checkpoints": [checkpoint.checkpoint_digest for checkpoint in chain], "producer_attempt_id": attempt, "producer_fence": fence}

    def __post_init__(self) -> None:
        values = self._validated(self.project_ref, self.specification, self.tool_ref, self.scene_ref, self.scene_sha256, self.frame_start, self.frame_end, self.format, self.artifact_refs, self.artifact_content_sha256s, self.checkpoints, self.producer_attempt_id, self.producer_fence)
        settings = _digest({"specification": self.specification.canonical_digest, "checkpoints": [checkpoint.checkpoint_digest for checkpoint in self.checkpoints]})
        if not self.complete or _sha(self.settings_sha256, "settings_sha256") != settings or _sha(self.bake_digest, "bake_digest") != _digest(self._payload(*values, settings)):
            raise SimulationContractError("bake completeness or digest is invalid")


def vfx_production_pack() -> ProductionPack:
    capabilities = tuple(Capability(CapabilityRef(f"vfx.{name}", "1.0.0"), f"Bounded vfx {name}", {}, {"result": f"minitz://contracts/vfx-{name}/v1"}, (), "2026-08-31T00:00:00+00:00") for name in _NAMES)
    refs = {capability.name: capability.capability_ref for capability in capabilities}
    steps = tuple(GraphRecipeStepRegistration(name, refs[name], () if index == 0 else (_NAMES[index - 1],)) for index, name in enumerate(_NAMES))
    return ProductionPack(ProductionPackRef("vfx", "1.0.0"), capabilities, (GraphRecipeRegistration("pack-recipe://vfx/production@1.0.0", steps),), tuple(ValidatorRegistration(f"pack-validator://vfx/{name}@1.0.0", refs[name], f"validation-check://artifact-role/{_ROLES[index % len(_ROLES)]}/v1") for index, name in enumerate(_NAMES)), _ROLES, {capability.capability_ref.value: ("adapter://process/v1",) for capability in capabilities}, {capability.capability_ref.value: "resource-profile://vfx/project-configured/v1" for capability in capabilities}, "2026-08-31T00:00:00+00:00")
