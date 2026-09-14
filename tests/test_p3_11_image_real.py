"""Focused REAL deterministic image runtime evidence."""
from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from threading import Barrier, Lock
from typing import Any, cast

from PIL import Image, PngImagePlugin
import pytest

from minitz_os.engine.artifact import Artifact, ArtifactRef, ArtifactService
from minitz_os.engine.image_pack import (
    IMAGE_ARTIFACT_ROLES,
    ChannelPacking,
    ImageArtifactContentRef,
    ImageContractError,
    ImageOperation,
    ImageOutputRef,
    ImageSpecification,
    NormalConvention,
    TextureMaterialBinding,
    TextureSpecification,
)
from minitz_os.engine.scheduler import ScheduledDispatch, Scheduler


def _runtime() -> Any:
    return importlib.import_module("minitz.image_tool")


def _support() -> Any:
    path = Path(__file__).with_name("test_p3_05_three_d_real.py")
    spec = importlib.util.spec_from_file_location("p3_11_support", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _environments(tmp_path: Path, count: int = 1) -> tuple[Any, ...]:
    return cast(tuple[Any, ...], _support()._environments(tmp_path, count=count))


def _dispatch(environment: Any) -> ScheduledDispatch:
    allocation = Scheduler(environment.database).get_allocation(
        environment.access, environment.allocation_ref
    )
    return ScheduledDispatch(allocation, environment.attempt)


def _encoded_image(
    mode: str,
    size: tuple[int, int],
    pixels: Sequence[object],
    *,
    format: str = "PNG",
    text: dict[str, str] | None = None,
) -> bytes:
    image = Image.new(mode, size)
    image.putdata(pixels)
    output = BytesIO()
    options: dict[str, object] = {}
    if format == "PNG" and text:
        metadata = PngImagePlugin.PngInfo()
        for key, value in text.items():
            metadata.add_text(key, value)
        options["pnginfo"] = metadata
    image.save(output, format=format, **options)
    return output.getvalue()


def _source(
    environment: Any,
    payload: bytes,
    *,
    media_type: str = "image/png",
    role: str = "image.source",
) -> ImageArtifactContentRef:
    content = environment.objects.put(payload, media_type=media_type)
    artifact = ArtifactService(environment.database).create_artifact(
        environment.access,
        project_ref=environment.access.project_ref,
        role=role,
        content_ref=content,
        source_refs=(),
        source_artifact_refs=(),
        source_content_refs=(),
        derivation_type="image.fixture",
        metadata={"media_type": media_type},
    )
    return ImageArtifactContentRef(
        environment.access.project_ref,
        artifact.artifact_ref.value,
        content.value,
        content.digest,
    )


def _specification(
    environment: Any,
    runtime_ref: str,
    *,
    image_id: str,
    sources: tuple[ImageArtifactContentRef, ...],
    operation: str,
    parameters: dict[str, str],
    size: tuple[int, int],
    format: str,
    channels: tuple[str, ...],
    role: str,
    profile_ref: str = "profile://image/srgb",
    alpha_mode: str = "none",
    metadata_policy: dict[str, str] | None = None,
) -> ImageSpecification:
    recipe_payload = json.dumps(
        {"operation": operation, "parameters": parameters},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    image_operation = ImageOperation(
        operation,
        f"recipe://image/{operation}/v1",
        hashlib.sha256(recipe_payload).hexdigest(),
        parameters,
    )
    return ImageSpecification.create(
        environment.access.project_ref,
        image_id,
        sources,
        (),
        image_operation,
        size[0],
        size[1],
        format,
        channels,
        8,
        profile_ref,
        alpha_mode,
        metadata_policy
        or {"exif": "strip", "icc_profile": "strip", "text": "strip"},
        "model://image/deterministic",
        "1.0.0",
        runtime_ref,
        0,
        {},
        None,
        None,
        None,
        "validator://image/real/v1",
        {"role": role},
    )


def _artifact_ref(value: str, project_ref: object) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    assert len(parts) == 3
    return ArtifactRef(cast(Any, project_ref), parts[1], int(parts[2]))


def _read_output(
    environment: Any, output: ImageOutputRef
) -> tuple[Artifact, Image.Image, bytes]:
    artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(output.output.artifact_ref, environment.access.project_ref),
    )
    assert artifact.content_ref is not None
    payload = environment.objects.read(artifact.content_ref)
    image = Image.open(BytesIO(payload))
    image.load()
    return artifact, image, payload


def test_real_inspection_decodes_pixels_and_rejects_corrupt_bytes(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    runtime = _runtime()
    tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
    )
    source = _source(
        environment,
        _encoded_image(
            "RGBA",
            (3, 2),
            [(10, 20, 30, 255), (40, 50, 60, 128), (70, 80, 90, 0)] * 2,
            text={"asset": "canonical"},
        ),
    )

    inspection = tool.inspect(source, "validator://image/decode/v1")

    assert (inspection.width, inspection.height) == (3, 2)
    assert inspection.format == "PNG"
    assert inspection.channels == ("R", "G", "B", "A")
    assert inspection.bit_depth == 8
    assert inspection.alpha_mode == "straight"
    corrupt = _source(environment, b"not-an-image")
    with pytest.raises(ImageContractError, match="decode|corrupt"):
        tool.inspect(corrupt, "validator://image/decode/v1")


def test_crop_resize_and_jpeg_conversion_publish_immutable_derivations(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    runtime = _runtime()
    dispatch = _dispatch(environment)
    tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=dispatch,
    )
    pixels = [
        (x * 40, y * 50, 10 + x + y, 64 + x * 30)
        for y in range(4)
        for x in range(4)
    ]
    source = _source(
        environment,
        _encoded_image("RGBA", (4, 4), pixels, text={"asset": "keep-me"}),
    )
    crop_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="crop",
        sources=(source,),
        operation="crop",
        parameters={"x": "1", "y": "1", "width": "2", "height": "2"},
        size=(2, 2),
        format="PNG",
        channels=("R", "G", "B", "A"),
        role="image.edited",
        alpha_mode="straight",
        metadata_policy={"exif": "strip", "icc_profile": "strip", "text": "preserve"},
    )

    crop = tool.execute(crop_spec, environment.attempt.attempt_id, environment.attempt.fence)

    crop_artifact, crop_image, _ = _read_output(environment, crop)
    assert crop_image.size == (2, 2)
    assert crop_image.info["asset"] == "keep-me"
    assert list(crop_image.get_flattened_data())[0] == pixels[5]
    derivation = ArtifactService(environment.database).list_derivations(
        environment.access, crop_artifact.artifact_ref
    )[0]
    assert tuple(item.value for item in derivation.source_artifact_refs) == (
        source.artifact_ref,
    )
    assert tuple(item.digest for item in derivation.source_content_refs) == (
        source.content_sha256,
    )
    original = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(source.artifact_ref, environment.access.project_ref),
    )
    assert original.content_ref is not None and original.content_ref.digest == source.content_sha256

    resize_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="resize",
        sources=(crop.output,),
        operation="resize",
        parameters={"interpolation": "nearest"},
        size=(1, 1),
        format="PNG",
        channels=("R", "G", "B", "A"),
        role="image.edited",
        alpha_mode="straight",
    )
    first_resize = tool.execute(
        resize_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    second_resize = tool.execute(
        resize_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    assert first_resize.output.content_sha256 == second_resize.output.content_sha256

    convert_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="jpeg",
        sources=(crop.output,),
        operation="convert",
        parameters={
            "alpha": "flatten",
            "background": "255,255,255",
            "quality": "90",
            "subsampling": "0",
        },
        size=(2, 2),
        format="JPEG",
        channels=("R", "G", "B"),
        role="image.edited",
    )
    converted = tool.execute(
        convert_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    _, jpeg, payload = _read_output(environment, converted)
    assert jpeg.format == "JPEG" and jpeg.mode == "RGB" and jpeg.size == (2, 2)
    assert "asset" not in jpeg.info and "exif" not in jpeg.info and "icc_profile" not in jpeg.info
    assert payload.startswith(b"\xff\xd8")


def test_mask_composite_thumbnail_and_enhance_are_deterministic(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    runtime = _runtime()
    tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=_dispatch(environment),
    )
    base = _source(
        environment,
        _encoded_image("RGBA", (2, 2), [(0, 0, 200, 255)] * 4),
    )
    layer = _source(
        environment,
        _encoded_image(
            "RGBA",
            (2, 2),
            [(200, 0, 0, 0), (200, 0, 0, 255), (200, 0, 0, 255), (200, 0, 0, 0)],
        ),
    )
    mask_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="mask",
        sources=(layer,),
        operation="mask",
        parameters={"source": "alpha", "threshold": "128", "invert": "false"},
        size=(2, 2),
        format="PNG",
        channels=("L",),
        role="image.mask",
    )
    mask = tool.execute(mask_spec, environment.attempt.attempt_id, environment.attempt.fence)
    _, mask_image, _ = _read_output(environment, mask)
    assert list(mask_image.get_flattened_data()) == [0, 255, 255, 0]

    composite_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="composite",
        sources=(base, layer, mask.output),
        operation="compose",
        parameters={"x": "0", "y": "0", "blend": "over"},
        size=(2, 2),
        format="PNG",
        channels=("R", "G", "B", "A"),
        role="image.composite",
        alpha_mode="straight",
    )
    composite = tool.execute(
        composite_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    _, composite_image, _ = _read_output(environment, composite)
    assert list(composite_image.get_flattened_data()) == [
        (0, 0, 200, 255),
        (200, 0, 0, 255),
        (200, 0, 0, 255),
        (0, 0, 200, 255),
    ]

    thumbnail_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="thumbnail",
        sources=(composite.output,),
        operation="thumbnail",
        parameters={"interpolation": "nearest"},
        size=(1, 1),
        format="PNG",
        channels=("R", "G", "B", "A"),
        role="image.preview",
        alpha_mode="straight",
    )
    thumbnail = tool.execute(
        thumbnail_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    assert _read_output(environment, thumbnail)[1].size == (1, 1)

    enhance_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="enhance",
        sources=(base,),
        operation="enhance",
        parameters={"kind": "brightness", "factor": "0.5"},
        size=(2, 2),
        format="PNG",
        channels=("R", "G", "B", "A"),
        role="image.edited",
        alpha_mode="straight",
    )
    enhanced_a = tool.execute(
        enhance_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    enhanced_b = tool.execute(
        enhance_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    assert enhanced_a.output.content_sha256 == enhanced_b.output.content_sha256
    assert _read_output(environment, enhanced_a)[1].getpixel((0, 0)) == (0, 0, 100, 255)


def test_color_conversion_is_explicit_and_data_texture_pixels_are_untouched(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    runtime = _runtime()
    tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=_dispatch(environment),
    )
    color_source = _source(
        environment, _encoded_image("RGB", (1, 1), [(128, 64, 32)])
    )
    incomplete = _specification(
        environment,
        tool.runtime_ref,
        image_id="implicit-color",
        sources=(color_source,),
        operation="color",
        parameters={"source_space": "srgb"},
        size=(1, 1),
        format="PNG",
        channels=("R", "G", "B"),
        role="image.edited",
    )
    with pytest.raises(ImageContractError, match="explicit|target"):
        tool.execute(incomplete, environment.attempt.attempt_id, environment.attempt.fence)

    color_spec = replace(
        incomplete,
        image_id="explicit-color",
        operation=ImageOperation(
            "color",
            "recipe://image/color/v1",
            hashlib.sha256(b"srgb-linear").hexdigest(),
            {"source_space": "srgb", "target_space": "linear-srgb"},
        ),
        canonical_digest=ImageSpecification.create(
            environment.access.project_ref,
            "explicit-color",
            (color_source,),
            (),
            ImageOperation(
                "color",
                "recipe://image/color/v1",
                hashlib.sha256(b"srgb-linear").hexdigest(),
                {"source_space": "srgb", "target_space": "linear-srgb"},
            ),
            1,
            1,
            "PNG",
            ("R", "G", "B"),
            8,
            "profile://image/srgb",
            "none",
            {"exif": "strip", "icc_profile": "strip", "text": "strip"},
            "model://image/deterministic",
            "1.0.0",
            tool.runtime_ref,
            0,
            {},
            None,
            None,
            None,
            "validator://image/real/v1",
            {"role": "image.edited"},
        ).canonical_digest,
    )
    color = tool.execute(color_spec, environment.attempt.attempt_id, environment.attempt.fence)
    assert _read_output(environment, color)[1].getpixel((0, 0)) == (55, 13, 4)

    data_source = _source(
        environment, _encoded_image("L", (2, 1), [1, 254]), role="image.roughness"
    )
    data_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="data-texture",
        sources=(data_source,),
        operation="texture",
        parameters={"semantic": "data"},
        size=(2, 1),
        format="PNG",
        channels=("L",),
        role="image.roughness",
        profile_ref="profile://image/data",
    )
    data_output = tool.execute(
        data_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    assert list(_read_output(environment, data_output)[1].get_flattened_data()) == [1, 254]
    resized_data = _specification(
        environment,
        tool.runtime_ref,
        image_id="bad-data-texture",
        sources=(data_source,),
        operation="texture",
        parameters={"semantic": "data"},
        size=(1, 1),
        format="PNG",
        channels=("L",),
        role="image.roughness",
        profile_ref="profile://image/data",
    )
    with pytest.raises(ImageContractError, match="data texture"):
        tool.execute(
            resized_data, environment.attempt.attempt_id, environment.attempt.fence
        )


def test_channels_texture_validation_and_material_binding_persist_exact_evidence(
    tmp_path: Path,
) -> None:
    environment = _environments(tmp_path)[0]
    runtime = _runtime()
    tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=_dispatch(environment),
    )
    source = _source(
        environment, _encoded_image("RGB", (2, 1), [(10, 20, 30), (40, 50, 60)])
    )
    extract_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="extract-green",
        sources=(source,),
        operation="channel",
        parameters={"action": "extract", "channel": "G"},
        size=(2, 1),
        format="PNG",
        channels=("L",),
        role="image.edited",
    )
    extracted = tool.execute(
        extract_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    assert list(_read_output(environment, extracted)[1].get_flattened_data()) == [20, 50]

    red = _source(environment, _encoded_image("L", (1, 1), [10]))
    green = _source(environment, _encoded_image("L", (1, 1), [20]))
    blue = _source(environment, _encoded_image("L", (1, 1), [30]))
    packing = json.dumps({"R": "0:L", "G": "1:L", "B": "2:L"}, sort_keys=True)
    pack_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="pack-rgb",
        sources=(red, green, blue),
        operation="texture_pack",
        parameters={"packing": packing},
        size=(1, 1),
        format="PNG",
        channels=("R", "G", "B"),
        role="image.packed",
        profile_ref="profile://image/data",
    )
    packed = tool.execute(pack_spec, environment.attempt.attempt_id, environment.attempt.fence)
    assert _read_output(environment, packed)[1].getpixel((0, 0)) == (10, 20, 30)

    normal_source = _source(
        environment,
        _encoded_image("RGB", (2, 1), [(128, 128, 255), (255, 128, 128)]),
        role="image.normal",
    )
    normal_spec = _specification(
        environment,
        tool.runtime_ref,
        image_id="normal",
        sources=(normal_source,),
        operation="texture",
        parameters={"semantic": "data"},
        size=(2, 1),
        format="PNG",
        channels=("R", "G", "B"),
        role="image.normal",
        profile_ref="profile://image/data",
    )
    normal_output = tool.execute(
        normal_spec, environment.attempt.attempt_id, environment.attempt.fence
    )
    texture_spec = TextureSpecification(
        environment.access.project_ref,
        normal_spec,
        ("normal", "data"),
        ChannelPacking("normal-rgb", {"R": "normal.x", "G": "normal.y", "B": "normal.z"}),
        NormalConvention("tangent", "opengl"),
        ("image.normal",),
    )
    validation = tool.validate_texture(
        texture_spec,
        normal_output,
        environment.attempt.attempt_id,
        environment.attempt.fence,
    )
    validation_artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(validation.artifact_ref, environment.access.project_ref),
    )
    assert validation_artifact.role in IMAGE_ARTIFACT_ROLES
    assert validation_artifact.content_ref is not None
    report = json.loads(environment.objects.read(validation_artifact.content_ref))
    assert report["normal_convention"] == {"convention": "opengl", "space": "tangent"}
    assert report["texture_content_sha256"] == normal_output.output.content_sha256

    material = _source(
        environment,
        b'{"material":"hero"}',
        media_type="application/json",
        role="3d.material",
    )
    render_input = _source(
        environment,
        _encoded_image("RGB", (1, 1), [(12, 34, 56)]),
        role="render.frame",
    )
    vfx_input = _source(
        environment,
        _encoded_image("RGB", (1, 1), [(65, 43, 21)]),
        role="vfx.preview",
    )
    binding = TextureMaterialBinding(
        environment.access.project_ref,
        texture_spec,
        material,
        {"image.normal": normal_output.output.artifact_ref},
        {"image.normal": "data"},
    )
    bound = tool.bind_material(
        binding,
        environment.attempt.attempt_id,
        environment.attempt.fence,
        render_input=render_input,
        vfx_input=vfx_input,
    )
    bound_artifact = ArtifactService(environment.database).get_artifact(
        environment.access,
        _artifact_ref(bound.artifact_ref, environment.access.project_ref),
    )
    assert bound_artifact.role in IMAGE_ARTIFACT_ROLES
    assert bound_artifact.content_ref is not None
    bound_report = json.loads(environment.objects.read(bound_artifact.content_ref))
    assert bound_report["material_content_sha256"] == material.content_sha256
    assert bound_report["textures"]["image.normal"]["content_sha256"] == normal_output.output.content_sha256
    assert bound_report["consumer_inputs"] == {
        "3d": {
            "artifact_ref": material.artifact_ref,
            "content_sha256": material.content_sha256,
        },
        "render": {
            "artifact_ref": render_input.artifact_ref,
            "content_sha256": render_input.content_sha256,
        },
        "vfx": {
            "artifact_ref": vfx_input.artifact_ref,
            "content_sha256": vfx_input.content_sha256,
        },
    }
    with pytest.raises(ImageContractError, match="render"):
        tool.bind_material(
            binding,
            environment.attempt.attempt_id,
            environment.attempt.fence,
            render_input=normal_output.output,
            vfx_input=vfx_input,
        )


