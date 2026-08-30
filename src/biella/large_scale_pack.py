"""Large-scale multi-domain production-pack data and Graph recipe compiler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType

from .artifact import ArtifactRef
from .capability import Capability, CapabilityRef
from .graph import GraphContractError, GraphRef, Node, NodeInputBinding, NodeRef
from .production_pack import (
    GraphRecipeRegistration,
    GraphRecipeStepRegistration,
    ProductionPack,
    ProductionPackRef,
    ValidatorRegistration,
)
from .run import RunRef
from .task import TaskRef


_VERSION = "1.0.0"
_CREATED_AT = "2026-08-30T00:00:00+00:00"
_PACKAGE_IMPLEMENTATION_REF = "production-pack://large-scale-package/1.0.0"
_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,1024}")
_DOMAIN_ORDER = (
    "software",
    "game",
    "3d",
    "character",
    "animation",
    "environment",
    "render",
    "vfx",
    "image",
    "audio",
    "video",
    "package",
)
_BRANCH_DOMAINS = _DOMAIN_ORDER[:-1]


class ProductionComponentReality(str, Enum):
    """Honest execution classification for one integrated component."""

    REAL = "REAL"
    REFERENCE = "REFERENCE"


@dataclass(frozen=True)
class MultiDomainBranch:
    """One independent branch in a large-scale composition recipe."""

    domain: str
    capability_ref: CapabilityRef
    reality: ProductionComponentReality
    implementation_ref: str
    resource_profile_ref: str

    def __post_init__(self) -> None:
        if self.domain not in _BRANCH_DOMAINS:
            raise GraphContractError("Production branch domain is unsupported")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        if not isinstance(self.reality, ProductionComponentReality):
            raise GraphContractError("Production branch reality is malformed")
        for value, name in (
            (self.implementation_ref, "implementation_ref"),
            (self.resource_profile_ref, "resource_profile_ref"),
        ):
            if not isinstance(value, str) or _REF_PATTERN.fullmatch(value) is None:
                raise GraphContractError(f"Production branch {name} must be an exact ref")
        if self.reality is ProductionComponentReality.REFERENCE and not self.implementation_ref.startswith(
            "reference://"
        ):
            raise GraphContractError("REFERENCE branch requires an explicit reference implementation")
        if self.reality is ProductionComponentReality.REAL and self.implementation_ref.startswith(
            "reference://"
        ):
            raise GraphContractError("REAL branch cannot bind a reference implementation")


@dataclass(frozen=True)
class MultiDomainGraphRecipe:
    """Immutable fan-out/fan-in recipe; execution remains normal Graph data."""

    recipe_ref: str
    domains: tuple[str, ...]
    branches: tuple[MultiDomainBranch, ...]
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.recipe_ref, str) or _REF_PATTERN.fullmatch(self.recipe_ref) is None:
            raise GraphContractError("Production recipe_ref must be an exact ref")
        if not isinstance(self.domains, tuple) or self.domains != _DOMAIN_ORDER:
            raise GraphContractError("Production recipe domains must be the exact supported set")
        if not isinstance(self.branches, tuple) or not all(
            isinstance(item, MultiDomainBranch) for item in self.branches
        ):
            raise GraphContractError("Production recipe branches are malformed")
        if tuple(item.domain for item in self.branches) != _BRANCH_DOMAINS:
            raise GraphContractError("Production recipe branches must cover every pre-package domain")
        payload = {
            "branches": [
                {
                    "capability_ref": item.capability_ref.value,
                    "domain": item.domain,
                    "implementation_ref": item.implementation_ref,
                    "reality": item.reality.value,
                    "resource_profile_ref": item.resource_profile_ref,
                }
                for item in self.branches
            ],
            "domains": list(self.domains),
            "recipe_ref": self.recipe_ref,
        }
        object.__setattr__(self, "semantic_digest", _sha256(payload))


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _capability(name: str, description: str, output_name: str, output_contract: str) -> Capability:
    side_effects = () if name in {"requirements", "runtime-validation", "performance-validation"} else (
        "workspace.artifact.create",
    )
    return Capability(
        capability_ref=CapabilityRef(f"production.{name}", _VERSION),
        description=description,
        input_contract={
            "project": "biella://contracts/project-ref/v1",
            "task": "biella://contracts/task-ref/v1",
            "run": "biella://contracts/run-ref/v1",
            "graph": "biella://contracts/graph-ref/v1",
        },
        output_contract={output_name: output_contract},
        side_effects=side_effects,
        created_at=_CREATED_AT,
    )


def _capabilities() -> tuple[Capability, ...]:
    definitions = [
        _capability(
            "requirements",
            "Resolve exact Project requirements and configuration refs as data.",
            "requirements",
            "biella://contracts/production-requirements/v1",
        )
    ]
    definitions.extend(
        _capability(
            f"domain.{domain}",
            f"Produce the exact {domain} component through a replaceable capability implementation.",
            "component",
            "biella://contracts/production-component-artifact/v1",
        )
        for domain in _BRANCH_DOMAINS
    )
    definitions.extend(
        (
            _capability(
                "integrate",
                "Integrate exact component Artifact revisions without latest resolution.",
                "integration",
                "biella://contracts/production-integration-output/v1",
            ),
            _capability(
                "build",
                "Build the exact integrated production candidate.",
                "build",
                "biella://contracts/production-build-output/v1",
            ),
            _capability(
                "runtime-validation",
                "Validate observed runtime evidence for the exact build.",
                "validation",
                "biella://contracts/production-validation-result/v1",
            ),
            _capability(
                "performance-validation",
                "Measure only Project-defined performance budgets for the exact build.",
                "validation",
                "biella://contracts/production-validation-result/v1",
            ),
            _capability(
                "package",
                "Package the exact validated build as a durable Artifact.",
                "package",
                "biella://contracts/production-package-output/v1",
            ),
        )
    )
    return tuple(definitions)


def large_scale_graph_recipe() -> MultiDomainGraphRecipe:
    """Return explicit bundle metadata for implemented and downstream domains."""

    branches: list[MultiDomainBranch] = []
    for domain in _BRANCH_DOMAINS:
        if domain in {"software", "game"}:
            reality = ProductionComponentReality.REAL
            implementation = f"production-pack://{domain}/1.0.0"
        else:
            reality = ProductionComponentReality.REFERENCE
            implementation = f"reference://production/{domain}/1.0.0"
        branches.append(
            MultiDomainBranch(
                domain=domain,
                capability_ref=CapabilityRef(f"production.domain.{domain}", _VERSION),
                reality=reality,
                implementation_ref=implementation,
                resource_profile_ref=f"project-config://production/resource/{domain}",
            )
        )
    return MultiDomainGraphRecipe(
        recipe_ref="pack-recipe://large-scale-production/multi-domain-fanout-fanin@1.0.0",
        domains=_DOMAIN_ORDER,
        branches=tuple(branches),
    )


def large_scale_production_pack() -> ProductionPack:
    """Return the provider-neutral large-scale composition pack descriptor."""

    capabilities = _capabilities()
    by_name = {item.name: item.capability_ref for item in capabilities}
    domain_steps = tuple(
        GraphRecipeStepRegistration(
            f"domain-{domain}",
            by_name[f"domain.{domain}"],
            ("requirements",),
        )
        for domain in _BRANCH_DOMAINS
    )
    domain_ids = tuple(item.step_id for item in domain_steps)
    graph_recipe = GraphRecipeRegistration(
        recipe_ref="pack-recipe://large-scale-production/multi-domain-fanout-fanin@1.0.0",
        steps=(
            GraphRecipeStepRegistration("requirements", by_name["requirements"]),
            *domain_steps,
            GraphRecipeStepRegistration("integration", by_name["integrate"], domain_ids),
            GraphRecipeStepRegistration("build", by_name["build"], ("integration",)),
            GraphRecipeStepRegistration(
                "runtime-validation",
                by_name["runtime-validation"],
                ("build",),
            ),
            GraphRecipeStepRegistration(
                "performance-validation",
                by_name["performance-validation"],
                ("build",),
            ),
            GraphRecipeStepRegistration(
                "package",
                by_name["package"],
                ("build", "performance-validation", "runtime-validation"),
            ),
        ),
    )
    branch_metadata = {item.domain: item for item in large_scale_graph_recipe().branches}
    bindings: dict[str, tuple[str, ...]] = {}
    for capability in capabilities:
        common = ("adapter://artifact/v1", "adapter://resource/v1")
        if capability.name.startswith("domain."):
            domain = capability.name.split(".", 1)[1]
            branch_adapters = (
                (*common, "adapter://filesystem/v1", "adapter://workspace/v1")
                if domain == "audio"
                else common
            )
            bindings[capability.capability_ref.value] = tuple(
                sorted(
                    (
                        *branch_adapters,
                        branch_metadata[domain].implementation_ref,
                    )
                )
            )
        elif capability.name in {"runtime-validation", "performance-validation"}:
            bindings[capability.capability_ref.value] = tuple(
                sorted((*common, "adapter://validation/v1"))
            )
        elif capability.name == "requirements":
            bindings[capability.capability_ref.value] = (
                "adapter://artifact/v1",
                "adapter://project/v1",
            )
        else:
            bindings[capability.capability_ref.value] = tuple(
                sorted((*common, "adapter://workspace/v1"))
            )
    profiles = {
        item.capability_ref.value: (
            branch_metadata[item.name.split(".", 1)[1]].resource_profile_ref
            if item.name.startswith("domain.")
            else f"project-config://production/resource/{item.name}"
        )
        for item in capabilities
    }
    validators = tuple(
        ValidatorRegistration(
            registration_ref=f"pack-validator://large-scale-production/{name}@1.0.0",
            capability_ref=by_name[name],
            validator_ref=f"validation-check://production/{name}/v1",
            required=True,
        )
        for name in ("integrate", "build", "runtime-validation", "performance-validation", "package")
    )
    return ProductionPack(
        pack_ref=ProductionPackRef("large-scale-production", _VERSION),
        capability_definitions=capabilities,
        graph_recipes=(graph_recipe,),
        validators=validators,
        artifact_roles=tuple(
            [f"production.component.{domain}" for domain in _DOMAIN_ORDER]
            + [
                "production.build.output",
                "production.integration.manifest",
                "production.integration.output",
                "production.package.output",
                "production.validation.result",
            ]
        ),
        adapter_bindings=bindings,
        resource_profiles=profiles,
        created_at=_CREATED_AT,
    )


def _node_ref(graph_ref: GraphRef, step_id: str) -> NodeRef:
    node_id = "nod_" + hashlib.sha256(
        f"{graph_ref.graph_id}\x00{step_id}".encode()
    ).hexdigest()[:32]
    return NodeRef(graph_ref, node_id)


def _freeze_branch_inputs(
    graph_ref: GraphRef,
    branch_inputs: Mapping[str, ArtifactRef] | None,
) -> Mapping[str, ArtifactRef]:
    if branch_inputs is None:
        return MappingProxyType({})
    if not isinstance(branch_inputs, Mapping):
        raise GraphContractError("branch_inputs must be a mapping")
    copied = dict(branch_inputs)
    if set(copied) - set(_BRANCH_DOMAINS):
        raise GraphContractError("branch_inputs contains an unsupported domain")
    if not all(isinstance(value, ArtifactRef) for value in copied.values()):
        raise GraphContractError("branch_inputs must contain exact ArtifactRef values")
    if any(value.project_ref != graph_ref.project_ref for value in copied.values()):
        raise GraphContractError("branch_inputs crossed Project scope")
    return MappingProxyType(dict(sorted(copied.items())))


def _freeze_branch_capability_grants(
    branch_capability_grants: Mapping[str, Sequence[CapabilityRef]] | None,
) -> Mapping[str, tuple[CapabilityRef, ...]]:
    if branch_capability_grants is None:
        return MappingProxyType({})
    if not isinstance(branch_capability_grants, Mapping):
        raise GraphContractError("branch_capability_grants must be a mapping")
    copied = dict(branch_capability_grants)
    if set(copied) - set(_BRANCH_DOMAINS):
        raise GraphContractError(
            "branch_capability_grants contains an unsupported domain"
        )
    frozen: dict[str, tuple[CapabilityRef, ...]] = {}
    for domain, values in copied.items():
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise GraphContractError(
                "branch_capability_grants values must be capability sequences"
            )
        capabilities = tuple(values)
        if len(capabilities) > 32 or not all(
            isinstance(item, CapabilityRef) for item in capabilities
        ):
            raise GraphContractError(
                "branch_capability_grants are malformed or unbounded"
            )
        frozen[domain] = tuple(sorted(set(capabilities)))
    return MappingProxyType(dict(sorted(frozen.items())))


def compile_large_scale_graph_nodes(
    *,
    graph_ref: GraphRef,
    task_ref: TaskRef,
    run_ref: RunRef,
    branch_inputs: Mapping[str, ArtifactRef] | None = None,
    branch_capability_grants: Mapping[
        str,
        Sequence[CapabilityRef],
    ]
    | None = None,
) -> tuple[Node, ...]:
    """Compile the exact recipe into normal revision-local Graph Nodes."""

    if not isinstance(graph_ref, GraphRef):
        raise TypeError("graph_ref must be GraphRef")
    if not isinstance(task_ref, TaskRef) or not isinstance(run_ref, RunRef):
        raise GraphContractError("Exact TaskRef and RunRef are required")
    if task_ref.project_ref != graph_ref.project_ref or run_ref.project_ref != graph_ref.project_ref:
        raise GraphContractError("Production recipe identities crossed Project scope")
    exact_inputs = _freeze_branch_inputs(graph_ref, branch_inputs)
    capability_grants = _freeze_branch_capability_grants(
        branch_capability_grants
    )
    recipe = large_scale_graph_recipe()
    requirements_ref = _node_ref(graph_ref, "requirements")
    requirements = Node(
        requirements_ref,
        "PRODUCTION_REQUIREMENTS",
        (CapabilityRef("production.requirements", _VERSION),),
        (),
        (),
        {"requirements": "biella://contracts/production-requirements/v1"},
        None,
        "READ_ONLY",
        {"resource.profile_ref": "project-config://production/resource/requirements"},
        ("project.configuration.exact",),
    )
    branches: list[Node] = []
    for branch in recipe.branches:
        ref = _node_ref(graph_ref, f"domain-{branch.domain}")
        inputs: list[NodeInputBinding] = [
            NodeInputBinding.from_node_output(
                "requirements",
                requirements_ref,
                "requirements",
            )
        ]
        branch_input = exact_inputs.get(branch.domain)
        if branch_input is not None:
            inputs.append(
                NodeInputBinding.from_identity(
                    "branch_input",
                    graph_ref.project_ref,
                    branch_input,
                )
            )
        branches.append(
            Node(
                ref,
                "PRODUCTION_DOMAIN_" + branch.domain.upper().replace("-", "_"),
                (branch.capability_ref, *capability_grants.get(branch.domain, ())),
                (requirements_ref,),
                tuple(inputs),
                {"component": "biella://contracts/production-component-artifact/v1"},
                None,
                "PROJECT_WRITE",
                {
                    "production.domain": branch.domain,
                    "production.implementation_ref": branch.implementation_ref,
                    "production.reality": branch.reality.value,
                    "resource.profile_ref": branch.resource_profile_ref,
                },
                ("component.artifact.exact", "component.reality.explicit"),
            )
        )
    branch_refs = {branch.domain: node.node_ref for branch, node in zip(recipe.branches, branches)}
    integration_ref = _node_ref(graph_ref, "integration")
    integration = Node(
        integration_ref,
        "PRODUCTION_INTEGRATE",
        (CapabilityRef("production.integrate", _VERSION),),
        tuple(branch_refs.values()),
        tuple(
            NodeInputBinding.from_node_output(
                f"component_{domain}",
                branch_refs[domain],
                "component",
            )
            for domain in _BRANCH_DOMAINS
        ),
        {"integration": "biella://contracts/production-integration-output/v1"},
        None,
        "PROJECT_WRITE",
        {"resource.profile_ref": "project-config://production/resource/integrate"},
        ("components.exact", "artifact.selection.unambiguous"),
    )
    build_ref = _node_ref(graph_ref, "build")
    build = Node(
        build_ref,
        "PRODUCTION_BUILD",
        (CapabilityRef("production.build", _VERSION),),
        (integration_ref,),
        (NodeInputBinding.from_node_output("integration", integration_ref, "integration"),),
        {"build": "biella://contracts/production-build-output/v1"},
        None,
        "PROJECT_WRITE",
        {"resource.profile_ref": "project-config://production/resource/build"},
        ("build.integrated.exact",),
    )
    runtime_ref = _node_ref(graph_ref, "runtime-validation")
    performance_ref = _node_ref(graph_ref, "performance-validation")
    runtime = Node(
        runtime_ref,
        "PRODUCTION_RUNTIME_VALIDATION",
        (CapabilityRef("production.runtime-validation", _VERSION),),
        (build_ref,),
        (NodeInputBinding.from_node_output("build", build_ref, "build"),),
        {"validation": "biella://contracts/production-validation-result/v1"},
        None,
        "READ_ONLY",
        {"resource.profile_ref": "project-config://production/resource/runtime-validation"},
        ("runtime.observed",),
    )
    performance = Node(
        performance_ref,
        "PRODUCTION_PERFORMANCE_VALIDATION",
        (CapabilityRef("production.performance-validation", _VERSION),),
        (build_ref,),
        (NodeInputBinding.from_node_output("build", build_ref, "build"),),
        {"validation": "biella://contracts/production-validation-result/v1"},
        None,
        "READ_ONLY",
        {"resource.profile_ref": "project-config://production/resource/performance-validation"},
        ("performance.project-defined",),
    )
    package_ref = _node_ref(graph_ref, "package")
    package = Node(
        package_ref,
        "PRODUCTION_PACKAGE",
        (CapabilityRef("production.package", _VERSION),),
        (build_ref, runtime_ref, performance_ref),
        (
            NodeInputBinding.from_node_output("build", build_ref, "build"),
            NodeInputBinding.from_node_output("runtime_validation", runtime_ref, "validation"),
            NodeInputBinding.from_node_output(
                "performance_validation",
                performance_ref,
                "validation",
            ),
        ),
        {"package": "biella://contracts/production-package-output/v1"},
        None,
        "PROJECT_WRITE",
        {
            "production.implementation_ref": _PACKAGE_IMPLEMENTATION_REF,
            "production.reality": ProductionComponentReality.REAL.value,
            "resource.profile_ref": "project-config://production/resource/package",
        },
        ("package.validated.exact",),
    )
    nodes: Sequence[Node] = (
        requirements,
        *branches,
        integration,
        build,
        runtime,
        performance,
        package,
    )
    return tuple(nodes)
