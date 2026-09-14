# MiniTZ AI Peer Resources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitHub Copilot as a digest-bound MiniTZ full-agent peer for Codex, with scoped Cloudflare BYOK fallback, while preserving existing Antigravity, direct local-Qwen, and Commander/resource paths.

**Architecture:** Extend the existing `biella_main_coder` peer contract rather than creating another agent system. Copilot peer execution is read-only, task/capsule/projection bound, content-addressed, schema validated, and nonblocking. Native Copilot is used when qualified; an already-qualified ACTIVE Antigravity peer remains valid. When native Copilot is genuinely unavailable, scoped Copilot+Cloudflare is the BYOK fallback. Direct local-Qwen remains a MiniTZ local Resource and is not auto-wrapped by Copilot unless its persisted profile matches residency.

**Tech Stack:** Python 3, GitHub Copilot CLI 1.0.83, Ollama 0.33.2 / qwen3-coder-next:biella, existing MiniTZ task packet/memory/Commander runtime, pytest.

**Spec:** `docs/superpowers/specs/2026-09-12-minitz-ai-peer-resources-design.md`

## Global Constraints
- TASK_PROGRAM.json remains the only task/order/status/progression authority.
- Bind all work to CODEX-L40-BRIDGE-01 rev 2 / task digest bad155270bc76f93055d966a7711a84fe0b0900585e565792d02aa40887197d7 / Program rev 66 until canonical authority changes.
- Preserve the dirty live MiniTZ workspace; no reset, stash, broad clean, or task replay.
- No raw credential values in prompts, semantic memory, source, ordinary logs, or evidence.
- API acquisition is permitted only when current qualified resources cannot satisfy the peer contract.
- Do not probe quota merely to discover quota.

---

### Task 1: Copilot peer adapter contract
**Files:** Modify `ops/local-ai/biella_main_coder.py`; Test `tests/test_main_coder_pool.py`.
**Interfaces:** Produce `copilot_session_id(...)`, `build_copilot_peer_command(...)`, `classify_copilot_observation(...)`, and Copilot-aware coder selection without changing existing AGR interfaces.
- [ ] Write failing tests for deterministic digest-bound Copilot session identity, read-only command permissions, local-Qwen BYOK env, failure classification, and coder-role ordering.
- [ ] Run focused tests and verify RED for missing Copilot APIs.
- [ ] Implement the minimal adapter helpers. Read-only command must deny `write` and `shell`, use current repo cwd, use a task-digest-derived session UUID, and request only a silent prompt response.
- [ ] Build child env without logging secret values; local-Qwen profile sets only provider base URL/type/model and requires no key.
- [ ] Run focused tests GREEN.

### Task 2: Runner peer integration
**Files:** Modify `ops/local-ai/biella_production_runner.py`; Test `tests/test_production_runner.py` and `tests/test_main_coder_pool.py`.
**Interfaces:** Existing `_launch_main_coder_peer_assist` accepts `peer_coder='copilot'`; collection parses the silent Copilot response as schema JSON and classifies failure without blocking Codex.
- [ ] Write failing tests showing Copilot peer launch is read-only, receives current capsule/projection refs, and a failed Copilot peer leaves Codex route intact.
- [ ] Run focused tests RED.
- [ ] Add Copilot branch to peer launch/collection and peer route selection. Prefer Copilot as Codex's full-agent peer; retain AGR fallback.
- [ ] Preserve content-addressed peer keys and accepted/rejected evidence format.
- [ ] Run focused tests GREEN.

### Task 3: Native-to-Cloudflare Copilot fallback
**Files:** Modify `ops/local-ai/biella_main_coder.py`, `ops/local-ai/biella_production_runner.py`; Test `tests/test_main_coder_pool.py`, `tests/test_production_runner.py`.
**Interfaces:** On genuine native Copilot auth/quota/offline failure, one Copilot+Cloudflare attempt may run using only the existing protected Cloudflare account/token injected at child-process boundary. Local-Qwen remains direct MiniTZ intelligence and the Copilot-Qwen path is unavailable unless persisted model parameters match the resident profile.
- [x] Write failing tests for fallback eligibility, protected credential injection, minimal child environment, and no fallback on schema/content rejection.
- [x] Run RED.
- [x] Implement one bounded Cloudflare fallback without quota probing or recursive fan-out; reject automatic Copilot-Qwen routing when model-profile readiness fails.
- [x] Ensure fallback result records backend profile/model identity.
- [x] Run GREEN.

### Task 4: Task prompt discoverability
**Files:** Modify `ops/local-ai/biella_task_packet.py` or the smallest existing prompt surface; Test `tests/test_task_packet.py` or the closest current test.
**Interfaces:** Codex learns that a validated peer assist may exist and that peers are resources/evidence only.
- [ ] Write a failing prompt-contract test.
- [ ] Run RED.
- [ ] Add one concise peer-resource instruction; do not add another workflow or approval gate.
- [ ] Run GREEN.

### Task 5: Functional qualification
**Files:** Create task-owned evidence under `/root/biella/analysis/codex_l40_bridge/`; no canonical task mutation.
**Interfaces:** Evidence binds Program rev/digest, task rev/digest, capsule/projection digests, backend/model, and read-only verdict.
- [ ] Run focused pytest for main-coder/runner/task-packet paths.
- [ ] Run native Copilot exact-schema peer probe against current task context.
- [ ] Run Copilot+Cloudflare exact-schema peer probe. Preserve the failed Copilot-Qwen receipt as negative qualification evidence; do not replay it under the same incompatible profile.
- [ ] Confirm Antigravity compatibility tests still pass; do not re-probe known account eligibility merely for quota/status discovery.
- [ ] Run secret-value verifier on new prompt/evidence/code surfaces.
- [ ] Persist a machine-readable qualification receipt; task completion remains canonical-controller-owned.

### Task 6: Existing API provider extension only if required
**Files:** Prefer no source change. If a required provider credential is invalid/missing, update only protected MiniTZ credential state/config through existing `biella configure` or provider-specific authorized flow.
- [ ] Check non-secret provider health/status first.
- [ ] If Copilot native + Cloudflare fallback + direct local Qwen + existing connected API helpers satisfy acceptance, do not create new credentials.
- [ ] If a required path still lacks a usable provider, obtain the minimum owner-authorized API credential, store it only in MiniTZ protected private state, validate one real capability call, and record only non-secret metadata/receipt.
