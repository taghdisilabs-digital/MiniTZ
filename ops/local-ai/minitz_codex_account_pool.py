#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import sys
from typing import Any, BinaryIO, Iterable, Mapping

SCHEMA = "minitz.codex_account_pool/v1"
STATE_SCHEMA = "minitz.codex_account_pool_state/v1"
CHECKPOINT_SCHEMA = "minitz.codex_account_switch_checkpoint/v1"
DEFAULT_ACCOUNTS_ROOT = Path("/root/attached-storage/minitz-os-sandbox/state/credentials/codex-accounts")
DEFAULT_SHARED_ROOT = Path("/root/.codex")
DEFAULT_RUNTIME_ROOT = Path("/root/attached-storage/minitz-os-sandbox/state/production")
SHARED_ASSETS = ("AGENTS.md", "cache", "tmp", "plugins", "skills", "models_cache.json", "config.toml")
_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_USAGE_LIMIT_RE = re.compile(r"(?:usage_limit_exceeded|rate_limit_exceeded|you(?:'|’)?ve hit your usage limit|usage limit|rate limit|out of credit|quota[^\n]{0,80}(?:exhaust|reached|exceed))", re.I)
_APPROACHING_RE = re.compile(r"(?:approach(?:ing)?|near(?:ing)?)\s+(?:your\s+)?(?:weekly\s+)?usage limit", re.I)
_REMAINING_RE = re.compile(r"(?:(?:remaining)[^%\n]{0,40}?\b(\d{1,3})\s*%|\b(\d{1,3})\s*%[^\n]{0,40}(?:remaining))", re.I)
_RETRY_RE = re.compile(r"(?:try again at|retry at|available at)\s+([^\n]+)", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def _read_json(path: Path, default: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default or {})
    return dict(value) if isinstance(value, Mapping) else dict(default or {})


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _validate_account_id(account_id: str) -> str:
    value = str(account_id).strip()
    if not _ACCOUNT_ID_RE.fullmatch(value):
        raise ValueError("invalid Codex account id")
    return value


def _registry_template() -> dict[str, Any]:
    return {"schema": SCHEMA, "accounts": []}


def load_registry(path: Path) -> dict[str, Any]:
    data = _read_json(Path(path), _registry_template())
    if data.get("schema") != SCHEMA or not isinstance(data.get("accounts"), list):
        raise ValueError("invalid MiniTZ Codex account registry")
    return data


def _ensure_shared_assets(home: Path, shared_root: Path) -> None:
    home = Path(home); shared_root = Path(shared_root)
    home.mkdir(parents=True, exist_ok=True); os.chmod(home, 0o700)
    for name in SHARED_ASSETS:
        source = shared_root / name
        if not source.exists():
            continue
        target = home / name
        if target == source:
            continue
        if target.is_symlink() and target.resolve() == source.resolve():
            continue
        if target.exists() or target.is_symlink():
            if target.is_file() and source.is_file() and target.read_bytes() == source.read_bytes():
                target.unlink()
            elif target.is_dir() and not any(target.iterdir()):
                target.rmdir()
            else:
                continue
        target.symlink_to(source, target_is_directory=source.is_dir())


def add_account(registry_path: Path, account_id: str, home: Path, *, shared_root: Path = DEFAULT_SHARED_ROOT,
                enabled: bool = True) -> dict[str, Any]:
    account_id = _validate_account_id(account_id); home = Path(home).resolve()
    _ensure_shared_assets(home, Path(shared_root).resolve())
    registry = load_registry(registry_path)
    existing = next((row for row in registry["accounts"] if row.get("account_id") == account_id), None)
    if existing is None:
        existing = {
            "account_id": account_id,
            "home": str(home),
            "enabled": bool(enabled),
            "added_at": _now().isoformat(),
        }
        registry["accounts"].append(existing)
    else:
        existing["home"] = str(home); existing["enabled"] = bool(enabled)
    _atomic_json(registry_path, registry)
    return dict(existing)


def set_account_enabled(registry_path: Path, account_id: str, enabled: bool) -> dict[str, Any]:
    registry = load_registry(registry_path); account_id = _validate_account_id(account_id)
    row = next((item for item in registry["accounts"] if item.get("account_id") == account_id), None)
    if row is None:
        raise KeyError(account_id)
    row["enabled"] = bool(enabled)
    _atomic_json(registry_path, registry)
    return dict(row)


def _state_template() -> dict[str, Any]:
    return {"schema": STATE_SCHEMA, "active_account": None, "cooldowns": {}}


def load_state(path: Path) -> dict[str, Any]:
    data = _read_json(path, _state_template())
    if data.get("schema") != STATE_SCHEMA:
        data = _state_template()
    if not isinstance(data.get("cooldowns"), Mapping):
        data["cooldowns"] = {}
    return data


def _cooling_until(state: Mapping[str, Any], account_id: str, now: datetime) -> bool:
    raw = str((state.get("cooldowns") or {}).get(account_id) or "")
    if not raw:
        return False
    try:
        target = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return target > now


def _account_ready(row: Mapping[str, Any], state: Mapping[str, Any], now: datetime) -> bool:
    home = Path(str(row.get("home") or ""))
    return bool(row.get("enabled", True)) and (home / "auth.json").is_file() and not _cooling_until(state, str(row.get("account_id") or ""), now)


def pool_capacity_retry_at(registry: Mapping[str, Any], state: Mapping[str, Any], *, now: datetime | None = None) -> datetime | None:
    """Return earliest capacity recovery when every enabled authenticated account is cooling."""
    now = now or _now(); cooling: list[datetime] = []; eligible = 0
    for row in registry.get("accounts", []):
        if not isinstance(row, Mapping) or not bool(row.get("enabled", True)):
            continue
        home = Path(str(row.get("home") or ""))
        if not (home / "auth.json").is_file():
            continue
        eligible += 1
        raw = str((state.get("cooldowns") or {}).get(str(row.get("account_id") or "")) or "")
        try:
            target = datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
        except ValueError:
            target = None
        if target is None:
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        if target <= now:
            return None
        cooling.append(target)
    return min(cooling) if eligible and len(cooling) == eligible else None


def select_next_account(registry: Mapping[str, Any], state: Mapping[str, Any], current_account: str | None,
                        *, now: datetime | None = None, excluded: Iterable[str] = ()) -> dict[str, Any] | None:
    now = now or _now(); excluded_ids = {str(item) for item in excluded}
    rows = [row for row in registry.get("accounts", []) if isinstance(row, Mapping)]
    if not rows:
        return None
    ids = [str(row.get("account_id") or "") for row in rows]
    start = (ids.index(str(current_account)) + 1) if current_account in ids else 0
    for offset in range(len(rows)):
        row = rows[(start + offset) % len(rows)]
        account_id = str(row.get("account_id") or "")
        if account_id in excluded_ids or account_id == str(current_account or ""):
            continue
        if _account_ready(row, state, now):
            return dict(row)
    return None


def active_account(registry: Mapping[str, Any], state: Mapping[str, Any], preferred: str | None = None,
                   *, now: datetime | None = None) -> dict[str, Any] | None:
    now = now or _now()
    wanted = str(preferred or state.get("active_account") or "")
    for row in registry.get("accounts", []):
        if isinstance(row, Mapping) and str(row.get("account_id") or "") == wanted and _account_ready(row, state, now):
            return dict(row)
    for row in registry.get("accounts", []):
        if isinstance(row, Mapping) and _account_ready(row, state, now):
            return dict(row)
    return None


def fresh_exec_args(args: list[str]) -> list[str]:
    result = list(args)
    try:
        exec_index = result.index("exec")
    except ValueError:
        return result
    if exec_index + 1 >= len(result) or result[exec_index + 1] != "resume":
        return result
    del result[exec_index + 1]
    if result and result[-1] == "-" and len(result) >= 2:
        del result[-2]
    return result


def passive_low_remaining(text: str, *, threshold: int = 10) -> bool:
    value = str(text or "")
    if _APPROACHING_RE.search(value):
        return True
    match = _REMAINING_RE.search(value)
    if not match:
        return False
    raw = next((group for group in match.groups() if group is not None), None)
    return raw is not None and int(raw) <= max(0, min(100, int(threshold)))


def is_usage_limit(text: str) -> bool:
    return bool(_USAGE_LIMIT_RE.search(str(text or "")))


def _retry_at_from_text(text: str, observed: datetime | None = None) -> datetime:
    observed = observed or _now()
    match = _RETRY_RE.search(str(text or ""))
    if not match:
        return observed + timedelta(minutes=30)
    raw = match.group(1).strip().rstrip(".")
    raw = re.sub(r"(?<=\d)(?:st|nd|rd|th)(?=,)", "", raw, flags=re.I)
    for fmt in ("%b %d, %Y %I:%M %p UTC", "%b %d, %Y %I:%M %p"):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc if raw.upper().endswith(" UTC") else (observed.tzinfo or timezone.utc))
    return observed + timedelta(minutes=30)


