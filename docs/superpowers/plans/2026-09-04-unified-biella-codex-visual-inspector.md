# Unified Biella Codex + Visual Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use executing-plans task-by-task.

**Goal:** One root `biella-codex` controller with shared Codex project context and a private Visuals/Assets inspection layer.

**Architecture:** Collapse model-specific launchers into one controller wrapper and one `/root/.codex` authority. Extend the existing control gateway with an allowlisted asset index/preview API and update the existing Website control UI to consume it.

**Tech Stack:** Bash, Codex CLI 0.153.2, Python stdlib gateway/tests, static HTML/CSS/JS Website control UI, systemd, Git/GitHub.

**Spec:** `docs/superpowers/specs/2026-09-04-unified-biella-codex-visual-inspector-design.md`

## Global Constraints
- Preserve existing task/progress state and valid work.
- No new model-specific production authorities.
- Keep memory scopes distinct while sharing the Codex home/context layer.
- Historical/recovery assets are explicitly labeled and never auto-promoted.
- Context expansion is progressive and bounded.
- Existing control auth/operator/observer rules remain intact.

---

### Task 1: Single controller contract
- [ ] Add failing tests that require `biella-codex` as the only public AI controller and forbid Luna/Astra/model/work/local-agent public links.
- [ ] Replace controller wrapper with model-neutral root/Yolo/full-env behavior.
- [ ] Update installer/workstation CLI and remove old public links on install.
- [ ] Verify wrapper args and inherited provider environment with a deterministic stub.
### Task 2: Shared context and progressive guidance
- [ ] Add failing policy tests for one active Codex home and progressive context rules.
- [ ] Update root Codex policy so all controller models share project authority and context-loading behavior.
- [ ] Verify `.codex-local-qwen` contains no promotable memory rows; leave it inactive.

### Task 3: Control gateway asset API
- [ ] Add failing tests for allowlisted asset discovery, metadata, status/source class, and safe preview serving.
- [ ] Implement asset catalog with path containment and bounded scan/result limits.
- [ ] Add authenticated `/v1/control/assets` and `/v1/control/assets/file` endpoints.
- [ ] Verify no arbitrary filesystem read is possible through the endpoint.

### Task 4: Browser runner unification
- [ ] Update failing runner tests to require `/usr/local/bin/biella-codex` only.
- [ ] Launch noninteractive dialog through unified controller with progressive context contract.
- [ ] Verify browser dialog retains full environment and current lane as starting context only.

### Task 5: Visuals / Assets UI
- [ ] Add failing Website control-contract tests for the new panel and API usage.
- [ ] Implement filters, cards, image/video/audio previews and metadata/detail view.
- [ ] Build Website and run existing control/browser tests.

### Task 6: Install, live qualification and durability
- [ ] Run full affected Engine/control tests.
- [ ] Install unified controller and gateway; remove old public AI launcher symlinks.
- [ ] Build/install the Website control UI and restart gateway.
- [ ] Verify live authenticated assets endpoint, control URL, controller environment and existing tunnel/services.
- [ ] Commit/push Engine and Website branch changes and verify exact remote SHAs/readback.
