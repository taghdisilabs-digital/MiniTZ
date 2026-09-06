#!/usr/bin/env python3
"""Validate D01-42 through rendered gameplay, live Niagara and recorded mixer PCM.

Requires the current Unreal Editor target and feedback assets already built.
Keeps every attempt, including failure evidence, and never publishes metadata.
"""
import argparse
import array
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import pwd
import re
import sys
import wave

from PIL import Image, ImageStat
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, identities, runtime_run, source_revision


STAGES = ("combat", "hurt", "pressure", "success", "failure")
REQUIRED_PHASES = {"fresh_assets", "confirmed_spatial_combat", "rejected_events_silent", "particles_rendered",
                   "melee_and_dense_combat", "dense_rendered_tick", "damage_bounded", "pressure_transition_only", "success_once", "restart_reset",
                   "failure_once", "lifecycle_drained"}


def decode_audio(path):
    with wave.open(str(path), "rb") as stream:
        channels, width, rate, frames = stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()
        assert width == 2 and channels in (1, 2), f"Unexpected mixer PCM format in {path.name}"
        samples = array.array("h", stream.readframes(frames))
    if sys.byteorder != "little":
        samples.byteswap()
    assert rate >= 22050 and len(samples) == frames * channels, f"Incomplete mixer PCM in {path.name}"
    duration = frames / rate
    assert 0.3 <= duration <= 12, f"Unbounded/empty recording in {path.name}: {duration}s"
    peak = max(abs(value) for value in samples) / 32768
    clipped_samples = sum(value <= -32768 or value >= 32767 for value in samples)
    assert clipped_samples == 0 and peak < 0.99, f"Clipped or headroom-free mixer output in {path.name}: peak={peak}"
    rms = math.sqrt(sum(float(value) ** 2 for value in samples) / len(samples)) / 32768
    audible_frames = sum(any(abs(samples[offset + channel]) > 32 for channel in range(channels))
                         for offset in range(0, len(samples), channels))
    audible_seconds = audible_frames / rate
    assert peak > 0.005 and rms > 0.0001 and audible_seconds > 0.03, f"Silent/inaudible rendered cue in {path.name}"
    return {**file_identity(path), "sample_rate": rate, "channels": channels, "pcm_bits": width * 8,
            "frames": frames, "clipped_samples": clipped_samples, "duration_seconds": round(duration, 4), "peak": round(peak, 6),
            "rms": round(rms, 6), "audible_seconds": round(audible_seconds, 4),
            "source": "Unreal runtime master submix; software audio mixer, not physical-speaker capture"}


def ensure_runtime_output(folder, account):
    missing, parent = [], folder
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    folder.mkdir(parents=True, exist_ok=False)
    for parent in missing:
        parent.chmod(0o755)
    if os.geteuid() == 0:
        os.chown(folder, account.pw_uid, account.pw_gid)


