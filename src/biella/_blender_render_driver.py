"""Adapter-local Blender render worker; no public contract types live here."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


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
    scene.render.film_transparent = False
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
    camera = scene.camera
    if camera is None:
        bpy.ops.object.camera_add(location=(7.0, -7.0, 5.0))
        camera = bpy.context.object
        scene.camera = camera
    matrix = config["camera_transform"]
    camera.matrix_world = [matrix[index:index + 4] for index in range(0, 16, 4)]
    pass_id = config["pass_id"]
    view_layer = scene.view_layers[0]
    if pass_id == "z":
        view_layer.use_pass_z = True
    elif pass_id == "normal":
        view_layer.use_pass_normal = True
    elif pass_id != "beauty":
        raise ValueError("requested Blender pass is unsupported")
    scene.frame_set(int(config["frame"]))
    scene.render.filepath = str(config["output_path"])
    bpy.ops.render.render(write_still=True)
    if pass_id != "beauty":
        render_result = bpy.data.images.get("Render Result")
        pass_name = {"z": "Z", "normal": "Normal"}[pass_id]
        render_pass = next((item for item in render_result.layers[0].passes if item.name == pass_name), None)
        if render_pass is None:
            raise ValueError("requested Blender pass is absent")
        image = bpy.data.images.new("BiellaRenderPass", width=render_result.size[0], height=render_result.size[1], alpha=True)
        image.pixels.foreach_set(render_pass.rect)
        image.filepath_raw = str(config["output_path"])
        image.file_format = "PNG"
        image.save()
    print("BIELLA_RENDER=" + json.dumps({"frame": int(config["frame"]), "output_path": config["output_path"], "policy": policy}, sort_keys=True))


if __name__ == "__main__":
    main()
