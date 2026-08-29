"""Web application production-pack data for the universal Biella substrate."""

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
    "frontend",
    "backend",
    "fullstack",
    "component",
    "route",
    "api",
    "database_integrate",
    "build",
    "run",
    "test",
    "browser_validate",
    "performance",
    "accessibility",
    "package",
)

_DESCRIPTIONS = {
    "inspect": "Discover exact Project framework, runtime, package, routing, test, database, environment, and entrypoint evidence.",
    "frontend": "Modify an exact candidate frontend according to Project-owned design and framework authority.",
    "backend": "Modify exact candidate service, route, storage, or background behavior according to Project architecture.",
    "fullstack": "Coordinate dependency-aware frontend and backend candidate work without imposing a fixed framework hierarchy.",
    "component": "Create or change a bounded Project-framework component with observed behavior evidence.",
    "route": "Create or change a Project-authorized frontend or backend route in the exact candidate.",
    "api": "Implement or observe a Project-authorized API or health endpoint through exact HTTP evidence.",
    "database_integrate": "Integrate the database selected by the Project without assuming a universal database or migration authority.",
    "build": "Build the exact web candidate and require a captured build output Artifact.",
    "run": "Start the exact candidate runtime and retain endpoint, process, log, health, and failure evidence.",
    "test": "Execute exact candidate web tests and retain observed process evidence.",
    "browser_validate": "Validate exact live candidate behavior with bounded browser interaction and durable outputs.",
    "performance": "Measure explicit Project-defined web dimensions without a universal threshold.",
    "accessibility": "Record explicit semantic, keyboard, or automated accessibility checks without claiming universal certification.",
    "package": "Produce and capture the exact requested static, server, container, or package output without implicit deployment.",
}


def _capability(name: str) -> Capability:
    output_role = {
        "inspect": "inspection",
        "frontend": "candidate",
        "backend": "candidate",
        "fullstack": "graph",
        "component": "candidate",
        "route": "candidate",
        "api": "http-evidence",
        "database_integrate": "database-evidence",
        "build": "build-artifact",
        "run": "runtime-evidence",
        "test": "test-evidence",
        "browser_validate": "browser-evidence",
        "performance": "performance-evidence",
        "accessibility": "accessibility-evidence",
        "package": "package-artifact",
    }[name]
    side_effects = {
        "frontend": ("workspace.filesystem.write",),
        "backend": ("workspace.filesystem.write",),
        "fullstack": ("workspace.filesystem.write",),
        "component": ("workspace.filesystem.write",),
        "route": ("workspace.filesystem.write",),
        "api": ("workspace.filesystem.write", "http.execute"),
        "database_integrate": ("workspace.filesystem.write", "database.execute"),
        "build": ("workspace.process.execute", "workspace.artifact.create"),
        "run": ("workspace.process.execute",),
        "test": ("workspace.process.execute",),
        "browser_validate": ("browser.execute",),
        "performance": ("http.execute", "browser.execute", "workspace.process.execute"),
        "accessibility": ("browser.execute",),
        "package": ("workspace.process.execute", "workspace.artifact.create"),
    }.get(name, ())
    return Capability(
        capability_ref=CapabilityRef(f"web.{name}", _VERSION),
        description=_DESCRIPTIONS[name],
        input_contract={
            "project": "biella://contracts/project-ref/v1",
            "repository": "biella://contracts/repository-ref/v1",
            "task": "biella://contracts/task-ref/v1",
        },
        output_contract={output_role: f"biella://contracts/web-{output_role}/v1"},
        side_effects=side_effects,
        created_at=_CREATED_AT,
    )


