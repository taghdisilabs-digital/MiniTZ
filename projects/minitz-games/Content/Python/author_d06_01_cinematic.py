"""Author and read back D06-01's editable runtime handoff sequence.

The sequence is deliberately technical: one editable camera binding and one
camera-cut section.  The native director supplies the camera from the live
game world at runtime, so this asset never contains a duplicate player or a
disconnected presentation map.

Authoring creates the asset once.  Readback uses ``-D06VerifyCinematic`` and
does not write the sequence.
"""

import hashlib
import json
import os
from pathlib import Path

import unreal


PROJECT = Path(__file__).resolve().parents[2]
ASSET_PATH = "/Game/Cinematics/LS_Demo01_RuntimeHandoff"
ROOT = "/Game/Cinematics"
VERIFY = "-D06VerifyCinematic" in unreal.SystemLibrary.get_command_line()
LIB = unreal.EditorAssetLibrary
ASSETS = unreal.AssetToolsHelpers.get_asset_tools()
SOURCE_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError("D06_CINEMATIC AUTHORING FAIL: " + message)


def command_value(prefix):
    for token in unreal.SystemLibrary.get_command_line().split():
        if token.startswith(prefix):
            return token[len(prefix):]
    return None


report_value = (os.environ.get("BIELLA_D06_CINEMATIC_REPORT") or
                command_value("-BiellaD06CinematicOutput="))
REPORT = Path(report_value) if report_value else PROJECT / "Build/Cinematics/D06-01-authoring.json"


def load_or_create():
    existing = LIB.does_asset_exist(ASSET_PATH)
    sequence = LIB.load_asset(ASSET_PATH) if existing else None
    if sequence is None:
        require(not VERIFY, "editable sequence is missing in verify mode")
        sequence = ASSETS.create_asset(
            "LS_Demo01_RuntimeHandoff", ROOT, unreal.LevelSequence,
            unreal.LevelSequenceFactoryNew())
    require(sequence is not None, "cannot load or create editable Level Sequence")
    require(sequence.get_class().get_name() == "LevelSequence",
            "runtime handoff asset is not a LevelSequence")
    return sequence, existing


def inspect(sequence):
    bindings = list(sequence.get_bindings())
    require(len(bindings) == 1, "sequence must contain exactly one camera binding")
    tracks = list(sequence.get_tracks())
    camera_tracks = [track for track in tracks
                     if track.get_class().get_name() == "MovieSceneCameraCutTrack"]
    require(len(camera_tracks) == 1, "sequence must contain exactly one camera-cut track")
    sections = list(camera_tracks[0].get_sections())
    require(len(sections) == 1, "camera-cut track must contain exactly one section")
    start_frame = int(sequence.get_playback_start())
    end_frame = int(sequence.get_playback_end())
    require(start_frame == 0 and end_frame > start_frame,
            "sequence playback range must be non-empty and start at zero")
    return {
        "class": sequence.get_class().get_name(),
        "binding_count": len(bindings),
        "binding_name": str(bindings[0].get_display_name()),
        "binding_id": str(bindings[0].get_id()),
        "binding_class": "CameraActor",
        "camera_cut_track_count": len(camera_tracks),
        "camera_cut_section_count": len(sections),
        "playback_start": start_frame,
        "playback_end": end_frame,
    }


def author(sequence, existing):
    if existing:
        return inspect(sequence)

    binding = sequence.add_spawnable_from_class(unreal.CameraActor)
    require(binding is not None, "cannot add the editable runtime camera binding")
    binding.set_display_name("RuntimePresentationCamera")

    camera_cut_track = sequence.add_track(unreal.MovieSceneCameraCutTrack)
    require(camera_cut_track is not None, "cannot add camera-cut track")
    section = camera_cut_track.add_section()
    require(section is not None, "cannot add camera-cut section")
    section.set_start_frame_seconds(0.0)
    section.set_end_frame_seconds(3.0)

    binding_id = unreal.MovieSceneObjectBindingID()
    binding_id.set_editor_property("Guid", binding.get_id())
    section.set_camera_binding_id(binding_id)
    sequence.set_playback_start(0)
    sequence.set_playback_end(72)
    LIB.set_metadata_tag(sequence, "D06.SourceSHA256", SOURCE_SHA)
    LIB.set_metadata_tag(sequence, "D06.Status", "GENERATED_DRAFT")
    require(LIB.save_loaded_asset(sequence), "editable sequence save failed")
    return inspect(sequence)


def main():
    report = {
        "task_id": "D06-01",
        "result": "FAIL",
        "mode": "verify" if VERIFY else "author",
        "asset": ASSET_PATH,
        "source_sha256": SOURCE_SHA,
    }
    try:
        sequence, existing = load_or_create()
        report["sequence"] = author(sequence, existing)
        report["result"] = "PASS"
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("D06_CINEMATIC_AUTHORING COMPLETE mode=%s asset=%s bindings=%d camera_cut_tracks=%d playback_end=%d" % (
            report["mode"], ASSET_PATH, report["sequence"]["binding_count"],
            report["sequence"]["camera_cut_track_count"], report["sequence"]["playback_end"]))
        return 0
    except Exception as error:
        report["error"] = str(error)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(str(error))
        raise


if __name__ == "__main__":
    main()
