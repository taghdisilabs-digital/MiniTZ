# Biella Engine — Final ZIP Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Package revision target: 1.2.0

## 1. Purpose

This document defines the exact final archive contract for the Biella Engine brand production package.

A ZIP is not valid merely because compression succeeds. Release requires validated source, exports, QA evidence, clean extraction and hash readback.

## 2. Exact archive name

First authoritative release archive:

`BIELLA_ENGINE_BRAND_MASTER_v001.zip`

Subsequent approved archive versions increment only the three-digit asset version:
- `BIELLA_ENGINE_BRAND_MASTER_v002.zip`
- `BIELLA_ENGINE_BRAND_MASTER_v003.zip`

Do not use `final`, `final2`, `latest`, dates-only versioning, personal names or spaces.

## 3. Required internal root

The archive must contain exactly one package root:

`BIELLA_BRAND_PREPRODUCTION/`

Do not:
- place package files loose at ZIP root;
- add a redundant wrapper folder;
- rename internal paths during compression;
- change package topology only for the ZIP.

`FOLDER_STRUCTURE.txt` remains the directory authority.

## 4. Required root files

The following must exist directly inside `BIELLA_BRAND_PREPRODUCTION/`:

1. `BRAND_MASTER_SPEC.md`
2. `ASSET_MANIFEST.json`
3. `INTRO_SCENE_BRIEF.md`
4. `ACCEPTANCE_CRITERIA.md`
5. `TECHNICAL_DELIVERY_SPEC.md`
6. `LOCKED_VS_FLEXIBLE.md`
7. `FILE_NAMING_STANDARD.md`
8. `FOLDER_STRUCTURE.txt`
9. `VERSION_LOG.md`
10. `PRIMARY_REFERENCE.png`

No root control file may be silently relocated.

## 5. Required control files in subfolders

The final package must also contain the remaining canonical control assets at the paths defined by `FOLDER_STRUCTURE.txt`, including:

- `01_REFERENCE/REFERENCE_NOTES.md`
- `02_LOGO/MASTER_LOGO_GEOMETRY.svg`
- `02_LOGO/LOGO_CONSTRUCTION_SHEET.pdf`
- `02_LOGO/LOGO_COMPONENT_MAP.pdf`
- `01_REFERENCE/EXPLODED_STATE_REFERENCE.png`
- `01_REFERENCE/ASSEMBLED_STATE_REFERENCE.png`
- `01_REFERENCE/ACTIVE_STATE_REFERENCE.png`
- `03_BRAND_SYSTEM/MATERIAL_PALETTE.pdf`
- `03_BRAND_SYSTEM/COLOR_TOKENS.json`
- `03_BRAND_SYSTEM/TYPOGRAPHY_SPEC.md`
- `03_BRAND_SYSTEM/PBR_MATERIAL_SPEC.md`
- `04_3D/PIVOT_CONNECTOR_SPEC.md`
- `05_MOTION/CAMERA_SHOT_LIST.md`
- `05_MOTION/LIGHTING_PRESETS.md`
- `05_MOTION/FX_REQUIREMENTS.md`
- `05_MOTION/MOTION_LAYER_SPEC.md`
- `06_RENDER/RENDER_PASS_SPEC.md`
- `07_LOADING_SCREENS/LOADING_SCREEN_MATRIX.md`
- `08_UI/UI_ASSET_LIST.md`
- `09_CORPORATE/CORPORATE_ASSET_LIST.md`
- `10_PHYSICAL/PHYSICAL_APPLICATION_LIST.md`
- `11_EXPORTS/EXPORT_MATRIX.csv`
- `12_QA/QA_CHECKLIST.md`
- `13_DELIVERY/README_TEMPLATE.md`
- `13_DELIVERY/FINAL_ZIP_SPEC.md`

A release may not be marked complete while any required manifest item remains `NOT_CREATED`, blocked or unverified.

## 6. Required production source

Before final compression, the package must include the actual approved editable source required by `TECHNICAL_DELIVERY_SPEC.md`, including:
- authoritative vector master;
- native separated 3D source;
- motion/compositing source where meaningful post-production exists;
- PBR source textures where used;
- reproducible render source;
- production-ready physical-manufacturing source;
- package documentation and QA evidence.

Interchange formats never replace native editable source.

## 7. Required exports

All mandatory rows in `11_EXPORTS/EXPORT_MATRIX.csv` must exist.

