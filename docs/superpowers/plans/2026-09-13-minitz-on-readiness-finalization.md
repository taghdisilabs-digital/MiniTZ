# MiniTZ ON Readiness Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Ubuntu 26.04 MiniTZ target truthfully ready for an explicit owner ON command while keeping MiniTZ OFF during repair.

**Architecture:** Preserve the existing dirty target tree and checkpointed work. Remove Google Drive from automatic publication, align ON/SLEEP/OFF lifecycle semantics, reconcile source/publication state without donor mutation, validate the complete target, then synchronize canonical task evidence only through MiniTZ authority paths.

**Tech Stack:** Python 3.14, pytest, mypy, systemd contracts, Git, MiniTZ Task Program, Windows/OpenSSH/S3 publication resources.

**Spec:** Owner-approved design in current MiniTZ repair conversation and `ops/workstation/AGENTS.md`.

## Global Constraints

- MiniTZ remains OFF until the owner explicitly orders ON.
- Ubuntu 24.04 donor source/systemd is not mutated.
- No reset, clean, stash, history rewrite, or broad rollback.
- Raw credentials never enter Git, prompts, ordinary logs, or semantic memory.
- Accepted dirty work is preserved and repaired in place.
- External publication failure must not own task progression.

---

### Task 1: Remove Google Drive from automatic publication

**Files:** `ops/local-ai/biella_publication.py`, `ops/local-ai/biella_execution_style.py`, `ops/local-ai/biella_execution_map.py`, `ops/workstation/AGENTS.md`, `ops/local-ai/minitz_policy.py`, publication tests.

- [ ] Add failing tests proving background publication never calls rclone and starts no Drive worker.
- [ ] Keep explicit/manual Drive helpers only as retired compatibility paths.
- [ ] Mark Drive state `EXPLICIT_ONLY`; preserve historical receipts without retrying them.
- [ ] Remove five-task automatic Drive guidance from active policy/context.
- [ ] Run targeted publication/policy tests.

### Task 2: Canonical ON/SLEEP/OFF lifecycle

**Files:** `ops/local-ai/biella_customer_handoff.py`, lifecycle entrypoints/installers, lifecycle tests.

- [ ] Add failing tests: SLEEP freezes production writers but keeps Ollama/Qwen warm; OFF stops runtime/model residency; ON restores only after readiness.
- [ ] Split warm SLEEP from deep OFF behavior without changing host power.
- [ ] Preserve checkpoint/resume compatibility and exact prior service state.
- [ ] Run lifecycle/customer-handoff targeted tests.

### Task 3: Source, resource, and publication convergence

**Files:** target Git state, MiniTZ resource/provider registry, Windows/S3 publication resource metadata and credential refs.

- [ ] Reconcile current target branch with remote history without donor source mutation.
- [ ] Register Windows VPS and S3/hosting publication capabilities by non-secret references only.
- [ ] Keep cPanel/hosting publication explicit and scoped; do not make external hosting an ON prerequisite unless task acceptance requires it.
- [ ] Resolve stale publication reconciliation state and retire automatic Drive pending state.
- [ ] Verify repository diff has no accidental conflicts or secret material.

### Task 4: Qualification and canonical synchronization

- [ ] Run `git diff --check` and `python3 -m mypy --strict src`.
- [ ] Run targeted lifecycle/publication/resource tests.
- [ ] Run full `python3 -m pytest -q --disable-warnings` to completion.
- [ ] Reconcile the living Task Program using its canonical transaction/writer path; do not fabricate completion.
- [ ] Create a fresh local recovery checkpoint and verify hashes.
- [ ] Re-check MiniTZ remains OFF, system has zero failed units, and readiness gates are green.

### Acceptance

MiniTZ is ready for an explicit ON command only when the fresh full qualification is green, lifecycle semantics match the owner contract, publication retries cannot block execution, target source state is coherent, current Task Program evidence is synchronized, and MiniTZ is still OFF.
