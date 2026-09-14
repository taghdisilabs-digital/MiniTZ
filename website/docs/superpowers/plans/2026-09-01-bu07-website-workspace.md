# BU-07 Website Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish a real, testable `biellagames.dev` website application workspace without mutating the active Engine `main` execution branch, with truthful asset/game-media boundaries and deployment evidence.

**Architecture:** Use `patrickminitz-web/biella-engine` branch `website` as an isolated Website Project workspace because no dedicated website repository exists and repository creation is not exposed by the connected GitHub actions. The app is a dependency-light static application built into `dist/`; Cloudflare Workers static assets is the intended production host, with version preview URLs and explicit rollback evidence when credentials/project access exist.

**Tech Stack:** HTML/CSS/ES modules, Node.js build script, Python unittest + Playwright 1.57.0 browser qualification, GitHub Actions, Cloudflare Workers static assets/Wrangler.

**Spec:** `docs/biellawebsite/MINITZ_UNIVERSE_36_TASK_MASTER_PACK.md` BU-07 plus current user-approved repair scope.

## Global Constraints

- Website Project scope only; no duplicate Engine scheduler/memory/routing/model/browser/validation systems.
- Never represent images, demos, or website UI as game runtime completion.
- Website visual slots 01-50 are not `MIGRATED_VERIFIED` without exact source bytes, Drive identity, SHA-256, and GitHub publication path.
- BU-16 may publish only `ACCEPTED_RUNTIME_MEDIA` tied to exact `biella-games` source/build identity and Mahdi acceptance.
- Git publication requires branch commit/tree/path readback.
- Preview/production deployment status is evidence-derived; missing Cloudflare credentials/project access remains unresolved, not success.

### Task 1: BU-07 application scaffold
- [ ] Keep failing contract tests as RED evidence.
- [ ] Create source entrypoint, styling, client script, build script, package metadata and Wrangler config.
- [ ] Build and run unit tests.

### Task 2: Website asset + game runtime media lanes
- [ ] Materialize all 50 manifest slots in a machine-readable ledger.
- [ ] Record exact-filename Drive search result (`0/50`) without inventing source matches.
- [ ] Create BU-16 accepted-runtime-media consumption contract with no fake accepted items.
- [ ] Run contract tests.

### Task 3: Governance + browser evidence
- [ ] Add Website `AGENTS.md` after source exists.
- [ ] Add browser test and execute against built output.
- [ ] Add CI workflow.

### Task 4: Deployment surfaces
- [ ] Add preview workflow using Cloudflare Worker version upload / preview URL when credentials exist.
- [ ] Add production workflow using explicit deploy plus endpoint readback.
- [ ] Add rollback workflow/API contract against a prior successful Worker version.
- [ ] Do not claim deployment unless a remote deployment ID/version URL and HTTP readback are observed.

### Task 5: Durable GitHub publication
- [ ] Create/update isolated `website` branch without changing Engine `main`.
- [ ] Remote-read branch commit/tree and critical files.
- [ ] Inspect workflow run evidence if GitHub schedules it.