def task_identities(editor):
    paths = [path for path in (PROJECT / "Content/Feedback").rglob("*") if path.is_file()]
    paths += [path for path in (PROJECT / "SourceAssets/Audio/Demo01").rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    paths += [PROJECT / "Content/Python/import_demo_feedback_audio.py", PROJECT / "Content/Python/build_demo_feedback_vfx.py",
              PROJECT / "Content/Python/run_demo_feedback_vfx_authoring.py",
              PROJECT / "tests/verify_d01_042_audio_assets.py", Path(__file__)]
    return identities(editor) + [file_identity(path) for path in sorted(paths)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", type=Path, default=DEFAULT_EDITOR)
    parser.add_argument("--timeout", type=float, default=150)
    parser.add_argument("--output", type=Path, help="Fresh evidence directory for a scoped regression")
    parser.add_argument("--captures", type=Path, help="Fresh capture directory; default location is unchanged")
    args = parser.parse_args()
    if not 0 < args.timeout <= 150:
        parser.error("--timeout must be between zero and 150 seconds")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = (args.output or PROJECT / "Build/Demo01/D01-042-runs" / stamp).resolve()
    captures = (args.captures or Path("/root/biella/artifacts/games/D01-042") / stamp).resolve()
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(evidence, account)
    ensure_runtime_output(captures, account)
    protected = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
                 PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md", PROJECT / "docs/PRODUCTION.md"]
    report_path = evidence / "validation.json"
    report = {"task_id": "D01-42", "result": "FAIL", "visual_status": "GENERATED_DRAFT", "simulation_delta_seconds": 1 / 60,
              "timing_note": "Fixed simulation delta protects short effects from screenshot readback stalls; wall measurements are not shipping performance acceptance.",
              "revision": source_revision(), "identities_before": task_identities(args.editor),
              "protected_before": [file_identity(path) for path in protected], "captures_directory": str(captures)}

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    save()
    print(f"D01-42 evidence: {report_path}", flush=True)
    try:
        prefix = ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []
        # DeterministicAudio selects UE's NonRealtimeAudioRenderer directly.
        # It runs the actual mixer and decoding without requiring audio hardware.
        # Fixed simulation steps preserve short particle lifetimes across blocking
        # screenshot readback. Reported wall timing is evidence, not a FPS claim.
        command = prefix + ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", str(args.editor),
                   str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaGameplayMap", "-game", "-vulkan",
                   "-NoVSync", "-windowed", "-ResX=1280", "-ResY=720", "-unattended", "-AudioMixer",
                   "-DeterministicAudio", "-UseFixedTimeStep", "-FPS=60", "-nosplash", "-NoAsyncLoadingThread", "-stdout", "-FullStdOutLogOutput",
                   f"-AbsLog={evidence / 'feedback.engine.log'}",
                   "-ExecCmds=Automation RunTests BiellaGames.Demo01.EventFeedback; SoftQuit",
                   f"-BiellaFeedbackOutput={captures}"]
        report["runtime"] = runtime_run(command, evidence / "feedback.stdout.log", args.timeout)
        save()
        runtime = report["runtime"]
        assert not runtime["timed_out"] and runtime["returncode"] == 0, "Unreal failed or exceeded the process deadline"
        log = Path(runtime["log"]["path"]).read_text(errors="replace")
        assert re.search(r"Result=\{Success\}.*Name=\{EventFeedback\}", log), "EventFeedback automation did not pass"
        assert "D01_042_TEST COMPLETE" in log, "Scenario completion missing"
        assert not re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|D01_042_TEST FAIL", log), "Unreal runtime error"
        report["phases"] = re.findall(r"D01_042_TEST PASS phase=(\w+)", log)
        assert REQUIRED_PHASES <= set(report["phases"]), f"Missing required phases: {REQUIRED_PHASES - set(report['phases'])}"
        report["particle_samples"] = [{"cue": int(cue), "live_particles": int(count)} for cue, count in
                                      re.findall(r"D01_042_TEST PARTICLES cue=(\d+) count=(\d+) registered=true render_state=true", log)]
        assert len(report["particle_samples"]) == 4 and all(item["live_particles"] > 0 for item in report["particle_samples"]), "Live rendered particle proof missing"
        report["audio"] = [decode_audio(captures / f"{stage}.wav") for stage in STAGES]
        assert len({item["sha256"] for item in report["audio"]}) == len(STAGES), "Cue recordings are unexpectedly identical"
        report["frames"] = []
        report["particle_attributes"] = re.findall(r"D01_042_TEST ATTR ([^\n]+)", log)
        assert len(report["particle_attributes"]) == 8, "Missing spatial particle attribute evidence"
        report["dense_tick"] = re.findall(r"D01_042_TEST DENSE ([^\n]+)", log)
        assert report["dense_tick"], "Dense simulation timing evidence missing"
        for stage in (*STAGES, "dense_combat"):
            path = captures / f"{stage}.png"
            with Image.open(path) as frame:
                frame.load()
                assert frame.size == (1280, 720), "Capture viewport dimensions differ"
                deviation = ImageStat.Stat(frame.convert("RGB")).stddev
                assert max(deviation) > 15, "Blank/near-uniform rendered frame"
            report["frames"].append({**file_identity(path), "rgb_stddev": deviation})
        report["identities_after"] = task_identities(args.editor)
        report["protected_after"] = [file_identity(path) for path in protected]
        assert report["identities_before"] == report["identities_after"], "Tested source/assets/build changed during run"
        assert report["protected_before"] == report["protected_after"], "Protected canonical metadata changed"
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError) as error:
        report["error"] = str(error)
    finally:
        save()
    print(json.dumps({"result": report["result"], "validation": str(report_path), "error": report.get("error")}, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
