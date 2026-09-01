"""Real Blender environment evidence on the accepted 3D substrate."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from threading import Barrier
from typing import Any, cast

import pytest

from biella.three_d_tool import (
    ThreeDEnvironmentLayoutSpec,
    ThreeDContractError,
    ThreeDOperation,
    ThreeDPlacedAssetSpec,
    ThreeDScopeError,
)
from biella.environment_pack import (
    EnvironmentContractError,
    EnvironmentIntegrationManifest,
    EnvironmentSpecification,
    PlacedAsset,
    ProceduralTerrain,
)
from biella.artifact import ArtifactRef


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_08_environment_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest(env: Any, request: Any, result: Any, report: dict[str, Any]) -> EnvironmentIntegrationManifest:
    assert result.output_artifact_ref is not None and result.output_content_ref is not None
    layout = request.environment_spec
    assert layout is not None
    output_ref = result.output_artifact_ref.value
    output_digest = result.output_content_ref.digest
    specification = EnvironmentSpecification(
        project_ref=env.access.project_ref, environment_id="forest-test", source_ref=output_ref,
        content_sha256=output_digest, units="meters",
        coordinates={"up": "z", "handedness": "right"}, layout={"kind": "grid"},
        gameplay_navigation={"agent": "generic"}, visual={"style": "natural"},
        asset_library_refs=tuple(item.artifact_ref.value for item in layout.placed_assets),
        target_tool_engine={"tool": "blender"}, performance={"lod": "2"},
        partition={"strategy": "generic"}, output_acceptance_refs=("acceptance://environment/forest",),
        representation_tags=("tag://environment/editable",),
    )
    terrain = ProceduralTerrain(
        project_ref=env.access.project_ref, terrain_id="forest-terrain",
        generator_ref=f"generator://three-d/{layout.generator}", generator_version=layout.generator_version,
        config={key: str(value) for key, value in layout.generator_config.items()}, seed=layout.seed,
        terrain_ref=output_ref, content_sha256=output_digest,
    )
    reported_assets = report["environment_identity"]["placed_assets"]
    assets = tuple(
        PlacedAsset(
            project_ref=env.access.project_ref, asset_id=item.asset_id, source_ref=item.artifact_ref.value,
            content_sha256=item.content_sha256, transform=tuple(float(value) for value in reported_assets[index]["transform"]),
            material_ref=item.material_ref, variant=item.variant, parent_ref=item.parent_ref,
            partition_id=item.partition_id,
        )
        for index, item in enumerate(layout.placed_assets)
    )
    runtime_digest = hashlib.sha256(json.dumps(report["runtime"], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return EnvironmentIntegrationManifest(
        project_ref=env.access.project_ref, specification=specification, terrain=terrain, placed_assets=assets,
        structure_ref=output_ref, prop_ref=output_ref, vegetation_ref=output_ref, material_ref=output_ref,
        collision_ref=output_ref, navigation_ref=output_ref, partition_ref=output_ref,
        tool_ref=request.identity.adapter_ref, runtime_ref=f"runtime://biella/{runtime_digest}",
        derivation_ref=f"derivation://three-d/environment/{result.record_sha256}", content_sha256=output_digest,
    )


def test_real_environment_terrain_assets_collision_navigation_lod_preview_export(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    assets = []
    for name, path in (("Rock", "environment-rock.blend"), ("Tree", "environment-tree.blend")):
        result = env.adapter.createAsset(
            env.access, env.attempt,
            support._request(env, ThreeDOperation.MODEL, source=None, source_path=None, output_path=path, output_role="3d.mesh", output_media_type="application/x-blender", config={"name": name, "unit_system": "METRIC"}),
            idempotency_key=f"environment-{name.lower()}",
        )
        assert result.output_artifact_ref is not None and result.output_content_ref is not None
        assets.append(result)
    layout = ThreeDEnvironmentLayoutSpec(
        layout_id="forest-test", generator="grid-terrain", generator_version="1.0.0", seed=42,
        generator_config={"terrain_size": 24.0},
        placed_assets=(
            ThreeDPlacedAssetSpec(assets[0].output_artifact_ref, assets[0].output_content_ref.digest, "assets/rock.blend", (2.0, 1.0, 0.0), (0.0, 0.0, 0.2), (1.0, 1.0, 1.0), "rock", "material://environment/rock", "default", None, "north"),
            ThreeDPlacedAssetSpec(assets[1].output_artifact_ref, assets[1].output_content_ref.digest, "assets/tree.blend", (-3.0, 2.0, 0.0), (0.0, 0.0, -0.3), (1.5, 1.5, 2.0), "tree", "material://environment/tree", "autumn", "parent://environment/forest", "south"),
        ),
        material_names=("terrain", "foliage"), partitions=("north", "south"), lod_levels=2,
        include_collision=True, include_navigation=True,
    )
    request = replace(
        support._request(env, ThreeDOperation.MODEL, source=None, source_path=None, output_path="environment.blend", output_role="3d.scene", output_media_type="application/x-blender"),
        operation=ThreeDOperation.ENVIRONMENT, output_role="3d.environment",
        auxiliary_artifact_bindings={"assets/rock.blend": assets[0].output_artifact_ref, "assets/tree.blend": assets[1].output_artifact_ref},
        environment_spec=layout,
    )
    result = env.adapter.executeOperation(env.access, env.attempt, request, idempotency_key="environment-main")
    assert result.editable_source and result.output_artifact_ref is not None, result.failure_reason
    report = support._report(env, result)
    assert report["environment_identity"]["layout_sha256"] == layout.semantic_digest
    assert report["environment_identity"]["placed_assets"] == [
        {
            **item,
            "transform": item["transform"],
        }
        for item in report["environment_identity"]["placed_assets"]
    ]
    assert report["environment_identity"]["placed_assets"][1]["material_ref"] == "material://environment/tree"
    assert report["environment_identity"]["placed_assets"][1]["rotation_euler"] == [0.0, 0.0, -0.3]
    assert report["environment_identity"]["placed_assets"][1]["scale"] == [1.5, 1.5, 2.0]
    reopened_source = env.adapter.inspectAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.INSPECT,
            source=result.output_artifact_ref,
            source_path="environment.blend",
            output_path="environment-source-reopen.json",
            output_role="3d.inspection",
            output_media_type="application/json",
        ),
        idempotency_key="environment-source-reopen",
    )
    reopened_environment = support._report(env, reopened_source)["inspection"]["environment"]
    assert reopened_environment["generator"]["name"] == "grid-terrain"
    assert reopened_environment["generator"]["version"] == "1.0.0"
    assert reopened_environment["generator"]["config"] == {"terrain_size": 24.0}
    assert reopened_environment["generator"]["seed"] == 42
    objects = reopened_environment["objects"]
    roles = [item["role"] for item in objects]
    assert roles.count("collision") == 1
    assert roles.count("navigation") == 1
    authoritative = {item["asset_id"]: item for item in objects if item["role"] == "placed_asset"}
    assert authoritative["rock"]["artifact_ref"] == assets[0].output_artifact_ref.value
    assert authoritative["rock"]["artifact_content_sha256"] == assets[0].output_content_ref.digest
    assert authoritative["rock"]["materials"] == ["material://environment/rock"]
    lods = [item for item in objects if item["role"] == "lod"]
    assert {item["lod_source_asset_id"] for item in lods} == {"rock", "tree"}
    assert all(item["faces"] < authoritative[item["lod_source_asset_id"]]["faces"] for item in lods)
    assert all(item["lod_source_content_sha256"] == authoritative[item["lod_source_asset_id"]]["artifact_content_sha256"] for item in lods)
    partitions = {item["partition_id"]: item for item in reopened_environment["partitions"]}
    assert partitions["north"]["asset_ids"] == ["rock"]
    assert partitions["north"]["artifact_content_sha256s"] == [assets[0].output_content_ref.digest]
    assert partitions["south"]["asset_ids"] == ["tree"]
    assert {"terrain", "foliage", "material://environment/rock", "material://environment/tree"} <= set(reopened_environment["materials"])
    manifest = _manifest(env, request, result, report)
    finalized = env.adapter.finalizeEnvironmentIntegrationManifest(env.access, request, result, manifest)
    assert finalized.manifest == manifest
    replayed_publication = type(env.adapter)(env.database, env.objects).finalizeEnvironmentIntegrationManifest(
        env.access, request, result, manifest,
    )
    assert replayed_publication == finalized
    assert type(env.adapter)(env.database, env.objects).verifyEnvironmentManifestPublication(env.access, finalized) == finalized
    with pytest.raises(EnvironmentContractError):
        env.adapter.verifyEnvironmentManifestPublication(
            env.access, replace(finalized, manifest_artifact_ref=assets[0].output_artifact_ref),
        )
    with pytest.raises(EnvironmentContractError):
        env.adapter.verifyEnvironmentManifestPublication(
            env.access, replace(finalized, manifest_content_ref=result.output_content_ref),
        )
    with pytest.raises(EnvironmentContractError):
        env.adapter.verifyEnvironmentManifestPublication(
            env.access, replace(finalized, manifest_artifact_ref=ArtifactRef(env.access.project_ref, finalized.manifest_artifact_ref.artifact_id, finalized.manifest_artifact_ref.revision + 1)),
        )
    with pytest.raises((EnvironmentContractError, ThreeDContractError)):
        env.adapter.finalizeEnvironmentIntegrationManifest(
            env.access, request, replace(result, reality=support.ThreeDReality.REFERENCE, editable_source=False), manifest,
        )
    with pytest.raises(EnvironmentContractError):
        env.adapter.finalizeEnvironmentIntegrationManifest(
            env.access, request, result, replace(manifest, content_sha256="0" * 64),
        )
    with pytest.raises(EnvironmentContractError):
        env.adapter.finalizeEnvironmentIntegrationManifest(
            env.access, request, result,
            replace(manifest, placed_assets=(replace(manifest.placed_assets[0], transform=(2.0, *manifest.placed_assets[0].transform[1:])), *manifest.placed_assets[1:])),
        )
    beta = support.ProjectStore(env.database).create_project(namespace="environment-beta", display_name="Environment Beta")
    with pytest.raises(ThreeDScopeError):
        env.adapter.executeOperation(beta.access, env.attempt, request, idempotency_key="environment-beta")
    preview = env.adapter.preview(env.access, env.attempt, support._request(env, ThreeDOperation.PREVIEW, source=result.output_artifact_ref, source_path="environment.blend", output_path="environment.png", output_role="3d.preview", output_media_type="image/png", config={"resolution": 64, "samples": 1}), idempotency_key="environment-preview")
    assert preview.preview_only
    exported = env.adapter.export(env.access, env.attempt, support._request(env, ThreeDOperation.CONVERT, source=result.output_artifact_ref, source_path="environment.blend", output_path="environment.glb", output_role="3d.interchange-export", output_media_type="model/gltf-binary"), idempotency_key="environment-export")
    reopened = env.adapter.inspectAsset(env.access, env.attempt, support._request(env, ThreeDOperation.INSPECT, source=exported.output_artifact_ref, source_path="environment.glb", output_path="environment-reopen.json", output_role="3d.inspection", output_media_type="application/json"), idempotency_key="environment-reopen")
    assert support._report(env, reopened)["inspection"]["source_format"] == "GLTF"


def test_environment_rejects_declared_digest_different_from_bound_artifact_content(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    asset = env.adapter.createAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path="digest-source.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"name": "DigestSource", "unit_system": "METRIC"},
        ),
        idempotency_key="environment-digest-source",
    )
    assert asset.output_artifact_ref is not None and asset.output_content_ref is not None
    layout = ThreeDEnvironmentLayoutSpec(
        layout_id="digest-mismatch",
        generator="grid-terrain",
        generator_version="1.0.0",
        seed=5,
        generator_config={"terrain_size": 12.0},
        placed_assets=(
            ThreeDPlacedAssetSpec(
                asset.output_artifact_ref,
                "0" * 64,
                "assets/source.blend",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                (1.0, 1.0, 1.0),
                "digest-source",
                "material://environment/source",
                "default",
                None,
                "main",
            ),
        ),
        material_names=("terrain",),
        partitions=("main",),
        lod_levels=1,
        include_collision=True,
        include_navigation=True,
    )
    request = replace(
        support._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path="digest-mismatch.blend",
            output_role="3d.scene",
            output_media_type="application/x-blender",
        ),
        operation=ThreeDOperation.ENVIRONMENT,
        output_role="3d.environment",
        auxiliary_artifact_bindings={"assets/source.blend": asset.output_artifact_ref},
        environment_spec=layout,
    )
    with pytest.raises(ThreeDContractError, match="digest differs from bound Artifact ContentRef"):
        env.adapter.executeOperation(
            env.access,
            env.attempt,
            request,
            idempotency_key="environment-digest-mismatch",
        )


def test_real_environment_terrain_geometry_is_identity_deterministic(tmp_path: Path) -> None:
    support = _support()
    env = support._environment(tmp_path)
    asset = env.adapter.createAsset(
        env.access,
        env.attempt,
        support._request(
            env,
            ThreeDOperation.MODEL,
            source=None,
            source_path=None,
            output_path="determinism-source.blend",
            output_role="3d.mesh",
            output_media_type="application/x-blender",
            config={"name": "DeterminismSource", "unit_system": "METRIC"},
        ),
        idempotency_key="environment-determinism-source",
    )
    assert asset.output_artifact_ref is not None and asset.output_content_ref is not None

    def realize(label: str, *, seed: int, terrain_size: float) -> dict[str, Any]:
        layout = ThreeDEnvironmentLayoutSpec(
            layout_id=f"determinism-{label}",
            generator="grid-terrain",
            generator_version="1.0.0",
            seed=seed,
            generator_config={"terrain_size": terrain_size},
            placed_assets=(
                ThreeDPlacedAssetSpec(
                    asset.output_artifact_ref,
                    asset.output_content_ref.digest,
                    "assets/source.blend",
                    (0.0, 0.0, 0.0),
                    (0.0, 0.0, 0.0),
                    (1.0, 1.0, 1.0),
                    "determinism-source",
                    "material://environment/source",
                    "default",
                    None,
                    "main",
                ),
            ),
            material_names=("terrain",),
            partitions=("main",),
            lod_levels=1,
            include_collision=True,
            include_navigation=True,
        )
        request = replace(
            support._request(
                env,
                ThreeDOperation.MODEL,
                source=None,
                source_path=None,
                output_path=f"{label}.blend",
                output_role="3d.scene",
                output_media_type="application/x-blender",
            ),
            operation=ThreeDOperation.ENVIRONMENT,
            output_role="3d.environment",
            auxiliary_artifact_bindings={"assets/source.blend": asset.output_artifact_ref},
            environment_spec=layout,
        )
        result = env.adapter.executeOperation(
            env.access,
            env.attempt,
            request,
            idempotency_key=f"environment-determinism-{label}",
        )
        assert result.editable_source, result.failure_reason
        return cast(dict[str, Any], support._report(env, result)["inspection"]["environment"]["generator"])

    first = realize("same-a", seed=19, terrain_size=12.0)
    second = realize("same-b", seed=19, terrain_size=12.0)
    changed_seed = realize("changed-seed", seed=20, terrain_size=12.0)
    changed_config = realize("changed-config", seed=19, terrain_size=18.0)
    assert first["terrain_geometry_sha256"] == second["terrain_geometry_sha256"]
    assert first["terrain_geometry_sha256"] != changed_seed["terrain_geometry_sha256"]
    assert first["terrain_geometry_sha256"] != changed_config["terrain_geometry_sha256"]


def test_independent_environment_branches_overlap_and_recover_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    support = _support()
    env = support._environment(tmp_path)
    asset = env.adapter.createAsset(
        env.access, env.attempt,
        support._request(env, ThreeDOperation.MODEL, source=None, source_path=None, output_path="branch-source.blend", output_role="3d.mesh", output_media_type="application/x-blender", config={"name": "BranchSource", "unit_system": "METRIC"}),
        idempotency_key="environment-branch-source",
    )
    assert asset.output_artifact_ref is not None and asset.output_content_ref is not None

    def branch_request(branch: str) -> Any:
        layout = ThreeDEnvironmentLayoutSpec(
            layout_id=f"branch-{branch}", generator="grid-terrain", generator_version="1.0.0", seed=7,
            generator_config={"terrain_size": 12.0, "branch": branch},
            placed_assets=(ThreeDPlacedAssetSpec(asset.output_artifact_ref, asset.output_content_ref.digest, "assets/source.blend", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), f"{branch}-asset", f"material://environment/{branch}", "default", None, branch),),
            material_names=(branch,), partitions=(branch,), lod_levels=1,
            include_collision=True, include_navigation=True,
        )
        return replace(
            support._request(env, ThreeDOperation.MODEL, source=None, source_path=None, output_path=f"{branch}.blend", output_role="3d.scene", output_media_type="application/x-blender"),
            operation=ThreeDOperation.ENVIRONMENT, output_role="3d.environment",
            auxiliary_artifact_bindings={"assets/source.blend": asset.output_artifact_ref}, environment_spec=layout,
        )

    requests = {branch: branch_request(branch) for branch in ("terrain", "structure", "vegetation", "material")}
    process_gate = Barrier(4)
    persist_gate = Barrier(4)
    run_process = support.ManagedProcessAdapter._run_process

    def synchronized_run_process(*args: object, **kwargs: object) -> object:
        process_gate.wait(timeout=120)
        return run_process(*args, **kwargs)

    monkeypatch.setattr(support.ManagedProcessAdapter, "_run_process", synchronized_run_process)
    adapters = {branch: type(env.adapter)(env.database, env.objects) for branch in requests}
    originals = {branch: adapter._service._persist for branch, adapter in adapters.items()}

    def persist(branch: str, *args: object, **kwargs: object) -> object:
        persist_gate.wait(timeout=120)
        if branch == "material":
            raise RuntimeError("environment worker loss after durable process")
        return originals[branch](*args, **kwargs)

    for branch, adapter in adapters.items():
        monkeypatch.setattr(adapter._service, "_persist", lambda *args, _branch=branch, **kwargs: persist(_branch, *args, **kwargs))
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            branch: executor.submit(adapter.executeOperation, env.access, env.attempt, requests[branch], idempotency_key=f"environment-branch-{branch}")
            for branch, adapter in adapters.items()
        }
        results = {branch: future.result() for branch, future in futures.items() if branch != "material"}
        with pytest.raises(RuntimeError, match="worker loss after durable process"):
            futures["material"].result()
    assert all(result.editable_source and result.output_artifact_ref is not None for result in results.values())
    failed_request = requests["material"]
    process_key = f"three-d-blender-{failed_request.request_sha256[:36]}"
    with sqlite3.connect(env.database) as connection:
        assert tuple(int(connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE call_id=(SELECT call_id FROM managed_process_claims WHERE idempotency_key=?)",
            (process_key,),
        ).fetchone()[0]) for table in ("managed_process_claims", "managed_process_prepared_executions", "managed_process_executions", "managed_process_results")) == (1, 1, 1, 1)
    recovered = type(env.adapter)(env.database, env.objects).executeOperation(
        env.access, env.attempt, failed_request, idempotency_key="environment-branch-material",
    )
    replayed = type(env.adapter)(env.database, env.objects).executeOperation(
        env.access, env.attempt, failed_request, idempotency_key="environment-branch-material",
    )
    assert recovered == replayed and recovered.editable_source
    with sqlite3.connect(env.database) as connection:
        assert int(connection.execute("SELECT COUNT(*) FROM three_d_operation_results WHERE project_id=? AND idempotency_key=?", (env.access.project_ref.value, "environment-branch-material")).fetchone()[0]) == 1
