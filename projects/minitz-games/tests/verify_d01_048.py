#!/usr/bin/env python3
"""Replay D01-48 package, live gameplay, media and source-integrity evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageStat

from run_d01_042 import decode_audio, REQUIRED_PHASES as FEEDBACK_PHASES, STAGES
from verify_d01_031 import verify as verify_shared
from verify_d01_033 import verify as verify_pressure
from verify_d01_039 import require, verify as verify_core


PACKAGE_SHA = "c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8"
PACKAGE_COMMIT = "00c7243077403d9ebfb812318cd23a3a5b13641f"
EXPECTED_RUNS = {
    "core-nullrhi": ("DeterministicPlaytest", "nullrhi", "039"),
    "core-vulkan": ("DeterministicPlaytest", "vulkan", "039"),
    "shared": ("SharedInteraction", "vulkan", "031"),
    "pressure": ("PressureResponses", "vulkan", "033"),
    "navigation": ("RivalNavigation", "vulkan", "029"),
    "visual": ("VisualReadability", "vulkan", "040"),
    "feedback": ("EventFeedback", "vulkan", "042"),
}
NAVIGATION_PHASES = ["detour", "hold", "retreat", "dynamic_obstruction", "occluded_combat_position",
                     "bounded_failure", "route_reopened", "no_target_stop", "defeat_stop"]
VISUAL_STAGES = ["active_06m", "active_12m", "active_20m", "low_health_pressure_100", "success", "failure"]
FAULTS = (r"\bLog\w+:\s*(?:Error|Fatal):|Fatal error:|Assertion failed:|Ensure condition failed:|"
          r"Result=\{Fail\}|Segmentation fault|Unhandled Exception|D01_\d+_TEST FAIL")


def verify_identity(item):
    path = Path(item["path"])
    require(path.is_file(), f"Missing evidence artifact: {path}")
    require(type(item["bytes"]) is int and path.stat().st_size == item["bytes"], f"Artifact size changed: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    require(digest.hexdigest() == item["sha256"], f"Artifact hash changed: {path}")
    return path


def verify_coverage(runs):
    require(len(runs) == len(EXPECTED_RUNS), "Exactly seven acceptance runs are required")
    selected = {run["name"]: run for run in runs}
    require(set(selected) == set(EXPECTED_RUNS), "Missing or duplicate acceptance suites")
    for name, run in selected.items():
        require((run["suite"], run["renderer"]) == EXPECTED_RUNS[name][:2], f"Wrong suite/renderer for {name}")
    extractions = [str(Path(run["extraction"]).resolve()) for run in runs]
    require(len(set(extractions)) == len(runs), "Each suite requires an independent clean extraction")
    return selected


def verify_runtime(run):
    runtime = run["runtime"]
    require(runtime["timed_out"] is False, f"{run['name']}: process timeout")
    require(type(runtime["returncode"]) is int and runtime["returncode"] == 0,
            f"{run['name']}: nonzero process exit")
    content = verify_identity(runtime["log"]).read_text(encoding="utf-8", errors="replace")
    require(not re.search(FAULTS, content, re.I), f"{run['name']}: observed runtime error/failure")
    mount = re.search(r"Mounted Pak file[^\n]*BiellaGames-Linux\.pak", content)
    require(mount, f"{run['name']}: canonical gameplay pak was not mounted")
    for signal in ("GAME_INSTANCE_READY", "WORLD_READY", "HUD_READY", "CONTROLLER_READY"):
        require(f"D01_SIGNAL {signal}" in content, f"{run['name']}: missing {signal}")
    marker = f"D01_{EXPECTED_RUNS[run['name']][2]}_TEST COMPLETE"
    complete = content.find(marker)
    success = re.search(r"Result=\{Success\}\s+Name=\{" + re.escape(run["suite"]) +
                        r"\}\s+Path=\{BiellaGames\.Demo01\." + re.escape(run["suite"]) + r"\}", content)
    exit_marker = content.find("**** TEST COMPLETE. EXIT CODE: 0 ****")
    clean_exit = content.rfind("LogExit: Exiting.")
    require(complete >= 0 and success and exit_marker >= 0 and clean_exit >= 0,
            f"{run['name']}: missing scenario/automation/clean exit completion")
    require(mount.start() < complete < success.start() < exit_marker < clean_exit,
            f"{run['name']}: invalid launch/gameplay/automation/exit order")
    if run["renderer"] == "vulkan":
        require("LogVulkanRHI:" in content and "swapchain" in content.lower(),
                f"{run['name']}: missing real Vulkan swapchain evidence")
    return content


def verify_frame(item):
    path = verify_identity(item)
    with Image.open(path) as frame:
        frame.load()
        require(frame.format == "PNG" and frame.size == (1280, 720), f"Invalid rendered viewport: {path}")
        deviation = ImageStat.Stat(frame.convert("RGB")).stddev
        require(max(deviation) > 15, f"Blank/near-uniform rendered frame: {path}")
    return {**item, "size": [1280, 720], "rgb_stddev": deviation}


def verify_snapshot(before, after, label):
    require(before and before == after, f"{label} changed during acceptance")
    paths = [item["path"] for item in before]
    require(len(paths) == len(set(paths)), f"Duplicate {label} identities")
    for item in after:
        verify_identity(item)


def verify_tooling(report):
    verify_identity(report['runner'])
    expected = {'verify_d01_048.py', 'verify_d01_039.py', 'verify_d01_031.py',
                'verify_d01_033.py', 'run_d01_042.py', 'run_d01_039.py'}
    recorded = report['verification_tools']
    require(len(recorded) == len(expected) and
            {Path(item['path']).name for item in recorded} == expected,
            'Incomplete or duplicate acceptance-validator identities')
    for item in recorded:
        verify_identity(item)


def verify(report):
    require(report["task_id"] == "D01-48", "Wrong task identity")
    runs = verify_coverage(report["runs"])
    require(report["package"]["sha256"] == PACKAGE_SHA, "Package differs from completed D01-46/47")
    verify_identity(report["package"])
    require(report["package_source_commit"] == PACKAGE_COMMIT and report["package_source_diff"] == [],
            "Gameplay source does not match the recorded package revision")
    require(re.fullmatch(r"[0-9a-f]{40}", report["revision"]["head"]) and
            re.fullmatch(r"[0-9a-f]{40}", report["revision"]["head_tree"]), "Missing exact repository revision")
    verify_tooling(report)
    if report.get('execution_manifest'):
        verify_identity(report['execution_manifest'])
    verify_snapshot(report["source_before"], report["source_after"], "Source/assets")
    verify_snapshot(report["protected_before"], report["protected_after"], "Protected canonical metadata")
    require({Path(item["path"]).name for item in report["protected_before"]} ==
            {"03_BIELLA_CURRENT_STATE.md", "04_BIELLA_ACTIVE_TASK.md", "PRODUCTION.md"},
            "Incomplete protected canonical metadata identity")
    logs, summaries, package_reference = {}, {}, None
    for name, run in runs.items():
        extraction = Path(run["extraction"]).resolve()
        require(Path(run["runtime"]["cwd"]).resolve() == extraction, f"{name}: runtime did not launch outside Project")
        command = run["runtime"]["command"]
        launcher = extraction / "Linux/BiellaGames.sh"
        require(str(launcher) in command and not any("UnrealEditor" in arg for arg in command),
                f"{name}: intended packaged launcher was not used")
        require(f"-{run['renderer']}" in command, f"{name}: requested renderer missing from launch")
        require(f"-ExecCmds=Automation RunTests BiellaGames.Demo01.{run['suite']}; SoftQuit" in command,
                f"{name}: command does not select the recorded suite")
        verify_snapshot(run["package_members_before"], run["package_members_after"], f"{name} package members")
        member_map = {str(Path(item["path"]).resolve().relative_to(extraction)): (item["sha256"], item["bytes"])
                      for item in run["package_members_after"]}
        require(set(member_map) == {"Linux/BiellaGames.sh", "Linux/BiellaGames/Binaries/Linux/BiellaGames",
                                    "Linux/BiellaGames/Content/Paks/BiellaGames-Linux.pak"}, f"{name}: package members incomplete")
        if package_reference is None:
            package_reference = member_map
        require(member_map == package_reference, f"{name}: independently extracted package bytes differ")
        if run.get("engine_log"):
            verify_identity(run["engine_log"])
        logs[name] = verify_runtime(run)
        summaries[name] = {"result": "PASS", "suite": run["suite"], "renderer": run["renderer"],
                           "elapsed_wall_seconds": run["runtime"]["elapsed_seconds"]}
    telemetry = []
    for name in ("core-nullrhi", "core-vulkan"):
        command = runs[name]["runtime"]["command"]
        require(all(flag in command for flag in ("-UseFixedTimeStep", "-FPS=60", "-BiellaPlaytestSeed=1337")),
                "Core run must use recorded seed and fixed simulation step")
        telemetry.append(verify_identity(runs[name]["telemetry"]))
    core = verify_core(telemetry)
    require(all(run["seed"] == 1337 for run in core["runs"]), "Core telemetry seed mismatch")
    summaries["shared"]["gameplay"] = verify_shared(Path(runs["shared"]["runtime"]["log"]["path"]))
    summaries["pressure"]["gameplay"] = verify_pressure(Path(runs["pressure"]["runtime"]["log"]["path"]))
    navigation = re.findall(r"D01_029_TEST PASS phase=(\w+)", logs["navigation"])
    require(navigation == NAVIGATION_PHASES, "Navigation/collision acceptance phases incomplete or reordered")
    summaries["navigation"]["phases"] = navigation
    visual = logs["visual"]
    require(all(f"phase={phase}" in visual for phase in ("movement", "aim_lane", "role_presentation")),
            "Rendered camera, input or presentation checks missing")
    require("captures=6 viewport=1280x720" in visual and "restart_input=R failure=true source=rendered_runtime" in visual,
            "Rendered terminal/restart coverage incomplete")
    expected_visual = {f"{stage}_1280x720.png" for stage in VISUAL_STAGES}
    require({Path(item["path"]).name for item in runs["visual"]["captures"]} == expected_visual and
            len(runs["visual"]["captures"]) == 6, "Missing or duplicate staged visual captures")
    summaries["visual"]["frames"] = [verify_frame(item) for item in runs["visual"]["captures"]]
    feedback = logs["feedback"]
    phases = set(re.findall(r"D01_042_TEST PASS phase=(\w+)", feedback))
    require(FEEDBACK_PHASES <= phases, f"Feedback gameplay phases missing: {FEEDBACK_PHASES - phases}")
    particles = re.findall(r"D01_042_TEST PARTICLES cue=(\d+) count=(\d+) registered=true render_state=true", feedback)
    require(len(particles) == 4 and all(int(count) > 0 for _, count in particles), "Missing live rendered Niagara particles")
    require(len(re.findall(r"D01_042_TEST ATTR ([^\n]+)", feedback)) == 8 and "D01_042_TEST DENSE " in feedback,
            "Missing spatial particle/dense simulation evidence")
    expected_feedback = {f"{stage}.png" for stage in (*STAGES, "dense_combat")} | {f"{stage}.wav" for stage in STAGES}
    captures = runs["feedback"]["captures"]
    require({Path(item["path"]).name for item in captures} == expected_feedback and len(captures) == 11,
            "Missing or duplicate feedback frame/audio artifacts")
    command = runs["feedback"]["runtime"]["command"]
    require(all(flag in command for flag in ("-AudioMixer", "-DeterministicAudio", "-UseFixedTimeStep", "-FPS=60")) and
            "-nosound" not in command, "Feedback requires the live audio mixer")
    audio = [decode_audio(verify_identity(item)) for item in captures if Path(item["path"]).suffix == ".wav"]
    require(len({item["sha256"] for item in audio}) == 5, "Distinct gameplay cues produced identical audio")
    summaries["feedback"]["audio"] = audio
    summaries["feedback"]["frames"] = [verify_frame(item) for item in captures if Path(item["path"]).suffix == ".png"]
    return {"task_id": "D01-48", "result": "PASS", "package_sha256": PACKAGE_SHA,
            "core": core, "runs": summaries,
            "qualification": "Actual Linux Development package; seven clean processes; fixture conditions remain explicit"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(json.loads(args.report.read_text())), indent=2))
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"task_id": "D01-48", "result": "FAIL", "error": str(error)}, indent=2))
        raise SystemExit(1)
