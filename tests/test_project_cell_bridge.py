from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OPS = ROOT / "ops/project-cell"
for path in (SRC, OPS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from minitz_os.engine.project_cell import (
    ProjectCellContractError,
    ProjectCellManifest,
    RemoteAssistanceRequest,
    TaskEnvelope,
)
import minitz_project_cell_runtime as runtime


def _manifest(tmp_path: Path, project_id: str = "site-a") -> ProjectCellManifest:
    workspace = tmp_path / project_id / "workspace"
    artifacts = tmp_path / project_id / "artifacts"
    cache = tmp_path / project_id / "cache"
    for path in (workspace, artifacts, cache):
        path.mkdir(parents=True, exist_ok=True)
    return ProjectCellManifest(
        project_id=project_id,
        project_name=project_id,
        project_type="customer",
        workspace_root=str(workspace),
        repository_root=None,
        canonical_artifact_root=str(artifacts),
        project_memory_namespace=f"project-cell://{project_id}/memory",
        run_memory_namespace=f"project-cell://{project_id}/runs",
        cache_root=str(cache),
        historical_evidence_root=None,
        deployment_targets=("UNKNOWN",),
        execution_nodes=(),
        provider_permissions={"chatgpt_remote": {"allowed": True}},
        acceptance_authority="Mahdi Taghdisi",
    )


def test_manifest_rejects_engine_root_and_cache_as_canonical(tmp_path: Path):
    workspace = tmp_path / "workspace"
    cache = tmp_path / "cache"
    workspace.mkdir(); cache.mkdir()
    with pytest.raises(ProjectCellContractError, match="Engine source root"):
        ProjectCellManifest(
            project_id="site-a", project_name="Site A", project_type="customer",
            workspace_root=str(ROOT), repository_root=None,
            canonical_artifact_root=str(tmp_path / "artifacts"),
            project_memory_namespace="project-cell://site-a/memory",
            run_memory_namespace="project-cell://site-a/runs", cache_root=str(cache),
            historical_evidence_root=None, deployment_targets=("UNKNOWN",),
            execution_nodes=(), provider_permissions={}, acceptance_authority="Mahdi Taghdisi",
        )
    with pytest.raises(ProjectCellContractError, match="cache_root"):
        ProjectCellManifest(
            project_id="site-a", project_name="Site A", project_type="customer",
            workspace_root=str(workspace), repository_root=None,
            canonical_artifact_root=str(cache), project_memory_namespace="project-cell://site-a/memory",
            run_memory_namespace="project-cell://site-a/runs", cache_root=str(cache),
            historical_evidence_root=None, deployment_targets=("UNKNOWN",),
            execution_nodes=(), provider_permissions={}, acceptance_authority="Mahdi Taghdisi",
        )


def test_task_envelope_and_remote_request_are_project_scoped_and_credential_free(tmp_path: Path):
    envelope = TaskEnvelope(
        task_id="task-1", project_id="site-a", run_id="run-1",
        objective="Resolve the current isolated blocker.",
        acceptance_contract={"status": "validated"}, current_checkpoint_id="chk-1",
        allowed_scope={"paths": ["workspace"]}, forbidden_scope={"paths": ["other-projects"]},
    )
    request = RemoteAssistanceRequest(
        request_id="req-1", project_id="site-a", run_id="run-1", task_id="task-1",
        checkpoint_id="chk-1", request_type="ONLINE_INFORMATION_REQUIRED",
        question_or_action="Check current vendor documentation for the observed error.",
        required_output={"findings": "list"}, current_verified_facts=("error observed",),
        relevant_files_or_snippets=(), blockers=("vendor behavior unknown",),
        constraints=("do not change project requirements",), do_not_assume=("credentials",),
        online_capabilities_allowed=("web_search",), return_format={"status": "string"},
    )
    assert envelope.project_id == request.project_id == "site-a"
    with pytest.raises(ProjectCellContractError, match="credential"):
        RemoteAssistanceRequest(
            request_id="req-2", project_id="site-a", run_id="run-1", task_id="task-1",
            checkpoint_id="chk-1", request_type="ONLINE_INFORMATION_REQUIRED",
            question_or_action="Use token=secret-value to inspect the API.", required_output={},
            current_verified_facts=(), relevant_files_or_snippets=(), blockers=(),
            constraints=(), do_not_assume=(), online_capabilities_allowed=("web_search",), return_format={},
        )


def _sandbox_project(root: Path, project_id: str) -> Path:
    cell = root / project_id
    workspace = cell / "workspace"
    repo = workspace / "repo"
    for path in (workspace, cell / "cache", cell / "logs", cell / "tmp", cell / "home"):
        path.mkdir(parents=True, exist_ok=True)
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    (repo / "README.md").write_text("project\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    (cell / "project.json").write_text(json.dumps({
        "id": project_id, "repo_url": "https://github.com/example/project.git",
        "cloudflare_account_id": "account", "allowed_capabilities": [],
        "image": "worker:test", "default_gpu_mode": "none",
    }) + "\n", encoding="utf-8")
    return repo


