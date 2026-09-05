# Unified Biella Monorepo + Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse Biella Git, Drive, feeder state, control UI, and local workspace into one current production authority without losing any completed or in-progress work.

**Architecture:** `patrickminitz-web/biella-engine` remains the sole active Git repository. Biella Games moves intact under `projects/biella-games/`; Website/control, reusable capabilities/APIs/schemas, and controller/runtime remain repo-root Engine concerns. Git/Drive/runtime progress is projected from canonical sources; feeder runtime state is telemetry only.

**Tech Stack:** Git/GitHub, Google Drive/Docs, Python 3, Bash, Codex CLI, systemd, Unreal Engine 5.8.2, static HTML/CSS/JS control console.

**Spec:** `docs/superpowers/specs/2026-09-05-biella-ai-production-map-task-contract-design.md`

## Global Constraints
- Preserve every completed/in-progress task and unique source/evidence before authority switch.
- One active Git repository and one canonical local repo root after migration.
- No Games-specific source silently becomes reusable Engine capability.
- P4-06 remains `INCOMPLETE_DEFERRED`; do not claim it complete.
- Automated feeder stays stopped until the new state path is verified.
- Do not use/reset/redeem Codex account usage; external provider free tiers, trial/prepaid credits, and paid API use are authorized when task-useful.
- Delete recovery/backups only after unique-value verification.

---

### Task 1: Freeze all unique progress

**Files:** existing branches/worktrees only; no canonical source change.

- [x] Preserve current Games Demo worktree to remote branch/commit `2193b769e61b43ebfc4f910f6380c68e6b828cd5`.
- [x] Preserve state-bridge scaffold/test to `e50cb09a6d0b8f36da72ef16d4148620311a663c`.
- [x] Preserve Demo continuity edits to `44b9a90e9f9143b7f9c859682f5595d621955882`.
- [ ] Verify the AAA-SF ZIP is redundant, then mark it archived/non-authoritative; do not delete it during this migration.
- [ ] Record the exact imported source identities in monorepo provenance.

### Task 2: Build the one-repo source tree

**Files:**
- Create: `projects/biella-games/**`
- Create: `docs/migration/ONE_REPO_PROVENANCE_2026-09-05.md`
- Import: `website/**` and current website workflows from `control-live-20260904`.
- Import/normalize: capability-preparation schema/research.
- Import: AAA-SF future program under `docs/future/aaa-challenger-solo-founder/`.

- [ ] Import the exact Games preservation commit under `projects/biella-games/`.
- [ ] Merge only unique current continuity data from `44b9a90`; do not overwrite newer Demo state.
- [ ] Import current Website/control source without reverting newer Engine files.
- [ ] Classify capability-preparation inputs; activate only reusable schema/mechanisms and store dated research as reference/evidence.
- [ ] Import AAA-SF as `FUTURE_PROGRAM_BLOCKED`, not an active workflow.
- [ ] Add provenance with exact source repo/commit/tree identities and classifications.

### Task 3: Collapse canonical task/state authority

**Files:**
- Modify: `docs/project-state/03_BIELLA_CURRENT_STATE.md`
- Modify: `docs/project-state/04_BIELLA_ACTIVE_TASK.md`
- Modify: `projects/biella-games/docs/DEMO_01_QUEUE.md`
- Modify: `ops/local-ai/biella_codex_feeder.py`
- Test: `tests/test_codex_feeder.py`

- [ ] Make 03 the compact global execution state: one repo, Games active, Demo `26/50`, current `D01-027`, P4-06 `INCOMPLETE_DEFERRED`.
- [ ] Make 04 the one exact active task packet for D01-027 with read/write/acceptance/validation/persist/stop fields.
- [ ] Refactor feeder status/start logic to derive durable Games progress from `projects/biella-games/docs/DEMO_01_QUEUE.md`; keep cooldown/attempt/heartbeat only in runtime state.
- [ ] Write failing tests proving no durable `games-production.json` completion ledger is required.
- [ ] Run the tests RED, implement, then run GREEN.

### Task 4: Unify workspace paths and controller projections

**Files:**
- Modify: `ops/workstation/AGENTS.md`
- Modify: `ops/control_gateway/biella_control_state.py`
- Modify: `ops/control_gateway/biella_control_gateway.py`
- Modify: installer/runtime scripts and tests that name `/root/biella/repos/biella-games`.

- [ ] Replace active Games checkout references with `/root/biella/repos/biella-engine/projects/biella-games`.
- [ ] Project one current task/section/progress/Git identity/heartbeat into control state.
- [ ] Remove Website/Games repository selection logic; lanes are project contexts inside one repository.
- [ ] Update controller/workstation tests to reject a second active repo root.

### Task 4A: Activate cost-aware Resource routing

**Files:**
- Create: `ops/workstation/biella-resource.py`
- Create: `ops/workstation/provider-registry.json`
- Modify: `ops/workstation/biella`
- Modify: `ops/workstation/biella-provider-check.sh`
- Modify: `ops/workstation/install-biella-workstation.sh`
- Modify: `ops/workstation/AGENTS.md`
- Modify: `ops/control_gateway/biella_control_state.py`
- Test: `tests/test_resource_router.py`
- Test: `tests/workstation_provider_registry_test.sh`

