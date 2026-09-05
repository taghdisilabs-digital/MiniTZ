# GitHub + Drive Current-State Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one verified current-state bridge that publishes current Git/GitHub/task state to exact canonical Drive IDs and exposes the same manifest to the browser control console.

**Architecture:** A small Python state-bridge module builds a manifest from three Git lanes plus current project-state YAML, then an exact-ID Drive publisher uses the authenticated `gdrive:` rclone remote with pre-write ID checks and post-write byte/ID readback. The workstation CLI and control gateway consume the same installed manifest; focused CI validates generation offline without Drive writes.

**Tech Stack:** Python 3.12, PyYAML 6.x, Git/gh CLI, rclone Google Drive backend, systemd, unittest, Bash contracts, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-04-github-drive-current-state-bridge-design.md`

## Global Constraints

- Execution may be unrestricted, but changes remain bounded to the approved GitHub/Drive current-state bridge.
- Preserve all completed task status and unrelated user work.
- Canonical Drive writes use exact file IDs and byte readback; no filename-selected mutation.
- Never delete, rename, or promote duplicate-title/historical/recovery Drive material.
- Do not print credentials or rclone tokens.
- CI performs no Drive writes.
- `gdrive:` is the current working OAuth remote; `drive:` is not modified.

---
### Task 1: Source registry and manifest generation

**Files:**
- Create: `ops/state_bridge/__init__.py`
- Create: `ops/state_bridge/source_registry.json`
- Create: `ops/state_bridge/biella_state_bridge.py`
- Test: `tests/test_state_bridge.py`

**Interfaces:**
- Consumes: repository paths, `docs/project-state/03_BIELLA_CURRENT_STATE.md`, `04_BIELLA_ACTIVE_TASK.md`, exact source registry.
- Produces: `build_manifest(config, runner, now) -> dict[str, object]`, `load_registry(path) -> dict`, `write_manifest(path, manifest) -> bytes`.

- [ ] **Step 1: Write failing manifest tests**

Test that a fake command runner produces Engine/Website/Games local+remote SHAs, `MATCH/AHEAD/BEHIND/DIVERGED`, active task `ENG-P4-06`, exact prompt Drive ID, service state, and exact canonical Drive source IDs. Also assert malformed/missing YAML fails rather than guessing.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python3 -m unittest tests.test_state_bridge.StateBridgeManifestTest -v`
Expected: FAIL because `ops.state_bridge.biella_state_bridge` does not exist.

- [ ] **Step 3: Implement the minimal registry and generator**

Registry keys must include `lanes.Engine`, `lanes.Website`, `lanes.Games`, `drive.root_id`, and targets `current_state`, `active_task`, `context_index`, `manifest`. Parse only the fenced YAML documents from the two project-state files with `yaml.safe_load`; do not scrape prose.

- [ ] **Step 4: Run focused tests and offline validation**

Run: `python3 -m unittest tests.test_state_bridge.StateBridgeManifestTest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ops/state_bridge tests/test_state_bridge.py
git commit -m "feat: generate verified Biella current-state manifest"
```

---
### Task 2: Exact-ID Drive publisher and generated current index

**Files:**
- Modify: `ops/state_bridge/biella_state_bridge.py`
- Test: `tests/test_state_bridge.py`

**Interfaces:**
- Consumes: `manifest: dict`, registry Drive targets, local source bytes, `gdrive:` command runner.
- Produces: `publish_target(target, local_bytes, runner) -> PublicationReceipt`, `render_context_index(manifest) -> bytes`, and `sync_state(...) -> dict`.

- [ ] **Step 1: Write failing publisher tests**

Use a fake rclone runner. Assert that an existing target is statted before `copyto`, a wrong observed Drive ID aborts before write, successful publication performs `copyto`, `cat`, SHA-256 comparison, and a second `lsjson --stat` ID check. Assert generated index contains manifest ID/path, current Engine task, all three lane SHAs, and canonical authority links.

- [ ] **Step 2: Run the focused publisher tests and confirm RED**

Run: `python3 -m unittest tests.test_state_bridge.StateBridgeDriveTest -v`
Expected: FAIL because publisher functions are absent.

