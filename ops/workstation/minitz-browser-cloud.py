#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
TARGETS_PATH = HERE / "windows-browser-cloud-targets.json"
DEFAULT_SSH_CONFIG = Path("/root/.ssh/config")


class BrowserCloudError(RuntimeError):
    pass


def load_manifest(path: Path = TARGETS_PATH) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "minitz.browser_cloud_targets/v1":
        raise BrowserCloudError("invalid browser-cloud target manifest")
    if data.get("authority") != "NONE" or not isinstance(data.get("targets"), dict):
        raise BrowserCloudError("browser-cloud manifest authority/targets are invalid")
    return data

def _ssh_config() -> Path:
    return Path(os.environ.get("MINITZ_WINDOWS_BROWSER_SSH_CONFIG", str(DEFAULT_SSH_CONFIG)))


def _run(args: list[str], *, timeout: float = 15.0, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BrowserCloudError(f"transport execution failed: {type(exc).__name__}") from None
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "remote command failed").strip()
        raise BrowserCloudError(detail[:1200])
    return proc


def _ssh_args(manifest: Mapping[str, Any], remote_command: str) -> list[str]:
    alias = str(manifest["transport"]["ssh_alias"])
    return ["ssh", "-F", str(_ssh_config()), alias, remote_command]


def _restart_bridge(manifest: Mapping[str, Any]) -> None:
    task = str(manifest["transport"]["bridge_task"])
    command = f"powershell -NoProfile -Command \"Start-ScheduledTask -TaskName '{task}'\""
    _run(_ssh_args(manifest, command), timeout=10.0)

def _remote_paths(manifest: Mapping[str, Any], request_id: str) -> tuple[str, str, str]:
    base = str(manifest["transport"]["remote_base"])
    request = base + "\\requests\\" + request_id + ".json"
    response = base + "\\responses\\" + request_id + ".json"
    scp_request = request.replace("\\", "/")
    return request, response, scp_request


def _read_response(manifest: Mapping[str, Any], response_path: str) -> str:
    command = (
        "powershell -NoProfile -Command \""
        f"if(Test-Path '{response_path}'){{Get-Content -Raw '{response_path}'}}"
        "\""
    )
    proc = _run(_ssh_args(manifest, command), timeout=8.0, check=False)
    return proc.stdout.strip()


def _remove_response(manifest: Mapping[str, Any], response_path: str) -> None:
    command = (
        "powershell -NoProfile -Command \""
        f"Remove-Item -Force -ErrorAction SilentlyContinue '{response_path}'"
        "\""
    )
    _run(_ssh_args(manifest, command), timeout=8.0, check=False)

def bridge_request(op: str, *, target: str | None = None, timeout: float = 12.0) -> dict[str, Any]:
    manifest = load_manifest()
    if target is not None and target not in manifest["targets"]:
        raise BrowserCloudError(f"unknown browser target: {target}")
    request_id = "minitz-" + uuid.uuid4().hex
    request_path, response_path, scp_request = _remote_paths(manifest, request_id)
    payload: dict[str, Any] = {"op": op}
    if target is not None:
        payload["target"] = target

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        local_request = Path(handle.name)
    try:
        alias = str(manifest["transport"]["ssh_alias"])
        _run([
            "scp", "-q", "-F", str(_ssh_config()), str(local_request),
            f"{alias}:{scp_request}",
        ], timeout=10.0)
        started = time.monotonic()
        deadline = started + max(2.0, timeout)
        restart_at = started + min(2.0, max(0.5, timeout / 4.0))
        restarted = False
        while time.monotonic() < deadline:
            raw = _read_response(manifest, response_path)
            if raw:
                _remove_response(manifest, response_path)
                response = json.loads(raw.lstrip("\ufeff"))
                if not isinstance(response, dict):
                    raise BrowserCloudError("browser bridge returned non-object response")
                return response
            if not restarted and time.monotonic() >= restart_at:
                _restart_bridge(manifest)
                restarted = True
                deadline = max(deadline, time.monotonic() + max(4.0, timeout))
            time.sleep(0.25)
    finally:
        local_request.unlink(missing_ok=True)
    raise BrowserCloudError(f"browser bridge timed out for request {request_id}")

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minitz-browser-cloud")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("targets")
    activate = sub.add_parser("activate")
    activate.add_argument("target", choices=sorted(load_manifest()["targets"]))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "targets":
            result: Mapping[str, Any] = load_manifest()
        elif args.command == "status":
            result = bridge_request("status")
        elif args.command == "activate":
            result = bridge_request("activate", target=args.target)
        else:
            raise AssertionError(args.command)
    except (BrowserCloudError, json.JSONDecodeError, KeyError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True), file=os.sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
