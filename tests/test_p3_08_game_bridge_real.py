"""REAL Blender-to-Game bridge qualification over exact Artifact bindings."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

from minitz_os.engine import (
    ArtifactRef,
    ArtifactService,
    GameEngineOperation,
    GameEngineReality,
    GameEngineStatus,
    GameRuntimeInputBinding,
    ProjectRef,
)
from minitz_os.engine.artifact import ContentRef
from minitz_os.engine.game_engine import GameAssetInput
import minitz_os.engine.game_engine as game_engine


NOT_RUN_GODOT = (
    "P3-08 REAL bridge NOT_RUN: exact local Godot 4.3 container image is unavailable"
)
NOT_RUN_BLENDER = (
    "P3-08 REAL bridge NOT_RUN: local Blender executable is unavailable"
)


def _p3_03_support() -> Any:
    name = "p3_03_game_bridge_support"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).with_name("test_p3_03_game_real.py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _content_payload(content_ref: ContentRef) -> dict[str, object]:
    return {
        "algorithm": content_ref.algorithm,
        "digest": content_ref.digest,
        "media_type": content_ref.media_type,
        "size_bytes": content_ref.size_bytes,
    }


def _artifact(
    env: Any,
    role: str,
    content: bytes,
    media_type: str,
    derivation: str,
) -> Any:
    content_ref = env.objects.put(content, media_type=media_type)
    return ArtifactService(env.database).create_artifact(
        env.access,
        project_ref=env.access.project_ref,
        role=role,
        content_ref=content_ref,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(content_ref,),
        derivation_type=derivation,
        metadata={"media_type": media_type},
    )


def _binding(
    artifact: Any,
    runtime_path: str,
    *,
    role: str | None = None,
    content_ref: ContentRef | None = None,
) -> Any:
    binding_type = getattr(game_engine, "GameRuntimeInputBinding", None)
    assert binding_type is not None, "Game runtime Artifact binding seam is missing"
    assert GameRuntimeInputBinding is binding_type
    assert artifact.content_ref is not None
    return binding_type(
        artifact.artifact_ref,
        artifact.role if role is None else role,
        artifact.content_ref if content_ref is None else content_ref,
        runtime_path,
    )


def _require_godot_runtime(support: Any) -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip(NOT_RUN_GODOT)
    available = subprocess.run(
        (docker, "image", "inspect", support.IMAGE_REF),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
    if available.returncode != 0:
        pytest.skip(NOT_RUN_GODOT)


def _detect(env: Any, support: Any) -> None:
    detection_spec = replace(
        support._spec(env, "true"),
        entrypoint=env.identity.engine_executable_path,
        args=env.identity.engine_version_args,
        working_directory="/tmp",
        outputs=(),
        environment={},
    )
    detected = env.adapter.detect_project(
        env.access,
        env.primary_attempt,
        support._request(
            env,
            GameEngineOperation.DETECT,
            detection_spec,
            "game.engine.detection",
        ),
        idempotency_key="p3-08-environment-detect",
    )
    assert detected.reality is GameEngineReality.REAL
    assert detected.status is GameEngineStatus.SUCCEEDED


def _blender_environment_bytes(tmp_path: Path) -> bytes:
    blender = shutil.which("blender")
    if blender is None:
        pytest.skip(NOT_RUN_BLENDER)
    output = tmp_path / "p3-08-blender-environment.glb"
    source = tmp_path / "p3-08-blender-environment.blend"
    generator = tmp_path / "p3-08-generate-environment.py"
    generator.write_text(
        f'''import bpy

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def material(name, color):
    value = bpy.data.materials.new(name=name)
    value.diffuse_color = (*color, 1.0)
    return value

def cube(name, location, scale, selected_material=None):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    value = bpy.context.object
    value.name = name
    value.scale = scale
    if selected_material is not None:
        value.data.materials.append(selected_material)
    return value

terrain_material = material("TerrainMaterial", (0.18, 0.42, 0.16))
foliage_material = material("FoliageMaterial", (0.08, 0.28, 0.07))
rock_material = material("RockMaterial", (0.32, 0.34, 0.36))

terrain = cube("Terrain", (0.0, 0.0, -0.5), (8.0, 8.0, 0.5), terrain_material)
terrain["minitz_partition"] = "terrain"
placed = cube("PlacedTree", (4.0, -2.0, 1.0), (1.5, 2.0, 0.75), foliage_material)
placed["minitz_material_ref"] = "material://environment/foliage"
placed["minitz_partition"] = "north"
cube("Terrain-col", (0.0, 0.0, -0.5), (8.0, 8.0, 0.5), None)

bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0.0, 0.0, 0.01))
navigation = bpy.context.object
navigation.name = "Navigation-navmesh"
navigation["minitz_navigation"] = "walkable"

cube("Rock_LOD0", (-3.0, 2.0, 0.6), (1.0, 1.0, 1.0), rock_material)
cube("Rock_LOD1", (-3.0, 2.0, 0.6), (0.65, 0.65, 0.65), rock_material)

bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
partition = bpy.context.object
partition.name = "Partition_north"
partition["minitz_partition"] = "north"

bpy.ops.wm.save_as_mainfile(filepath={os.fspath(source)!r})
bpy.ops.export_scene.gltf(
    filepath={os.fspath(output)!r},
    export_format="GLB",
    export_extras=True,
    export_apply=False,
)
print("MINITZ_P3_08_BLENDER_EXPORT=" + {os.fspath(output)!r})
''',
        encoding="utf-8",
    )
    completed = subprocess.run(
        (
            blender,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python",
            os.fspath(generator),
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"MINITZ_P3_08_BLENDER_EXPORT={output}" in completed.stdout
    payload = output.read_bytes()
    assert payload[:4] == b"glTF" and len(payload) > 1_000
    return payload


def _runtime_script() -> bytes:
    return b'''extends SceneTree

const INPUT_ROOT := "/run/minitz/game-inputs/"

func _walk(node: Node, nodes: Array[Node]) -> void:
    nodes.append(node)
    for child in node.get_children():
        _walk(child, nodes)

func _find(nodes: Array[Node], fragment: String) -> Node:
    for node in nodes:
        if fragment.to_lower() in String(node.name).to_lower():
            return node
    return null

func _input_file_count() -> int:
    var directory := DirAccess.open(INPUT_ROOT)
    assert(directory != null)
    var count := 0
    directory.list_dir_begin()
    var name := directory.get_next()
    while name != "":
        if not directory.current_is_dir():
            count += 1
        name = directory.get_next()
    directory.list_dir_end()
    return count

func _init() -> void:
    var manifest = JSON.parse_string(
        FileAccess.get_file_as_string(INPUT_ROOT + "bindings.json")
    )
    assert(manifest is Dictionary)
    var bindings: Array = manifest["bindings"]
    var exact_bindings := bindings.size() == 2 and _input_file_count() == 3
    var paths := {}
    for binding in bindings:
        var runtime_path := String(binding["runtime_path"])
        var content: Dictionary = binding["content_ref"]
        paths[runtime_path] = true
        exact_bindings = exact_bindings and FileAccess.file_exists(INPUT_ROOT + runtime_path)
        exact_bindings = exact_bindings and FileAccess.get_sha256(INPUT_ROOT + runtime_path) == content["digest"]
        exact_bindings = exact_bindings and binding["artifact_role"] == "game.asset.environment.input"
    exact_bindings = exact_bindings and paths.has("environment.glb") and paths.has("validate_bridge.gd")

    var packed := load("res://evidence/bridge/environment.glb") as PackedScene
    assert(packed != null)
    var environment: Node = packed.instantiate()
    var nodes: Array[Node] = []
    _walk(environment, nodes)
    var placed := _find(nodes, "PlacedTree") as Node3D
    var transform_valid := placed != null and placed.position.length() > 0.1
    var scale_valid := placed != null and placed.scale.distance_to(Vector3.ONE) > 0.1
    var material_valid := false
    if placed is MeshInstance3D:
        var mesh_instance := placed as MeshInstance3D
        if mesh_instance.mesh != null:
            for surface in range(mesh_instance.mesh.get_surface_count()):
                var selected_material := mesh_instance.get_active_material(surface)
                if selected_material != null and "FoliageMaterial" in selected_material.resource_name:
                    material_valid = true
    var collision_runtime := false
    var navigation_runtime := false
    for node in nodes:
        collision_runtime = collision_runtime or node is StaticBody3D or node is CollisionShape3D
        navigation_runtime = navigation_runtime or node is NavigationRegion3D
    var lod_valid := _find(nodes, "LOD0") != null and _find(nodes, "LOD1") != null
    var partition_valid := _find(nodes, "Partition_north") != null
    var valid := (
        exact_bindings
        and transform_valid
        and scale_valid
        and material_valid
        and collision_runtime
        and navigation_runtime
        and lod_valid
        and partition_valid
    )
    DirAccess.make_dir_recursive_absolute("res://evidence/run")
    var output := FileAccess.open("res://evidence/run/runtime.json", FileAccess.WRITE)
    output.store_string(JSON.stringify({
        "valid": valid,
        "project_ref": manifest["project_ref"],
        "bindings": bindings,
        "exact_bindings": exact_bindings,
        "position": [] if placed == null else [placed.position.x, placed.position.y, placed.position.z],
        "scale": [] if placed == null else [placed.scale.x, placed.scale.y, placed.scale.z],
        "transform_valid": transform_valid,
        "scale_valid": scale_valid,
        "material_valid": material_valid,
        "collision_runtime": collision_runtime,
        "navigation_runtime": navigation_runtime,
        "lod_valid": lod_valid,
        "partition_valid": partition_valid,
    }))
    output.close()
    print("MINITZ_P3_08_EXACT_BLENDER_ENVIRONMENT_CONSUMED")
    quit(0 if valid else 1)
'''


def test_runtime_input_binding_contract_is_exact_and_digest_bound() -> None:
    binding_type = getattr(game_engine, "GameRuntimeInputBinding", None)
    assert binding_type is not None, "Game runtime Artifact binding seam is missing"
    project_ref = ProjectRef.new()
    artifact_ref = ArtifactRef(project_ref, "art_" + "1" * 32, 7)
    content_ref = ContentRef.from_bytes(
        b"exact environment bytes",
        media_type="model/gltf-binary",
    )
    binding = binding_type(
        artifact_ref,
        "game.asset.environment.input",
        content_ref,
        "environment.glb",
    )
    assert binding.payload() == {
        "artifact_ref": artifact_ref.value,
        "artifact_role": "game.asset.environment.input",
        "content_ref": _content_payload(content_ref),
        "runtime_path": "environment.glb",
    }
    assert binding.container_path == "/run/minitz/game-inputs/environment.glb"


def test_real_adapter_fails_result_for_invalid_runtime_artifact_bindings(
    tmp_path: Path,
) -> None:
    support = _p3_03_support()
    _require_godot_runtime(support)
    env = support._environment(tmp_path)
    _detect(env, support)

    exported = _artifact(
        env,
        "game.asset.environment.input",
        b"exact Blender GLB placeholder for binding validation",
        "model/gltf-binary",
        "p3-08.binding-export",
    )
    assert exported.content_ref is not None
    updated_content = env.objects.put(
        b"newer exact Blender GLB placeholder",
        media_type="model/gltf-binary",
    )
    updated = ArtifactService(env.database).create_revision(
        env.access,
        prior_ref=exported.artifact_ref,
        role=exported.role,
        content_ref=updated_content,
        source_refs=(),
        source_artifact_refs=(exported.artifact_ref,),
        source_content_refs=(exported.content_ref, updated_content),
        derivation_type="p3-08.binding-export-revision",
        metadata={"media_type": "model/gltf-binary"},
    )
    wrong_role = _artifact(
        env,
        "game.asset.image.input",
        b"wrong role bytes",
        "image/png",
        "p3-08.binding-wrong-role",
    )
    extra = _artifact(
        env,
        "game.asset.environment.input",
        b"extra authorized-looking bytes",
        "application/octet-stream",
        "p3-08.binding-extra",
    )
    forged_content = env.objects.put(
        b"forged substitute",
        media_type="model/gltf-binary",
    )
    missing_ref = ArtifactRef(
        env.access.project_ref,
        "art_" + "f" * 32,
        1,
    )
    missing_artifact = replace(exported, artifact_ref=missing_ref)
    valid = _binding(exported, "environment.glb")
    cases = (
        (
            "forged",
            (GameAssetInput("environment", exported.artifact_ref),),
            (_binding(exported, "environment.glb", content_ref=forged_content),),
        ),
        (
            "missing",
            (GameAssetInput("environment", missing_ref),),
            (_binding(missing_artifact, "environment.glb"),),
        ),
        (
            "stale",
            (GameAssetInput("environment", updated.artifact_ref),),
            (valid,),
        ),
        (
            "role",
            (GameAssetInput("environment", wrong_role.artifact_ref),),
            (_binding(wrong_role, "environment.glb", role="game.asset.environment.input"),),
        ),
        (
            "omitted",
            (GameAssetInput("environment", exported.artifact_ref),),
            (),
        ),
        (
            "extra",
            (GameAssetInput("environment", exported.artifact_ref),),
            (valid, _binding(extra, "extra.bin")),
        ),
    )
    for label, assets, bindings in cases:
        spec = support._spec(
            env,
            "mkdir -p evidence/run; printf invalid > evidence/run/invalid.json",
            outputs=(("evidence/run/invalid.json", "application/json"),),
        )
        request = replace(
            support._request(
                env,
                GameEngineOperation.IMPORT,
                spec,
                "game.import.output",
            ),
            asset_inputs=assets,
            runtime_input_bindings=bindings,
        )
        result = env.adapter.import_project(
            env.access,
            env.primary_attempt,
            request,
            idempotency_key=f"p3-08-invalid-binding-{label}",
        )
        assert result.reality is GameEngineReality.REAL
        assert result.status is GameEngineStatus.FAILED
        assert result.output_artifact_refs == ()
        assert result.failure_reason is not None and label in result.failure_reason


def test_real_game_consumes_exact_blender_exported_environment_artifact(
    tmp_path: Path,
) -> None:
    support = _p3_03_support()
    _require_godot_runtime(support)
    env = support._environment(tmp_path)
    export_bytes = _blender_environment_bytes(tmp_path)
    script_bytes = _runtime_script()
    exported = _artifact(
        env,
        "game.asset.environment.input",
        export_bytes,
        "model/gltf-binary",
        "p3-08.blender-environment-export",
    )
    validator = _artifact(
        env,
        "game.asset.environment.input",
        script_bytes,
        "application/x-gdscript",
        "p3-08.godot-environment-consumer",
    )
    assert exported.content_ref is not None and validator.content_ref is not None
    assets = (
        GameAssetInput("environment", exported.artifact_ref),
        GameAssetInput("environment", validator.artifact_ref),
    )
    bindings = (
        _binding(exported, "environment.glb"),
        _binding(validator, "validate_bridge.gd"),
    )
    _detect(env, support)

    import_spec = support._spec(
        env,
        "set -euo pipefail; cleanup(){ rm -rf evidence/bridge; }; trap cleanup EXIT; "
        "rm -rf evidence/bridge evidence/run; "
        "mkdir -p evidence/bridge evidence/run; "
        "cp /run/minitz/game-inputs/environment.glb evidence/bridge/environment.glb; "
        "godot --headless --path . --editor --quit; "
        "cp /run/minitz/game-inputs/bindings.json evidence/run/import.json; "
        "rm -rf evidence/bridge",
        outputs=(("evidence/run/import.json", "application/json"),),
    )
    import_request = replace(
        support._request(
            env,
            GameEngineOperation.IMPORT,
            import_spec,
            "game.import.output",
            required_output_markers=("Godot Engine",),
        ),
        asset_inputs=assets,
        runtime_input_bindings=bindings,
    )
    imported = env.adapter.import_project(
        env.access,
        env.primary_attempt,
        import_request,
        idempotency_key="p3-08-blender-environment-import",
    )
    assert imported.reality is GameEngineReality.REAL
    assert imported.status is GameEngineStatus.SUCCEEDED, imported.failure_reason
    imported_artifact = env.artifacts.get_artifact(
        env.access,
        imported.output_artifact_refs[0],
    )
    assert set(artifact.artifact_ref for artifact in (exported, validator)) <= set(
        imported_artifact.source_artifact_refs
    )
    imported_manifest = json.loads(
        support._output_bytes(env, imported, "game.import.output")
    )
    assert imported_manifest["project_ref"] == env.access.project_ref.value
    assert imported_manifest["bindings"] == [
        {
            "artifact_ref": exported.artifact_ref.value,
            "artifact_role": exported.role,
            "content_ref": _content_payload(exported.content_ref),
            "kind": "environment",
            "runtime_path": "environment.glb",
        },
        {
            "artifact_ref": validator.artifact_ref.value,
            "artifact_role": validator.role,
            "content_ref": _content_payload(validator.content_ref),
            "kind": "environment",
            "runtime_path": "validate_bridge.gd",
        },
    ]

    build_request = support._request(
        env,
        GameEngineOperation.BUILD,
        support._spec(
            env,
            "set -euo pipefail; mkdir -p dist; "
            "godot --headless --path . --export-pack 'Linux/X11' dist/minitz-game.pck; "
            "test -s dist/minitz-game.pck",
            outputs=(("dist/minitz-game.pck", "application/octet-stream"),),
        ),
        "game.build.output",
    )
    built = env.adapter.build(
        env.access,
        env.primary_attempt,
        build_request,
        idempotency_key="p3-08-blender-environment-build",
    )
    assert built.reality is GameEngineReality.REAL
    assert built.status is GameEngineStatus.SUCCEEDED, built.failure_reason

    run_spec = support._spec(
        env,
        "set -euo pipefail; cleanup(){ rm -rf evidence/bridge; }; trap cleanup EXIT; "
        "rm -rf evidence/bridge; mkdir -p evidence/bridge; "
        "cp /run/minitz/game-inputs/environment.glb evidence/bridge/environment.glb; "
        "cp /run/minitz/game-inputs/validate_bridge.gd evidence/bridge/validate_bridge.gd; "
        "godot --headless --path . --editor --quit; "
        "godot --headless --path . --script res://evidence/bridge/validate_bridge.gd; "
        "rm -rf evidence/bridge",
        outputs=(("evidence/run/runtime.json", "application/json"),),
    )
    run_request = replace(
        support._request(
            env,
            GameEngineOperation.RUN,
            run_spec,
            "game.runtime.observation",
            build_artifact_ref=built.output_artifact_refs[0],
            required_output_markers=(
                "MINITZ_P3_08_EXACT_BLENDER_ENVIRONMENT_CONSUMED",
            ),
        ),
        asset_inputs=assets,
        runtime_input_bindings=bindings,
    )
    ran = env.adapter.run(
        env.access,
        env.primary_attempt,
        run_request,
        idempotency_key="p3-08-blender-environment-run",
    )
    assert ran.reality is GameEngineReality.REAL
    assert ran.status is GameEngineStatus.SUCCEEDED, ran.failure_reason
    assert ran.runtime_observed
    runtime_artifact = env.artifacts.get_artifact(
        env.access,
        ran.output_artifact_refs[0],
    )
    assert set(artifact.artifact_ref for artifact in (exported, validator)) <= set(
        runtime_artifact.source_artifact_refs
    )
    runtime = json.loads(
        support._output_bytes(env, ran, "game.runtime.observation")
    )
    assert runtime["valid"] is True
    assert runtime["project_ref"] == env.access.project_ref.value
    for key in (
        "exact_bindings",
        "transform_valid",
        "scale_valid",
        "material_valid",
        "collision_runtime",
        "navigation_runtime",
        "lod_valid",
        "partition_valid",
    ):
        assert runtime[key] is True
    assert len(runtime["position"]) == 3
    assert len(runtime["scale"]) == 3
    assert all(math.isfinite(float(value)) for value in runtime["position"])
    assert all(
        math.isfinite(float(value)) and float(value) > 0.0
        for value in runtime["scale"]
    )
    by_path = {item["runtime_path"]: item for item in runtime["bindings"]}
    assert by_path["environment.glb"]["artifact_ref"] == exported.artifact_ref.value
    assert by_path["environment.glb"]["content_ref"]["digest"] == _sha256(
        export_bytes
    )
    assert by_path["validate_bridge.gd"]["artifact_ref"] == validator.artifact_ref.value
    assert by_path["validate_bridge.gd"]["content_ref"]["digest"] == _sha256(
        script_bytes
    )
