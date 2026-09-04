# P3-14 Durable Delivery Closure Design

**Date:** 2026-09-04  
**Owner:** Mahdi Taghdisi  
**Scope:** Biella Engine P3-14 only

## Goal

Make the already-present P3-14 delivery implementation durably reproducible and observable by running its focused package/publish/cross-domain tests in GitHub Actions, emitting a bounded evidence artifact, and recording current-state pointers only from fresh results.

## Existing implementation

P3-14 implementation already exists in:

- `src/biella/delivery_pack.py`
- `src/biella/delivery_tool.py`
- `src/biella/cloudflare_kv_publish.py`
- `src/biella/production_integration.py`
- `tests/test_p3_14_delivery_pack.py`
- `tests/test_p3_14_delivery_local.py`
- `tests/test_p3_14_delivery_publish.py`
- `tests/test_p3_14_cross_domain.py`

The implementation already separates package assembly, local verification, upload, remote readback, release state, and ambiguous outcomes. This change qualifies that surface and makes its evidence durable; it does not redesign those contracts.

## Boundaries

- Engine remains the reusable kernel and delivery implementation owner.
- Website and Games remain separate consumers; no consumer activation is claimed here.
- P4-06 remains a separate qualification boundary.
- No historical, archived, MiniTZ, or unverified production payload is imported into current filings.
- No new manager, reviewer hierarchy, router, model endpoint, or security architecture is introduced.
- No secret or signing-key bytes are stored in code, GitHub artifacts, or Drive evidence.

## Design

1. Add a focused GitHub Actions workflow for P3-14.
2. Run the four existing focused P3-14 test modules, strict mypy for the delivery sources, compileall, and wheel build.
3. Emit a machine-readable CI evidence file containing:
   - exact GitHub source commit and tree;
   - source/test file SHA-256 values;
   - test command and observed result;
   - typecheck, compile, and wheel results;
   - explicit reality classifications;
   - no credentials or aggregate authority fields.
4. Upload the wheel and evidence artifact.
5. Add a durable P3-14 evidence document only after the workflow result is observed.
6. Update `docs/project-state/03_BIELLA_CURRENT_STATE.md` and `04_BIELLA_ACTIVE_TASK.md` only with the exact observed commit/tree, workflow run, artifact, and evidence digest.
7. Read back the remote commit/tree and verify the final files before any completion statement.

## Failure semantics

- A package test failure leaves P3-14 incomplete.
- A typecheck, compile, or wheel failure leaves P3-14 incomplete.
- A local package verification result does not imply remote publication.
- A successful upload without readback remains uploaded/unverified.
- Any ambiguous external side effect remains `OUTCOME_UNKNOWN`.
- Existing verified work is retained; no cleanup or destructive synchronization is performed.

## Acceptance evidence

P3-14 can be marked durably complete only when fresh GitHub Actions output proves the focused tests, strict typecheck, compile, and wheel build, and the resulting evidence artifact is read back with its exact digest. The evidence document must preserve the distinction between CI/reference execution and any real external infrastructure result.
