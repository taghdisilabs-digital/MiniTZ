# Biella Engine — Next 10 Execution Steps

> **For agentic workers:** REQUIRED SUB-SKILL: use Superpowers test-driven-development and verification-before-completion for implementation steps. Work one numbered step at a time. Stop after remote GitHub readback.

**Goal:** Resume Biella on durable non-Spot infrastructure, preserve already-tested evidence without pretending lost source bytes still exist, and advance the durable P0 kernel from current GitHub truth.

**Current infrastructure observation:** the replacement EC2 instance is `Lifecycle: normal`; the S3 bucket `biella-artifacts-backups-checkpoints` exists and is currently empty.

## Infrastructure decision

**CREATE NOW**
- one dedicated **200 GB gp3 EBS data volume** in the same Availability Zone as the replacement EC2 instance;
- attach it after launch so it is independent of the disposable root filesystem;
- mount it at `/srv/biella` and place all canonical working directories there;
- enable EC2 termination protection;
- enable S3 Versioning on `biella-artifacts-backups-checkpoints` if it is not already enabled;
- create a daily EBS snapshot policy for the Biella data volume, retaining 7 daily snapshots.

**DO NOT RENT NOW**
- no GPU is required for these 10 steps;
- do not rent H100/H200/B200-class compute until the local ModelProvider/resource-routing work is ready for real inference qualification;
- when a GPU is needed, use On-Demand/normal capacity for canonical work, not Spot.

## Global execution rule

Every implementation step uses:

`inspect current Git -> read exact contract -> failing focused test -> minimum implementation -> focused tests -> affected regressions -> inspect outputs -> commit -> push -> remote GitHub readback -> record exact commit/tree -> stop`

Previously observed P0-01 tests are valid historical execution evidence. They are not current GitHub source bytes. Re-establishment must use the exact Biella contract and may use the previous measurements as acceptance evidence/targets, but must not invent lost source.

---

## 1. Durable host and storage verification

**Action:** configure the replacement normal EC2 instance for machine-loss-safe work before writing Biella code.

**Codex prompt:**

```text
BIella infrastructure verification only. Do not modify application source.

1. Inspect mounted block devices and filesystems.
2. Confirm the dedicated persistent Biella data volume is mounted at /srv/biella and is writable.
3. Create only these working directories if absent:
   /srv/biella/repos
   /srv/biella/work
   /srv/biella/checkpoints
   /srv/biella/backups
4. Report filesystem type, device, total/free space, mount options, hostname, OS version, CPU/RAM, Git, Node/npm, Docker and AWS CLI versions if installed.
5. Do not install GPU/NVIDIA packages on a CPU-only host.
6. Do not create or modify Biella source yet.
7. Return a compact PASS/FAIL table and exact unresolved dependencies.
```

**Exit:** `/srv/biella` is persistent and writable.

## 2. Clone and establish the durable build workspace

**Action:** clone only from current GitHub `main` onto `/srv/biella` and establish Codex operating files.

**Codex prompt:**

```text
Work only in /srv/biella/repos/biella-engine.

Clone/fetch patrickminitz-web/biella-engine and inspect actual current main before editing. Do not reconstruct lost code from chat history.

Read first:
- docs/project-state/BIELLA_PROJECT_CONTEXT_SNAPSHOT_2026-08-26.md
- docs/superpowers/specs/2026-08-26-biella-build-structure-design.md
- docs/superpowers/plans/2026-08-26-biella-build-structure.md
- docs/superpowers/plans/2026-08-26-biella-next-10-steps.md

Create or update only the minimum durable operator files needed for Codex continuity:
- AGENTS.md
- CURRENT_TASK.md
- docs/operations/source-durability.md

Rules:
- GitHub remote source is code authority.
- Preserve previous P0-01 test evidence as prior evidence, not current source.
- No active product code or normal product docs should depend on the retired historical project name.
- No provider/GPU/cloud/database/model becomes a kernel primitive.
- Every accepted change must be committed, pushed, and remotely read back.

Run relevant doc/repo checks, commit, push main, then fetch the remote commit and tree and report them. Stop.
```

## 3. Re-establish P0-01 as durable Biella source

**Action:** rebuild the generic historical-source firewall from the exact P0-01 contract, preserving previously proven semantics without copying unavailable source.

**Codex prompt:**

```text
Execute Biella P0-01 only.

Use the exact current P0-01 contract supplied with this task. Treat the previous 35/35 tests + typecheck/build PASS as real prior evidence, not as source code.

Requirements:
- generic historical-source/quarantine semantics only;
- no retired project branding in active package/API names;
- content-addressed quarantine with provenance;
- semantic extraction;
- six canonical classifications;
- contamination-aware normalization;
- candidate-only output;
- active runtime/retrieval/memory exclusion;
- fail closed on unclassified/invalid admission;
- normal package root must not expose migration internals.

Use strict TDD:
1. write focused failing tests;
2. run and capture failure;
3. implement minimum task-scoped TypeScript/Node solution consistent with prior proven implementation evidence unless current repo evidence requires otherwise;
4. run focused tests;
5. run full affected tests, typecheck and build;
6. inspect package exports and generated artifacts;
7. commit and push;
8. fetch remote commit/tree and verify exact readback.

Return exact test counts, typecheck/build results, files changed, commit, tree, worktree status and limitations. Stop before P0-02.
```

