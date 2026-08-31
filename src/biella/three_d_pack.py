"""Provider-neutral 3D modeling and scene production-pack data."""

from __future__ import annotations

from .capability import Capability, CapabilityRef
from .production_pack import (
    GraphRecipeRegistration,
    GraphRecipeStepRegistration,
    ProductionPack,
    ProductionPackRef,
    ValidatorRegistration,
)


_VERSION = "1.0.0"
_CREATED_AT = "2026-08-30T00:00:00+00:00"
_CAPABILITY_NAMES = (
    "inspect",
    "model",
    "mesh_edit",
    "topology",
    "uv",
    "material",
    "scene",
    "convert",
    "optimize",
    "validate",
    "preview",
)

_DESCRIPTIONS = {
    "inspect": "Inspect bounded hierarchy, geometry, topology, UV, material, texture, transform, scale, and dependency facts from an exact 3D source.",
    "model": "Create an exact editable 3D source through a replaceable tool adapter.",
    "mesh_edit": "Apply a bounded geometry edit while retaining exact editable-source derivation.",
    "topology": "Apply or inspect Project-requested topology operations without a universal topology policy.",
    "uv": "Create or modify UV data only when required by the exact Task.",
    "material": "Bind material parameters and exact texture Artifacts without generating texture content.",
    "scene": "Create or modify exact scene hierarchy, transforms, cameras, or lights.",
    "convert": "Derive a requested interchange representation from exact editable source.",
    "optimize": "Apply Project-scoped optimization criteria without a global polygon budget.",
    "validate": "Reopen or parse an exact source/export and retain technical validation evidence.",
    "preview": "Generate secondary preview evidence that cannot substitute for editable 3D source proof.",
}

_OUTPUTS = {
    "inspect": ("inspection", "3d-inspection"),
    "model": ("mesh", "3d-editable-source"),
    "mesh_edit": ("mesh", "3d-editable-source"),
    "topology": ("mesh", "3d-editable-source"),
    "uv": ("uv_data", "3d-uv-data"),
    "material": ("material", "3d-material"),
    "scene": ("scene", "3d-editable-source"),
    "convert": ("interchange_export", "3d-interchange-export"),
    "optimize": ("mesh", "3d-editable-source"),
    "validate": ("validation", "3d-validation"),
    "preview": ("preview", "3d-preview"),
}

_SIDE_EFFECTS = {
    "inspect": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "model": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "mesh_edit": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "topology": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "uv": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "material": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "scene": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "convert": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "optimize": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "validate": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
    "preview": ("workspace.process.execute", "workspace.filesystem.write", "workspace.artifact.create"),
}


def _capability(name: str) -> Capability:
    output_name, output_contract = _OUTPUTS[name]
    return Capability(
        capability_ref=CapabilityRef(f"3d.{name}", _VERSION),
        description=_DESCRIPTIONS[name],
        input_contract={
            "asset": "biella://contracts/artifact-ref/v1",
            "candidate": "biella://contracts/workspace-snapshot-ref/v1",
            "project": "biella://contracts/project-ref/v1",
            "task": "biella://contracts/task-ref/v1",
        },
        output_contract={
            output_name: f"biella://contracts/{output_contract}/v1",
        },
        side_effects=_SIDE_EFFECTS[name],
        created_at=_CREATED_AT,
    )


def three_d_production_pack() -> ProductionPack:
    """Return the immutable, DCC-neutral 3D pack descriptor as data."""

    capabilities = tuple(_capability(name) for name in _CAPABILITY_NAMES)
    by_name = {item.name: item.capability_ref for item in capabilities}
    recipes = (
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://3d/editable-asset-production@1.0.0",
            steps=(
                GraphRecipeStepRegistration("model", by_name["model"]),
                GraphRecipeStepRegistration("inspect", by_name["inspect"], ("model",)),
                GraphRecipeStepRegistration("mesh_edit", by_name["mesh_edit"], ("inspect",)),
                GraphRecipeStepRegistration("material", by_name["material"], ("mesh_edit",)),
                GraphRecipeStepRegistration("convert", by_name["convert"], ("material",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("convert",)),
                GraphRecipeStepRegistration("preview", by_name["preview"], ("material", "validate")),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://3d/topology-uv-validation@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("topology", by_name["topology"], ("inspect",)),
                GraphRecipeStepRegistration("uv", by_name["uv"], ("topology",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("uv",)),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://3d/scene-optimize-export@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("scene", by_name["scene"], ("inspect",)),
                GraphRecipeStepRegistration("optimize", by_name["optimize"], ("scene",)),
                GraphRecipeStepRegistration("convert", by_name["convert"], ("optimize",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("convert",)),
            ),
        ),
    )
    validator_roles = (
        ("bounded-inspection", "inspect", "3d.inspection"),
        ("editable-mesh", "model", "3d.mesh"),
        ("edited-mesh", "mesh_edit", "3d.mesh"),
        ("topology-result", "topology", "3d.mesh"),
        ("uv-result", "uv", "3d.uv-data"),
        ("material-result", "material", "3d.material"),
        ("editable-scene", "scene", "3d.scene"),
        ("interchange-reopen", "convert", "3d.interchange-export"),
        ("optimized-mesh", "optimize", "3d.mesh"),
        ("technical-validation", "validate", "3d.validation"),
        ("secondary-preview", "preview", "3d.preview"),
    )
    validators = tuple(
        ValidatorRegistration(
            registration_ref=f"pack-validator://3d/{registration_name}@1.0.0",
            capability_ref=by_name[capability_name],
            validator_ref=f"validation-check://artifact-role/{artifact_role}/v1",
        )
        for registration_name, capability_name, artifact_role in validator_roles
    )
    common = (
        "adapter://artifact/v1",
        "adapter://filesystem/v1",
        "adapter://process/v1",
        "adapter://three-d-tool/v1",
        "adapter://workspace/v1",
    )
    adapter_bindings = {
        capability.capability_ref.value: (
            *common,
            *(("adapter://validation/v1",) if capability.name == "validate" else ()),
        )
        for capability in capabilities
    }
    resource_profiles = {
        capability.capability_ref.value: "resource-profile://3d/project-configured-dcc/v1"
        for capability in capabilities
    }
    return ProductionPack(
        pack_ref=ProductionPackRef("3d", _VERSION),
        capability_definitions=capabilities,
        graph_recipes=recipes,
        validators=validators,
        artifact_roles=(
            "3d.collision-mesh",
            "3d.inspection",
            "3d.interchange-export",
            "3d.lod-set",
            "3d.material",
            "3d.mesh",
            "3d.preview",
            "3d.scene",
            "3d.texture-set",
            "3d.uv-data",
            "3d.validation",
        ),
        adapter_bindings=adapter_bindings,
        resource_profiles=resource_profiles,
        created_at=_CREATED_AT,
    )
