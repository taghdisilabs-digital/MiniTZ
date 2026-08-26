# Biella Engine Source Lineage Reconciliation

Status: ACTIVE SOURCE-STATE EVIDENCE  
Observed: 2026-08-26  
Repository: `patrickminitz-web/biella-engine`

## Purpose

This file records a verified source-control discrepancy without rewriting either history or reconstructing missing source bytes.

## Verified local engine history

The Biella living Drive records preserve a direct local-Git observation from `/home/ubuntu/biella-work/biella-engine`:

- branch: `main`
- bootstrap root: `a84049a310d983604775ce42e8d619b0c10b592e`
- P0-01 commit: `b7cc3db0a9feb34d72764261d32163d2b05ac123`
- P0-01 tree: `ec44bacc13e11f9c38c1b5ac7c3844ac74f24a11`
- commit message: `feat: implement P0-01 migration firewall`
- worktree at verification: clean
- tests at verification: `35/35` plus typecheck/build PASS

That evidence came from direct local repository/source/test inspection. It remains the strongest evidence currently available for the implemented P0-01 engine state.

## Verified connected GitHub history

The connected private GitHub repository is accessible. Its history was independently initialized with:

- root commit: `dd60e06585cd306760f9e43622b31cedac721161` — `Create README.md`
- pre-reconciliation head: `f160c3cf187a4e526a6462a4038799ba5d5b4d43` — `Add Biella website asset manifest`
- pre-reconciliation content: `README.md` plus Biella website/document specifications under `docs/biellawebsite/`
- source-lineage commit: `dd9f119891840a11cf444e66c2d801294e80e11d`
- reconciliation merge: `01d06c2268fc28d2c5920911ec1c5872e677b19b` — merge of PR #1
- additional observed documentation before that merge: `docs/superpowers/specs/2026-08-26-biella-build-structure-design.md` and `docs/superpowers/plans/2026-08-26-biella-build-structure.md`

Fresh comparison from `f160c3cf187a4e526a6462a4038799ba5d5b4d43` to the post-merge `main` showed only documentation/source-state additions. The recorded local P0-01 commit `b7cc3db0a9feb34d72764261d32163d2b05ac123` is still not resolvable in connected remote history, and searches for `P0-01`, `migration firewall`, and `ActiveReferenceBoundary` found no remote engine implementation.

Therefore the connected GitHub history and the last verified local engine history do not share the recorded Biella engine root.

## Root cause supported by evidence

The Drive continuity records show that the local Biella repository had a configured GitHub origin but no configured upstream, and explicitly recorded that remote HEAD had not been inspected. The connected GitHub history was later initialized independently with a README root.

This is consistent with two Git histories that started independently. It is not evidence that P0-01 was never implemented; it is evidence that the verified local engine history was not present in the connected remote history.

## Safety preservation completed

The exact pre-reconciliation remote website/document head is preserved at:

- `archive/website-history-20260826` -> `f160c3cf187a4e526a6462a4038799ba5d5b4d43`

The reconciliation record was created at:

- `dd9f119891840a11cf444e66c2d801294e80e11d`

PR #1 merged that record into `main` at:

- `01d06c2268fc28d2c5920911ec1c5872e677b19b`

The temporary `reconcile/source-lineage-20260826` branch was deleted after merge. Remote `main` was not force-reset or rewritten by this correction; it advanced through normal documentation commits and the merge. Its ancestry remains rooted at the independently initialized README root `dd60e06585cd306760f9e43622b31cedac721161`.

## Required exact reconciliation when the local Git object database is accessible

Do not reconstruct P0-01 from planning documents, Drive prose, interface registries, or generated code.

Reconciliation must start by re-reading `/home/ubuntu/biella-work/biella-engine` and verifying that the exact recorded objects still exist:

- `a84049a310d983604775ce42e8d619b0c10b592e`
- `b7cc3db0a9feb34d72764261d32163d2b05ac123`
- tree `ec44bacc13e11f9c38c1b5ac7c3844ac74f24a11`

If those objects are present, preserve/export them exactly before changing remote engine ancestry. Preserve the current documentation history separately, then replay or otherwise integrate the desired documentation files onto the verified clean engine history without making the independently initialized README root the permanent Biella engine ancestry.

Do not use an unrelated-history merge merely because Git permits it: Biella's existing project rule is that the clean engine history has one bootstrap root and does not acquire unrelated product/history roots accidentally.

If the exact local objects are absent, mark the P0-01 source bytes as missing and perform recovery; do not fabricate them from documentation.

## Source-truth interpretation

Until exact local Git is re-inspected:

1. the P0-01 implementation claim is a last-directly-verified local repository fact;
2. connected GitHub `main` is a live remote containing website, planning/design, and source-state documentation, not verified P0-01 engine code;
3. the archive branch preserves the exact pre-reconciliation documentation head;
4. neither history should be destroyed to make documentation look consistent;
5. MiniTZ history remains historical evidence only and is not a repair source for Biella Git ancestry.

## External reference

GitHub documents adding an existing local repository to GitHub as an import of the existing repository/revision history. Git documents `--allow-unrelated-histories` as an exceptional override for histories that began independently. Those mechanisms explain the discrepancy but do not override Biella's clean-history requirement.