- [ ] Write failing tests for semantic capability routing, no-secret registry output, free/trial/prepaid preference with paid allowed, missing-locator handling, and compact Tavily/Exa/fast-LLM operations.
- [ ] Add one provider registry covering Cloudflare, Saturn, Groq, Cerebras, OpenRouter, Mistral, Tavily, Exa, Pinecone, Qdrant, Deepgram, AssemblyAI, ElevenLabs, Stability AI, Supabase, Neon, Upstash, Cloudinary, Axiom, Pexels, and Modal.
- [ ] Add `biella resource status|route|search|fast-llm` as the single provider-dispatch surface; it must never print credential values.
- [ ] Route research to Tavily/Exa and fast inference to eligible Groq/Cerebras/Mistral/OpenRouter implementations; compact provider responses before returning them to Codex.
- [ ] Expose provider capability/health state in the existing control System projection.
- [ ] Install and qualify the exact dispatcher bytes; do not probe quotas or activate a second controller.

### Task 5: Rebuild the private control UI

**Files:**
- Modify: `website/src/control/index.html`
- Modify: `website/src/control/app.js`
- Modify: `website/src/control/styles.css`
- Modify: `website/tests/test_control_contracts.py`
- Modify: `website/tests/browser/test_control_site.py`

- [ ] Replace the nine-view navigation with `Control | Work | Outputs | System`.
- [ ] Add persistent `ACTIVE | WAITING | STALE | STOPPED | ERROR` liveness with heartbeat freshness, current task, model/reasoning, progress, next task, Git/Drive state, and latest evidence.
- [ ] Render one canonical task row per semantic task; aliases/evidence are details, not duplicate work.
- [ ] Replace generic neon dashboard styling with the approved graphite production-workstation visual system and real artifact-first Outputs presentation.
- [ ] Run static contract tests and browser tests.

### Task 6: Validate the monorepo from its new paths

- [ ] Run Engine focused/full tests, strict type/build checks required by current source, controller/runtime contracts, and control-gateway tests.
- [ ] Run Website build + control contract/browser tests from the tracked `website/` subtree.
- [ ] Run `projects/biella-games/tests/verify_demo01.py` from the nested Project path.
- [ ] Build the current Unreal Editor target from `projects/biella-games/BiellaGames.uproject` with UE 5.8.2.
- [ ] Launch the canonical project headlessly and verify the current map/runtime signals; do not advance D01-027 while qualifying migration.
- [ ] Verify imported Games source/evidence digests against preservation commit `2193b769...` before path-specific edits.

### Task 7: Publish one canonical Git authority

- [ ] Commit coherent migration revisions on the temporary consolidation branch.
- [ ] Rebase/fast-forward only if `origin/main` has not moved incompatibly; otherwise reconcile current main without discarding work.
- [ ] Push canonical `main` and remote-readback exact commit/tree/required paths.
- [ ] Install exact controller/workstation/control bytes from the resulting main.
- [ ] Verify `/root/biella/repos/biella-engine` is the only active repo root and points to the published main.

### Task 8: Unify Google Drive without losing file identities

- [ ] Rename the existing `BiellaEngine` root to `Biella` if it is the current authoritative root and retain its folder ID.
- [ ] Create/reuse `CURRENT`, `PROJECTS/GAMES`, `OUTPUTS`, and `ARCHIVE` under that root.
- [ ] Move 03/04 and current continuity files into `CURRENT` preserving file IDs.
- [ ] Move/reparent the Games production root under `PROJECTS/GAMES` while preserving its folder/file IDs.
- [ ] Publish/read back the monorepo provenance and current state/active task.
- [ ] Move or label historical provenance, recovery, and backups under `ARCHIVE`; do not delete progress or recovery copies during this migration.

### Task 9: Retire superseded Git/workspace copies

- [ ] Compare every temporary/divergent branch against canonical main after import; retain nothing merely because it is old.
- [ ] Archive/rename `biella-games` and `capability_preparation` GitHub repos only after canonical readback proves their required material is represented.
- [ ] Remove merged/superseded worktrees and temporary branches.
- [ ] Move `/root/biella/repos/biella-games` out of active routing into `/root/biella/archive/repos/` after its preservation commit and imported subtree are both verified; do not delete it.
- [ ] Verify `/root/spark-biella-games` against canonical admitted material, then deactivate it from active routing and retain it as archived recovery; do not delete it during this migration.
- [ ] Remove proven redundant local `/root/biella/recovery`, `/root/biella/backups`, and stale checkpoints.
- [ ] Keep the auto feeder stopped at final handoff unless the unified state/controller qualification explicitly authorizes restart.

### Task 10: Durable closure

- [ ] Update 03/04 one final time with exact monorepo commit/tree, Drive IDs, active D01-027, feeder `STOPPED_BY_OWNER`, and remaining unresolved migrations if any.
- [ ] Verify GitHub and Drive remote readback.
- [ ] Remove this implementation plan from the active tip if all unique rules have been absorbed into canonical state/policy; Git history retains it.
- [ ] Remove the temporary consolidation worktree/branch after main and installed bytes are verified.
