# P3-14 Durable Delivery Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Durably qualify the existing P3-14 delivery implementation and record only fresh GitHub evidence.

**Architecture:** Reuse the existing delivery contracts and focused tests. Add one task-scoped GitHub Actions workflow and one evidence record; update current-state files only after the workflow result and remote readback are observed.

**Tech Stack:** Python 3.11, pytest, mypy, setuptools wheel build, GitHub Actions, existing Biella Engine SQLite/object-store test fixtures.

**Spec:** `docs/superpowers/specs/2026-09-04-p3-14-durable-closure-design.md`

## Global Constraints

- `PACKAGE != PUBLISH != DEPLOY != RELEASE != VERIFY`.
- External publication requires existing Task/Run authority.
- P3-14 tests must use the existing source and preserve Project isolation.
- No historical or archived material enters current filings.
- No secret bytes enter GitHub, artifacts, or Drive.
- P4-06 and Website/Game consumer activation remain outside this change.
- Current-state claims require fresh workflow output and exact remote readback.

---

### Task 1: Add focused P3-14 qualification workflow

**Files:**
- Create: `.github/workflows/p3-14-delivery-qualification.yml`
- Test: `tests/test_p3_14_delivery_pack.py`
- Test: `tests/test_p3_14_delivery_local.py`
- Test: `tests/test_p3_14_delivery_publish.py`
- Test: `tests/test_p3_14_cross_domain.py`

**Interfaces:**
- Consumes the existing P3-14 delivery APIs and tests.
- Produces a GitHub Actions run, a wheel, and `dist/p3_14_delivery_qualification_evidence.json`.

- [ ] **Step 1: Add the workflow on the isolated branch**

The workflow must run on pushes to `main` and the isolated `codex/**` branches when P3-14 source/tests/workflow/state evidence paths change, and support manual dispatch. Its validation job must:

1. check out the exact commit;
2. install `.[test]`;
3. install FFmpeg because the cross-domain test builds and probes MP4 data;
4. run:
   `python -m pytest tests/test_p3_14_delivery_pack.py tests/test_p3_14_delivery_local.py tests/test_p3_14_delivery_publish.py tests/test_p3_14_cross_domain.py -q`;
5. run strict mypy over `delivery_pack.py`, `delivery_tool.py`, `cloudflare_kv_publish.py`, and `production_integration.py`;
6. run `python -m compileall -q src/biella`;
7. build a wheel with `python -m pip wheel . --no-deps -w dist`;
8. write the evidence JSON from the checked-out source and workflow environment;
9. upload the wheel and evidence JSON as a named artifact.

The evidence JSON must include the checked-out commit/tree, file SHA-256 values, command results, wheel SHA-256 values, and explicit `REFERENCE_CI`/ `NOT_RUN` classifications for unavailable external infrastructure. It must not include credentials or claim that CI is an L40S/GPU run.

- [ ] **Step 2: Verify workflow contents by remote file readback**

Read back the exact workflow blob from the isolated branch and confirm the required test, typecheck, compile, wheel, evidence, and artifact steps are present.

- [ ] **Step 3: Commit the workflow**

Commit message: `ci: qualify P3-14 durable delivery`.

---

### Task 2: Run and inspect fresh remote qualification

**Files:**
- Produced by workflow: `dist/p3_14_delivery_qualification_evidence.json`
- Produced by workflow: `dist/*.whl`

**Interfaces:**
- Consumes the workflow from Task 1.
- Produces the workflow run ID, job result, artifact ID, evidence digest, and test counts.

- [ ] **Step 1: Trigger qualification from the isolated branch**

Push the workflow commit to the isolated `codex/p3-14-durable-closure-20260904` branch so its branch-scoped trigger starts a fresh run; use manual dispatch only if the connector exposes it. Do not infer success from commit creation.

- [ ] **Step 2: Read the workflow run and job result**

Require an observed successful run. If it fails, preserve the failure result and stop P3-14 closure.

- [ ] **Step 3: Read the workflow artifact**

Read back the evidence artifact through GitHub’s workflow-artifact interface where available. Record its exact digest and the wheel identity. Do not claim external publication from this CI result.

---

### Task 3: Persist the P3-14 evidence record

**Files:**
- Create: `docs/project-state/evidence/P3_14_DELIVERY_QUALIFICATION_EVIDENCE.md`

**Interfaces:**
- Consumes exact workflow output from Task 2.
- Produces the durable human-readable P3-14 evidence record.

- [ ] **Step 1: Write the evidence document**

The document must record only observed values:

- task and exact source commit/tree;
- workflow run, job, and artifact identities;
- focused test result and counts;
- mypy, compile, and wheel results;
- source and evidence SHA-256 values;
- package/publish behavior covered by the existing tests;
- `REFERENCE_CI` and `NOT_RUN` classifications;
- no claim of L40S execution or live external publication unless separately observed;
- unresolved facts.

- [ ] **Step 2: Read back the exact document**

Verify the remote file contents and ensure no secret-like values, historical payload, or unsupported completion claim appears.

- [ ] **Step 3: Commit the evidence document**

Commit message: `docs: record P3-14 qualification evidence`.

---

### Task 4: Update current-state continuity

**Files:**
- Modify: `docs/project-state/03_BIELLA_CURRENT_STATE.md`
- Modify: `docs/project-state/04_BIELLA_ACTIVE_TASK.md`

**Interfaces:**
- Consumes the exact accepted result commit/tree and evidence identities from Task 3.
- Produces current P3-14 status and the next dependency pointer.

- [ ] **Step 1: Update only from observed qualification**

If and only if the complete focused workflow and artifact readback succeed, replace the P3-14 incomplete status with the exact observed durable result. Preserve P4-06 as incomplete unless its own evidence is present.

- [ ] **Step 2: Read back current-state files**

Verify the files point to the final commit/tree and evidence artifact, and that Website/Game activation is not claimed.

- [ ] **Step 3: Commit continuity updates**

Commit message: `docs: close P3-14 durable delivery boundary`.

---

### Task 5: Final verification and publication handoff

**Files:**
- Final branch commit/tree and changed files.

**Interfaces:**
- Consumes all preceding observed identities.
- Produces exact remote readback for GitHub and the Drive update payload.

- [ ] **Step 1: Read back final branch commit/tree**

Confirm all intended files exist and no unrelated files changed.

- [ ] **Step 2: Verify the final acceptance checklist**

Confirm that package integrity, project isolation, external-state distinction, and evidence durability are represented by observed test/workflow output.

- [ ] **Step 3: Publish the exact evidence document and state updates to the canonical Drive locations**

Use the current Drive P3-14 continuity locations. Preserve existing Drive organization and do not upload secrets, historical payloads, or unverified claims.

- [ ] **Step 4: Read back Drive content**

Verify the exact published bytes/text and record the Drive file IDs/revision outcomes.

- [ ] **Step 5: Commit final handoff metadata if required**

Use a separate commit only when the verified Drive IDs or publication state must be recorded in GitHub.