- [ ] **Step 3: Implement exact-ID publication**

Use commands shaped as:

```bash
rclone lsjson "gdrive:<path>" --drive-root-folder-id <root-id> --metadata --stat
rclone copyto <local-file> "gdrive:<path>" --drive-root-folder-id <root-id>
rclone cat "gdrive:<path>" --drive-root-folder-id <root-id>
```

All existing mutable targets require registry ID equality before and after write. Manifest creation is allowed only when registry ID is `null`; once created, discovery returns the new ID for a follow-up registry commit.

- [ ] **Step 4: Implement generated index and source publication**

Publish exact committed bytes of `03_BIELLA_CURRENT_STATE.md` and `04_BIELLA_ACTIVE_TASK.md`. Generate the current index from manifest/navigation pointers rather than copying stale task prose.

- [ ] **Step 5: Run Drive unit tests**

Run: `python3 -m unittest tests.test_state_bridge.StateBridgeDriveTest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ops/state_bridge/biella_state_bridge.py tests/test_state_bridge.py
git commit -m "feat: publish state to exact Drive records"
```

---
### Task 3: Workstation CLI installation and low-noise automatic sync

**Files:**
- Create: `ops/state_bridge/install-biella-state-bridge.sh`
- Modify: `ops/workstation/biella`
- Modify: `ops/local-ai/biella-work.sh`
- Test: `tests/state_bridge_contract_test.sh`
- Modify: `tests/low_noise_autopilot_contract_test.sh`

**Interfaces:**
- Produces: `/usr/local/bin/biella-state-sync`, `/usr/local/lib/biella-state/*`, `/var/lib/biella-state/current-state.json`, `biella sync-state`, and `biella state`.

- [ ] **Step 1: Write failing shell contracts**

Assert installer deploys the Python module+registry, CLI exposes `sync-state`/`state`, and `biella-work.sh` captures the enclosing Git HEAD before/after. If a successful run changes HEAD, it invokes `biella-state-sync` before printing the final message; unchanged runs do not sync.

- [ ] **Step 2: Run contracts and confirm RED**

Run: `bash tests/state_bridge_contract_test.sh && bash tests/low_noise_autopilot_contract_test.sh`
Expected: FAIL on missing installer/CLI literals.

- [ ] **Step 3: Implement installer and CLI wiring**

Install code root-owned under `/usr/local/lib/biella-state`, state directory `/var/lib/biella-state`, and symlink `/usr/local/bin/biella-state-sync`. Preserve the existing `biella` and low-noise behavior.

- [ ] **Step 4: Implement changed-HEAD auto-sync**

`biella-work.sh` must keep Codex stdout/stderr suppression. On changed HEAD, run `biella-state-sync sync` with output captured; on failure append only `STATE_SYNC: FAILED` plus the bounded failure tail after the agent's final result.

- [ ] **Step 5: Run shell contracts**

Run: `bash tests/state_bridge_contract_test.sh && bash tests/low_noise_autopilot_contract_test.sh && bash tests/workstation_supervisor_contract_test.sh`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ops/state_bridge/install-biella-state-bridge.sh ops/workstation/biella ops/local-ai/biella-work.sh tests
git commit -m "feat: add automatic Biella state synchronization"
```

---
### Task 4: Browser gateway consumes and republishes manifest state

**Files:**
- Modify: `ops/control_gateway/biella_control_state.py`
- Modify: `ops/control_gateway/biella_control_gateway.py`
- Modify: `ops/control_gateway/biella_control_runner.py`
- Test: `tests/test_control_state.py`
- Test: `tests/test_control_gateway.py`
- Test: `tests/test_control_runner.py`

**Interfaces:**
- Produces: `ControlState.state_manifest() -> dict[str, object]`, `GET /v1/control/state-manifest`, manifest-backed overview fields, and post-agent state-sync event.

- [ ] **Step 1: Write failing gateway/state tests**

Assert a valid manifest overrides commit/branch/task fields in overview, invalid/missing manifest falls back to existing live Git logic, `/v1/control/state-manifest` is authenticated read-only, and a successful dialog with changed HEAD invokes `/usr/local/bin/biella-state-sync sync` exactly once.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python3 -m unittest tests.test_control_state tests.test_control_gateway tests.test_control_runner -v`
Expected: FAIL on missing manifest API/sync integration.

