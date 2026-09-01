from __future__ import annotations

from dataclasses import replace

import pytest

import biella
from biella.audio_pack import (
    AudioArtifactContentRef,
    AudioContractError,
    AudioOutputRef,
    AudioSpecification,
    EditableAudioSessionBinding,
    MixSpecification,
    ProcessingChain,
    StemSpecification,
    audio_production_pack,
)
from biella.production_pack import ProductionPackRef
from biella.project import ProjectRef


MANDATORY = {
    "inspect", "import", "generate", "edit", "trim", "segment", "resample", "clean",
    "filter", "normalize", "mix", "master", "convert", "analyze", "spatial_prepare",
    "preview", "export", "validate",
}
OPTIONAL = {"speech", "transcribe", "stem_separation"}
ATTEMPT = "natt_" + "b" * 32


def _artifact(project_ref: ProjectRef, name: str, digest: str) -> AudioArtifactContentRef:
    return AudioArtifactContentRef(project_ref, f"artifact://{project_ref.value}/{name}/1", f"content://audio/{name}", digest)


def _specification(project_ref: ProjectRef) -> AudioSpecification:
    source = _artifact(project_ref, "source", "a" * 64)
    prompt = _artifact(project_ref, "prompt", "b" * 64)
    chain = ProcessingChain("chain://audio/dialogue/v1", "c" * 64, "1.0.0", ("effect://audio/denoise/v1",), {"strength": "0.2"})
    return AudioSpecification.create(
        project_ref, "dialogue", (source,), "generate", "recipe://audio/generate/v1", "d" * 64,
        None, None, None, None, None, None, None, "audio/wav", "wav", None, None, None,
        chain, {"tool": "config://audio/v1"}, {"integrated_lufs": "-16", "true_peak_dbtp": "-1"},
        "algorithm://ebu-r128/v1", {"mode": "none"}, "model://audio/generic/v1", "1.0.0",
        "runtime://audio/generic/v1", 7, "voice://generic/v1", "en", prompt,
        "validator://audio/generic/v1", {"role": "audio.generated"},
    )


def test_audio_pack_registers_mandatory_and_explicit_optional_descriptors() -> None:
    pack = audio_production_pack()
    assert pack.pack_ref == ProductionPackRef("audio", "1.0.0")
    capabilities = {item.capability_id: item for item in pack.capability_definitions}
    assert set(capabilities) == {f"audio.{name}" for name in MANDATORY | OPTIONAL}
    assert all("optional" not in capabilities[f"audio.{name}"].input_contract for name in MANDATORY)
    assert all(capabilities[f"audio.{name}"].input_contract["optional"] == "contract://capability/optional/v1" for name in OPTIONAL)
    assert {"audio.source", "audio.clip", "audio.stem", "audio.generated", "audio.cleaned", "audio.mix", "audio.master", "audio.preview", "audio.export", "audio.analysis", "audio.validation-evidence", "audio.prompt", "audio.session", "audio.transcript"} <= set(pack.artifact_roles)
    assert {
        "AUDIO_ARTIFACT_ROLES", "AUDIO_CAPABILITIES", "AUDIO_OPTIONAL_CAPABILITIES",
        "AudioArtifactContentRef", "AudioContractError", "AudioInspectionRef",
        "AudioModelAdapter", "AudioOutputRef", "AudioSpecification", "AudioToolAdapter",
        "EditableAudioSessionBinding", "GameAudioHandoffBinding", "MixSpecification",
        "ProcessingChain", "StemSpecification", "VideoAudioHandoffBinding",
        "audio_production_pack", "AudioByteValidator", "CloudflareAudioHttpResponse",
        "CloudflareAudioModel", "CloudflareAudioModelError", "CloudflareAudioTransport",
        "cloudflare_audio_model_adapter", "AudioDecodedMetadata", "AudioInspection",
        "AudioMixResult", "AudioStemBatch", "AudioTargetMeasurements", "DeterministicAudioTool",
    } <= set(biella.__all__)


def test_audio_specification_provenance_conversions_and_output_fail_closed() -> None:
    project_ref = ProjectRef.new()
    specification = _specification(project_ref)
    output = AudioOutputRef.create(project_ref, specification, _artifact(project_ref, "output", "e" * 64), 2.0, 48000, ("left", "right"), "pcm", "pcm_s16le", 16, ATTEMPT, 1, "audio.generate")
    assert output.specification_digest == specification.canonical_digest
    with pytest.raises(AudioContractError, match="canonical_digest"):
        replace(specification, model_version="2.0.0")
    with pytest.raises(AudioContractError, match="sample rates"):
        AudioSpecification.create(project_ref, "x", specification.sources, "edit", "recipe://audio/edit/v1", "d" * 64, 0.0, 1.0, 1.0, 48000, None, ("left", "right"), None, "audio/wav", "wav", "pcm", "pcm_s16le", 16, specification.processing_chain, {}, {}, "algorithm://ebu-r128/v1", {}, "model://audio/generic/v1", "1", "runtime://audio/generic/v1", 1, None, None, None, "validator://audio/generic/v1", {})
    with pytest.raises(AudioContractError, match="Project"):
        AudioSpecification.create(project_ref, "x", specification.sources, "generate", "recipe://audio/generate/v1", "d" * 64, 0.0, 1.0, 1.0, None, None, None, None, "audio/wav", "wav", None, "pcm_s16le", 16, specification.processing_chain, {}, {}, "algorithm://ebu-r128/v1", {}, "model://audio/generic/v1", "1", "runtime://audio/generic/v1", 1, None, None, _artifact(ProjectRef.new(), "prompt", "b" * 64), "validator://audio/generic/v1", {})


def test_stems_mix_and_editable_session_bind_exact_project_contracts() -> None:
    project_ref = ProjectRef.new()
    specification = _specification(project_ref)
    stem = StemSpecification(project_ref, specification, "dialogue", _artifact(project_ref, "stem", "f" * 64))
    mix = MixSpecification(project_ref, "mix://audio/dialogue/v1", "1.0.0", (stem,), {"dialogue": "0.0"})
    session = EditableAudioSessionBinding(project_ref, specification, _artifact(project_ref, "session", "0" * 64), "tool://audio/editor/v1", "1.0.0")
    assert mix.stems == (stem,) and session.specification is specification
    with pytest.raises(AudioContractError, match="Project"):
        MixSpecification(ProjectRef.new(), "mix://audio/dialogue/v1", "1.0.0", (stem,), {"dialogue": "0.0"})
