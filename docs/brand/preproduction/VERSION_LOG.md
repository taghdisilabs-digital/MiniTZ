# Biella Engine — Version Log

Status: ACTIVE PRE-PRODUCTION REVISION RECORD  
Schema version: 1.0  
Current authoritative control revision: `1.0.0`  
Package completion status: `IN_PROGRESS`

## Rules

- Record every approved change that alters a canonical control document, authoritative source asset, geometry, material system, motion source, export requirement, or delivery rule.
- Do not use this log to claim an asset exists unless its exact file is present and verified.
- Git commit identity and Drive file identity should be added after publication/readback.
- Derived exports inherit the source revision they were generated from.
- Superseded files remain historical/version-control evidence; they are not current authority.
- The current authoritative revision is the newest approved revision whose required source files and publication evidence are valid.

## Revision format

Use semantic control revisions:

```text
MAJOR.MINOR.PATCH
```

- `MAJOR`: founder-approved change to locked identity, master geometry, or package contract.
- `MINOR`: approved new production subsystem/specification or materially expanded deliverable set.
- `PATCH`: correction that does not change locked identity or intended outputs.

Asset working versions (`v001`, `v002`, …) remain separate from this package-level revision.

## Revision history

| Revision | Date | Changed by | Approval | What changed | Authority / evidence |
|---|---|---|---|---|---|
| `1.0.0` | 2026-08-27 | ChatGPT Project, owner-directed | Founder request approved | Established approved pre-production control baseline. Existing `BRAND_MASTER_SPEC.md` remains the brand authority. Added `LOCKED_VS_FLEXIBLE.md`, `FILE_NAMING_STANDARD.md`, `FOLDER_STRUCTURE.txt`, and this `VERSION_LOG.md`. Reserved exact root identity `PRIMARY_REFERENCE.png` but did not fabricate or substitute image bytes because the exact founder-supplied reference file is not currently retrievable. | Drive/Git identities to be recorded after successful publication/readback. |

## Current authoritative files

| File | Revision/status | Notes |
|---|---|---|
| `BRAND_MASTER_SPEC.md` | `1.0` / APPROVED | Existing canonical Drive control document. |
| `LOCKED_VS_FLEXIBLE.md` | `1.0.0` / CURRENT | Defines immutable identity vs production freedom. |
| `FILE_NAMING_STANDARD.md` | `1.0.0` / CURRENT | Defines deterministic naming and versioning. |
| `FOLDER_STRUCTURE.txt` | `1.0.0` / CURRENT | Defines shared Codex/Biella package topology. |
| `VERSION_LOG.md` | `1.0.0` / CURRENT | This revision record. |
| `PRIMARY_REFERENCE.png` | `UNRESOLVED_EXACT_SOURCE` | Required exact founder-approved image. No substitute may be created. |

## Publication record

Populate only from actual readback:

```yaml
drive:
  folder: BIELLA_BRAND_PREPRODUCTION
  folder_id: 1Jt_dzBVJXQqM4VffdxTllNgawdXxcBk1
  locked_vs_flexible_file_id: 1L6I0FZM8Ezj_Oyhi8Bk3S9TyNqS9a2j5
  file_naming_standard_file_id: 1f5DxACecV-pFG_CJNtRHSCAx0Ydi11nJ
  folder_structure_file_id: 1aamryGAVkvtt4DkvrNB6S1Jk3ifNDtkO
  version_log_file_id: 1Kc82Z19GT-LuBN7W9HtWyzlatVy4YDHp
  primary_reference_file_id: UNRESOLVED_EXACT_SOURCE

github:
  repository: patrickminitz-web/biella-engine
  branch: main
  package_path: docs/brand/preproduction
  result_commit: RECORDED_BY_COMMIT_CONTAINING_THIS_FILE
  result_tree: RECORDED_BY_COMMIT_CONTAINING_THIS_FILE
```

## Approval note

A downstream asset is not authoritative merely because it has a higher asset version number. Locked brand authority, approved master geometry, current package revision, and actual publication/readback evidence control.
