from __future__ import annotations

from dataclasses import replace
import math

import pytest

import biella
from biella.environment_pack import EnvironmentContractError, EnvironmentIntegrationManifest, EnvironmentSpecification, PlacedAsset, ProceduralTerrain, environment_production_pack
from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef
from biella.three_d_tool import EnvironmentManifestPublication, ThreeDEnvironmentLayoutSpec, ThreeDPlacedAssetSpec


CAPS = {"inspect", "layout", "terrain", "structure", "populate", "vegetation", "material", "lighting_setup", "collision", "navigation_prepare", "lod", "optimize", "partition", "export", "preview", "validate"}


def test_environment_pack_has_exact_capabilities_roles_recipes_and_validators() -> None:
    pack = environment_production_pack()
    assert pack.pack_ref == ProductionPackRef("environment", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == {f"environment.{name}" for name in CAPS}
    assert pack.artifact_roles and pack.graph_recipes and pack.validators


def test_environment_contracts_and_provider_neutral_specs_are_root_exports() -> None:
    expected = {"EnvironmentSpecification": EnvironmentSpecification, "EnvironmentIntegrationManifest": EnvironmentIntegrationManifest, "PlacedAsset": PlacedAsset, "ProceduralTerrain": ProceduralTerrain, "environment_production_pack": environment_production_pack, "ThreeDPlacedAssetSpec": ThreeDPlacedAssetSpec, "ThreeDEnvironmentLayoutSpec": ThreeDEnvironmentLayoutSpec, "EnvironmentManifestPublication": EnvironmentManifestPublication}
    assert set(expected) <= set(biella.__all__)
    assert all(getattr(biella, name) is value for name, value in expected.items())


def test_environment_records_fail_closed_for_stale_project_and_transform() -> None:
    project = ProjectRef.new()
    spec = EnvironmentSpecification(project, "world-01", "artifact://env/source/v1", "a" * 64, "meter", {"up": "Z"}, {"layout": "open"}, {"nav": "required"}, {"visual": "project"}, ("artifact://library/v1",), {"tool": "engine"}, {"performance": "project"}, {"partition": "project"}, ("contract://output/env/v1",), ("representation://env/streamed/v1",))
    asset = PlacedAsset(project, "tree-01", "artifact://asset/tree/v1", "b" * 64, (1.0,) * 16, "artifact://material/tree/v1", "summer", None, "partition-a")
    terrain = ProceduralTerrain(project, "terrain-01", "generator://terrain/v1", "1.0.0", {"noise": "simple"}, 7, "artifact://terrain/v1", "c" * 64)
    manifest = EnvironmentIntegrationManifest(project, spec, terrain, (asset,), "artifact://structure/v1", "artifact://prop/v1", "artifact://vegetation/v1", "artifact://material/v1", "artifact://collision/v1", "artifact://nav/v1", "artifact://partition/v1", "tool://engine/v1", "runtime://engine/v1", "derivation://env/v1", "d" * 64)
    assert manifest.require_specification(spec) is spec
    assert manifest.require_placed_assets((asset,)) == (asset,)
    with pytest.raises(EnvironmentContractError): replace(asset, transform=(math.inf,) * 16)
    with pytest.raises(EnvironmentContractError): manifest.require_placed_assets((replace(asset, transform=(2.0,) * 16),))
    with pytest.raises(EnvironmentContractError): manifest.require_placed_assets((replace(asset, material_ref="artifact://material/changed/v1"),))
    with pytest.raises(EnvironmentContractError): manifest.require_specification(replace(spec, project_ref=ProjectRef.new()))
