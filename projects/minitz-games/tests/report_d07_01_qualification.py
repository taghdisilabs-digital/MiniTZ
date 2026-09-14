"""Readable D07 qualification report derived only from retained measured evidence."""
import json
import re
from pathlib import Path

from run_d01_039 import PROJECT, file_identity

ROOT = PROJECT / "Build/Qualification/D07-01"


def verify_support(summary):
    """Read back ancillary proof; a PASS string alone is never sufficient."""
    controls = summary["diagnostic_controls"]["report"]
    receipt = controls["receipt"]
    assert file_identity(Path(receipt["path"])) == receipt, "Diagnostic receipt changed"
    report = json.loads(Path(receipt["path"]).read_text())
    assert controls["result"] == report["result"] == "PASS" and controls["watchdog_expected_rejection"]
    assert report["tests_run"] >= 50 and report["failures"] == report["errors"] == 0
    for item in report["source"] + report["raw"]:
        assert file_identity(Path(item["path"])) == item, "Diagnostic input/raw bytes changed"
    visuals = summary["visual_observations"]["report"]
    assert visuals["observations"], "Visual readback missing"
    for item in visuals["observations"]:
        assert file_identity(Path(item["image"]["path"])) == item["image"], "Reviewed image changed"


def enrich(summary, manifest, reverified):
    rows = summary["scenarios"]
    summary["measurement_semantics"] = {
        "native_frames": "Native engine end-of-frame wall cadence, NOT display scanout or generated/interpolated frames. TSR is temporal upscaling/AA, not frame generation.",
        "thread_gpu": "Latest completed asynchronous engine counters; not a same-frame CPU/GPU pass decomposition. Zero/unavailable samples remain disclosed.",
        "hitches": "33.3/50/100 ms are reporting bins, not approved budgets. Every interval retained. Native warmup/capture/transition windows separate; D02 whole-probe distributions include screenshot stalls.",
        "simulation": "Variable-step native/D02/surface traces separate sim delta from wall delta. Fixed-step 60 Hz soak/audio are causal correctness probes, not native FPS measurements.",
        "resources": "Independent approximately 1 Hz /proc and NVIDIA process samples. CPU 100% means one logical core; GPU utilization is device-wide on a shared host. Process CPU/RSS cover UnrealEditor, not separate ShaderCompileWorker/Zen child totals. Editor, sampler and capture overhead affect the observation.",
        "latency": "Real injected movement/fire/camera input and resulting collision, damage, state, audio and rendered frames are verified; device-to-photon/audio latency is UNOBSERVABLE without timestamped external input/display instrumentation.",
    }
    summary["raw_reverified_against_current_runtime_inputs"] = reverified
    summary["verification_implementation"] = manifest["verification_implementation"]
    summary["reproduce"] = [
        "python3 tests/run_d07_01_qualification.py --scenario all  # executes missing scenarios; hash-checked passes reused",
        "python3 tests/run_d07_01_qualification.py --scenario verify  # exact raw bytes + current runtime identity + all scenario validators",
        "python3 tests/test_d07_01_qualification.py  # adversarial diagnostics, receipt integrity, metrics and watchdog controls",
        "python3 -m unittest discover -s tests -p 'test_d01_044*.py'  # predecessor native/resource verifier regression",
    ]
    summary["predecessor_scope"] = {
        "build": "Current D06 UE module reused; each run hashes the engine executable/build version, module/build receipts, project Source/Config/Content/Plugins. No gameplay/content/config change in D07.",
        "presentation": "D03 accepted surfaces, animation, audio and PSO implementation retained. Earlier whole-build evidence has changed material inputs, so it is historical context, not substituted for current D07 measurements. Current material/camera, audio, native feedback and traversal probes exercise the integrated build.",
        "pso_history": str(PROJECT / "Build/Presentation/pso-final-readback-01.json"),
        "pso_limit": "Earlier D03 cooked/seeded PSO evidence does not establish a current Windows shipping or first-install compilation pass. D07 clean/warm means private user/driver state with installed engine DDC retained; shader/PSO log counters are not equivalent to frame stalls.",
        "soak": "900-second, minimum 20-cycle current Vulkan soak compares causal event sequences to the exact qualified D01 deterministic reference, not volatile 03/04 state.",
    }
    summary["encountered_failed_attempts"] = []
    for path in sorted((ROOT / "runs").glob("*/*/validation.json")):
        report = json.loads(path.read_text())
        if report["result"] == "FAIL":
            summary["encountered_failed_attempts"].append({"receipt": file_identity(path), "error": report.get("error"),
                "scenario": report["scenario"], "current_result": rows.get(report["scenario"], {}).get("result"),
                "current_receipt": rows.get(report["scenario"], {}).get("evidence")})
    for key, filename in (("diagnostic_controls", "diagnostics/validation.json"), ("visual_observations", "visual-observations.json")):
        path = ROOT / filename
        if path.exists():
            summary[key] = {"identity": file_identity(path), "report": json.loads(path.read_text())}
    if reverified:
        verify_support(summary)
    summary["qualification_matrix"] = {
        "native_fps_frame_time_simulation_cpu_gpu_ram_vram": ["native720", "native1080"],
        "streaming_lod_culling_ground_collision_residency": ["streaming"],
        "dense_navigation_autonomous_combat_scaling": ["population4", "population12"],
        "chaos_destruction_hazard_light_weather_persistence": ["environment"],
        "vfx_audio_bursts_actual_gameplay": ["native720", "native1080", "environment", "audio"],
        "camera_temporal_surfaces_clean_warm_user_driver_cache": ["shadercold", "shaderwarm"],
        "repeated_process_launch_restart_reload_soak": ["native720", "native1080", "soak"],
        "diagnostics": "All scenario logs, process lifetime/PID/start identity, raw errors and watchdog evidence retained; synthetic failure controls explicitly separate from gameplay.",
    }
    summary["dominant_cost_observations"] = {}
    summary["startup_shader_pso_observations"] = {}
    for name, row in rows.items():
        log_path = Path(row["evidence"]).parent / "runtime.stdout.log"
        if not log_path.exists():
            continue
        log = log_path.read_text(errors="replace")
        counts = re.findall(r"Encountered (\d+) PSO creation hitches so far \((\d+) graphics, (\d+) compute\)\. (\d+) of them were precached", log)
        initialization = re.findall(r"\(Engine Initialization\) Total time: ([0-9.]+) seconds", log)
        summary["startup_shader_pso_observations"][name] = {
            "engine_initialization_seconds": [float(v) for v in initialization],
            "last_reported_pso_hitch_counter": dict(zip(("total", "graphics", "compute", "precached"), map(int, counts[-1]))) if counts else None,
            "scope": "Logged PSO creation-job hitch counter, not exact final PSO total or game frame stalls. No counter does not mean zero activity. Raw startup and shader/PSO lines retained.",
            "evidence": file_identity(log_path)}
    for name in ("native720", "native1080"):
        row = rows.get(name, {})
        counters = row.get("observations", {}).get("engine_timing_ms", {})
        if all(k in counters for k in ("game_ms", "render_ms", "rhi_ms", "gpu_ms")):
            dominant = max(("game_ms", "render_ms", "rhi_ms", "gpu_ms"), key=lambda k: counters[k]["p50"])
            summary["dominant_cost_observations"][name] = {
                "largest_median_counter": dominant, "counters_ms": counters,
                "interpretation": "Largest recorded steady-state counter, not proof of hardware saturation. Asynchronous engine counters, render submission/pacing and headless presentation require a pass-level profiler to establish cause. Shared device utilization cannot be assigned wholly to this game.",
                "evidence": row["evidence"]}
    risks = summary["unresolved_production_risks"]
    soak_resource = rows.get("soak", {}).get("resource_context", {})
    if "mid_to_late_rss_delta_mib" in soak_resource:
        risks.append({"id": "observed_soak_rss_growth",
            "finding": f"Soak process RSS rose {soak_resource['mid_to_late_rss_delta_mib']:.2f} MiB between the recorded middle and final {soak_resource['rss_window_samples']}-sample windows. This is observed growth, not proof of a leak or bounded long-term memory use.",
            "evidence": [soak_resource["raw"]]})
    for name in ("shadercold", "shaderwarm"):
        row = rows.get(name, {})
        frames = row.get("observations", {}).get("frame_time", {})
        if frames:
            risks.append({"id": name + "_worst_interval",
                "finding": f"{name} whole-probe worst interval is {frames['max_ms']:.2f} ms; {frames['hitches_gt_ms']['50']} intervals exceed the descriptive 50 ms bin. Capture-free settled windows do not erase these stalls. Frame-phase and shader logs locate observations, but do not establish a pass-level cause.",
                "evidence": [row["observations"]["raw"]]})
    warned = [name for name, row in rows.items() if any("unfreed allocations" in line
              for line in row.get("diagnostics", {}).get("warning_and_error_lines", []))]
    if warned:
        risks.append({"id": "vulkan_teardown_allocations",
            "finding": "Vulkan teardown reports unfreed allocations in the listed runs. Processes closed without an observed fatal/device loss, but these warnings remain unresolved and are not evidence of leak-free resource teardown.",
            "evidence": [str(Path(rows[name]["evidence"]).parent / "runtime.stdout.log") for name in warned]})
    for ident, finding, names in (
        ("restart_hitches", "Native repeated restart/transition hitches recur even with warm caches. See every worst frame, transition interval and per-cycle recurrence; no hitch is trimmed or converted to a target pass.", ["native720", "native1080"]),
        ("capture_and_streaming_hitches", "D02 all-probe stalls include screenshot capture and streamed-cell transitions. Causal load/unload/LOD/collision checks pass only on the measured route; whole-world seam freedom and hitch budgets are not established.", ["streaming", "population12", "environment"]),
        ("bounded_scalability", "Population 4 and 12 and two native resolutions establish observed workload scaling, not maximum supported population or approved low/medium/high hardware tiers. Native quality groups are 3; broader quality/hardware sweep remains unqualified.", ["population4", "population12", "native720", "native1080"]),
        ("content_complexity", "Current playable milestone uses sparse arena/street geometry and mannequin actors. These current-source probes do not establish final AAA content-density, art or full-game performance acceptance.", ["native1080", "streaming", "shaderwarm"]),
        ("clean_warm_scope", "Fresh user/driver versus reused cache replay retains installed DDC and OS page caches. Current cooked shipping startup/first-install shader compilation, PSO coverage and cross-driver caches remain unqualified.", ["shadercold", "shaderwarm"]),
        ("pso_replay_scope", "Both current editor surface probes use -logpso, which can reset user PSO recording/cache state at startup. Warm replay means preserved driver and derived shader state at launch, not preseeded or fully warm user PSO coverage. Exact before/after cache files and startup counters are retained.", ["shadercold", "shaderwarm"]),
        ("stability_scope", "Bounded 15-minute soak with deterministic restarts is not overnight, multi-day or fleet crash/leak qualification. RSS windows include caches and editor overhead; positive growth is retained and not called leak-free.", ["soak"]),
        ("headless_audio_display", "Vulkan Xvfb and SDL dummy audio verify rendered PNGs and recorded mix bytes, not physical monitor pacing, speaker output or interactive loading-screen handoff. Audio-mix uses the accepted wall-clock mixer with fixed-step gameplay; native/soak use deterministic audio. Known No Window and Vulkan bindless optional-optimization warnings remain disclosed.", ["audio", "native720"]),
    ):
        risks.append({"id": ident, "finding": finding, "evidence": [rows[n]["evidence"] for n in names if n in rows]})
    summary["publication"] = manifest["publication"]


