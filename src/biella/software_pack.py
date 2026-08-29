"""Software production-pack data for the universal Biella substrate."""

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
_CREATED_AT = "2026-08-29T00:00:00+00:00"
_CAPABILITY_NAMES = (
    "inspect",
    "search",
    "architecture",
    "engineer",
    "modify",
    "debug",
    "refactor",
    "test",
    "build",
    "run",
    "profile",
    "package",
    "validate",
)

_DESCRIPTIONS = {
    "inspect": "Inspect exact repository identity, structure, status, toolchain, and relevant architecture.",
    "search": "Retrieve focused source context without default full-repository model exposure.",
    "architecture": "Apply Project-scoped architecture and acceptance configuration to bounded software work.",
    "engineer": "Coordinate dependency-aware software work through existing Graph and scheduler contracts.",
    "modify": "Apply a bounded candidate change against an exact repository base in an isolated Workspace.",
    "debug": "Diagnose observed failure evidence and identify the smallest responsible defect boundary.",
    "refactor": "Change internal structure while preserving externally validated behavior.",
    "test": "Execute affected tests and retain exact observed process evidence.",
    "build": "Build an exact candidate and require a captured build output Artifact.",
    "run": "Execute an exact built or source candidate and observe required runtime behavior.",
    "profile": "Measure a baseline, profile an exact candidate, and retain comparable evidence.",
    "package": "Package an exact candidate and capture the produced package Artifact.",
    "validate": "Evaluate Project criteria from durable observed evidence without fabricated success.",
}


def _capability(name: str) -> Capability:
    capability_ref = CapabilityRef(f"software.{name}", _VERSION)
    common_input = {
        "project": "biella://contracts/project-ref/v1",
        "repository": "biella://contracts/repository-ref/v1",
        "task": "biella://contracts/task-ref/v1",
    }
    output_role = {
        "inspect": "inspection",
        "search": "context",
        "architecture": "decision",
        "engineer": "graph",
        "modify": "candidate",
        "debug": "diagnosis",
        "refactor": "candidate",
        "test": "test-evidence",
        "build": "build-artifact",
        "run": "runtime-evidence",
        "profile": "profile-evidence",
        "package": "package-artifact",
        "validate": "validation-result",
    }[name]
    side_effects = {
        "modify": ("workspace.filesystem.write",),
        "debug": ("workspace.process.execute",),
        "refactor": ("workspace.filesystem.write",),
        "test": ("workspace.process.execute",),
        "build": ("workspace.process.execute", "workspace.artifact.create"),
        "run": ("workspace.process.execute",),
        "profile": ("workspace.process.execute",),
        "package": ("workspace.process.execute", "workspace.artifact.create"),
    }.get(name, ())
    return Capability(
        capability_ref=capability_ref,
        description=_DESCRIPTIONS[name],
        input_contract=common_input,
        output_contract={output_role: f"biella://contracts/software-{output_role}/v1"},
        side_effects=side_effects,
        created_at=_CREATED_AT,
    )


def software_production_pack() -> ProductionPack:
    """Return the immutable software pack descriptor as data."""

    capabilities = tuple(_capability(name) for name in _CAPABILITY_NAMES)
    by_name = {item.name: item.capability_ref for item in capabilities}
    recipes = (
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://software/inspect-modify-test@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("modify", by_name["modify"], ("inspect",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("modify",)),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://software/debug-repair-validate@1.0.0",
            steps=(
                GraphRecipeStepRegistration("debug", by_name["debug"]),
                GraphRecipeStepRegistration("modify", by_name["modify"], ("debug",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("modify",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("test",)),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://software/production-repair@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("debug", by_name["debug"], ("inspect",)),
                GraphRecipeStepRegistration("modify", by_name["modify"], ("debug",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("modify",)),
                GraphRecipeStepRegistration("build", by_name["build"], ("test",)),
                GraphRecipeStepRegistration("run", by_name["run"], ("build",)),
                GraphRecipeStepRegistration("validate", by_name["validate"], ("run",)),
            ),
        ),
    )
    validators = (
        ValidatorRegistration(
            registration_ref="pack-validator://software/test-observation@1.0.0",
            capability_ref=by_name["test"],
            validator_ref="validation-check://process-exit-and-output/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://software/build-output@1.0.0",
            capability_ref=by_name["build"],
            validator_ref="validation-check://artifact-role/software.build.output/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://software/runtime-observation@1.0.0",
            capability_ref=by_name["run"],
            validator_ref="validation-check://process-exit-and-output/v1",
        ),
    )
    adapter_bindings: dict[str, tuple[str, ...]] = {}
    resource_profiles: dict[str, str] = {}
    for capability in capabilities:
        name = capability.name
        adapters = {
            "inspect": ("adapter://git/v1", "adapter://filesystem/v1"),
            "search": ("adapter://context-retrieval/v1", "adapter://filesystem/v1"),
            "architecture": ("adapter://project-memory/v1", "adapter://context-retrieval/v1", "adapter://model/v1"),
            "engineer": ("adapter://graph/v1", "adapter://scheduler/v1", "adapter://model/v1"),
            "modify": ("adapter://git/v1", "adapter://workspace/v1", "adapter://filesystem/v1"),
            "debug": ("adapter://process/v1", "adapter://context-retrieval/v1", "adapter://model/v1"),
            "refactor": ("adapter://git/v1", "adapter://workspace/v1"),
            "test": ("adapter://process/v1", "adapter://workspace/v1"),
            "build": ("adapter://artifact/v1", "adapter://process/v1", "adapter://workspace/v1"),
            "run": ("adapter://process/v1", "adapter://workspace/v1"),
            "profile": ("adapter://process/v1", "adapter://resource/v1"),
            "package": ("adapter://process/v1", "adapter://artifact/v1"),
            "validate": ("adapter://validation/v1",),
        }[name]
        adapter_bindings[capability.capability_ref.value] = adapters
        resource_profiles[capability.capability_ref.value] = (
            "resource-profile://software/bounded-cpu-workspace/v1"
        )
    return ProductionPack(
        pack_ref=ProductionPackRef("software", _VERSION),
        capability_definitions=capabilities,
        graph_recipes=recipes,
        validators=validators,
        artifact_roles=(
            "diagnosis.evidence",
            "package.output",
            "runtime.output",
            "software.build.output",
            "source.base",
            "source.candidate",
            "test.result",
        ),
        adapter_bindings=adapter_bindings,
        resource_profiles=resource_profiles,
        created_at=_CREATED_AT,
    )
