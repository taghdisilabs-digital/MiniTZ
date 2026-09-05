# Monorepo Production Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy auto-feeder with one monorepo-native `biella-codex production` runner that derives work from 03/04 + Project `PRODUCTION.md`, maintains fresh liveness, and resumes without duplicate state.

**Architecture:** Split the current monolithic feeder into focused state, packet, routing, evidence, and runner modules. Runtime JSON is telemetry only. `biella-codex` remains the only public controller and `biella resource` remains the only provider-dispatch surface.

**Tech Stack:** Python 3.12, Bash, systemd transient units, pytest, Git/GitHub, Google Drive continuity, existing Codex CLI.

**Spec:** `docs/superpowers/specs/2026-09-05-monorepo-production-runner-design.md`

## Global Constraints

- Canonical repo: `/root/biella/repos/biella-engine`, GitHub `patrickminitz-web/biella-engine`.
- Preserve every completed Games task and Engine P4-06=`INCOMPLETE_DEFERRED`.
- Global state is `docs/project-state/03_BIELLA_CURRENT_STATE.md`; exact active task is `docs/project-state/04_BIELLA_ACTIVE_TASK.md`.
- No `games-production.json`, second scheduler, second queue, or runtime completion ledger.
- `biella-codex` is the only public controller; new production CLI is `biella-codex production ...`.
- Hard/deep-memory/hard-creation route to Astra Ultra when available; creation never below high reasoning.
- Never call `/usage`, redeem resets, probe quotas, or print secrets.
- Runtime heartbeat interval <=30 seconds; `STALE` threshold remains 90 seconds.
- Cut over only after the current legacy child finishes; do not overwrite active Games edits.

---
### Task 1: Canonical Production State Module

**Files:**
- Create: `ops/local-ai/biella_production_state.py`
- Create: `tests/test_production_state.py`
- Modify: none in Games source

**Interfaces:**
- Produces `TaskRecord`, `ProductionState`, `load_project_production(project_root)`, `load_active_task(repo_root)`, `resolve_current_task(repo_root, project_root)`, `mark_task_complete(...)`, `write_active_task(...)`, `sync_current_state(...)`.
- Consumes only 03, 04, and Project `PRODUCTION.md`.

- [ ] **Step 1: Write failing state-resolution tests**

```python
def test_resolve_current_task_requires_04_and_project_to_agree(tmp_path):
    repo, project = write_fixture(tmp_path, active_id="D01-030", project_id="D01-030")
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-030"

def test_completed_project_task_repairs_stale_active_pointer(tmp_path):
    repo, project = write_fixture(tmp_path, active_id="D01-029", project_id="D01-030", d01_029="COMPLETE")
    resolved = state.resolve_current_task(repo, project)
    assert resolved.id == "D01-030"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests/test_production_state.py`
Expected: import/module failure because `biella_production_state.py` does not exist.

- [ ] **Step 3: Implement parser/update module**

Use dataclasses with explicit fields; keep regex parsing compatible with existing `## Section:` and task-line syntax. `write_active_task()` emits the existing v8 compact packet shape and never copies runtime telemetry as authority.

- [ ] **Step 4: Run state tests GREEN**

Run: `pytest -q tests/test_production_state.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add ops/local-ai/biella_production_state.py tests/test_production_state.py
git commit -m "refactor: isolate canonical production state"
```

### Task 2: Task Packet and Codex Routing Modules

**Files:**
- Create: `ops/local-ai/biella_task_packet.py`
- Create: `ops/local-ai/biella_codex_routing.py`
- Create: `tests/test_task_packet.py`
- Create: `tests/test_codex_routing.py`

**Interfaces:**
- `compile_task_packet(repo_root, production, task) -> str`
- `Route(model: str, reasoning: str)`
- `select_route(task_class, catalog, cooldowns, now) -> Route`
- `discover_catalog() -> dict[str, set[str]]`

- [ ] **Step 1: Write failing packet/routing tests**

```python
def test_hard_routes_astra_ultra():
    assert routing.select_route("hard", catalog(), {}, NOW) == routing.Route("gpt-6-astra", "ultra")

def test_packet_contains_exact_active_contract_without_policy_duplication(tmp_path):
    packet = packets.compile_task_packet(repo, production, task)
    assert "TASK: D01-030" in packet
    assert "04_BIELLA_ACTIVE_TASK.md" in packet
    assert "/usage" not in packet
```

- [ ] **Step 2: Run and verify RED**

Run: `pytest -q tests/test_task_packet.py tests/test_codex_routing.py`
Expected: missing modules.

- [ ] **Step 3: Move existing routing logic and implement packet compiler**

