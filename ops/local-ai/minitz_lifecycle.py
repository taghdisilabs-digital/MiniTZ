#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import minitz_task_program as task_program

MODEL_SERVICES = (
    "minitz-ollama.service",
    "minitz-qwen-residency.service",
)
CONTROL_SERVICES = (
    "project-sandbox-broker.service",
    "minitz-control-gateway.service",
)
WRITER_SERVICES = ("minitz-production.service",)
ON_START_ORDER = (*MODEL_SERVICES, *CONTROL_SERVICES, *WRITER_SERVICES)
OFF_SERVICES = (
    "minitz-production.service",
    "minitz-control-gateway.service",
    "project-sandbox-broker.service",
    "minitz-qwen-residency.service",
    "minitz-ollama.service",
)
ON_TARGET = "minitz-on.target"
DEFAULT_REPO_ROOT = Path(os.environ.get("MINITZ_REPO_ROOT", "/root/attached-storage/minitz-os-sandbox/workspace/repo"))
DEFAULT_TASK_PROGRAM = Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json"))
DEFAULT_RUNTIME = Path(os.environ.get("MINITZ_RUNTIME_ROOT", "/root/attached-storage/minitz-os-sandbox/state/production")) / "runtime.json"
DEFAULT_RECEIPT = Path(os.environ.get(
    "MINITZ_READINESS_RECEIPT",
    "/root/attached-storage/minitz-os-sandbox/state/qualification/READY_TO_ON.json",
))
ATTACHMENT_PATHS = (
    Path("/root/attached-storage/minitz-os-sandbox/state/production/memory/compacted-memory.json"),
    Path("/root/attached-storage/minitz-os-sandbox/state/production/memory/current-task.json"),
)
TASK_VALIDATION_TESTS = (
    "tests/test_execution_policy_law.py",
    "tests/test_gpu_residency_policy.py",
    "tests/test_minitz_lifecycle.py",
    "tests/test_minitz_task_program_evolution.py",
    "tests/test_booster_sync.py",
    "tests/test_resource_quality_pressure.py",
    "tests/test_production_source_sync.py",
    "tests/test_minitz_progressive_truth.py",
    "tests/test_minitz_final_closure.py",
    "tests/test_minitz_os_sandbox.py",
    "tests/test_never_ever_control_boundaries.py",
    "tests/test_minitz_data_residency.py",
    "tests/test_security_privacy.py",
    "tests/test_task_guidance.py",
    "tests/test_task_guidance_runner.py",
    "tests/test_codex_account_pool.py",
)


class LifecycleError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _assert_current_source_root(repo: Path) -> None:
    resolved = Path(repo).expanduser().resolve()
    try:
        resolved.relative_to(Path("/mnt").resolve())
    except ValueError:
        return
    raise LifecycleError(
        f"historical /mnt source is evidence-only and cannot be current MiniTZ authority: {resolved}"
    )


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], text=True, stderr=subprocess.STDOUT, timeout=30
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise LifecycleError((exc.output or "git command failed")[-2000:]) from exc


def _unit_active(unit: str) -> bool:
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", unit],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def _systemctl(action: str, unit: str) -> None:
    proc = subprocess.run(
        ["systemctl", action, unit], text=True, capture_output=True, check=False,
    )
    if proc.returncode == 0:
        return
    detail = (proc.stderr or proc.stdout or f"systemctl {action} {unit} failed").strip()
    lowered = detail.lower()
    if action in {"stop", "disable"} and any(
        marker in lowered for marker in ("not loaded", "not found", "does not exist", "no such file")
    ):
        return
    raise LifecycleError(detail)