def markdown(summary):
    lines = ["# D07-01 measured runtime qualification", "", f"Result: {summary['result']}", "",
             summary["scope"], "", summary["targets"], "",
             "PASS below means the measured scenario and evidence integrity passed, not target-hardware, shipping-platform or artistic acceptance.", "",
             "## Measured matrix", "",
             "| Scenario | Result | Frames | p50 / p95 / p99 / max (ms) | >50 ms | Peak process RSS / VRAM (MiB) |",
             "| --- | --- | ---: | --- | ---: | --- |"]
    for name, row in summary["scenarios"].items():
        f = row.get("observations", {}).get("frame_time", row.get("verification", {}).get("frame_time", {}).get("all_measurement", {}))
        metrics = " / ".join(f"{f[k]:.2f}" for k in ("p50_ms", "p95_ms", "p99_ms", "max_ms")) if f else "not sampled"
        r = row.get("resource_context", {})
        mem = " / ".join(f"{r[k]:.1f}" if r.get(k) is not None else "unavailable" for k in ("peak_rss_mib", "peak_process_vram_mib"))
        lines.append(f"| {name} | {row['result']} | {f.get('count', 'n/a')} | {metrics} | {f.get('hitches_gt_ms', {}).get('50', 'n/a')} | {mem} |")
    lines += ["", "Native rows exclude separately retained warmup/capture windows; other frame rows include probe/capture/transition cost. Soak/audio fixed-step clocks are not native FPS.", ""]
    for name in ("native720", "native1080"):
        row = summary["scenarios"].get(name, {})
        f = row.get("verification", {}).get("frame_time", {}).get("all_measurement")
        r = row.get("resources", {})
        if f and r:
            lines += [f"- {name}: {f['observed_fps']:.2f} measured native frames/s over {f['duration_seconds']:.3f} s; CPU mean {r['cpu_percent_one_core']['mean']:.1f}% (100%=one core), process RSS mean {r['rss_mib']['mean']:.1f} MiB, process VRAM mean {r['process_vram_mib']['mean']:.1f} MiB. Mean sample cost {r['sample_cost_seconds']['mean'] * 1000:.1f} ms per approximately 1 Hz resource query."]
    for name, item in summary["dominant_cost_observations"].items():
        c = item["counters_ms"]
        lines.append(f"- {name} median game / render / RHI / GPU counters: " + " / ".join(f"{c[k]['p50']:.2f}" for k in ("game_ms", "render_ms", "rhi_ms", "gpu_ms")) + " ms. " + item["interpretation"])
    soak = summary["scenarios"].get("soak", {}).get("verification", {})
    if soak:
        lines.append(f"- Soak: {soak['workload_wall_seconds']:.2f} wall seconds, {soak['completed_cycles']} causal cycles, {soak['total_restarts']} real restarts; maximum progress-heartbeat gap {soak['maximum_heartbeat_gap_seconds']:.2f} s. All autonomous dwell and actor/feedback lifetime assertions passed.")
    streaming = summary["scenarios"].get("streaming", {}).get("verification", {})
    if streaming:
        lines.append(f"- Streaming: {streaming['visible_cell_loads']} visible-cell loads and {streaming['visible_cell_unloads']} unloads over {streaming['wall_seconds']:.2f} s. Exact traversal, LOD, residency, navigation and state-restore assertions are retained in streaming.json and the frame/event traces.")
    for name in ("shadercold", "shaderwarm"):
        row = summary["scenarios"].get(name, {})
        costs = row.get("verification", {}).get("costs", {})
        if costs:
            lines.append(f"- {name}, capture-free settled windows: " + "; ".join(f"{phase} wall p50/p95 {v['wall_p50_ms']:.2f}/{v['wall_p95_ms']:.2f} ms, latest GPU p50 {v['gpu_p50_ms']:.2f} ms" for phase, v in costs.items()) + ". Whole-probe hitches remain in the matrix.")
        startup = summary["startup_shader_pso_observations"].get(name)
        if startup:
            lines.append(f"- {name} engine initialization: {startup['engine_initialization_seconds']} s; last reported PSO creation-job hitch counter: {startup['last_reported_pso_hitch_counter']}. This is not a frame-stall count or first-install compile qualification.")
    lines += ["", "## Evidence and interpretation", ""]
    for name, row in summary["scenarios"].items():
        path = Path(row["evidence"]).relative_to(ROOT)
        lines.append(f"- [{name} raw validation]({path.as_posix()}): exact command, runtime input/build/content digests, resource trace, completion diagnostics and raw artifact identities. Recomputed per-phase distributions and worst/recurring hitch rows are in summary.json.")
    lines += ["", *[f"- {key}: {value}" for key, value in summary["measurement_semantics"].items()], "",
              "## Retained failures and negative controls", ""]
    for item in summary["encountered_failed_attempts"]:
        lines.append(f"- {item['scenario']}: {item['error']} Original immutable receipt: {item['receipt']['path']}. Current result: {item['current_result']}.")
    lines.append("Diagnostic controls and visual observations, when present, are linked with exact digests in summary.json. Synthetic faults are never substituted for gameplay proof.")
    lines += ["", "## Unresolved production risks", ""]
    lines += [f"- {r['id']}: {r['finding']} Evidence: {r['evidence']}" for r in summary["unresolved_production_risks"]]
    lines += ["", "## Replay and durability", "", "```sh", *summary["reproduce"], "```", "", summary["publication"], ""]
    return "\n".join(lines)