- [ ] **Step 3: Implement manifest-backed state**

Read `/var/lib/biella-state/current-state.json` with JSON validation and no mutation. Use manifest lane fields only when present and structurally valid; preserve the existing direct state adapter as fallback.

- [ ] **Step 4: Implement read-only route and post-dialog sync**

Add `GET /v1/control/state-manifest`. In the runner, compare lane HEAD before/after successful Codex execution; when changed, run state sync and publish a compact `state_sync` SSE event. Do not undo code work on sync failure.

- [ ] **Step 5: Run gateway suite**

Run: `python3 -m unittest tests.test_control_state tests.test_control_gateway tests.test_control_runner -v && bash tests/control_gateway_service_contract_test.sh && bash tests/control_tunnel_contract_test.sh`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ops/control_gateway tests/test_control_*.py
git commit -m "feat: serve unified state manifest in control gateway"
```

---
### Task 5: GitHub CI, live Drive publication, and canonical integration

**Files:**
- Create: `.github/workflows/state-bridge-ci.yml`
- Modify: `ops/state_bridge/source_registry.json` after first manifest publication to record its exact Drive ID.
- Modify: `docs/project-state/BIELLA_DRIVE_LIVE_MANIFEST.md` only to add the new machine-manifest pointer and remove stale copied active-boundary text.

**Interfaces:**
- CI command: `python3 -m unittest tests.test_state_bridge -v` plus offline generator validation.
- Live command: `biella sync-state`.

- [ ] **Step 1: Add CI workflow and failing workflow contract**

Create a focused workflow on pushes/PRs affecting `ops/state_bridge/**`, control-gateway state integration, workstation wrappers, project-state records, or the workflow itself. Install PyYAML, run unit/shell contracts, then run `python3 ops/state_bridge/biella_state_bridge.py validate --offline`.

- [ ] **Step 2: Run all local tests before live publication**

Run:

```bash
python3 -m unittest tests.test_state_bridge tests.test_control_state tests.test_control_gateway tests.test_control_runner -v
bash tests/state_bridge_contract_test.sh
bash tests/low_noise_autopilot_contract_test.sh
bash tests/local_ai_runtime_contract_test.sh
bash tests/workstation_supervisor_contract_test.sh
bash tests/control_gateway_service_contract_test.sh
bash tests/control_tunnel_contract_test.sh
git diff --check
```

Expected: all PASS and clean diff check.

- [ ] **Step 3: Install state bridge in the live VPS and generate locally**

Run the state-bridge installer from the verified branch. Generate `/var/lib/biella-state/current-state.json` without Drive mutation first and validate JSON plus browser fallback behavior.

- [ ] **Step 4: First exact Drive publication**

Run `biella sync-state`. For the new manifest path only, allow create-then-discover. Record the returned Drive ID, update `source_registry.json`, rerun tests, commit the ID, then rerun `biella sync-state` so every target uses a fixed exact ID.

- [ ] **Step 5: Verify Drive and browser readback**

Require exact SHA-256 equality for current-state, active-task, generated index, and manifest files. Verify the permanent browser endpoint returns HTTP 200 and authenticated state endpoint is configured. Verify local manifest source IDs equal the registry.

- [ ] **Step 6: Push branch and reconcile with current `main`**

Fetch `origin/main`. If the parallel autopilot advanced `main`, merge/rebase only through a normal non-destructive Git merge and rerun the full suite. Merge the verified integration branch into `main`, push, and verify GitHub remote HEAD/readback.

- [ ] **Step 7: Final state publication after canonical merge**

Run `biella sync-state` from canonical `main` so Drive/browser manifest records the final merged SHA. Verify exact Drive ID+byte readback and control-console HTTP readback again.

- [ ] **Step 8: Commit/update progress record if any live publication receipt changes source files**

Only record observed IDs, SHAs, workflow results, and readback status. Do not mark unrelated project tasks complete.
