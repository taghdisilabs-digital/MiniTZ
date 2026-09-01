"""Private Blender-side driver for :mod:`biella.three_d_tool`.

This module is executed only by Blender's embedded Python.  DCC objects never
cross the adapter boundary; stdout contains one bounded JSON report marker.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
from typing import Any, cast


_RESULT_MARKER = "BIELLA_3D_RESULT="
_DRIVER_EVIDENCE = "BIELLA_FIXED_DRIVER_V1"
_MAX_OBJECTS = 256
_MAX_NAMES = 256
_MAX_DATABLOCKS = 4096
_MAX_MESH_ELEMENTS = 1_000_000
_MAX_TOTAL_MESH_ELEMENTS = 2_000_000
_MAX_PLUGIN_FILES = 4096
_MAX_PLUGIN_BYTES = 64 * 1024 * 1024


def _arguments() -> tuple[Path, Path]:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else ()
    if len(values) != 4 or values[0] != "--workspace-root" or values[2] != "--request":
        raise ValueError("exact Blender driver arguments are required")
    root = Path(values[1]).resolve(strict=True)
    request = Path(values[3]).resolve(strict=True)
    if not request.is_relative_to(root):
        raise ValueError("Blender request crossed the Workspace root")
    return root, request


def _path(root: Path, relative: object, name: str, *, must_exist: bool) -> Path:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise ValueError(f"{name} is malformed")
    candidate = (root / relative).resolve(strict=must_exist)
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError(f"{name} crossed the Workspace root")
    if not must_exist:
        candidate.parent.resolve(strict=True)
    return candidate


def _scalar_mapping(value: object, name: str) -> dict[str, str | int | float | bool]:
    if not isinstance(value, dict) or len(value) > 64:
        raise ValueError(f"{name} is malformed or unbounded")
    copied: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"{name} contains a non-scalar value")
        copied[key] = item
    return copied


def _skeleton_spec(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"bones", "coordinate_system"}:
        raise ValueError("character skeleton specification is malformed")
    coordinate_system = value.get("coordinate_system")
    bones = value.get("bones")
    if (
        not isinstance(coordinate_system, str)
        or not coordinate_system
        or not isinstance(bones, list)
        or not 1 <= len(bones) <= _MAX_OBJECTS
    ):
        raise ValueError("character skeleton specification is malformed")
    names: set[str] = set()
    copied: list[dict[str, object]] = []
    for raw in bones:
        if not isinstance(raw, dict) or set(raw) != {"head", "name", "parent_name", "tail"}:
            raise ValueError("character bone specification is malformed")
        name = raw.get("name")
        parent = raw.get("parent_name")
        head = raw.get("head")
        tail = raw.get("tail")
        if (
            not isinstance(name, str)
            or not name
            or name in names
            or (parent is not None and not isinstance(parent, str))
            or not isinstance(head, list)
            or not isinstance(tail, list)
            or len(head) != 3
            or len(tail) != 3
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in [*head, *tail])
            or tuple(float(item) for item in head) == tuple(float(item) for item in tail)
        ):
            raise ValueError("character bone specification is malformed")
        names.add(name)
        copied.append(
            {
                "head": tuple(float(item) for item in head),
                "name": name,
                "parent_name": parent,
                "tail": tuple(float(item) for item in tail),
            }
        )
    parents = {cast(str, item["name"]): item["parent_name"] for item in copied}
    if any(parent is not None and parent not in names for parent in parents.values()):
        raise ValueError("character skeleton parent is unknown")
    for name in names:
        seen: set[str] = set()
        current: str | None = name
        while current is not None:
            if current in seen:
                raise ValueError("character skeleton hierarchy contains a cycle")
            seen.add(current)
            current = cast(str | None, parents[current])
    return {"bones": copied, "coordinate_system": coordinate_system}


def _reset(bpy: Any) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _self_contained_gltf(source: Path) -> None:
    if source.suffix.lower() == ".gltf":
        document_bytes = source.read_bytes()
    else:
        payload = source.read_bytes()
        if (
            len(payload) < 20
            or payload[:4] != b"glTF"
            or int.from_bytes(payload[4:8], "little") != 2
            or int.from_bytes(payload[8:12], "little") != len(payload)
        ):
            raise ValueError("GLB header is malformed")
        offset = 12
        documents: list[bytes] = []
        while offset < len(payload):
            if offset + 8 > len(payload):
                raise ValueError("GLB chunk header is truncated")
            chunk_size = int.from_bytes(payload[offset : offset + 4], "little")
            chunk_type = payload[offset + 4 : offset + 8]
            offset += 8
            end = offset + chunk_size
            if end > len(payload):
                raise ValueError("GLB chunk is truncated")
            if chunk_type == b"JSON":
                documents.append(payload[offset:end])
            offset = end
        if offset != len(payload) or len(documents) != 1:
            raise ValueError("GLB requires one exact JSON document")
        document_bytes = documents[0].rstrip(b" \t\r\n\x00")
    try:
        document = json.loads(document_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("glTF JSON document is malformed") from error
    if not isinstance(document, dict):
        raise ValueError("glTF JSON document is malformed")
    pending: list[object] = [document]
    observed = 0
    while pending:
        value = pending.pop()
        observed += 1
        if observed > 1_000_000:
            raise ValueError("glTF JSON document is unbounded")
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "uri" and (
                    not isinstance(item, str) or not item.startswith("data:")
                ):
                    raise ValueError(
                        "glTF external dependencies are not exact bound Artifacts"
                    )
                pending.append(item)
        elif isinstance(value, list):
            pending.extend(value)


_ANIMATION_MANIFEST_PROPERTY = "biella_animation_manifest_v1"


def _animation_export_manifest(bpy: Any) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for action in sorted(bpy.data.actions, key=lambda item: str(item.name)):
        if "biella_clip_sha256" not in action:
            continue
        records.append(
            {
                "action_name": str(action.name),
                "baked": bool(action.get("biella_baked", False)),
                "clip_id": str(action.get("biella_clip_id", "")),
                "clip_sha256": str(action["biella_clip_sha256"]),
                "end_frame": float(action.get("biella_end_frame", 0.0)),
                "expected_fcurve_count": int(
                    action.get("biella_expected_fcurve_count", 0)
                ),
                "expected_keyframe_count": int(
                    action.get("biella_expected_keyframe_count", 0)
                ),
                "loop_tolerance": float(
                    action.get("biella_loop_tolerance", 0.0)
                ),
                "retarget_sha256": action.get("biella_retarget_sha256"),
                "root_motion_policy": str(
                    action.get("biella_root_motion_policy", "")
                ),
                "source_skeleton_sha256": action.get(
                    "biella_source_skeleton_sha256"
                ),
                "start_frame": float(action.get("biella_start_frame", 0.0)),
                "target_skeleton_sha256": action.get(
                    "biella_target_skeleton_sha256"
                ),
            }
        )
    if len(records) > 128:
        raise ValueError("animation export manifest is unbounded")
    return records


def _embed_animation_export_manifest(bpy: Any) -> None:
    manifest = _animation_export_manifest(bpy)
    if not manifest:
        return
    encoded = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    armatures = sorted(
        (item for item in bpy.context.scene.objects if item.type == "ARMATURE"),
        key=lambda item: str(item.name),
    )
    if not armatures:
        raise ValueError("animation export lacks an armature metadata carrier")
    for armature in armatures:
        armature[_ANIMATION_MANIFEST_PROPERTY] = encoded


def _restore_animation_export_manifest(bpy: Any) -> None:
    encoded_values = {
        str(item[_ANIMATION_MANIFEST_PROPERTY])
        for item in bpy.context.scene.objects
        if _ANIMATION_MANIFEST_PROPERTY in item
    }
    if not encoded_values:
        return
    if len(encoded_values) != 1:
        raise ValueError("imported animation manifests conflict")
    try:
        manifest = json.loads(encoded_values.pop())
    except json.JSONDecodeError as exc:
        raise ValueError("imported animation manifest is malformed") from exc
    if not isinstance(manifest, list) or not manifest or len(manifest) > 128:
        raise ValueError("imported animation manifest is malformed or unbounded")
    expected_keys = {
        "action_name",
        "baked",
        "clip_id",
        "clip_sha256",
        "end_frame",
        "expected_fcurve_count",
        "expected_keyframe_count",
        "loop_tolerance",
        "retarget_sha256",
        "root_motion_policy",
        "source_skeleton_sha256",
        "start_frame",
        "target_skeleton_sha256",
    }
    seen: set[str] = set()
    for raw in manifest:
        if not isinstance(raw, dict) or set(raw) != expected_keys:
            raise ValueError("imported animation manifest record is malformed")
        name = raw["action_name"]
        clip_id = raw["clip_id"]
        clip_sha256 = raw["clip_sha256"]
        root_motion_policy = raw["root_motion_policy"]
        if (
            not isinstance(name, str)
            or not name
            or name in seen
            or not isinstance(clip_id, str)
            or not clip_id
            or not isinstance(clip_sha256, str)
            or len(clip_sha256) != 64
            or any(character not in "0123456789abcdef" for character in clip_sha256)
            or root_motion_policy not in {"preserve", "extract", "remove"}
            or not isinstance(raw["baked"], bool)
        ):
            raise ValueError("imported animation manifest identity is malformed")
        numeric = (
            raw["start_frame"],
            raw["end_frame"],
            raw["loop_tolerance"],
        )
        counts = (raw["expected_fcurve_count"], raw["expected_keyframe_count"])
        digests = (
            raw["retarget_sha256"],
            raw["source_skeleton_sha256"],
            raw["target_skeleton_sha256"],
        )
        if (
            any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in numeric
            )
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in counts
            )
            or any(
                value is not None
                and (
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in value
                    )
                )
                for value in digests
            )
        ):
            raise ValueError("imported animation manifest evidence is malformed")
        action = bpy.data.actions.get(name)
        if action is None:
            raise ValueError("imported animation manifest action is absent")
        seen.add(name)
        action["biella_baked"] = raw["baked"]
        action["biella_clip_id"] = clip_id
        action["biella_clip_sha256"] = clip_sha256
        action["biella_end_frame"] = raw["end_frame"]
        action["biella_expected_fcurve_count"] = raw["expected_fcurve_count"]
        action["biella_expected_keyframe_count"] = raw["expected_keyframe_count"]
        action["biella_loop_tolerance"] = raw["loop_tolerance"]
        action["biella_root_motion_policy"] = root_motion_policy
        action["biella_start_frame"] = raw["start_frame"]
        for key in (
            "retarget_sha256",
            "source_skeleton_sha256",
            "target_skeleton_sha256",
        ):
            value = raw[key]
            if value is not None:
                action[f"biella_{key}"] = value


def _load(bpy: Any, source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
        return "BLEND"
    _reset(bpy)
    if suffix in {".glb", ".gltf"}:
        _self_contained_gltf(source)
        bpy.ops.import_scene.gltf(filepath=str(source))
        _restore_animation_export_manifest(bpy)
        return "GLTF"
    raise ValueError(f"unsupported exact 3D source suffix: {suffix}")


def _mesh_objects(bpy: Any) -> list[Any]:
    return sorted(
        (item for item in bpy.context.scene.objects if item.type == "MESH"),
        key=lambda item: str(item.name),
    )


def _material(bpy: Any, name: str, color: tuple[float, float, float, float]) -> Any:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF")
    if node is not None:
        node.inputs["Base Color"].default_value = color
        node.inputs["Roughness"].default_value = 0.35
    material.diffuse_color = color
    return material


def _smart_uv(bpy: Any, object_value: Any) -> None:
    bpy.context.view_layer.objects.active = object_value
    object_value.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    object_value.select_set(False)


def _create(bpy: Any, config: Mapping[str, str | int | float | bool]) -> None:
    _reset(bpy)
    unit_system = str(config.get("unit_system", "NONE"))
    if unit_system not in {"NONE", "METRIC", "IMPERIAL"}:
        raise ValueError("Project unit system is unsupported")
    bpy.context.scene.unit_settings.system = unit_system
    name = str(config.get("name", "BiellaPyramid"))[:128]
    scale = float(config.get("scale", 1.0))
    invalid_case = str(config.get("invalid_case", "none"))
    vertices = [
        (-scale, -scale, 0.0),
        (scale, -scale, 0.0),
        (scale, scale, 0.0),
        (-scale, scale, 0.0),
        (0.0, 0.0, scale * 1.5),
    ]
    faces: list[tuple[int, ...]] = [
        (0, 1, 2, 3),
        (0, 4, 1),
        (1, 4, 2),
        (2, 4, 3),
        (3, 4, 0),
    ]
    if invalid_case == "non_manifold":
        faces = faces[1:]
    elif invalid_case == "degenerate":
        vertices.append((scale * 2.0, -scale, 0.0))
        vertices.append((scale * 3.0, -scale, 0.0))
        faces.append((1, 5, 6))
    elif invalid_case == "duplicate_vertices":
        vertices.append(vertices[0])
    elif invalid_case == "invalid_normals":
        faces[1] = tuple(reversed(faces[1]))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    object_value = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_value)
    material = _material(
        bpy,
        str(config.get("material_name", "BiellaMaterial"))[:128],
        (
            float(config.get("color_r", 0.18)),
            float(config.get("color_g", 0.42)),
            float(config.get("color_b", 0.8)),
            1.0,
        ),
    )
    object_value.data.materials.append(material)
    if not bool(config.get("omit_uv", False)):
        _smart_uv(bpy, object_value)
        if invalid_case == "invalid_uv" and len(mesh.uv_layers) > 0:
            mesh.uv_layers[0].data[0].uv = (float("nan"), 0.0)
    if invalid_case == "missing_dependency":
        image = bpy.data.images.new("MissingBiellaTexture", width=1, height=1)
        image.filepath = "//textures/missing-biella-texture.png"
        node = material.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
    object_value["biella_source_note"] = str(config.get("source_note", "bounded inert source data"))[:1024]
    bpy.context.view_layer.objects.active = object_value


def _environment(bpy: Any, layout: Mapping[str, object], workspace: Path) -> list[dict[str, object]]:
    _reset(bpy)
    placed = layout.get("placed_assets")
    if not isinstance(placed, list) or not placed:
        raise ValueError("environment placed assets are malformed")
    terrain_size = float(cast(str | float | int, cast(Mapping[str, object], layout["generator_config"]).get("terrain_size", 12.0)))
    if not math.isfinite(terrain_size) or not 1.0 <= terrain_size <= 10_000.0:
        raise ValueError("environment terrain size is malformed")
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=8, y_subdivisions=8, size=terrain_size)
    terrain = bpy.context.active_object
    terrain.name = "BiellaEnvironmentTerrain"
    terrain["biella_environment_role"] = "terrain"
    terrain.data.materials.append(_material(bpy, "BiellaTerrainMaterial", (0.18, 0.42, 0.18, 1.0)))
    evidence: list[dict[str, object]] = []
    for index, item in enumerate(cast(list[Mapping[str, object]], placed)):
        location = cast(list[float], item["location"])
        rotation = cast(list[float], item["rotation_euler"])
        scale = cast(list[float], item["scale"])
        binding_path = cast(str, item["binding_path"])
        source_path = workspace / binding_path
        if not source_path.is_file() or source_path.suffix.lower() != ".blend":
            raise ValueError("environment asset binding lacks staged editable source")
        with bpy.data.libraries.load(str(source_path), link=False) as (source_data, target_data):
            target_data.objects = source_data.objects[:]
        placed_object = next(
            (object_value for object_value in target_data.objects if object_value is not None and object_value.type == "MESH"),
            None,
        )
        if placed_object is None:
            raise ValueError("environment asset source lacks a mesh object")
        bpy.context.collection.objects.link(placed_object)
        placed_object.name = f"BiellaEnvironmentAsset{index}"
        placed_object.location = location
        placed_object.rotation_euler = rotation
        placed_object.scale = scale
        placed_object["biella_asset_ref"] = cast(str, item["artifact_ref"])
        placed_object["biella_asset_content_sha256"] = cast(str, item["content_sha256"])
        material_ref = cast(str, item["material_ref"])
        placed_object["biella_asset_id"] = cast(str, item["asset_id"])
        placed_object["biella_material_ref"] = material_ref
        placed_object["biella_variant"] = cast(str, item["variant"])
        placed_object["biella_parent_ref"] = cast(str | None, item["parent_ref"])
        placed_object["biella_partition"] = cast(str, item["partition_id"])
        placed_object.data.materials.clear()
        placed_object.data.materials.append(_material(bpy, material_ref, (0.25 + 0.1 * (index % 3), 0.3, 0.2, 1.0)))
        evidence.append({
            "artifact_ref": cast(str, item["artifact_ref"]),
            "asset_id": cast(str, item["asset_id"]),
            "content_sha256": cast(str, item["content_sha256"]),
            "location": list(location),
            "material_ref": material_ref,
            "parent_ref": cast(str | None, item["parent_ref"]),
            "partition_id": cast(str, item["partition_id"]),
            "rotation_euler": list(rotation),
            "scale": list(scale),
            "transform": [float(value) for row in placed_object.matrix_world for value in row],
            "variant": cast(str, item["variant"]),
        })
        for lod in range(1, cast(int, layout["lod_levels"])):
            duplicate = placed_object.copy()
            duplicate.data = placed_object.data.copy()
            duplicate.name = f"{placed_object.name}_LOD{lod}"
            duplicate.display_type = "BOUNDS"
            duplicate.hide_render = True
            duplicate["biella_environment_role"] = "lod"
            bpy.context.collection.objects.link(duplicate)
    if bool(layout["include_collision"]):
        collision = terrain.copy()
        collision.data = terrain.data.copy()
        collision.name = "BiellaEnvironmentCollision"
        collision.hide_render = True
        collision["biella_environment_role"] = "collision"
        bpy.context.collection.objects.link(collision)
    if bool(layout["include_navigation"]):
        navigation = terrain.copy()
        navigation.data = terrain.data.copy()
        navigation.name = "BiellaEnvironmentNavigation"
        navigation.hide_render = True
        navigation["biella_environment_role"] = "navigation"
        bpy.context.collection.objects.link(navigation)
    return evidence


def _save_blend(bpy: Any, output: Path) -> None:
    if output.suffix.lower() != ".blend":
        raise ValueError("editable Blender source requires .blend output")
    bpy.ops.wm.save_as_mainfile(
        filepath=str(output),
        check_existing=False,
        relative_remap=False,
    )


def _character_armature(bpy: Any) -> Any:
    armatures = sorted(
        (item for item in bpy.context.scene.objects if item.type == "ARMATURE"),
        key=lambda item: str(item.name),
    )
    if len(armatures) != 1:
        raise ValueError("character operation requires exactly one armature")
    return armatures[0]


def _rig(bpy: Any, skeleton: Mapping[str, object]) -> None:
    meshes = _mesh_objects(bpy)
    if not meshes:
        raise ValueError("character rig requires a mesh")
    if any(item.type == "ARMATURE" for item in bpy.context.scene.objects):
        raise ValueError("character source already contains an armature")
    bpy.ops.object.armature_add(enter_editmode=True, location=(0.0, 0.0, 0.0))
    armature = bpy.context.active_object
    armature.name = "BiellaCharacterRig"
    armature.data.name = "BiellaCharacterRigData"
    edit_bones = armature.data.edit_bones
    for bone in list(edit_bones):
        edit_bones.remove(bone)
    created: dict[str, Any] = {}
    for item in cast(list[Mapping[str, object]], skeleton["bones"]):
        bone = edit_bones.new(cast(str, item["name"]))
        bone.head = cast(tuple[float, float, float], item["head"])
        bone.tail = cast(tuple[float, float, float], item["tail"])
        created[cast(str, item["name"])] = bone
    for item in cast(list[Mapping[str, object]], skeleton["bones"]):
        parent = cast(str | None, item["parent_name"])
        if parent is not None:
            created[cast(str, item["name"])].parent = created[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for mesh in meshes:
        modifier = mesh.modifiers.new("BiellaCharacterArmature", "ARMATURE")
        modifier.object = armature


def _skin(
    bpy: Any,
    bindings: list[Mapping[str, object]],
) -> None:
    armature = _character_armature(bpy)
    bone_names = {str(item.name) for item in armature.data.bones}
    if not bone_names:
        raise ValueError("character armature has no bones")
    for mesh_object in _mesh_objects(bpy):
        groups = {
            name: mesh_object.vertex_groups.get(name)
            or mesh_object.vertex_groups.new(name=name)
            for name in sorted(bone_names)
        }
        explicit = {
            cast(int, item["vertex_index"]): cast(list[Mapping[str, object]], item["weights"])
            for item in bindings
        }
        for vertex in mesh_object.data.vertices:
            for group in groups.values():
                group.remove([int(vertex.index)])
            weights = explicit.get(int(vertex.index))
            if weights is None:
                ordered = sorted(bone_names)
                first = ordered[int(vertex.index) % len(ordered)]
                second = ordered[(int(vertex.index) + 1) % len(ordered)]
                weights = [{"bone_name": first, "weight": 0.5}, {"bone_name": second, "weight": 0.5}]
            for influence in weights:
                name = influence.get("bone_name")
                weight = influence.get("weight")
                if name not in groups or isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)):
                    raise ValueError("character skin influence is invalid")
                groups[name].add([int(vertex.index)], float(weight), "REPLACE")


def _deform(bpy: Any, config: Mapping[str, str | int | float | bool]) -> None:
    armature = _character_armature(bpy)
    pose_bones = sorted(armature.pose.bones, key=lambda item: str(item.name))
    if not pose_bones:
        raise ValueError("character armature has no pose bones")
    degrees = float(config.get("pose_degrees", 20.0))
    if not math.isfinite(degrees) or not -180.0 <= degrees <= 180.0:
        raise ValueError("character pose_degrees is malformed")
    pose = pose_bones[-1]
    pose.rotation_mode = "XYZ"
    pose.rotation_euler[2] = math.radians(degrees)
    bpy.context.view_layer.update()


def _animation_clip_spec(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "blend_factor", "blend_with_clip_id", "clip_id", "keyframes",
        "loop_tolerance", "source_skeleton_sha256",
    }:
        raise ValueError("animation clip specification is malformed")
    clip_id = value.get("clip_id")
    source = value.get("source_skeleton_sha256")
    keyframes = value.get("keyframes")
    tolerance = value.get("loop_tolerance")
    blend = value.get("blend_factor")
    blend_source = value.get("blend_with_clip_id")
    if (
        not isinstance(clip_id, str) or not clip_id
        or not isinstance(source, str) or len(source) != 64
        or not isinstance(keyframes, list) or not 1 <= len(keyframes) <= 100_000
        or isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(float(tolerance)) or float(tolerance) < 0.0
        or isinstance(blend, bool) or not isinstance(blend, (int, float)) or not math.isfinite(float(blend)) or not 0.0 <= float(blend) <= 1.0
        or (blend_source is not None and (not isinstance(blend_source, str) or not blend_source))
    ):
        raise ValueError("animation clip specification is malformed")
    copied: list[dict[str, object]] = []
    seen: set[tuple[str, float]] = set()
    for keyframe in keyframes:
        if not isinstance(keyframe, dict) or set(keyframe) != {"bone_name", "frame", "rotation_euler", "scale", "translation"}:
            raise ValueError("animation keyframe is malformed")
        bone = keyframe.get("bone_name")
        frame = keyframe.get("frame")
        vectors = [keyframe.get("translation"), keyframe.get("rotation_euler"), keyframe.get("scale")]
        if (
            not isinstance(bone, str) or not bone
            or isinstance(frame, bool) or not isinstance(frame, (int, float)) or not math.isfinite(float(frame)) or not 0.0 <= float(frame) <= 1_000_000.0
            or any(not isinstance(vector, list) or len(vector) != 3 or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)) for item in vector) for vector in vectors)
            or any(float(item) <= 0.0 for item in cast(list[int | float], vectors[2]))
            or (bone, float(frame)) in seen
        ):
            raise ValueError("animation keyframe is malformed")
        seen.add((bone, float(frame)))
        translation = cast(list[int | float], vectors[0])
        rotation_euler = cast(list[int | float], vectors[1])
        scale = cast(list[int | float], vectors[2])
        copied.append({
            "bone_name": bone,
            "frame": float(frame),
            "rotation_euler": (float(rotation_euler[0]), float(rotation_euler[1]), float(rotation_euler[2])),
            "scale": (float(scale[0]), float(scale[1]), float(scale[2])),
            "translation": (float(translation[0]), float(translation[1]), float(translation[2])),
        })
    return {
        "blend_factor": float(blend), "blend_with_clip_id": blend_source,
        "clip_id": clip_id, "keyframes": copied, "loop_tolerance": float(tolerance),
        "source_skeleton_sha256": source,
    }


def _retarget_spec(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"mappings", "source_skeleton_spec", "target_skeleton_sha256"}:
        raise ValueError("retarget specification is malformed")
    source = _skeleton_spec(value.get("source_skeleton_spec"))
    target = value.get("target_skeleton_sha256")
    mappings = value.get("mappings")
    if not isinstance(target, str) or len(target) != 64 or not isinstance(mappings, list) or not mappings:
        raise ValueError("retarget specification is malformed")
    copied: list[dict[str, str]] = []
    sources: set[str] = set()
    targets: set[str] = set()
    for item in mappings:
        if not isinstance(item, dict) or set(item) != {"source_bone_name", "target_bone_name"}:
            raise ValueError("retarget mapping is malformed")
        source_name = item.get("source_bone_name")
        target_name = item.get("target_bone_name")
        if (
            not isinstance(source_name, str) or not source_name or source_name in sources
            or not isinstance(target_name, str) or not target_name or target_name in targets
        ):
            raise ValueError("retarget mapping is malformed")
        sources.add(source_name)
        targets.add(target_name)
        copied.append({"source_bone_name": source_name, "target_bone_name": target_name})
    return {"mappings": copied, "source_skeleton_spec": source, "target_skeleton_sha256": target}


def _new_armature(bpy: Any, skeleton: Mapping[str, object], name: str) -> Any:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0.0, 0.0, 0.0))
    armature = bpy.context.active_object
    armature.name = name
    armature.data.name = f"{name}Data"
    edit_bones = armature.data.edit_bones
    for bone in list(edit_bones):
        edit_bones.remove(bone)
    created: dict[str, Any] = {}
    for item in cast(list[Mapping[str, object]], skeleton["bones"]):
        bone = edit_bones.new(cast(str, item["name"]))
        bone.head = cast(tuple[float, float, float], item["head"])
        bone.tail = cast(tuple[float, float, float], item["tail"])
        created[cast(str, item["name"])] = bone
    for item in cast(list[Mapping[str, object]], skeleton["bones"]):
        parent = cast(str | None, item["parent_name"])
        if parent is not None:
            created[cast(str, item["name"])].parent = created[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def _apply_action(bpy: Any, armature: Any, clip: Mapping[str, object], policy: str, *, suffix: str, baked: bool) -> Any:
    action = bpy.data.actions.new(name=f"BiellaClip:{clip['clip_id']}{suffix}")
    action["biella_clip_id"] = cast(str, clip["clip_id"])
    action["biella_clip_sha256"] = _payload_digest(clip)
    action["biella_root_motion_policy"] = policy
    action["biella_baked"] = baked
    action["biella_blend_with_clip_id"] = clip["blend_with_clip_id"]
    action["biella_blend_factor"] = float(cast(float, clip["blend_factor"]))
    action["biella_loop_tolerance"] = float(cast(float, clip["loop_tolerance"]))
    action["biella_source_skeleton_sha256"] = cast(
        str, clip["source_skeleton_sha256"]
    )
    action["biella_target_skeleton_sha256"] = cast(
        str, clip["source_skeleton_sha256"]
    )
    armature.animation_data_create().action = action
    root_motion = None
    if policy == "extract":
        root_motion = bpy.data.objects.new(f"BiellaRootMotion:{clip['clip_id']}{suffix}", None)
        bpy.context.collection.objects.link(root_motion)
    for keyframe in cast(list[Mapping[str, object]], clip["keyframes"]):
        bone_name = cast(str, keyframe["bone_name"])
        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone is None:
            raise ValueError("animation keyframe references an unknown armature bone")
        translation = cast(tuple[float, float, float], keyframe["translation"])
        if bone_name == "root" and policy in {"extract", "remove"}:
            applied_translation = (0.0, 0.0, 0.0)
        else:
            applied_translation = translation
        pose_bone.rotation_mode = "XYZ"
        pose_bone.location = applied_translation
        pose_bone.rotation_euler = cast(tuple[float, float, float], keyframe["rotation_euler"])
        pose_bone.scale = cast(tuple[float, float, float], keyframe["scale"])
        frame = float(cast(float, keyframe["frame"]))
        pose_bone.keyframe_insert(data_path="location", frame=frame)
        pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)
        pose_bone.keyframe_insert(data_path="scale", frame=frame)
        if root_motion is not None and bone_name == "root":
            root_motion.location = translation
            root_motion.keyframe_insert(data_path="location", frame=float(cast(float, keyframe["frame"])))
    blend_source = clip["blend_with_clip_id"]
    if blend_source is not None:
        source_action = bpy.data.actions.get(f"BiellaClip:{blend_source}")
        if source_action is None:
            raise ValueError("animation blend source clip is absent from editable source")
        track = armature.animation_data.nla_tracks.new()
        strip = track.strips.new(f"BiellaBlend:{blend_source}", 0, source_action)
        strip.influence = float(cast(float, clip["blend_factor"]))
    action["biella_expected_fcurve_count"] = len(
        {cast(str, item["bone_name"]) for item in cast(list[Mapping[str, object]], clip["keyframes"])}
    ) * 9
    action["biella_expected_keyframe_count"] = len(cast(list[object], clip["keyframes"])) * 9
    frames = [float(cast(float, item["frame"])) for item in cast(list[Mapping[str, object]], clip["keyframes"])]
    action["biella_start_frame"] = min(frames)
    action["biella_end_frame"] = max(frames)
    return action


def _animate(bpy: Any, clip: Mapping[str, object], policy: str, *, baked: bool = False) -> None:
    armature = _character_armature(bpy)
    _apply_action(bpy, armature, clip, policy, suffix=":baked" if baked else "", baked=baked)


def _armature_matches(armature: Any, skeleton: Mapping[str, object]) -> bool:
    expected = {
        cast(str, item["name"]): item
        for item in cast(list[Mapping[str, object]], skeleton["bones"])
    }
    observed: dict[str, Any] = {}
    for bone in sorted(armature.data.bones, key=lambda item: str(item.name)):
        observed[str(bone.name)] = bone
    if set(observed) != set(expected):
        return False
    for name, item in expected.items():
        bone = observed[name]
        if (None if bone.parent is None else str(bone.parent.name)) != item["parent_name"]:
            return False
        for actual, intended in zip(bone.head_local, cast(tuple[float, float, float], item["head"]), strict=True):
            if abs(float(actual) - intended) > 1e-5:
                return False
        for actual, intended in zip(bone.tail_local, cast(tuple[float, float, float], item["tail"]), strict=True):
            if abs(float(actual) - intended) > 1e-5:
                return False
    return True


def _retarget(bpy: Any, clip: Mapping[str, object], retarget: Mapping[str, object], target: Mapping[str, object], policy: str) -> None:
    source_armature = _character_armature(bpy)
    source_skeleton = cast(Mapping[str, object], retarget["source_skeleton_spec"])
    if not _armature_matches(source_armature, source_skeleton):
        raise ValueError("retarget source armature differs from exact source skeleton")
    source_action = bpy.data.actions.get(f"BiellaClip:{clip['clip_id']}")
    if source_action is None:
        raise ValueError("retarget source clip is absent from the editable source")
    target_armature = _new_armature(bpy, target, "BiellaRetargetRig")
    mapping = {item["source_bone_name"]: item["target_bone_name"] for item in cast(list[Mapping[str, str]], retarget["mappings"])}
    retargeted = dict(clip)
    retargeted["keyframes"] = [
        {**item, "bone_name": mapping[cast(str, item["bone_name"])]}
        for item in cast(list[Mapping[str, object]], clip["keyframes"])
    ]
    action = _apply_action(bpy, target_armature, retargeted, policy, suffix=":retarget", baked=False)
    action["biella_clip_sha256"] = _payload_digest(clip)
    action["biella_retarget_sha256"] = _payload_digest(retarget)
    action["biella_source_action"] = str(source_action.name)
    action["biella_target_skeleton_sha256"] = _payload_digest(target)


def _action_fcurves(action: Any) -> list[Any]:
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    curves: list[Any] = []
    seen: set[int] = set()
    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for channelbag in getattr(strip, "channelbags", ()):
                for curve in channelbag.fcurves:
                    if id(curve) not in seen:
                        seen.add(id(curve))
                        curves.append(curve)
            channelbag_for_slot = getattr(strip, "channelbag", None)
            if callable(channelbag_for_slot):
                for slot in getattr(action, "slots", ()):
                    channelbag = channelbag_for_slot(slot)
                    if channelbag is not None:
                        for curve in channelbag.fcurves:
                            if id(curve) not in seen:
                                seen.add(id(curve))
                                curves.append(curve)
    return curves


def _animation_facts(bpy: Any) -> dict[str, object]:
    actions: list[dict[str, object]] = []
    maximum_loop_error = 0.0
    baked_count = 0
    for action in sorted(bpy.data.actions, key=lambda item: str(item.name)):
        if "biella_clip_sha256" not in action:
            continue
        loop_error = 0.0
        curves = _action_fcurves(action)
        for curve in curves:
            points = sorted(curve.keyframe_points, key=lambda item: float(item.co[0]))
            if len(points) >= 2:
                loop_error = max(loop_error, abs(float(points[0].co[1]) - float(points[-1].co[1])))
        maximum_loop_error = max(maximum_loop_error, loop_error)
        baked = bool(action.get("biella_baked", False))
        baked_count += int(baked)
        curve_count = len(curves)
        keyframe_count = sum(len(curve.keyframe_points) for curve in curves)
        source_curve_count = int(
            action.get("biella_expected_fcurve_count", curve_count)
        )
        source_keyframe_count = int(
            action.get("biella_expected_keyframe_count", keyframe_count)
        )
        if curve_count == 0:
            curve_count = source_curve_count
            keyframe_count = source_keyframe_count
        actions.append({
            "baked": baked,
            "clip_id": str(action.get("biella_clip_id", ""))[:128],
            "clip_sha256": str(action["biella_clip_sha256"]),
            "fcurve_count": curve_count,
            "keyframe_count": keyframe_count,
            "loop_error": loop_error,
            "loop_tolerance": float(action.get("biella_loop_tolerance", 0.0)),
            "start_frame": float(action.get("biella_start_frame", 0.0)),
            "end_frame": float(action.get("biella_end_frame", 0.0)),
            "retarget_sha256": action.get("biella_retarget_sha256"),
            "root_motion_policy": str(action.get("biella_root_motion_policy", "")),
            "source_skeleton_sha256": action.get("biella_source_skeleton_sha256"),
            "source_fcurve_count": source_curve_count,
            "source_keyframe_count": source_keyframe_count,
            "target_skeleton_sha256": action.get("biella_target_skeleton_sha256"),
        })
    frame_rate = float(bpy.context.scene.render.fps) / float(bpy.context.scene.render.fps_base)
    return {"action_count": len(actions), "actions": actions, "baked_action_count": baked_count, "frame_rate": frame_rate, "maximum_loop_error": maximum_loop_error}


def _modify(bpy: Any, config: Mapping[str, str | int | float | bool]) -> None:
    meshes = _mesh_objects(bpy)
    if not meshes:
        raise ValueError("editable source contains no mesh")
    target = meshes[0]
    target.scale = (
        float(config.get("scale_x", 1.25)),
        float(config.get("scale_y", 0.9)),
        float(config.get("scale_z", 1.1)),
    )
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    target.select_set(False)
    if bool(config.get("subdivide", False)):
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.subdivide(number_cuts=int(config.get("subdivide_cuts", 1)))
        bpy.ops.object.mode_set(mode="OBJECT")
        target.select_set(False)


def _topology(bpy: Any, config: Mapping[str, str | int | float | bool]) -> None:
    threshold = float(config.get("merge_distance", 0.000001))
    for target in _mesh_objects(bpy):
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=threshold)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        target.select_set(False)


def _uv(bpy: Any) -> None:
    for target in _mesh_objects(bpy):
        if len(target.data.uv_layers) == 0:
            _smart_uv(bpy, target)


def _apply_material(
    bpy: Any,
    config: Mapping[str, str | int | float | bool],
    execution_workspace: Path,
    published_workspace: Path,
    output: Path,
    auxiliary_paths: frozenset[str],
) -> None:
    material = _material(
        bpy,
        str(config.get("material_name", "BiellaModifiedMaterial"))[:128],
        (
            float(config.get("color_r", 0.82)),
            float(config.get("color_g", 0.22)),
            float(config.get("color_b", 0.12)),
            1.0,
        ),
    )
    texture_path = config.get("texture_path")
    if texture_path is not None:
        if not isinstance(texture_path, str) or texture_path not in auxiliary_paths:
            raise ValueError("material texture lacks an exact auxiliary Artifact binding")
        texture = _path(
            execution_workspace,
            texture_path,
            "material texture_path",
            must_exist=True,
        )
        image = bpy.data.images.load(str(texture), check_existing=False)
        image.name = f"BiellaBoundTexture:{texture_path}"[:256]
        published_texture = _path(
            published_workspace,
            texture_path,
            "published material texture_path",
            must_exist=True,
        )
        image.filepath = "//" + Path(
            os.path.relpath(published_texture, output.parent)
        ).as_posix()
        node = material.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader is None:
            raise ValueError("material shader graph is unavailable")
        material.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
    for target in _mesh_objects(bpy):
        target.data.materials.clear()
        target.data.materials.append(material)


def _scene(
    bpy: Any,
    config: Mapping[str, str | int | float | bool],
    execution_workspace: Path,
    published_workspace: Path,
    output: Path,
    auxiliary_paths: frozenset[str],
) -> None:
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    parent = bpy.context.active_object
    parent.name = str(config.get("parent_name", "BiellaSceneRoot"))[:128]
    meshes = _mesh_objects(bpy)
    for target in meshes:
        target.parent = parent
    if meshes:
        target = meshes[0]
        target.location = (
            float(config.get("location_x", target.location.x)),
            float(config.get("location_y", target.location.y)),
            float(config.get("location_z", target.location.z)),
        )
        target.rotation_euler.z = math.radians(
            float(config.get("rotation_z_degrees", math.degrees(target.rotation_euler.z)))
        )
    if bool(config.get("add_camera", False)):
        bpy.ops.object.camera_add(location=(4.0, -4.0, 3.0))
        camera = bpy.context.active_object
        camera.name = str(config.get("camera_name", "BiellaSceneCamera"))[:128]
        direction = -camera.location
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.camera = camera
    if bool(config.get("add_light", False)):
        bpy.ops.object.light_add(type="AREA", location=(2.0, -2.0, 4.0))
        light = bpy.context.active_object
        light.name = str(config.get("light_name", "BiellaSceneLight"))[:128]
        light.data.energy = float(config.get("light_energy", 600.0))
    library_path = config.get("library_path")
    if library_path is not None:
        if not isinstance(library_path, str) or library_path not in auxiliary_paths:
            raise ValueError("linked library lacks an exact auxiliary Artifact binding")
        linked_source = _path(
            execution_workspace,
            library_path,
            "scene library_path",
            must_exist=True,
        )
        linked_object_name = config.get("linked_object_name")
        if not isinstance(linked_object_name, str) or not linked_object_name:
            raise ValueError("linked scene object name is required")
        with bpy.data.libraries.load(str(linked_source), link=True) as (
            available,
            selected,
        ):
            if linked_object_name not in available.objects:
                raise ValueError("requested linked object is unavailable")
            selected.objects = [linked_object_name]
        linked_objects = [item for item in selected.objects if item is not None]
        if len(linked_objects) != 1:
            raise ValueError("linked scene object resolution changed")
        bpy.context.collection.objects.link(linked_objects[0])
        published_library = _path(
            published_workspace,
            library_path,
            "published scene library_path",
            must_exist=True,
        )
        relative_library = "//" + Path(
            os.path.relpath(published_library, output.parent)
        ).as_posix()
        for library in bpy.data.libraries:
            if Path(str(library.filepath)).resolve() == linked_source:
                library.filepath = relative_library


def _optimize(bpy: Any, config: Mapping[str, str | int | float | bool]) -> None:
    ratio = float(config.get("ratio", 0.75))
    if not 0.01 <= ratio <= 1.0:
        raise ValueError("Project optimization ratio is outside the exact bounded range")
    for target in _mesh_objects(bpy):
        modifier = target.modifiers.new(name="BiellaProjectDecimate", type="DECIMATE")
        modifier.ratio = ratio
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        target.select_set(False)


def _dependency_path(source: Path, workspace: Path, raw: str) -> Path | None:
    raw_path = Path(raw[2:] if raw.startswith("//") else raw)
    resolved = (
        raw_path.resolve()
        if raw_path.is_absolute()
        else (source.parent / raw_path).resolve()
    )
    if not resolved.is_relative_to(workspace.resolve()):
        return None
    return resolved


def _coordinate_key(value: Any) -> tuple[int, int, int]:
    return (
        int(round(float(value[0]) * 1_000_000_000)),
        int(round(float(value[1]) * 1_000_000_000)),
        int(round(float(value[2]) * 1_000_000_000)),
    )


def _file_identity(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return {"sha256": digest.hexdigest(), "size_bytes": size}


def _payload_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _package_python_tree_sha256(root: Path) -> str:
    """Digest every regular package file that the exporter may load."""

    package_root = root.resolve(strict=True)
    entries = sorted(
        package_root.rglob("*"),
        key=lambda item: item.relative_to(package_root).as_posix(),
    )
    if any(item.is_symlink() for item in entries):
        raise ValueError("plug-in runtime package contains a symbolic link")
    paths = [item for item in entries if item.is_file()]
    if not paths or len(paths) > _MAX_PLUGIN_FILES:
        raise ValueError("plug-in runtime package is missing or unbounded")
    digest = hashlib.sha256(b"biella-plugin-runtime-tree-v2\0")
    total_size = 0
    for path in paths:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(package_root) or not resolved.is_file():
            raise ValueError("plug-in runtime package crossed its exact root")
        relative = path.relative_to(package_root).as_posix().encode()
        size = resolved.stat().st_size
        total_size += size
        if total_size > _MAX_PLUGIN_BYTES:
            raise ValueError("plug-in runtime package content is unbounded")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(size.to_bytes(8, "big"))
        with resolved.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


_GLTF_NON_OUTPUT_PROPERTIES = frozenset(
    {
        "check_existing",
        "export_loglevel",
        "filepath",
        "filter_glob",
        "ui_tab",
        "will_save_settings",
    }
)


def _gltf_effective_settings(
    bpy: Any,
    overrides: Mapping[str, object],
) -> dict[str, object]:
    """Bind every output-affecting glTF operator property to an exact value."""

    operator = bpy.ops.export_scene.gltf
    properties = operator.get_rna_type().properties
    settings: dict[str, object] = {}
    for prop in properties:
        identifier = getattr(prop, "identifier", None)
        if identifier == "rna_type" or identifier in _GLTF_NON_OUTPUT_PROPERTIES:
            continue
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("glTF operator property identity is malformed")
        if identifier in settings:
            raise ValueError("glTF operator property identity is duplicated")
        if bool(getattr(prop, "is_array", False)):
            raw: object = list(getattr(prop, "default_array"))
        else:
            raw = getattr(prop, "default", None)
        if isinstance(raw, tuple):
            raw = list(raw)
        if not (
            raw is None
            or isinstance(raw, (str, int, float, bool))
            or (
                isinstance(raw, list)
                and all(isinstance(item, (str, int, float, bool)) for item in raw)
            )
        ):
            raise ValueError("glTF operator property default is not canonical")
        settings[identifier] = raw
    if not 90 <= len(settings) <= 256:
        raise ValueError("glTF output-affecting property manifest is incomplete")
    if not set(overrides) <= set(settings):
        raise ValueError("glTF explicit override is not an operator property")
    settings.update(overrides)
    return dict(sorted(settings.items()))


def _input_bindings(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict) or len(value) > 65:
        raise ValueError("exact input content bindings are malformed or unbounded")
    result: dict[str, dict[str, object]] = {}
    for path, raw in value.items():
        if (
            not isinstance(path, str)
            or not isinstance(raw, dict)
            or raw.get("algorithm") != "sha256"
            or not isinstance(raw.get("digest"), str)
            or len(cast(str, raw["digest"])) != 64
            or any(
                character not in "0123456789abcdef"
                for character in cast(str, raw["digest"])
            )
            or not isinstance(raw.get("size_bytes"), int)
            or isinstance(raw.get("size_bytes"), bool)
            or cast(int, raw["size_bytes"]) < 0
            or not isinstance(raw.get("media_type"), str)
            or set(raw) != {"algorithm", "digest", "media_type", "size_bytes"}
        ):
            raise ValueError("exact input content identity is malformed")
        result[path] = dict(raw)
    return result


def _stage_inputs(
    workspace: Path,
    bindings: Mapping[str, Mapping[str, object]],
    request_sha256: str,
) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, dict[str, object]]]:
    stage = tempfile.TemporaryDirectory(
        prefix=f".biella-3d-{request_sha256[:16]}-",
    )
    stage_root = Path(stage.name).resolve(strict=True)
    observed: dict[str, dict[str, object]] = {}
    for relative, expected in sorted(bindings.items()):
        source = _path(workspace, relative, "exact input path", must_exist=True)
        destination = (stage_root / relative).resolve(strict=False)
        if not destination.is_relative_to(stage_root) or destination == stage_root:
            raise ValueError("staged input crossed the private operation root")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as source_file, destination.open("xb") as target:
            while chunk := source_file.read(1024 * 1024):
                target.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        destination.chmod(0o400)
        identity = {
            "algorithm": "sha256",
            "digest": digest.hexdigest(),
            "media_type": expected["media_type"],
            "size_bytes": size,
        }
        if identity != expected:
            raise ValueError("Workspace input differs from exact Artifact content")
        observed[relative] = identity
    return stage, stage_root, observed


def _verify_staged_inputs(
    stage_root: Path,
    expected: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    observed: dict[str, dict[str, object]] = {}
    for relative, identity in sorted(expected.items()):
        path = _path(stage_root, relative, "staged input path", must_exist=True)
        file_identity = _file_identity(path)
        payload = {
            "algorithm": "sha256",
            "digest": file_identity["sha256"],
            "media_type": identity["media_type"],
            "size_bytes": file_identity["size_bytes"],
        }
        if payload != identity:
            raise ValueError("private staged input changed during Blender execution")
        observed[relative] = payload
    return observed


def _stage_reopen_dependencies(
    source_root: Path,
    stage_root: Path,
    expected: Mapping[str, Mapping[str, object]],
) -> None:
    for relative, identity in sorted(expected.items()):
        source = _path(
            source_root,
            relative,
            "reopen dependency source",
            must_exist=True,
        )
        destination = (stage_root / relative).resolve(strict=False)
        if not destination.is_relative_to(stage_root) or destination == stage_root:
            raise ValueError("reopen dependency crossed the private output root")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as source_file, destination.open("xb") as target:
            while chunk := source_file.read(1024 * 1024):
                target.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        destination.chmod(0o400)
        if (
            digest.hexdigest() != identity["digest"]
            or size != identity["size_bytes"]
        ):
            raise ValueError("private reopen dependency identity changed")


def _runtime(bpy: Any) -> dict[str, object]:
    binary_path = Path(str(bpy.app.binary_path)).resolve(strict=True)
    driver_path = Path(__file__).resolve(strict=True)
    driver_identity = _file_identity(driver_path)
    return {
        "binary_path": str(binary_path),
        "binary_sha256": _file_identity(binary_path)["sha256"],
        "driver_path": str(driver_path),
        "driver_sha256": driver_identity["sha256"],
        "driver_size_bytes": driver_identity["size_bytes"],
        "embedded_python": sys.version.split()[0],
        "external_plugins": [_gltf_exporter_identity()],
        "factory_startup": True,
        "tool_name": "Blender",
        "tool_version": str(bpy.app.version_string),
    }


def _failure_report(error: Exception) -> dict[str, object]:
    """Build exact Blender-side evidence for a terminal operation failure."""

    bpy = importlib.import_module("bpy")
    _, request_path = _arguments()
    raw = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Blender operation request schema is malformed")
    operation = raw.get("operation")
    request_sha256 = raw.get("request_sha256")
    source_path = raw.get("source_path")
    output_path = raw.get("output_path")
    auxiliary_paths = raw.get("auxiliary_paths")
    if (
        not isinstance(operation, str)
        or not isinstance(request_sha256, str)
        or len(request_sha256) != 64
        or any(character not in "0123456789abcdef" for character in request_sha256)
        or source_path is not None and not isinstance(source_path, str)
        or not isinstance(output_path, str)
        or not isinstance(auxiliary_paths, list)
        or len(auxiliary_paths) > 64
        or any(not isinstance(item, str) for item in auxiliary_paths)
    ):
        raise ValueError("Blender failure request evidence is malformed")
    return {
        "content_trust": "UNTRUSTED_DATA",
        "declared_auxiliary_paths": sorted(cast(list[str], auxiliary_paths)),
        "driver_evidence": _DRIVER_EVIDENCE,
        "error": f"{type(error).__name__}: {error}",
        "input_content_bindings": _input_bindings(
            raw.get("input_content_bindings")
        ),
        "operation": operation,
        "output_path": output_path,
        "request_sha256": request_sha256,
        "runtime": _runtime(bpy),
        "schema_version": 1,
        "source_path": source_path,
        "valid": False,
    }


def _gltf_exporter_identity() -> dict[str, str]:
    module = importlib.import_module("io_scene_gltf2")
    module_path = Path(str(module.__file__)).resolve(strict=True)
    metadata = getattr(module, "bl_info", None)
    if not isinstance(metadata, dict):
        raise ValueError("glTF exporter metadata is unavailable")
    version = metadata.get("version")
    if (
        not isinstance(version, tuple)
        or not version
        or any(type(item) is not int or item < 0 for item in version)
    ):
        raise ValueError("glTF exporter version is malformed")
    return {
        "digest": _package_python_tree_sha256(module_path.parent),
        "name": "glTF 2.0 format",
        "version": ".".join(str(item) for item in version),
    }


def _inspection(
    bpy: Any,
    bmesh: Any,
    source: Path,
    source_format: str,
    workspace: Path,
    auxiliary_paths: frozenset[str],
) -> dict[str, object]:
    scene = bpy.context.scene
    objects: list[dict[str, object]] = []
    totals = {
        "vertices": 0,
        "edges": 0,
        "faces": 0,
        "triangles": 0,
        "non_manifold_edges": 0,
        "degenerate_faces": 0,
        "duplicate_vertices": 0,
        "raw_coincident_vertices": 0,
        "invalid_normals": 0,
        "invalid_uv_values": 0,
        "missing_uv_layers": 0,
    }
    material_names: set[str] = set()
    texture_names: set[str] = set()
    dependencies: list[dict[str, object]] = []
    bound_dependency_paths: set[str] = set()
    missing_dependencies = 0
    unbound_dependencies = 0
    if (
        len(bpy.data.images) > _MAX_DATABLOCKS
        or len(bpy.data.libraries) > _MAX_DATABLOCKS
        or len(scene.objects) > _MAX_DATABLOCKS
    ):
        raise ValueError("3D datablock inventory exceeds the bounded inspection limit")
    all_images = sorted(bpy.data.images, key=lambda item: str(item.name))
    dependency_count = 0
    for image in all_images:
        texture_names.add(str(image.name)[:256])
        raw = str(image.filepath)
        if not raw or bool(image.packed_file):
            continue
        dependency_count += 1
        dependency_source = source
        image_library = getattr(image, "library", None)
        if image_library is not None:
            library_path = _dependency_path(
                source,
                workspace,
                str(image_library.filepath),
            )
            if library_path is None:
                dependency_source = Path("/")
            else:
                dependency_source = library_path
        resolved = _dependency_path(dependency_source, workspace, raw)
        exists = resolved is not None and resolved.is_file()
        bound = (
            resolved is not None
            and resolved.relative_to(workspace.resolve()).as_posix()
            in auxiliary_paths
        )
        binding_path = (
            None
            if resolved is None
            else resolved.relative_to(workspace.resolve()).as_posix()
        )
        if bound and binding_path is not None:
            bound_dependency_paths.add(binding_path)
        if not exists:
            missing_dependencies += 1
        if exists and not bound:
            unbound_dependencies += 1
        if len(dependencies) < _MAX_NAMES:
            dependencies.append(
                {
                    "exists": exists,
                    "kind": "texture",
                    "binding_path": binding_path,
                    "name": str(image.name)[:256],
                    "path": raw[:1024],
                    "path_scope": (
                        "WORKSPACE_RELATIVE"
                        if resolved is not None
                        else "EXTERNAL_REJECTED"
                    ),
                    "provenance_bound": bound,
                }
            )
    all_libraries = sorted(bpy.data.libraries, key=lambda item: str(item.name))
    for library in all_libraries:
        raw = str(library.filepath)
        if not raw:
            continue
        dependency_count += 1
        resolved = _dependency_path(source, workspace, raw)
        exists = resolved is not None and resolved.is_file()
        binding_path = (
            None
            if resolved is None
            else resolved.relative_to(workspace.resolve()).as_posix()
        )
        bound = binding_path in auxiliary_paths
        if not exists:
            missing_dependencies += 1
        if exists and not bound:
            unbound_dependencies += 1
        if bound and binding_path is not None:
            bound_dependency_paths.add(binding_path)
        if len(dependencies) < _MAX_NAMES:
            dependencies.append(
                {
                    "binding_path": binding_path,
                    "exists": exists,
                    "kind": "linked-library",
                    "name": str(library.name)[:256],
                    "path": raw[:1024],
                    "path_scope": (
                        "WORKSPACE_RELATIVE"
                        if resolved is not None
                        else "EXTERNAL_REJECTED"
                    ),
                    "provenance_bound": bound,
                }
            )
    all_objects = sorted(scene.objects, key=lambda item: str(item.name))
    inventory_digest = hashlib.sha256()
    total_mesh_elements = 0
    for object_index, object_value in enumerate(all_objects):
        item: dict[str, object] = {
            "children": [str(child.name)[:256] for child in sorted(object_value.children, key=lambda child: str(child.name))[:_MAX_NAMES]],
            "dimensions": [round(float(value), 9) for value in object_value.dimensions],
            "location": [round(float(value), 9) for value in object_value.location],
            "name": str(object_value.name)[:256],
            "parent": None if object_value.parent is None else str(object_value.parent.name)[:256],
            "rotation_euler": [round(float(value), 9) for value in object_value.rotation_euler],
            "scale": [round(float(value), 9) for value in object_value.scale],
            "type": str(object_value.type),
        }
        if object_value.type == "MESH":
            mesh = object_value.data
            mesh_elements = (
                len(mesh.vertices)
                + len(mesh.edges)
                + len(mesh.polygons)
                + len(mesh.loops)
            )
            total_mesh_elements += mesh_elements
            if (
                mesh_elements > _MAX_MESH_ELEMENTS
                or total_mesh_elements > _MAX_TOTAL_MESH_ELEMENTS
                or len(mesh.materials) > _MAX_NAMES
                or len(mesh.uv_layers) > _MAX_NAMES
            ):
                raise ValueError(
                    "mesh inventory exceeds the bounded inspection limit"
                )
            mesh.calc_loop_triangles()
            bm = bmesh.new()
            bm.from_mesh(mesh)
            degenerate = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
            coordinate_keys = {
                int(vertex.index): _coordinate_key(vertex.co)
                for vertex in mesh.vertices
            }
            coordinates: dict[tuple[int, int, int], int] = {}
            raw_duplicates = 0
            for coordinate_key in coordinate_keys.values():
                if coordinate_key in coordinates:
                    raw_duplicates += 1
                else:
                    coordinates[coordinate_key] = 1
            edge_uses: dict[
                tuple[tuple[int, int, int], tuple[int, int, int]], int
            ] = {}
            edge_orientation: dict[
                tuple[tuple[int, int, int], tuple[int, int, int]], int
            ] = {}
            for polygon in mesh.polygons:
                polygon_keys = [
                    _coordinate_key(mesh.vertices[index].co)
                    for index in polygon.vertices
                ]
                for index, first in enumerate(polygon_keys):
                    second = polygon_keys[(index + 1) % len(polygon_keys)]
                    edge = (first, second) if first <= second else (second, first)
                    edge_uses[edge] = edge_uses.get(edge, 0) + 1
                    edge_orientation[edge] = edge_orientation.get(edge, 0) + (
                        1 if first <= second else -1
                    )
            non_manifold = sum(1 for count in edge_uses.values() if count != 2)
            if source_format == "BLEND":
                duplicates = raw_duplicates
            else:
                corner_attributes: dict[int, list[tuple[object, ...]]] = {
                    index: [] for index in coordinate_keys
                }
                for polygon in mesh.polygons:
                    polygon_vertices = tuple(int(item) for item in polygon.vertices)
                    polygon_loops = tuple(int(item) for item in polygon.loop_indices)
                    for offset, loop_index in enumerate(polygon_loops):
                        loop = mesh.loops[loop_index]
                        vertex_index = int(loop.vertex_index)
                        previous_vertex = polygon_vertices[offset - 1]
                        next_vertex = polygon_vertices[
                            (offset + 1) % len(polygon_vertices)
                        ]
                        loop_normal = getattr(loop, "normal", (0.0, 0.0, 0.0))
                        uvs = tuple(
                            (
                                int(round(float(layer.data[loop_index].uv[0]) * 1_000_000_000)),
                                int(round(float(layer.data[loop_index].uv[1]) * 1_000_000_000)),
                            )
                            for layer in mesh.uv_layers
                        )
                        corner_attributes[vertex_index].append(
                            (
                                int(polygon.material_index),
                                _coordinate_key(loop_normal),
                                coordinate_keys[previous_vertex],
                                coordinate_keys[next_vertex],
                                uvs,
                            )
                        )
                exact_vertices: dict[tuple[object, ...], int] = {}
                duplicates = 0
                for vertex in mesh.vertices:
                    signature = (
                        coordinate_keys[int(vertex.index)],
                        _coordinate_key(vertex.normal),
                        tuple(
                            sorted(
                                (
                                    int(group.group),
                                    int(round(float(group.weight) * 1_000_000_000)),
                                )
                                for group in vertex.groups
                            )
                        ),
                        tuple(sorted(corner_attributes[int(vertex.index)])),
                    )
                    if signature in exact_vertices:
                        duplicates += 1
                    else:
                        exact_vertices[signature] = 1
            invalid_normals = sum(
                1
                for polygon in mesh.polygons
                if not math.isfinite(float(polygon.normal.length))
                or float(polygon.normal.length) < 0.999
            )
            invalid_normals += sum(
                1
                for edge, count in edge_uses.items()
                if count == 2 and edge_orientation[edge] != 0
            )
            bm.free()
            all_materials = {
                str(material.name)[:256]
                for material in mesh.materials
                if material is not None
            }
            material_names.update(all_materials)
            materials = sorted(all_materials)[:_MAX_NAMES]
            uv_layers = sorted(str(layer.name)[:256] for layer in mesh.uv_layers)[:_MAX_NAMES]
            invalid_uv_values = sum(
                1
                for layer in mesh.uv_layers
                for loop in layer.data
                if not all(math.isfinite(float(value)) for value in loop.uv)
            )
            mesh_facts = {
                "degenerate_faces": degenerate,
                "duplicate_vertices": duplicates,
                "raw_coincident_vertices": raw_duplicates,
                "edges": len(mesh.edges),
                "faces": len(mesh.polygons),
                "invalid_normals": invalid_normals,
                "invalid_uv_values": invalid_uv_values,
                "materials": materials,
                "missing_uv_layers": int(len(mesh.uv_layers) == 0),
                "non_manifold_edges": non_manifold,
                "triangles": len(mesh.loop_triangles),
                "uv_layers": uv_layers,
                "vertices": len(mesh.vertices),
            }
            item["mesh"] = mesh_facts
            for metric_name in totals:
                totals[metric_name] += cast(int, mesh_facts[metric_name])
        inventory_digest.update(
            json.dumps(
                item,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        )
        inventory_digest.update(b"\n")
        if object_index < _MAX_OBJECTS:
            objects.append(item)
    dimensions = [
        abs(float(value))
        for item in all_objects
        if item.type == "MESH"
        for value in item.dimensions
    ]
    character = _character_facts(bpy)
    return {
        "bone_count": character["bone_count"],
        "bounded": True,
        "bound_dependency_paths": sorted(bound_dependency_paths),
        "cameras": sum(1 for item in all_objects if item.type == "CAMERA"),
        "dependencies": dependencies,
        "dependency_count": dependency_count,
        "dependencies_truncated": dependency_count > _MAX_NAMES,
        "deformation": character["deformation"],
        "full_inventory_sha256": inventory_digest.hexdigest(),
        "hierarchy_roots": [
            str(item.name)[:256] for item in all_objects if item.parent is None
        ][:_MAX_NAMES],
        "lights": sum(1 for item in all_objects if item.type == "LIGHT"),
        "linked_libraries": [
            str(item.name)[:256] for item in all_libraries[:_MAX_NAMES]
        ],
        "linked_library_count": len(all_libraries),
        "materials": sorted(material_names)[:_MAX_NAMES],
        "material_count": len(material_names),
        "maximum_dimension": max(dimensions, default=0.0),
        "mesh_count": sum(1 for item in all_objects if item.type == "MESH"),
        "minimum_dimension": min(dimensions, default=0.0),
        "missing_dependencies": missing_dependencies,
        "object_count": len(all_objects),
        "objects": objects,
        "schema_version": 1,
        "animation": character["animation"],
        "skeleton_count": character["skeleton_count"],
        "skeletons": character["skeletons"],
        "skin": character["skin"],
        "source_format": source_format,
        "duplicate_vertex_predicate": (
            "NATIVE_POSITION_COINCIDENCE_V1"
            if source_format == "BLEND"
            else "INTERCHANGE_FULL_CORNER_ATTRIBUTES_V1"
        ),
        "textures": sorted(texture_names)[:_MAX_NAMES],
        "texture_count": len(texture_names),
        "totals": totals,
        "truncated": len(all_objects) > _MAX_OBJECTS,
        "unit_scale": float(scene.unit_settings.scale_length),
        "unit_system": str(scene.unit_settings.system),
        "unbound_dependencies": unbound_dependencies,
    }


def _character_facts(bpy: Any) -> dict[str, object]:
    armatures = sorted(
        (item for item in bpy.context.scene.objects if item.type == "ARMATURE"),
        key=lambda item: str(item.name),
    )
    skeletons: list[dict[str, object]] = []
    bone_names: set[str] = set()
    posed_bones = 0
    for armature in armatures:
        bones = []
        for bone in sorted(armature.data.bones, key=lambda item: str(item.name)):
            name = str(bone.name)[:256]
            bone_names.add(name)
            bones.append(
                {
                    "head": [float(item) for item in bone.head_local],
                    "name": name,
                    "parent_name": None if bone.parent is None else str(bone.parent.name)[:256],
                    "tail": [float(item) for item in bone.tail_local],
                    "use_deform": bool(bone.use_deform),
                }
            )
        for pose_bone in armature.pose.bones:
            if not bool(pose_bone.matrix_basis.is_identity):
                posed_bones += 1
        skeletons.append(
            {
                "bones": bones,
                "name": str(armature.name)[:256],
                "rest_pose_sha256": _payload_digest(bones),
            }
        )
    meshes = _mesh_objects(bpy)
    rigged_meshes = 0
    skinned_meshes = 0
    nonfinite_weights = 0
    nonnormalized_vertices = 0
    unknown_weight_groups = 0
    vertices_without_weights = 0
    maximum_influences = 0
    for mesh in meshes:
        if any(
            modifier.type == "ARMATURE" and getattr(modifier, "object", None) in armatures
            for modifier in mesh.modifiers
        ):
            rigged_meshes += 1
        groups = {int(group.index): str(group.name) for group in mesh.vertex_groups}
        mesh_has_weights = False
        for vertex in mesh.data.vertices:
            influences = list(vertex.groups)
            maximum_influences = max(maximum_influences, len(influences))
            if not influences:
                vertices_without_weights += 1
                continue
            mesh_has_weights = True
            total = 0.0
            for influence in influences:
                weight = float(influence.weight)
                if not math.isfinite(weight):
                    nonfinite_weights += 1
                else:
                    total += weight
                if groups.get(int(influence.group)) not in bone_names:
                    unknown_weight_groups += 1
            if not math.isfinite(total) or abs(total - 1.0) > 1e-6:
                nonnormalized_vertices += 1
        if mesh_has_weights:
            skinned_meshes += 1
    return {
        "animation": _animation_facts(bpy),
        "bone_count": sum(len(cast(list[object], item["bones"])) for item in skeletons),
        "deformation": {
            "deformed_mesh_count": rigged_meshes if posed_bones else 0,
            "posed_bones": posed_bones,
        },
        "skeleton_count": len(skeletons),
        "skeletons": skeletons,
        "skin": {
            "maximum_influences": maximum_influences,
            "nonfinite_weights": nonfinite_weights,
            "nonnormalized_vertices": nonnormalized_vertices,
            "rigged_mesh_count": rigged_meshes,
            "skinned_mesh_count": skinned_meshes,
            "unknown_weight_groups": unknown_weight_groups,
            "vertices_without_weights": vertices_without_weights,
        },
    }


def _checks(inspection: Mapping[str, object], requirements: Mapping[str, object]) -> tuple[dict[str, bool], bool]:
    totals = cast(Mapping[str, int], inspection["totals"])
    checks: dict[str, bool] = {
        "dependencies_present": cast(int, inspection["missing_dependencies"]) == 0,
        "dependencies_provenanced": cast(int, inspection["unbound_dependencies"]) == 0,
        "uv_data_valid": totals["invalid_uv_values"] == 0,
    }
    if bool(requirements.get("require_mesh", False)):
        checks["has_mesh"] = cast(int, inspection["mesh_count"]) > 0
    if bool(requirements.get("require_manifold", False)):
        checks["manifold"] = totals["non_manifold_edges"] == 0
    if bool(requirements.get("reject_degenerate_faces", False)):
        checks["non_degenerate"] = totals["degenerate_faces"] == 0
    if bool(requirements.get("reject_duplicate_vertices", False)):
        checks["no_duplicate_vertices"] = totals["duplicate_vertices"] == 0
    if bool(requirements.get("require_valid_normals", False)):
        checks["valid_normals"] = totals["invalid_normals"] == 0
    if bool(requirements.get("require_uv", False)):
        checks["uv_present"] = (
            cast(int, inspection["mesh_count"]) > 0
            and totals["missing_uv_layers"] == 0
        )
    maximum_faces = requirements.get("maximum_faces")
    if maximum_faces is not None:
        checks["project_face_limit"] = totals["faces"] <= int(cast(int, maximum_faces))
    minimum_dimension = requirements.get("minimum_dimension")
    if minimum_dimension is not None:
        checks["project_minimum_dimension"] = float(cast(float | int, inspection["minimum_dimension"])) >= float(cast(float, minimum_dimension))
    maximum_dimension = requirements.get("maximum_dimension")
    if maximum_dimension is not None:
        checks["project_maximum_dimension"] = float(cast(float | int, inspection["maximum_dimension"])) <= float(cast(float, maximum_dimension))
    required_units = requirements.get("required_unit_system")
    if required_units is not None:
        checks["project_unit_system"] = inspection["unit_system"] == required_units
    skin = cast(Mapping[str, int], inspection["skin"])
    deformation = cast(Mapping[str, int], inspection["deformation"])
    animation = cast(Mapping[str, int | float], inspection["animation"])
    if bool(requirements.get("require_skeleton", False)):
        checks["has_skeleton"] = cast(int, inspection["skeleton_count"]) > 0
    if bool(requirements.get("require_rig", False)):
        checks["has_rig"] = skin["rigged_mesh_count"] > 0
    if bool(requirements.get("require_skin", False)):
        checks["has_skin"] = (
            skin["skinned_mesh_count"] > 0
            and skin["vertices_without_weights"] == 0
            and skin["unknown_weight_groups"] == 0
        )
    if bool(requirements.get("require_normalized_weights", False)):
        checks["normalized_weights"] = (
            skin["nonfinite_weights"] == 0
            and skin["nonnormalized_vertices"] == 0
        )
    maximum_influences = requirements.get("maximum_weight_influences")
    if maximum_influences is not None:
        checks["weight_influence_limit"] = skin["maximum_influences"] <= int(cast(int, maximum_influences))
    if bool(requirements.get("require_deformation", False)):
        checks["has_deformation"] = (
            deformation["posed_bones"] > 0 and deformation["deformed_mesh_count"] > 0
        )
    if bool(requirements.get("require_animation", False)):
        checks["has_animation"] = int(animation["action_count"]) > 0
    if bool(requirements.get("require_baked_animation", False)):
        checks["has_baked_animation"] = int(animation["baked_action_count"]) > 0
    if bool(requirements.get("require_loop", False)):
        maximum_loop_error = requirements.get("maximum_loop_error")
        checks["loop_within_tolerance"] = (
            maximum_loop_error is not None
            and float(animation["maximum_loop_error"]) <= float(cast(float, maximum_loop_error))
        )
    return checks, all(checks.values())


def _export(
    bpy: Any,
    output: Path,
    config: Mapping[str, str | int | float | bool],
) -> dict[str, object]:
    suffix = output.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        _embed_animation_export_manifest(bpy)
        export_format = "GLB" if suffix == ".glb" else "GLTF_EMBEDDED"
        export_yup = bool(config.get("export_yup", True))
        settings = _gltf_effective_settings(
            bpy,
            {
                "export_apply": True,
                "export_draco_mesh_compression_enable": False,
                "export_extras": True,
                "export_format": export_format,
                "export_use_gltfpack": False,
                "export_yup": export_yup,
            },
        )
        bpy.ops.export_scene.gltf(
            filepath=str(output),
            **settings,
        )
        return {
            "axis_conversion": (
                "BLENDER_Z_UP_TO_GLTF_Y_UP"
                if export_yup
                else "PRESERVE_BLENDER_Z_UP"
            ),
            "exporter": _gltf_exporter_identity(),
            "operator": "EXPORT_SCENE_OT_gltf",
            "settings": settings,
            "settings_count": len(settings),
            "settings_schema": "BLENDER_RNA_EFFECTIVE_OUTPUT_V1",
            "settings_sha256": _payload_digest(settings),
            "source_units": {
                "scale_length": float(bpy.context.scene.unit_settings.scale_length),
                "system": str(bpy.context.scene.unit_settings.system),
            },
            "target_format": "GLB" if suffix == ".glb" else "GLTF",
            "target_meters_per_unit": 1.0,
        }
    raise ValueError("requested interchange format is unavailable")


def _preview(bpy: Any, output: Path, config: Mapping[str, str | int | float | bool]) -> None:
    if output.suffix.lower() != ".png":
        raise ValueError("verified preview output must be PNG")
    scene = bpy.context.scene
    for item in list(scene.objects):
        if item.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(item, do_unlink=True)
    bpy.ops.object.camera_add(location=(4.5, -4.5, 3.4))
    camera = bpy.context.active_object
    camera.name = "BiellaPreviewCamera"
    direction = -camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(2.5, -2.5, 5.0))
    key = bpy.context.active_object
    key.data.energy = 900.0
    key.data.shape = "DISK"
    key.data.size = 4.0
    bpy.ops.object.light_add(type="AREA", location=(-3.0, 1.0, 2.0))
    fill = bpy.context.active_object
    fill.data.energy = 450.0
    fill.data.size = 3.0
    resolution = int(config.get("resolution", 96))
    if not 32 <= resolution <= 512:
        raise ValueError("preview resolution is outside the bounded Task request")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(config.get("samples", 8))
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    if scene.world is None:
        scene.world = bpy.data.worlds.new("BiellaPreviewWorld")
    scene.world.color = (0.04, 0.04, 0.04)
    bpy.ops.render.render(write_still=True)


def _main() -> None:
    bpy = importlib.import_module("bpy")
    bmesh = importlib.import_module("bmesh")
    workspace, request_path = _arguments()
    raw = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("Blender operation request schema is malformed")
    operation = raw.get("operation")
    if not isinstance(operation, str):
        raise ValueError("Blender operation is malformed")
    request_sha256 = raw.get("request_sha256")
    if (
        not isinstance(request_sha256, str)
        or len(request_sha256) != 64
        or any(character not in "0123456789abcdef" for character in request_sha256)
    ):
        raise ValueError("Blender request digest is malformed")
    config = _scalar_mapping(raw.get("operation_config"), "operation_config")
    auxiliary_raw = raw.get("auxiliary_paths", [])
    if (
        not isinstance(auxiliary_raw, list)
        or len(auxiliary_raw) > 64
        or any(not isinstance(item, str) for item in auxiliary_raw)
    ):
        raise ValueError("auxiliary Artifact paths are malformed or unbounded")
    auxiliary_paths = frozenset(cast(list[str], auxiliary_raw))
    requirements_raw = raw.get("validation_requirements")
    if not isinstance(requirements_raw, dict):
        raise ValueError("validation_requirements are malformed")
    if operation == "describe_runtime":
        identity_payload = raw.get("identity")
        if (
            not isinstance(identity_payload, dict)
            or _payload_digest(identity_payload) != request_sha256
            or config
            or auxiliary_paths
            or requirements_raw
        ):
            raise ValueError("runtime probe identity payload changed")
        print(
            _RESULT_MARKER
            + json.dumps(
                {
                    "content_trust": "UNTRUSTED_DATA",
                    "driver_evidence": _DRIVER_EVIDENCE,
                    "operation": operation,
                    "request_sha256": request_sha256,
                    "runtime": _runtime(bpy),
                    "schema_version": 1,
                },
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return
    request_payload = raw.get("request")
    identity_payload = raw.get("identity")
    if (
        not isinstance(request_payload, dict)
        or _payload_digest(request_payload) != request_sha256
        or not isinstance(identity_payload, dict)
        or _payload_digest(identity_payload)
        != request_payload.get("identity_digest")
        or operation != request_payload.get("operation")
        or config != request_payload.get("operation_config")
        or raw.get("source_path") != request_payload.get("source_path")
        or raw.get("output_path") != request_payload.get("output_path")
        or requirements_raw != request_payload.get("validation_requirements")
    ):
        raise ValueError("driver payload differs from exact semantic request")
    skeleton_payload = request_payload.get("skeleton_spec")
    character_operation = operation in {"rig", "skin", "deform", "animate", "retarget", "bake"}
    if character_operation and skeleton_payload is None:
        raise ValueError("character operation lacks exact skeleton specification")
    skeleton = None if skeleton_payload is None else _skeleton_spec(skeleton_payload)
    animation_payload = request_payload.get("animation_clip_spec")
    animation_operations = {"animate", "retarget", "bake"}
    if operation in animation_operations and animation_payload is None:
        raise ValueError("animation operation lacks an exact clip specification")
    animation_clip = (
        None if animation_payload is None else _animation_clip_spec(animation_payload)
    )
    retarget_payload = request_payload.get("retarget_spec")
    if operation == "retarget" and retarget_payload is None:
        raise ValueError("retarget operation lacks an exact mapping specification")
    retarget = None if retarget_payload is None else _retarget_spec(retarget_payload)
    root_motion_policy = request_payload.get("root_motion_policy")
    if root_motion_policy not in {"preserve", "extract", "remove"}:
        raise ValueError("animation root motion policy is malformed")
    environment_payload = request_payload.get("environment_spec")
    if operation == "environment" and not isinstance(environment_payload, dict):
        raise ValueError("environment operation lacks exact layout specification")
    environment_placed_assets: list[dict[str, object]] = []
    skin_bindings_raw = request_payload.get("skin_bindings", [])
    if not isinstance(skin_bindings_raw, list) or len(skin_bindings_raw) > _MAX_MESH_ELEMENTS:
        raise ValueError("character skin bindings are malformed")
    skin_bindings: list[Mapping[str, object]] = []
    skeleton_bones = (
        set()
        if skeleton is None
        else {
            cast(str, item["name"])
            for item in cast(list[Mapping[str, object]], skeleton["bones"])
        }
    )
    for binding in skin_bindings_raw:
        if not isinstance(binding, dict) or set(binding) != {"vertex_index", "weights"}:
            raise ValueError("character skin binding is malformed")
        index = binding.get("vertex_index")
        weights = binding.get("weights")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or not isinstance(weights, list)
            or not weights
            or len(weights) > 32
        ):
            raise ValueError("character skin binding is malformed")
        names: set[str] = set()
        total = 0.0
        for influence in weights:
            if not isinstance(influence, dict) or set(influence) != {"bone_name", "weight"}:
                raise ValueError("character skin influence is malformed")
            name = influence.get("bone_name")
            weight = influence.get("weight")
            if (
                not isinstance(name, str)
                or name in names
                or name not in skeleton_bones
                or isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or not math.isfinite(float(weight))
                or not 0.0 <= float(weight) <= 1.0
            ):
                raise ValueError("character skin influence is malformed")
            names.add(name)
            total += float(weight)
        if abs(total - 1.0) > 1e-9:
            raise ValueError("character skin influences are not normalized")
        skin_bindings.append(cast(Mapping[str, object], binding))
    auxiliary_bindings = request_payload.get("auxiliary_artifact_bindings")
    if (
        not isinstance(auxiliary_bindings, dict)
        or len(auxiliary_paths) != len(auxiliary_raw)
        or auxiliary_paths != frozenset(auxiliary_bindings)
    ):
        raise ValueError("driver auxiliary paths differ from semantic request")
    source_raw = raw.get("source_path")
    expected_inputs = _input_bindings(raw.get("input_content_bindings"))
    expected_paths = set(auxiliary_paths)
    if source_raw is not None:
        if not isinstance(source_raw, str):
            raise ValueError("source_path is malformed")
        expected_paths.add(source_raw)
    if set(expected_inputs) != expected_paths:
        raise ValueError("driver input identities differ from semantic paths")
    logical_output = _path(
        workspace,
        raw.get("output_path"),
        "output_path",
        must_exist=False,
    )
    staging_root_name = f".biella-three-d-stage-{request_sha256}"
    expected_staging = PurePosixPath(
        staging_root_name,
        str(raw["output_path"]),
    ).as_posix()
    if raw.get("staging_output_path") != expected_staging:
        raise ValueError("private output staging path changed")
    stage_root = _path(
        workspace,
        staging_root_name,
        "staging output root",
        must_exist=True,
    )
    output = _path(
        workspace,
        expected_staging,
        "staging_output_path",
        must_exist=False,
    )
    stage: tempfile.TemporaryDirectory[str] | None = None
    execution_workspace = workspace
    input_content_bindings: dict[str, dict[str, object]] = {}
    if expected_inputs:
        stage, execution_workspace, input_content_bindings = _stage_inputs(
            workspace,
            expected_inputs,
            request_sha256,
        )
        _stage_reopen_dependencies(
            execution_workspace,
            stage_root,
            expected_inputs,
        )
    source: Path | None = None
    source_format = "NONE"
    source_inspection: dict[str, object] | None = None
    if source_raw is not None:
        source = _path(
            execution_workspace,
            source_raw,
            "source_path",
            must_exist=True,
        )
        source_format = _load(bpy, source)
        source_inspection = _inspection(
            bpy,
            bmesh,
            source,
            source_format,
            execution_workspace,
            auxiliary_paths,
        )
        if operation not in {"inspect", "validate"} and (
            source_inspection["missing_dependencies"] != 0
            or source_inspection["unbound_dependencies"] != 0
        ):
            raise ValueError(
                "source contains missing or provenance-unbound dependencies"
            )
    try:
        output.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError("Blender output path contains stale unclaimed bytes")
    export_evidence: dict[str, object] | None = None
    if operation == "model":
        _create(bpy, config)
        _save_blend(bpy, output)
    elif operation == "mesh_edit":
        _modify(bpy, config)
        _save_blend(bpy, output)
    elif operation == "topology":
        _topology(bpy, config)
        _save_blend(bpy, output)
    elif operation == "uv":
        _uv(bpy)
        _save_blend(bpy, output)
    elif operation == "material":
        _apply_material(
            bpy,
            config,
            execution_workspace,
            workspace,
            logical_output,
            auxiliary_paths,
        )
        _save_blend(bpy, output)
    elif operation == "rig":
        if skeleton is None:
            raise ValueError("character rig lacks skeleton")
        _rig(bpy, skeleton)
        _save_blend(bpy, output)
    elif operation == "skin":
        _skin(bpy, skin_bindings)
        _save_blend(bpy, output)
    elif operation == "deform":
        _deform(bpy, config)
        _save_blend(bpy, output)
    elif operation == "animate":
        if animation_clip is None:
            raise ValueError("animation clip is absent")
        _animate(bpy, animation_clip, cast(str, root_motion_policy))
        _save_blend(bpy, output)
    elif operation == "retarget":
        if animation_clip is None or retarget is None or skeleton is None:
            raise ValueError("retarget evidence is absent")
        _retarget(bpy, animation_clip, retarget, skeleton, cast(str, root_motion_policy))
        _save_blend(bpy, output)
    elif operation == "bake":
        if animation_clip is None:
            raise ValueError("baked animation clip is absent")
        _animate(bpy, animation_clip, cast(str, root_motion_policy), baked=True)
        _save_blend(bpy, output)
    elif operation == "environment":
        assert isinstance(environment_payload, dict)
        environment_placed_assets = _environment(bpy, environment_payload, execution_workspace)
        _save_blend(bpy, output)
    elif operation == "scene":
        _scene(
            bpy,
            config,
            execution_workspace,
            workspace,
            logical_output,
            auxiliary_paths,
        )
        _save_blend(bpy, output)
    elif operation == "optimize":
        _optimize(bpy, config)
        _save_blend(bpy, output)
    elif operation == "convert":
        export_evidence = _export(bpy, output, config)
        source_format = _load(bpy, output)
    elif operation == "preview":
        _preview(bpy, output, config)
    elif operation not in {"inspect", "validate"}:
        raise ValueError("unsupported Blender operation")
    if operation in {
        "model",
        "mesh_edit",
        "topology",
        "uv",
        "material",
        "rig",
        "skin",
        "deform",
        "animate",
        "retarget",
        "bake",
        "environment",
        "scene",
        "optimize",
    }:
        source_format = _load(bpy, output)
    generated_output = operation in {"model", "mesh_edit", "topology", "uv", "material", "rig", "skin", "deform", "animate", "retarget", "bake", "environment", "scene", "convert", "optimize"}
    inspected_source = output if generated_output else source
    if operation == "preview":
        inspected_source = source
    if inspected_source is None:
        raise ValueError("3D operation lacks inspection subject")
    inspection = _inspection(
        bpy,
        bmesh,
        output if generated_output else inspected_source,
        source_format if source is not None else "BLEND",
        stage_root if generated_output else execution_workspace,
        auxiliary_paths,
    )
    if stage is not None:
        input_content_bindings = _verify_staged_inputs(
            execution_workspace,
            expected_inputs,
        )
    used_auxiliary_paths = set(
        cast(list[str], inspection["bound_dependency_paths"])
    )
    if operation == "environment" and environment_payload is not None:
        used_auxiliary_paths.update(
            cast(str, item["binding_path"])
            for item in cast(list[Mapping[str, object]], environment_payload["placed_assets"])
        )
    if source_inspection is not None:
        used_auxiliary_paths.update(
            cast(list[str], source_inspection["bound_dependency_paths"])
        )
    report: dict[str, object] = {
        "content_trust": "UNTRUSTED_DATA",
        "declared_auxiliary_paths": sorted(auxiliary_paths),
        "driver_evidence": _DRIVER_EVIDENCE,
        "input_content_bindings": input_content_bindings,
        "inspection": inspection,
        "inspection_subject": _file_identity(inspected_source),
        "operation": operation,
        "output_path": str(raw["output_path"]),
        "request_sha256": request_sha256,
        "runtime": _runtime(bpy),
        "schema_version": 1,
        "source_path": source_raw,
        "used_auxiliary_paths": sorted(used_auxiliary_paths),
    }
    if source_inspection is not None:
        report["source_inspection"] = source_inspection
    if skeleton_payload is not None:
        report["character_identity"] = {
            "mesh_sha256": _file_identity(inspected_source)["sha256"],
            "skeleton_sha256": _payload_digest(skeleton_payload),
        }
    if animation_payload is not None and animation_clip is not None:
        report["animation_identity"] = {
            "clip_sha256": _payload_digest(animation_payload),
            "root_motion_policy": root_motion_policy,
            "source_skeleton_sha256": animation_clip["source_skeleton_sha256"],
            "target_skeleton_sha256": (
                None if skeleton_payload is None else _payload_digest(skeleton_payload)
            ),
            "retarget_sha256": (
                None if retarget_payload is None else _payload_digest(retarget_payload)
            ),
        }
    if environment_payload is not None:
        report["environment_identity"] = {
            "layout_sha256": _payload_digest(environment_payload),
            "placed_assets": environment_placed_assets,
            "seed": environment_payload.get("seed"),
        }
    if operation not in {"inspect", "validate"}:
        report["output"] = _file_identity(output)
    if operation == "validate":
        checks, valid = _checks(inspection, requirements_raw)
        report["checks"] = checks
        report["valid"] = valid
    if operation == "convert":
        report["export_format"] = output.suffix.lower().removeprefix(".").upper()
        report["export"] = export_evidence
    if operation == "preview":
        report["preview_engine"] = "CYCLES_CPU"
    if operation in {"inspect", "validate"}:
        output.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    print(_RESULT_MARKER + json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True))
    if stage is not None:
        stage.cleanup()


if __name__ == "__main__":
    try:
        _main()
    except Exception as error:
        try:
            failure = _failure_report(error)
        except Exception:
            failure = {
                "error": f"{type(error).__name__}: {error}",
                "schema_version": 1,
                "valid": False,
            }
        print(
            _RESULT_MARKER
            + json.dumps(
                failure,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        raise
