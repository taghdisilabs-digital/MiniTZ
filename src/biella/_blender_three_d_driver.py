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


def _load(bpy: Any, source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
        return "BLEND"
    _reset(bpy)
    if suffix in {".glb", ".gltf"}:
        _self_contained_gltf(source)
        bpy.ops.import_scene.gltf(filepath=str(source))
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


def _save_blend(bpy: Any, output: Path) -> None:
    if output.suffix.lower() != ".blend":
        raise ValueError("editable Blender source requires .blend output")
    bpy.ops.wm.save_as_mainfile(
        filepath=str(output),
        check_existing=False,
        relative_remap=False,
    )


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
    return {
        "bounded": True,
        "bound_dependency_paths": sorted(bound_dependency_paths),
        "cameras": sum(1 for item in all_objects if item.type == "CAMERA"),
        "dependencies": dependencies,
        "dependency_count": dependency_count,
        "dependencies_truncated": dependency_count > _MAX_NAMES,
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
    return checks, all(checks.values())


def _export(
    bpy: Any,
    output: Path,
    config: Mapping[str, str | int | float | bool],
) -> dict[str, object]:
    suffix = output.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        export_format = "GLB" if suffix == ".glb" else "GLTF_EMBEDDED"
        export_yup = bool(config.get("export_yup", True))
        settings = _gltf_effective_settings(
            bpy,
            {
                "export_apply": True,
                "export_draco_mesh_compression_enable": False,
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
        "scene",
        "optimize",
    }:
        source_format = _load(bpy, output)
    generated_output = operation in {"model", "mesh_edit", "topology", "uv", "material", "scene", "convert", "optimize"}
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
