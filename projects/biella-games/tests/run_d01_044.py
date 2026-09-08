#!/usr/bin/env python3
"""Measure the current native Demo01 on this host; retain every attempt.

No target budget or shipping qualification is inferred from these measurements.
One Unreal process at a time. OS/NVML sampling is external at ~1 Hz; engine
frames are buffered by the test. Raw startup and teardown samples are retained.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import pwd
import re
import signal
import shutil
import statistics
import subprocess
import time
import xml.etree.ElementTree as ET

from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, identities, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_043 import PROTECTED, finalize_log, process_members
from verify_d01_039 import require


def read_numbers(path):
    return {parts[0].rstrip(":"): int(parts[1]) for line in Path(path).read_text().splitlines()
            if len(parts := line.split()) >= 2 and parts[1].isdigit()}


def process_sample(pid):
    root = Path(f"/proc/{pid}")
    raw = (root / "stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    status = read_numbers(root / "status")
    return {"pid": pid, "start_ticks": int(fields[19]), "cpu_ticks": int(fields[11]) + int(fields[12]),
            "minor_faults": int(fields[7]), "major_faults": int(fields[9]), "threads": int(fields[17]),
            "rss_kib": status["VmRSS"], "rss_peak_kib": status["VmHWM"],
            "swap_kib": status.get("VmSwap", 0), "virtual_bytes": int(fields[20]),
            "io": read_numbers(root / "io")}


def gpu_sample():
    # nvidia-smi -q includes graphics PIDs; compute-apps alone omits Vulkan.
    result = subprocess.run(["nvidia-smi", "-q", "-x"], capture_output=True, text=True, timeout=5, check=True)
    root = ET.fromstring(result.stdout)
    records = []
    for gpu in root.findall("gpu"):
        def value(path):
            raw = gpu.findtext(path, "N/A")
            match = re.match(r"^([0-9.]+)(?: |$)", raw)
            return float(match[1]) if match else None
        records.append({"name": gpu.findtext("product_name"), "uuid": gpu.findtext("uuid"),
                        "driver": root.findtext("driver_version"), "pstate": gpu.findtext("performance_state"),
                        "utilization_percent": value("utilization/gpu_util"),
                        "memory_utilization_percent": value("utilization/memory_util"),
                        "vram_used_mib": value("fb_memory_usage/used"), "vram_total_mib": value("fb_memory_usage/total"),
                        "power_w": value("gpu_power_readings/instant_power_draw"),
                        "temperature_c": value("temperature/gpu_temp"), "sm_clock_mhz": value("clocks/sm_clock"),
                        "processes": [{"pid": int(p.findtext("pid")), "type": p.findtext("type"),
                                       "name": p.findtext("process_name"), "used_memory": p.findtext("used_memory")}
                                      for p in gpu.findall("processes/process_info")]})
    return records


def host_identity():
    cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    limits = {}
    relative = Path("/proc/self/cgroup").read_text().strip().split("::")[-1].lstrip("/")
    for name in ("cpu.max", "memory.max", "cpuset.cpus.effective"):
        path = Path("/sys/fs/cgroup") / relative / name
        limits[name] = path.read_text().strip() if path.exists() else "UNAVAILABLE"
    return {"platform": platform.platform(), "cpu": cpu, "logical_cpus": os.cpu_count(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
            "memory_kib": read_numbers("/proc/meminfo"), "cgroup_limits": limits, "gpus": gpu_sample()}


def monitor(command, directory, timeout, process_names=("UnrealEditor",)):
    start = time.monotonic()
    failure, seen, last_sample = None, set(), 0
    log_path = directory / "runtime.stdout.log"
    with log_path.open("xb") as output, (directory / "resources.jsonl").open("x") as resource:
        process = subprocess.Popen(command, cwd=PROJECT, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                now = time.monotonic()
                if now - start > timeout:
                    failure = "overall process deadline"
                    break
                if now - last_sample >= 1:
                    members = process_members(process.pid)
                    samples = []
                    for member in members:
                        if member["name"] in process_names:
                            try:
                                samples.append(process_sample(member["pid"]))
                                seen.add((member["pid"], member["start_ticks"]))
                            except (OSError, KeyError):
                                pass  # Process can exit between /proc reads; next sample/exit records it.
                    sample = {"elapsed_seconds": now - start,
                              "clocks": {str(i): time.clock_gettime(i) for i in (0, 1, 4, 6)},
                              "unreal": samples, "host_memory_kib": read_numbers("/proc/meminfo"),
                              "host_cpu_ticks": [int(v) for v in Path("/proc/stat").read_text().splitlines()[0].split()[1:]],
                              "gpus": gpu_sample()}
                    sample["sampling_cost_seconds"] = time.monotonic() - now
                    resource.write(json.dumps(sample) + "\n")
                    resource.flush()
                    last_sample = now
                time.sleep(.1)
            if failure:
                write_json(directory / "watchdog.json", {"reason": failure, "members": process_members(process.pid)})
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait(timeout=15)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    survivors = process_members(process.pid)
    if survivors:
        os.killpg(process.pid, signal.SIGKILL)
    finalization = finalize_log(log_path)
    return {"returncode": returncode, "watchdog_failure": failure, "elapsed_seconds": time.monotonic() - start,
            "unreal_process_identities": [{"pid": pid, "start_ticks": ticks} for pid, ticks in sorted(seen)],
            "survivors": survivors, "log_finalization": finalization}


def task_identities():
    paths = list((PROJECT / "Content").rglob("*.uasset"))
    paths += [PROJECT / "tests" / name for name in ("run_d01_044.py", "verify_d01_044.py", "test_d01_044.py", "test_d01_044_resources.py",
                                                    "run_d01_043.py", "run_d01_042.py")]
    return identities(DEFAULT_EDITOR) + [file_identity(p) for p in sorted(paths)]


def verify_resources(directory, perf):
    """Join independent OS samples to Unreal's exact selected Linux clock."""
    with (directory / "frames.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    frames = [row for row in rows if row["stage"] == "measure"]
    require(bool(frames), "No measured frames for resource alignment")
    first = float(perf["platform_seconds_start"]) + float(frames[0]["wall_seconds"]) - float(frames[0]["wall_delta_ms"]) / 1000
    last = float(perf["platform_seconds_start"]) + float(frames[-1]["wall_seconds"])
    clock_id = str(perf["settings"]["platform_clock_id"])
    samples = [json.loads(line) for line in (directory / "resources.jsonl").read_text().splitlines()]
    selected = [s for s in samples if first <= s["clocks"][clock_id] <= last]
    require(len(selected) >= max(5, (last - first) * .7), "Insufficient OS samples in native measurement window")
    times = [s["clocks"][clock_id] for s in selected]
    require(all(0 < b - a < 3 for a, b in zip(times, times[1:])), "OS resource sampling stalled or clock regressed")
    require(times[0] - first < 3 and last - times[-1] < 3, "OS resource coverage misses measurement boundaries")
    processes = []
    gpus = []
    vram = []
    other_gpu_processes = set()
    for sample in selected:
        matches = [p for p in sample["unreal"] if p["pid"] == perf["process_id"]]
        require(len(matches) == 1, "Resource sample lost exact Unreal PID")
        processes.append(matches[0])
        require(len(sample["gpus"]) == 1, "Measurement currently requires exactly one observed GPU")
        gpu = sample["gpus"][0]
        gpus.append(gpu)
        matches = [p for p in gpu["processes"] if p["pid"] == perf["process_id"]]
        require(len(matches) == 1, "GPU resource sample does not contain the measured graphics PID")
        require("G" in matches[0]["type"], "Measured Unreal PID is not a GPU graphics process")
        match = re.fullmatch(r"([0-9]+) MiB", matches[0]["used_memory"] or "")
        require(match is not None, "Per-process VRAM residency unavailable")
        vram.append(float(match[1]))
        other_gpu_processes.update((p["pid"], p["type"], p["name"]) for p in gpu["processes"] if p["pid"] != perf["process_id"])
    require(len({p["start_ticks"] for p in processes}) == 1, "Unreal PID reused during resource capture")
    require(len({g["uuid"] for g in gpus}) == 1, "GPU identity changed")
    ticks = os.sysconf("SC_CLK_TCK")
    cpu = [(b["cpu_ticks"] - a["cpu_ticks"]) / ticks / (tb - ta) * 100
           for a, b, ta, tb in zip(processes, processes[1:], times, times[1:])]
    require(all(value >= 0 for value in cpu), "CPU accounting regressed")
    def distribution(values):
        require(values and all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in values),
                "Missing/invalid resource value")
        return {"min": min(values), "mean": statistics.mean(values), "max": max(values)}
    rss = [p["rss_kib"] / 1024 for p in processes]
    n = min(10, len(rss) // 2)
    faults = {name: processes[-1][name] - processes[0][name] for name in ("minor_faults", "major_faults")}
    io = {name: processes[-1]["io"][name] - processes[0]["io"][name]
          for name in ("read_bytes", "write_bytes", "syscr", "syscw")}
    require(all(v >= 0 for v in [*faults.values(), *io.values()]), "Process accounting counters regressed")
    host_busy, host_steal = [], []
    for a, b in zip(selected, selected[1:]):
        delta = [y - x for x, y in zip(a["host_cpu_ticks"][:8], b["host_cpu_ticks"][:8])]
        require(sum(delta) > 0, "Host CPU accounting stalled")
        host_busy.append(100 * (sum(delta) - delta[3] - delta[4]) / sum(delta))
        host_steal.append(100 * delta[7] / sum(delta))
    return {"sampling": "Independent /proc and nvidia-smi graphics-process samples (~1 Hz); CPU 100% = one logical core.",
            "clock_id": int(clock_id), "measurement_clock_start": first, "measurement_clock_end": last,
            "samples": len(selected), "pid": perf["process_id"], "start_ticks": processes[0]["start_ticks"],
            "gpu_uuid": gpus[0]["uuid"], "sample_cost_seconds": distribution([s["sampling_cost_seconds"] for s in selected]),
            "cpu_percent_one_core": distribution(cpu), "rss_mib": distribution(rss),
            "rss_hwm_mib": max(p["rss_peak_kib"] for p in processes) / 1024,
            "rss_first_window_mean_mib": statistics.mean(rss[:n]), "rss_last_window_mean_mib": statistics.mean(rss[-n:]),
            "rss_window_delta_mib": statistics.mean(rss[-n:]) - statistics.mean(rss[:n]),
            "window_sample_count": n, "process_vram_mib": distribution(vram),
            "device_vram_mib": distribution([g["vram_used_mib"] for g in gpus]),
            "gpu_utilization_percent": distribution([g["utilization_percent"] for g in gpus]),
            "gpu_memory_utilization_percent": distribution([g["memory_utilization_percent"] for g in gpus]),
            "gpu_power_w": distribution([g["power_w"] for g in gpus]),
            "gpu_temperature_c": distribution([g["temperature_c"] for g in gpus]),
            "gpu_sm_clock_mhz": distribution([g["sm_clock_mhz"] for g in gpus]),
            "host_cpu_busy_percent_all_cores": distribution(host_busy),
            "host_cpu_steal_percent_all_cores": distribution(host_steal),
            "threads": distribution([p["threads"] for p in processes]), "fault_deltas": faults, "io_deltas": io,
            "swap_mib": distribution([p["swap_kib"] / 1024 for p in processes]),
            "host_available_memory_mib": distribution([s["host_memory_kib"]["MemAvailable"] / 1024 for s in selected]),
            "other_gpu_processes": [{"pid": pid, "type": kind, "name": name} for pid, kind, name in sorted(other_gpu_processes)],
            "memory_interpretation": "Bounded observed residency/windows include caches and editor overhead; no leak-free claim or target budget."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--warmup", type=float, default=10)
    parser.add_argument("--width", type=int, choices=(1280, 1920), default=1280)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 600 or not 3 <= args.warmup <= 60:
        parser.error("seconds must be 10..600 and warmup 3..60")
    height = {1280: 720, 1920: 1080}[args.width]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = PROJECT / "Build/Demo01/D01-044-runs" / f"{stamp}-{args.width}x{height}"
    captures = Path("/root/biella/artifacts/games/D01-044") / directory.name
    account = pwd.getpwnam("unreal") if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    ensure_runtime_output(directory, account)
    ensure_runtime_output(captures, account)
    report = {"task_id": "D01-44", "result": "FAIL", "created_utc": stamp,
              "mode": "MEASUREMENT" if args.seconds >= 120 else "SMOKE_ONLY",
              "revision": source_revision(), "identities_before": task_identities(),
              "protected_before": [file_identity(p) for p in PROTECTED], "host": host_identity(),
              "scope": "Native Linux UnrealEditor -game Development, Vulkan, Xvfb; no shipping or target-tier acceptance.",
              "capture_status": "GENERATED_DRAFT", "captures_directory": str(captures)}
    report_path = directory / "validation.json"
    write_json(report_path, report)
    print(f"D01-44 evidence: {report_path}", flush=True)
    try:
        prefix = ["runuser", "-u", account.pw_name, "--"] if os.geteuid() == 0 else []
        settings = ["t.MaxFPS 0", "r.VSync 0", "r.ScreenPercentage 100", "r.DynamicRes.OperationMode 0"]
        settings += [f"sg.{name}Quality 3" for name in ("ViewDistance", "AntiAliasing", "Shadow", "GlobalIllumination",
                                                       "Reflection", "PostProcess", "Texture", "Effects", "Foliage", "Shading", "Landscape")]
        command = prefix + ["xvfb-run", "-a", "-s", f"-screen 0 {args.width}x{height}x24", str(DEFAULT_EDITOR),
                           str(PROJECT / "BiellaGames.uproject"), "/Game/Maps/BiellaGameplayMap", "-game", "-vulkan",
                           "-NoVSync", "-windowed", f"-ResX={args.width}", f"-ResY={height}", "-unattended",
                           "-AudioMixer", "-DeterministicAudio", "-nosplash", "-NoAsyncLoadingThread", "-stdout",
                           "-FullStdOutLogOutput", f"-AbsLog={directory / 'runtime.engine.log'}",
                           "-ExecCmds=" + ",".join(settings + ["Automation RunTests BiellaGames.Demo01.NativePerformance; SoftQuit"]),
                           f"-BiellaTelemetry={directory / 'telemetry.jsonl'}", f"-BiellaPerfOutput={directory}",
                           f"-BiellaPerfCaptures={captures}", f"-BiellaPerfSeconds={args.seconds}", f"-BiellaPerfWarmup={args.warmup}"]
        report["command"] = command
        write_json(report_path, report)
        report["runtime"] = monitor(command, directory, args.seconds + args.warmup + 180)
        write_json(report_path, report)
        run = report["runtime"]
        require(run["returncode"] == 0 and not run["watchdog_failure"], "Unreal process failed/deadline")
        require(len(run["unreal_process_identities"]) == 1 and not run["survivors"], "Unreal identity/exit mismatch")
        require(run["log_finalization"]["closed"], "Runtime log still has inherited writers")
        from verify_d01_044 import verify_run
        report["verification"] = verify_run(directory, args.seconds, args.width, height, args.warmup)
        report["resources"] = verify_resources(directory, json.loads((directory / "perf.json").read_text()))
        copies = directory / "captures"
        copies.mkdir()
        for capture in captures.glob("*.png"):
            shutil.copy2(capture, copies / capture.name)
        report["capture_copies"] = [file_identity(p) for p in sorted(copies.glob("*.png"))]
        report["identities_after"] = task_identities()
        report["protected_after"] = [file_identity(p) for p in PROTECTED]
        require(report["identities_before"] == report["identities_after"], "Tested bytes changed during run")
        require(report["protected_before"] == report["protected_after"], "Protected metadata changed")
        report["evidence"] = [file_identity(p) for p in sorted(directory.iterdir()) if p.is_file() and p != report_path]
        report["result"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    finally:
        write_json(report_path, report)
    print(json.dumps({"result": report["result"], "mode": report["mode"], "validation": str(report_path),
                      "error": report.get("error")}, indent=2), flush=True)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