Move `_ROUTE_PROFILES`, reasoning/cooldown/catalog logic unchanged except imports. Packet compiler embeds the active-task text plus Project task identity and the existing `biella resource route <capability>` delegation rule.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/test_task_packet.py tests/test_codex_routing.py`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add ops/local-ai/biella_task_packet.py ops/local-ai/biella_codex_routing.py tests/test_task_packet.py tests/test_codex_routing.py
git commit -m "refactor: isolate task packets and model routing"
```

### Task 3: Evidence and Result Handling

**Files:**
- Create: `ops/local-ai/biella_production_evidence.py`
- Create: `tests/test_production_evidence.py`

**Interfaces:**
- `result_schema() -> dict[str, object]`
- `parse_result(path, expected_task_id) -> TaskResult`
- `apply_result(repo_root, project_root, result, route) -> None`

- [ ] **Step 1: Write failing evidence tests**

```python
def test_result_task_id_must_match(tmp_path):
    path = write_result(tmp_path, task_id="D01-999", status="COMPLETE")
    with pytest.raises(ValueError, match="task_id mismatch"):
        evidence.parse_result(path, "D01-030")

def test_complete_updates_project_and_active_task(tmp_path):
    result = TaskResult("D01-030", "COMPLETE", "done", ["runtime pass"])
    evidence.apply_result(repo, project, result, Route("gpt-6-astra", "ultra"))
    assert "D01-031" in (repo / "docs/project-state/04_BIELLA_ACTIVE_TASK.md").read_text()
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_production_evidence.py`
Expected: missing module/functions.

- [ ] **Step 3: Implement strict result handling**

Accept only `COMPLETE`, `COMPLETE_ALREADY`, `CONTINUE`, `EXTERNAL_DEPENDENCY`, `OWNER_DECISION`. Completion uses the state module to update Project completion and 03/04; invalid/missing evidence never advances state.

- [ ] **Step 4: Run GREEN**

Run: `pytest -q tests/test_production_evidence.py`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add ops/local-ai/biella_production_evidence.py tests/test_production_evidence.py
git commit -m "refactor: isolate production evidence closure"
```

### Task 4: Single-Flight Production Runner with Live Heartbeat

**Files:**
- Create: `ops/local-ai/biella_production_runner.py`
- Create: `tests/test_production_runner.py`
- Reuse logic from: `ops/local-ai/biella_codex_feeder.py`

**Interfaces:**
- `run_production(repo_root, project_root, runtime_root) -> int`
- `production_status(repo_root, project_root, runtime_root, now=None) -> dict`
- `start_production(repo_root, project_root) -> int`
- `stop_production(repo_root, project_root) -> int`

- [ ] **Step 1: Write failing heartbeat/single-flight tests**

```python
def test_long_child_keeps_runtime_heartbeat_fresh(tmp_path, monkeypatch):
    runner = make_runner_with_slow_child(tmp_path, seconds=0.15, heartbeat_interval=0.02)
    assert runner.run_once() == 0
    beats = read_recorded_heartbeats(tmp_path)
    assert len(beats) >= 2

def test_second_runner_cannot_acquire_lock(tmp_path):
    first = ProductionLock(tmp_path / "run.lock"); first.acquire()
    with pytest.raises(AlreadyRunning):
        ProductionLock(tmp_path / "run.lock").acquire()
