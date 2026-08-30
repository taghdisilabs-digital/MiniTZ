"""Engine-neutral game production-pack data for the universal substrate."""

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
    "import",
    "modify",
    "build",
    "run",
    "test",
    "profile",
    "capture",
    "export",
    "package",
    "validate",
)

_DESCRIPTIONS = {
    "inspect": "Detect and inspect exact game Project source, configuration, scenes, assets, tests, plugins, entry state, and engine identity.",
    "import": "Import the exact candidate with a replaceable engine adapter while treating generated caches as rebuildable outputs.",
    "modify": "Apply a bounded change to authoritative source or assets in an isolated candidate Workspace.",
    "build": "Build the exact candidate for the Project-selected target and require the expected output Artifact.",
    "run": "Launch the exact source or build and retain runtime, entry-state, crash, error, and behavior evidence.",
    "test": "Execute Project-selected engine-native or software tests and retain exact observed evidence.",
    "profile": "Measure only Project-requested runtime and package dimensions without a global performance threshold.",
    "capture": "Capture requested screenshot, video, log, state, or performance evidence without inferring gameplay correctness.",
    "export": "Export the exact candidate for the selected target and bind engine, configuration, and output identity.",
    "package": "Package an exact game output as a durable Artifact without implying publication.",
    "validate": "Evaluate Project acceptance criteria from exact game evidence without fabricated success.",
}

_OUTPUT_CONTRACTS = {
    "inspect": ("inspection", "game-inspection"),
    "import": ("import_output", "game-import-output"),
    "modify": ("candidate", "game-candidate"),
    "build": ("build_artifact", "game-build-output"),
    "run": ("runtime_evidence", "game-runtime-observation"),
    "test": ("test_evidence", "game-test-result"),
    "profile": ("profile_evidence", "game-profile-report"),
    "capture": ("capture_evidence", "game-capture-output"),
    "export": ("export_artifact", "game-export-output"),
    "package": ("package_artifact", "game-package-output"),
    "validate": ("validation_result", "game-validation-result"),
}

_SIDE_EFFECTS = {
    "inspect": ("workspace.process.execute", "workspace.artifact.create"),
    "import": ("workspace.process.execute", "workspace.artifact.create"),
    "modify": ("workspace.filesystem.write",),
    "build": ("workspace.process.execute", "workspace.artifact.create"),
    "run": ("workspace.process.execute", "workspace.artifact.create"),
    "test": ("workspace.process.execute", "workspace.artifact.create"),
    "profile": ("workspace.process.execute", "workspace.artifact.create"),
    "capture": ("workspace.process.execute", "workspace.artifact.create"),
    "export": ("workspace.process.execute", "workspace.artifact.create"),
    "package": ("workspace.process.execute", "workspace.artifact.create"),
}


def _capability(name: str) -> Capability:
    output_name, output_contract = _OUTPUT_CONTRACTS[name]
    return Capability(
        capability_ref=CapabilityRef(f"game.{name}", _VERSION),
        description=_DESCRIPTIONS[name],
        input_contract={
            "candidate": "biella://contracts/workspace-snapshot-ref/v1",
            "game_project": "biella://contracts/game-project-identity/v1",
            "project": "biella://contracts/project-ref/v1",
            "task": "biella://contracts/task-ref/v1",
        },
        output_contract={
            output_name: f"biella://contracts/{output_contract}/v1",
        },
        side_effects=_SIDE_EFFECTS.get(name, ()),
        created_at=_CREATED_AT,
    )


