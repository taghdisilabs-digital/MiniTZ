from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def observe_local_capacity() -> dict[str, Any]:
    """Read host/cgroup headroom without altering host configuration or GPU state."""
    result: dict[str, Any] = {"observed_at": datetime.now(timezone.utc).isoformat(), "ram_available_mib": None, "gpu_free_mib": None, "memory_pressure_full_avg10": None}
    try:
        mem = {line.split(':', 1)[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if len(line.split()) >= 2}
        result.update(ram_total_mib=mem['MemTotal'] / 1024, ram_available_mib=mem['MemAvailable'] / 1024)
        result['cpu_load_1m_per_core'] = os.getloadavg()[0] / max(1, os.cpu_count() or 1)
    except (OSError, ValueError, KeyError):
        pass
    cgroup = Path('/sys/fs/cgroup')
    try:
        for line in Path('/proc/self/cgroup').read_text().splitlines():
            if line.startswith('0::'):
                candidate = cgroup / line[3:].lstrip('/')
                if candidate.is_dir():
                    cgroup = candidate
        maximum = (cgroup / 'memory.max').read_text().strip()
        if maximum != 'max':
            headroom = max(0, int(maximum) - int((cgroup / 'memory.current').read_text())) / 1048576
            result['cgroup_memory_headroom_mib'] = headroom
            if result['ram_available_mib'] is not None:
                result['ram_available_mib'] = min(result['ram_available_mib'], headroom)
    except (OSError, ValueError):
        pass
    pressures: list[float] = []
    for path in (Path('/proc/pressure/memory'), cgroup / 'memory.pressure'):
        try:
            for line in path.read_text().splitlines():
                if line.startswith('full '):
                    pressures.append(float(dict(item.split('=', 1) for item in line.split()[1:])['avg10']))
        except (OSError, ValueError, KeyError):
            continue
    if pressures:
        result['memory_pressure_full_avg10'] = max(pressures)
    try:
        proc = subprocess.run(['nvidia-smi', '--query-gpu=memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3, check=False)
        rows = [line for line in proc.stdout.splitlines() if line.strip()]
        if proc.returncode == 0 and len(rows) == 1:
            total, used, utilization = (float(value.strip()) for value in rows[0].split(','))
            result.update(gpu_total_mib=total, gpu_used_mib=used, gpu_free_mib=max(0, total-used), gpu_utilization_percent=utilization)
        elif len(rows) > 1:
            result['gpu_observation_reason'] = 'RESOURCE_DEVICE_BINDING_REQUIRED'
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return result