```

- [ ] **Step 2: Run RED**

Run: `pytest -q tests/test_production_runner.py`
Expected: missing runner module.

- [ ] **Step 3: Implement subprocess poll loop and telemetry-only runtime**

Use `subprocess.Popen`; write prompt to stdin; poll child at <=1 second; call `heartbeat()` at <=30-second production default. Runtime keys are only `status,project,task_id,attempt,pid,child_pid,active_model,active_reasoning,cooldowns,last_result,heartbeat_at,updated_at`.

- [ ] **Step 4: Implement one systemd unit**

Unit name returned by the runner is exactly `biella-codex-production`. `start` uses one transient unit and passes canonical repo/project roots as environment values.

- [ ] **Step 5: Run GREEN**

Run: `pytest -q tests/test_production_runner.py`
Expected: pass, including fresh heartbeat and lock behavior.

- [ ] **Step 6: Commit**

```bash
git add ops/local-ai/biella_production_runner.py tests/test_production_runner.py
git commit -m "feat: add monorepo production runner"
```

### Task 5: Controller, Installer, Control, and Policy Cutover

**Files:**
- Modify: `ops/local-ai/biella-codex.sh`
- Modify: `ops/local-ai/install-biella-ai.sh`
- Modify: `ops/control_gateway/biella_control_state.py`
- Modify: `ops/workstation/AGENTS.md`
- Modify: `ops/local-ai/README.md`
- Modify: `tests/unified_codex_controller_contract_test.sh`
- Modify: `tests/control_gateway_service_contract_test.sh`
- Create/modify focused control tests as needed.

**Interfaces:**
- Public CLI: `biella-codex production {run,start,status,stop,sync}`.
- Control invokes `/usr/local/bin/biella-codex production status`.

- [ ] **Step 1: Change controller/control tests first**

Require `production` and explicitly forbid `feed`, `biella_codex_feeder.py`, and project-specific feeder unit names in active controller/install/control source.

- [ ] **Step 2: Run RED**

Run: `bash tests/unified_codex_controller_contract_test.sh && pytest -q tests/test_control_state.py tests/test_control_projection_monorepo.py`
Expected: fail because current source still exposes `feed`.

- [ ] **Step 3: Wire production modules and installer**

`biella-codex.sh` dispatches `production` to `biella_production_runner.py`. Installer copies the five new Python modules and removes installed legacy feeder bytes. Shared policy names 03/04 + Project `PRODUCTION.md` as durable production state.

- [ ] **Step 4: Update Control status command**

Replace `biella-codex feed status` with `biella-codex production status`; preserve projection payload field names so frontend behavior does not change.

- [ ] **Step 5: Run GREEN**

Run: `bash tests/unified_codex_controller_contract_test.sh && pytest -q tests/test_control_state.py tests/test_control_projection_monorepo.py`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add ops/local-ai ops/control_gateway/biella_control_state.py ops/workstation/AGENTS.md tests
git commit -m "refactor: switch controller to production runner"
```

### Task 6: Legacy Removal, Runtime Configuration, Cutover, and Live Resume

**Files:**
- Delete: `ops/local-ai/biella_codex_feeder.py`
- Delete/replace legacy feeder-specific tests that are fully covered by the new focused modules.
- Update installed bytes under `/usr/local/lib/biella-ai/` through the canonical installer.
- Runtime config only: `/root/.config/biella-ai/runtime.env`.

- [ ] **Step 1: Wait for the frozen legacy D01-030 child to exit**

Verify `0002-D01-030-*.result.json` exists or the child exits; inspect Project `PRODUCTION.md`, 03/04, Git status, and `origin/main`. Resume the frozen parent only if needed to consume that exact result; prevent it from starting D01-031.

- [ ] **Step 2: Rebase/cherry-pick rewrite onto latest canonical main**

Preserve all D01-030 commits. Resolve only controller/state-module conflicts; do not edit Games implementation files during the rewrite merge.

- [ ] **Step 3: Remove legacy surface and run full tests**

Run:
```bash
pytest -q tests/test_production_state.py tests/test_task_packet.py tests/test_codex_routing.py tests/test_production_evidence.py tests/test_production_runner.py tests/test_control_state.py tests/test_control_projection_monorepo.py
bash tests/unified_codex_controller_contract_test.sh
bash tests/local_ai_runtime_contract_test.sh
bash tests/workstation_provider_registry_test.sh
bash tests/control_gateway_service_contract_test.sh
```
Expected: all pass; search finds no active `games-production.json`, `biella_codex_feeder.py`, or `biella-codex feed` references outside historical/archive evidence.

- [ ] **Step 4: Set the three runtime locators without printing secrets**

Set `SUPABASE_URL=https://jktmfmfxhynzickoaswt.supabase.co`, `UPSTASH_EMAIL=patrickminitz@gmail.com`, and `CLOUDINARY_CLOUD_NAME=efex8ff4` in the existing mode-0600 runtime environment; verify only `SET/MISSING` flags via `biella resource status`.

- [ ] **Step 5: Install exact canonical bytes**

Run `ops/local-ai/install-biella-ai.sh`, `ops/workstation/install-biella-workstation.sh`, and control gateway installer/build where changed. Verify SHA256 equality between canonical source and installed controller/runner/policy files.

- [ ] **Step 6: Start the new runner and prove liveness**

Run `biella-codex production start`, then verify within >30 seconds that heartbeat advances, status remains `ACTIVE`, one production parent and one task child exist, and the task ID equals the canonical successor after D01-030.

- [ ] **Step 7: Publish and read back**

Commit/push final `main`; verify exact GitHub commit/tree/path readback. Update existing Drive 03/04/provenance files in place when their bytes changed, preserving file IDs and SHA256 equality.

- [ ] **Step 8: Remove temporary rewrite worktrees/branches**

After merged-main tests and live resume pass, remove `production-runner-20260905` and `feeder-heartbeat-20260905` worktrees/branches. Keep no duplicate active controller checkout.