def _failed_systemd_units() -> list[str]:
    proc = subprocess.run(
        ["systemctl", "--failed", "--no-legend", "--plain"],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode not in (0, 1):
        raise LifecycleError((proc.stderr or proc.stdout or "systemctl --failed failed").strip())
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _blocking_failed_units() -> list[str]:
    """Model-resource failures are observable degradation, not production-stop authority."""
    return [
        row for row in _failed_systemd_units()
        if not any(unit in row for unit in MODEL_SERVICES)
    ]


def _qualification_command(args: Sequence[str], cwd: Path) -> None:
    proc = subprocess.run(list(args), cwd=str(cwd), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stdout + "\n" + proc.stderr).strip()[-4000:]
        raise LifecycleError(f"qualification command failed ({' '.join(args)}): {detail}")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _authorize_command(command: str, task_program_path: Path) -> None:
    operation_kind = {
        "qualify": "DERIVED_STATE_MUTATION",
        "sleep": "LIFECYCLE_MUTATION",
        "off": "LIFECYCLE_MUTATION",
        "on": "LIFECYCLE_MUTATION",
    }.get(str(command))
    if operation_kind is None:
        return
    try:
        program = task_program.load(Path(task_program_path))
        task_program.authorize_operation(
            task_program.owner_action_mode(program), operation_kind,
        )
    except ValueError as exc:
        raise LifecycleError(str(exc)) from exc


def qualify(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    task_program_path: Path = DEFAULT_TASK_PROGRAM,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    _assert_current_source_root(repo)
    program = Path(task_program_path).resolve()
    receipt = Path(receipt_path).resolve()
    if not program.is_file():
        raise LifecycleError(f"MiniTZ Task Program is unavailable: {program}")
    qualified_while_off = not _unit_active(ON_TARGET)
    _qualification_command(("git", "diff", "--check"), repo)
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise LifecycleError("workspace is dirty; ON qualification requires a clean accepted source boundary")
    _qualification_command((sys.executable, "-m", "mypy", "--strict", "src"), repo)
    _qualification_command(
        (sys.executable, "-m", "pytest", "-q", "--disable-warnings", *TASK_VALIDATION_TESTS), repo
    )
    _qualification_command(("bash", "tests/local_ai_runtime_smoke_test.sh"), repo)
    _qualification_command(("bash", "tests/workstation_supervisor_contract_test.sh"), repo)
    _qualification_command(("bash", "tests/control_gateway_service_contract_test.sh"), repo)
    failed = _blocking_failed_units()
    if failed:
        raise LifecycleError("failed systemd units remain: " + "; ".join(failed[:10]))
    payload = {
        "schema": "minitz.on_readiness/v1",
        "status": "READY",
        "qualified_at": _now(),
        "qualified_while_off": qualified_while_off,
        "repo_root": str(repo),
        "repo_head": _git(repo, "rev-parse", "HEAD"),
        "repo_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "task_program_path": str(program),
        "task_program_sha256": _sha256(program),
        "validation": {
            "git_diff_check": "PASS",
            "mypy_strict_src": "PASS",
            "pytest_task_specific": "PASS",
            "local_ai_runtime_smoke": "PASS",
            "workstation_supervisor_contract": "PASS",
            "control_gateway_contract": "PASS",
            "failed_systemd_units": 0,
        },
    }
    _atomic_json(receipt, payload)
    return payload


def assert_ready(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    task_program_path: Path = DEFAULT_TASK_PROGRAM,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    _assert_current_source_root(repo)
    program = Path(task_program_path).resolve()
    receipt = Path(receipt_path).resolve()
    if not receipt.is_file():
        raise LifecycleError("MiniTZ ON readiness receipt is missing")
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("MiniTZ ON readiness receipt is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "minitz.on_readiness/v1":
        raise LifecycleError("MiniTZ ON readiness receipt schema is invalid")
    if payload.get("status") != "READY" or not isinstance(payload.get("qualified_while_off"), bool):
        raise LifecycleError("MiniTZ ON readiness receipt is not a valid READY receipt")
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise LifecycleError("workspace is dirty after ON qualification")
    head = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    if payload.get("repo_head") != head or payload.get("repo_tree") != tree:
        raise LifecycleError("source changed after ON qualification")
    if not program.is_file():
        raise LifecycleError("MiniTZ Task Program is unavailable")
    if payload.get("task_program_sha256") != _sha256(program):
        raise LifecycleError("MiniTZ Task Program changed after ON qualification")
    failed = _blocking_failed_units()
    if failed:
        raise LifecycleError("failed systemd units remain: " + "; ".join(failed[:10]))
    return {"status": "READY", "repo_head": head, "repo_tree": tree, "receipt": str(receipt)}


def assert_startup_attached(*, task_program_path: Path = DEFAULT_TASK_PROGRAM) -> dict[str, Any]:
    program = Path(task_program_path).resolve()
    if not program.is_file():
        raise LifecycleError(f"MiniTZ Task Program is unavailable: {program}")
    try:
        payload = json.loads(program.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("MiniTZ Task Program is unreadable") from exc
    if not isinstance(payload, dict):
        raise LifecycleError("MiniTZ Task Program root must be an object")
    missing = [str(path) for path in ATTACHMENT_PATHS if not path.is_file()]
    if missing:
        raise LifecycleError("MiniTZ startup attachments are missing: " + ", ".join(missing))
    inactive = [unit for unit in CONTROL_SERVICES if not _unit_active(unit)]
    if inactive:
        raise LifecycleError("MiniTZ startup prerequisites are inactive: " + ", ".join(inactive))
    model_resources = {unit: ("ACTIVE" if _unit_active(unit) else "UNAVAILABLE") for unit in MODEL_SERVICES}
    return {
        "status": "ATTACHED",
        "task_program": str(program),
        "task_program_sha256": _sha256(program),
        "attachments": [str(path) for path in ATTACHMENT_PATHS],
        "prerequisite_services": [*CONTROL_SERVICES],
        "model_resources": model_resources,
    }


def sleep() -> dict[str, Any]:
    _systemctl("stop", ON_TARGET)
    _systemctl("disable", ON_TARGET)
    for service in WRITER_SERVICES:
        _systemctl("stop", service)
        _systemctl("disable", service)
    return {"state": "SLEEP", "warm_model_services": list(MODEL_SERVICES)}


def off() -> dict[str, Any]:
    _systemctl("stop", ON_TARGET)
    _systemctl("disable", ON_TARGET)
    for service in OFF_SERVICES:
        _systemctl("stop", service)
        _systemctl("disable", service)
    return {"state": "OFF"}


def _qwen_resident() -> bool:
    url = os.environ.get("MINITZ_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/ps"
    model = os.environ.get("MINITZ_QWEN_MODEL", "qwen3-coder-next:minitz")
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read())
    except Exception:
        return False
    return any(
        (row.get("name") == model or row.get("model") == model) and int(row.get("size_vram") or 0) > 0
        for row in payload.get("models", []) if isinstance(row, dict)
    )


def _control_gateway_reachable() -> bool:
    url = os.environ.get("MINITZ_CONTROL_SESSION_URL", "http://127.0.0.1:8787/v1/control/session")
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read())
        return isinstance(payload, dict)
    except Exception:
        return False


def _memory_attached() -> bool:
    return all(path.is_file() for path in ATTACHMENT_PATHS)


def _production_runtime_connected() -> bool:
    path = Path(os.environ.get("MINITZ_RUNTIME_ROOT", str(DEFAULT_RUNTIME.parent))) / "runtime.json"
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        heartbeat = datetime.fromisoformat(str(payload.get("heartbeat_at") or "").replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        age = (now - heartbeat.astimezone(timezone.utc)).total_seconds()
        return str(payload.get("status") or "") not in {"", "STOPPED"} and 0 <= age <= 120
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def status() -> dict[str, Any]:
    services = {service: _unit_active(service) for service in ON_START_ORDER}
    target_active = _unit_active(ON_TARGET)
    checks = {
        "local_qwen_resident": _qwen_resident(),
        "control_gateway_reachable": _control_gateway_reachable(),
        "memory_attached": _memory_attached(),
        "production_runtime_connected": _production_runtime_connected(),
    }
    fully_connected = target_active and all(services.values()) and all(checks.values())
    if fully_connected:
        state_name = "ON"
    elif not target_active and all(services.get(unit, False) for unit in MODEL_SERVICES) and not any(services.get(unit, False) for unit in WRITER_SERVICES):
        state_name = "SLEEP"
    elif target_active or any(services.values()):
        state_name = "RECOVERING"
    else:
        state_name = "OFF"
    return {
        "state": state_name,
        "fully_connected": fully_connected,
        "target_active": target_active,
        "services": services,
        "checks": checks,
        "receipt_present": DEFAULT_RECEIPT.is_file(),
    }


def on() -> dict[str, Any]:
    for service in ON_START_ORDER:
        _systemctl("enable", service)
        _systemctl("start", service)
    _systemctl("enable", ON_TARGET)
    _systemctl("start", ON_TARGET)
    try:
        timeout_seconds = max(1.0, float(os.environ.get("MINITZ_ON_CONNECT_TIMEOUT_SECONDS", "300")))
    except ValueError:
        timeout_seconds = 300.0
    deadline = time.monotonic() + timeout_seconds
    observed = status()
    while not observed["fully_connected"] and time.monotonic() < deadline:
        time.sleep(1.0)
        observed = status()
    if observed["fully_connected"]:
        return observed
    failed = [name for name, ok in observed["services"].items() if not ok]
    failed.extend(name for name, ok in observed["checks"].items() if not ok)
    try:
        off()
    except LifecycleError:
        pass
    raise LifecycleError("MiniTZ ON failed to reach a fully connected state: " + ", ".join(failed))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minitz-lifecycle")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--task-program", type=Path, default=DEFAULT_TASK_PROGRAM)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("command", choices=("qualify", "assert-ready", "assert-startup-attached", "sleep", "off", "on", "status"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _authorize_command(args.command, args.task_program)
        if args.command == "qualify":
            result = qualify(repo_root=args.repo_root, task_program_path=args.task_program, receipt_path=args.receipt)
        elif args.command == "assert-ready":
            result = assert_ready(repo_root=args.repo_root, task_program_path=args.task_program, receipt_path=args.receipt)
        elif args.command == "assert-startup-attached":
            result = assert_startup_attached(task_program_path=args.task_program)
        elif args.command == "sleep":
            result = sleep()
        elif args.command == "off":
            result = off()
        elif args.command == "on":
            result = on()
        else:
            result = status()
    except LifecycleError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
