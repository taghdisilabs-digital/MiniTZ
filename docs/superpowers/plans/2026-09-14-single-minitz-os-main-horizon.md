# Single MiniTZ OS Main Horizon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one real MiniTZ OS from one canonical source tree and publish/qualify one installable/bootable OS artifact.

**Architecture:** Ubuntu 24.04 remains the host VPS OS. Ubuntu 26.04 sandbox contains the only MiniTZ OS source tree; the same tree drives development, installation, runtime, and release. MiniTZ uses one private GitHub repository with only `main`, and all capabilities, APIs, secrets, resources, memory, task execution, browser/computer control, UI, installation, update, recovery, and release logic live in that tree.

**Tech Stack:** Ubuntu 26.04 sandbox, Python, systemd, Docker/OCI where useful, NVIDIA L40S, Git/GitHub, MiniTZ Task Program.

**Spec:** `ops/workstation/AGENTS.md` section `SINGLE_MINITZ_OS_FINAL_AUTHORITY`

## Global Constraints

- One MiniTZ OS.
- One canonical source tree.
- One private GitHub repository.
- Exactly one active branch: `main`.
- No fork, no parallel repository, no split source.
- Ubuntu 24.04 VPS is host OS only.
- Ubuntu 26.04 sandbox is the MiniTZ OS build/qualification environment.
- Installed MiniTZ bytes derive from the same canonical source tree.
- One final bootable/installable OS artifact.
- All capabilities/APIs/secret/resource/memory/task behavior belong to MiniTZ OS.
- Windows is never a MiniTZ worker; owner-explicit auxiliary use only.
- Migration/unification is allowed only to transfer unique value into the target.
- Abandoned repos/branches/forks receive no future MiniTZ OS push.

---

### Task 1: Startup foundation
**Files:** `ops/local-ai/`, `ops/workstation/`, `tests/`
**Interfaces:** Consumes L40/GPU/runtime state. Produces a verified attached MiniTZ runtime before task execution.
- [ ] Write/extend tests asserting startup order: GPU/local LLM -> memory/cache/task attach -> control/resources -> Codex -> task execution.
- [ ] Run targeted startup tests and confirm the new assertions fail before implementation where coverage is missing.
- [ ] Implement the smallest startup/service changes without starting browser/Windows resources.
- [ ] Verify local AI residency, attached Task Program/memory/cache, control/resource health, and Codex availability.
- [ ] Commit on `main` only.

### Task 2: Single canonical source tree
**Files:** `src/`, `ops/`, `website/`, `pyproject.toml`, `tests/`
**Interfaces:** Consumes startup foundation. Produces one source/install/runtime authority rooted in the Ubuntu 26.04 sandbox repo.
- [ ] Add tests rejecting donor repo/runtime paths as active MiniTZ source authority.
- [ ] Remove split dev/install source paths and point installed services at the canonical tree/package output.
- [ ] Preserve required provenance before retiring legacy active aliases.
- [ ] Verify one source identity drives runtime and installation.
- [ ] Commit on `main` only.

### Task 3: Knowledge and capability transfer
**Files:** canonical MiniTZ source tree plus `docs/provenance/`
**Interfaces:** Consumes donor/legacy evidence as read-only input. Produces normalized MiniTZ-native capabilities and anti-regression knowledge.
- [ ] Inventory only value not already present in MiniTZ.
- [ ] Port proven mechanisms, acceptance rules, failure lessons, and reconstruction knowledge into canonical code/tests/docs.
- [ ] Record provenance and mark donor material non-authoritative.
- [ ] Verify no unique required value is lost before retirement.
- [ ] Commit on `main` only.

### Task 4: AI runtime and resource execution
**Files:** `ops/local-ai/`, `src/biella/resource.py`, `src/biella/routing.py`, `tests/`
**Interfaces:** Produces local LLM/GPU, Codex, provider, Boost/Commander, and resource routing under one Task Program authority.
- [ ] Test canonical writer/resource boundaries and Windows-not-a-worker.
- [ ] Qualify GPU residency and local model availability with protected headroom.
- [ ] Attach Codex/providers as replaceable resources without second authority.
- [ ] Verify Boost/Commander non-authoritative execution and recovery.
- [ ] Commit on `main` only.

### Task 5: Complete OS capability surface
**Files:** `src/biella/`, capability packs/tools, `tests/`
**Interfaces:** Produces software, web, game, 3D, character, animation, render, image, audio, video, filesystem/process/network, and API capabilities.
- [ ] Map every retained capability to MiniTZ capability/resource/action contracts.
- [ ] Migrate missing proven implementations into the canonical tree.
- [ ] Add task-derived validation and evidence for every capability family.
- [ ] Verify unavailable capabilities report truthful state rather than fake readiness.
- [ ] Commit on `main` only.