## 4. P0-02 — Project Namespace / Isolation

**Codex prompt:**

```text
Execute Biella P0-02 only from the exact current P0-02 contract.

Implement Project namespace/isolation as a universal kernel primitive. Project-specific source, assets, rules, memory, acceptance, tools and publication targets must never leak into another Project or Engine defaults.

Use TDD. Test at minimum:
- unique Project identity;
- isolation of Project-scoped state;
- no cross-project read/write by default;
- no provider/model/GPU assumptions;
- previous P0-01 behavior remains intact.

Run focused tests, affected regressions, typecheck and build. Commit, push, remote-readback commit/tree, report exact evidence, then stop before P0-03.
```

## 5. P0-03 — Capability Contract

**Codex prompt:**

```text
Execute Biella P0-03 only from the exact current P0-03 contract.

Implement Capability as semantic ability independent of current hardware/provider/tool availability.

Test at minimum:
- stable capability identity/versioning;
- requirements/constraints are explicit;
- no provider/model/GPU/tool implementation embedded in Capability identity;
- unavailable Resources do not delete Capability existence;
- Project isolation remains intact.

Use TDD, run focused and affected regression tests, typecheck/build, commit, push, remote-readback exact commit/tree, report evidence, stop before P0-04.
```

## 6. P0-04 — Task Contract

**Codex prompt:**

```text
Execute Biella P0-04 only from the exact current P0-04 contract.

Implement immutable Task revisions describing what the Project wants, required inputs/outputs, constraints and acceptance conditions. Task must not encode worker topology, model choice, provider choice, GPU count or fixed agent pipeline.

Test at minimum:
- immutable Task revision N;
- modification creates N+1;
- exact Project binding;
- explicit required capabilities and output/acceptance contract;
- old revisions remain addressable;
- no execution topology leaks into Task.

Use TDD, run focused/affected tests, typecheck/build, commit, push, remote-readback, report exact evidence, stop before P0-05.
```

## 7. P0-05 — Run Identity / Attempts / Leases / Fencing

**Codex prompt:**

```text
Execute Biella P0-05 only from the exact current P0-05 contract.

Implement Run identity, attempts, leases, heartbeat/expiry semantics and monotonically advancing fencing so a stale executor can never finalize after a newer fence exists.

Test at minimum:
- stable run_id with separate attempt identity;
- lease acquisition/heartbeat/expiry;
- fence N rejected after N+1 exists;
- stale completion/failure/checkpoint rejection;
- restart-safe identity semantics;
- no fixed worker/provider/GPU assumptions.

Use TDD and include adversarial stale-worker tests. Run focused/affected tests, typecheck/build, commit, push, remote-readback, report evidence, stop before P0-06.
```

## 8. P0-06 — Artifact & Source Identity

**Codex prompt:**

```text
Execute Biella P0-06 only from the exact current P0-06 contract.

Implement the invariant:
Artifact != Content Object != Storage Location.

Exact bytes require cryptographic content identity. A corrupt/mismatched object must never be served as verified content merely because a storage location exists.

Test at minimum:
- SHA-256 exact content identity;
- same bytes at multiple locations resolve to one Content identity;
- different bytes never share verified identity;
- Artifact metadata can reference content without becoming content;
- storage relocation does not change content identity;
- digest mismatch/corruption fails closed.

Use TDD, regress P0-01..P0-05, typecheck/build, commit, push, remote-readback, report evidence, stop before P0-07.
```

## 9. P0-07 — Graph & Node Contract

**Codex prompt:**

```text
Execute Biella P0-07 only from the exact current P0-07 contract.

Implement immutable Graph revisions for one Run plan and Node as productive work. Replanning must create Graph revision N+1. Independent Nodes may be runnable concurrently when dependencies permit, but do not implement the full scheduler yet.

Test at minimum:
- immutable Graph revision;
- replan creates N+1;
- explicit Node dependencies;
- cycle rejection;
- readiness derived from dependency state;
- independent Nodes can both be READY;
- no fixed agent hierarchy/global pipeline.

Use TDD, run affected regressions, typecheck/build, commit, push, remote-readback, report evidence, stop before P0-08.
```

## 10. P0-08 — Event Ledger

**Codex prompt:**

```text
Execute Biella P0-08 only from the exact current P0-08 contract.

Implement append-only Event history attributable to Project/Task/Run/Graph/Node/attempt/fence where applicable. Events are durable execution evidence; do not turn telemetry logs into authority.

Test at minimum:
- append-only ordering/identity;
- no in-place event mutation;
- exact execution identity linkage;
- stale-fence events cannot authorize stale finalization;
- event replay can reconstruct the observed state transitions required by this prompt;
- no raw secrets/prompts embedded in generic telemetry/event correlation fields unless the Task explicitly stores them as content.

Use TDD, regress P0-01..P0-07, typecheck/build, commit, push, remote-readback, report exact evidence. Stop. Next batch begins with P0-09 Durable Execution State and P0-10 P0 Integration Qualification.
```

## GPU/local-AI timing

Do not install or rent GPU infrastructure during these 10 steps. After P0-10 and the early P1 resource/model contracts exist, rent one On-Demand H100 80GB or equivalent only for real local inference/adapter qualification. Ubuntu 26.04 is currently listed by NVIDIA as a supported NVIDIA Container Toolkit platform, so the replacement OS is compatible with the later GPU path.
