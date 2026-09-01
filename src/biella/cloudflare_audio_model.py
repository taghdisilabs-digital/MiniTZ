"""Cloudflare Workers AI audio adapters with fenced audio publication."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Protocol
import urllib.error
import urllib.request

from .artifact import ArtifactError, ArtifactRef, ArtifactService, ContentRef
from .audio_pack import (
    AUDIO_ARTIFACT_ROLES,
    AudioArtifactContentRef,
    AudioContractError,
    AudioModelAdapter,
    AudioOutputRef,
    AudioSpecification,
)
from .call_ledger import CallAuthorityError, CallError, CallLedgerService, ModelCall
from .capability import CapabilityRef
from .execution import NodeExecutionAttempt, NodeExecutionError, NodeExecutionService
from .object_store import ObjectStorageBackend
from .project import ProjectAccess, ProjectRef
from .run import ExecutionAttempt, RunError, RunService


_MODEL = "model://cloudflare/melotts"
_AURA_MODEL = "model://cloudflare/deepgram-aura-1"
_MODEL_VERSION = "1"
_MODEL_API_ID = "@cf/myshell-ai/melotts"
_AURA_MODEL_API_ID = "@cf/deepgram/aura-1"
_PROVIDER = "provider://cloudflare/workers-ai"
_RUNTIME = "runtime://cloudflare/workers-ai/v1"
_VOICE = "voice://cloudflare/melotts/default"
_AURA_VOICE = "voice://cloudflare/deepgram-aura-1/asteria"
_DERIVATION = "audio.cloudflare.melotts"
_AURA_DERIVATION = "audio.cloudflare.deepgram-aura-1"
_VALIDATION_DERIVATION = "audio.cloudflare.melotts.validation"
_AURA_VALIDATION_DERIVATION = "audio.cloudflare.deepgram-aura-1.validation"
_VALIDATION_MEDIA_TYPE = "application/vnd.biella.audio-validation+json"
_MEASUREMENT_ALGORITHM = "algorithm://audio/ffmpeg-full-decode/v1"
_NATIVE_CHAIN = "chain://audio/provider-native/v1"
_NATIVE_EFFECT = "effect://audio/provider-native/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ABSOLUTE_REF = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")
_SOURCE_ROLES = frozenset(AUDIO_ARTIFACT_ROLES) - {
    "audio.prompt",
    "audio.transcript",
    "audio.validation-evidence",
}


@dataclass(frozen=True)
class _CloudflareAudioBinding:
    api_id: str
    voice_ref: str
    label: str
    derivation: str
    validation_derivation: str
    speaker: str | None


_MODEL_BINDINGS: Mapping[str, _CloudflareAudioBinding] = {
    _MODEL: _CloudflareAudioBinding(
        _MODEL_API_ID,
        _VOICE,
        "MeloTTS",
        _DERIVATION,
        _VALIDATION_DERIVATION,
        None,
    ),
    _AURA_MODEL: _CloudflareAudioBinding(
        _AURA_MODEL_API_ID,
        _AURA_VOICE,
        "Deepgram Aura-1",
        _AURA_DERIVATION,
        _AURA_VALIDATION_DERIVATION,
        "asteria",
    ),
}


class CloudflareAudioModelError(AudioContractError):
    """Sanitized Cloudflare audio adapter failure."""


@dataclass(frozen=True)
class CloudflareAudioHttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class CloudflareAudioTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> CloudflareAudioHttpResponse: ...


class AudioDecodedMetadata(Protocol):
    @property
    def media_type(self) -> str: ...

    @property
    def container(self) -> str: ...

    @property
    def codec(self) -> str: ...

    @property
    def sample_rate(self) -> int: ...

    @property
    def sample_format(self) -> str: ...

    @property
    def bit_depth(self) -> int: ...

    @property
    def channels(self) -> int: ...

    @property
    def channel_layout(self) -> tuple[str, ...]: ...

    @property
    def duration(self) -> float: ...

    @property
    def sample_count(self) -> int: ...

    @property
    def bit_rate(self) -> int | None: ...

    @property
    def content_sha256(self) -> str: ...

    @property
    def pcm_sha256(self) -> str: ...

    @property
    def decoder(self) -> str: ...

    @property
    def peak(self) -> float: ...

    @property
    def rms(self) -> float: ...

    @property
    def loudness_lufs(self) -> float: ...

    @property
    def clipping_samples(self) -> int: ...

    @property
    def silence_samples(self) -> int: ...


class AudioByteValidator(Protocol):
    @property
    def project_ref(self) -> ProjectRef: ...

    @property
    def validator_ref(self) -> str: ...

    def validate(
        self,
        payload: bytes,
        *,
        expected_media_type: str,
    ) -> AudioDecodedMetadata: ...


@dataclass(frozen=True)
class _ResolvedArtifact:
    artifact_ref: ArtifactRef
    content_ref: ContentRef
    role: str
    payload: bytes


@dataclass(frozen=True)
class _ValidatedAudio:
    media_type: str
    container: str
    codec: str
    sample_rate: int
    sample_format: str
    bit_depth: int
    channels: int
    channel_layout: tuple[str, ...]
    duration: float
    sample_count: int
    bit_rate: int | None
    content_sha256: str
    pcm_sha256: str
    decoder: str
    peak: float
    rms: float
    loudness_lufs: float
    clipping_samples: int
    silence_samples: int


class _ProviderCallFailure(CloudflareAudioModelError):
    def __init__(
        self,
        category: str,
        message: str,
        response: CloudflareAudioHttpResponse | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.response = response


def _http_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_seconds: float,
) -> CloudflareAudioHttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return CloudflareAudioHttpResponse(
                response.status,
                dict(response.headers.items()),
                response.read(),
            )
    except urllib.error.HTTPError as exc:
        return CloudflareAudioHttpResponse(exc.code, dict(exc.headers.items()), exc.read())
    except urllib.error.URLError:
        raise OSError("Cloudflare request unavailable") from None


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _float_text(value: float) -> str:
    return format(value, ".17g")


class CloudflareAudioModel:
    """REAL Workers AI audio resource; secrets remain in the process environment."""

    project_ref: ProjectRef
    model_ref: str
    runtime_ref: str
    determinism: str

    def __init__(
        self,
        database_path: str | Path,
        object_store: ObjectStorageBackend,
        *,
        access: ProjectAccess,
        validator: AudioByteValidator,
        model_ref: str = _MODEL,
        runtime_ref: str = _RUNTIME,
        transport: CloudflareAudioTransport = _http_transport,
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        if not isinstance(access, ProjectAccess):
            raise TypeError("Cloudflare audio model requires ProjectAccess")
        if not isinstance(object_store, ObjectStorageBackend):
            raise TypeError("Cloudflare audio model requires ObjectStorageBackend")
        try:
            binding = _MODEL_BINDINGS[model_ref]
        except KeyError:
            raise CloudflareAudioModelError(
                "Cloudflare model_ref must name a bound Workers AI audio model"
            ) from None
        if runtime_ref != _RUNTIME:
            raise CloudflareAudioModelError("Cloudflare runtime_ref must name Workers AI")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0.0
        ):
            raise CloudflareAudioModelError("Cloudflare timeout must be finite and positive")
        try:
            validator_project = validator.project_ref
            validator_ref = validator.validator_ref
            validate = validator.validate
        except (AttributeError, TypeError):
            raise TypeError("Cloudflare audio model requires a full audio-byte validator") from None
        if validator_project != access.project_ref:
            raise CloudflareAudioModelError("audio validator crossed Project scope")
        if not isinstance(validator_ref, str) or _ABSOLUTE_REF.fullmatch(validator_ref) is None:
            raise CloudflareAudioModelError("audio validator identity is invalid")
        if not callable(validate):
            raise TypeError("Cloudflare audio model requires a callable audio validator")

        self.access = access
        self.project_ref = access.project_ref
        self.model_ref = model_ref
        self.model_version = _MODEL_VERSION
        self.runtime_ref = runtime_ref
        self._binding = binding
        self.determinism = "provider-unseeded"
        self.validator = validator
        self.validator_ref = validator_ref
        self.objects = object_store
        self.artifacts = ArtifactService(database_path)
        self.executions = NodeExecutionService(database_path)
        self.runs = RunService(database_path)
        self.calls = CallLedgerService(database_path)
        self.transport = transport
        self.environment = os.environ if environment is None else environment
        self.timeout_seconds = float(timeout_seconds)

    def _current_authority(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
    ) -> ExecutionAttempt:
        try:
            current = self.executions.get_node_execution(access, attempt.node_ref)
            producer = next(
                (
                    candidate
                    for candidate in self.runs.list_attempts(access, attempt.run_ref)
                    if candidate.attempt_id == attempt.run_attempt_id
                    and candidate.fence == attempt.run_fence
                ),
                None,
            )
            if producer is None or producer.completed_at is not None:
                raise CloudflareAudioModelError("Cloudflare Run attempt is stale")
            run = self.runs.assert_current_run_authority(access, producer)
        except (NodeExecutionError, RunError):
            raise CloudflareAudioModelError("Cloudflare Node or Run attempt is stale") from None
        if (
            current.status != "RUNNING"
            or current.current_attempt_id != attempt.attempt_id
            or current.current_fence != attempt.fence
            or producer.run_ref != attempt.run_ref
            or producer.task_ref != attempt.task_ref
            or producer.task_digest != attempt.task_digest
            or run.task_ref != attempt.task_ref
            or run.task_digest != attempt.task_digest
        ):
            raise CloudflareAudioModelError("Cloudflare Node or Run attempt is stale")
        return producer

    def _bind_specification(self, specification: AudioSpecification) -> None:
        label = self._binding.label
        if specification.project_ref != self.project_ref:
            raise CloudflareAudioModelError("audio specification crossed Project scope")
        if specification.operation not in {"generate", "speech"}:
            raise CloudflareAudioModelError(f"{label} accepts only generate or speech operations")
        if (
            specification.model_ref != self.model_ref
            or specification.model_version != self.model_version
            or specification.runtime_ref != self.runtime_ref
        ):
            raise CloudflareAudioModelError("audio model, version, or runtime identity does not match adapter")
        if specification.media_type != "audio/mpeg" or specification.container != "mp3":
            raise CloudflareAudioModelError(f"{label} output must be audio/mpeg in an MP3 container")
        if specification.codec not in {None, "mp3"}:
            raise CloudflareAudioModelError(f"{label} codec requirement is unsupported")
        if specification.seed != 0:
            raise CloudflareAudioModelError(f"{label} does not accept a seed")
        if specification.voice_ref != self._binding.voice_ref:
            raise CloudflareAudioModelError(f"{label} exposes only the bound provider voice")
        if (
            not isinstance(specification.language, str)
            or _LANGUAGE.fullmatch(specification.language) is None
        ):
            raise CloudflareAudioModelError(f"{label} language is invalid")
        if specification.validator_ref != self.validator_ref:
            raise CloudflareAudioModelError("audio validator identity does not match adapter")
        if specification.tool_config or specification.loudness_policy or specification.spatial_metadata:
            raise CloudflareAudioModelError(
                f"{label} cannot prove requested tool, loudness, or spatial controls"
            )
        chain = specification.processing_chain
        if (
            chain.chain_ref != _NATIVE_CHAIN
            or chain.version != "1.0.0"
            or chain.effects != (_NATIVE_EFFECT,)
            or chain.config
        ):
            raise CloudflareAudioModelError(
                f"{label} accepts only the provider-native processing chain"
            )
        if specification.measurement_algorithm_ref != _MEASUREMENT_ALGORITHM:
            raise CloudflareAudioModelError("audio measurement algorithm does not match full decode")
        if (
            specification.source_sample_rate is not None
            and specification.source_sample_rate != specification.target_sample_rate
        ):
            raise CloudflareAudioModelError(
                f"{label} cannot perform a requested sample-rate conversion"
            )
        if (
            specification.source_channel_layout is not None
            and specification.source_channel_layout != specification.target_channel_layout
        ):
            raise CloudflareAudioModelError(
                f"{label} cannot perform a requested channel conversion"
            )
        if specification.time_start is not None and specification.time_start != 0.0:
            raise CloudflareAudioModelError(f"{label} output must begin at zero")

        expected_contract = {
            "role": "audio.generated",
            "media_type": "audio/mpeg",
            "container": "mp3",
            "codec": "mp3",
        }
        contract = dict(specification.output_contract)
        if contract.get("role") != "audio.generated":
            raise CloudflareAudioModelError(f"{label} output role must be audio.generated")
        if any(expected_contract.get(key) != value for key, value in contract.items()):
            raise CloudflareAudioModelError(
                f"{label} output contract contains unsupported requirements"
            )

    def _request_payload(
        self,
        prompt: str,
        specification: AudioSpecification,
    ) -> dict[str, str]:
        if self._binding.speaker is None:
            if specification.language is None:
                raise CloudflareAudioModelError("MeloTTS language is invalid")
            return {"prompt": prompt, "lang": specification.language}
        return {
            "text": prompt,
            "speaker": self._binding.speaker,
            "encoding": "mp3",
        }

    def _provider_request_config(self) -> dict[str, object] | None:
        if self._binding.speaker is None:
            return None
        return {
            "container": {
                "sent": False,
                "selection": "provider-default",
            },
            "encoding": "mp3",
            "speaker": self._binding.speaker,
        }

    def _credentials(self) -> tuple[str, str]:
        account = self.environment.get("CLOUDFLARE_ACCOUNT_ID")
        token = self.environment.get("CLOUDFLARE_API_TOKEN")
        if (
            not isinstance(account, str)
            or re.fullmatch(r"[0-9a-fA-F]{32}", account) is None
            or not isinstance(token, str)
            or len(token) < 16
            or len(token) > 4096
            or any(character.isspace() or ord(character) < 33 for character in token)
        ):
            raise CloudflareAudioModelError("Cloudflare credentials are unavailable")
        return account, token

    def _artifact(
        self,
        access: ProjectAccess,
        value: AudioArtifactContentRef,
        label: str,
    ) -> _ResolvedArtifact:
        if value.project_ref != self.project_ref:
            raise CloudflareAudioModelError(f"{label} crossed Project scope")
        prefix = f"artifact://{self.project_ref.value}/"
        if not value.artifact_ref.startswith(prefix):
            raise CloudflareAudioModelError(f"{label} ArtifactRef is malformed or foreign")
        try:
            artifact_id, revision = value.artifact_ref.removeprefix(prefix).rsplit("/", 1)
            artifact_ref = ArtifactRef(self.project_ref, artifact_id, int(revision))
            artifact = self.artifacts.get_artifact(access, artifact_ref)
        except (ArtifactError, ValueError):
            raise CloudflareAudioModelError(f"{label} ArtifactRef is invalid") from None
        content = artifact.content_ref
        if (
            content is None
            or content.value != value.content_ref
            or content.digest != value.content_sha256
        ):
            raise CloudflareAudioModelError(
                f"{label} Artifact/Content identity is stale or forged"
            )
        try:
            payload = self.objects.read(content)
        except Exception:
            raise CloudflareAudioModelError(f"{label} content is missing or corrupt") from None
        if hashlib.sha256(payload).hexdigest() != content.digest:
            raise CloudflareAudioModelError(f"{label} content is missing or corrupt")
        return _ResolvedArtifact(artifact_ref, content, artifact.role, payload)

    def _prompt(
        self,
        access: ProjectAccess,
        specification: AudioSpecification,
    ) -> tuple[str, _ResolvedArtifact]:
        if specification.prompt is None:
            raise CloudflareAudioModelError("generative specification has no prompt identity")
        resolved = self._artifact(access, specification.prompt, "prompt")
        if resolved.role != "audio.prompt" or resolved.content_ref.media_type != "text/plain":
            raise CloudflareAudioModelError("prompt must be an audio.prompt UTF-8 text/plain Artifact")
        try:
            prompt = resolved.payload.decode("utf-8")
        except UnicodeDecodeError:
            raise CloudflareAudioModelError("prompt content is not UTF-8") from None
        if not prompt.strip():
            raise CloudflareAudioModelError("prompt content is empty")
        return prompt, resolved

    def _sources(
        self,
        access: ProjectAccess,
        specification: AudioSpecification,
    ) -> tuple[_ResolvedArtifact, ...]:
        entries = tuple(self._artifact(access, item, "reference") for item in specification.sources)
        if any(
            item.role not in _SOURCE_ROLES or not item.content_ref.media_type.startswith("audio/")
            for item in entries
        ):
            raise CloudflareAudioModelError("reference is not an exact audio provenance Artifact")
        return entries

    @staticmethod
    def _call_inputs(
        entries: Sequence[_ResolvedArtifact],
    ) -> tuple[ArtifactRef | ContentRef, ...]:
        values: dict[str, ArtifactRef | ContentRef] = {}
        for entry in entries:
            values[entry.artifact_ref.value] = entry.artifact_ref
            values[entry.content_ref.value] = entry.content_ref
        return tuple(values[key] for key in sorted(values))

    def _start_call(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: AudioSpecification,
        inputs: Sequence[ArtifactRef | ContentRef],
    ) -> ModelCall:
        try:
            return self.calls.start_model_call(
                access,
                attempt,
                idempotency_key=f"cloudflare-audio-{attempt.attempt_id}",
                capability_ref=CapabilityRef(f"audio.{specification.operation}", "1.0.0"),
                purpose="INITIAL",
                retry_of=None,
                provider_id=_PROVIDER,
                model_id=self.model_ref,
                deployment_id=None,
                runtime_id=self.runtime_ref,
                input_refs=inputs,
                provider_trace_id=None,
            )
        except CallError:
            raise CloudflareAudioModelError("Cloudflare ModelCall authority was rejected") from None

    def _send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> CloudflareAudioHttpResponse:
        try:
            return self.transport(method, url, headers, body, self.timeout_seconds)
        except Exception:
            raise _ProviderCallFailure(
                "PROVIDER_UNAVAILABLE",
                "Cloudflare audio request was unavailable",
            ) from None

    @staticmethod
    def _content_type(response: CloudflareAudioHttpResponse) -> str:
        for key, value in response.headers.items():
            if key.lower() == "content-type":
                return value.split(";", 1)[0].strip().lower()
        return ""

    def _response_audio(self, response: CloudflareAudioHttpResponse) -> bytes:
        if response.status < 200 or response.status >= 300:
            raise _ProviderCallFailure(
                "PROVIDER_HTTP_FAILURE",
                f"Cloudflare audio generation failed with HTTP {response.status}",
                response,
            )
        content_type = self._content_type(response)
        if content_type == "audio/mpeg":
            if not response.body:
                raise _ProviderCallFailure(
                    "PROVIDER_RESPONSE_INVALID",
                    "Cloudflare audio response is empty",
                    response,
                )
            return response.body
        if content_type != "application/json" and not content_type.endswith("+json"):
            raise _ProviderCallFailure(
                "PROVIDER_RESPONSE_INVALID",
                "Cloudflare response is neither audio/mpeg nor JSON",
                response,
            )
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise _ProviderCallFailure(
                "PROVIDER_RESPONSE_INVALID",
                "Cloudflare JSON audio response is invalid",
                response,
            ) from None
        value: object
        if isinstance(decoded, str):
            value = decoded
        elif isinstance(decoded, dict):
            if decoded.get("success") is False:
                raise _ProviderCallFailure(
                    "PROVIDER_RESPONSE_INVALID",
                    "Cloudflare JSON audio response reports failure",
                    response,
                )
            result = decoded.get("result", decoded)
            value = result.get("audio") if isinstance(result, dict) else result
        else:
            value = None
        if not isinstance(value, str) or not value:
            raise _ProviderCallFailure(
                "PROVIDER_RESPONSE_INVALID",
                "Cloudflare JSON response has no audio payload",
                response,
            )
        try:
            payload = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise _ProviderCallFailure(
                "PROVIDER_RESPONSE_INVALID",
                "Cloudflare JSON audio payload is not base64",
                response,
            ) from None
        if not payload:
            raise _ProviderCallFailure(
                "PROVIDER_RESPONSE_INVALID",
                "Cloudflare JSON audio payload is empty",
                response,
            )
        return payload

    def _decode_audio(
        self,
        payload: bytes,
        response: CloudflareAudioHttpResponse,
    ) -> _ValidatedAudio:
        try:
            metadata = self.validator.validate(payload, expected_media_type="audio/mpeg")
        except Exception:
            raise _ProviderCallFailure(
                "AUDIO_DECODE_FAILED",
                "provider audio is not fully decodable",
                response,
            ) from None

        layout = tuple(metadata.channel_layout)
        scalar_integers = (
            metadata.sample_rate,
            metadata.bit_depth,
            metadata.channels,
            metadata.sample_count,
            metadata.clipping_samples,
            metadata.silence_samples,
        )
        metrics = (metadata.duration, metadata.peak, metadata.rms, metadata.loudness_lufs)
        if (
            metadata.media_type != "audio/mpeg"
            or metadata.container != "mp3"
            or metadata.codec != "mp3"
            or not isinstance(metadata.sample_format, str)
            or not metadata.sample_format
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in scalar_integers
            )
            or metadata.sample_rate < 1
            or metadata.bit_depth < 1
            or metadata.channels < 1
            or metadata.sample_count < 1
            or not layout
            or len(layout) != metadata.channels
            or any(not isinstance(channel, str) or not channel for channel in layout)
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in metrics
            )
            or metadata.duration <= 0.0
            or (
                metadata.bit_rate is not None
                and (
                    not isinstance(metadata.bit_rate, int)
                    or isinstance(metadata.bit_rate, bool)
                    or metadata.bit_rate < 1
                )
            )
            or _SHA256.fullmatch(metadata.content_sha256) is None
            or metadata.content_sha256 != hashlib.sha256(payload).hexdigest()
            or _SHA256.fullmatch(metadata.pcm_sha256) is None
            or _ABSOLUTE_REF.fullmatch(metadata.decoder) is None
        ):
            raise _ProviderCallFailure(
                "AUDIO_DECODE_FAILED",
                "provider audio full-decode metadata is invalid",
                response,
            )
        return _ValidatedAudio(
            metadata.media_type,
            metadata.container,
            metadata.codec,
            metadata.sample_rate,
            metadata.sample_format,
            metadata.bit_depth,
            metadata.channels,
            layout,
            float(metadata.duration),
            metadata.sample_count,
            metadata.bit_rate,
            metadata.content_sha256,
            metadata.pcm_sha256,
            metadata.decoder,
            float(metadata.peak),
            float(metadata.rms),
            float(metadata.loudness_lufs),
            metadata.clipping_samples,
            metadata.silence_samples,
        )

    @staticmethod
    def _enforce_output(
        specification: AudioSpecification,
        audio: _ValidatedAudio,
        response: CloudflareAudioHttpResponse,
    ) -> None:
        mismatch = (
            (specification.codec is not None and specification.codec != audio.codec)
            or (
                specification.sample_format is not None
                and specification.sample_format != audio.sample_format
            )
            or (specification.bit_depth is not None and specification.bit_depth != audio.bit_depth)
            or (
                specification.target_sample_rate is not None
                and specification.target_sample_rate != audio.sample_rate
            )
            or (
                specification.target_channel_layout is not None
                and specification.target_channel_layout != audio.channel_layout
            )
        )
        if specification.duration is not None:
            tolerance = 1.0 / audio.sample_rate
            mismatch = mismatch or not math.isclose(
                specification.duration,
                audio.duration,
                rel_tol=0.0,
                abs_tol=tolerance,
            )
            assert specification.time_end is not None
            mismatch = mismatch or not math.isclose(
                specification.time_end,
                audio.duration,
                rel_tol=0.0,
                abs_tol=tolerance,
            )
        if mismatch:
            raise _ProviderCallFailure(
                "OUTPUT_CONTRACT_VIOLATION",
                "provider audio violates the exact decoded output contract",
                response,
            )

    def _audio_metadata(
        self,
        specification: AudioSpecification,
        call: ModelCall,
        audio: _ValidatedAudio,
    ) -> dict[str, str]:
        return {
            "media_type": audio.media_type,
            "schema_ref": "schema://biella/audio-generated/v1",
            "schema_version": "1.0.0",
            "semantic_label": "audio.generated",
        }

    def _validation_payload(
        self,
        specification: AudioSpecification,
        call: ModelCall,
        audio: _ValidatedAudio,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "bit_depth": audio.bit_depth,
            "bit_rate": audio.bit_rate,
            "channels": audio.channels,
            "channel_layout": list(audio.channel_layout),
            "clipping_samples": audio.clipping_samples,
            "codec": audio.codec,
            "container": audio.container,
            "content_sha256": audio.content_sha256,
            "decoder": audio.decoder,
            "duration": audio.duration,
            "full_decode": True,
            "loudness_lufs": audio.loudness_lufs,
            "media_type": audio.media_type,
            "model_call_ref": call.call_ref.value,
            "pcm_sha256": audio.pcm_sha256,
            "peak": audio.peak,
            "rms": audio.rms,
            "sample_count": audio.sample_count,
            "sample_format": audio.sample_format,
            "sample_rate": audio.sample_rate,
            "silence_samples": audio.silence_samples,
            "specification_digest": specification.canonical_digest,
            "validator_ref": self.validator_ref,
        }
        provider_request_config = self._provider_request_config()
        if provider_request_config is not None:
            payload["provider_request_config"] = provider_request_config
        return payload

    def _publish_success(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: AudioSpecification,
        call: ModelCall,
        provenance: Sequence[_ResolvedArtifact],
        payload: bytes,
        audio: _ValidatedAudio,
    ) -> AudioOutputRef:
        try:
            output_content = self.objects.put(payload, media_type=audio.media_type)
        except Exception:
            raise _ProviderCallFailure(
                "OUTPUT_STORAGE_FAILED",
                "provider audio storage failed",
            ) from None
        producer = self._current_authority(access, attempt)
        try:
            artifact = self.artifacts.publish_from_run(
                access,
                producer_attempt=producer,
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role="audio.generated",
                content_ref=output_content,
                source_refs=(),
                source_artifact_refs=tuple(item.artifact_ref for item in provenance),
                source_content_refs=tuple(item.content_ref for item in provenance),
                derivation_type=self._binding.derivation,
                metadata=self._audio_metadata(specification, call, audio),
            )
        except ArtifactError:
            raise _ProviderCallFailure(
                "OUTPUT_PUBLICATION_FAILED",
                "provider audio publication was rejected",
            ) from None

        try:
            validation_content = self.objects.put(
                _json_bytes(self._validation_payload(specification, call, audio)),
                media_type=_VALIDATION_MEDIA_TYPE,
            )
        except Exception:
            raise _ProviderCallFailure(
                "VALIDATION_EVIDENCE_FAILED",
                "provider audio validation evidence storage failed",
            ) from None
        producer = self._current_authority(access, attempt)
        try:
            validation_artifact = self.artifacts.publish_from_run(
                access,
                producer_attempt=producer,
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role="audio.validation-evidence",
                content_ref=validation_content,
                source_refs=(),
                source_artifact_refs=(artifact.artifact_ref,),
                source_content_refs=(output_content,),
                derivation_type=self._binding.validation_derivation,
                metadata={
                    "media_type": _VALIDATION_MEDIA_TYPE,
                    "schema_ref": "schema://biella/audio-validation/full-decode/v1",
                    "schema_version": "1.0.0",
                    "semantic_label": "audio.validation-evidence",
                },
            )
        except ArtifactError:
            raise _ProviderCallFailure(
                "VALIDATION_EVIDENCE_FAILED",
                "provider audio validation evidence publication failed",
            ) from None
        try:
            self.calls.finish_model_call(
                access,
                attempt,
                call.call_ref,
                idempotency_key=f"cloudflare-audio-finish-{attempt.attempt_id}",
                status="SUCCEEDED",
                output_refs=(
                    output_content,
                    artifact.artifact_ref,
                    validation_content,
                    validation_artifact.artifact_ref,
                ),
                usage=None,
                cost=None,
                failure_category=None,
                failure_reason=None,
                failure_evidence_refs=(),
            )
        except CallAuthorityError:
            raise CloudflareAudioModelError("Cloudflare Node or Run attempt is stale") from None
        except CallError:
            raise _ProviderCallFailure(
                "MODEL_CALL_REJECTED",
                "Cloudflare ModelCall completion was rejected",
            ) from None

        output = AudioArtifactContentRef(
            self.project_ref,
            artifact.artifact_ref.value,
            output_content.value,
            output_content.digest,
        )
        return AudioOutputRef.create(
            self.project_ref,
            specification,
            output,
            audio.duration,
            audio.sample_rate,
            audio.channel_layout,
            audio.codec,
            audio.sample_format,
            audio.bit_depth,
            attempt.attempt_id,
            attempt.fence,
            self._binding.derivation,
        )

    def _record_failure(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: AudioSpecification,
        call: ModelCall,
        provenance: Sequence[_ResolvedArtifact],
        failure: _ProviderCallFailure,
        response: CloudflareAudioHttpResponse | None,
    ) -> None:
        selected_response = failure.response if failure.response is not None else response
        receipt: dict[str, object] = {
            "category": failure.category,
            "model_call_ref": call.call_ref.value,
            "model_ref": self.model_ref,
            "response_content_type": (
                None if selected_response is None else self._content_type(selected_response)
            ),
            "response_sha256": (
                None
                if selected_response is None
                else hashlib.sha256(selected_response.body).hexdigest()
            ),
            "response_status": None if selected_response is None else selected_response.status,
            "specification_digest": specification.canonical_digest,
            "validator_ref": self.validator_ref,
        }
        provider_request_config = self._provider_request_config()
        if provider_request_config is not None:
            receipt["provider_request_config"] = provider_request_config
        try:
            evidence_content = self.objects.put(
                _json_bytes(receipt),
                media_type=_VALIDATION_MEDIA_TYPE,
            )
            producer = self._current_authority(access, attempt)
            evidence_artifact = self.artifacts.publish_from_run(
                access,
                producer_attempt=producer,
                expected_task_ref=attempt.task_ref,
                expected_task_digest=attempt.task_digest,
                role="audio.validation-evidence",
                content_ref=evidence_content,
                source_refs=(),
                source_artifact_refs=tuple(item.artifact_ref for item in provenance),
                source_content_refs=tuple(item.content_ref for item in provenance),
                derivation_type=self._binding.validation_derivation,
                metadata={
                    "media_type": _VALIDATION_MEDIA_TYPE,
                    "schema_ref": "schema://biella/audio-validation/failure/v1",
                    "schema_version": "1.0.0",
                    "semantic_label": "audio.validation-evidence",
                },
            )
            self.calls.finish_model_call(
                access,
                attempt,
                call.call_ref,
                idempotency_key=f"cloudflare-audio-failure-{attempt.attempt_id}",
                status="FAILED",
                output_refs=(),
                usage=None,
                cost=None,
                failure_category=failure.category,
                failure_reason=str(failure),
                failure_evidence_refs=(evidence_content, evidence_artifact.artifact_ref),
            )
        except Exception:
            return

    def generate(
        self,
        access: ProjectAccess,
        attempt: NodeExecutionAttempt,
        specification: AudioSpecification,
    ) -> AudioOutputRef:
        if (
            access != self.access
            or not isinstance(attempt, NodeExecutionAttempt)
            or attempt.node_ref.project_ref != self.project_ref
            or attempt.run_ref.project_ref != self.project_ref
            or attempt.task_ref.project_ref != self.project_ref
        ):
            raise CloudflareAudioModelError("Cloudflare generation crossed Project or authority")
        if not isinstance(specification, AudioSpecification):
            raise CloudflareAudioModelError("audio specification is invalid")
        self._current_authority(access, attempt)
        self._bind_specification(specification)
        account, token = self._credentials()
        prompt, prompt_entry = self._prompt(access, specification)
        source_entries = self._sources(access, specification)
        provenance = (prompt_entry, *source_entries)
        call = self._start_call(
            access,
            attempt,
            specification,
            self._call_inputs(provenance),
        )
        response: CloudflareAudioHttpResponse | None = None
        try:
            response = self._send(
                "POST",
                (
                    f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/"
                    f"{self._binding.api_id}"
                ),
                {
                    "Accept": "audio/mpeg, application/json",
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                _json_bytes(self._request_payload(prompt, specification)),
            )
            self._current_authority(access, attempt)
            payload = self._response_audio(response)
            audio = self._decode_audio(payload, response)
            self._enforce_output(specification, audio, response)
            self._current_authority(access, attempt)
            return self._publish_success(
                access,
                attempt,
                specification,
                call,
                provenance,
                payload,
                audio,
            )
        except _ProviderCallFailure as failure:
            self._record_failure(
                access,
                attempt,
                specification,
                call,
                provenance,
                failure,
                response,
            )
            raise CloudflareAudioModelError(str(failure)) from None


def cloudflare_audio_model_adapter(*args: object, **kwargs: object) -> AudioModelAdapter:
    """Return the replaceable provider-neutral audio adapter protocol."""
    return CloudflareAudioModel(*args, **kwargs)  # type: ignore[arg-type]
