"""Real Game-adapter bridge qualification for exact environment artifacts."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shlex
import sys
from typing import Any

import pytest

from biella import ArtifactService, GameEngineOperation, GameEngineReality, GameEngineScopeError, RuntimeMount
from biella.environment_pack import (
    EnvironmentContractError,
    EnvironmentIntegrationManifest,
    EnvironmentSpecification,
    PlacedAsset,
    ProceduralTerrain,
)
from biella.game_engine import GameAssetInput


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


def _artifact(env: Any, role: str, content: bytes, media_type: str, derivation: str) -> Any:
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


def _validate_bridge_manifest(
    payload: object,
    *,
    project_ref: str,
    expected: dict[str, tuple[str, str]],
) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("project_ref") != project_ref:
        raise ValueError("environment manifest Project scope is invalid")
    for name in ("export", "collision", "navigation"):
        item = payload.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"environment manifest {name} is missing")
        expected_ref, expected_sha = expected[name]
        if item.get("artifact_ref") != expected_ref or item.get("sha256") != expected_sha:
            raise ValueError(f"environment manifest {name} reference is forged")
    placements = payload.get("placements")
    if not isinstance(placements, list) or len(placements) != 1:
        raise ValueError("environment manifest placements are missing")
    placement = placements[0]
    if not isinstance(placement, dict):
        raise ValueError("environment manifest placement is malformed")
    transform = placement.get("transform")
    scale = placement.get("scale")
    if not isinstance(transform, list) or len(transform) != 16:
        raise ValueError("environment manifest transform is malformed")
    if not isinstance(scale, list) or len(scale) != 3:
        raise ValueError("environment manifest scale is malformed")
    try:
        transform_values = tuple(float(value) for value in transform)
        scale_values = tuple(float(value) for value in scale)
    except (TypeError, ValueError) as error:
        raise ValueError("environment manifest transform or scale is non-numeric") from error
    if not all(math.isfinite(value) for value in transform_values):
        raise ValueError("environment manifest transform is non-finite")
    if not all(math.isfinite(value) and value > 0.0 for value in scale_values):
        raise ValueError("environment manifest scale is invalid")
    return payload


def _stage(env: Any, path: str, artifact: Any, key: str) -> None:
    assert artifact.content_ref is not None
    (Path(env.control_root.canonical_path) / "inputs" / path).parent.mkdir(parents=True, exist_ok=True)
    env.filesystem.write(
        env.access,
        env.primary_attempt,
        root_ref=env.control_root.root_ref,
        path=f"inputs/{path}",
        content_ref=artifact.content_ref,
        idempotency_key=key,
        mode=0o644,
    )


def _with_bridge_inputs(env: Any, spec: Any) -> Any:
    return replace(
        spec,
        mounts=spec.mounts
        + (RuntimeMount(env.control_root.root_ref, "inputs", "/workspace/bridge-input", True),),
    )


def _runtime_script() -> bytes:
    return b'''extends SceneTree

func _finite_positive(values: Array) -> bool:
    if values.size() != 3:
        return false
    for value in values:
        var number := float(value)
        if is_nan(number) or is_inf(number) or number <= 0.0:
            return false
    return true

func _finite_transform(values: Array) -> bool:
    if values.size() != 16:
        return false
    for value in values:
        var number := float(value)
        if is_nan(number) or is_inf(number):
            return false
    return true

func _init() -> void:
    var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://evidence/bridge/environment-manifest.json"))
    assert(manifest is Dictionary)
    var export_data: Dictionary = manifest["export"]
    var collision_data: Dictionary = manifest["collision"]
    var navigation_data: Dictionary = manifest["navigation"]
    var placement: Dictionary = manifest["placements"][0]
    var packed = load("res://evidence/bridge/environment.tscn")
    assert(packed is PackedScene)
    var environment = packed.instantiate()
    var collision = environment.get_node_or_null("Collision")
    var navigation = environment.get_node_or_null("Navigation")
    var valid = (
        FileAccess.get_sha256("res://evidence/bridge/environment.tscn") == export_data["sha256"]
        and FileAccess.get_sha256("res://evidence/bridge/collision.json") == collision_data["sha256"]
        and FileAccess.get_sha256("res://evidence/bridge/navigation.json") == navigation_data["sha256"]
        and _finite_transform(placement["transform"])
        and _finite_positive(placement["scale"])
        and collision is StaticBody3D
        and navigation is NavigationRegion3D
    )
    DirAccess.make_dir_recursive_absolute("res://evidence/run")
    var output = FileAccess.open("res://evidence/run/runtime.json", FileAccess.WRITE)
    output.store_string(JSON.stringify({
        "valid": valid,
        "project_ref": manifest["project_ref"],
        "export": export_data,
        "collision": collision_data,
        "navigation": navigation_data,
        "transform": placement["transform"],
        "scale": placement["scale"],
        "collision_node": collision != null,
        "navigation_node": navigation != null,
    }))
    output.close()
    print("BIELLA_ENVIRONMENT_BRIDGE_RUNTIME")
    quit()
'''


def test_real_game_import_and_runtime_bridge_environment_artifacts(tmp_path: Path) -> None:
    support = _p3_03_support()
    env = support._environment(tmp_path)
    transform = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 4.0, 0.0, -2.0, 1.0]
    scale = [1.0, 1.0, 1.0]
    export_bytes = b'''[gd_scene load_steps=3 format=3]\n\n[sub_resource type="BoxMesh" id="BoxMesh_env"]\nsize = Vector3(2, 1, 2)\n\n[sub_resource type="BoxShape3D" id="BoxShape_env"]\nsize = Vector3(2, 1, 2)\n\n[node name="Environment" type="Node3D"]\n[node name="Visual" type="MeshInstance3D" parent="."]\nmesh = SubResource("BoxMesh_env")\n[node name="Collision" type="StaticBody3D" parent="."]\n[node name="Shape" type="CollisionShape3D" parent="Collision"]\nshape = SubResource("BoxShape_env")\n[node name="Navigation" type="NavigationRegion3D" parent="."]\n'''
    collision_bytes = b'{"shape":"box","size":[2,1,2]}'
    navigation_bytes = b'{"regions":["environment"]}'
    export = _artifact(env, "game.asset.environment.input", export_bytes, "application/x-godot-scene", "p3-08.environment-export")
    collision = _artifact(env, "game.asset.environment.input", collision_bytes, "application/json", "p3-08.environment-collision")
    navigation = _artifact(env, "game.asset.environment.input", navigation_bytes, "application/json", "p3-08.environment-navigation")
    expected = {
        "export": (export.artifact_ref.value, _sha256(export_bytes)),
        "collision": (collision.artifact_ref.value, _sha256(collision_bytes)),
        "navigation": (navigation.artifact_ref.value, _sha256(navigation_bytes)),
    }
    manifest_payload: dict[str, object] = {
        "project_ref": env.access.project_ref.value,
        "export": {"artifact_ref": expected["export"][0], "sha256": expected["export"][1]},
        "collision": {"artifact_ref": expected["collision"][0], "sha256": expected["collision"][1]},
        "navigation": {"artifact_ref": expected["navigation"][0], "sha256": expected["navigation"][1]},
        "placements": [{"transform": transform, "scale": scale}],
    }
    _validate_bridge_manifest(manifest_payload, project_ref=env.access.project_ref.value, expected=expected)
    specification = EnvironmentSpecification(env.access.project_ref, "world-01", export.artifact_ref.value, _sha256(export_bytes), "meter", {"up": "Z"}, {"layout": "bridge"}, {"nav": "required"}, {"visual": "game"}, ("artifact://library/environment/v1",), {"tool": "godot"}, {"performance": "project"}, {"partition": "project"}, ("contract://output/environment/v1",), ("representation://environment/bridge/v1",))
    terrain = ProceduralTerrain(env.access.project_ref, "terrain-01", "generator://terrain/v1", "1.0.0", {"mode": "fixture"}, 7, export.artifact_ref.value, _sha256(export_bytes))
    placed = PlacedAsset(env.access.project_ref, "environment-01", export.artifact_ref.value, _sha256(export_bytes), tuple(transform), "artifact://material/environment/v1", "default", None, "partition-a")
    integration = EnvironmentIntegrationManifest(env.access.project_ref, specification, terrain, (placed,), export.artifact_ref.value, export.artifact_ref.value, export.artifact_ref.value, "artifact://material/environment/v1", collision.artifact_ref.value, navigation.artifact_ref.value, "artifact://partition/environment/v1", "tool://godot/v1", "runtime://godot/v1", "derivation://environment/bridge/v1", _sha256(json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode()))
    assert integration.collision_ref == collision.artifact_ref.value
    assert integration.navigation_ref == navigation.artifact_ref.value
    manifest_bytes = json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode()
    manifest = _artifact(env, "game.asset.environment.input", manifest_bytes, "application/json", "p3-08.environment-manifest")
    script = _artifact(env, "game.asset.environment.input", _runtime_script(), "application/x-gdscript", "p3-08.environment-runtime-validator")
    _stage(env, "environment.tscn", export, "stage-environment-export")
    _stage(env, "collision.json", collision, "stage-environment-collision")
    _stage(env, "navigation.json", navigation, "stage-environment-navigation")
    _stage(env, "environment-manifest.json", manifest, "stage-environment-manifest")
    _stage(env, "environment_bridge.gd", script, "stage-environment-runtime-validator")
    assets = tuple(GameAssetInput("environment", item.artifact_ref) for item in (export, manifest, collision, navigation))
    detection_spec = replace(
        support._spec(env, "true"),
        entrypoint=env.identity.engine_executable_path,
        args=env.identity.engine_version_args,
        working_directory="/tmp",
        outputs=(),
        environment={},
    )
    detection_request = support._request(
        env,
        GameEngineOperation.DETECT,
        detection_spec,
        "game.engine.detection",
    )
    detected = env.adapter.detect_project(
        env.access,
        env.primary_attempt,
        detection_request,
        idempotency_key="p3-08-environment-detect",
    )
    assert detected.reality is GameEngineReality.REAL
    import_spec = _with_bridge_inputs(env, support._spec(
        env,
        "set -euo pipefail; rm -rf evidence/run; mkdir -p evidence/run evidence/bridge; cp /workspace/bridge-input/* evidence/bridge/; godot --headless --path . --editor --quit; rm -rf evidence/bridge; "
        + "printf '%s' "
        + shlex.quote(json.dumps({"project_ref": env.access.project_ref.value, "export": expected["export"], "collision": expected["collision"], "navigation": expected["navigation"]}, sort_keys=True))
        + " > evidence/run/import.json",
        outputs=(("evidence/run/import.json", "application/json"),),
    ))
    import_request = replace(
        support._request(env, GameEngineOperation.IMPORT, import_spec, "game.import.output", required_output_markers=("Godot Engine",)),
        asset_inputs=assets,
    )
    imported = env.adapter.import_project(env.access, env.primary_attempt, import_request, idempotency_key="p3-08-environment-import")
    assert imported.reality is GameEngineReality.REAL
    import_artifact = env.artifacts.get_artifact(env.access, imported.output_artifact_refs[0])
    assert set(item.artifact_ref for item in assets) <= set(import_artifact.source_artifact_refs)
    assert json.loads(support._output_bytes(env, imported, "game.import.output")) == {"collision": list(expected["collision"]), "export": list(expected["export"]), "navigation": list(expected["navigation"]), "project_ref": env.access.project_ref.value}
    build_request = replace(
        support._request(
            env,
            GameEngineOperation.BUILD,
            support._spec(
                env,
                "set -euo pipefail; mkdir -p dist; godot --headless --path . --export-pack 'Linux/X11' dist/biella-game.pck; test -s dist/biella-game.pck",
                outputs=(("dist/biella-game.pck", "application/octet-stream"),),
            ),
            "game.build.output",
        ),
        asset_inputs=assets,
    )
    built = env.adapter.build(env.access, env.primary_attempt, build_request, idempotency_key="p3-08-environment-build")
    assert built.reality is GameEngineReality.REAL
    build_ref = built.output_artifact_refs[0]
    run_spec = _with_bridge_inputs(env, support._spec(
        env,
        "set -euo pipefail; mkdir -p evidence/bridge; cp /workspace/bridge-input/* evidence/bridge/; godot --headless --path . --script res://evidence/bridge/environment_bridge.gd; rm -rf evidence/bridge",
        outputs=(("evidence/run/runtime.json", "application/json"),),
    ))
    run_request = replace(
        support._request(env, GameEngineOperation.RUN, run_spec, "game.runtime.observation", build_artifact_ref=build_ref, required_output_markers=("BIELLA_ENVIRONMENT_BRIDGE_RUNTIME",)),
        asset_inputs=assets,
    )
    ran = env.adapter.run(env.access, env.primary_attempt, run_request, idempotency_key="p3-08-environment-run")
    assert ran.reality is GameEngineReality.REAL and ran.runtime_observed
    runtime_artifact = env.artifacts.get_artifact(env.access, ran.output_artifact_refs[0])
    assert set(item.artifact_ref for item in assets) <= set(runtime_artifact.source_artifact_refs)
    runtime = json.loads(support._output_bytes(env, ran, "game.runtime.observation"))
    assert runtime == {"collision": manifest_payload["collision"], "collision_node": True, "export": manifest_payload["export"], "navigation": manifest_payload["navigation"], "navigation_node": True, "project_ref": env.access.project_ref.value, "scale": scale, "transform": transform, "valid": True}
    forged = json.loads(manifest_bytes)
    forged["export"]["artifact_ref"] = "artifact://forged/environment/v1"
    with pytest.raises(ValueError, match="forged"):
        _validate_bridge_manifest(forged, project_ref=env.access.project_ref.value, expected=expected)
    missing = json.loads(manifest_bytes)
    del missing["collision"]
    with pytest.raises(ValueError, match="missing"):
        _validate_bridge_manifest(missing, project_ref=env.access.project_ref.value, expected=expected)
    nonfinite = json.loads(manifest_bytes)
    nonfinite["placements"][0]["transform"][0] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        _validate_bridge_manifest(nonfinite, project_ref=env.access.project_ref.value, expected=expected)
    invalid_scale = json.loads(manifest_bytes)
    invalid_scale["placements"][0]["scale"][0] = 0.0
    with pytest.raises(ValueError, match="scale"):
        _validate_bridge_manifest(invalid_scale, project_ref=env.access.project_ref.value, expected=expected)
    with pytest.raises(EnvironmentContractError):
        replace(placed, transform=(math.inf,) * 16)
    foreign_content = env.objects.put(b"foreign", media_type="application/octet-stream")
    foreign = ArtifactService(env.database).create_artifact(env.beta_access, project_ref=env.beta_access.project_ref, role="game.asset.environment.input", content_ref=foreign_content, source_refs=(), source_artifact_refs=(), source_content_refs=(foreign_content,), derivation_type="p3-08.foreign-environment", metadata={"media_type": "application/octet-stream"})
    foreign_manifest = json.loads(manifest_bytes)
    foreign_manifest["navigation"] = {"artifact_ref": foreign.artifact_ref.value, "sha256": _sha256(b"foreign")}
    with pytest.raises(ValueError, match="forged"):
        _validate_bridge_manifest(foreign_manifest, project_ref=env.access.project_ref.value, expected=expected)
    with pytest.raises(GameEngineScopeError):
        replace(import_request, asset_inputs=(GameAssetInput("environment", foreign.artifact_ref),))
