#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROTECTED_SERVICES = (
    "biella-ollama.service",
    "biella-qwen-residency.service",
    "biella-codex-production.service",
)
STOP_ORDER = tuple(reversed(PROTECTED_SERVICES))


class HandoffError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str | None:
    if not Path(path).is_file():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def dirty_workspace_fingerprint(repo_root: Path) -> str:
    repo_root = Path(repo_root)
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True, check=True,
    )
    digest = hashlib.sha256()
    digest.update(proc.stdout)
    for record in proc.stdout.split(b"\0"):
        if len(record) < 4:
            continue
        raw = record[3:].decode("utf-8", errors="surrogateescape")
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        path = repo_root / raw
        digest.update(raw.encode("utf-8", errors="surrogateescape"))
        if path.is_symlink():
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class BiellaCustomerHandoff:
    def __init__(self, repo_root: Path, runtime_root: Path, handoff_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.runtime_root = Path(runtime_root).resolve()
        self.handoff_root = Path(handoff_root).resolve()
        self.active_checkpoint_path = self.handoff_root / "active.json"
        self.history_root = self.handoff_root / "history"
        self.pause_request_path = self.runtime_root / "customer-pause-request.json"
        self.pause_ack_path = self.runtime_root / "customer-pause-ack.json"
    def service_states(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for name in PROTECTED_SERVICES:
            active = subprocess.run(
                ["systemctl", "is-active", "--quiet", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            ).returncode == 0
            enabled_proc = subprocess.run(
                ["systemctl", "is-enabled", name], text=True, capture_output=True, check=False,
            )
            enabled = (enabled_proc.stdout or enabled_proc.stderr or "unknown").strip().splitlines()[0]
            result[name] = {"active": active, "enabled": enabled}
        return result

    def guard_production(self) -> None:
        if self.running_customer_count() > 0:
            raise HandoffError("cannot start Biella while a customer container is running")

    def running_customer_count(self) -> int:
        proc = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or "docker ps failed").strip())
        return sum(1 for line in proc.stdout.splitlines() if line.strip().startswith("psb-"))

    def set_enabled_state(self, name: str, state: str) -> None:
        if state == "enabled":
            cmd = ["systemctl", "enable", name]
        elif state == "disabled":
            cmd = ["systemctl", "disable", name]
        elif state == "masked":
            cmd = ["systemctl", "mask", name]
        else:
            return
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or f"failed to set {name} {state}").strip())
    def set_active_state(self, name: str, active: bool) -> None:
        cmd = ["systemctl", "start" if active else "stop", name]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or f"failed to {'start' if active else 'stop'} {name}").strip())

    def verify_source_alignment(self) -> None:
        script = self.repo_root / "ops/local-ai/biella-production-source-sync.sh"
        if not script.is_file():
            raise HandoffError(f"source alignment script missing: {script}")
        env = os.environ.copy()
        env["BIELLA_REPO_ROOT"] = str(self.repo_root)
        proc = subprocess.run([str(script)], text=True, capture_output=True, check=False, env=env)
        if proc.returncode != 0:
            raise HandoffError((proc.stderr or proc.stdout or "source alignment failed").strip())

    def _git_identity(self) -> dict[str, str]:
        def git(*args: str) -> str:
            return subprocess.check_output(["git", "-C", str(self.repo_root), *args], text=True).strip()
        return {"branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}

    def _runtime_identity(self) -> tuple[str | None, dict[str, str | None]]:
        runtime_path = self.runtime_root / "runtime.json"
        runtime: dict[str, Any] = {}
        if runtime_path.is_file():
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        task_id = str(runtime.get("task_id") or "") or None
        task_memory = self.runtime_root / "task-memory" / f"{task_id}.json" if task_id else Path("/")
        projection = self.runtime_root / "memory/current-task.json"
        return task_id, {
            "runtime_sha256": _sha256(runtime_path),
            "task_memory_sha256": _sha256(task_memory) if task_id else None,
            "projection_sha256": _sha256(projection),
        }
    def cooperative_pause(self, timeout_seconds: float = 3600.0) -> None:
        _atomic_json(self.pause_request_path, {
            "schema": "biella.customer_pause_request/v1",
            "requested_at": _now(),
        })
        deadline = time.monotonic() + max(1.0, timeout_seconds)
        while time.monotonic() < deadline:
            inactive = subprocess.run(
                ["systemctl", "is-active", "--quiet", "biella-codex-production.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            ).returncode != 0
            if inactive and self.pause_ack_path.is_file():
                return
            time.sleep(0.25)
        raise HandoffError("production did not reach a cooperative customer checkpoint before timeout")

    def checkpoint(self) -> dict[str, Any]:
        if self.active_checkpoint_path.is_file():
            current = json.loads(self.active_checkpoint_path.read_text(encoding="utf-8"))
            if current.get("workspace_fingerprint") != dirty_workspace_fingerprint(self.repo_root):
                raise HandoffError("existing customer checkpoint no longer matches Biella dirty worktree")
            self.sleep_services()
            return current
        original_services = self.service_states()
        if original_services["biella-codex-production.service"]["active"]:
            self.cooperative_pause()
        task_id, runtime_identity = self._runtime_identity()
        checkpoint = {
            "schema": "biella.customer_handoff_checkpoint/v1",
            "created_at": _now(),
            "repo": self._git_identity(),
            "task_id": task_id,
            "runtime": runtime_identity,
            "workspace_fingerprint": dirty_workspace_fingerprint(self.repo_root),
            "services": original_services,
        }
        _atomic_json(self.active_checkpoint_path, checkpoint)
        for name in STOP_ORDER:
            self.set_active_state(name, False)
        for name in PROTECTED_SERVICES:
            self.set_enabled_state(name, "disabled")
        return checkpoint
    def sleep_services(self) -> None:
        for name in STOP_ORDER:
            self.set_active_state(name, False)
        for name in PROTECTED_SERVICES:
            self.set_enabled_state(name, "disabled")

    def resume(self) -> dict[str, Any]:
        if not self.active_checkpoint_path.is_file():
            return {"status": "NO_CHECKPOINT"}
        if self.running_customer_count() != 0:
            raise HandoffError("cannot resume Biella while a customer container is still running")
        checkpoint = json.loads(self.active_checkpoint_path.read_text(encoding="utf-8"))
        expected = str(checkpoint.get("workspace_fingerprint") or "")
        current = dirty_workspace_fingerprint(self.repo_root)
        if not expected or current != expected:
            raise HandoffError("Biella dirty worktree changed while customer checkpoint was held")
        current_task, current_runtime = self._runtime_identity()
        expected_runtime = checkpoint.get("runtime")
        if current_task != checkpoint.get("task_id") or not isinstance(expected_runtime, dict) or current_runtime != expected_runtime:
            raise HandoffError("Biella runtime continuity changed while customer checkpoint was held")
        self.verify_source_alignment()
        services = checkpoint.get("services")
        if not isinstance(services, dict):
            raise HandoffError("checkpoint service state is invalid")
        for name in PROTECTED_SERVICES:
            state = services.get(name)
            if not isinstance(state, dict):
                raise HandoffError(f"checkpoint missing service state for {name}")
            self.set_enabled_state(name, str(state.get("enabled") or "unknown"))
        for name in PROTECTED_SERVICES:
            self.set_active_state(name, bool(services[name].get("active")))
        self.pause_request_path.unlink(missing_ok=True)
        self.pause_ack_path.unlink(missing_ok=True)
        self.history_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(self.active_checkpoint_path.read_bytes()).hexdigest()
        history = self.history_root / f"{digest}.json"
        shutil.copy2(self.active_checkpoint_path, history)
        self.active_checkpoint_path.unlink()
        return {"status": "RESTORED", "checkpoint_sha256": digest, "history": str(history)}

    def import_lessons(self, source_path: Path, inbox_root: Path) -> dict[str, Any]:
        source_path = Path(source_path)
        if not source_path.is_file():
            return {"status": "NO_LESSONS"}
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != "project_sandbox.sanitized_lessons/v1":
            raise HandoffError("lesson is not project-neutral: invalid bundle schema")
        raw_lessons = payload.get("lessons")
        if not isinstance(raw_lessons, list) or len(raw_lessons) > 100:
            raise HandoffError("lesson is not project-neutral: invalid lesson list")
        lessons = [_validate_neutral_lesson(item) for item in raw_lessons]
        if not lessons:
            source_path.unlink(missing_ok=True)
            return {"status": "NO_LESSONS"}
        encoded = json.dumps(lessons, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        inbox_root = Path(inbox_root)
        inbox_root.mkdir(parents=True, exist_ok=True)
        target = inbox_root / f"{digest}.json"
        candidate = {
            "schema": "biella.external_lesson_candidate/v1",
            "sha256": digest, "imported_at": _now(), "lessons": lessons,
            "authority": "PROJECT_NEUTRAL_CANDIDATE_NOT_ACTIVE_AUTHORITY",
        }
        if not target.exists():
            _atomic_json(target, candidate)
        source_path.unlink(missing_ok=True)
        return {"status": "IMPORTED", "sha256": digest, "path": str(target)}


_LESSON_CATEGORIES = {
    "build_method", "test_method", "tool_compatibility", "failure_fix", "performance",
    "cache_efficiency", "deployment_mechanic", "container_ci", "coding_workflow",
}
_LESSON_EVIDENCE = {"test", "build", "runtime", "benchmark", "deployment", "tool_output"}
_LESSON_KEYS = {"category", "title", "problem", "method", "result", "evidence_type", "timestamp"}
_NEUTRAL_FORBIDDEN = re.compile(
    r"(?:https?://|git@|www\.|(?:^|\s)/(?:[A-Za-z0-9_.-]+/){1,}|\b[A-Za-z]:\\|"
    r"\b(?:customer|client|brand|logo|palette|typography|font|visual|screenshot|copywriting|"
    r"business data|product requirement|design language|style guide)\b|```)",
    re.I,
)


def _validate_neutral_lesson(record: Any) -> dict[str, str]:
    if not isinstance(record, dict) or set(record) != _LESSON_KEYS:
        raise HandoffError("lesson is not project-neutral: invalid schema")
    category = str(record["category"])
    evidence = str(record["evidence_type"])
    if category not in _LESSON_CATEGORIES or evidence not in _LESSON_EVIDENCE:
        raise HandoffError("lesson is not project-neutral: unsupported category or evidence")
    result = {key: str(record[key]).strip() for key in _LESSON_KEYS}
    for key in ("title", "problem", "method", "result"):
        value = result[key]
        if not value or _NEUTRAL_FORBIDDEN.search(value):
            raise HandoffError("lesson is not project-neutral: forbidden content")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-customer-handoff")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("checkpoint", "resume", "import-lessons", "status", "guard-production"):
        sub.add_parser(name)
    return parser


def _default_manager() -> BiellaCustomerHandoff:
    repo = Path(os.environ.get("BIELLA_REPO_ROOT", "/root/biella/repos/biella-engine"))
    runtime = Path(os.environ.get("BIELLA_CODEX_PRODUCTION_RUNTIME_ROOT", "/mnt/biella-extra/biella-runtime/codex-production"))
    handoff_root = Path(os.environ.get("BIELLA_CUSTOMER_HANDOFF_ROOT", "/mnt/biella-extra/biella-runtime/customer-handoff"))
    return BiellaCustomerHandoff(repo, runtime, handoff_root)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manager = _default_manager()
    if args.command == "checkpoint":
        result = manager.checkpoint()
    elif args.command == "resume":
        result = manager.resume()
    elif args.command == "import-lessons":
        source = Path(os.environ.get("BIELLA_EXTERNAL_LESSON_SOURCE", "/run/project-sandbox-broker/biella-lessons.json"))
        inbox = Path(os.environ.get("BIELLA_EXTERNAL_LESSON_INBOX", "/root/biella/artifacts/external-lessons/inbox"))
        result = manager.import_lessons(source, inbox)
    elif args.command == "guard-production":
        manager.guard_production()
        result = {"status": "CLEAR"}
    else:
        result = {
            "checkpoint_held": manager.active_checkpoint_path.is_file(),
            "running_customer_count": manager.running_customer_count(),
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
