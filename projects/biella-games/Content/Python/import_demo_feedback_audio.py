"""Author/verify finite native Audio Mixer SoundWaves from editable PCM masters.

UnrealEditor-Cmd <project> -run=pythonscript -script=<this-file>
  -EnablePlugins=PythonScriptPlugin -unattended -nullrhi -nosound -nop4
Existing assets are verified without modification. -D01ReimportFeedbackAudio
explicitly rebuilds from changed masters; -D01VerifyFeedbackAudio is read-only
and requires every saved SoundWave. The runtime uses native assets, not Python.
"""
import hashlib
import json
from pathlib import Path
import wave

import unreal


PROJECT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
ROOT = PROJECT / "SourceAssets/Audio/Demo01"
DESTINATION = "/Game/Feedback/Audio"


def require(condition, message):
    if not condition:
        raise RuntimeError("D01_042_AUDIO FAIL: " + message)


def verify_asset(asset, name, cue):
    require(isinstance(asset, unreal.SoundWave), name + " is not a native SoundWave")
    require(asset.get_editor_property("num_channels") == 1, name + " must be spatializable mono")
    require(asset.get_editor_property("imported_sample_rate") == 48000, name + " sample rate")
    require(abs(asset.get_editor_property("duration") - cue["duration_seconds"]) < 0.001, name + " duration")
    require(not asset.get_editor_property("looping"), name + " must be finite")
    require(asset.get_editor_property("loading_behavior") == unreal.SoundWaveLoadingBehavior.FORCE_INLINE,
            name + " must avoid first-use streaming latency")
    require(asset.get_sound_asset_compression_type() == unreal.SoundAssetCompressionType.PCM,
            name + " must use lossless PCM decoding")
    require(unreal.EditorAssetLibrary.get_metadata_tag(asset, "D01.SourceSHA256") == cue["sha256"],
            name + " source changed; use explicit -D01ReimportFeedbackAudio")
    # Round-trip the native asset's retained wave content through Unreal's exporter
    # and decode it, rather than claiming import success from the task return alone.
    export = PROJECT / "Saved/D01-042/AudioReadback" / (name + ".wav")
    export.parent.mkdir(parents=True, exist_ok=True)
    task = unreal.AssetExportTask()
    task.set_editor_property("object", asset)
    task.set_editor_property("filename", str(export))
    task.set_editor_property("automated", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("exporter", unreal.SoundExporterWAV())
    require(unreal.Exporter.run_asset_export_task(task), name + " native export failed")
    with wave.open(str(export)) as stream, wave.open(str(ROOT / (name + ".wav"))) as source:
        require(stream.getparams() == source.getparams(), name + " native decoded format changed")
        require(stream.readframes(stream.getnframes()) == source.readframes(source.getnframes()),
                name + " native decoded PCM differs from master")
    result = {"asset": asset.get_path_name(), "duration_seconds": asset.get_editor_property("duration"),
              "channels": asset.get_editor_property("num_channels"), "sample_rate": 48000,
              "encoding": "PCM", "loading": "ForceInline", "source_sha256": cue["sha256"],
              "native_roundtrip_pcm": "PASS", "status": "GENERATED_DRAFT"}
    unreal.log("D01_042_AUDIO PASS " + json.dumps(result, sort_keys=True))
    return result


manifest = json.loads((ROOT / "manifest.json").read_text())
command = unreal.SystemLibrary.get_command_line()
reimport = "-D01ReimportFeedbackAudio" in command
verify_only = "-D01VerifyFeedbackAudio" in command
require(not (reimport and verify_only), "Reimport and read-only verification cannot be combined")
results = []
for name, cue in manifest["cues"].items():
    source = ROOT / (name + ".wav")
    require(hashlib.sha256(source.read_bytes()).hexdigest() == cue["sha256"], name + " source manifest mismatch")
    asset_path = DESTINATION + "/" + name
    asset = unreal.EditorAssetLibrary.load_asset(asset_path) if unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
    if not asset or reimport:
        require(not verify_only, name + " saved asset missing")
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(source))
        task.set_editor_property("destination_path", DESTINATION)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", reimport)
        task.set_editor_property("save", False)
        task.set_editor_property("factory", unreal.SoundFactory())
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        require(asset is not None, "Import produced no SoundWave: " + name)
        asset.set_editor_property("looping", False)
        asset.set_editor_property("loading_behavior", unreal.SoundWaveLoadingBehavior.FORCE_INLINE)
        asset.set_sound_asset_compression_type(unreal.SoundAssetCompressionType.PCM)
        unreal.EditorAssetLibrary.set_metadata_tag(asset, "D01.SourceSHA256", cue["sha256"])
        unreal.EditorAssetLibrary.set_metadata_tag(asset, "D01.Status", "GENERATED_DRAFT")
        require(unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False), name + " save failed")
    results.append(verify_asset(asset, name, cue))
report = PROJECT / "Build/Demo01/D01-042-audio-assets.json"
report.write_text(json.dumps({"task_id": "D01-42", "result": "PASS", "assets": results}, indent=2) + "\n")
unreal.log("D01_042_AUDIO COMPLETE assets=" + str(len(results)) + " result=PASS")
