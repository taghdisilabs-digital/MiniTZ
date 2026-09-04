# Biella Codex Usage-Aware Feeder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested usage-aware task feeder behind the single `biella-codex` entrypoint and start the 50-task Demo-01 run.

**Architecture:** A small Python feeder owns queue parsing, task classification, model selection, observed-limit cooldowns, single-flight locking, fresh-context Codex execution, and progress persistence. The existing shell wrapper intercepts only the `feed` subcommand; normal interactive Codex behavior is unchanged.

**Tech Stack:** Python 3 standard library, Bash, Codex CLI, systemd-run for detached execution, Git.

**Spec:** `docs/superpowers/specs/2026-09-04-biella-codex-usage-aware-feeder-design.md`

## Global Constraints
- `biella-codex` remains the only AI/production entrypoint.
- Never invoke `/usage` or redeem usage resets.
- Creation tasks never use low reasoning.
- Hard/deep-memory tasks prefer `gpt-6-astra` with `ultra`.
- One feeder task at a time; preserve verified work.

---

### Task 1: Model selector and observed-limit state
**Files:** Create `ops/local-ai/biella_codex_feeder.py`; create `tests/test_codex_feeder.py`.
- [ ] Write failing tests for task-class routing, creation reasoning floor, Astra Ultra hard/deep routing, and cooldown fallback.
- [ ] Run focused tests and verify RED.
- [ ] Implement minimal pure selector/state logic.
- [ ] Run focused tests and verify GREEN.

### Task 2: Queue execution and checkpoint persistence
**Files:** Modify `ops/local-ai/biella_codex_feeder.py`; modify `tests/test_codex_feeder.py`.
- [ ] Write failing tests for 50-task queue continuity, resume, single-flight state, success advance, and usage-limit fallback without `/usage`.
- [ ] Verify RED, implement, verify GREEN.

### Task 3: Single-entrypoint integration
**Files:** Modify `ops/local-ai/biella-codex.sh`, `ops/local-ai/install-biella-ai.sh`, controller contract tests.
- [ ] Write failing shell/runtime contract for `biella-codex feed` and installed feeder path.
- [ ] Verify RED, implement wrapper/installer integration, verify GREEN.

### Task 4: Demo-01 queue and detached run
**Files:** Create a durable run queue under `/root/biella/work/demo01-codex-feeder/` at install/start time; no project-wide prompt files.
- [ ] Generate exactly 50 compact tasks with classes.
- [ ] Validate numbering, dependency order, and class constraints.
- [ ] Install exact verified source, start detached feeder, and read back status.

### Task 5: Regression, commit, publish
- [ ] Run focused feeder/controller tests plus existing workstation/control contracts.
- [ ] Commit coherent source, fast-forward main only if unchanged, push, remote-readback exact SHA.
- [ ] Verify live installed bytes and feeder status.
