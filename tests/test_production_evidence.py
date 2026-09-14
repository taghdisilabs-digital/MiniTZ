from pathlib import Path
import importlib.util
import json
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
import biella_production_state as state
import biella_codex_routing as routing

MODULE = LOCAL_AI / "biella_production_evidence.py"
spec = importlib.util.spec_from_file_location("biella_production_evidence", MODULE)
assert spec and spec.loader
evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evidence
spec.loader.exec_module(evidence)


def fixture(root: Path):
    repo = root / "repo"; project = repo / "projects/biella-games"
    (repo / "docs/project-state").mkdir(parents=True); (project / "docs").mkdir(parents=True)
    (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").write_text("active_execution:\n  id: D01-030\n  state: PENDING\ngames:\n  completed_demo_tasks: 29\n  queued_successor: D01-030\n", encoding="utf-8")
    (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").write_text("task:\n  id: D01-030\n  project: Biella Games\n  section: demo01\n  class: hard\n  title: Rival combat\n  status: PENDING\n", encoding="utf-8")
    (project / "docs/PRODUCTION.md").write_text("# P\n\nStatus: `IN_PROGRESS`\nCurrent section: `demo01`\nCurrent task: `D01-030`\n\n## Section: demo01 | Demo | IN_PROGRESS\n\n- [x] D01-029 | hard | Prior | COMPLETE | prior\n- [ ] D01-030 | hard | Rival combat | PENDING | \n- [ ] D01-031 | hard | Interaction | PENDING | \n", encoding="utf-8")
    return repo, project


def write_result(path: Path, task_id: str, status: str, evidence_items=None):
    path.write_text(json.dumps({"task_id": task_id, "status": status, "summary": "done", "evidence": evidence_items or []}), encoding="utf-8")
    return path


def test_result_task_id_must_match(tmp_path: Path):
    path = write_result(tmp_path / "result.json", "D01-999", "COMPLETE", ["runtime pass"])
    with pytest.raises(ValueError, match="task_id mismatch"):
        evidence.parse_result(path, "D01-030")


def test_complete_requires_evidence(tmp_path: Path):
    path = write_result(tmp_path / "result.json", "D01-030", "COMPLETE", [])
    with pytest.raises(ValueError, match="evidence"):
        evidence.parse_result(path, "D01-030")


def test_service_style_typed_completion_resolves_active_repo_src_without_pythonpath(tmp_path: Path):
    import os, subprocess
    typed = {
        "kind": "VALIDATION", "task_id": "D01-030", "task_revision": 1,
        "task_digest": "0" * 64, "scope_ref": "task://test/D01-030",
        "evidence_ref": "test://runtime-pass", "evidence_sha256": "1" * 64,
        "implementation_ref": "test://implementation", "verdict": "PASS",
    }
    result_path = write_result(tmp_path / "typed.json", "D01-030", "COMPLETE", [typed])
    code = "import importlib.util,sys; from pathlib import Path; " + f"sys.path.insert(0,{str(LOCAL_AI)!r}); " + f"s=importlib.util.spec_from_file_location('service_evidence',{str(MODULE)!r}); " + "m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); " + "r=m.parse_result(Path(sys.argv[1]),'D01-030'); print(r.status)"
    env = dict(os.environ); env.pop("PYTHONPATH", None); env["BIELLA_REPO_ROOT"] = str(ROOT)
    proc = subprocess.run([sys.executable, "-I", "-c", code, str(result_path)], cwd="/", env=env, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "COMPLETE"


def test_provider_completion_record_digest_is_recomputed_at_admission(tmp_path: Path):
    from biella.validation import ValidationCompletionEvidence
    typed = {
        "kind": "VALIDATION", "task_id": "D01-030", "task_revision": 1,
        "task_digest": "0" * 64, "scope_ref": "task://test/D01-030/1",
        "evidence_ref": "test://runtime-pass", "evidence_sha256": "1" * 64,
        "implementation_ref": "test://implementation", "verdict": "PASS",
        "record_sha256": "f" * 64,
    }
    path = write_result(tmp_path / "typed-bad-self-digest.json", "D01-030", "COMPLETE", [typed])

    result = evidence.parse_result(path, "D01-030")

    admitted = json.loads(result.evidence[0])
    expected_input = dict(typed); expected_input.pop("record_sha256")
    expected = ValidationCompletionEvidence.from_mapping(expected_input).record_sha256
    assert admitted["record_sha256"] == expected
    assert admitted["record_sha256"] != typed["record_sha256"]


def test_complete_updates_project_and_active_task(tmp_path: Path):
    repo, project = fixture(tmp_path)
    result = evidence.TaskResult("D01-030", "COMPLETE", "done", ("runtime pass",))
    evidence.apply_result(repo, project, result, routing.Route("gpt-6-astra", "ultra"))
    assert state.find_task(state.load_project_production(project), "D01-030").status == "COMPLETE"
    assert state.load_active_task(repo).id == "D01-31"


def test_continue_does_not_advance(tmp_path: Path):
    repo, project = fixture(tmp_path)
    result = evidence.TaskResult("D01-030", "CONTINUE", "more work", ("partial",))
    evidence.apply_result(repo, project, result, routing.Route("gpt-6-astra", "ultra"))
    assert state.load_active_task(repo).id == "D01-30"


def test_continue_does_not_dirty_durable_state(tmp_path: Path):
    repo, project = fixture(tmp_path)
    before03 = (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_bytes()
    before04 = (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_bytes()
    result = evidence.TaskResult("D01-030", "CONTINUE", "more work", ("partial",))
    evidence.apply_result(repo, project, result, routing.Route("gpt-6-astra", "ultra"))
    assert (repo / "docs/project-state/03_BIELLA_CURRENT_STATE.md").read_bytes() == before03
    assert (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_bytes() == before04


def test_persist_continuity_commits_and_pushes_exact_main(tmp_path: Path):
    import subprocess
    repo, project = fixture(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    remote = tmp_path / "remote.git"; subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True); subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "main"], check=True)
    result = evidence.TaskResult("D01-030", "COMPLETE", "done", ("runtime pass",))
    evidence.apply_result(repo, project, result, routing.Route("gpt-6-astra", "ultra"))
    identity = evidence.persist_continuity(repo, "D01-030", publish_drive=False)
    local = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    remote_head = subprocess.check_output(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"], text=True).strip()
    assert identity["commit"] == local == remote_head
    assert subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True) == ""


def test_drive_publications_include_project_production():
    targets = dict(evidence.drive_publications(Path("/repo")))
    assert targets["docs/project-state/03_BIELLA_CURRENT_STATE.md"] == "gdrive:Biella/CURRENT/03_BIELLA_CURRENT_STATE.md"
    assert targets["docs/project-state/04_BIELLA_ACTIVE_TASK.md"] == "gdrive:Biella/CURRENT/04_BIELLA_ACTIVE_TASK.md"
    assert targets["projects/biella-games/docs/PRODUCTION.md"] == "gdrive:Biella/PROJECTS/GAMES/PRODUCTION.md"


def test_result_accepts_legacy_alias_for_canonical_expected(tmp_path: Path):
    path = write_result(tmp_path / "result.json", "D01-030", "COMPLETE", ["runtime pass"])
    result = evidence.parse_result(path, "D01-30")
    assert result.task_id == "D01-30"


def test_derived_ledger_publication_is_not_part_of_critical_drive_targets():
    critical = dict(evidence.drive_publications(Path("/repo")))
    derived = dict(evidence.derived_drive_publications(Path("/repo")))
    assert "docs/task-program/D_TASK_LEDGER.json" not in critical
    assert derived["docs/task-program/D_TASK_LEDGER.json"] == "gdrive:Biella/D_TASK_PROGRAM/D_TASK_LEDGER.json"
    assert derived["docs/task-program/D_TASK_MANIFEST.json"] == "gdrive:Biella/D_TASK_PROGRAM/D_TASK_MANIFEST.json"


def test_generated_task_ledger_is_allowed_continuity_output():
    assert "docs/task-program/D_TASK_LEDGER.json" in evidence._CONTINUITY_PATHS


def _source_pair(root: Path):
    import subprocess
    remote = root / "source-remote.git"
    repo = root / "source-local"
    other = root / "source-other"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    (repo / "source.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "main"], check=True)
    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(other)], check=True)
    subprocess.run(["git", "-C", str(other), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(other), "config", "user.email", "test@example.invalid"], check=True)
    return repo, remote, other


def test_remote_source_guard_allows_aligned_and_local_ahead(tmp_path: Path):
    import subprocess
    repo, _remote, _other = _source_pair(tmp_path)
    aligned = evidence.assert_remote_source_current(repo)
    assert aligned["state"] == "ALIGNED"
    (repo / "local.txt").write_text("progress\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "local.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "local progress"], check=True)
    ahead = evidence.assert_remote_source_current(repo)
    assert ahead["state"] == "LOCAL_AHEAD"


def test_remote_source_guard_rejects_vps_behind_remote(tmp_path: Path):
    import subprocess
    repo, _remote, other = _source_pair(tmp_path)
    (other / "source.txt").write_text("new\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(other), "add", "source.txt"], check=True)
    subprocess.run(["git", "-C", str(other), "commit", "-qm", "new source"], check=True)
    subprocess.run(["git", "-C", str(other), "push", "-q", "origin", "main"], check=True)
    with pytest.raises(evidence.SourceAlignmentError, match="behind origin/main"):
        evidence.assert_remote_source_current(repo)


def test_complete_with_task_owned_output_is_persisted_locally(tmp_path: Path):
    import subprocess
    repo, project = fixture(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    task_file = project / "active-task-output.txt"
    task_file.write_text("validated but not committed\n", encoding="utf-8")
    complete = evidence.TaskResult("D01-030", "COMPLETE", "done", ("runtime pass",))
    normalized = evidence.enforce_clean_completion_boundary(repo, complete, owned_files={str(task_file.relative_to(repo)): __import__("hashlib").sha256(task_file.read_bytes()).hexdigest()})
    assert normalized.status == "COMPLETE"
    assert "committed locally" in normalized.evidence[-1]
    assert subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True) == ""


def test_complete_with_clean_task_output_stays_complete(tmp_path: Path):
    import subprocess
    repo, project = fixture(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Biella Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    complete = evidence.TaskResult("D01-030", "COMPLETE", "done", ("runtime pass",))
    normalized = evidence.enforce_clean_completion_boundary(repo, complete)
    assert normalized == complete


def test_result_schema_constrains_completion_evidence_to_canonical_typed_objects(monkeypatch):
    contract={
        "task_id":"T","task_revision":7,"task_digest":"a"*64,"scope_ref":"task://minitz/T/7",
        "required_criteria":("criterion-a",),"allowed_criteria":("criterion-a","criterion-b"),
    }
    monkeypatch.setattr(evidence,"_minitz_completion_contract",lambda _task:(contract,{"task_id":"T"}))
    schema=evidence.result_schema("T")
    item=schema["properties"]["evidence"]["items"]
    assert item["type"]=="object"
    assert item["additionalProperties"] is False
    assert "kind" in item["required"]
    assert "type" not in item["properties"]
    assert "provenance" not in item["properties"]
    assert item["properties"]["implementation_ref"]["type"]=="string"
    assert set(item["required"])==set(item["properties"])


def test_task_specific_result_schema_binds_current_completion_identity(monkeypatch):
    contract={
        "task_id":"T","task_revision":7,"task_digest":"a"*64,"scope_ref":"task://minitz/T/7",
        "required_criteria":("criterion-a",),"allowed_criteria":("criterion-a","criterion-b"),
    }
    monkeypatch.setattr(evidence,"_minitz_completion_contract",lambda _task:(contract,{"task_id":"T"}))
    schema=evidence.result_schema("T")
    props=schema["properties"]
    assert props["task_id"]=={"type":"string","const":"T"}
    assert props["task_revision"]=={"type":"integer","const":7}
    assert props["task_digest"]=={"type":"string","const":"a"*64}
    assert props["scope_ref"]=={"type":"string","const":"task://minitz/T/7"}
    item=props["evidence"]["items"]["properties"]
    assert item["task_id"]=={"type":"string","const":"T"}
    assert item["task_revision"]=={"type":"integer","const":7}
    assert item["task_digest"]=={"type":"string","const":"a"*64}
    assert item["scope_ref"]=={"type":"string","const":"task://minitz/T/7"}
