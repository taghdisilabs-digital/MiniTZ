# Biella Workstation Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one durable `biella` workstation interface that supervises local Qwen, exposes fast/full Codex agent modes, integrates configured production providers, uses the extra runtime disk, and removes known temporary runtime noise.

**Architecture:** A small Bash supervisor under `ops/workstation/` owns workstation commands and systemd installation. Existing local-AI scripts remain the authoritative Qwen warmup/provider helpers where appropriate; the supervisor composes them instead of creating another model stack. Provider failures are independent health states, not global startup blockers.

**Tech Stack:** Bash, systemd, Ollama HTTP APIs, Codex CLI, Modal CLI, curl, Python 3, existing Biella provider scripts.

**Spec:** `docs/superpowers/specs/2026-09-04-biella-workstation-supervisor-design.md`

## Global Constraints

- Keep `qwen3-coder-next:biella`, 26 GPU layers, 16K context, `keep_alive=-1`, and VRAM residency strictly below 30 GiB.
- Keep secrets only in `/root/.config/biella-ai/runtime.env` with root ownership and mode `0600`.
- Do not broadly migrate or delete production/evidence data.
- Do not kill Desktop Commander, SSH, Docker, or arbitrary processes.
- Healthy providers stay usable when another provider is degraded.

---

## Progress

- Task 1 — COMPLETED and verified 2026-09-04.
- Task 2 — COMPLETED and verified 2026-09-04.
- Task 3 — COMPLETED and verified 2026-09-04.
- Task 4 — COMPLETED and verified 2026-09-04.
- Task 5 — IN_PROGRESS.

### Task 1: Supervisor command contract

**Files:**
- Create: `ops/workstation/biella`
- Create: `ops/workstation/biella-lib.sh`
- Create: `ops/workstation/install-biella-workstation.sh`
- Create: `tests/workstation_supervisor_contract_test.sh`

**Interfaces:**
- Produces: `biella <up|down|status|doctor|agent|codex|providers|modal|logs|cleanup>`.

- [x] Write a failing contract test that requires all subcommands, root-only runtime loading, `/mnt/biella-extra/biella-runtime`, and no model-download command.
- [x] Run `bash tests/workstation_supervisor_contract_test.sh`; expect failure because files are absent.
- [x] Implement command dispatch and shared helpers without changing live services.
- [x] Run the contract test and `bash -n` on all new scripts; expect PASS.
- [x] Commit `feat: add Biella workstation supervisor interface`.
### Task 2: Durable Ollama service

**Files:**
- Create: `ops/workstation/biella-ollama.service`
- Modify: `ops/workstation/install-biella-workstation.sh`
- Modify: `tests/workstation_supervisor_contract_test.sh`

**Interfaces:**
- Produces: `biella-ollama.service` listening only on `127.0.0.1:11434` with current proven Qwen runtime environment.

- [x] Extend the contract test to require the exact Ollama environment values and `User=ollama`.
- [x] Run the contract test; expect failure because the service file is absent.
- [x] Add the systemd unit and installer logic that copies/enables it but does not touch model bytes.
- [x] Add `biella up` warmup checks for `/api/ps` and `/v1/responses` and the `<30 GiB` VRAM bound.
- [x] Run contract and existing local-AI smoke tests; expect PASS.
- [x] Commit `feat: supervise Biella Ollama with systemd`.

### Task 3: Fast and full agent modes with noise control

**Files:**
- Create: `ops/workstation/AGENTS.md`
- Create: `ops/local-ai/biella-local-agent.sh`
- Modify: `ops/local-ai/install-biella-ai.sh`
- Modify: `tests/local_ai_runtime_contract_test.sh`

**Interfaces:**
- Produces: `biella-local-agent` delegating to `biella-codex` with `mcp_servers.saturn.enabled=false`.
- Produces: global noise policy installed to `/root/.codex/AGENTS.md`.

- [x] Add failing tests requiring the local-agent wrapper and noise-policy installation.
- [x] Verify the tests fail for the missing artifacts.
- [x] Implement the delegating wrapper and policy; do not duplicate unrestricted flags already owned by `biella-codex`.
- [x] Run local-AI contract/smoke tests and supervisor contract tests.
- [x] Commit `feat: add fast local agent and noise control`.

### Task 4: Provider, storage, and cleanup integration

**Files:**
- Modify: `ops/workstation/biella`
- Modify: `ops/workstation/biella-lib.sh`
- Modify: `tests/workstation_supervisor_contract_test.sh`

**Interfaces:**
- `biella providers` reports configured provider HTTP health without response bodies or secrets.
- `biella cleanup` targets only known temporary Biella process signatures.
- `biella doctor` reports storage, GPU, binaries, MCP, Modal, provider, and Gemini status independently.

- [x] Add failing tests for independent provider health, runtime storage paths, and bounded cleanup signatures.
- [x] Implement runtime directories under `/mnt/biella-extra/biella-runtime/{cache,tmp,logs,builds,models}`.
- [x] Implement provider checker composition for Cloudflare, Groq, Cerebras, OpenRouter, Mistral, Tavily, Exa, Pinecone, Qdrant, Deepgram, AssemblyAI, ElevenLabs, Stability AI, Supabase, Neon, Upstash, Cloudinary, Axiom, Pexels, Modal, Saturn, and Gemini/Google independent status reporting.
- [x] Implement bounded cleanup for the legacy `llm-router`, ports 61374/81374 Python servers, and the matching quick tunnel only.
- [x] Run all shell contract/smoke tests and `git diff --check`.
- [x] Commit `feat: integrate providers storage and bounded cleanup`.
### Task 5: Install, cut over, and verify workstation

**Files:**
- Modify as needed from Tasks 1-4 only after verification evidence identifies a defect.

**Interfaces:**
- Produces installed `/usr/local/bin/biella`, `biella-local-agent`, `biella-codex`, and active `biella-ollama.service`.

- [ ] Run all repository shell tests and `git diff --check`; require zero failures before touching live service ownership.
- [ ] Install the supervisor and refreshed local-AI runtime from the isolated branch.
- [ ] Start `biella-ollama.service`, warm Qwen, verify native and `/v1` APIs, then retire the legacy `tmux llm-router` only after the service is healthy.
- [ ] Run `biella providers`; require the core verified provider set to remain healthy and require every additional lane to report an explicit independent state rather than blocking the workstation.
- [ ] Run Modal token info, Codex MCP list, GPU/VRAM checks, disk checks, and `biella doctor`.
- [ ] Run bounded cleanup and verify the known temporary HTTP/tunnel processes are gone while Desktop Commander remains online.
- [ ] Re-run all workstation acceptance checks after cleanup.
- [ ] Commit any evidence-driven fixes, verify branch clean, and fast-forward `main` only after all acceptance checks pass.

## Plan self-review

- Spec coverage: supervisor, systemd Ollama, fast/full agents, provider independence, noise control, extra runtime storage, bounded cleanup, and acceptance checks are all assigned to tasks.
- Placeholder scan: no incomplete implementation markers remain.
- Interface consistency: `biella-local-agent`, `biella-codex`, `biella-ollama.service`, and `biella` subcommands use the same names throughout.
