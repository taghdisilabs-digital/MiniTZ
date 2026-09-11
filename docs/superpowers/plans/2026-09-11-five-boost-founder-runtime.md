# MiniTZ Five-Boost Founder Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five isolated Boost workers over 30 Commander lanes, a single shared derived task projection, reserved-route awareness, two-slot GPU residency policy, Linux HAL/trust/browser-swarm task coverage, and website visibility without starting execution.

**Architecture:** The living MiniTZ Task Program remains the only progression authority. Five Boost lists and worker reports are digest-bound non-authoritative projections; hardware/trust/swarm readiness remains qualification-gated. Runtime and website surfaces consume sanitized projections only.

**Tech Stack:** Python 3.12, Bash, systemd source contracts, JSON, pytest, Node website build/tests.

**Spec:** `docs/superpowers/specs/2026-09-11-five-boost-founder-runtime-design.md`

## Global Constraints

- Do not start production, Ollama, Qwen residency, NVIDIA persistence, or Boost workers during this change.
- Preserve current canonical Task/Run identity while evolving the Task Program.
- Exactly five Boost groups, exactly six unique Commander lanes per group.
- No second queue, scheduler, progression authority, or overlapping active write scope.
- Linux-only HAL; no Windows compatibility work.
- Reserve at least 2,048 MiB GPU VRAM; visual slot remains unbound until qualified.
- Never probe quota/balance or expose raw credential values.

---
### Task 1: Five-Boost fabric and task lists

**Files:** `ops/local-ai/minitz_boost_fabric.py`, `tests/test_boost_fabric.py`

- [x] Test exact 5×6 Commander partition and 800-task derived lists.
- [x] Implement disjoint write-scope assignment and digest-bound current assignments.
- [x] Add worker report validation and shared `current.json` projection.
- [x] Add Linux HAL/trust/swarm/cache qualification prerequisites.

### Task 2: Autofeeder and Task Program evolution

**Files:** `ops/local-ai/biella_production_runner.py`, `ops/local-ai/minitz_task_program.py`, `ops/local-ai/minitz_founder_extension.py`, related tests.

- [x] Refresh Boost state only for `minitz-task-program` production.
- [x] Add Task Program SHA fast-path to avoid repeated 4,000+ row recomputation.
- [x] Add transactional `insert_tasks_after()` preserving current execution.
- [x] Define seven owner-approved canonical tasks and validate insertion/readback.

### Task 3: GPU residency policy

**Files:** `ops/workstation/minitz-gpu-residency.json`, Qwen/Ollama workstation source and tests.

- [x] Set Qwen to 34/48 GPU blocks with 35,828 MiB hard budget.
- [x] Reserve 8,192 MiB for a qualification-gated visual model and 2,048 MiB free.
- [x] Permit two loaded model slots without auto-downloading visual weights.
### Task 4: Control and public website projection

**Files:** control gateway projections plus `website/src/control/*`, `website/src/live/*` and tests.

- [x] Add detailed private Boost/task/Commander projection.
- [x] Add sanitized public five-Boost aggregate.
- [x] Add private Boosts view and public `5 BOOST WORKERS` metric.
- [x] Preserve read-only website authority and secret/path redaction.

### Task 5: Runtime packaging and owner sleep

**Files:** local-AI/workstation installers, owner-sleep wrapper and shell contracts.

- [x] Install Boost/founder modules and GPU residency policy.
- [x] Repair owner-sleep to call the installed handoff manager that actually exists.
- [x] Preserve prior service enablement/active state; never auto-start an inactive service.

### Task 6: Verification and live cutover

- [x] Run Boost/HAL/GPU/task-program/control affected-scope tests.
- [x] Run website unit tests and production build.
- [x] Run workstation/controller/runtime/control-gateway shell contracts.
- [x] Run Python/Bash syntax checks and `git diff --check`.
- [ ] Commit isolated branch and reconcile with current `main`.
- [ ] Apply seven-task Task Program extension and refresh 03/04 projections.
- [ ] Generate current five-Boost runtime task plan while execution remains stopped.
- [ ] Install source bytes without starting services and verify stopped/GPU-zero state.
