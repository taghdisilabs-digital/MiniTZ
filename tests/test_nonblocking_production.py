from pathlib import Path
import importlib
import json
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/local-ai"))
import minitz_production_evidence as evidence
import minitz_customer_handoff as handoff


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def repository(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    p = repo / "docs/project-state/03_MINITZ_CURRENT_STATE.md"
    p.parent.mkdir(parents=True); p.write_text("current\n")
    git(repo, "add", "."); git(repo, "commit", "-qm", "base")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-qu", "origin", "main")
    return repo, remote


def test_checkpoint_uses_mockable_sleep_boundary_not_real_systemd(tmp_path, monkeypatch):
    repo, _ = repository(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    (runtime / "runtime.json").write_text('{"task_id":"D05-01"}')
    manager = handoff.MiniTZCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", lambda: {name: {"active": False, "enabled": "disabled"} for name in handoff.PROTECTED_SERVICES})
    calls = []
    monkeypatch.setattr(manager, "sleep_services", lambda: calls.append("sleep"))
    def forbidden(*args):
        raise AssertionError("checkpoint bypassed sleep boundary and reached host service controls")
    monkeypatch.setattr(manager, "set_active_state", forbidden)
    monkeypatch.setattr(manager, "set_enabled_state", forbidden)
    manager.checkpoint()
    assert calls == ["sleep"]


def test_sleep_boundary_excludes_public_website_and_control_spine():
    assert "minitz-public-site.service" not in handoff.PROTECTED_SERVICES
    assert "minitz-control-gateway.service" not in handoff.PROTECTED_SERVICES
    assert "caddy.service" not in handoff.PROTECTED_SERVICES
    assert "minitz-website-live-deploy.path" not in handoff.PROTECTED_SERVICES


def test_owner_sleep_entrypoint_uses_canonical_warm_lifecycle_boundary():
    script = ROOT / "ops/local-ai/minitz-owner-sleep"
    assert script.is_file()
    text = script.read_text()
    assert "/usr/local/lib/minitz-ai/minitz_lifecycle.py sleep" in text
    assert "minitz_customer_handoff.py checkpoint" not in text
    for forbidden in ("minitz-public-site.service", "caddy.service", "minitz-website-live-deploy.path"):
        assert forbidden not in text


def test_local_continuity_commit_does_not_need_remote_transport(tmp_path, monkeypatch):
    repo, _ = repository(tmp_path)
    (repo / "docs/project-state/03_MINITZ_CURRENT_STATE.md").write_text("upgraded\n")
    assert hasattr(evidence, "persist_local_continuity")
    original = evidence._git
    def local_only(root, *args, **kwargs):
        assert args[0] not in {"fetch", "push", "ls-remote"}
        return original(root, *args, **kwargs)
    monkeypatch.setattr(evidence, "_git", local_only)
    result = evidence.persist_local_continuity(repo, "D05-01")
    assert result["commit"] == git(repo, "rev-parse", "HEAD")
    assert git(repo, "status", "--porcelain") == ""


def test_remote_transport_loss_is_not_source_divergence(tmp_path, monkeypatch):
    repo, _ = repository(tmp_path)
    original = evidence._git
    def offline(root, *args, **kwargs):
        if args[0] == "fetch":
            return subprocess.CompletedProcess(args, 1, "", "temporary network outage")
        return original(root, *args, **kwargs)
    monkeypatch.setattr(evidence, "_git", offline)
    assert hasattr(evidence, "SourceTransportError")
    with pytest.raises(evidence.SourceTransportError):
        evidence.assert_remote_source_current(repo)


def test_publication_retry_persists_and_coalesces_without_task_replay(tmp_path, monkeypatch):
    repo, remote = repository(tmp_path)
    spec = importlib.util.find_spec("minitz_publication")
    assert spec is not None
    pub = importlib.import_module("minitz_publication")
    first = {"commit": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}")}
    pub.request_publication(repo, "D05-01", first)
    def outage(*args):
        raise RuntimeError("Drive unavailable")
    monkeypatch.setattr(pub, "publish_drive_revision", outage)
    result = pub.drain_once(repo, force_drive=True)
    assert result["status"] == "PENDING"
    source = repo / "docs/project-state/03_MINITZ_CURRENT_STATE.md"
    source.write_text("next task\n")
    git(repo, "add", str(source.relative_to(repo))); git(repo, "commit", "-qm", "next")
    second = {"commit": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}")}
    pub.request_publication(repo, "D06-01", second)
    observed = []
    monkeypatch.setattr(pub, "publish_drive_revision", lambda repo, commit: observed.append(commit) or {"verified": True})
    assert pub.drain_once(repo, force_drive=True)["status"] == "SYNCED"
    assert observed == [second["commit"]]
    assert pub.read_publication(repo)["commit"] == second["commit"]
    assert subprocess.check_output(["git", "--git-dir", str(remote), "rev-parse", "main"], text=True).strip() == second["commit"]


def test_persistence_has_no_forever_publication_retry_loop():
    import inspect
    import minitz_production_runner as runner
    text = inspect.getsource(runner._persist_until_success)
    assert "while True" not in text
    assert "time.sleep" not in text


def test_next_hundred_map_has_exact_source_bound_tasks():
    path = ROOT / "docs/task-program/D_NEXT_100_TASKS.json"
    assert path.is_file()
    payload = json.loads(path.read_text())
    tasks = payload["tasks"]
    assert len(tasks) == len({t["task_id"] for t in tasks}) == 100
    assert tasks[0]["task_id"] == "D05-01"
    assert tasks[-1]["task_id"] == "D23-05"
    assert payload["registry_is_queue"] is False
    for task in tasks:
        assert task["objective"] and task["deliverable"] and task["validation"]
        assert task["source_refs"] and task["execution_root"]
        assert (ROOT / task["execution_root"]).is_dir()
        assert "status" not in task
        for ref in task["source_refs"]:
            assert (ROOT / ref["path"]).is_file()


def test_runner_injects_only_active_task_execution_map():
    import minitz_execution_map as mapping
    canonical = Path("/root/minitz/repos/minitz-engine")
    program = Path("/root/minitz/analysis/live_audit/TASK_PROGRAM.json")
    if not canonical.is_dir() or not program.is_file():
        pytest.skip("canonical MiniTZ Task Program is not mounted")
    text = mapping.task_context(canonical, "UNIFY-04")
    assert "UNIFY-04" in text
    assert "ENDUSER-SPEC-01" not in text
    assert len(text) < 14000
    assert mapping.task_working_directory(canonical, canonical / "projects/minitz-games", "OS-SPEC-01") == canonical


def test_minitz_task_execution_projection_excludes_historical_completion():
    import minitz_execution_map as mapping
    canonical = Path("/root/minitz/repos/minitz-engine")
    program = Path("/root/minitz/analysis/live_audit/TASK_PROGRAM.json")
    if not canonical.is_dir() or not program.is_file():
        pytest.skip("canonical MiniTZ Task Program is not mounted")
    text = mapping.task_context(canonical, "UNIFY-04")
    body = text.split("CURRENT_MINITZ_TASK\n", 1)[1].split("\nEND_CURRENT_MINITZ_TASK", 1)[0]
    payload = json.loads(body.split("\n", 1)[1])
    task = payload["task"]
    assert "completion" not in task
    assert task["task_record_sha256"]
    assert task["task_id"] == "UNIFY-04"


def test_validated_task_files_are_committed_without_another_model_turn(tmp_path):
    repo, _ = repository(tmp_path)
    task = repo / "projects/minitz-games/validated.txt"
    task.parent.mkdir(parents=True); task.write_text("validated task output\n")
    unrelated = repo / "unrelated.txt"; unrelated.write_text("do not include\n")
    result = evidence.TaskResult("D05-01", "COMPLETE", "validated", ("runtime evidence",))
    final = evidence.enforce_clean_completion_boundary(repo, result, owned_files={str(task.relative_to(repo)): __import__("hashlib").sha256(task.read_bytes()).hexdigest()})
    assert final.status == "COMPLETE"
    assert git(repo, "show", "HEAD:projects/minitz-games/validated.txt") == "validated task output"
    assert unrelated.read_text() == "do not include\n"
    assert git(repo, "status", "--porcelain") == "?? unrelated.txt"


def test_resume_clears_pause_request_before_starting_production(tmp_path, monkeypatch):
    repo, _ = repository(tmp_path)
    runtime = tmp_path / "runtime"; runtime.mkdir()
    (runtime / "runtime.json").write_text('{"task_id":"D05-01"}')
    manager = handoff.MiniTZCustomerHandoff(repo, runtime, tmp_path / "handoff")
    monkeypatch.setattr(manager, "service_states", lambda: {name: {"active": True, "enabled": "enabled"} for name in handoff.PROTECTED_SERVICES})
    monkeypatch.setattr(manager, "cooperative_pause", lambda: None)
    monkeypatch.setattr(manager, "sleep_services", lambda: None)
    manager.checkpoint()
    manager.pause_request_path.write_text('{}')
    manager.pause_ack_path.write_text('{}')
    monkeypatch.setattr(manager, "running_customer_count", lambda: 0)
    monkeypatch.setattr(manager, "verify_source_alignment", lambda: None)
    monkeypatch.setattr(manager, "set_enabled_state", lambda *args: None)
    def start(name, active):
        if name == "minitz-production.service" and active:
            assert not manager.pause_request_path.exists()
    monkeypatch.setattr(manager, "set_active_state", start)
    assert manager.resume()["status"] == "RESTORED"


def test_bootstrap_network_failure_keeps_valid_local_source(tmp_path):
    repo, _ = repository(tmp_path)
    git(repo, "remote", "set-url", "origin", str(tmp_path / "unavailable-remote.git"))
    import os
    env = {**os.environ, "MINITZ_REPO_ROOT": str(repo), "MINITZ_SOURCE_SYNC_INSTALLER": ""}
    outcome = subprocess.run([str(ROOT / "ops/local-ai/minitz-source-sync.sh")], capture_output=True, text=True, env=env)
    assert outcome.returncode == 0, outcome.stderr
    assert "REMOTE_UNAVAILABLE_LOCAL_CONTINUATION" in outcome.stdout


def test_known_remote_conflict_never_overwrites_drive_with_stale_revision(tmp_path, monkeypatch):
    import minitz_publication as pub
    repo, remote = repository(tmp_path)
    identity = {"commit": git(repo, "rev-parse", "HEAD"), "tree": git(repo, "rev-parse", "HEAD^{tree}")}
    pub.request_publication(repo, "D05-01", identity)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(other)], check=True)
    git(other, "config", "user.name", "Test"); git(other, "config", "user.email", "test@example.invalid")
    (other / "new-authority.txt").write_text("newer remote authority\n")
    git(other, "add", "."); git(other, "commit", "-qm", "newer authority"); git(other, "push", "-q", "origin", "main")
    called = []
    monkeypatch.setattr(pub, "publish_drive_revision", lambda *_args: called.append(True) or {"verified": True})
    assert pub.drain_once(repo, force_drive=True)["status"] == "RECONCILIATION_REQUIRED"
    assert called == []
    assert pub.read_publication(repo)["last_receipt"]["source_state"] == "RECONCILIATION_REQUIRED"


def test_execution_creates_runtime_readable_files_without_global_umask_change(tmp_path, monkeypatch):
    import minitz_production_runner as runner
    target = tmp_path / "generated-source.txt"
    output = tmp_path / "result.json"
    code = f"from pathlib import Path; Path({str(target)!r}).write_text('source'); Path({str(output)!r}).write_text('{{}}')"
    monkeypatch.setattr(runner.routing, "build_codex_command", lambda *_args, **_kwargs: [sys.executable, "-c", code])
    telemetry = runner.initial_runtime()
    import os
    previous_umask = os.umask(0o077)
    try:
        rc, _ = runner.invoke_structured("task", runner.routing.Route("gpt-reserve", "max"), tmp_path / "schema.json", output,
            tmp_path / "stdout.log", tmp_path / "stderr.log", tmp_path / "runtime.json", telemetry, cwd=tmp_path)
    finally:
        os.umask(previous_umask)
    assert rc == 0
    assert target.stat().st_mode & 0o777 == 0o644
