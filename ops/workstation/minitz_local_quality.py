"""Measured local admission and task-owned evaluators; never task authority."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping


def _number(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def snapshot() -> dict[str, Any]:
    """Observe RAM, container limits, PSI and GPU while preserving UNKNOWN."""
    result: dict[str, Any] = {"schema": "minitz.local_pressure/v1", "authority": "OBSERVATION_ONLY",
        "observed_at_epoch": time.time(), "host_available_bytes": None,
        "cgroup_headroom_bytes": None, "memory_full_avg10": None, "memory_some_avg10": None,
        "gpu_free_mib": None, "gpu_utilization_percent": None}
    try:
        memory = {line.split(":")[0]: int(line.split()[1]) * 1024
                  for line in Path("/proc/meminfo").read_text().splitlines() if len(line.split()) >= 2}
        result.update(host_available_bytes=memory.get("MemAvailable"), host_total_bytes=memory.get("MemTotal"),
                      swap_used_bytes=memory.get("SwapTotal", 0) - memory.get("SwapFree", 0))
    except (OSError, ValueError):
        pass
    cg = Path("/sys/fs/cgroup")
    try:
        relative = next(line[3:] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::"))
        candidate = cg / relative.lstrip("/")
        if (candidate / "memory.current").is_file():
            cg = candidate
    except (OSError, StopIteration):
        pass
    current, maximum = _number(cg / "memory.current"), _number(cg / "memory.max")
    result.update(cgroup_current_bytes=current, cgroup_limit_bytes=maximum)
    if current is not None:
        result["cgroup_headroom_bytes"] = max(0, maximum - current) if maximum is not None else result["host_available_bytes"]
    for prefix in ("some", "full"):
        values = []
        for path in (Path("/proc/pressure/memory"), cg / "memory.pressure"):
            try:
                for line in path.read_text().splitlines():
                    if line.startswith(prefix + " "):
                        values.append(float(dict(item.split("=") for item in line.split()[1:])["avg10"]))
            except (OSError, ValueError, KeyError):
                pass
        result[f"memory_{prefix}_avg10"] = max(values) if values else None
    try:
        proc = subprocess.run(["nvidia-smi", "--query-gpu=uuid,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3, check=True)
        rows = list(csv.reader(proc.stdout.splitlines()))
        devices = [{"uuid": r[0].strip(), "total_mib": int(r[1]), "used_mib": int(r[2]),
                    "utilization_percent": int(r[3])} for r in rows]
        result["gpus"] = devices
        if devices:
            gpu = devices[0]
            result.update(gpu_uuid=gpu["uuid"], gpu_used_mib=gpu["used_mib"],
                gpu_free_mib=gpu["total_mib"] - gpu["used_mib"], gpu_utilization_percent=gpu["utilization_percent"])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return result


def admit(observation: Mapping[str, Any], policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Capacity policy is resource configuration, not a product hardware limit."""
    policy = dict(policy or {})
    limits = {"host_available_bytes": ("min", policy.get("ram_reserve_bytes", 4 * 1024**3)),
        "cgroup_headroom_bytes": ("min", policy.get("container_reserve_bytes", 1024**3)),
        "gpu_free_mib": ("min", policy.get("gpu_reserve_mib", 512)),
        "memory_full_avg10": ("max", policy.get("memory_full_limit", 5.0)),
        "memory_some_avg10": ("max", policy.get("memory_some_limit", 20.0))}
    reasons = []
    stamp = observation.get("observed_at_epoch")
    if stamp is not None and (not isinstance(stamp, (int, float)) or not -1 <= time.time() - stamp <= 30):
        reasons.append("STALE_OBSERVATION")
    for key, (direction, threshold) in limits.items():
        value = observation.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            reasons.append("UNKNOWN:" + key)
        elif (direction == "min" and value < threshold) or (direction == "max" and value > threshold):
            reasons.append("PRESSURE:" + key)
    return {"allowed": not reasons, "reasons": reasons, "observation": dict(observation), "policy": policy}


def exact_json_evaluator(expected: Mapping[str, Any]) -> Callable[[str], dict[str, Any]]:
    """An owner/task-defined oracle, not a model's own success claim."""
    target = json.dumps(dict(expected), sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(target.encode()).hexdigest()
    def evaluate(text: str) -> dict[str, Any]:
        try:
            value = json.loads(text)
            actual = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (ValueError, TypeError):
            actual = None
        passed = actual == target
        return {"evaluator": "minitz.exact-json.v1", "contract_sha256": digest,
                "verdict": "PASS" if passed else "FAIL", "score": 1.0 if passed else 0.0,
                "acceptance": "exact fields, values and JSON types; no extra claims"}
    return evaluate


def checked_cached_call(prompt: str, expected: Mapping[str, Any], identity: Mapping[str, Any],
                        cache_root: Path, execute: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """Reuse only content-checked results, serializing equivalent work across callers."""
    import fcntl
    import tempfile
    material = {"prompt": prompt, "expected": dict(expected), "identity": dict(identity),
                "evaluator_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    key = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    root = Path(cache_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (key + ".json")
    evaluator = exact_json_evaluator(expected)
    with (root / (key + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            cached = json.loads(path.read_text())
            text = cached["result"]["text"]
            if cached.get("key") == key and cached.get("output_sha256") == hashlib.sha256(text.encode()).hexdigest() and evaluator(text)["verdict"] == "PASS":
                return {**cached["result"], "quality": evaluator(text), "cache_hit": True, "cache_key": key}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        result = execute(prompt)
        verdict = evaluator(str(result.get("text", "")))
        if verdict["verdict"] != "PASS":
            raise ValueError("output failed task quality evaluator; result not cached")
        result = {**result, "quality": verdict, "cache_hit": False, "cache_key": key}
        record = {"schema": "minitz.quality_cache/v1", "authority": "CACHE_ONLY", "key": key,
                  "output_sha256": hashlib.sha256(result["text"].encode()).hexdigest(), "result": result}
        fd, name = tempfile.mkstemp(dir=root, prefix=key, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)
        return result