def test_project_and_stale_node_fences_fail_closed(tmp_path: Path) -> None:
    environment = _environments(tmp_path / "primary")[0]
    runtime = _runtime()
    dispatch = _dispatch(environment)
    source = _source(
        environment, _encoded_image("RGB", (1, 1), [(10, 20, 30)])
    )
    tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=dispatch,
    )
    specification = _specification(
        environment,
        tool.runtime_ref,
        image_id="fenced",
        sources=(source,),
        operation="crop",
        parameters={"x": "0", "y": "0", "width": "1", "height": "1"},
        size=(1, 1),
        format="PNG",
        channels=("R", "G", "B"),
        role="image.edited",
    )
    with pytest.raises(ImageContractError, match="fence|producer"):
        tool.execute(
            specification, environment.attempt.attempt_id, environment.attempt.fence + 1
        )

    forged_attempt = replace(environment.attempt, fence=environment.attempt.fence + 1)
    forged_allocation = replace(
        dispatch.allocation, node_attempt_fence=forged_attempt.fence
    )
    forged_tool = runtime.DeterministicImageTool(
        environment.database,
        environment.objects,
        access=environment.access,
        dispatch=ScheduledDispatch(forged_allocation, forged_attempt),
    )
    with pytest.raises(ImageContractError, match="stale|current"):
        forged_tool.execute(specification, forged_attempt.attempt_id, forged_attempt.fence)

    foreign_root = tmp_path / "foreign"
    foreign_root.mkdir()
    foreign = _environments(foreign_root)[0]
    foreign_source = _source(
        foreign, _encoded_image("RGB", (1, 1), [(1, 2, 3)])
    )
    foreign_spec = _specification(
        foreign,
        tool.runtime_ref,
        image_id="foreign",
        sources=(foreign_source,),
        operation="crop",
        parameters={"x": "0", "y": "0", "width": "1", "height": "1"},
        size=(1, 1),
        format="PNG",
        channels=("R", "G", "B"),
        role="image.edited",
    )
    with pytest.raises(ImageContractError, match="Project"):
        tool.execute(
            foreign_spec, environment.attempt.attempt_id, environment.attempt.fence
        )


