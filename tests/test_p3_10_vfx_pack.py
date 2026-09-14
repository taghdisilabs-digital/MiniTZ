from __future__ import annotations

from dataclasses import replace

import pytest

import minitz_os.engine as minitz_engine
from minitz_os.engine.production_pack import ProductionPackRef
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.vfx_pack import SimulationBakeRef, SimulationCheckpointRef, SimulationContractError, SimulationSpecification, vfx_production_pack

CAPS = {"inspect", "particles", "smoke", "fire", "fluid", "cloth", "hair", "rigidbody", "softbody", "destruction", "volumetric", "procedural", "simulate", "bake", "resume", "export", "preview", "validate", "composite_prepare"}
ATTEMPT = "natt_" + "1" * 32


def _spec(project_ref: ProjectRef) -> SimulationSpecification:
    return SimulationSpecification.create(project_ref, "sim-01", "artifact://scene/v1", "a" * 64, "artifact://geometry/v1", "b" * 64, "artifact://animation/v1", "c" * 64, "fluid", "1.0.0", {"solver": "generic"}, {"density": "1"}, 0, 1, 0.0, 1.0, 0.01, 2, {"collision": "on"}, {"force": "gravity"}, ("artifact://output/v1",), ("d" * 64,), {"cache": "required"}, {"renderer": "generic"}, {"validation": "required"}, {"resource": "project"}, 7, "generator://vfx/v1", "tool://vfx/v1", "runtime://vfx/v1", "solver://vfx/v1", "1.0.0", "deterministic")


def _checkpoints(project_ref: ProjectRef, specification: SimulationSpecification) -> tuple[SimulationCheckpointRef, SimulationCheckpointRef]:
    first = SimulationCheckpointRef.create(project_ref, specification, 0, 0.0, "artifact://checkpoint/0", "e" * 64, specification.scene_ref, specification.scene_sha256, ATTEMPT, 1, "2026-08-31T00:00:00+00:00")
    second = SimulationCheckpointRef.create(project_ref, specification, 1, 1.0, "artifact://checkpoint/1", "f" * 64, first.artifact_ref, first.content_sha256, ATTEMPT, 1, "2026-08-31T00:00:00+00:00")
    return first, second


def test_vfx_pack_exact_registrations() -> None:
    pack = vfx_production_pack()
    assert pack.pack_ref == ProductionPackRef("vfx", "1.0.0")
    assert {capability.capability_id for capability in pack.capability_definitions} == {f"vfx.{name}" for name in CAPS}
    assert "vfx.cache" in pack.artifact_roles
    assert {"SimulationAdapter", "SimulationBakeRef", "SimulationCheckpointRef", "SimulationContractError", "SimulationSpecification", "vfx_production_pack", "BlenderSimulationAdapter", "ReferenceSimulationAdapter"} <= set(minitz_engine.__all__)


def test_simulation_contracts_bind_every_output_affecting_identity() -> None:
    project_ref = ProjectRef.new()
    specification = _spec(project_ref)
    first, second = _checkpoints(project_ref, specification)
    bake = SimulationBakeRef.create(project_ref, specification, "application/x-blender", ("artifact://checkpoint/1", "artifact://bake/1"), ("f" * 64, "0" * 64), (first, second), ATTEMPT, 1)
    assert bake.complete and bake.checkpoints == (first, second)
    with pytest.raises(SimulationContractError, match="canonical_digest"):
        replace(specification, seed=8)
    with pytest.raises(SimulationContractError, match="not finite"):
        SimulationSpecification.create(project_ref, "sim-01", "artifact://scene/v1", "a" * 64, "artifact://geometry/v1", "b" * 64, "artifact://animation/v1", "c" * 64, "fluid", "1", {}, {}, 0, 1, float("nan"), 1.0, 0.1, 1, {}, {}, ("artifact://output/v1",), ("d" * 64,), {}, {}, {}, {}, 0, "generator://vfx/v1", "tool://vfx/v1", "runtime://vfx/v1", "solver://vfx/v1", "1", "deterministic")
    with pytest.raises(SimulationContractError, match="checkpoint"):
        replace(first, producer_fence=2)
    with pytest.raises(SimulationContractError, match="bake"):
        SimulationBakeRef.create(project_ref, specification, "application/x-blender", ("artifact://bake/1",), ("0" * 64,), (first,), ATTEMPT, 1)
    with pytest.raises(SimulationContractError, match="chain"):
        SimulationBakeRef.create(project_ref, specification, "application/x-blender", ("artifact://checkpoint/1", "artifact://bake/1"), ("f" * 64, "0" * 64), (first, object()), ATTEMPT, 1)  # type: ignore[arg-type]