### Task 6: Human browser/computer and owner-attention capability
**Files:** `src/biella/browser_adapter.py`, owner-attention/audio modules, `ops/`, `tests/`
**Interfaces:** Produces persistent authenticated browser/computer/work execution plus human-boundary audio alerts.
- [ ] Test profile isolation, session persistence, foreground Chrome non-interference, and financial-surface deny-by-default.
- [ ] Implement authenticated GUI actions without requiring official APIs.
- [ ] Implement owner attention audio with multilingual provider-agnostic voice presets and temporary audio eviction.
- [ ] Verify CAPTCHA/2FA pauses and resumes the same Task/Run without bypass logic.
- [ ] Commit on `main` only.

### Task 7: Security, privacy, credentials, trust, and recovery
**Files:** secret/credential/trust/integrity/network/recovery modules and tests.
**Interfaces:** Produces protected secret references, privacy boundaries, trust anchors, offline degradation, integrity, and bounded rollback.
- [ ] Test raw-secret exclusion from prompts/logs/memory/artifacts.
- [ ] Implement/qualify credential broker and trust boundaries.
- [ ] Qualify integrity, network transition, restart continuity, and rollback.
- [ ] Run adversarial privacy/recovery tests.
- [ ] Commit on `main` only.

### Task 8: Normal-user MiniTZ OS surface
**Files:** `website/`, control/UI modules, doctor/operator tooling, tests.
**Interfaces:** Produces one discoverable UI/helper for normal users without requiring programming/admin expertise.
- [ ] Test discoverability and understandable running/succeeded/failed/needs-attention states.
- [ ] Integrate browser/computer/files/apps/tasks/runs/resources/memory/health into one MiniTZ surface.
- [ ] Implement doctor diagnostics and actionable repair explanations.
- [ ] Verify normal operation does not require hidden engineering steps.
- [ ] Commit on `main` only.

### Task 9: Install/update from the same source
**Files:** installer/provision/update/recovery packaging files and tests.
**Interfaces:** Produces deterministic install/first boot/update from the canonical source tree.
- [ ] Test that installation inputs resolve to the canonical source identity.
- [ ] Implement deterministic installation and first-boot provisioning.
- [ ] Implement signed update and rollback without a second source authority.
- [ ] Verify restart preserves task/memory/resource state.
- [ ] Commit on `main` only.

### Task 10: One private GitHub `main`
**Files:** `.git` remote configuration and publication policy; no second source tree.
**Interfaces:** Produces one private GitHub remote and remote-readback identity for `main`.
- [ ] Attach the owner-authorized private MiniTZ OS repository when credentials expose it.
- [ ] Remove donor local repo as `origin`; retain donor location only as provenance/read-only input if still needed.
- [ ] Verify default/active branch is `main` and no MiniTZ OS fork/parallel repo is used.
- [ ] Push canonical commits and read back exact remote commit/tree.
- [ ] Record abandoned repositories as zero-authority; do not delete without explicit owner instruction.

### Task 11: Bootable/installable MiniTZ OS artifact
**Files:** release/image build definitions, manifest, signing/integrity tests.
**Interfaces:** Consumes canonical source/install logic. Produces one bootable/installable OS artifact.
- [ ] Choose the technically correct boot artifact format for the supported target machines from current build evidence.
- [ ] Build the artifact only from the canonical source tree and record exact source/manifest digests.
- [ ] Boot/install it in an isolated qualification target.
- [ ] Verify first boot, GPU/CPU fallback, storage/network, MiniTZ services, and owner lifecycle.
- [ ] Commit build definitions/manifest on `main`; publish binary through approved release storage, not source duplication.

### Task 12: Full system qualification
**Files:** qualification tests/evidence only plus bounded fixes discovered by those tests.
**Interfaces:** Produces a release qualification receipt for the exact source and boot artifact.
- [ ] Run capability, security, recovery, performance, install, update, and clean-machine acceptance suites.
- [ ] Repair only failing bounded scopes and rerun affected regressions.
- [ ] Verify one source tree, one Task Program authority, one private `main`, and zero hidden donor runtime dependency.
- [ ] Bind qualification receipt to exact Git commit/tree and boot artifact digest.
- [ ] Commit final source fixes on `main`.

### Task 13: Owner acceptance and final closure
**Files:** canonical task/evidence/acceptance records.
**Interfaces:** Consumes the qualified source and artifact. Produces final MiniTZ OS acceptance.
- [ ] Prove install-to-usable MiniTZ on a clean supported target.
- [ ] Prove daily operation, local AI, browser/computer, capabilities, memory, recovery, update, and owner control.
- [ ] Confirm abandoned repositories/donor trees have zero authority and all required value has a MiniTZ destination.
- [ ] Confirm one private GitHub `main`, one canonical source tree, and one bootable/installable artifact.
- [ ] Close the Task Program only from evidence-backed owner acceptance.
