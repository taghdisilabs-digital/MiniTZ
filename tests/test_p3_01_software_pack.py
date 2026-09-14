"""P3-01 software ProductionPack and real repository acceptance tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import minitz_os.engine as minitz_engine
import pytest
from minitz_os.engine import (
    ArtifactService,
    Capability,
    CapabilityConflictError,
    CapabilityNotFoundError,
    CapabilityRef,
    CapabilityRegistry,
    FilesystemAdapter,
    FilesystemMode,
    FilesystemObjectStorageBackend,
    FilesystemScope,
    GitAdapter,
    GraphRecipeRegistration,
    GraphRef,
    GraphService,
    NetworkPolicy,
    Node,
    NodeExecutionService,
    NodeRef,
    ProcessExecutionRequest,
    ProcessStatus,
    ProductionPack,
    ProductionPackConflictError,
    ProductionPackIntegrityError,
    ProductionPackNotFoundError,
    ProductionPackRef,
    ProductionPackRegistry,
    ProjectStore,
    ProjectValidationCriteria,
    RunService,
    TaskRevisionService,
    ValidationCheck,
    ValidationContractError,
    ValidationService,
    ValidationVerdict,
    ValidatorRegistration,
    WorkspaceNetworkPolicy,
    WorkspaceRepositorySource,
    WorkspaceRootGrant,
    WorkspaceService,
    WorkspaceType,
    software_production_pack,
)


SOFTWARE_CAPABILITIES = {
    f"software.{name}"
    for name in (
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
}


def test_t01_public_pack_interfaces_and_software_descriptor_are_exact_data() -> None:
    assert {
        "GraphRecipeRegistration",
        "ProductionPack",
        "ProductionPackRef",
        "ProductionPackRegistry",
        "ValidatorRegistration",
        "software_production_pack",
    }.issubset(set(minitz_engine.__all__))

    pack = software_production_pack()
    assert pack.pack_ref == ProductionPackRef("software", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == SOFTWARE_CAPABILITIES
    assert set(pack.adapter_bindings) == {item.capability_ref.value for item in pack.capability_definitions}
    assert all(pack.adapter_bindings[key] for key in pack.adapter_bindings)
    bound_adapters = {
        reference
        for references in pack.adapter_bindings.values()
        for reference in references
    }
    assert {
        "adapter://context-retrieval/v1",
        "adapter://git/v1",
        "adapter://model/v1",
        "adapter://process/v1",
        "adapter://validation/v1",
        "adapter://workspace/v1",
    } <= bound_adapters
    assert "adapter://artifact/v1" in pack.adapter_bindings[
        CapabilityRef("software.build", "1.0.0").value
    ]
    assert "workspace.process.execute" in next(
        item
        for item in pack.capability_definitions
        if item.capability_id == "software.debug"
    ).side_effects
    assert pack.graph_recipe_refs
    assert pack.validator_refs
    assert pack.resource_profiles
    assert "source.candidate" in pack.artifact_roles
    assert pack.semantic_digest == software_production_pack().semantic_digest
    assert not hasattr(minitz, "SoftwareTask")
    assert not hasattr(minitz, "SoftwareRun")
    assert not hasattr(minitz, "CodeAgentManager")


def test_t02_pack_registration_is_durable_idempotent_and_immutable(tmp_path: Path) -> None:
    database = tmp_path / "packs.sqlite3"
    pack = software_production_pack()
    registry = ProductionPackRegistry(database)
    registered = registry.register(pack, idempotency_key="software-pack-v1")
    replay = registry.register(pack, idempotency_key="software-pack-v1")

    assert replay == registered
    assert registry.get(pack.pack_ref) == registered
    assert registry.list_packs() == (registered,)
    capabilities = CapabilityRegistry(database)
    assert {
        capabilities.get(CapabilityRef(capability_id, "1.0.0")).capability_id
        for capability_id in SOFTWARE_CAPABILITIES
    } == SOFTWARE_CAPABILITIES

    with pytest.raises(ProductionPackConflictError):
        registry.register(
            replace(pack, pack_ref=ProductionPackRef("software", "1.0.1")),
            idempotency_key="software-pack-v1",
        )
    with sqlite3.connect(database) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE production_packs SET semantic_digest=? WHERE pack_id=? AND version=?",
            ("0" * 64, "software", "1.0.0"),
        )


def test_t02_atomic_pack_registration_rolls_back_partial_capabilities(
    tmp_path: Path,
) -> None:
    database = tmp_path / "atomic-packs.sqlite3"
    registry = ProductionPackRegistry(database)
    software = registry.register(
        software_production_pack(),
        idempotency_key="atomic-software",
    )
    inserted_first = Capability(
        CapabilityRef("atomic.first", "1.0.0"),
        "Must roll back when a later Capability conflicts",
    )
    conflicting_later = replace(
        next(
            item
            for item in software.capability_definitions
            if item.capability_id == "software.inspect"
        ),
        description="Conflicting immutable inspection contract",
    )
    atomic = ProductionPack(
        ProductionPackRef("atomic", "1.0.0"),
        (inserted_first, conflicting_later),
        (),
        (),
        ("atomic.result",),
        {
            inserted_first.capability_ref.value: ("adapter://atomic/first",),
            conflicting_later.capability_ref.value: ("adapter://atomic/conflict",),
        },
        {
            inserted_first.capability_ref.value: "resource-profile://atomic/default",
            conflicting_later.capability_ref.value: "resource-profile://atomic/default",
        },
    )

    with pytest.raises(CapabilityConflictError):
        registry.register(atomic, idempotency_key="atomic-failing-pack")
    with pytest.raises(CapabilityNotFoundError):
        CapabilityRegistry(database).get(inserted_first.capability_ref)
    with pytest.raises(ProductionPackNotFoundError):
        registry.get(atomic.pack_ref)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM production_pack_idempotency "
            "WHERE idempotency_key='atomic-failing-pack'"
        ).fetchone() == (0,)


def test_t02_existing_pack_replay_rejects_missing_capability_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing-pack-capability.sqlite3"
    registry = ProductionPackRegistry(database)
    pack = software_production_pack()
    registry.register(pack, idempotency_key="software-original")
    missing = pack.capability_definitions[0].capability_ref

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER capabilities_no_delete")
        connection.execute(
            "DELETE FROM capabilities WHERE capability_id=? AND version=?",
            (missing.capability_id, missing.version),
        )

    with pytest.raises(ProductionPackIntegrityError, match="Capability"):
        registry.register(pack, idempotency_key="software-after-capability-loss")
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM production_pack_idempotency "
            "WHERE idempotency_key='software-after-capability-loss'"
        ).fetchone() == (0,)


def test_t02_concurrent_pack_conflict_has_one_winner_and_no_loser_footprint(
    tmp_path: Path,
) -> None:
    database = tmp_path / "concurrent-packs.sqlite3"
    registry = ProductionPackRegistry(database)

    def candidate(name: str) -> ProductionPack:
        capability = Capability(
            CapabilityRef(f"concurrent.{name}", "1.0.0"),
            f"Concurrent candidate {name}",
        )
        return ProductionPack(
            ProductionPackRef(f"concurrent-{name}", "1.0.0"),
            (capability,),
            (),
            (),
            (f"concurrent.{name}.result",),
            {
                capability.capability_ref.value: (
                    f"adapter://concurrent/{name}",
                )
            },
            {
                capability.capability_ref.value: (
                    f"resource-profile://concurrent/{name}"
                )
            },
        )

    candidates = (candidate("alpha"), candidate("beta"))

    def register(pack: ProductionPack) -> ProductionPack | Exception:
        try:
            return registry.register(pack, idempotency_key="concurrent-one-winner")
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(register, candidates))
    winners = tuple(item for item in outcomes if isinstance(item, ProductionPack))
    conflicts = tuple(
        item for item in outcomes if isinstance(item, ProductionPackConflictError)
    )
    assert len(winners) == 1
    assert len(conflicts) == 1
    winner = winners[0]
    loser = next(item for item in candidates if item.pack_ref != winner.pack_ref)
    assert registry.get(winner.pack_ref) == winner
    with pytest.raises(ProductionPackNotFoundError):
        registry.get(loser.pack_ref)
    with pytest.raises(CapabilityNotFoundError):
        CapabilityRegistry(database).get(
            loser.capability_definitions[0].capability_ref
        )


def test_t03_recipes_and_validator_bindings_are_optional_pack_data_not_a_global_hierarchy() -> None:
    pack = software_production_pack()
    assert all(isinstance(item, GraphRecipeRegistration) for item in pack.graph_recipes)
    assert all(isinstance(item, ValidatorRegistration) for item in pack.validators)
    assert any(
        {item.capability_ref.capability_id for item in recipe.steps}
        == {"software.inspect", "software.modify", "software.test"}
        for recipe in pack.graph_recipes
    )
    assert not any("critic" in item.registration_ref for item in pack.validators)
    assert not any("critic" in recipe.recipe_ref for recipe in pack.graph_recipes)
    assert all(not item.required for item in pack.validators)


def test_t04_project_software_configuration_remains_project_scoped_data(tmp_path: Path) -> None:
    database = tmp_path / "project-config.sqlite3"
    projects = ProjectStore(database)
    alpha_architecture = f"config://sha256/{'a' * 64}"
    alpha_tests = f"config://sha256/{'b' * 64}"
    beta_architecture = f"config://sha256/{'c' * 64}"
    beta_tests = f"config://sha256/{'d' * 64}"
    alpha = projects.create_project(
        namespace="software-alpha",
        display_name="Software Alpha",
        configuration_refs={
            "software.architecture": alpha_architecture,
            "software.test": alpha_tests,
        },
    )
    beta = projects.create_project(
        namespace="software-beta",
        display_name="Software Beta",
        configuration_refs={
            "software.architecture": beta_architecture,
            "software.test": beta_tests,
        },
    )
    ProductionPackRegistry(database).register(
        software_production_pack(),
        idempotency_key="software-pack-projects",
    )

    assert projects.resolve_configuration(
        alpha.access,
        alpha.project.project_ref,
        "software.architecture",
    ) == alpha_architecture
    assert projects.resolve_configuration(
        beta.access,
        beta.project.project_ref,
        "software.architecture",
    ) == beta_architecture
    with pytest.raises(minitz_engine.ProjectScopeError):
        projects.resolve_configuration(
            beta.access,
            alpha.project.project_ref,
            "software.architecture",
        )


def _git(path: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_EMAIL": "software-pack@example.invalid",
            "GIT_AUTHOR_NAME": "Software Pack Test",
            "GIT_COMMITTER_EMAIL": "software-pack@example.invalid",
            "GIT_COMMITTER_NAME": "Software Pack Test",
        }
    )
    result = subprocess.run(
        ("/usr/bin/git", *arguments),
        cwd=path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_t05_real_repository_debug_repair_build_runtime_recovery_and_isolation(
    tmp_path: Path,
) -> None:
    source_root_path = tmp_path / "source-root"
    source_path = source_root_path / "demo"
    candidate_root_path = tmp_path / "candidate-root"
    source_path.mkdir(parents=True)
    candidate_root_path.mkdir()
    _git(source_path, "init", "--initial-branch=main")
    (source_path / ".gitignore").write_text(
        "__pycache__/\ndist/\n",
        encoding="utf-8",
    )
    (source_path / "app.py").write_text(
        "def greet(name: str) -> str:\n"
        "    return f\"Hello {name}?\"\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    print(greet(\"MiniTZ\"))\n",
        encoding="utf-8",
    )
    (source_path / "test_app.py").write_text(
        "import unittest\n\n"
        "from app import greet\n\n\n"
        "class GreetingTest(unittest.TestCase):\n"
        "    def test_exact_greeting(self) -> None:\n"
        "        self.assertEqual(greet(\"MiniTZ\"), \"Hello, MiniTZ!\")\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (source_path / "build.py").write_text(
        "from pathlib import Path\n\n"
        "source = Path(\"app.py\").read_bytes()\n"
        "output = Path(\"dist/software-demo.bundle\")\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_bytes(b\"MINITZ-SOFTWARE-PACK\\n\" + source)\n"
        "print(output.as_posix())\n",
        encoding="utf-8",
    )
    _git(source_path, "add", "--all")
    _git(source_path, "commit", "-m", "controlled failing fixture")
    base_commit = _git(source_path, "rev-parse", "HEAD^{commit}")
    base_tree = _git(source_path, "rev-parse", "HEAD^{tree}")
    (source_path / "local-notes.txt").write_text(
        "unrelated dirty source must remain\n",
        encoding="utf-8",
    )
    source_status = _git(source_path, "status", "--porcelain=v1")
    beta_source_root_path = tmp_path / "beta-source-root"
    beta_source_path = beta_source_root_path / "demo"
    beta_source_path.mkdir(parents=True)
    _git(beta_source_path, "init", "--initial-branch=main")
    (beta_source_path / "app.py").write_text(
        "print('Beta project source')\n",
        encoding="utf-8",
    )
    _git(beta_source_path, "add", "--all")
    _git(beta_source_path, "commit", "-m", "independent beta fixture")
    beta_base_commit = _git(beta_source_path, "rev-parse", "HEAD^{commit}")
    beta_base_tree = _git(beta_source_path, "rev-parse", "HEAD^{tree}")

    database = tmp_path / "software-e2e.sqlite3"
    projects = ProjectStore(database)
    alpha = projects.create_project(
        namespace="software-e2e-alpha",
        display_name="Software E2E Alpha",
        configuration_refs={"software.test": f"config://sha256/{'1' * 64}"},
    )
    beta = projects.create_project(
        namespace="software-e2e-beta",
        display_name="Software E2E Beta",
        configuration_refs={"software.test": f"config://sha256/{'2' * 64}"},
    )
    registered_pack = ProductionPackRegistry(database).register(
        software_production_pack(),
        idempotency_key="software-e2e-pack",
    )
    production_recipe = next(
        recipe
        for recipe in registered_pack.graph_recipes
        if recipe.recipe_ref
        == "pack-recipe://software/production-repair@1.0.0"
    )
    assert tuple(step.step_id for step in production_recipe.steps) == (
        "inspect",
        "debug",
        "modify",
        "test",
        "build",
        "run",
        "validate",
    )
    software_capabilities = tuple(
        step.capability_ref for step in production_recipe.steps
    )
    objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    filesystem = FilesystemAdapter(database, objects)
    git = GitAdapter(database, objects)
    model = minitz_engine.ReferenceModelAdapter(database, objects)
    model_runtime = minitz_engine.ModelRuntimeIdentity(
        model.adapter_ref,
        "runtime://python/p3-01-reference",
        "p3-01-generation-1",
        "provider://minitz/reference",
        "model://minitz/p3-01-reference",
        "p3-01-v1",
        None,
        (),
        "REFERENCE",
    )
    model_deployment = model.register_deployment(
        alpha.access,
        minitz_engine.ModelDeployment(
            minitz_engine.ModelDeploymentRef.new(alpha.project.project_ref),
            model.adapter_ref,
            model_runtime.provider_ref,
            model_runtime.model_ref,
            model_runtime.model_revision,
            None,
            None,
            (
                minitz_engine.ModelOperation.EMBED,
                minitz_engine.ModelOperation.INFER,
                minitz_engine.ModelOperation.RERANK,
            ),
            ("text",),
            4096,
            True,
            False,
            8,
            (),
            (),
            (),
            False,
            model_runtime,
        ),
        idempotency_key="software-model-deployment",
    )
    capabilities = tuple(
        sorted(
            (
                *filesystem.register_capabilities(alpha.access),
                *git.process.register_capabilities(alpha.access),
                *git.register_capabilities(alpha.access),
                *model.register_capabilities(alpha.access, model_deployment),
                *software_capabilities,
            )
        )
    )
    beta_capabilities = tuple(
        sorted(
            (
                *filesystem.register_capabilities(beta.access),
                *git.process.register_capabilities(beta.access),
                *git.register_capabilities(beta.access),
            )
        )
    )
    task = TaskRevisionService(database).create_task(
        alpha.access,
        project_ref=alpha.project.project_ref,
        idempotency_key="software-e2e-task",
        task_type="software.debug",
        objective="Repair the exact greeting defect and prove candidate behavior",
        required_capabilities=capabilities,
        input_refs=(),
        output_contract={"candidate": "schema://minitz/software-candidate/1"},
        constraints={
            "validation.build_required": True,
            "validation.runtime_required": True,
        },
        side_effect_authority="EXTERNAL_SIDE_EFFECT",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=("artifact", "build", "content-ref", "runtime", "test"),
        acceptance_criteria=("validation.success_rule=ALL_REQUIRED_PASS",),
        resource_hints={
            "resource_profile_ref": registered_pack.resource_profiles[
                CapabilityRef("software.debug", "1.0.0").value
            ]
        },
    )
    runs = RunService(database)
    run = runs.create_run(alpha.access, task_ref=task.task_ref)
    run_attempt = runs.acquire_run_lease(
        alpha.access,
        run.run_ref,
        owner_ref="controller://software-pack-e2e",
        lease_seconds=1800,
    )
    graph_ref = GraphRef.new(alpha.project.project_ref)
    node = Node(
        NodeRef.new(graph_ref),
        "TOOL",
        capabilities,
        (),
        (),
        dict(task.output_contract),
        None,
        "EXTERNAL_SIDE_EFFECT",
        {},
        task.evidence_requirements,
    )
    GraphService(database).create_graph(
        alpha.access,
        graph_ref=graph_ref,
        task_ref=task.task_ref,
        expected_task_digest=task.canonical_digest,
        run_ref=run.run_ref,
        nodes=(node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=run_attempt,
    )
    executions = NodeExecutionService(database)
    executions.prepare_run(alpha.access, run.run_ref)
    attempt = executions.lease_node(
        alpha.access,
        node.node_ref,
        authority_attempt=run_attempt,
        owner_ref="executor://software-pack-e2e",
        lease_seconds=1800,
        idempotency_key="software-e2e-lease",
    )
    executions.start_node(
        alpha.access,
        attempt,
        idempotency_key="software-e2e-start",
    )
    beta_task = TaskRevisionService(database).create_task(
        beta.access,
        project_ref=beta.project.project_ref,
        idempotency_key="software-e2e-beta-task",
        task_type="software.inspect",
        objective="Inspect only the independent beta repository",
        required_capabilities=beta_capabilities,
        input_refs=(),
        output_contract={"inspection": "schema://minitz/repository-inspection/1"},
        constraints={},
        side_effect_authority="PROJECT_WRITE",
        data_policy_ref=None,
        egress_policy_ref=None,
        evidence_requirements=("artifact", "content-ref"),
        acceptance_criteria=(),
        resource_hints={},
    )
    beta_runs = RunService(database)
    beta_run = beta_runs.create_run(beta.access, task_ref=beta_task.task_ref)
    beta_run_attempt = beta_runs.acquire_run_lease(
        beta.access,
        beta_run.run_ref,
        owner_ref="controller://software-pack-beta",
        lease_seconds=1800,
    )
    beta_graph_ref = GraphRef.new(beta.project.project_ref)
    beta_node = Node(
        NodeRef.new(beta_graph_ref),
        "TOOL",
        beta_capabilities,
        (),
        (),
        dict(beta_task.output_contract),
        None,
        "PROJECT_WRITE",
        {},
        beta_task.evidence_requirements,
    )
    GraphService(database).create_graph(
        beta.access,
        graph_ref=beta_graph_ref,
        task_ref=beta_task.task_ref,
        expected_task_digest=beta_task.canonical_digest,
        run_ref=beta_run.run_ref,
        nodes=(beta_node,),
        compiler_identity=None,
        compiler_version=None,
        authority_attempt=beta_run_attempt,
    )
    beta_executions = NodeExecutionService(database)
    beta_executions.prepare_run(beta.access, beta_run.run_ref)
    beta_attempt = beta_executions.lease_node(
        beta.access,
        beta_node.node_ref,
        authority_attempt=beta_run_attempt,
        owner_ref="executor://software-pack-beta",
        lease_seconds=1800,
        idempotency_key="software-beta-lease",
    )
    beta_executions.start_node(
        beta.access,
        beta_attempt,
        idempotency_key="software-beta-start",
    )
    source_root = filesystem.register_root(
        alpha.access,
        path=source_root_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=False,
        idempotency_key="software-source-root",
    )
    candidate_root = filesystem.register_root(
        alpha.access,
        path=candidate_root_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=True,
        idempotency_key="software-candidate-root",
    )
    beta_source_root = filesystem.register_root(
        beta.access,
        path=beta_source_root_path,
        scope=FilesystemScope.PROJECT,
        mode=FilesystemMode.READ_WRITE,
        allow_remove=False,
        idempotency_key="software-beta-source-root",
    )
    repository = git.register_repository(
        alpha.access,
        attempt,
        root_ref=source_root.root_ref,
        relative_path="demo",
        expected_commit_sha=base_commit,
        expected_tree_sha=base_tree,
        idempotency_key="software-register-repository",
    )
    beta_repository = git.register_repository(
        beta.access,
        beta_attempt,
        root_ref=beta_source_root.root_ref,
        relative_path="demo",
        expected_commit_sha=beta_base_commit,
        expected_tree_sha=beta_base_tree,
        idempotency_key="software-register-beta-repository",
    )
    beta_inspection = git.inspect(
        beta.access,
        beta_attempt,
        beta_repository,
        idempotency_key="software-inspect-beta-repository",
    )
    assert (beta_inspection.head_commit_sha, beta_inspection.head_tree_sha) == (
        beta_base_commit,
        beta_base_tree,
    )
    inspection = git.inspect(
        alpha.access,
        attempt,
        repository,
        idempotency_key="software-inspect-repository",
    )
    assert (inspection.head_commit_sha, inspection.head_tree_sha) == (
        base_commit,
        base_tree,
    )
    assert inspection.untracked_paths == ("local-notes.txt",)
    focused_source = filesystem.read(
        alpha.access,
        attempt,
        root_ref=source_root.root_ref,
        path="demo/app.py",
        media_type="text/x-python",
        idempotency_key="software-read-focused-source",
    )
    retrieval = minitz_engine.RetrievalService(database, objects)
    index = retrieval.buildIndex(
        alpha.access,
        attempt,
        minitz_engine.IndexBuildRequest(
            "software-focused-source",
            (focused_source.artifact_ref,),
            "unicode-fixed-v1",
            256,
            True,
            model_deployment,
            model.capability_ref(minitz_engine.ModelOperation.EMBED),
            "software-focused-index-v1",
        ),
        model,
        credentials={},
    )
    assert index.index.state is minitz_engine.RetrievalIndexState.READY
    assert len(index.chunks) == 1
    retrieval_receipt = retrieval.search(
        alpha.access,
        attempt,
        minitz_engine.RetrievalSearchRequest(
            "software-focused-source",
            "greeting punctuation defect",
            (focused_source.artifact_ref,),
            1,
            True,
            model_deployment,
            model.capability_ref(minitz_engine.ModelOperation.EMBED),
            model_deployment,
            model.capability_ref(minitz_engine.ModelOperation.RERANK),
            None,
            "software-focused-search-v1",
        ),
        model,
        credentials={},
    )
    assert retrieval_receipt.source_scope == (focused_source.artifact_ref,)
    run_memory = minitz_engine.RunMemoryService(database).reconstruct(
        alpha.access,
        attempt.run_ref,
    )
    context_manifest, context_receipt = minitz_engine.ContextCompiler(
        database,
        objects,
    ).compileContext(
        alpha.access,
        attempt,
        minitz_engine.ContextCompileRequest(
            (focused_source.artifact_ref,),
            (),
            (),
            run_memory,
            (retrieval_receipt.receipt_ref,),
            (),
            (focused_source.artifact_ref,),
            minitz_engine.ContextBudget(2048, 128),
            minitz_engine.ContextReductionPolicy.EXCLUDE_OPTIONAL,
            (),
            (),
            "software-focused-context-v1",
        ),
    )
    assert context_manifest.retrieval_scope == (focused_source.artifact_ref.value,)
    assert context_receipt.context_ref is not None
    focused_context = objects.read(context_receipt.context_ref)
    assert b"def greet" in focused_context
    assert b"test_exact_greeting" not in focused_context
    assert b"MINITZ-SOFTWARE-PACK" not in focused_context

    workspaces = WorkspaceService(database, objects, filesystem, git)
    policy = workspaces.create_policy(
        alpha.access,
        root_grants=(WorkspaceRootGrant(candidate_root.root_ref, "READ_WRITE"),),
        network_policy=WorkspaceNetworkPolicy.NONE,
        allowed_capabilities=capabilities,
        side_effect_boundary="PROJECT_WRITE",
        timeout_seconds=1800,
        process_limit=32,
        idempotency_key="software-workspace-policy",
    )
    workspace = workspaces.create_workspace(
        alpha.access,
        attempt,
        workspace_type=WorkspaceType.REPOSITORY,
        base_sources=(WorkspaceRepositorySource(repository),),
        execution_policy_ref=policy.policy_ref,
        candidate_root_ref=candidate_root.root_ref,
        relative_path="candidate",
        idempotency_key="software-create-workspace",
    )
    materialized = workspaces.materialize(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        idempotency_key="software-materialize-workspace",
    )
    assert materialized.repository_workspace_ref is not None
    candidate_path = candidate_root_path / "candidate"
    python_executable = str(Path(sys.executable).resolve())

    def process_request(*arguments: str) -> ProcessExecutionRequest:
        return ProcessExecutionRequest(
            alpha.project.project_ref,
            candidate_root.root_ref,
            "candidate",
            python_executable,
            tuple(arguments),
            network_policy=NetworkPolicy.INHERIT,
        )

    failing_test = git.process.execute(
        alpha.access,
        attempt,
        process_request("-m", "unittest", "-q"),
        idempotency_key="software-test-red",
    )
    assert failing_test.status is ProcessStatus.FAILED
    assert failing_test.exit_code == 1
    assert "Hello MiniTZ?" in objects.read(failing_test.stderr_ref).decode("utf-8")
    assert git.process.get_result(alpha.access, failing_test.tool_call_ref) == failing_test

    patch_ref = objects.put(
        b"diff --git a/app.py b/app.py\n"
        b"--- a/app.py\n"
        b"+++ b/app.py\n"
        b"@@ -1,5 +1,5 @@\n"
        b" def greet(name: str) -> str:\n"
        b"-    return f\"Hello {name}?\"\n"
        b"+    return f\"Hello, {name}!\"\n"
        b" \n"
        b" \n"
        b" if __name__ == \"__main__\":\n",
        media_type="text/x-diff",
    )
    changed = git.apply_patch(
        alpha.access,
        attempt,
        materialized.repository_workspace_ref,
        patch_ref=patch_ref,
        expected_commit_sha=base_commit,
        idempotency_key="software-apply-repair",
    )
    candidate_diff = objects.read(changed.unstaged_diff_ref)
    assert candidate_diff.count(b"diff --git") == 1
    assert b"diff --git a/app.py b/app.py" in candidate_diff
    workspaces.record_tool_call(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        changed.tool_call_ref,
        network_used=False,
    )
    passing_test = git.process.execute(
        alpha.access,
        attempt,
        process_request("-m", "unittest", "-q"),
        idempotency_key="software-test-green",
    )
    assert passing_test.status is ProcessStatus.SUCCEEDED
    workspaces.record_tool_call(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        passing_test.tool_call_ref,
        network_used=False,
    )
    committed = git.commit(
        alpha.access,
        attempt,
        materialized.repository_workspace_ref,
        expected_parent_commit_sha=base_commit,
        message="Repair exact greeting",
        author_name="Software Pack Test",
        author_email="software-pack@example.invalid",
        idempotency_key="software-commit-candidate",
    )
    workspaces.record_tool_call(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        committed.tool_call_ref,
        network_used=False,
    )
    assert committed.parent_commit_sha == base_commit
    assert committed.commit_sha == _git(candidate_path, "rev-parse", "HEAD^{commit}")
    assert committed.tree_sha == _git(candidate_path, "rev-parse", "HEAD^{tree}")

    build = git.process.execute(
        alpha.access,
        attempt,
        process_request("build.py"),
        idempotency_key="software-build",
    )
    assert build.status is ProcessStatus.SUCCEEDED
    assert build.exit_code == 0
    assert "dist/software-demo.bundle" in build.stdout_preview
    workspaces.record_tool_call(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        build.tool_call_ref,
        network_used=False,
    )
    build_read = filesystem.read(
        alpha.access,
        attempt,
        root_ref=candidate_root.root_ref,
        path="candidate/dist/software-demo.bundle",
        media_type="application/vnd.minitz_engine.software-bundle",
        idempotency_key="software-read-build-output",
    )
    workspaces.record_tool_call(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        build_read.tool_call_ref,
        network_used=False,
    )
    artifacts = ArtifactService(database)
    unbound_build_artifact = artifacts.create_artifact(
        alpha.access,
        project_ref=alpha.project.project_ref,
        role="software.build.output",
        content_ref=build_read.output_ref,
        source_refs=(),
        source_artifact_refs=(build.artifact_ref, build_read.artifact_ref),
        source_content_refs=(build.result_ref, build_read.output_ref),
        derivation_type="software.build.capture",
        metadata={
            "media_type": build_read.output_ref.media_type,
            "schema_ref": "schema://minitz/software-build-output/1",
        },
    )
    runtime = git.process.execute(
        alpha.access,
        attempt,
        process_request("app.py"),
        idempotency_key="software-runtime",
    )
    assert runtime.status is ProcessStatus.SUCCEEDED
    assert objects.read(runtime.stdout_ref) == b"Hello, MiniTZ!\n"
    workspaces.record_tool_call(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        runtime.tool_call_ref,
        network_used=False,
    )

    receipt = workspaces.capture(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        test_artifact_refs=(failing_test.artifact_ref, passing_test.artifact_ref),
        idempotency_key="software-capture-candidate",
    )
    assert receipt.repository_head_commit == committed.commit_sha
    assert receipt.repository_head_tree == committed.tree_sha
    assert set(receipt.test_artifact_refs) == {
        failing_test.artifact_ref,
        passing_test.artifact_ref,
    }
    assert _git(source_path, "status", "--porcelain=v1") == source_status
    wrong_candidate_artifact = artifacts.create_revision(
        alpha.access,
        prior_ref=unbound_build_artifact.artifact_ref,
        role="software.build.output",
        content_ref=build_read.output_ref,
        source_refs=(),
        source_artifact_refs=(unbound_build_artifact.artifact_ref,),
        source_content_refs=(build.result_ref, build_read.output_ref),
        derivation_type="software.build.unbound-candidate",
        metadata={
            "media_type": build_read.output_ref.media_type,
            "schema_ref": "schema://minitz/software-build-output/1",
        },
    )
    build_artifact = artifacts.create_revision(
        alpha.access,
        prior_ref=wrong_candidate_artifact.artifact_ref,
        role="software.build.output",
        content_ref=build_read.output_ref,
        source_refs=(),
        source_artifact_refs=(
            wrong_candidate_artifact.artifact_ref,
            receipt.snapshot_artifact_ref,
        ),
        source_content_refs=(build.result_ref, build_read.output_ref),
        derivation_type="software.build.bind-candidate",
        metadata={
            "media_type": build_read.output_ref.media_type,
            "schema_ref": "schema://minitz/software-build-output/1",
        },
    )
    assert receipt.snapshot_artifact_ref in build_artifact.source_artifact_refs
    unplanned_provenanced_artifact = artifacts.create_revision(
        alpha.access,
        prior_ref=build_artifact.artifact_ref,
        role="software.build.output",
        content_ref=build_read.output_ref,
        source_refs=(),
        source_artifact_refs=(
            build_artifact.artifact_ref,
            receipt.snapshot_artifact_ref,
        ),
        source_content_refs=(build.result_ref, build_read.output_ref),
        derivation_type="software.build.unplanned-provenance",
        metadata={
            "media_type": build_read.output_ref.media_type,
            "schema_ref": "schema://minitz/software-build-output/1",
        },
    )

    legacy_material = json.dumps(
        [
            "software-reconstruct-candidate",
            "write",
            "dist/software-demo.bundle",
        ],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    legacy_reconstruction_key = (
        "workspace-"
        + hashlib.sha256(legacy_material.encode()).hexdigest()[:48]
    )
    legacy_child_write = filesystem.write(
        alpha.access,
        attempt,
        root_ref=candidate_root.root_ref,
        path="candidate/dist/software-demo.bundle",
        content_ref=build_read.output_ref,
        idempotency_key=legacy_reconstruction_key,
    )
    assert legacy_child_write.payload["schema_version"] == 1

    shutil.rmtree(candidate_path)
    restarted_objects = FilesystemObjectStorageBackend(tmp_path / "objects")
    restarted_filesystem = FilesystemAdapter(database, restarted_objects)
    restarted_git = GitAdapter(database, restarted_objects)
    restarted_workspaces = WorkspaceService(
        database,
        restarted_objects,
        restarted_filesystem,
        restarted_git,
    )
    restored = restarted_workspaces.reconstruct(
        alpha.access,
        attempt,
        workspace.workspace_ref,
        idempotency_key="software-reconstruct-candidate",
    )
    assert restored.repository_workspace_ref is not None
    assert (candidate_path / "dist/software-demo.bundle").stat().st_mode & 0o7777 == 0o644
    versioned_material = json.dumps(
        [
            "software-reconstruct-candidate",
            "write-mode-v2",
            "dist/software-demo.bundle",
        ],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    versioned_reconstruction_key = (
        "workspace-"
        + hashlib.sha256(versioned_material.encode()).hexdigest()[:48]
    )
    assert versioned_reconstruction_key != legacy_reconstruction_key
    with sqlite3.connect(database) as connection:
        request_row = connection.execute(
            """
            SELECT request_digest, request_size, request_media_type
            FROM filesystem_operation_claims
            WHERE project_id=? AND node_attempt_id=? AND idempotency_key=?
            """,
            (
                alpha.project.project_ref.value,
                attempt.attempt_id,
                versioned_reconstruction_key,
            ),
        ).fetchone()
    assert request_row is not None
    versioned_request = minitz_engine.ContentRef(
        "sha256",
        request_row[0],
        request_row[1],
        request_row[2],
    )
    assert json.loads(restarted_objects.read(versioned_request))[
        "schema_version"
    ] == 2
    assert _git(candidate_path, "rev-parse", "HEAD^{commit}") == committed.commit_sha
    assert _git(candidate_path, "rev-parse", "HEAD^{tree}") == committed.tree_sha
    assert restarted_git.process.get_result(
        alpha.access,
        passing_test.tool_call_ref,
    ) == passing_test
    assert restarted_git.process.get_result(
        alpha.access,
        failing_test.tool_call_ref,
    ) == failing_test
    assert restarted_git.process.get_result(
        alpha.access,
        runtime.tool_call_ref,
    ) == runtime
    assert ArtifactService(database).get_artifact(
        alpha.access,
        build_artifact.artifact_ref,
    ) == build_artifact
    assert build_artifact.content_ref is not None
    assert restarted_objects.read(build_artifact.content_ref) == (
        b"MINITZ-SOFTWARE-PACK\n"
        b"def greet(name: str) -> str:\n"
        b"    return f\"Hello, {name}!\"\n\n\n"
        b"if __name__ == \"__main__\":\n"
        b"    print(greet(\"MiniTZ\"))\n"
    )
    assert restarted_workspaces.get_receipt(alpha.access, receipt.snapshot_ref) == receipt
    with pytest.raises(minitz_engine.GitScopeError):
        restarted_git.get_repository(beta.access, repository)
    with pytest.raises(minitz_engine.GitScopeError):
        restarted_git.get_repository(alpha.access, beta_repository)
    with pytest.raises(minitz_engine.WorkspaceScopeError):
        restarted_workspaces.get_workspace(beta.access, workspace.workspace_ref)

    validation = ValidationService(database)
    criteria = ProjectValidationCriteria(
        alpha.project.project_ref,
        (
            ValidationCheck(
                CapabilityRef("validation.build", "1.0.0"),
                True,
                next(
                    item.registration_ref
                    for item in registered_pack.validators
                    if item.capability_ref.capability_id == "software.build"
                ),
                ("artifact",),
                parameters={
                    "artifact_role": "software.build.output",
                    "source_artifact_ref": receipt.snapshot_artifact_ref.value,
                },
            ),
        ),
        f"config://sha256/{'3' * 64}",
    )
    plan = validation.compile_plan(
        alpha.access,
        attempt,
        subjects=(
            validation.bind_artifact_subject(alpha.access, build_artifact.artifact_ref),
            validation.bind_artifact_subject(
                alpha.access,
                wrong_candidate_artifact.artifact_ref,
            ),
            validation.bind_tool_call_subject(alpha.access, passing_test.tool_call_ref),
            validation.bind_workspace_subject(alpha.access, receipt.snapshot_ref),
        ),
        project_criteria=criteria,
        idempotency_key="software-validation-plan",
    )
    role_check = next(
        item
        for item in plan.checks
        if item.parameters.get("artifact_role") == "software.build.output"
    )
    with pytest.raises(ValidationContractError, match="role"):
        validation.record_result(
            alpha.access,
            attempt,
            plan.plan_ref,
            check_id=role_check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://software/build-output",
            runtime_ref="runtime://software/local-cpu",
            evidence_refs=(build.artifact_ref.value,),
            idempotency_key="software-wrong-build-artifact",
        )
    with pytest.raises(ValidationContractError, match="subject"):
        validation.record_result(
            alpha.access,
            attempt,
            plan.plan_ref,
            check_id=role_check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://software/build-output",
            runtime_ref="runtime://software/local-cpu",
            evidence_refs=(unbound_build_artifact.artifact_ref.value,),
            idempotency_key="software-unbound-build-artifact",
        )
    with pytest.raises(ValidationContractError, match="provenance"):
        validation.record_result(
            alpha.access,
            attempt,
            plan.plan_ref,
            check_id=role_check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://software/build-output",
            runtime_ref="runtime://software/local-cpu",
            evidence_refs=(wrong_candidate_artifact.artifact_ref.value,),
            idempotency_key="software-wrong-candidate-build-artifact",
        )
    with pytest.raises(ValidationContractError, match="provenance"):
        validation.record_result(
            alpha.access,
            attempt,
            plan.plan_ref,
            check_id=role_check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref="validator://software/build-output",
            runtime_ref="runtime://software/local-cpu",
            evidence_refs=(
                wrong_candidate_artifact.artifact_ref.value,
                unplanned_provenanced_artifact.artifact_ref.value,
            ),
            idempotency_key="software-split-subject-provenance-artifacts",
        )
    evidence_by_capability = {
        "validation.build": build_artifact.artifact_ref.value,
        "validation.runtime": runtime.artifact_ref.value,
        "validation.test": passing_test.artifact_ref.value,
    }
    for check in plan.checks:
        validation.record_result(
            alpha.access,
            attempt,
            plan.plan_ref,
            check_id=check.check_id,
            verdict=ValidationVerdict.PASS,
            validator_kind="DETERMINISTIC",
            implementation_ref=f"validator://software/{check.capability_ref.capability_id}",
            runtime_ref="runtime://software/local-cpu",
            evidence_refs=(
                evidence_by_capability.get(
                    check.capability_ref.capability_id,
                    receipt.snapshot_artifact_ref.value,
                ),
            ),
            idempotency_key=f"software-result-{check.check_id}",
        )
    aggregate = validation.aggregate(
        alpha.access,
        attempt,
        plan.plan_ref,
        idempotency_key="software-validation-aggregate",
    )
    assert aggregate.verdict is ValidationVerdict.PASS
    assert aggregate.accepted


def test_t06_no_domain_specific_kernel_or_placeholder_escape_hatches() -> None:
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / "src/minitz_os/engine/production_pack.py",
            root / "src/minitz_os/engine/software_pack.py",
        )
    )
    active_runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "src/minitz").rglob("*.py"))
        if path.name != "migration.py"
    )
    tests = Path(__file__).read_text(encoding="utf-8")
    assert "class SoftwareTask" not in active_runtime
    assert "class SoftwareRun" not in active_runtime
    assert "class CodeAgentManager" not in active_runtime
    assert "QuarantineRef" not in active_runtime
    assert "pytest.mark." + "skip" not in tests
    assert "pytest.mark." + "xfail" not in tests
    assert "Not" + "Implemented" not in source
    assert "TO" + "DO" not in source