def web_production_pack() -> ProductionPack:
    """Return the immutable, framework-neutral web pack descriptor as data."""

    capabilities = tuple(_capability(name) for name in _CAPABILITY_NAMES)
    by_name = {item.name: item.capability_ref for item in capabilities}
    recipes = (
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://web/frontend-live-validation@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("frontend", by_name["frontend"], ("inspect",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("frontend",)),
                GraphRecipeStepRegistration("build", by_name["build"], ("test",)),
                GraphRecipeStepRegistration("runtime", by_name["run"], ("build",)),
                GraphRecipeStepRegistration("browser", by_name["browser_validate"], ("runtime",)),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://web/backend-api-validation@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("backend", by_name["backend"], ("inspect",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("backend",)),
                GraphRecipeStepRegistration("runtime", by_name["run"], ("test",)),
                GraphRecipeStepRegistration("http", by_name["api"], ("runtime",)),
            ),
        ),
        GraphRecipeRegistration(
            recipe_ref="pack-recipe://web/fullstack-live-validation@1.0.0",
            steps=(
                GraphRecipeStepRegistration("inspect", by_name["inspect"]),
                GraphRecipeStepRegistration("frontend", by_name["frontend"], ("inspect",)),
                GraphRecipeStepRegistration("backend", by_name["backend"], ("inspect",)),
                GraphRecipeStepRegistration("test", by_name["test"], ("frontend", "backend")),
                GraphRecipeStepRegistration("build", by_name["build"], ("frontend", "backend")),
                GraphRecipeStepRegistration("runtime", by_name["run"], ("build", "test")),
                GraphRecipeStepRegistration("http", by_name["api"], ("runtime",)),
                GraphRecipeStepRegistration("browser", by_name["browser_validate"], ("runtime",)),
                GraphRecipeStepRegistration("package", by_name["package"], ("http", "browser")),
            ),
        ),
    )
    validators = (
        ValidatorRegistration(
            registration_ref="pack-validator://web/build-output@1.0.0",
            capability_ref=by_name["build"],
            validator_ref="validation-check://artifact-role/web.build.output/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://web/live-runtime@1.0.0",
            capability_ref=by_name["run"],
            validator_ref="validation-check://artifact-role/web.runtime.observation/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://web/http-response@1.0.0",
            capability_ref=by_name["api"],
            validator_ref="validation-check://artifact-role/web.http.response/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://web/browser-behavior@1.0.0",
            capability_ref=by_name["browser_validate"],
            validator_ref="validation-check://artifact-role/web.browser.validation/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://web/performance-measurement@1.0.0",
            capability_ref=by_name["performance"],
            validator_ref="validation-check://artifact-role/web.performance.report/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://web/accessibility-evidence@1.0.0",
            capability_ref=by_name["accessibility"],
            validator_ref="validation-check://artifact-role/web.accessibility.report/v1",
        ),
        ValidatorRegistration(
            registration_ref="pack-validator://web/package-output@1.0.0",
            capability_ref=by_name["package"],
            validator_ref="validation-check://artifact-role/web.package.output/v1",
        ),
    )
    bindings = {
        "inspect": ("adapter://git/v1", "adapter://filesystem/v1", "adapter://context-retrieval/v1"),
        "frontend": ("adapter://git/v1", "adapter://workspace/v1", "adapter://filesystem/v1", "adapter://model/v1"),
        "backend": ("adapter://git/v1", "adapter://workspace/v1", "adapter://filesystem/v1", "adapter://model/v1"),
        "fullstack": ("adapter://graph/v1", "adapter://scheduler/v1", "adapter://workspace/v1"),
        "component": ("adapter://git/v1", "adapter://workspace/v1", "adapter://browser/v1"),
        "route": ("adapter://git/v1", "adapter://workspace/v1", "adapter://http/v1"),
        "api": ("adapter://git/v1", "adapter://workspace/v1", "adapter://http/v1"),
        "database_integrate": ("adapter://git/v1", "adapter://workspace/v1", "adapter://postgresql/v1"),
        "build": ("adapter://artifact/v1", "adapter://process/v1", "adapter://workspace/v1"),
        "run": ("adapter://process/v1", "adapter://workspace/v1", "adapter://http/v1"),
        "test": ("adapter://process/v1", "adapter://workspace/v1", "adapter://browser/v1"),
        "browser_validate": ("adapter://browser/v1", "adapter://http/v1", "adapter://validation/v1"),
        "performance": ("adapter://browser/v1", "adapter://http/v1", "adapter://process/v1", "adapter://resource/v1", "adapter://validation/v1"),
        "accessibility": ("adapter://browser/v1", "adapter://validation/v1"),
        "package": ("adapter://artifact/v1", "adapter://process/v1", "adapter://workspace/v1", "adapter://validation/v1"),
    }
    adapter_bindings = {
        capability.capability_ref.value: bindings[capability.name]
        for capability in capabilities
    }
    resource_profiles = {
        capability.capability_ref.value: "resource-profile://web/bounded-cpu-workspace/v1"
        for capability in capabilities
    }
    return ProductionPack(
        pack_ref=ProductionPackRef("web", _VERSION),
        capability_definitions=capabilities,
        graph_recipes=recipes,
        validators=validators,
        artifact_roles=(
            "source.base",
            "source.candidate",
            "test.result",
            "web.accessibility.report",
            "web.browser.screenshot",
            "web.browser.validation",
            "web.build.output",
            "web.http.response",
            "web.package.output",
            "web.performance.report",
            "web.runtime.observation",
        ),
        adapter_bindings=adapter_bindings,
        resource_profiles=resource_profiles,
        created_at=_CREATED_AT,
    )
