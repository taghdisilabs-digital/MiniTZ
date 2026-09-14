#!/usr/bin/env python3
"""D07-01: reproducible current-host qualification using existing real UE probes.

Run scenarios individually or all serially. Reuse passing raw evidence only
after its hashes and runtime inputs match. Failed attempts remain immutable.
The summary is a rebuildable report, never a production/task-state authority.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import pwd
import re
import shutil
import statistics
import sys

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_043 import REFERENCE
from run_d01_044 import host_identity, monitor, verify_resources
from run_d02_01 import identities, reject_material_fallbacks, runtime_has_task_error
from verify_d01_043 import verify_capture
from verify_d01_044 import BASELINE_LOG, frame_statistics, warnings, verify_run as verify_native
from verify_d02_01 import verify as verify_streaming
from verify_d02_02 import verify as verify_population
from verify_d02_04 import verify as verify_environment
from verify_d03_01_surfaces import verify as verify_surfaces
from verify_d03_01_audio_mix import measure as measure_mix, qualify_mix

ROOT = PROJECT / "Build/Qualification/D07-01"
LEDGER = Path("/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl")
SPECS = {
    "native720": {"test": "Demo01.NativePerformance", "width": 1280, "seconds": 120, "warmup": 10},
    "native1080": {"test": "Demo01.NativePerformance", "width": 1920, "seconds": 120, "warmup": 10},
    "streaming": {"test": "D02.WorldStreaming", "width": 1280},
    "population4": {"test": "D02.Population", "width": 1280, "count": 4},
    "population12": {"test": "D02.Population", "width": 1280, "count": 12},
    "environment": {"test": "D02.Environment", "width": 1280, "frame_cap": 60},
    "soak": {"test": "Demo01.StabilitySoak", "width": 1280, "seconds": 900, "cycles": 20},
    "shadercold": {"test": "D03.Surfaces", "width": 1280, "cache": "fresh_user_and_driver"},
    "shaderwarm": {"test": "D03.Surfaces", "width": 1280, "cache": "reuse_exact_cold_state"},
    "audio": {"test": "D03.AudioMix", "width": 1280},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def failure(kind, message, evidence):
    with LEDGER.open("a") as stream:
        stream.write(json.dumps({"task_id": "D07-01", "time": now(), "type": kind,
                                "status": "CONTINUE", "diagnostics": str(message)[:2000],
                                "evidence": str(evidence)}) + "\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def runtime_inputs():
    # Existing identity collector includes engine/module/build receipts and
    # editable Source/Config/Content/Plugins, but never volatile 03/04 state.
    return identities(DEFAULT_EDITOR)


def verification_implementation():
    # Capture the actual imported local verifier/monitor closure, not only the
    # entrypoint. These are evidence dependencies, never gameplay identity gates.
    from report_d07_01_qualification import enrich
    paths = {Path(module.__file__).resolve() for module in list(sys.modules.values())
             if getattr(module, "__file__", None) and Path(module.__file__).resolve().parent == PROJECT / "tests"
             and Path(module.__file__).suffix == ".py"}
    paths.update((PROJECT / "tests").glob("*d07_01*.py"))
    return [file_identity(p) for p in sorted(paths)]


def command(name, directory, cache_state=None):
    spec = SPECS[name]
    width = spec["width"]
    height = 720 if width == 1280 else 1080
    world = "BiellaGameplayMap" if spec["test"].startswith("Demo01") or name == "audio" else "BiellaOpenWorldMap"
    settings = [f"t.MaxFPS {spec.get('frame_cap', 60 if name == 'soak' else 0)}",
                "r.VSync 0", "r.ScreenPercentage 100", "r.DynamicRes.OperationMode 0"]
    extra = []
    if name.startswith("native"):
        settings += [f"sg.{quality}Quality 3" for quality in (
            "ViewDistance", "AntiAliasing", "Shadow", "GlobalIllumination", "Reflection",
            "PostProcess", "Texture", "Effects", "Foliage", "Shading", "Landscape")]
        extra += [f"-BiellaPerfOutput={directory}", f"-BiellaPerfCaptures={directory / 'captures'}",
                  f"-BiellaPerfSeconds={spec['seconds']}", f"-BiellaPerfWarmup={spec['warmup']}",
                  f"-BiellaTelemetry={directory / 'telemetry.jsonl'}", "-NoAsyncLoadingThread"]
    elif name == "soak":
        extra += ["-UseFixedTimeStep", "-FPS=60", "-NoAsyncLoadingThread",
                  "-BiellaPlaytestSeed=1337", f"-BiellaSoakSeconds={spec['seconds']}",
                  f"-BiellaSoakCycles={spec['cycles']}", f"-BiellaTelemetry={directory / 'telemetry.jsonl'}"]
    elif name == "streaming":
        extra += [f"-BiellaStreamingOutput={directory}"]
    elif name.startswith("population"):
        extra += [f"-BiellaPopulationOutput={directory}", f"-BiellaPopulationCount={spec['count']}"]
    elif name == "environment":
        extra += [f"-BiellaEnvironmentOutput={directory}"]
    elif name.startswith("shader"):
        settings += ["r.MotionBlurQuality 0", "r.AntiAliasingMethod 4"]
        extra += [f"-BiellaPresentationOutput={directory}", f"-UserDir={cache_state / 'user'}/",
                  "-logpso"]
    elif name == "audio":
        extra += [f"-BiellaAudioMixOutput={directory}", "-UseFixedTimeStep", "-FPS=60", "-NoAsyncLoadingThread"]
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    prefix = ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []
    environment = ["SDL_AUDIODRIVER=dummy"]
    if cache_state:
        # Private mount overlays preserve the live user's caches and Saved tree.
        # PID namespace is shared so the independent OS sampler retains true IDs.
        prefix = ["bwrap", "--die-with-parent", "--bind", "/", "/", "--dev-bind", "/dev", "/dev",
                  "--bind", str(cache_state / "home"), account.pw_dir,
                  "--bind", str(cache_state / "user/Saved"), str(PROJECT / "Saved"), "--"] + prefix
        environment += [f"XDG_CACHE_HOME={cache_state / 'xdg-cache'}",
                        f"XDG_CONFIG_HOME={cache_state / 'xdg-config'}",
                        f"__GL_SHADER_DISK_CACHE_PATH={cache_state / 'driver'}"]
    return prefix + ["env", *environment, "xvfb-run", "-a", "-s",
                     f"-screen 0 {width}x{height}x24", str(DEFAULT_EDITOR),
                     str(PROJECT / "BiellaGames.uproject"), f"/Game/Maps/{world}", "-game", "-vulkan",
                     "-NoVSync", "-windowed", f"-ResX={width}", f"-ResY={height}", "-unattended",
                     "-AudioMixer", *([] if name == "audio" else ["-DeterministicAudio"]), "-nosplash", "-stdout", "-FullStdOutLogOutput",
                     f"-AbsLog={directory / 'runtime.engine.log'}",
                     "-ExecCmds=" + ",".join(settings + [f"Automation RunTests BiellaGames.{spec['test']}; SoftQuit"])] + extra


NEW_WARNINGS = {
    "LogConsoleManager: Warning: Setting the console variable 'r.MotionBlurQuality' with 'SetByScalability' was ignored as it is lower priority than the previous 'SetByCode'. Value remains '0'": "Current render profile deliberately forces motion blur off; effective settings/captures remain measured.",
    "LogMoviePlayer: Warning: PassLoadingScreenWindowBackToGame failed.  No Window": "Headless loading-screen window handoff warning; playable viewport and decoded post-restart captures verified separately. Interactive loading handoff remains a risk.",
    "LogRHI: Warning: Dynamic Uniform Buffers are enabled, but they will not be used with Vulkan bindless.": "Vulkan bindless excludes this optional optimization; no fallback material or device loss permitted.",
    "LogRHI: Warning: Memory defrag is enabled, but it will not be used with Vulkan bindless.": "Vulkan bindless excludes defrag; resource pressure remains measured rather than assumed safe.",
}


def native_log(log, baseline):
    require("D01_044_TEST COMPLETE" in log, "Missing native performance completion marker")
    require(not runtime_has_task_error(log), "Fatal/assert/ensure/runtime error; inspect retained log")
    observed = warnings(log)
    unexpected = set(observed) - set(warnings(baseline)) - set(NEW_WARNINGS)
    require(not unexpected, f"Unclassified native warnings: {sorted(unexpected)}")
    return {"warnings": dict(observed), "current_diagnostic_classifications": NEW_WARNINGS,
            "baseline": file_identity(BASELINE_LOG), "scope": "Not warning-free; every new native signature classified explicitly."}


def diagnostics(directory, name):
    log = (directory / "runtime.stdout.log").read_text(errors="replace")
    test = SPECS[name]["test"].split(".")[-1]
    require("**** TEST COMPLETE. EXIT CODE: 0 ****" in log, "Missing Unreal completion")
    require(re.search(r"Result=\{Success\}.*Name=\{" + test + r"\}", log), "Missing scenario automation success")
    require(not runtime_has_task_error(log), "Fatal/assert/ensure/runtime error; inspect retained log")
    require(not re.search(r"VK_ERROR_DEVICE_LOST|D01_TELEMETRY_ERROR", log), "Device loss or telemetry failure")
    reject_material_fallbacks(log)
    return {"result": "PASS",
            "warning_and_error_lines": [line[:1000] for line in log.splitlines()
                                       if re.search(r"\b(?:Warning|Error):", line)],
            "shader_pso_lines": [line[:1000] for line in log.splitlines()
                                 if re.search(r"ShaderPipelineCache|PSO|shaders.*compil|compil.*shader", line, re.I)],
            "classification": "Exact known pre-world Dataflow startup diagnostic is disclosed; task-window errors are rejected."}


def resource_context(directory):
    samples = [json.loads(line) for line in (directory / "resources.jsonl").read_text().splitlines()]
    processes = [p for s in samples for p in s["unreal"]]
    require(len(processes) >= 5, "Missing independent process resource samples")
    require(len({(p["pid"], p["start_ticks"]) for p in processes}) == 1, "Resource process identity changed")
    measured = [s for s in samples if s["unreal"]]
    gaps = [b["clocks"]["1"] - a["clocks"]["1"] for a, b in zip(measured, measured[1:])]
    require(all(0 < gap < 3 for gap in gaps), "Resource capture gap/clock regression")
    cpu = [(b["unreal"][0]["cpu_ticks"] - a["unreal"][0]["cpu_ticks"]) / os.sysconf("SC_CLK_TCK") / gap * 100
           for a, b, gap in zip(measured, measured[1:], gaps)]
    require(all(math.isfinite(v) and v >= 0 for v in cpu), "Invalid CPU accounting")
    vram = [float(p["used_memory"].split()[0]) for s in samples for g in s["gpus"]
            for p in g["processes"] if any(p["pid"] == u["pid"] for u in s["unreal"])
            and re.match(r"^[0-9.]+ MiB$", p["used_memory"])]
    rss = [p["rss_kib"] / 1024 for p in processes]
    window = min(30, max(1, len(rss) // 10))
    mid = len(rss) // 2
    return {"scope": "UnrealEditor process lifetime incl. startup/teardown, not aggregate ShaderCompileWorker/Zen child usage; native runs also have exact frame-window alignment. Mid-to-late RSS windows are descriptive, not a leak test.",
            "samples": len(samples), "peak_rss_mib": max(p["rss_kib"] for p in processes) / 1024,
            "max_swap_mib": max(p["swap_kib"] for p in processes) / 1024,
            "mid_to_late_rss_delta_mib": statistics.mean(rss[-window:]) - statistics.mean(rss[mid:mid + window]),
            "rss_window_samples": window, "peak_process_vram_mib": max(vram) if vram else None,
            "whole_lifetime_cpu_percent_one_core": {"mean": statistics.mean(cpu), "max": max(cpu)},
            "resource_max_gap_seconds": max(gaps),
            "process_identities": sorted({(p["pid"], p["start_ticks"]) for p in processes}),
            "gpu_context": samples[len(samples) // 2]["gpus"],
            "raw": file_identity(directory / "resources.jsonl")}


def frame_observations(directory, name):
    path = directory / "frames.csv"
    if not path.exists():
        return {"scope": "No per-frame trace for this causal/soak probe; use native traces for variable-step FPS. Fixed-step soak/audio do not measure native simulation performance."}
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(rows, "Empty frame trace")
    require(all(math.isfinite(float(v)) for row in rows for k, v in row.items() if k not in ("stage", "phase")),
            "Nonfinite frame observation")
    key = "wall_delta_ms" if "wall_delta_ms" in rows[0] else "wall_ms"
    selected = [r for r in rows if r.get("stage", "measure") == "measure"]
    require(selected, "No measured frame intervals")
    require(all(float(r[key]) > 0 for r in selected), "Nonpositive frame observation")
    groups = {phase: [r for r in selected if r["phase"] == phase]
              for phase in sorted({r["phase"] for r in selected})}
    hitches = [r for r in selected if float(r[key]) > 50]
    numeric = ("pawn_count", "autonomous_pawns", "active_audio", "active_vfx", "active", "spawned",
               "visible_cells", "loaded_cells", "resident_bytes", "safety_holds", "view_yaw", "yaw")
    result = {"raw": file_identity(path), "frame_time": frame_statistics([float(r[key]) for r in selected]),
              "all_trace_stages": dict(Counter(r.get("stage", "scenario") for r in rows)),
              "phase_frame_time": {p: frame_statistics([float(r[key]) for r in group]) for p, group in groups.items()},
              "worst_frames": sorted(selected, key=lambda r: float(r[key]), reverse=True)[:20],
              "recurring_hitches_over_50ms": {"count": len(hitches), "by_phase": dict(Counter(r["phase"] for r in hitches)),
                                             "by_cycle": dict(Counter(r["cycle"] for r in hitches)) if "cycle" in rows[0] else None},
              "workload_ranges": {k: {"min": min(float(r[k]) for r in selected), "max": max(float(r[k]) for r in selected)}
                                  for k in numeric if k in rows[0]},
              "interpretation": "33.3/50/100 ms bins are descriptive, NOT acceptance budgets. Native measure excludes capture/warmup (reported separately); other all-scenario distributions retain screenshots/transitions."}
    if name == "streaming":
        result["first_interval_scope"] = "First interval starts at scenario construction, not a preceding captured frame; included in all-probe statistics and worst intervals. Adjacent-frame cadence is reported separately."
        result["adjacent_frame_time"] = frame_statistics([float(r[key]) for r in selected[1:]])
    sim_key = "sim_delta_ms" if "sim_delta_ms" in rows[0] else "sim_ms"
    if sim_key in rows[0]:
        result["simulation_delta_ms"] = frame_statistics([float(r[sim_key]) for r in selected])
        result["simulation_seconds_per_wall_second"] = sum(float(r[sim_key]) for r in selected) / sum(float(r[key]) for r in selected)
    for timing in ("game_ms", "render_ms", "rhi_ms", "gpu_ms", "game_wait_ms", "render_wait_ms", "swap_ms"):
        if timing in rows[0]:
            values = [float(r[timing]) for r in selected]
            result.setdefault("engine_timing_ms", {})[timing] = {"p50": statistics.median(values),
                "p99": float(__import__("numpy").percentile(values, 99)), "max": max(values),
                "zero_samples": sum(v == 0 for v in values)}
    return result


def validate(directory, name):
    spec = SPECS[name]
    result = {"diagnostics": diagnostics(directory, name), "resource_context": resource_context(directory),
              "observations": frame_observations(directory, name)}
    if name.startswith("native"):
        result["verification"] = verify_native(directory, spec["seconds"], spec["width"],
                                               720 if spec["width"] == 1280 else 1080, spec["warmup"], native_log)
        result["resources"] = verify_resources(directory, json.loads((directory / "perf.json").read_text()))
    elif name == "soak":
        result["verification"] = verify_capture(directory / "telemetry.jsonl", spec["seconds"], spec["cycles"], REFERENCE)
    elif name == "streaming":
        result["verification"] = verify_streaming(directory)
    elif name.startswith("population"):
        result["verification"] = verify_population(directory, spec["count"], "vulkan")
    elif name == "environment":
        result["verification"] = verify_environment(directory)
    elif name.startswith("shader"):
        result["verification"] = verify_surfaces(directory, 4, 100)
    elif name == "audio":
        result["verification"] = measure_mix(directory)
        qualify_mix(result["verification"])
        require(json.loads((directory / "result.json").read_text(encoding="utf-8-sig"))["success"], "Native audio assertions failed")
        log = (directory / "runtime.stdout.log").read_text()
        require(len(re.findall("D03_AUDIO_TRIGGER ", log)) == 3 and "D03_AUDIO_COMPLETE" in log, "Gameplay audio triggers missing")
    return result


def raw_identities(directory):
    return [file_identity(p) for p in sorted(directory.rglob("*"))
            if p.is_file() and not (p.name == "validation.json" or p.name.startswith("revalidation-"))]


def cache_identities(directory):
    return [file_identity(p) for p in sorted(directory.rglob("*")) if p.is_file()]


def retained_report(name, pointer, current):
    path = Path(pointer["validation"])
    require(pointer.get("validation_identity") == file_identity(path), f"{name}: validation receipt identity changed")
    report = json.loads(path.read_text())
    require(pointer["runtime_input_digest"] == report["runtime_input_digest"] == current, f"{name}: runtime inputs changed")
    require(report["result"] == pointer["result"], f"{name}: result pointer mismatch")
    require(report["spec"] == SPECS[name], f"{name}: scenario specification changed")
    require(report["raw"] == raw_identities(Path(pointer["directory"])), f"{name}: raw evidence bytes changed")
    if report["result"] == "PASS":
        run = report["runtime"]
        require(run["returncode"] == 0 and not run["watchdog_failure"] and
                run["log_finalization"]["closed"] and not run["survivors"] and
                len(run["unreal_process_identities"]) == 1, f"{name}: successful runtime lifetime missing")
    return report


def revalidate(manifest):
    """Repair a verifier-only failure from exact raw bytes, never overwrite its receipt."""
    for name, pointer in manifest["scenarios"].items():
        report = json.loads(Path(pointer["validation"]).read_text())
        require(report["runtime_input_digest"] == digest(runtime_inputs()), "Material inputs changed")
        directory = Path(pointer["directory"])
        require(report["raw"] == raw_identities(directory), "Raw evidence changed")
        run = report["runtime"]
        require(run["returncode"] == 0 and not run["watchdog_failure"] and
                run["log_finalization"]["closed"] and not run["survivors"] and
                len(run["unreal_process_identities"]) == 1, "Runtime failed; cannot reclassify")
        actual = validate(directory, name)
        if report["result"] == "PASS":
            continue
        report.update(actual)
        report["prior_validation"] = file_identity(Path(pointer["validation"]))
        report["prior_error"] = report.pop("error", None)
        report.update(result="PASS", revalidated_utc=now(), revalidator=file_identity(Path(__file__)))
        path = directory / ("revalidation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".json")
        write_json(path, report)
        pointer.update(result="PASS", validation=str(path), validation_identity=file_identity(path))
        write_json(ROOT / "manifest.json", manifest)
        print(f"REVALIDATED {name}: exact prior raw bytes; {path}", flush=True)


def execute(name, manifest):
    prior = manifest["scenarios"].get(name)
    inputs = runtime_inputs()
    if prior and prior["result"] == "PASS" and prior["runtime_input_digest"] == digest(inputs):
        retained_report(name, prior, digest(inputs))
        print(f"REUSED {name}: {prior['validation']}", flush=True)
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = ROOT / "runs" / name / stamp
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(directory, account)
    if name.startswith("native"):
        ensure_runtime_output(directory / "captures", account)
    cache_state = None
    cache_before = None
    if name == "shadercold":
        cache_state = Path("/mnt/biella-extra/biella-runtime/d07-01-shader") / stamp
        for sub in ("", "home", "user", "user/Saved", "xdg-cache", "xdg-config", "driver"):
            ensure_runtime_output(cache_state / sub, account)
        cache_before = cache_identities(cache_state)
        require(not cache_before, "Cold driver/user state is not empty")
    elif name == "shaderwarm":
        cold = manifest["scenarios"]["shadercold"]
        require(cold["result"] == "PASS", "Cold material path must complete before warm replay")
        cold_report = json.loads(Path(cold["validation"]).read_text())
        cache_state = Path(cold_report["cache_state"])
        cache_before = cache_identities(cache_state)
        require(cache_before == cold_report["cache_after"] and cache_before, "Cold-to-warm cache identity differs")
    report = {"task_id": "D07-01", "scenario": name, "result": "RUNNING", "created_utc": now(),
              "spec": SPECS[name], "source_revision": source_revision(),
              "runtime_inputs": inputs, "runtime_input_digest": digest(inputs),
              "runner": file_identity(Path(__file__)), "host": host_identity(),
              "command": command(name, directory, cache_state), "capture_status": "GENERATED_DRAFT"}
    if cache_state:
        report.update(cache_state=str(cache_state), cache_before=cache_before,
                      cache_scope="Private user/home/NVIDIA driver cache; engine installed DDC and OS page cache retained. Not cold storage or first install shader compilation.")
    path = directory / "validation.json"
    write_json(path, report)
    manifest["scenarios"][name] = {"result": "RUNNING", "directory": str(directory), "validation": str(path),
                                   "runtime_input_digest": digest(inputs)}
    write_json(ROOT / "manifest.json", manifest)
    print(f"RUN {name}: {path}", flush=True)
    try:
        report["runtime"] = monitor(report["command"], directory, 1200 if name == "soak" else 900)
        write_json(path, report)
        run = report["runtime"]
        require(run["returncode"] == 0 and not run["watchdog_failure"], "Process failure/deadline")
        require(len(run["unreal_process_identities"]) == 1 and not run["survivors"], "Process identity or exit mismatch")
        require(run["log_finalization"]["closed"], "Runtime log remains open")
        report.update(validate(directory, name))
        require(inputs == runtime_inputs(), "Runtime source/build/content changed during scenario")
        report["result"] = "PASS"
    except Exception as error:
        report["result"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
        failure("qualification.runtime_validation", report["error"], path)
    report["raw"] = raw_identities(directory)
    if cache_state:
        report["cache_after"] = cache_identities(cache_state)
    report["finished_utc"] = now()
    write_json(path, report)
    manifest["scenarios"][name].update(result=report["result"], validation_identity=file_identity(path))
    write_json(ROOT / "manifest.json", manifest)
    print(f"{report['result']} {name}: {report.get('error', '')}", flush=True)


def summarize(manifest, reverify=False):
    scenarios = {}
    current = digest(runtime_inputs())
    for name, pointer in manifest["scenarios"].items():
        report = retained_report(name, pointer, current)
        if report["result"] == "PASS":
            require(report["raw"] == raw_identities(Path(pointer["directory"])), f"{name}: raw evidence bytes changed")
            if reverify:
                report.update(validate(Path(pointer["directory"]), name))
        scenarios[name] = {k: report[k] for k in (
            "result", "spec", "error", "runtime", "verification", "resources", "resource_context", "diagnostics",
            "observations", "cache_scope", "cache_before", "cache_after", "cache_state")
            if k in report}
        scenarios[name]["evidence"] = pointer["validation"]
    complete = set(scenarios) == set(SPECS) and all(v["result"] == "PASS" for v in scenarios.values())
    summary = {"schema": "biella.d07_01.summary/v1", "task_id": "D07-01", "created_utc": now(),
               "result": "MEASUREMENTS_PASS" if complete else "CONTINUE",
               "scope": "Linux UE5.8.2 Development editor -game Vulkan/Xvfb on one shared L40S host. Native runs retain existing caches; shader cold/warm use private fresh then reused user/driver state, retaining installed DDC and OS caches.",
               "targets": "UNKNOWN: hardware/GPU/RAM/VRAM/resolution/native FPS/frame-time/hitch/input-latency budgets.",
               "scenarios": scenarios, "unresolved_production_risks": [
                   {"id": "targets", "evidence": str(PROJECT / "docs/TECHNICAL_DECISIONS.md"),
                    "finding": "No approved quantitative budgets; measurements cannot establish target-tier acceptance."},
                   {"id": "shipping", "evidence": str(ROOT / "manifest.json"),
                    "finding": "Windows PC x64 is accepted first platform; this Linux editor runtime does not qualify that package."},
                   {"id": "latency", "evidence": str(ROOT / "manifest.json"),
                    "finding": "Probes observe input-driven state/frames, but lack device-to-display latency measurement."},
                   {"id": "hardware", "evidence": str(ROOT / "manifest.json"),
                    "finding": "One shared L40S host; hardware/vendor spread and isolated machine repeatability unmeasured."},
               ]}
    from report_d07_01_qualification import enrich, markdown
    enrich(summary, manifest, reverify)
    write_json(ROOT / "summary.json", summary)
    (ROOT / "summary.md").write_text(markdown(summary))
    return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=[*SPECS, "all", "verify"], default="all")
    parser.add_argument("--revalidate", action="store_true", help="Replay exact retained raw after a validator repair")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {
        "schema": "biella.d07_01.manifest/v1", "task_id": "D07-01", "created_utc": now(),
        "source_revision": source_revision(), "runtime_inputs": runtime_inputs(),
        "authority": [file_identity(PROJECT / "docs/TECHNICAL_DECISIONS.md"),
                      file_identity(PROJECT / "docs/task-guides/D07-01.md")],
        "scenarios": {}, "scenario_specs": SPECS,
        "publication": "Auto Feeder owns GitHub/Drive replication from exact task commit; no remote success claimed."}
    require(manifest["task_id"] == "D07-01", "Wrong task manifest")
    manifest["scenario_specs"] = SPECS
    manifest["verification_implementation"] = verification_implementation()
    manifest["current_authority"] = [file_identity(PROJECT / "docs/TECHNICAL_DECISIONS.md"),
                                      file_identity(PROJECT / "docs/task-guides/D07-01.md")]
    manifest["evidence_dependencies"] = [file_identity(p) for p in (REFERENCE, BASELINE_LOG)]
    manifest["measurement_toolchain"] = {
        "python": {"version": sys.version, "executable": file_identity(Path(sys.executable).resolve())},
        "packages": {name: version(name) for name in ("numpy", "scipy", "Pillow")},
        "executables": [file_identity(Path(shutil.which(name)).resolve())
                        for name in ("bwrap", "xvfb-run", "Xvfb", "runuser", "nvidia-smi")],
        "scope": "Tool identities at final readback; exact command, engine/module/build, host/driver, live samples and runtime inputs retained per run."}
    if args.revalidate:
        revalidate(manifest)
    if args.scenario != "verify":
        for name in SPECS if args.scenario == "all" else [args.scenario]:
            execute(name, manifest)
            summarize(manifest)
    complete = summarize(manifest, reverify=args.scenario == "verify")
    if args.scenario == "verify":
        manifest["final_readback"] = {"utc": now(), "all_measurements_pass": complete,
            "runtime_input_digest": digest(runtime_inputs()), "summary": file_identity(ROOT / "summary.json"),
            "readable_summary": file_identity(ROOT / "summary.md")}
    write_json(path, manifest)
    print(json.dumps({"task_id": "D07-01", "all_measurements_pass": complete, "summary": str(ROOT / "summary.json")}))
    selected = list(SPECS) if args.scenario in ("all", "verify") else [args.scenario]
    return 0 if all(manifest["scenarios"].get(n, {}).get("result") == "PASS" for n in selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
