# Four-Month Portfolio Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the apex website with a clear, visual-first four-month portfolio while preserving the current immutable release and all existing secondary/live routes.

**Architecture:** Keep the existing static build and deployment topology. Add one canonical portfolio JSON dataset and one media manifest, render the story/projects/archive client-side from those bounded files, and copy only explicitly approved repository media into the release. `/live/`, `/investors/`, and `/control/` remain separate surfaces.

**Tech Stack:** Static HTML/CSS/ES modules, Node build script, Python unittest contracts, Playwright browser tests, existing local immutable release deployer.

**Spec:** `docs/superpowers/specs/2026-09-12-four-month-portfolio-site-design.md`

## Global Constraints
- Current deployed release `e071c1bd1843389da16f6924bb88f5f062878196` must remain intact.
- Do not claim “years”; primary chronology is roughly four months, May–September 2026.
- Do not fabricate G26-G50 or complete-game status for G22/G25.
- Actual media only; missing media remains explicit.
- Preserve `/live/`, `/investors/`, `/control/`.
- No host OS installation/configuration mutation.

---

### Task 1: Portfolio data contract and regression tests
**Files:**
- Create: `website/content/portfolio-index.json`
- Create: `website/content/portfolio-media.json`
- Modify: `website/tests/test_contracts.py`

**Interfaces:**
- Produces: `portfolio-index.json` records consumed by home/archive JS.
- Produces: `portfolio-media.json` with repo-relative source paths copied by build.

- [ ] Add failing tests requiring five primary nav destinations, `FOUR MONTHS`, G01-G25 presence, no G26, G22/G25 non-complete statuses, archive route, and build-time portfolio data copy.
- [ ] Run targeted contract tests and confirm RED.
- [ ] Add canonical data files with evidence-safe statuses and URLs.
- [ ] Run targeted tests and confirm GREEN.

### Task 2: Home story, timeline, projects, and archive preview
**Files:**
- Modify: `website/src/index.html`
- Modify: `website/src/styles.css`
- Modify: `website/src/app.js`
- Modify: `website/tests/browser/test_site.py`

**Interfaces:**
- Consumes: `/data/portfolio-index.json`, `/data/portfolio-media.json`, existing `/live-api/snapshot`.
- Produces: filterable project cards and visual preview without changing production authority.

- [ ] Add failing browser/contract assertions for hero, timeline, filters, project count, evidence labels, archive link, and live link.
- [ ] Run tests and confirm RED.
- [ ] Implement the visual-first home and responsive behavior.
- [ ] Run tests and confirm GREEN on desktop/mobile.

### Task 3: Dense Visual Archive route
**Files:**
- Create: `website/src/archive/index.html`
- Create: `website/src/archive/styles.css`
- Create: `website/src/archive/app.js`
- Modify: `website/scripts/build.mjs`
- Modify: `website/tests/browser/test_site.py`

**Interfaces:**
- Consumes: media manifest entries with public release URL/category/status/project.
- Produces: `/archive/` masonry-style lazy media wall with category/status filtering.

- [ ] Add failing archive browser assertions.
- [ ] Run and confirm RED.
- [ ] Implement archive route and media copying.
- [ ] Run and confirm GREEN.

### Task 4: Recovered media bundle
**Files:**
- Create/Populate: `website/reference/portfolio/`
- Modify: `website/content/portfolio-media.json`

**Interfaces:**
- Media source paths are immutable repo-relative inputs; release URLs live under `/portfolio-media/`.

- [ ] Capture/preserve public site visuals that are safe to publish.
- [ ] Add selected existing MiniTZ/Biella Games/investor media with provenance/status labels.
- [ ] Build and verify every manifest URL exists in `dist`.
- [ ] Verify no raw credentials/config/log screenshots are included.

### Task 5: Full validation and immutable deployment
**Files:**
- Build output only; existing deployer creates `/var/lib/biella-website/releases/<commit>`.

- [ ] Run all website unit/contract tests.
- [ ] Run production build with exact source commit/tree identity.
- [ ] Run desktop/mobile browser tests against build.
- [ ] Commit only website/spec/plan files on isolated branch.
- [ ] Merge/cherry-pick the website commit into canonical repo without unrelated dirty paths.
- [ ] Execute existing website live deploy mechanism.
- [ ] Verify current symlink points to new immutable release while old `e071c1bd…` remains.
- [ ] Verify `https://taghdisilabs.digital/`, `/archive/`, `/live/`, `/deployment.json` by remote HTTP readback.
