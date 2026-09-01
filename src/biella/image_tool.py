"""REAL deterministic image processing on existing Project and execution authorities."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from PIL import Image, ImageEnhance, ImageOps, PngImagePlugin, UnidentifiedImageError

from .artifact import Artifact, ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .execution import NodeExecutionAttempt, NodeExecutionService
from .image_pack import (
    IMAGE_ARTIFACT_ROLES,
    ImageArtifactContentRef,
    ImageContractError,
    ImageInspectionRef,
    ImageOutputRef,
    ImageSpecification,
    ImageToolAdapter,
    TextureMaterialBinding,
    TextureSpecification,
)
from .object_store import ObjectStorageBackend, ObjectStorageError
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt
from .scheduler import ScheduledDispatch


_FORMAT_ALIASES = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "jpeg": "JPEG",
    "jpg": "JPEG",
    "png": "PNG",
}
_MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}
_MODE_CHANNELS = {
    "1": ("1",),
    "L": ("L",),
    "LA": ("L", "A"),
    "RGB": ("R", "G", "B"),
    "RGBA": ("R", "G", "B", "A"),
}
_CHANNEL_MODES = {channels: mode for mode, channels in _MODE_CHANNELS.items()}
_RESAMPLING = {
    "nearest": Image.Resampling.NEAREST,
    "box": Image.Resampling.BOX,
    "bilinear": Image.Resampling.BILINEAR,
    "hamming": Image.Resampling.HAMMING,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}
_DATA_ROLES = {
    "image.alpha",
    "image.ao",
    "image.displacement",
    "image.metallic",
    "image.normal",
    "image.packed",
    "image.roughness",
}
_ROLE_BY_OPERATION = {
    "channel": "image.edited",
    "color": "image.edited",
    "compose": "image.composite",
    "convert": "image.edited",
    "crop": "image.edited",
    "enhance": "image.edited",
    "mask": "image.mask",
    "resize": "image.edited",
    "texture": "image.texture",
    "texture_pack": "image.packed",
    "thumbnail": "image.preview",
    "upscale": "image.edited",
}


@dataclass(frozen=True)
class _Decoded:
    image: Image.Image
    format: str
    info: Mapping[str, object]


@dataclass(frozen=True)
class _ResolvedArtifact:
    contract: ImageArtifactContentRef
    artifact: Artifact
    content_ref: ContentRef
    payload: bytes


@dataclass(frozen=True)
class _ResolvedSource(_ResolvedArtifact):
    decoded: _Decoded


def _canonical_format(value: str) -> str:
    checked = _FORMAT_ALIASES.get(value.lower(), value.upper())
    if checked not in _MEDIA_TYPES:
        raise ImageContractError("image output format is unsupported")
    return checked


def _integer(
    values: Mapping[str, str],
    name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    default: int | None = None,
) -> int:
    raw = values.get(name)
    if raw is None:
        if default is None:
            raise ImageContractError(f"image parameter {name} is required")
        result = default
    else:
        try:
            result = int(raw)
        except ValueError as exc:
            raise ImageContractError(f"image parameter {name} is invalid") from exc
    if (minimum is not None and result < minimum) or (
        maximum is not None and result > maximum
    ):
        raise ImageContractError(f"image parameter {name} is out of range")
    return result


def _number(
    values: Mapping[str, str],
    name: str,
    *,
    minimum: float | None = None,
) -> float:
    raw = values.get(name)
    if raw is None:
        raise ImageContractError(f"image parameter {name} is required")
    try:
        result = float(raw)
    except ValueError as exc:
        raise ImageContractError(f"image parameter {name} is invalid") from exc
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ImageContractError(f"image parameter {name} is invalid")
    return result


def _boolean(values: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    raise ImageContractError(f"image parameter {name} is invalid")


def _decode(payload: bytes) -> _Decoded:
    if not payload:
        raise ImageContractError("image bytes are empty or corrupt")
    try:
        with Image.open(BytesIO(payload)) as probe:
            detected = probe.format
            probe.verify()
        with Image.open(BytesIO(payload)) as reopened:
            reopened.load()
            if reopened.width < 1 or reopened.height < 1 or reopened.format != detected:
                raise ImageContractError("decoded image identity changed")
            image = reopened.copy()
            typed_info = cast(
                Mapping[str | tuple[int, int], object], reopened.info
            )
            normalized_info: dict[str, object] = {}
            for key, value in typed_info.items():
                if not isinstance(key, str):
                    raise ImageContractError("decoded image metadata key is malformed")
                normalized_info[key] = value
            info = MappingProxyType(normalized_info)
    except ImageContractError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageContractError("image bytes could not be decoded or are corrupt") from exc
    if detected is None:
        raise ImageContractError("decoded image has no format identity")
    return _Decoded(image, _canonical_format(detected), info)


def _bit_depth(image: Image.Image) -> int:
    if image.mode.startswith("I;16"):
        return 16
    if image.mode in {*_MODE_CHANNELS, "P", "I", "F"}:
        return 8 if image.mode not in {"I", "F"} else 32
    raise ImageContractError("decoded image mode is unsupported")


def _profile_ref(info: Mapping[str, object]) -> str:
    profile = info.get("icc_profile")
    if isinstance(profile, bytes) and profile:
        return f"profile://icc/sha256/{hashlib.sha256(profile).hexdigest()}"
    return "profile://image/unspecified"


def _channel_scalar(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ImageContractError("decoded image channel contains a non-integer pixel")
    return value


def _artifact_ref(project_ref: ProjectRef, value: str) -> ArtifactRef:
    parts = value.rsplit("/", 2)
    if len(parts) != 3 or parts[0] != f"artifact://{project_ref.value}":
        raise ImageContractError("image ArtifactRef is invalid or crossed Project scope")
    try:
        return ArtifactRef(project_ref, parts[1], int(parts[2]))
    except (TypeError, ValueError) as exc:
        raise ImageContractError("image ArtifactRef is malformed") from exc


def _resampling(parameters: Mapping[str, str]) -> Image.Resampling:
    interpolation = parameters.get("interpolation")
    if interpolation is None:
        raise ImageContractError("resize interpolation must be explicit")
    try:
        return _RESAMPLING[interpolation.lower()]
    except KeyError as exc:
        raise ImageContractError("resize interpolation is unsupported") from exc


def _background(parameters: Mapping[str, str]) -> tuple[int, int, int]:
    raw = parameters.get("background")
    if raw is None:
        raise ImageContractError("alpha flatten requires an explicit background")
    try:
        values = tuple(int(item.strip()) for item in raw.split(","))
    except ValueError as exc:
        raise ImageContractError("alpha background is invalid") from exc
    if len(values) != 3 or any(item < 0 or item > 255 for item in values):
        raise ImageContractError("alpha background is invalid")
    return values


def _target_mode(specification: ImageSpecification) -> str:
    try:
        mode = _CHANNEL_MODES[tuple(specification.channels)]
    except KeyError as exc:
        raise ImageContractError("image output channels are unsupported") from exc
    if mode == "1":
        raise ImageContractError("one-bit output is unsupported by this runtime")
    return mode


def _explicit_mode_conversion(
    image: Image.Image,
    target_mode: str,
    parameters: Mapping[str, str],
) -> Image.Image:
    if image.mode == target_mode:
        return image.copy()
    if image.mode in {"RGBA", "LA"} and target_mode in {"RGB", "L"}:
        if parameters.get("alpha") != "flatten":
            raise ImageContractError("alpha removal must be explicit")
        background = _background(parameters)
        if image.mode == "LA":
            rgb = image.getchannel("L").convert("RGB")
            alpha = image.getchannel("A")
        else:
            rgb = image.convert("RGB")
            alpha = image.getchannel("A")
        canvas = Image.new("RGB", image.size, background)
        canvas.paste(rgb, (0, 0), alpha)
        return canvas if target_mode == "RGB" else canvas.convert("L")
    if parameters.get("mode") != target_mode:
        raise ImageContractError("pixel mode conversion must be explicit")
    if image.mode not in _MODE_CHANNELS or target_mode not in _MODE_CHANNELS:
        raise ImageContractError("pixel mode conversion is unsupported")
    return image.convert(target_mode)


def _metadata_options(
    info: Mapping[str, object],
    policy: Mapping[str, str],
    format: str,
) -> dict[str, object]:
    allowed = {"exif", "icc_profile", "text"}
    if any(key not in allowed for key in policy):
        raise ImageContractError("metadata policy contains an unsupported field")
    normalized = {key: value.lower() for key, value in policy.items()}
    if any(value not in {"preserve", "strip"} for value in normalized.values()):
        raise ImageContractError("metadata policy must explicitly preserve or strip")
    options: dict[str, object] = {}
    if normalized.get("icc_profile", "strip") == "preserve":
        profile = info.get("icc_profile")
        if isinstance(profile, bytes) and profile:
            options["icc_profile"] = profile
    if normalized.get("exif", "strip") == "preserve":
        exif = info.get("exif")
        if isinstance(exif, bytes) and exif:
            options["exif"] = exif
    if format == "PNG" and normalized.get("text", "strip") == "preserve":
        png_info = PngImagePlugin.PngInfo()
        reserved = {
            "aspect",
            "background",
            "chromaticity",
            "dpi",
            "exif",
            "gamma",
            "icc_profile",
            "interlace",
            "srgb",
            "transparency",
        }
        for key in sorted(info):
            value = info[key]
            if key not in reserved and isinstance(value, str):
                png_info.add_text(key, value)
        options["pnginfo"] = png_info
    return options


def _encode(
    image: Image.Image,
    specification: ImageSpecification,
    source_info: Mapping[str, object],
) -> tuple[bytes, str]:
    format = _canonical_format(specification.format)
    output = BytesIO()
    options = _metadata_options(source_info, specification.metadata_policy, format)
    if format == "PNG":
        options.update({"compress_level": 9, "optimize": False})
    else:
        if image.mode != "RGB":
            raise ImageContractError("JPEG output requires exact RGB channels")
        quality = _integer(
            specification.operation.parameters,
            "quality",
            minimum=1,
            maximum=100,
            default=95,
        )
        subsampling_raw = specification.operation.parameters.get("subsampling", "0")
        subsampling_values = {"0": 0, "1": 1, "2": 2, "4:4:4": 0, "4:2:2": 1, "4:2:0": 2}
        try:
            subsampling = subsampling_values[subsampling_raw]
        except KeyError as exc:
            raise ImageContractError("JPEG subsampling is unsupported") from exc
        options.update(
            {
                "quality": quality,
                "subsampling": subsampling,
                "optimize": False,
                "progressive": False,
            }
        )
    try:
        image.save(output, format=format, **options)
    except (OSError, ValueError) as exc:
        raise ImageContractError("image output encoding failed") from exc
    return output.getvalue(), _MEDIA_TYPES[format]


def _linear_table(*, inverse: bool) -> list[int]:
    table: list[int] = []
    for integer in range(256):
        value = integer / 255.0
        if inverse:
            converted = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1.0 / 2.4) - 0.055
        else:
            converted = value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        table.append(max(0, min(255, round(converted * 255.0))))
    return table


def _color_conversion(image: Image.Image, parameters: Mapping[str, str]) -> Image.Image:
    source = parameters.get("source_space")
    target = parameters.get("target_space")
    if source is None or target is None:
        raise ImageContractError("color conversion requires explicit source and target spaces")
    source, target = source.lower(), target.lower()
    if image.mode not in {"RGB", "RGBA"}:
        raise ImageContractError("explicit color conversion requires RGB channels")
    if source == target:
        return image.copy()
    if (source, target) not in {
        ("srgb", "linear-srgb"),
        ("linear-srgb", "srgb"),
    }:
        raise ImageContractError("explicit color conversion is unsupported")
    channels = list(image.split())
    alpha = channels.pop() if image.mode == "RGBA" else None
    table = _linear_table(inverse=source == "linear-srgb")
    converted = [channel.point(table) for channel in channels]
    if alpha is not None:
        converted.append(alpha)
    return Image.merge(image.mode, converted)


class DeterministicImageTool(ImageToolAdapter):
    """Bound CPU image node; dispatch and allocation authority are supplied upstream."""

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        dispatch: ScheduledDispatch | None = None,
        tool_ref: str = "tool://pillow/12.1.1",
        runtime_ref: str = "runtime://image/pillow-12.1.1-cpu",
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise ImageContractError("exact ProjectAccess is required")
        if dispatch is not None and not isinstance(dispatch, ScheduledDispatch):
            raise ImageContractError("image dispatch authority is malformed")
        self.database = Path(database_path)
        self.objects = object_store
        self.access = access
        self.project_ref = access.project_ref
        self.dispatch = dispatch
        self.tool_ref = tool_ref
        self.runtime_ref = runtime_ref
        self.determinism = "deterministic-cpu"
        self.artifacts = ArtifactService(self.database)
        self.executions = NodeExecutionService(self.database)

    def _resolve_artifact(self, source: ImageArtifactContentRef) -> _ResolvedArtifact:
        if not isinstance(source, ImageArtifactContentRef) or source.project_ref != self.project_ref:
            raise ImageContractError("image source crossed Project scope")
        reference = _artifact_ref(self.project_ref, source.artifact_ref)
        try:
            artifact = self.artifacts.get_artifact(self.access, reference)
        except ArtifactError as exc:
            raise ImageContractError("image source Artifact is missing or stale") from exc
        content = artifact.content_ref
        if (
            content is None
            or content.value != source.content_ref
            or content.digest != source.content_sha256
        ):
            raise ImageContractError("image source Artifact/Content identity is stale or forged")
        try:
            if not self.objects.verify(content):
                raise ImageContractError("image source Content is unavailable or corrupt")
            payload = self.objects.read(content)
        except ObjectStorageError as exc:
            raise ImageContractError("image source Content is unavailable or corrupt") from exc
        try:
            content.verify(payload)
        except ArtifactError as exc:
            raise ImageContractError("image source Content identity changed") from exc
        return _ResolvedArtifact(source, artifact, content, payload)

    def _resolve_contract(self, source: ImageArtifactContentRef) -> _ResolvedSource:
        resolved = self._resolve_artifact(source)
        return _ResolvedSource(
            resolved.contract,
            resolved.artifact,
            resolved.content_ref,
            resolved.payload,
            _decode(resolved.payload),
        )

    def inspect(
        self, source: ImageArtifactContentRef, validator_ref: str
    ) -> ImageInspectionRef:
        resolved = self._resolve_contract(source)
        channels = tuple(resolved.decoded.image.getbands())
        return ImageInspectionRef.create(
            self.project_ref,
            source,
            resolved.decoded.image.width,
            resolved.decoded.image.height,
            resolved.decoded.format,
            channels,
            _bit_depth(resolved.decoded.image),
            _profile_ref(resolved.decoded.info),
            "straight" if "A" in channels else "none",
            validator_ref,
        )

    def _require_dispatch(
        self,
        dispatch: ScheduledDispatch,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> NodeExecutionAttempt:
        if not isinstance(dispatch, ScheduledDispatch):
            raise ImageContractError("exact ScheduledDispatch is required")
        allocation, attempt = dispatch.allocation, dispatch.node_attempt
        if (
            allocation.project_ref != self.project_ref
            or attempt.node_ref.project_ref != self.project_ref
            or producer_attempt_id != attempt.attempt_id
            or producer_fence != attempt.fence
        ):
            raise ImageContractError("image producer attempt/fence crossed Project or authority")
        if (
            allocation.status != "DISPATCHED"
            or allocation.node_ref != attempt.node_ref
            or allocation.run_ref != attempt.run_ref
            or allocation.run_attempt_id != attempt.run_attempt_id
            or allocation.run_attempt_fence != attempt.run_fence
            or allocation.node_attempt_id != attempt.attempt_id
            or allocation.node_attempt_fence != attempt.fence
            or allocation.owner_ref != attempt.owner_ref
            or allocation.lease_expires_at is None
        ):
            raise ImageContractError("image dispatch allocation/attempt evidence is stale or forged")
        current = self.executions.get_node_execution(self.access, attempt.node_ref)
        if (
            current.status in {"CANCELLED", "FAILED", "SUCCEEDED"}
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or current.current_owner_ref != attempt.owner_ref
            or current.current_run_attempt_id != attempt.run_attempt_id
            or current.current_run_fence != attempt.run_fence
            or current.run_ref != attempt.run_ref
            or current.task_ref != attempt.task_ref
            or current.task_digest != attempt.task_digest
        ):
            raise ImageContractError("image Node attempt is not current")
        try:
            node_expiry = datetime.fromisoformat(attempt.lease_expires_at)
            allocation_expiry = datetime.fromisoformat(allocation.lease_expires_at)
            now = datetime.now(node_expiry.tzinfo)
        except (TypeError, ValueError) as exc:
            raise ImageContractError("image dispatch lease is malformed") from exc
        if node_expiry <= now or allocation_expiry <= now:
            raise ImageContractError("image dispatch lease is stale")
        return attempt

    def _producer(self, attempt: NodeExecutionAttempt) -> ExecutionAttempt:
        run = self.artifacts.runs.get_run(self.access, attempt.run_ref)
        if (
            run.status != "RUNNING"
            or run.current_attempt_id != attempt.run_attempt_id
            or run.current_fence != attempt.run_fence
            or run.task_ref != attempt.task_ref
            or run.task_digest != attempt.task_digest
        ):
            raise ImageContractError("image producer Run authority is stale")
        matches = tuple(
            candidate
            for candidate in self.artifacts.runs.list_attempts(self.access, attempt.run_ref)
            if candidate.attempt_id == attempt.run_attempt_id
            and candidate.fence == attempt.run_fence
            and candidate.completed_at is None
        )
        if len(matches) != 1:
            raise ImageContractError("image producer Run attempt/fence is stale")
        return matches[0]

    def _publish(
        self,
        dispatch: ScheduledDispatch,
        *,
        role: str,
        payload: bytes,
        media_type: str,
        sources: Sequence[_ResolvedArtifact],
        derivation: str,
    ) -> ImageArtifactContentRef:
        attempt = dispatch.node_attempt
        producer = self._producer(attempt)
        content = self.objects.put(payload, media_type=media_type)
        if (
            not self.objects.verify(content)
            or self.objects.read(content) != payload
            or content.digest != hashlib.sha256(payload).hexdigest()
        ):
            raise ImageContractError("fresh image output Content verification failed")
        artifact = self.artifacts.publish_from_run(
            self.access,
            producer_attempt=producer,
            expected_task_ref=attempt.task_ref,
            expected_task_digest=attempt.task_digest,
            role=role,
            content_ref=content,
            source_refs=(),
            source_artifact_refs=tuple(item.artifact.artifact_ref for item in sources),
            source_content_refs=tuple(item.content_ref for item in sources),
            derivation_type=derivation,
            metadata={"media_type": media_type},
        )
        reopened = self.artifacts.get_artifact(self.access, artifact.artifact_ref)
        if reopened.content_ref != content or self.objects.read(content) != payload:
            raise ImageContractError("fresh image output Artifact verification failed")
        return ImageArtifactContentRef(
            self.project_ref, artifact.artifact_ref.value, content.value, content.digest
        )

    def _transform_crop(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1:
            raise ImageContractError("crop requires one exact source")
        parameters = specification.operation.parameters
        x = _integer(parameters, "x", minimum=0)
        y = _integer(parameters, "y", minimum=0)
        width = _integer(parameters, "width", minimum=1)
        height = _integer(parameters, "height", minimum=1)
        source = sources[0].decoded.image
        if x + width > source.width or y + height > source.height:
            raise ImageContractError("crop rectangle exceeds immutable source bounds")
        return source.crop((x, y, x + width, y + height))

    def _transform_resize(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1:
            raise ImageContractError("resize requires one exact source")
        if specification.operation.operation == "upscale" and (
            specification.width < sources[0].decoded.image.width
            or specification.height < sources[0].decoded.image.height
        ):
            raise ImageContractError("upscale cannot reduce source dimensions")
        return sources[0].decoded.image.resize(
            (specification.width, specification.height),
            resample=_resampling(specification.operation.parameters),
        )

    def _transform_convert(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1:
            raise ImageContractError("convert requires one exact source")
        return _explicit_mode_conversion(
            sources[0].decoded.image,
            _target_mode(specification),
            specification.operation.parameters,
        )

    def _transform_mask(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1 or _target_mode(specification) != "L":
            raise ImageContractError("mask requires one source and one L output channel")
        parameters = specification.operation.parameters
        selector = parameters.get("source")
        image = sources[0].decoded.image
        if selector == "alpha":
            if "A" not in image.getbands():
                raise ImageContractError("alpha mask source has no alpha channel")
            channel = image.getchannel("A")
        elif selector == "luminance":
            if image.mode != "L":
                raise ImageContractError("luminance mask requires an exact L source")
            channel = image.copy()
        else:
            raise ImageContractError("mask source channel must be explicit")
        threshold = _integer(parameters, "threshold", minimum=0, maximum=255)
        invert = _boolean(parameters, "invert")
        scalar_pixels = tuple(
            _channel_scalar(value) for value in channel.get_flattened_data()
        )
        values = bytes(
            255 - (255 if value >= threshold else 0)
            if invert
            else (255 if value >= threshold else 0)
            for value in scalar_pixels
        )
        return Image.frombytes("L", channel.size, values)

    def _transform_compose(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) not in {2, 3}:
            raise ImageContractError("compose requires base, layer, and optional exact mask")
        parameters = specification.operation.parameters
        if parameters.get("blend") != "over":
            raise ImageContractError("compose blend mode must be explicit and supported")
        base_source, layer_source = sources[0].decoded.image, sources[1].decoded.image
        if base_source.mode not in {"RGB", "RGBA"} or layer_source.mode not in {"RGB", "RGBA"}:
            raise ImageContractError("compose requires exact RGB or RGBA sources")
        base = base_source.convert("RGBA")
        layer = layer_source.convert("RGBA")
        if len(sources) == 3:
            mask = sources[2].decoded.image
            if mask.mode != "L" or mask.size != layer.size:
                raise ImageContractError("compose mask dimensions/channels are incompatible")
            layer.putalpha(mask)
        x = _integer(parameters, "x", minimum=0, default=0)
        y = _integer(parameters, "y", minimum=0, default=0)
        if x + layer.width > base.width or y + layer.height > base.height:
            raise ImageContractError("compose layer exceeds base bounds")
        base.alpha_composite(layer, (x, y))
        return base

    def _transform_thumbnail(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1:
            raise ImageContractError("thumbnail requires one exact source")
        return ImageOps.fit(
            sources[0].decoded.image,
            (specification.width, specification.height),
            method=_resampling(specification.operation.parameters),
            centering=(0.5, 0.5),
        )

    def _transform_enhance(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1:
            raise ImageContractError("enhance requires one exact source")
        parameters = specification.operation.parameters
        factor = _number(parameters, "factor", minimum=0.0)
        enhancers = {
            "brightness": ImageEnhance.Brightness,
            "color": ImageEnhance.Color,
            "contrast": ImageEnhance.Contrast,
            "sharpness": ImageEnhance.Sharpness,
        }
        try:
            enhancer = enhancers[cast(str, parameters.get("kind"))]
        except KeyError as exc:
            raise ImageContractError("enhancement kind is unsupported") from exc
        return enhancer(sources[0].decoded.image).enhance(factor)

    def _transform_channel(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        parameters = specification.operation.parameters
        if len(sources) != 1 or parameters.get("action") != "extract":
            raise ImageContractError("channel extraction requires one exact source")
        channel = parameters.get("channel")
        if channel is None or channel not in sources[0].decoded.image.getbands():
            raise ImageContractError("requested source channel is unavailable")
        if _target_mode(specification) != "L":
            raise ImageContractError("channel extraction output must be L")
        return sources[0].decoded.image.getchannel(channel)

    def _transform_texture(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        if len(sources) != 1:
            raise ImageContractError("texture requires one exact source")
        semantic = specification.operation.parameters.get("semantic")
        if semantic not in {"color", "data"}:
            raise ImageContractError("texture color/data semantic must be explicit")
        source = sources[0].decoded.image
        if source.size != (specification.width, specification.height) or tuple(
            source.getbands()
        ) != tuple(specification.channels):
            suffix = "data texture" if semantic == "data" else "color texture"
            raise ImageContractError(f"{suffix} cannot silently resize or change channels")
        if semantic == "data" and "icc_profile" in sources[0].decoded.info:
            raise ImageContractError("data texture cannot silently apply an ICC transform")
        return source.copy()

    def _transform_texture_pack(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        raw = specification.operation.parameters.get("packing")
        if raw is None:
            raise ImageContractError("texture channel packing must be explicit")
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ImageContractError("texture channel packing is malformed") from exc
        if not isinstance(loaded, dict) or set(loaded) != set(specification.channels):
            raise ImageContractError("texture channel packing does not match output channels")
        if not sources:
            raise ImageContractError("texture channel packing requires sources")
        output_bands: list[Image.Image] = []
        for output_channel in specification.channels:
            binding = loaded.get(output_channel)
            if not isinstance(binding, str):
                raise ImageContractError("texture channel binding is malformed")
            parts = binding.split(":", 1)
            try:
                source_index = int(parts[0])
            except (ValueError, IndexError) as exc:
                raise ImageContractError("texture channel source index is malformed") from exc
            if source_index < 0 or source_index >= len(sources) or len(parts) != 2:
                raise ImageContractError("texture channel source index is unavailable")
            source = sources[source_index].decoded.image
            source_channel = parts[1]
            if (
                source.size != (specification.width, specification.height)
                or source_channel not in source.getbands()
            ):
                raise ImageContractError("texture packing cannot silently resample source channels")
            output_bands.append(source.getchannel(source_channel))
        return Image.merge(_target_mode(specification), output_bands)

    def _transform(
        self, specification: ImageSpecification, sources: Sequence[_ResolvedSource]
    ) -> Image.Image:
        operation = specification.operation.operation
        if operation == "crop":
            output = self._transform_crop(specification, sources)
        elif operation in {"resize", "upscale"}:
            output = self._transform_resize(specification, sources)
        elif operation == "convert":
            output = self._transform_convert(specification, sources)
        elif operation == "mask":
            output = self._transform_mask(specification, sources)
        elif operation == "compose":
            output = self._transform_compose(specification, sources)
        elif operation == "thumbnail":
            output = self._transform_thumbnail(specification, sources)
        elif operation == "enhance":
            output = self._transform_enhance(specification, sources)
        elif operation == "color":
            if len(sources) != 1:
                raise ImageContractError("color conversion requires one exact source")
            output = _color_conversion(
                sources[0].decoded.image, specification.operation.parameters
            )
        elif operation == "channel":
            output = self._transform_channel(specification, sources)
        elif operation == "texture":
            output = self._transform_texture(specification, sources)
        elif operation == "texture_pack":
            output = self._transform_texture_pack(specification, sources)
        else:
            raise ImageContractError(
                "deterministic image runtime cannot claim this operation"
            )
        if specification.bit_depth != 8:
            raise ImageContractError("deterministic image transforms require 8-bit output")
        if output.size != (specification.width, specification.height):
            raise ImageContractError("transformed image dimensions differ from specification")
        if tuple(output.getbands()) != tuple(specification.channels):
            raise ImageContractError("transformed image channels differ from specification")
        return output

    def _validate_specification(self, specification: ImageSpecification) -> None:
        if not isinstance(specification, ImageSpecification):
            raise ImageContractError("exact ImageSpecification is required")
        if specification.project_ref != self.project_ref:
            raise ImageContractError("image specification crossed Project scope")
        if specification.runtime_ref != self.runtime_ref:
            raise ImageContractError("image specification runtime identity changed")
        if specification.operation.generative:
            raise ImageContractError(
                "deterministic image tool cannot claim a generative model operation"
            )
        if specification.operation.operation not in _ROLE_BY_OPERATION:
            raise ImageContractError("image operation is not implemented by this runtime")

    def execute(
        self,
        specification: ImageSpecification,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> ImageOutputRef:
        if self.dispatch is None:
            raise ImageContractError("execute requires one bound existing dispatch")
        attempt = self._require_dispatch(
            self.dispatch, producer_attempt_id, producer_fence
        )
        return self._execute_authorized(specification, self.dispatch, attempt)

    def execute_dispatched(
        self, specification: ImageSpecification, dispatch: ScheduledDispatch
    ) -> ImageOutputRef:
        attempt = self._require_dispatch(
            dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
        )
        return self._execute_authorized(specification, dispatch, attempt)

    def _execute_authorized(
        self,
        specification: ImageSpecification,
        dispatch: ScheduledDispatch,
        attempt: NodeExecutionAttempt,
    ) -> ImageOutputRef:
        self._validate_specification(specification)
        sources = tuple(self._resolve_contract(source) for source in specification.sources)
        output_image = self._transform(specification, sources)
        source_info: Mapping[str, object] = sources[0].decoded.info
        encoded, media_type = _encode(output_image, specification, source_info)
        verified = _decode(encoded)
        if (
            verified.image.size != (specification.width, specification.height)
            or tuple(verified.image.getbands()) != tuple(specification.channels)
            or verified.format != _canonical_format(specification.format)
        ):
            raise ImageContractError("freshly encoded image failed exact output verification")
        requested_role = specification.output_contract.get("role")
        role = requested_role or _ROLE_BY_OPERATION[specification.operation.operation]
        if role not in IMAGE_ARTIFACT_ROLES:
            raise ImageContractError("image output role is outside the production pack")
        output = self._publish(
            dispatch,
            role=role,
            payload=encoded,
            media_type=media_type,
            sources=sources,
            derivation=f"image.{specification.operation.operation.replace('_', '-')}",
        )
        return ImageOutputRef.create(
            self.project_ref,
            specification,
            output,
            attempt.attempt_id,
            attempt.fence,
            f"image.{specification.operation.operation}:{specification.operation.recipe_sha256}",
        )

    def execute_maps(
        self,
        specifications: Mapping[str, ImageSpecification],
        dispatches: Mapping[str, ScheduledDispatch],
    ) -> Mapping[str, ImageOutputRef]:
        if not isinstance(specifications, Mapping) or not isinstance(dispatches, Mapping):
            raise ImageContractError("independent image maps require exact mappings")
        specification_map, dispatch_map = dict(specifications), dict(dispatches)
        if not specification_map or set(specification_map) != set(dispatch_map):
            raise ImageContractError("independent image maps and dispatch keys must match")
        if len(specification_map) > 32:
            raise ImageContractError("independent image map fanout is unbounded")
        values = tuple(dispatch_map.values())
        if any(not isinstance(item, ScheduledDispatch) for item in values):
            raise ImageContractError("independent image map dispatch is malformed")
        if (
            len({item.allocation.allocation_ref for item in values}) != len(values)
            or len({item.node_attempt.attempt_id for item in values}) != len(values)
            or len({item.node_attempt.node_ref for item in values}) != len(values)
        ):
            raise ImageContractError(
                "independent image maps require distinct allocation, attempt, and node identities"
            )
        for key in sorted(specification_map):
            self._validate_specification(specification_map[key])
            dispatch = dispatch_map[key]
            self._require_dispatch(
                dispatch, dispatch.node_attempt.attempt_id, dispatch.node_attempt.fence
            )
        results: dict[str, ImageOutputRef] = {}
        with ThreadPoolExecutor(
            max_workers=len(specification_map), thread_name_prefix="biella-image"
        ) as executor:
            futures = {
                key: executor.submit(
                    self.execute_dispatched, specification_map[key], dispatch_map[key]
                )
                for key in sorted(specification_map)
            }
            for key in sorted(futures):
                results[key] = futures[key].result()
        return MappingProxyType(results)

    def _resolve_output(
        self, output: ImageOutputRef
    ) -> tuple[_ResolvedSource, ArtifactRef]:
        if not isinstance(output, ImageOutputRef) or output.project_ref != self.project_ref:
            raise ImageContractError("image output crossed Project scope")
        resolved = self._resolve_contract(output.output)
        return resolved, resolved.artifact.artifact_ref

    def validate_texture(
        self,
        specification: TextureSpecification,
        output: ImageOutputRef,
        producer_attempt_id: str,
        producer_fence: int,
    ) -> ImageArtifactContentRef:
        if self.dispatch is None:
            raise ImageContractError("texture validation requires a bound existing dispatch")
        self._require_dispatch(self.dispatch, producer_attempt_id, producer_fence)
        if (
            not isinstance(specification, TextureSpecification)
            or specification.project_ref != self.project_ref
            or output.specification_digest
            != specification.image_specification.canonical_digest
            or output.producer_attempt_id != producer_attempt_id
            or output.producer_fence != producer_fence
        ):
            raise ImageContractError("texture validation identity is stale or incompatible")
        resolved, _ = self._resolve_output(output)
        if resolved.artifact.role not in specification.output_roles:
            raise ImageContractError("texture Artifact role is outside exact texture specification")
        channels = tuple(resolved.decoded.image.getbands())
        packing_channels = tuple(specification.packing.channels)
        if any(channel not in channels for channel in packing_channels):
            raise ImageContractError("texture packing references unavailable channels")
        convention = specification.normal_convention
        if convention.space not in {"object", "tangent", "world"} or convention.convention not in {
            "directx",
            "opengl",
        }:
            raise ImageContractError("normal texture convention is unsupported")
        normal_stats: dict[str, object] | None = None
        if "normal" in specification.representation_tags or "image.normal" in specification.output_roles:
            if not {"R", "G", "B"}.issubset(channels):
                raise ImageContractError("normal texture requires exact RGB vectors")
            rgb = resolved.decoded.image.convert("RGB")
            minimum_length = math.inf
            maximum_length = 0.0
            for red, green, blue in cast(
                Sequence[tuple[int, int, int]], list(rgb.get_flattened_data())
            ):
                x = red / 127.5 - 1.0
                y = green / 127.5 - 1.0
                if convention.convention == "directx":
                    y = -y
                z = blue / 127.5 - 1.0
                length = math.sqrt(x * x + y * y + z * z)
                minimum_length = min(minimum_length, length)
                maximum_length = max(maximum_length, length)
                if not 0.5 <= length <= 1.5 or z < -0.05:
                    raise ImageContractError("normal texture contains invalid semantic vectors")
            normal_stats = {
                "maximum_length": format(maximum_length, ".12g"),
                "minimum_length": format(minimum_length, ".12g"),
            }
        report = {
            "normal_convention": {
                "convention": convention.convention,
                "space": convention.space,
            },
            "normal_stats": normal_stats,
            "packing": dict(specification.packing.channels),
            "representation_tags": list(specification.representation_tags),
            "texture_artifact_ref": resolved.artifact.artifact_ref.value,
            "texture_content_sha256": resolved.content_ref.digest,
            "texture_specification_digest": specification.image_specification.canonical_digest,
        }
        payload = json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        evidence = self._publish(
            self.dispatch,
            role="image.validation-evidence",
            payload=payload,
            media_type="application/json",
            sources=(resolved,),
            derivation="image.texture.validate",
        )
        evidence_artifact = self.artifacts.get_artifact(
            self.access, _artifact_ref(self.project_ref, evidence.artifact_ref)
        )
        if evidence_artifact.content_ref is None or json.loads(
            self.objects.read(evidence_artifact.content_ref)
        ) != report:
            raise ImageContractError("fresh texture validation evidence is corrupt")
        return evidence

    def bind_material(
        self,
        binding: TextureMaterialBinding,
        producer_attempt_id: str,
        producer_fence: int,
        *,
        render_input: ImageArtifactContentRef,
        vfx_input: ImageArtifactContentRef,
    ) -> ImageArtifactContentRef:
        if self.dispatch is None:
            raise ImageContractError("material binding requires a bound existing dispatch")
        self._require_dispatch(self.dispatch, producer_attempt_id, producer_fence)
        if not isinstance(binding, TextureMaterialBinding) or binding.project_ref != self.project_ref:
            raise ImageContractError("material binding crossed Project scope")
        if set(binding.texture_roles) != set(binding.texture_specification.output_roles):
            raise ImageContractError("material binding does not cover exact texture output roles")
        material = self._resolve_artifact(binding.material)
        if not material.artifact.role.startswith("3d."):
            raise ImageContractError("material binding requires an exact 3D Artifact")
        render_source = self._resolve_artifact(render_input)
        if not render_source.artifact.role.startswith("render."):
            raise ImageContractError("material binding requires an exact render Artifact")
        vfx_source = self._resolve_artifact(vfx_input)
        if not vfx_source.artifact.role.startswith("vfx."):
            raise ImageContractError("material binding requires an exact VFX Artifact")
        texture_sources: list[_ResolvedSource] = []
        texture_report: dict[str, dict[str, str]] = {}
        for role in sorted(binding.texture_roles):
            semantic = binding.semantics[role]
            if role in _DATA_ROLES and semantic != "data":
                raise ImageContractError("data texture role cannot claim color semantics")
            reference = _artifact_ref(self.project_ref, binding.texture_roles[role])
            artifact = self.artifacts.get_artifact(self.access, reference)
            if artifact.role != role or artifact.content_ref is None:
                raise ImageContractError("material texture role or Content identity is stale")
            content = artifact.content_ref
            payload = self.objects.read(content)
            content.verify(payload)
            decoded = _decode(payload)
            contract = ImageArtifactContentRef(
                self.project_ref, reference.value, content.value, content.digest
            )
            texture_sources.append(
                _ResolvedSource(contract, artifact, content, payload, decoded)
            )
            texture_report[role] = {
                "artifact_ref": reference.value,
                "content_sha256": content.digest,
                "semantic": semantic,
            }
        report = {
            "consumer_inputs": {
                "3d": {
                    "artifact_ref": material.artifact.artifact_ref.value,
                    "content_sha256": material.content_ref.digest,
                },
                "render": {
                    "artifact_ref": render_source.artifact.artifact_ref.value,
                    "content_sha256": render_source.content_ref.digest,
                },
                "vfx": {
                    "artifact_ref": vfx_source.artifact.artifact_ref.value,
                    "content_sha256": vfx_source.content_ref.digest,
                },
            },
            "material_artifact_ref": material.artifact.artifact_ref.value,
            "material_content_sha256": material.content_ref.digest,
            "texture_specification_digest": binding.texture_specification.image_specification.canonical_digest,
            "textures": texture_report,
        }
        payload = json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        evidence = self._publish(
            self.dispatch,
            role="image.validation-evidence",
            payload=payload,
            media_type="application/json",
            sources=(material, render_source, vfx_source, *texture_sources),
            derivation="image.texture.material-binding",
        )
        evidence_artifact = self.artifacts.get_artifact(
            self.access, _artifact_ref(self.project_ref, evidence.artifact_ref)
        )
        if evidence_artifact.content_ref is None or json.loads(
            self.objects.read(evidence_artifact.content_ref)
        ) != report:
            raise ImageContractError("fresh material binding evidence is corrupt")
        return evidence


__all__ = ["DeterministicImageTool"]
