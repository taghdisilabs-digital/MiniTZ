# Biella Engine — Version Log

Status: ACTIVE PRE-PRODUCTION REVISION RECORD  
Schema version: 1.0  
Current authoritative control revision: `1.0.1`  
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
| `1.0.1` | 2026-08-27 | ChatGPT Project, owner-directed | Founder requested items 10–14 | Identified the exact approved File Library reference source as `c287e56f-7700-452a-9884-af1276faaa1b.png` and completed `REFERENCE_NOTES.md`. Items 12–14 remain uncreated because authoritative geometry may not be guessed or traced from an unavailable raw source. | File Library reference identity + current brand/acceptance contracts. |

## Current authoritative files

| File | Revision/status | Notes |
|---|---|---|
| `BRAND_MASTER_SPEC.md` | `1.0` / APPROVED | Existing canonical Drive control document. |
| `LOCKED_VS_FLEXIBLE.md` | `1.0.0` / CURRENT | Defines immutable identity vs production freedom. |
| `FILE_NAMING_STANDARD.md` | `1.0.0` / CURRENT | Defines deterministic naming and versioning. |
| `FOLDER_STRUCTURE.txt` | `1.0.0` / CURRENT | Defines shared Codex/Biella package topology. |
| `VERSION_LOG.md` | `1.0.1` / CURRENT | This revision record. |
| `PRIMARY_REFERENCE.png` | `SOURCE_IDENTIFIED_NOT_YET_PACKAGED` | Exact File Library source identified as `c287e56f-7700-452a-9884-af1276faaa1b.png`; raw bytes are not yet mounted in the canonical package. |
| `REFERENCE_NOTES.md` | `1.0.1` / CURRENT | Reference-specific art direction and geometry interpretation boundaries. |
| `MASTER_LOGO_GEOMETRY.svg` | `NOT_CREATED` | Blocked on exact mounted `PRIMARY_REFERENCE.png` bytes; no approximate geometry may become authority. |
| `LOGO_CONSTRUCTION_SHEET.pdf` | `NOT_CREATED` | Must derive from approved master vector. |
| `LOGO_COMPONENT_MAP.pdf` | `NOT_CREATED` | Must derive from approved master vector. |

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
  primary_reference_file_id: SOURCE_IDENTIFIED_IN_FILE_LIBRARY_NOT_DRIVE

github:
  repository: patrickminitz-web/biella-engine
  branch: main
  package_path: docs/brand/preproduction
  result_commit: RECORDED_BY_COMMIT_CONTAINING_THIS_FILE
  result_tree: RECORDED_BY_COMMIT_CONTAINING_THIS_FILE
```

## Approval note

A downstream asset is not authoritative merely because it has a higher asset version number. Locked brand authority, approved master geometry, current package revision, and actual publication/readback evidence control.