def _task_program_identity(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    task_id = None
    current = payload.get("current_execution") if isinstance(payload.get("current_execution"), Mapping) else {}
    task_id = str(current.get("task_id") or "") or None
    if task_id is None:
        complete = {"COMPLETE", "COMPLETE_ALREADY", "COMPLETED", "RETIRED", "OBSOLETE", "DUPLICATE", "SUPERSEDED"}
        task_id = next((str(row.get("task_id")) for row in payload.get("tasks", []) if isinstance(row, Mapping) and str(row.get("status") or "") not in complete), None)
    return {"revision": payload.get("revision"), "task_id": task_id, "sha256": _sha256(path)}


def write_switch_checkpoint(runtime_root: Path, from_account: str, to_account: str, *, reason: str) -> dict[str, Any]:
    runtime_root = Path(runtime_root)
    runtime = _read_json(runtime_root / "runtime.json")
    task_id = str(runtime.get("task_id") or "") or None
    program_path = Path(os.environ.get("MINITZ_TASK_PROGRAM_PATH", "/root/attached-storage/minitz-os-sandbox/state/task-program/TASK_PROGRAM.json"))
    program = _task_program_identity(program_path)
    capsule = runtime_root / "task-memory" / f"{task_id}.json" if task_id else Path("/")
    prior_session = str(runtime.get("task_session_id") or "")
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "recorded_at": _now().isoformat(),
        "reason": str(reason),
        "from_account": str(from_account),
        "to_account": str(to_account),
        "task_id": task_id or program.get("task_id"),
        "attempt": runtime.get("attempt"),
        "prior_native_session_id_sha256": hashlib.sha256(prior_session.encode()).hexdigest() if prior_session else None,
        "task_capsule_sha256": _sha256(capsule) if task_id else None,
        "current_task_projection_sha256": _sha256(runtime_root / "memory/current-task.json"),
        "compacted_memory_sha256": _sha256(runtime_root / "memory/compacted-memory.json"),
        "task_program_revision": program.get("revision"),
        "task_program_sha256": program.get("sha256"),
        "resume_strategy": "FRESH_CODEX_SESSION_FROM_SHARED_MINITZ_CHECKPOINT",
        "progression_authority": "MINITZ_TASK_PROGRAM_ONLY",
    }
    recovery = runtime_root / "recovery"
    _atomic_json(recovery / "codex-account-switch-current.json", payload)
    history = recovery / "codex-account-switches"
    history.mkdir(parents=True, exist_ok=True)
    stamp = payload["recorded_at"].replace(":", "").replace("+00:00", "Z")
    _atomic_json(history / f"{stamp}-{from_account}-to-{to_account}.json", payload)
    event_path = recovery / "codex-account-switches.jsonl"
    fd = os.open(event_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush(); os.fsync(stream.fileno())
    return payload


def _default_paths() -> tuple[Path, Path, Path, Path]:
    runtime = Path(os.environ.get("MINITZ_RUNTIME_ROOT", str(DEFAULT_RUNTIME_ROOT)))
    accounts_root = Path(os.environ.get("MINITZ_CODEX_ACCOUNTS_ROOT", str(DEFAULT_ACCOUNTS_ROOT)))
    registry = Path(os.environ.get("MINITZ_CODEX_ACCOUNT_REGISTRY", str(accounts_root / "accounts.json")))
    state = Path(os.environ.get("MINITZ_CODEX_ACCOUNT_STATE", str(accounts_root / "pool-state.json")))
    return runtime, accounts_root, registry, state


def ensure_default_registry(registry_path: Path, state_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not Path(registry_path).is_file():
        registry = _registry_template()
        for account_id, home, enabled in (("mahdi", DEFAULT_ACCOUNTS_ROOT / "mahdi", True), ("patrick", DEFAULT_SHARED_ROOT, False)):
            if Path(home, "auth.json").is_file():
                registry["accounts"].append({"account_id": account_id, "home": str(home), "enabled": enabled, "added_at": _now().isoformat()})
        _atomic_json(registry_path, registry)
    if not Path(state_path).is_file():
        _atomic_json(state_path, {"schema": STATE_SCHEMA, "active_account": "mahdi", "cooldowns": {}})
    return load_registry(registry_path), load_state(state_path)


def _save_state(path: Path, state: Mapping[str, Any]) -> None:
    _atomic_json(path, state)


class _StreamedAccountResult(subprocess.CompletedProcess[bytes]):
    """Output already reached the parent journal; retained bytes are routing tails."""


_STREAM_TAIL_BYTES = 512 * 1024


def _forward_account_output(proc: subprocess.CompletedProcess[bytes]) -> None:
    if not isinstance(proc, _StreamedAccountResult):
        sys.stdout.buffer.write(proc.stdout)
        sys.stdout.buffer.flush()
        sys.stderr.buffer.write(proc.stderr)
        sys.stderr.buffer.flush()


def _run_account(account: Mapping[str, Any], args: list[str], stdin_bytes: bytes) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(account["home"])
    codex_bin = env.get("MINITZ_CODEX_REAL_BIN", "/usr/bin/codex")
    command = [codex_bin, *args]
    if "exec" not in args:
        return subprocess.run(command, input=stdin_bytes, capture_output=True, check=False, env=env)

    # Drain both pipes as they arrive. The parent owns durable full transcripts;
    # this router keeps bounded tails only for capacity/failover classification.
    tails = [bytearray(), bytearray()]
    errors: list[BaseException] = []
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env) as proc:
        assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None

        def drain(source: BinaryIO, sink: BinaryIO, tail: bytearray) -> None:
            try:
                while True:
                    block = source.read1(65536)
                    if not block:
                        break
                    sink.write(block)
                    sink.flush()
                    tail.extend(block)
                    del tail[:-_STREAM_TAIL_BYTES]
            except BaseException as exc:
                errors.append(exc)
                if proc.poll() is None:
                    proc.terminate()

        readers = [
            threading.Thread(target=drain, args=(proc.stdout, sys.stdout.buffer, tails[0]), daemon=True),
            threading.Thread(target=drain, args=(proc.stderr, sys.stderr.buffer, tails[1]), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            try:
                proc.stdin.write(stdin_bytes)
                proc.stdin.close()
            except BrokenPipeError:
                pass
            returncode = proc.wait()
            for reader in readers:
                reader.join()
            if errors:
                raise RuntimeError("MiniTZ Codex live output forwarding failed") from errors[0]
        except BaseException:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            raise
    return _StreamedAccountResult(command, returncode, bytes(tails[0]), bytes(tails[1]))


def _cleanup_retry_output(args: list[str], runtime_root: Path) -> None:
    try:
        index = args.index("-o")
        path = Path(args[index + 1]).resolve()
    except (ValueError, IndexError, OSError):
        return
    try:
        path.relative_to(Path(runtime_root).resolve())
    except ValueError:
        return
    path.unlink(missing_ok=True)


def _set_cooldown(state: dict[str, Any], account_id: str, text: str) -> None:
    cooldowns = dict(state.get("cooldowns") or {})
    cooldowns[account_id] = _retry_at_from_text(text).isoformat()
    state["cooldowns"] = cooldowns


def _clear_expired_cooldowns(state: dict[str, Any], now: datetime | None = None) -> None:
    now = now or _now(); cooldowns = dict(state.get("cooldowns") or {})
    keep = {}
    for account_id, raw in cooldowns.items():
        try:
            target = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if target.tzinfo is None: target = target.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if target > now: keep[str(account_id)] = target.isoformat()
    state["cooldowns"] = keep


def router_main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    runtime_root, _accounts_root, registry_path, state_path = _default_paths()
    registry, state = ensure_default_registry(registry_path, state_path)
    _clear_expired_cooldowns(state)
    preferred = os.environ.get("MINITZ_CODEX_PREFERRED_ACCOUNT")
    account = active_account(registry, state, preferred)
    if account is None:
        retry_at = pool_capacity_retry_at(registry, state)
        if retry_at is not None:
            print(f"MiniTZ Codex account pool CAPACITY_UNAVAILABLE retry_at={retry_at.isoformat()}", file=sys.stderr)
        else:
            print("MiniTZ Codex account pool has no enabled authenticated account", file=sys.stderr)
        return 78
    stdin_bytes = sys.stdin.buffer.read()
    if "exec" not in args:
        proc = _run_account(account, args, stdin_bytes)
        _forward_account_output(proc)
        return int(proc.returncode)

    attempted: set[str] = set()
    original_args = list(args)
    current_args = list(args)
    last_proc: subprocess.CompletedProcess[bytes] | None = None
    while account is not None:
        account_id = str(account["account_id"]); attempted.add(account_id)
        proc = _run_account(account, current_args, stdin_bytes); last_proc = proc
        combined = (proc.stderr + b"\n" + proc.stdout).decode("utf-8", errors="replace")
        if proc.returncode == 0:
            state["active_account"] = account_id
            threshold = int(os.environ.get("MINITZ_CODEX_ROTATE_REMAINING_PCT", "10"))
            next_account = select_next_account(registry, state, account_id, excluded=attempted)
            if next_account is not None and passive_low_remaining(combined, threshold=threshold):
                write_switch_checkpoint(runtime_root, account_id, str(next_account["account_id"]), reason="USAGE_APPROACHING")
                state["active_account"] = str(next_account["account_id"])
            _save_state(state_path, state)
            _forward_account_output(proc)
            return 0

        if not is_usage_limit(combined):
            _forward_account_output(proc)
            return int(proc.returncode)
        _set_cooldown(state, account_id, combined)
        next_account = select_next_account(registry, state, account_id, excluded=attempted)
        if next_account is None:
            state["active_account"] = account_id
            _save_state(state_path, state)
            _forward_account_output(proc)
            return int(proc.returncode)
        next_id = str(next_account["account_id"])
        write_switch_checkpoint(runtime_root, account_id, next_id, reason="USAGE_LIMIT")
        state["active_account"] = next_id; _save_state(state_path, state)
        _cleanup_retry_output(original_args, runtime_root)
        current_args = fresh_exec_args(original_args)
        account = next_account
    if last_proc is not None:
        _forward_account_output(last_proc)
        return int(last_proc.returncode)
    return 78


def _find_account(registry: Mapping[str, Any], account_id: str) -> dict[str, Any]:
    account_id = _validate_account_id(account_id)
    row = next((dict(item) for item in registry.get("accounts", []) if isinstance(item, Mapping) and item.get("account_id") == account_id), None)
    if row is None:
        raise KeyError(account_id)
    return row


def _account_status(row: Mapping[str, Any]) -> dict[str, Any]:
    env = os.environ.copy(); env["CODEX_HOME"] = str(row["home"])
    proc = subprocess.run([env.get("MINITZ_CODEX_REAL_BIN", "/usr/bin/codex"), "login", "status"], text=True, capture_output=True, check=False, env=env)
    return {"account_id": row["account_id"], "home": row["home"], "enabled": bool(row.get("enabled", True)), "logged_in": proc.returncode == 0, "status": (proc.stdout or proc.stderr).strip()[:500]}


def account_main(argv: list[str] | None = None) -> int:
    runtime_root, accounts_root, registry_path, state_path = _default_paths()
    registry, state = ensure_default_registry(registry_path, state_path)
    parser = argparse.ArgumentParser(prog="minitz-codex-account")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add"); add.add_argument("account_id"); add.add_argument("--home", type=Path); add.add_argument("--disabled", action="store_true")
    for name in ("enable", "disable", "use", "login", "status"):
        cmd = sub.add_parser(name); cmd.add_argument("account_id", nargs="?" if name == "status" else None)
    run = sub.add_parser("run"); run.add_argument("account_id"); run.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == "list":
        print(json.dumps({"registry": registry, "state": state}, sort_keys=True, indent=2)); return 0
    if args.command == "add":
        home = args.home or (accounts_root / args.account_id)
        row = add_account(registry_path, args.account_id, home, enabled=not args.disabled)
        print(json.dumps({**row, "login_command": f"minitz-codex-account login {row['account_id']}"}, sort_keys=True)); return 0
    if args.command in {"enable", "disable"}:
        row = set_account_enabled(registry_path, args.account_id, args.command == "enable")
        print(json.dumps(row, sort_keys=True)); return 0
    registry = load_registry(registry_path)
    if args.command == "use":
        row = _find_account(registry, args.account_id)
        if not row.get("enabled", True):
            raise SystemExit("account is disabled")
        state["active_account"] = row["account_id"]
        _save_state(state_path, state)
        print(json.dumps({"active_account": row["account_id"]}, sort_keys=True)); return 0
    if args.command == "status":
        rows = registry["accounts"] if args.account_id is None else [_find_account(registry, args.account_id)]
        print(json.dumps({"accounts": [_account_status(row) for row in rows]}, sort_keys=True, indent=2)); return 0
    row = _find_account(registry, args.account_id)
    env = os.environ.copy(); env["CODEX_HOME"] = str(row["home"])
    codex_bin = env.get("MINITZ_CODEX_REAL_BIN", "/usr/bin/codex")
    if args.command == "login":
        return subprocess.call([codex_bin, "login"], env=env)
    if args.command == "run":
        tail = list(args.args)
        if tail and tail[0] == "--": tail = tail[1:]
        return subprocess.call([codex_bin, *tail], env=env)
    return 2


if __name__ == "__main__":
    raise SystemExit(account_main())
