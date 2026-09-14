"""Adapter-local Blender render worker; no public contract types live here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


def _device(scene: Any, bpy: Any, policy: dict[str, Any]) -> dict[str, object]:
    backend = str(policy["backend"]).upper()
    requested = tuple(str(item) for item in policy.get("device_ids", ()))
    if backend == "CPU":
        scene.cycles.device = "CPU"
        return {"backend": "CPU", "devices": ["CPU"]}
    if backend not in {"CUDA", "OPTIX"} or not requested:
        raise ValueError("GPU render requires exact CUDA/OptiX device identities")
    addon = bpy.context.preferences.addons.get("cycles")
    if addon is None:
        raise ValueError("Cycles preferences are unavailable")
    preferences = addon.preferences
    preferences.compute_device_type = backend
    preferences.get_devices()
    selected: list[str] = []
    for device in preferences.devices:
        identity = f"{device.type}:{device.id}:{device.name}"
        enabled = any(token in identity for token in requested)
        device.use = enabled
        if enabled:
            selected.append(identity)
    if len(selected) != len(requested):
        raise ValueError("requested CUDA/OptiX devices were not exactly available")
    scene.cycles.device = "GPU"
    return {"backend": backend, "devices": sorted(selected)}


def _camera(scene: Any, bpy: Any, config: dict[str, Any]) -> Any:
    name = str(config["object"])
    existing = bpy.data.objects.get(name)
    if existing is None:
        if config["materialization"] != "CREATE_EXACT":
            raise ValueError("exact camera object is missing")
        camera_data = bpy.data.cameras.new(name + "Data")
        existing = bpy.data.objects.new(name, camera_data)
        scene.collection.objects.link(existing)
    if getattr(existing, "type", None) != "CAMERA":
        raise ValueError("exact camera object is not a camera")
    settings = config["settings"]
    camera_data = existing.data
    camera_data.type = settings["projection"]
    camera_data.clip_start = float(settings["clip_start"])
    camera_data.clip_end = float(settings["clip_end"])
    camera_data.sensor_width = float(settings["sensor_width_mm"])
    if camera_data.type == "PERSP":
        camera_data.lens = float(settings["lens_mm"])
    else:
        camera_data.ortho_scale = float(settings["ortho_scale"])
    matrix = config["transform"]
    existing.matrix_world = [matrix[index:index + 4] for index in range(0, 16, 4)]
    scene.camera = existing
    return existing


def _data_pass_output(scene: Any, bpy: Any, pass_id: str) -> None:
    tree = bpy.data.node_groups.new("MiniTZRenderPass", "CompositorNodeTree")
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    render_layers = tree.nodes.new(type="CompositorNodeRLayers")
    render_layers.scene = scene
    output = tree.nodes.new(type="NodeGroupOutput")
    tree.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    names = ("Depth", "Z") if pass_id == "z" else ("Normal",)
    source = next((render_layers.outputs.get(name) for name in names if render_layers.outputs.get(name) is not None), None)
    if source is None:
        raise ValueError("requested Blender pass is absent")
    tree.links.new(output.inputs["Image"], source)


def main() -> None:
    import bpy  # type: ignore[import-not-found]

    separator = sys.argv.index("--")
    config = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("render config is malformed")
    width, height = config["dimensions"]
    scene = bpy.context.scene
    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    channels = tuple(config["channels"])
    if channels == ("R", "G", "B", "A"):
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = True
    elif channels == ("R", "G", "B"):
        scene.render.image_settings.color_mode = "RGB"
        scene.render.film_transparent = False
    else:
        raise ValueError("exact PNG channels are unsupported")
    scene.render.engine = "CYCLES"
    quality = config["quality"]
    if config["kind"] == "preview":
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        policy = "preview-samples-1"
    elif config["kind"] == "final":
        requested_samples = int(quality.get("samples", "16"))
        scene.cycles.samples = max(16, requested_samples)
        scene.cycles.use_denoising = True
        policy = f"final-samples-{scene.cycles.samples}"
    else:
        raise ValueError("render kind is unsupported")
    camera = _camera(scene, bpy, config["camera"])
    device = _device(scene, bpy, config["device"])
    pass_id = config["pass_id"]
    view_layer = scene.view_layers[0]
    if pass_id == "z":
        view_layer.use_pass_z = True
        _data_pass_output(scene, bpy, pass_id)
    elif pass_id == "normal":
        view_layer.use_pass_normal = True
        _data_pass_output(scene, bpy, pass_id)
    elif pass_id != "beauty":
        raise ValueError("requested Blender pass is unsupported")
    scene.frame_set(int(config["frame"]))
    scene.render.filepath = str(config["output_path"])
    bpy.ops.render.render(write_still=True)
    device_digest = hashlib.sha256(
        json.dumps(device, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    print("MINITZ_RENDER=" + json.dumps({
        "camera_object": camera.name,
        "device": device,
        "device_digest": device_digest,
        "frame": int(config["frame"]),
        "output_path": config["output_path"],
        "pass_id": pass_id,
        "policy": policy,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
