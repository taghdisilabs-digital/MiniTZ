# MiniTZ Main Coder Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use the current session with TDD and verification; preserve the live dirty worktree.

**Goal:** Integrate Codex and AGR as two interchangeable MiniTZ main-coder backends with shared durable continuity, automatic failover, and safe parallel peer assistance.

**Architecture:** Add a small coder-pool/AGR adapter layer above the existing Codex router. The production runner remains the single controller and writer; coder-native sessions are backend-scoped while MiniTZ task memory/evidence/cache are shared. AGR parallel work is read-only until isolated-write support is separately proven.

**Tech Stack:** Python 3, existing MiniTZ runner, Codex CLI, Antigravity `agy` 1.2.0, pytest, systemd.

**Spec:** `docs/superpowers/specs/2026-09-10-main-coder-pool-design.md`

## Global Constraints
- Preserve `UNIFY-04` current execution and all unrelated dirty files.
- Exactly four coder statuses: OFFLINE, ACTIVE, OUT_OF_CREDIT, NEEDS_MODIFICATION.
- One canonical production writer; peer coder output is non-authoritative.
- Both coders use the same Task Program, task memory, memory projection, evidence/failure journals, cache and AGENTS policy.
- Never probe quota with dummy work; infer exhaustion only from real provider failures.

### Task 1: Define coder-pool state and AGR command contract
**Files:** Create `ops/local-ai/biella_main_coder.py`; Test `tests/test_main_coder_pool.py`.
- [ ] Write failing tests for four-state classification, AGR model discovery parsing, command construction, eligibility/error classification, primary/peer selection, and backend-scoped task sessions.
- [ ] Run the focused tests and confirm RED.
- [ ] Implement only enough coder-pool/AGR adapter code to make them GREEN.
- [ ] Run focused tests.

### Task 2: Migrate runtime continuity to backend-scoped sessions
**Files:** Modify `ops/local-ai/biella_production_runner.py`; Test `tests/test_production_runner.py`.
- [ ] Add failing tests proving Codex and AGR native sessions coexist per task and cross-coder handoff retains the shared task capsule.
- [ ] Preserve legacy `task_session_id`/`task_sessions` reads while writing the new `coder_sessions` map.
- [ ] Make resume selection backend-specific; fresh backend sessions still receive RESUME_EXISTING_TASK_SESSION when shared task progress exists.
- [ ] Run focused tests.

### Task 3: Add AGR structured invocation and failover
**Files:** Modify `ops/local-ai/biella_production_runner.py`, `ops/local-ai/biella_task_packet.py`; Test focused runner tests.
- [ ] Add failing tests for AGR invocation/result parsing and Codex usage-exhaustion handoff.
- [ ] Dispatch AGR through shared task packet/memory/policy; record AGR conversation IDs separately.
- [ ] On observed coder quota exhaustion, preserve current bytes/evidence and select the other ACTIVE coder.
- [ ] On AGR eligibility/config failure, mark NEEDS_MODIFICATION and continue existing valid routes.

### Task 4: Add safe dual-coder parallel peer assist
**Files:** Modify runner/coder-pool; Test `tests/test_main_coder_pool.py`, `tests/test_production_runner.py`.
- [ ] Add failing tests: both ACTIVE -> one writer + one distinct read-only peer; duplicate objective -> no second call; peer failure -> writer unaffected.
- [ ] Implement bounded read-only AGR/Codex peer assist with shared current-task projection and content-addressed cache.
- [ ] Never allow peer output to close/advance a task.

### Task 5: Apply common policy/install and verify
**Files:** Modify `ops/workstation/AGENTS.md`, `ops/local-ai/install-biella-ai.sh`; add new module to install set.
- [ ] Update policy language from Codex-only authority to single MiniTZ writer + main-coder pool while preserving all existing quality/continuity rules.
- [ ] Install source without resetting or restarting unrelated work.
- [ ] Run focused and affected regression suites.
- [ ] Run a real bounded AGR health call only if its four-state status is ACTIVE; otherwise record the observed NEEDS_MODIFICATION reason and do not force traffic.
- [ ] Verify current task/revision and dirty state remain preserved.