def test_runtime_adopts_project_without_copying_source_or_credentials(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"
    repo = _sandbox_project(sandboxes, "site-a")
    state_root = tmp_path / "project-cells"
    manager = runtime.ProjectCellRuntime(
        state_root=state_root, sandboxes_root=sandboxes,
        engine_repo_root=Path("/root/minitz/repos/minitz-engine"),
    )
    monkeypatch.setattr(manager, "container_status", lambda _project_id: {
        "exists": True, "running": True, "name": "psb-site-a", "image": "worker:test"
    })
    result = manager.adopt("site-a")
    manifest = json.loads(Path(result["manifest_path"]).read_text())
    assert manifest["project_id"] == "site-a"
    assert manifest["repository_root"] == str(repo.resolve())
    assert manifest["workspace_root"] == str((sandboxes / "site-a/workspace").resolve())
    assert manifest["canonical_artifact_root"] != manifest["cache_root"]
    encoded = json.dumps(manifest)
    assert "README.md" not in encoded
    assert "GITHUB_TOKEN" not in encoded
    assert Path(result["manifest_path"]).is_relative_to(state_root / "site-a")


def test_runtime_checkpoint_is_durable_scoped_and_resumable(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"
    repo = _sandbox_project(sandboxes, "site-a")
    state_root = tmp_path / "project-cells"
    manager = runtime.ProjectCellRuntime(state_root=state_root, sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda _project_id: {
        "exists": True, "running": True, "name": "psb-site-a", "image": "worker:test"
    })
    manager.adopt("site-a")
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    checkpoint = manager.checkpoint("site-a", task_id="UNVERIFIED", objective="UNVERIFIED")
    payload = json.loads(Path(checkpoint["checkpoint_path"]).read_text())
    assert payload["project_id"] == "site-a"
    assert payload["repo_state"]["branch"] == "main"
    assert payload["repo_state"]["commit"]
    assert payload["repo_state"]["dirty_files"] == ["README.md"]
    latest = manager.latest_checkpoint("site-a")
    assert latest["checkpoint_id"] == payload["checkpoint_id"]


def test_runtime_remote_request_never_crosses_project_namespace(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"
    _sandbox_project(sandboxes, "site-a")
    _sandbox_project(sandboxes, "site-b")
    manager = runtime.ProjectCellRuntime(state_root=tmp_path / "cells", sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda project_id: {
        "exists": True, "running": True, "name": f"psb-{project_id}", "image": "worker:test"
    })
    for project_id in ("site-a", "site-b"):
        manager.adopt(project_id)
        manager.checkpoint(project_id, task_id="UNVERIFIED", objective="UNVERIFIED")
    result = manager.remote_request(
        "site-a", request_type="ONLINE_INFORMATION_REQUIRED",
        question_or_action="Check current documentation for this scoped blocker.",
        required_output={"findings": "list"}, blockers=("external docs needed",),
    )
    path = Path(result["request_path"])
    assert path.is_relative_to(tmp_path / "cells/site-a")
    assert not path.is_relative_to(tmp_path / "cells/site-b")
    payload = json.loads(path.read_text())
    assert payload["project_id"] == "site-a"
    assert "site-b" not in json.dumps(payload)


def test_public_engine_exports_project_cell_contracts():
    import minitz_os.engine as minitz
    for name in (
        "ProjectCellManifest", "TaskEnvelope", "ProjectCellCheckpoint",
        "BlockerRecord", "RemoteAssistanceRequest", "RemoteAssistanceResponse",
    ):
        assert name in minitz.__all__
        assert getattr(minitz, name) is not None


def test_installer_exposes_project_cell_cli_on_source_refresh():
    installer = (ROOT / "ops/local-ai/install-minitz-ai.sh").read_text(encoding="utf-8")
    assert 'PROJECT_CELL_LINK="/usr/local/bin/minitz-project-cell"' in installer
    assert '../project-cell/minitz-project-cell' in installer
    assert 'install -o root -g root -m 755 "$SOURCE_DIR/../project-cell/minitz-project-cell" "$INSTALL_DIR/minitz-project-cell"' in installer
    assert 'ln -s "$INSTALL_DIR/minitz-project-cell" "$PROJECT_CELL_LINK"' in installer
    assert 'PROJECT_CELL_SOURCE=' not in installer


def test_adoption_binds_cell_to_native_minitz_project_task_run_store(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"
    _sandbox_project(sandboxes, "site-a")
    state_root = tmp_path / "project-cells"
    manager = runtime.ProjectCellRuntime(state_root=state_root, sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda _project_id: {
        "exists": True, "running": True, "name": "psb-site-a", "image": "worker:test"
    })
    result = manager.adopt("site-a")
    manifest = json.loads(Path(result["manifest_path"]).read_text())
    binding = manifest["engine_binding"]
    assert binding["project_ref"].startswith("prj_")
    assert binding["task_ref"].startswith("task://prj_")
    assert binding["run_ref"].startswith("run://prj_")
    assert (state_root / "engine.sqlite3").is_file()
    access_path = state_root / "engine-access/site-a.json"
    assert access_path.is_file() and access_path.stat().st_mode & 0o777 == 0o600
    assert "paccess_" not in json.dumps(manifest)
    assert "paccess_" not in Path(result["manifest_path"]).read_text()
    status = manager.status("site-a")
    assert status["manifest"]["engine_binding"] == binding


def test_adoption_persists_task_envelope_and_checkpoint_advances_pointer(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"
    _sandbox_project(sandboxes, "site-a")
    state_root = tmp_path / "cells"
    manager = runtime.ProjectCellRuntime(state_root=state_root, sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda _project_id: {
        "exists": True, "running": True, "name": "psb-site-a", "image": "worker:test"
    })
    result = manager.adopt("site-a")
    envelope_path = state_root / "site-a/task-envelope.json"
    assert envelope_path.is_file()
    before = json.loads(envelope_path.read_text())
    assert before["schema"] == "minitz.task_envelope/v1"
    assert before["project_id"] == "site-a"
    assert before["run_id"] == result["run_id"]
    assert before["task_id"] == "UNVERIFIED"
    assert before["objective"] == "UNVERIFIED"
    assert before["current_checkpoint_id"] is None
    checkpoint = manager.checkpoint("site-a", task_id="UNVERIFIED", objective="UNVERIFIED")
    after = json.loads(envelope_path.read_text())
    assert after["current_checkpoint_id"] == checkpoint["checkpoint_id"]
    assert "paccess_" not in envelope_path.read_text()


def test_remote_response_wrong_project_is_rejected(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"
    _sandbox_project(sandboxes, "site-a"); _sandbox_project(sandboxes, "site-b")
    manager = runtime.ProjectCellRuntime(state_root=tmp_path / "cells", sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda project_id: {
        "exists": True, "running": True, "name": f"psb-{project_id}", "image": "worker:test"
    })
    manager.adopt("site-a"); manager.checkpoint("site-a", task_id="UNVERIFIED", objective="UNVERIFIED")
    request = manager.remote_request("site-a", request_type="ONLINE_INFORMATION_REQUIRED", question_or_action="Check docs.", required_output={})
    req = json.loads(Path(request["request_path"]).read_text())
    response = tmp_path / "response.json"
    response.write_text(json.dumps({
        "response_id":"resp-1","request_id":req["request_id"],"project_id":"site-b",
        "run_id":req["run_id"],"task_id":req["task_id"],"status":"SUCCESS","findings":[],
        "actions_performed":[],"artifacts":[],"citations_or_sources":[],"unresolved":[],
        "suggested_next_actions":[],"confidence_or_verification_state":{},
    }) + "\n")
    with pytest.raises(ProjectCellContractError, match="crossed Project scope"):
        manager.integrate_response("site-a", response)


def test_blocker_record_stays_in_originating_cell(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"; _sandbox_project(sandboxes, "site-a")
    manager = runtime.ProjectCellRuntime(state_root=tmp_path / "cells", sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda _project_id: {"exists":True,"running":True,"name":"psb-site-a","image":"worker:test"})
    manager.adopt("site-a")
    result = manager.add_blocker("site-a", task_id="UNVERIFIED", category="ONLINE_INFORMATION", description="Current external behavior is unknown.", independent_work_remaining=("Continue local validation.",), suggested_provider="chatgpt_remote")
    path = Path(result["blocker_path"])
    assert path.is_relative_to(tmp_path / "cells/site-a")
    payload = json.loads(path.read_text())
    assert payload["project_id"] == "site-a"
    assert payload["status"] == "OPEN"


def test_project_cell_state_and_native_engine_database_are_root_only(tmp_path: Path, monkeypatch):
    sandboxes = tmp_path / "sandboxes"; _sandbox_project(sandboxes, "site-a")
    state_root = tmp_path / "cells"
    manager = runtime.ProjectCellRuntime(state_root=state_root, sandboxes_root=sandboxes)
    monkeypatch.setattr(manager, "container_status", lambda _project_id: {"exists":True,"running":True,"name":"psb-site-a","image":"worker:test"})
    manager.adopt("site-a")
    manager.checkpoint("site-a", task_id="UNVERIFIED", objective="UNVERIFIED")
    assert state_root.stat().st_mode & 0o777 == 0o700
    assert (state_root / "site-a").stat().st_mode & 0o777 == 0o700
    assert (state_root / "site-a/checkpoints").stat().st_mode & 0o777 == 0o700
    assert (state_root / "engine.sqlite3").stat().st_mode & 0o777 == 0o600
    assert (state_root / "site-a/manifest.json").stat().st_mode & 0o777 == 0o600
