# 30-Commander Assist Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 30 non-authoritative, nonblocking Commander assist lanes to MiniTZ while preserving one canonical writer and current `UNIFY-04` continuity.

**Architecture:** A new focused fabric module defines lanes, packets, leases, cache keys and validation. The production runner only launches/reaps read-only provider workers and passes a bounded index reference to the writer. Control/public projection reads the durable index.

**Tech Stack:** Python 3.12, pytest, subprocess, JSON, existing MiniTZ runtime/task memory and `biella resource fast-llm`.

**Spec:** `docs/superpowers/specs/2026-09-11-commander-assist-fabric-design.md`

## Global Constraints
- Exactly 30 logical Commander lanes.
- Authority is always `NONE`; no task/progression mutation.
- Writer never waits for Commander work.
- Do not use local Qwen for Commander lanes by default.
- Preserve current task/session/worktree identity across activation.
- Keep existing two TaskBoosters unchanged.

---

### Task 1: Commander fabric core
**Files:** create `ops/local-ai/minitz_commander_fabric.py`; create `tests/test_commander_fabric.py`.
**Produces:** lane registry, bounded packet/context, cache key, provider assignment, result schema/validation, status classification, index/lease helpers.
- [ ] Write failing tests for exact 30 lanes, unique roles, authority-free schema, deterministic cache key/provider assignment, bounded context, result validation and stale lease reconciliation.
- [ ] Run focused tests and confirm RED.
- [ ] Implement the minimal fabric module.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Nonblocking production integration
**Files:** modify `ops/local-ai/biella_production_runner.py`; modify `tests/test_production_runner.py`.
**Consumes:** Task 1 fabric API.
**Produces:** process handles, collect/launch/terminate lifecycle, writer-prompt index reference.
- [ ] Add failing tests proving launch is nonblocking, duplicate caches suppress reruns, zero lanes never block writer, prompt authority stays NONE, and exit terminates only Commander children.
- [ ] Run focused runner tests and confirm RED.
- [ ] Implement lifecycle integration without waiting on assists, with exact-provider leases, one-canary-first ramp, and bounded provider backoff.
- [ ] Run focused runner tests and confirm GREEN.

### Task 3: Projection and policy
**Files:** modify `ops/control_gateway/biella_control_state.py`, `ops/control_gateway/biella_live_projection.py`, `website/src/live/index.html`, `website/src/live/app.js`, `website/src/live/styles.css`, `ops/workstation/AGENTS.md`, plus focused tests.
**Produces:** bounded Commander counts/lane status visibility and canonical policy text.
- [ ] Add failing control/live/website contract tests.
- [ ] Implement aggregate/per-lane projection without raw findings.
- [ ] Run focused tests and confirm GREEN.

### Task 4: Install/activation and verification
**Files:** modify `ops/local-ai/install-biella-ai.sh` and installer/controller contract tests.
- [ ] Add installer contract test for Commander module.
- [ ] Install exact verified modules to `/usr/local/lib/biella-ai` and control projection to `/usr/local/lib/biella-control`.
- [ ] Run targeted regressions, shell contracts, `py_compile`, `git diff --check`, and secret scan.
- [ ] Commit exact owned files on the feature branch and fast-forward `main` only if live `main` has not diverged.
- [ ] Push exact `main` and verify GitHub readback.
- [ ] At a no-child safe boundary, restart only `biella-codex-production.service`; verify same `UNIFY-04` identity, fresh heartbeat, and Commander fabric projection.
- [ ] Verify public website/control remain HTTP 200 and show Commander aggregate.