Rows marked `YES` in the `required` field may not be missing.

Conditional rows require an explicit applicability decision in release evidence.

## 8. Excluded content

Do not include:
- application caches;
- autosaves;
- temp files;
- render scratch;
- `node_modules`;
- generated build caches;
- `.DS_Store`;
- `Thumbs.db`;
- editor swap/recovery files;
- WIP assets;
- rejected alternatives;
- duplicate authorities;
- unlinked test images;
- watermarked stock assets;
- placeholder geometry;
- placeholder textures;
- local absolute-path link files;
- secrets or credentials.

Git metadata is not required inside the archive.

## 9. Pre-compression validation

Run in this order:

### Step 1 — Freeze the release candidate
Create a release-candidate directory under `13_DELIVERY/RELEASE_CANDIDATES/`. Do not package a tree receiving uncontrolled writes.

### Step 2 — Validate manifest completeness
Check every `required_in_final_package: true` entry for:
- completion status;
- exact path;
- exact filename;
- existence;
- size;
- SHA-256.

### Step 3 — Validate naming
Check all filenames and paths against `FILE_NAMING_STANDARD.md`.

### Step 4 — Validate file signatures
Confirm actual file type, not extension only. JSON and CSV must parse.

### Step 5 — Validate dimensions/media properties
Use `EXPORT_MATRIX.csv` to check applicable dimensions, aspect ratio, frame rate, alpha, color space, audio properties and page size.

### Step 6 — Validate vectors
Open final SVG/PDF/EPS in compatible vector software. No authoritative logo raster embedding is allowed.

### Step 7 — Validate 3D
Reopen native scene and verify separated objects, pivots, bearings, connecting rod, states, materials, textures, cameras and lighting. Import GLB/GLTF, FBX and OBJ.

### Step 8 — Validate motion
Reopen editable motion source; verify independent layers, primary master, preview, frame rate, dimensions and alpha where required.

### Step 9 — Validate physical assets
Confirm one-color manufacturing variants, vector integrity and proof evidence where production approval is claimed.

### Step 10 — Generate release hashes
Calculate SHA-256 for every final file before compression and store the deterministic record under `12_QA/VALIDATION_EVIDENCE/`.

### Step 11 — Compare duplicates
Detect byte-identical duplicates and remove unjustified duplicate authorities.

## 10. Compression requirements

Archive format:
- ZIP;
- lossless;
- broadly compatible;
- no source conversion during compression.

Compression must not:
- transcode images/video;
- change line endings;
- rewrite source files;
- rename entries;
- flatten directories.

ZIP path separator:
`/`

All stored paths must be relative.

## 11. Post-compression verification

After creating `BIELLA_ENGINE_BRAND_MASTER_v001.zip`:

1. test the ZIP central directory;
2. confirm no CRC errors;
3. confirm expected root path;
4. extract into a new empty directory;
5. recalculate SHA-256 for every extracted file;
6. compare against the pre-compression hash record;
7. require `100%` hash match;
8. compare extracted paths against `FOLDER_STRUCTURE.txt`, `ASSET_MANIFEST.json` and `EXPORT_MATRIX.csv`;
9. reopen a focused sample from the extracted package: SVG, PDF, PNG alpha, JSON, CSV, native 3D source, one 3D interchange file, primary motion master and README.

## 12. Release evidence

Record:
- archive filename;
- archive byte size;
- archive SHA-256;
- package control revision;
- asset version;
- creation timestamp;
- file count;
- pre-compression hash-record identity;
- post-extraction verification result;
- QA report identity;
- release authority.

Store evidence under `12_QA/VALIDATION_EVIDENCE/` and reference it from `VERSION_LOG.md`.

## 13. Release failure conditions

Do not approve if:
- a required manifest item is absent;
- a required item remains `NOT_CREATED`;
- the vector master is missing;
- native editable 3D source is missing;
- required motion source is missing;
- a mandatory export row is missing;
- the archive cannot cleanly extract;
- any extracted hash differs;
- placeholders exist;
- external links are broken;
- alpha is fake/missing where required;
- names violate the naming standard;
- unapproved alternate logo geometry exists.

## 14. Approval state

The package may be labeled `APPROVED_PACKAGE` only after:
1. pre-compression QA passes;
2. archive creation succeeds;
3. clean extraction succeeds;
4. post-extraction hashes match;
5. functional readback succeeds;
6. release evidence is stored.

Compression alone is not completion.