def test_independent_maps_use_distinct_existing_dispatches_concurrently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    coordinator, first_child, second_child = _environments(tmp_path, count=3)
    runtime = _runtime()
    tool = runtime.DeterministicImageTool(
        coordinator.database,
        coordinator.objects,
        access=coordinator.access,
    )
    source = _source(
        coordinator,
        _encoded_image("RGB", (4, 4), [(x, y, x + y) for y in range(4) for x in range(4)]),
    )
    specifications = {
        name: _specification(
            coordinator,
            tool.runtime_ref,
            image_id=name,
            sources=(source,),
            operation="resize",
            parameters={"interpolation": "nearest"},
            size=(2, 2),
            format="PNG",
            channels=("R", "G", "B"),
            role="image.texture",
            profile_ref="profile://image/data",
        )
        for name in ("roughness", "metallic")
    }
    dispatches = {
        "roughness": _dispatch(first_child),
        "metallic": _dispatch(second_child),
    }
    real_execute = tool.execute_dispatched
    launch = Barrier(2)
    lock = Lock()
    active = 0
    maximum_active = 0

    def observe(specification: ImageSpecification, dispatch: ScheduledDispatch) -> ImageOutputRef:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            launch.wait(timeout=5.0)
            return cast(ImageOutputRef, real_execute(specification, dispatch))
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(tool, "execute_dispatched", observe)
    outputs = tool.execute_maps(specifications, dispatches)

    assert set(outputs) == {"roughness", "metallic"}
    assert maximum_active == 2
    with pytest.raises(ImageContractError, match="distinct|unique"):
        tool.execute_maps(
            specifications,
            {"roughness": dispatches["roughness"], "metallic": dispatches["roughness"]},
        )
