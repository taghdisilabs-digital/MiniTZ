#!/usr/bin/env python3
"""Host adapter for Biella-owned isolated Project cell state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping, Sequence
from uuid import uuid4

from biella.project import ProjectAccess, ProjectRef, ProjectStore
from biella.run import RunRef, RunService
from biella.task import TaskRef, TaskRevisionService
from biella.project_cell import (
    BlockerRecord,
    ProjectCellCheckpoint,
    ProjectCellContractError,
    ProjectCellManifest,
    RemoteAssistanceRequest,
    RemoteAssistanceResponse,
    TaskEnvelope,
)


DEFAULT_STATE_ROOT = Path("/mnt/biella-extra/biella-runtime/project-cells")
DEFAULT_SANDBOXES_ROOT = Path("/srv/project-sandboxes")
DEFAULT_ENGINE_REPO = Path("/root/biella/repos/biella-engine")
DEFAULT_CONTRACT = DEFAULT_ENGINE_REPO / "docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _atomic_json(path: Path, payload: object, *, mode: int = 0o600) -> None:
    _secure_dir(path.parent)
    encoded = _canonical_json(payload)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path); os.chmod(path, mode)
    finally:
        tmp.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProjectCellContractError(f"expected JSON object: {path}")
    return data


def _safe_child(root: Path, name: str) -> Path:
    if not name or any(part in {"", ".", ".."} for part in Path(name).parts) or "/" in name:
        raise ProjectCellContractError("project_id is not path-safe")
    root = root.resolve(); path = (root / name).resolve()
    if root not in path.parents:
        raise ProjectCellContractError("project cell state crossed runtime root")
    return path


class ProjectCellRuntime:
    def __init__(
        self,
        *,
        state_root: Path = DEFAULT_STATE_ROOT,
        sandboxes_root: Path = DEFAULT_SANDBOXES_ROOT,
        engine_repo_root: Path = DEFAULT_ENGINE_REPO,
        governing_contract: Path = DEFAULT_CONTRACT,
    ) -> None:
        self.state_root = Path(state_root).resolve()
        self.sandboxes_root = Path(sandboxes_root).resolve()
        self.engine_repo_root = Path(engine_repo_root).resolve()
        self.governing_contract = Path(governing_contract).resolve()
        _secure_dir(self.state_root)
        self.engine_database = self.state_root / "engine.sqlite3"
        self.engine_access_root = self.state_root / "engine-access"
        _secure_dir(self.engine_access_root)

    def cell_root(self, project_id: str) -> Path:
        return _safe_child(self.state_root, project_id)

    def sandbox_root(self, project_id: str) -> Path:
        path = _safe_child(self.sandboxes_root, project_id)
        if not path.is_dir():
            raise ProjectCellContractError(f"sandbox project does not exist: {project_id}")
        return path

    def load_config(self, project_id: str) -> dict[str, Any]:
        path = self.sandbox_root(project_id) / "project.json"
        if not path.is_file():
            raise ProjectCellContractError(f"project config does not exist: {path}")
        data = _read_json(path)
        if data.get("id") != project_id:
            raise ProjectCellContractError("project config identity mismatch")
        return data

    def repositories(self, project_id: str) -> tuple[Path, ...]:
        workspace = self.sandbox_root(project_id) / "workspace"
        repos: list[Path] = []
        for current, dirs, _files in os.walk(workspace):
            current_path = Path(current)
            try:
                depth = len(current_path.relative_to(workspace).parts)
            except ValueError:
                continue
            if depth > 3:
                dirs[:] = []
                continue
            if ".git" in dirs:
                repos.append(current_path.resolve()); dirs.remove(".git")
        return tuple(sorted(set(repos)))

    @staticmethod
    def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args],
            text=True, capture_output=True, check=False,
        )
        if check and proc.returncode != 0:
            raise ProjectCellContractError((proc.stderr or proc.stdout or "git command failed").strip())
        return proc

    def container_status(self, project_id: str) -> dict[str, Any]:
        name = f"psb-{project_id}"
        proc = subprocess.run(["docker", "container", "inspect", name], text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            return {"exists": False, "running": False, "name": name, "image": None}
        data = json.loads(proc.stdout)[0]
        state = data.get("State") or {}; config = data.get("Config") or {}
        return {"exists": True, "running": bool(state.get("Running")), "name": name, "image": config.get("Image")}

    def _contract_sha256(self) -> str:
        if not self.governing_contract.is_file():
            raise ProjectCellContractError(f"governing contract missing: {self.governing_contract}")
        return _sha_bytes(self.governing_contract.read_bytes())

    def _engine_project(self, project_id: str) -> tuple[ProjectAccess, str]:
        store = ProjectStore(self.engine_database)
        if self.engine_database.exists():
            os.chmod(self.engine_database, 0o600)
        access_path = self.engine_access_root / f"{project_id}.json"
        if access_path.is_file():
            data = _read_json(access_path)
            access = ProjectAccess(ProjectRef(str(data.get("project_ref") or "")), str(data.get("token") or ""))
            project = store.get_project(access, access.project_ref)
            if project.namespace != project_id:
                raise ProjectCellContractError("native Engine Project namespace differs from cell identity")
            return access, project.project_ref.value
        registration = store.create_project(
            namespace=project_id,
            display_name=project_id,
            metadata={
                "project_type": "customer",
                "execution_model": "isolated_project_cell",
                "bridge_contract_sha256": self._contract_sha256(),
            },
        )
        _atomic_json(access_path, {
            "schema": "biella.project_cell_engine_access/v1",
            "project_id": project_id,
            "project_ref": registration.project.project_ref.value,
            "token": registration.access.token,
        })
        return registration.access, registration.project.project_ref.value

    def _current_run(self, project_id: str) -> dict[str, Any]:
        access, project_ref_value = self._engine_project(project_id)
        project_ref = ProjectRef(project_ref_value)
        tasks = TaskRevisionService(self.engine_database)
        runs = RunService(self.engine_database)
        path = self.cell_root(project_id) / "current-run.json"
        if path.is_file():
            data = _read_json(path)
            if data.get("project_id") != project_id or data.get("project_ref") != project_ref_value:
                raise ProjectCellContractError("current run Project identity mismatch")
            task_ref = TaskRef(project_ref, str(data.get("native_task_id") or ""), int(data.get("native_task_revision") or 0))
            run_ref = RunRef(project_ref, str(data.get("run_id") or ""))
            task = tasks.get_task(access, task_ref)
            run = runs.get_run(access, run_ref)
            if run.task_ref != task.task_ref or run.task_digest != task.canonical_digest:
                raise ProjectCellContractError("native Engine Run binding differs from current cell Task")
            return data
        task = tasks.create_task(
            access,
            project_ref=project_ref,
            idempotency_key=f"project-cell-execution-{project_id}",
            task_type="project-cell.execution",
            objective="UNVERIFIED",
            required_capabilities=(),
            input_refs=(),
            output_contract={"continuation": "schema://biella/project-cell-continuation/v1"},
            constraints={"project_cell": True},
            side_effect_authority="PROJECT_WRITE",
            data_policy_ref="policy://biella/project-cell-isolation/v1",
            egress_policy_ref="policy://biella/minimum-sufficient-context/v1",
            evidence_requirements=("durable project-scoped checkpoint",),
            acceptance_criteria=("Project authority supplies task-specific acceptance before completion",),
            resource_hints={},
        )
        run = runs.create_run(access, task_ref=task.task_ref)
        os.chmod(self.engine_database, 0o600)
        data = {
            "schema": "biella.project_cell_run_projection/v1",
            "project_id": project_id,
            "project_ref": project_ref_value,
            "native_task_id": task.task_id,
            "native_task_revision": task.revision,
            "task_digest": task.canonical_digest,
            "run_id": run.run_id,
            "task_id": "UNVERIFIED",
            "objective": "UNVERIFIED",
            "created_at": run.created_at,
        }
        _atomic_json(path, data)
        return data

    def adopt(self, project_id: str) -> dict[str, Any]:
        config = self.load_config(project_id)
        root = self.sandbox_root(project_id)
        workspace = (root / "workspace").resolve()
        cache = (root / "cache").resolve()
        artifacts = (root / "artifacts").resolve()
        artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
        repositories = self.repositories(project_id)
        if len(repositories) > 1:
            raise ProjectCellContractError("project cell has multiple repository roots; explicit repository_root is required")
        repository = repositories[0] if repositories else None
        container = self.container_status(project_id)
        execution_nodes = (f"docker://{container['name']}",) if container.get("exists") else ()
        gpu_allowed = str(config.get("default_gpu_mode") or "none") in {"shared", "full"}
        permissions = {
            "local_compute": {"allowed": True},
            "local_gpu": {"allowed": gpu_allowed},
            "chatgpt_remote": {"allowed": True, "role": "delegated_subtask_provider"},
            "browser_cloud": {"allowed": "UNVERIFIED"},
            "registered_capabilities": list(config.get("allowed_capabilities") or []),
        }
        manifest = ProjectCellManifest(
            project_id=project_id,
            project_name=project_id,
            project_type="customer",
            workspace_root=str(workspace),
            repository_root=None if repository is None else str(repository),
            canonical_artifact_root=str(artifacts),
            project_memory_namespace=f"project-cell://{project_id}/memory",
            run_memory_namespace=f"project-cell://{project_id}/runs",
            cache_root=str(cache),
            historical_evidence_root=None,
            deployment_targets=("UNKNOWN",),
            execution_nodes=execution_nodes,
            provider_permissions=permissions,
            acceptance_authority="Mahdi Taghdisi",
            source_registry=f"file://{root / 'project.json'}",
            governing_contract_sha256=self._contract_sha256(),
        )
        run = self._current_run(project_id)
        payload = manifest.to_payload()
        payload["observed_at"] = _now()
        payload["broker_config_sha256"] = _sha_bytes((root / "project.json").read_bytes())
        payload["engine_binding"] = {
            "project_ref": run["project_ref"],
            "task_ref": f"task://{run['project_ref']}/{run['native_task_id']}/{run['native_task_revision']}",
            "task_digest": run["task_digest"],
            "run_ref": f"run://{run['project_ref']}/{run['run_id']}",
        }
        path = self.cell_root(project_id) / "manifest.json"
        _atomic_json(path, payload)
        envelope_path = self._write_task_envelope(project_id, run, payload)
        return {
            "status": "ADOPTED",
            "project_id": project_id,
            "manifest_path": str(path),
            "manifest_sha256": _sha_bytes(path.read_bytes()),
            "run_id": run["run_id"],
            "task_envelope_path": str(envelope_path),
        }

    def _write_task_envelope(
        self,
        project_id: str,
        run: Mapping[str, Any],
        manifest: Mapping[str, Any],
        *,
        checkpoint_id: str | None = None,
    ) -> Path:
        envelope = TaskEnvelope(
            task_id=str(run.get("task_id") or "UNVERIFIED"),
            project_id=project_id,
            run_id=str(run["run_id"]),
            objective=str(run.get("objective") or "UNVERIFIED"),
            acceptance_contract={"status": "UNVERIFIED"},
            current_checkpoint_id=checkpoint_id,
            allowed_scope={
                "workspace_root": str(manifest["workspace_root"]),
                "canonical_artifact_root": str(manifest["canonical_artifact_root"]),
                "project_memory_namespace": str(manifest["project_memory_namespace"]),
                "run_memory_namespace": str(manifest["run_memory_namespace"]),
            },
            forbidden_scope={
                "engine_source_root": str(self.engine_repo_root),
                "cross_project_cells": True,
                "credentials_in_remote_context": True,
            },
            governing_sources=(str(self.governing_contract),),
            current_runtime_facts={"engine_binding": dict(manifest.get("engine_binding") or {})},
            known_good_state={},
            blockers=(), dependencies=(), desired_outputs=(), deployment_required=False,
        )
        path = self.cell_root(project_id) / "task-envelope.json"
        _atomic_json(path, envelope.to_payload())
        return path

    def load_manifest(self, project_id: str) -> dict[str, Any]:
        path = self.cell_root(project_id) / "manifest.json"
        if not path.is_file():
            raise ProjectCellContractError(f"project cell is not adopted: {project_id}")
        data = _read_json(path)
        if data.get("project_id") != project_id:
            raise ProjectCellContractError("manifest Project identity mismatch")
        return data

    def _repo_state(self, project_id: str) -> dict[str, Any]:
        manifest = self.load_manifest(project_id)
        raw = manifest.get("repository_root")
        if raw is None:
            return {"branch": None, "commit": None, "dirty_files": []}
        repo = Path(str(raw))
        branch = self._git(repo, "branch", "--show-current").stdout.strip() or None
        commit = self._git(repo, "rev-parse", "HEAD").stdout.strip() or None
        status = self._git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
        dirty: list[str] = []
        for line in status.splitlines():
            if len(line) < 4:
                continue
            name = line[3:].strip('"')
            if " -> " in name:
                name = name.split(" -> ", 1)[1]
            dirty.append(name)
        return {"branch": branch, "commit": commit, "dirty_files": sorted(set(dirty))}

    def checkpoint(
        self,
        project_id: str,
        *,
        task_id: str | None = None,
        objective: str | None = None,
        phase: str | None = None,
        completed: Sequence[str] = (),
        in_progress: Sequence[str] = (),
        blocked: Sequence[str] = (),
        pending: Sequence[str] = (),
        decisions: Sequence[str] = (),
        next_actions: Sequence[str] = (),
    ) -> dict[str, Any]:
        manifest = self.load_manifest(project_id)
        run = self._current_run(project_id)
        task = task_id or str(run.get("task_id") or "UNVERIFIED")
        goal = objective or str(run.get("objective") or "UNVERIFIED")
        container = self.container_status(project_id)
        current_phase = phase or ("RUNNING" if container.get("running") else "STOPPED")
        remote_root = self.cell_root(project_id) / "remote"
        requests = tuple(sorted((remote_root / "requests").glob("*.json"))) if (remote_root / "requests").is_dir() else ()
        responses = tuple(sorted((remote_root / "responses").glob("*.json"))) if (remote_root / "responses").is_dir() else ()
        checkpoint_id = f"chk_{uuid4().hex}"
        runtime_state = {
            "running_services": [f"docker://{container['name']}"] if container.get("running") else [],
            "observed_routes": [key for key, value in dict(manifest.get("provider_permissions") or {}).items() if isinstance(value, dict) and value.get("allowed") is True],
            "observed_failures": [],
            "container": container,
        }
        record = ProjectCellCheckpoint(
            checkpoint_id=checkpoint_id,
            project_id=project_id,
            run_id=str(run["run_id"]),
            task_id=task,
            timestamp=_now(),
            phase=current_phase,
            objective=goal,
            repo_state=self._repo_state(project_id),
            runtime_state=runtime_state,
            completed=tuple(completed),
            in_progress=tuple(in_progress),
            blocked=tuple(blocked),
            pending=tuple(pending),
            artifacts=(),
            decisions=tuple(decisions),
            remote_assistance={
                "requests_sent": [path.stem for path in requests],
                "responses_integrated": [path.stem for path in responses],
                "responses_pending": [],
            },
            next_actions=tuple(next_actions),
            do_not_repeat=("DO_NOT_REPEAT_VERIFIED_WORK_WITHOUT_INVALIDATION",),
            do_not_touch=("OTHER_PROJECT_CELLS", "BIELLA_ENGINE_SOURCE_FROM_CUSTOMER_RUNTIME"),
        )
        path = self.cell_root(project_id) / "checkpoints" / f"{checkpoint_id}.json"
        payload = record.to_payload()
        _atomic_json(path, payload)
        digest = _sha_bytes(path.read_bytes())
        pointer = {
            "schema": "biella.project_cell_checkpoint_pointer/v1",
            "project_id": project_id,
            "checkpoint_id": checkpoint_id,
            "checkpoint_sha256": digest,
            "path": str(path),
        }
        _atomic_json(self.cell_root(project_id) / "latest-checkpoint.json", pointer)
        self._write_task_envelope(
            project_id, self._current_run(project_id), self.load_manifest(project_id),
            checkpoint_id=checkpoint_id,
        )
        return {"status": "CHECKPOINTED", "checkpoint_id": checkpoint_id, "checkpoint_path": str(path), "checkpoint_sha256": digest}

    def latest_checkpoint(self, project_id: str) -> dict[str, Any]:
        pointer_path = self.cell_root(project_id) / "latest-checkpoint.json"
        if not pointer_path.is_file():
            raise ProjectCellContractError(f"project cell has no checkpoint: {project_id}")
        pointer = _read_json(pointer_path)
        if pointer.get("project_id") != project_id:
            raise ProjectCellContractError("checkpoint pointer Project identity mismatch")
        path = Path(str(pointer.get("path") or ""))
        if not path.is_file() or _sha_bytes(path.read_bytes()) != pointer.get("checkpoint_sha256"):
            raise ProjectCellContractError("checkpoint pointer failed exact digest readback")
        return _read_json(path)

    def remote_request(
        self,
        project_id: str,
        *,
        request_type: str,
        question_or_action: str,
        required_output: Mapping[str, Any],
        current_verified_facts: Sequence[str] = (),
        relevant_files_or_snippets: Sequence[str] = (),
        blockers: Sequence[str] = (),
        constraints: Sequence[str] = (),
        do_not_assume: Sequence[str] = (),
        online_capabilities_allowed: Sequence[str] = ("web_search",),
        return_format: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        checkpoint = self.latest_checkpoint(project_id)
        request_id = f"req_{uuid4().hex}"
        record = RemoteAssistanceRequest(
            request_id=request_id,
            project_id=project_id,
            run_id=str(checkpoint["run_id"]),
            task_id=str(checkpoint["task_id"]),
            checkpoint_id=str(checkpoint["checkpoint_id"]),
            request_type=request_type,
            question_or_action=question_or_action,
            required_output=required_output,
            current_verified_facts=tuple(current_verified_facts),
            relevant_files_or_snippets=tuple(relevant_files_or_snippets),
            blockers=tuple(blockers),
            constraints=tuple(constraints),
            do_not_assume=tuple(do_not_assume),
            online_capabilities_allowed=tuple(online_capabilities_allowed),
            return_format={} if return_format is None else return_format,
        )
        path = self.cell_root(project_id) / "remote" / "requests" / f"{request_id}.json"
        _atomic_json(path, record.to_payload())
        return {
            "status": "QUEUED",
            "request_id": request_id,
            "request_path": str(path),
            "request_sha256": _sha_bytes(path.read_bytes()),
        }

    def integrate_response(self, project_id: str, response_path: Path) -> dict[str, Any]:
        response = _read_json(Path(response_path))
        if response.get("project_id") != project_id:
            raise ProjectCellContractError("remote response crossed Project scope")
        request_id = str(response.get("request_id") or "")
        request_path = self.cell_root(project_id) / "remote" / "requests" / f"{request_id}.json"
        if not request_path.is_file():
            raise ProjectCellContractError("remote response request identity is unknown")
        request = _read_json(request_path)
        for key in ("project_id", "run_id", "task_id", "request_id"):
            if response.get(key) != request.get(key):
                raise ProjectCellContractError(f"remote response {key} does not match request")
        record = RemoteAssistanceResponse(
            response_id=str(response.get("response_id") or ""), request_id=request_id,
            project_id=project_id, run_id=str(response.get("run_id") or ""),
            task_id=str(response.get("task_id") or ""), status=str(response.get("status") or ""),
            findings=tuple(response.get("findings") or ()),
            actions_performed=tuple(response.get("actions_performed") or ()),
            artifacts=tuple(response.get("artifacts") or ()),
            citations_or_sources=tuple(response.get("citations_or_sources") or ()),
            unresolved=tuple(response.get("unresolved") or ()),
            suggested_next_actions=tuple(response.get("suggested_next_actions") or ()),
            confidence_or_verification_state=dict(response.get("confidence_or_verification_state") or {}),
        )
        target = self.cell_root(project_id) / "remote" / "responses" / f"{record.response_id}.json"
        _atomic_json(target, record.to_payload())
        return {"status": "INTEGRATED", "response_id": record.response_id, "response_path": str(target), "response_sha256": _sha_bytes(target.read_bytes())}

    def add_blocker(
        self, project_id: str, *, task_id: str, category: str, description: str,
        observed_evidence: Sequence[str] = (), blocks: Sequence[str] = (),
        independent_work_remaining: Sequence[str] = (), suggested_provider: str | None = None,
        status: str = "OPEN",
    ) -> dict[str, Any]:
        self.load_manifest(project_id)
        blocker_id = f"blk_{uuid4().hex}"
        record = BlockerRecord(
            blocker_id=blocker_id, project_id=project_id, task_id=task_id,
            category=category, description=description,
            observed_evidence=tuple(observed_evidence), blocks=tuple(blocks),
            independent_work_remaining=tuple(independent_work_remaining),
            suggested_provider=suggested_provider, status=status,
        )
        path = self.cell_root(project_id) / "blockers" / f"{blocker_id}.json"
        _atomic_json(path, record.to_payload())
        return {"status": "RECORDED", "blocker_id": blocker_id, "blocker_path": str(path), "blocker_sha256": _sha_bytes(path.read_bytes())}

    def status(self, project_id: str) -> dict[str, Any]:
        manifest_path = self.cell_root(project_id) / "manifest.json"
        run_path = self.cell_root(project_id) / "current-run.json"
        result: dict[str, Any] = {
            "project_id": project_id,
            "adopted": manifest_path.is_file(),
            "container": self.container_status(project_id),
        }
        if manifest_path.is_file():
            result["manifest"] = _read_json(manifest_path)
            result["manifest_sha256"] = _sha_bytes(manifest_path.read_bytes())
        if run_path.is_file():
            result["run"] = _read_json(run_path)
        try:
            result["checkpoint"] = self.latest_checkpoint(project_id)
        except ProjectCellContractError:
            result["checkpoint"] = None
        remote = self.cell_root(project_id) / "remote"
        result["remote_requests"] = len(list((remote / "requests").glob("*.json"))) if (remote / "requests").is_dir() else 0
        result["remote_responses"] = len(list((remote / "responses").glob("*.json"))) if (remote / "responses").is_dir() else 0
        return result


def _json_arg(raw: str, name: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProjectCellContractError(f"{name} must be valid JSON") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="biella-project-cell")
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--sandboxes-root", default=str(DEFAULT_SANDBOXES_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("adopt", "status"):
        cmd = sub.add_parser(name); cmd.add_argument("project_id")
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("project_id"); checkpoint.add_argument("--task-id", default="UNVERIFIED")
    checkpoint.add_argument("--objective", default="UNVERIFIED"); checkpoint.add_argument("--phase")
    request = sub.add_parser("remote-request")
    request.add_argument("project_id"); request.add_argument("--request-type", required=True)
    request.add_argument("--question", required=True); request.add_argument("--required-output-json", default="{}")
    request.add_argument("--blocker", action="append", default=[])
    integrate = sub.add_parser("integrate-response")
    integrate.add_argument("project_id"); integrate.add_argument("response_file")
    blocker = sub.add_parser("blocker")
    blocker.add_argument("project_id"); blocker.add_argument("--task-id", required=True)
    blocker.add_argument("--category", required=True); blocker.add_argument("--description", required=True)
    blocker.add_argument("--suggested-provider")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manager = ProjectCellRuntime(
        state_root=Path(args.state_root), sandboxes_root=Path(args.sandboxes_root),
    )
    if args.command == "adopt":
        result = manager.adopt(args.project_id)
    elif args.command == "status":
        result = manager.status(args.project_id)
    elif args.command == "checkpoint":
        result = manager.checkpoint(
            args.project_id, task_id=args.task_id, objective=args.objective, phase=args.phase,
        )
    elif args.command == "remote-request":
        required = _json_arg(args.required_output_json, "required-output-json")
        if not isinstance(required, dict):
            raise ProjectCellContractError("required-output-json must decode to an object")
        result = manager.remote_request(
            args.project_id, request_type=args.request_type,
            question_or_action=args.question, required_output=required,
            blockers=tuple(args.blocker),
        )
    elif args.command == "integrate-response":
        result = manager.integrate_response(args.project_id, Path(args.response_file))
    elif args.command == "blocker":
        result = manager.add_blocker(
            args.project_id, task_id=args.task_id, category=args.category,
            description=args.description, suggested_provider=args.suggested_provider,
        )
    else:
        raise ProjectCellContractError(f"unsupported command: {args.command}")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
