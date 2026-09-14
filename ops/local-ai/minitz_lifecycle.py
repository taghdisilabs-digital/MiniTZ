#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

MODEL_SERVICES = (
    "biella-ollama.service",
    "biella-qwen-residency.service",
)
CONTROL_SERVICES = (
    "project-sandbox-broker.service",
    "biella-control-gateway.service",
)
WRITER_SERVICES = ("biella-codex-production.service",)
ON_START_ORDER = (*MODEL_SERVICES, *CONTROL_SERVICES, *WRITER_SERVICES)
OFF_SERVICES = (
    "biella-codex-production.service",
    "biella-control-gateway.service",
    "project-sandbox-broker.service",
    "biella-qwen-residency.service",
    "biella-ollama.service",
)
ON_TARGET = "minitz-on.target"
DEFAULT_REPO_ROOT = Path(os.environ.get("BIELLA_REPO_ROOT", "/mnt/biella-extra/minitz-os-sandbox/workspace/repo"))
DEFAULT_TASK_PROGRAM = Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/root/biella/analysis/live_audit/TASK_PROGRAM.json"))
DEFAULT_RECEIPT = Path(os.environ.get(
    "MINITZ_READINESS_RECEIPT",
    "/mnt/biella-extra/minitz-os-sandbox/state/qualification/READY_TO_ON.json",
))
TASK_VALIDATION_TESTS = (
    "tests/test_execution_policy_law.py",
    "tests/test_gpu_residency_policy.py",
    "tests/test_minitz_lifecycle.py",
    "tests/test_minitz_os_sandbox.py",
    "tests/test_never_ever_control_boundaries.py",
    "tests/test_minitz_data_residency.py",
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


def qualify(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
    task_program_path: Path = DEFAULT_TASK_PROGRAM,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    program = Path(task_program_path).resolve()
    receipt = Path(receipt_path).resolve()
    if _unit_active(ON_TARGET):
        raise LifecycleError("MiniTZ must be OFF before ON qualification")
    if not program.is_file():
        raise LifecycleError(f"MiniTZ Task Program is unavailable: {program}")
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
    failed = _failed_systemd_units()
    if failed:
        raise LifecycleError("failed systemd units remain: " + "; ".join(failed[:10]))
    payload = {
        "schema": "minitz.on_readiness/v1",
        "status": "READY",
        "qualified_at": _now(),
        "qualified_while_off": True,
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
    if payload.get("status") != "READY" or payload.get("qualified_while_off") is not True:
        raise LifecycleError("MiniTZ ON readiness receipt is not an OFF-qualified READY receipt")
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
    failed = _failed_systemd_units()
    if failed:
        raise LifecycleError("failed systemd units remain: " + "; ".join(failed[:10]))
    return {"status": "READY", "repo_head": head, "repo_tree": tree, "receipt": str(receipt)}


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


def on() -> dict[str, Any]:
    ready = assert_ready()
    for service in ON_START_ORDER:
        _systemctl("enable", service)
        _systemctl("start", service)
    _systemctl("enable", ON_TARGET)
    _systemctl("start", ON_TARGET)
    return {"state": "ON", "readiness": ready}


def status() -> dict[str, Any]:
    return {
        "state": "ON" if _unit_active(ON_TARGET) else "OFF_OR_SLEEP",
        "target_active": _unit_active(ON_TARGET),
        "services": {service: _unit_active(service) for service in ON_START_ORDER},
        "receipt_present": DEFAULT_RECEIPT.is_file(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minitz-lifecycle")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--task-program", type=Path, default=DEFAULT_TASK_PROGRAM)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("command", choices=("qualify", "assert-ready", "sleep", "off", "on", "status"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "qualify":
            result = qualify(repo_root=args.repo_root, task_program_path=args.task_program, receipt_path=args.receipt)
        elif args.command == "assert-ready":
            result = assert_ready(repo_root=args.repo_root, task_program_path=args.task_program, receipt_path=args.receipt)
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
