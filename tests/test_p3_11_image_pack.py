from __future__ import annotations

from dataclasses import replace

import pytest

import minitz_os.engine as minitz_engine
from minitz_os.engine.production_pack import ProductionPackRef
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.image_pack import (
    ChannelPacking,
    ImageArtifactContentRef,
    ImageContractError,
    ImageOperation,
    ImageOutputRef,
    ImageSpecification,
    NormalConvention,
    TextureMaterialBinding,
    TextureSpecification,
    image_production_pack,
)


CAPABILITIES = {
    "inspect", "generate", "edit", "inpaint", "outpaint", "mask", "compose",
    "crop", "resize", "convert", "enhance", "upscale", "color", "channel",
    "texture", "texture_pack", "thumbnail", "validate",
}
ATTEMPT = "natt_" + "a" * 32


def _source(project_ref: ProjectRef, name: str, digest: str) -> ImageArtifactContentRef:
    return ImageArtifactContentRef(project_ref, f"artifact://image/{name}", f"content://image/{name}", digest)


def _specification(project_ref: ProjectRef) -> ImageSpecification:
    source = _source(project_ref, "source", "a" * 64)
    reference = _source(project_ref, "reference", "b" * 64)
    operation = ImageOperation("generate", "recipe://image/generate/v1", "c" * 64, {"steps": "12"})
    return ImageSpecification.create(
        project_ref, "hero", (source,), (reference,), operation,
        1024, 512, "image/png", ("red", "green", "blue", "alpha"), 8,
        "profile://srgb/v1", "straight", {"retain": "copyright"},
        "model://image/generic/v1", "1.0.0", "runtime://image/generic/v1", 7,
        {"guidance": "3.5"}, f"artifact://{project_ref.value}/prompt/1", "content://prompt/hero", "d" * 64,
        "validator://image/generic/v1", {"role": "image.generated"},
    )


def test_image_pack_registers_exact_contract_surface() -> None:
    pack = image_production_pack()
    assert pack.pack_ref == ProductionPackRef("image", "1.0.0")
    assert {item.capability_id for item in pack.capability_definitions} == {f"image.{name}" for name in CAPABILITIES}
    assert {
        "image.source", "image.prompt", "image.generated", "image.edited", "image.mask", "image.layer",
        "image.composite", "image.texture", "image.normal", "image.roughness", "image.metallic",
        "image.ao", "image.displacement", "image.alpha", "image.packed", "image.preview",
        "image.validation-evidence",
    } <= set(pack.artifact_roles)
    assert {
        "IMAGE_ARTIFACT_ROLES", "IMAGE_CAPABILITIES", "ChannelPacking",
        "ImageArtifactContentRef", "ImageContractError", "ImageInspectionRef",
        "ImageModelAdapter", "ImageOperation", "ImageOutputRef", "ImageSpecification",
        "ImageToolAdapter", "NormalConvention", "TextureMaterialBinding",
        "TextureSpecification", "image_production_pack", "DeterministicImageTool",
        "CloudflareHttpResponse", "CloudflareImageModel", "CloudflareImageModelError",
        "CloudflareTransport", "cloudflare_image_model_adapter",
    } <= set(minitz_engine.__all__)


def test_image_specification_and_output_are_exact_and_fail_closed() -> None:
    project_ref = ProjectRef.new()
    specification = _specification(project_ref)
    output = ImageOutputRef.create(project_ref, specification, _source(project_ref, "output", "e" * 64), ATTEMPT, 1, "image.generate")
    assert output.specification_digest == specification.canonical_digest
    with pytest.raises(ImageContractError, match="canonical_digest"):
        replace(specification, width=2048)
    with pytest.raises(ImageContractError, match="project"):
        ImageSpecification.create(ProjectRef.new(), "hero", specification.sources, specification.references, specification.operation, 1024, 512, "image/png", ("red",), 8, "profile://srgb/v1", "straight", {}, "model://image/generic/v1", "1", "runtime://image/generic/v1", 1, {}, specification.prompt_artifact_ref, "content://prompt/hero", "d" * 64, "validator://image/generic/v1", {"role": "image.generated"})
    with pytest.raises(ImageContractError, match="prompt"):
        ImageSpecification.create(project_ref, "hero", specification.sources, (), specification.operation, 1, 1, "image/png", ("red",), 8, "profile://srgb/v1", "none", {}, "model://image/generic/v1", "1", "runtime://image/generic/v1", 1, {}, None, None, None, "validator://image/generic/v1", {})
    with pytest.raises(ImageContractError, match="prompt"):
        ImageSpecification.create(project_ref, "hero", specification.sources, (), specification.operation, 1, 1, "image/png", ("red",), 8, "profile://srgb/v1", "none", {}, "model://image/generic/v1", "1", "runtime://image/generic/v1", 1, {}, f"artifact://{project_ref.value}/prompt/1", None, "d" * 64, "validator://image/generic/v1", {})
    with pytest.raises(ImageContractError, match="Project"):
        ImageSpecification.create(project_ref, "hero", specification.sources, (), specification.operation, 1, 1, "image/png", ("red",), 8, "profile://srgb/v1", "none", {}, "model://image/generic/v1", "1", "runtime://image/generic/v1", 1, {}, f"artifact://{ProjectRef.new().value}/prompt/1", "content://prompt/hero", "d" * 64, "validator://image/generic/v1", {})


def test_texture_binding_has_explicit_color_data_and_packing_conventions() -> None:
    project_ref = ProjectRef.new()
    specification = _specification(project_ref)
    texture = TextureSpecification(project_ref, specification, ("texture.terrain",), ChannelPacking("orm", {"red": "ao", "green": "roughness", "blue": "metallic"}), NormalConvention("tangent", "opengl"), ("image.roughness", "image.metallic", "image.ao"))
    binding = TextureMaterialBinding(project_ref, texture, _source(project_ref, "material", "f" * 64), {"base_color": "image.generated", "normal": "image.normal"}, {"base_color": "color", "normal": "data"})
    assert binding.texture_specification is texture
    with pytest.raises(ImageContractError, match="packing"):
        ChannelPacking("orm", {"red": "ao", "green": "ao"})
    with pytest.raises(ImageContractError, match="project"):
        TextureMaterialBinding(ProjectRef.new(), texture, _source(project_ref, "material", "f" * 64), {"base_color": "image.generated"}, {"base_color": "color"})