def game_production_pack() -> ProductionPack:
    """Return the immutable, provider-neutral game pack descriptor as data."""

    capabilities = tuple(_capability(name) for name in _CAPABILITY_NAMES)
    by_name = {item.name: item.capability_ref for item in capabilities}
    recipes = (
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://game/candidate-runtime-validation@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("modify", by_name["modify"], ("inspect",)),
                GraphRecipeStepRegistration("import", by_name["import"], ("modify",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("import",)),
                GraphRecipeStepRegistration("build", by_name["build"], ("import", "test")),
                GraphRecipeStepRegistration("run", by_name["run"], ("build",)),
                GraphRecipeStepRegistration("capture", by_name["capture"], ("run",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("capture", "run", "test")),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://game/export-package-validation@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("import", by_name["import"], ("inspect",)),
                GraphRecipeStepRegistration("build", by_name["build"], ("import",)),
                GraphRecipeStepRegistration("export", by_name["export"], ("build",)),
                GraphRecipeStepRegistration("package", by_name["package"], ("export",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("package",)),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://game/runtime-profile-capture@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("import", by_name["import"], ("inspect",)),
                GraphRecipeStepRegistration("build", by_name["build"], ("import",)),
                GraphRecipeStepRegistration("run", by_name["run"], ("build",)),
                GraphRecipeStepRegistration("profile", by_name["profile"], ("run",)),
                GraphRecipeStepRegistration("capture", by_name["capture"], ("run",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("capture", "profile")),
            ),
        ),
    )
    validator_roles = (
        ("engine-detection", "inspect", "game.engine.detection"),
        ("project-inspection", "inspect", "game.project.inspection"),
        ("import-output", "import", "game.import.output"),
        ("build-output", "build", "game.build.output"),
        ("runtime-observation", "run", "game.runtime.observation"),
        ("test-result", "test", "game.test.result"),
        ("profile-report", "profile", "game.profile.report"),
        ("capture-output", "capture", "game.capture.output"),
        ("export-output", "export", "game.export.output"),
        ("package-output", "package", "game.package.output"),
        ("validation-result", "validate", "game.validation.result"),
    )
    validators = tuple(
        ValidatorRegistration(
            registration_ref=f"pack-validator://game/{registration_name}@1.0.0",
            capability_ref=by_name[capability_name],
            validator_ref=f"validation-check://artifact-role/{artifact_role}/v1",
        )
        for registration_name, capability_name, artifact_role in validator_roles
    )
    bindings = {
        "inspect": (
            "adapter://artifact/v1",
            "adapter://filesystem/v1",
            "adapter://game-engine/v1",
            "adapter://git/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://resource/v1",
            "adapter://workspace/v1",
        ),
        "import": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://workspace/v1",
        ),
        "modify": (
            "adapter://filesystem/v1",
            "adapter://git/v1",
            "adapter://workspace/v1",
        ),
        "build": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://resource/v1",
            "adapter://workspace/v1",
        ),
        "run": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://resource/v1",
            "adapter://workspace/v1",
        ),
        "test": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://workspace/v1",
        ),
        "profile": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://resource/v1",
            "adapter://validation/v1",
            "adapter://workspace/v1",
        ),
        "capture": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://workspace/v1",
        ),
        "export": (
            "adapter://artifact/v1",
            "adapter://game-engine/v1",
            "adapter://isolated-runtime/v1",
            "adapter://process/v1",
            "adapter://workspace/v1",
        ),
        "package": (
            "adapter://artifact/v1",
            "adapter://process/v1",
            "adapter://validation/v1",
            "adapter://workspace/v1",
        ),
        "validate": (
            "adapter://artifact/v1",
            "adapter://validation/v1",
        ),
    }
    adapter_bindings = {
        capability.capability_ref.value: bindings[capability.name]
        for capability in capabilities
    }
    resource_profiles = {
        capability.capability_ref.value: "resource-profile://game/project-configured/v1"
        for capability in capabilities
    }
    return ProductionPack(
        pack_ref=ProductionPackRef("game", _VERSION),
        capability_definitions=capabilities,
        graph_recipes=recipes,
        validators=validators,
        artifact_roles=(
            "game.asset.3d.input",
            "game.asset.animation.input",
            "game.asset.audio.input",
            "game.asset.character.input",
            "game.asset.environment.input",
            "game.asset.image.input",
            "game.asset.vfx.input",
            "game.build.output",
            "game.capture.output",
            "game.engine.detection",
            "game.export.output",
            "game.import.output",
            "game.package.output",
            "game.profile.report",
            "game.project.inspection",
            "game.runtime.observation",
            "game.test.result",
            "game.validation.result",
        ),
        adapter_bindings=adapter_bindings,
        resource_profiles=resource_profiles,
        created_at=_CREATED_AT,
    )
