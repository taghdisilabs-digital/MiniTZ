#!/usr/bin/env python3
"""Capture and verify D01-40 in fresh rendered Unreal processes at two viewports.

Reuses the existing D01-39 process deadline and source identity helpers. Runtime
screenshots are GENERATED_DRAFT evidence; no shipping display target is selected.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
from datetime import datetime, timezone

from PIL import Image, ImageStat
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, identities, runtime_run, source_revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", choices=("1280x720", "1920x1080", "both"), default="both")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = PROJECT / "Build/Demo01/D01-040-runs" / stamp
    captures = Path("/root/biella/artifacts/games/D01-040") / stamp
    account = pwd.getpwnam("unreal")
    for folder in (evidence, captures):
        missing = []
        parent = folder
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        folder.mkdir(parents=True)
        for parent in missing:
            parent.chmod(0o755)
        os.chown(folder, account.pw_uid, account.pw_gid)
    report_path = evidence / "validation.json"
    protected = [PROJECT.parents[1] / "docs/project-state/03_BIELLA_CURRENT_STATE.md",
                 PROJECT.parents[1] / "docs/project-state/04_BIELLA_ACTIVE_TASK.md", PROJECT / "docs/PRODUCTION.md"]
    report = {"task_id": "D01-40", "result": "FAIL", "visual_status": "GENERATED_DRAFT",
              "revision": source_revision(), "identities_before": identities(DEFAULT_EDITOR),
              "material": file_identity(PROJECT / "Content/Materials/M_DemoReadability.uasset"),
              "authoring_script": file_identity(PROJECT / "Content/Python/build_demo_readability_material.py"),
              "lighting_script": file_identity(PROJECT / "Content/Python/configure_demo_readability_lighting.py"),
              "runner": file_identity(Path(__file__)),
              "protected_before": [file_identity(p) for p in protected], "runs": []}

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    save()
    print(f"D01-40 evidence: {report_path}", flush=True)
    try:
        for resolution in (("1280x720", "1920x1080") if args.resolution == "both" else (args.resolution,)):
            width, height = map(int, resolution.split("x"))
            output = captures / resolution
            output.mkdir(mode=0o755)
            os.chown(output, account.pw_uid, account.pw_gid)
            # A real Slate window under Xvfb exercises UI-inclusive capture
            # through the same window/viewport path used by interactive play.
            command = ["runuser", "-u", "unreal", "--", "xvfb-run", "-a", "-s", "-screen 0 2560x1440x24", str(DEFAULT_EDITOR),
                       str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaGameplayMap", "-game",
                       "-vulkan", "-NoVSync", "-windowed",
                       f"-ResX={width}", f"-ResY={height}", "-unattended", "-nosound", "-nosplash",
                       "-NoAsyncLoadingThread", "-stdout", "-FullStdOutLogOutput",
                       f"-AbsLog={evidence / (resolution + '.engine.log')}",
                       "-ExecCmds=Automation RunTests BiellaGames.Demo01.VisualReadability; SoftQuit",
                       f"-BiellaReadabilityOutput={output}"]
            run = runtime_run(command, evidence / (resolution + ".stdout.log"), 150)
            run.update({"resolution": [width, height], "captures": [], "result": "FAIL"})
            report["runs"].append(run)
            save()
            assert not run["timed_out"] and run["returncode"] == 0, "Unreal process failed or timed out"
            log = Path(run["log"]["path"]).read_text(errors="replace")
            assert re.search(r"Result=\{Success\}.*Name=\{VisualReadability\}", log), "Automation success missing"
            assert "D01_040_TEST COMPLETE" in log, "Scenario completion missing"
            assert not re.search(r"Result=\{Fail\}|Fatal error:|Assertion failed:|Ensure condition failed:|D01_040_TEST FAIL", log), "Runtime error"
            for capture in sorted(output.glob("*.png")):
                with Image.open(capture) as frame:
                    frame.load()
                    assert frame.size == (width, height), "Screenshot is not the requested viewport"
                    extrema = frame.convert("RGB").getextrema()
                    deviation = ImageStat.Stat(frame.convert("RGB")).stddev
                    assert max(deviation) > 15, "Blank/near-uniform frame"
                run["captures"].append({**file_identity(capture), "rgb_extrema": extrema, "rgb_stddev": deviation})
            assert len(run["captures"]) >= 6, "Missing staged visual captures"
            run["phases"] = re.findall(r"D01_040_TEST PASS phase=(\w+)", log)
            run["result"] = "PASS"
            save()
            print(f"{resolution}: PASS, {len(run['captures'])} decoded runtime PNGs", flush=True)
        report["identities_after"] = identities(DEFAULT_EDITOR)
        report["protected_after"] = [file_identity(p) for p in protected]
        assert report["identities_before"] == report["identities_after"], "Tested source/build changed during run"
        assert report["material"] == file_identity(PROJECT / "Content/Materials/M_DemoReadability.uasset"), "Material changed during run"
        assert report["protected_before"] == report["protected_after"], "Protected canonical metadata changed"
        report["result"] = "PASS"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
