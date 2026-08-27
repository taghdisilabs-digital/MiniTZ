# Biella Engine — File Naming Standard

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27

## 1. Goals

File names must be deterministic, sortable, machine-readable, human-readable, and safe across Windows, Linux, macOS, Git, Google Drive, DCC tools, render systems, game engines, and packaging systems.

## 2. General syntax

Use uppercase ASCII tokens separated by underscores:

```text
<SUBJECT>_<STATE>_<VARIANT>_<SIZE_OR_FORMAT>_<DELIVERY>_v###.<ext>
```

Not every field is required. Omit empty fields; never create double underscores.

Examples:

```text
BIELLA_ENGINE_SYMBOL_MASTER_v001.svg
BIELLA_ENGINE_SYMBOL_ACTIVE_4K_ALPHA_v003.png
BIELLA_ENGINE_WORDMARK_HORIZONTAL_DARK_WEB_v002.svg
BIELLA_ENGINE_LOGO_STACKED_LIGHT_PRINT_v001.pdf
BIELLA_ENGINE_INTRO_MASTER_4K_24FPS_v005.blend
BIELLA_ENGINE_INTRO_PREVIEW_4K_24FPS_v005.mp4
```

## 3. Canonical fixed filenames

The control-package filenames specified by the founder remain exactly:

```text
BRAND_MASTER_SPEC.md
ASSET_MANIFEST.json
INTRO_SCENE_BRIEF.md
ACCEPTANCE_CRITERIA.md
TECHNICAL_DELIVERY_SPEC.md
LOCKED_VS_FLEXIBLE.md
FILE_NAMING_STANDARD.md
FOLDER_STRUCTURE.txt
VERSION_LOG.md
PRIMARY_REFERENCE.png
REFERENCE_NOTES.md
MASTER_LOGO_GEOMETRY.svg
LOGO_CONSTRUCTION_SHEET.pdf
LOGO_COMPONENT_MAP.pdf
EXPLODED_STATE_REFERENCE.png
ASSEMBLED_STATE_REFERENCE.png
ACTIVE_STATE_REFERENCE.png
MATERIAL_PALETTE.pdf
COLOR_TOKENS.json
TYPOGRAPHY_SPEC.md
PBR_MATERIAL_SPEC.md
PIVOT_CONNECTOR_SPEC.md
CAMERA_SHOT_LIST.md
LIGHTING_PRESETS.md
FX_REQUIREMENTS.md
MOTION_LAYER_SPEC.md
RENDER_PASS_SPEC.md
LOADING_SCREEN_MATRIX.md
UI_ASSET_LIST.md
CORPORATE_ASSET_LIST.md
PHYSICAL_APPLICATION_LIST.md
EXPORT_MATRIX.csv
QA_CHECKLIST.md
README_TEMPLATE.md
FINAL_ZIP_SPEC.md
```

Do not add version suffixes to these canonical control filenames. Their revision history is tracked by Git and `VERSION_LOG.md`.

## 4. Required suffix vocabulary

Use these suffixes with the following meanings.

| Suffix | Meaning |
|---|---|
| `_MASTER` | authoritative editable/master asset |
| `_DARK` | variant for dark backgrounds |
| `_LIGHT` | variant for light backgrounds |
| `_4K` | 3840×2160 deliverable or 4K-class asset as explicitly specified |
| `_ALPHA` | export contains meaningful alpha transparency |
| `_PRINT` | print-production derivative |
| `_WEB` | web-optimized derivative |
| `_MOTION` | motion/animation source or derivative |

Additional controlled suffixes:

```text
_SYMBOL
_WORDMARK
_LOGO
_STACKED
_HORIZONTAL
_VERTICAL
_MONO
_ACTIVE
_OFF
_EXPLODED
_ASSEMBLED
_PREVIEW
_SOURCE
_EDITABLE
_GLTF
_GLB
_FBX
_OBJ
_PNG
_JPG
_SVG
_PDF
```

Do not invent synonymous suffixes when an approved token exists.

## 5. Versioning

Derived and working assets use:

```text
v001
v002
v003
...
```

Rules:

- three digits;
- increment for every approved content change;
- never overwrite an earlier approved derivative under the same version;
- experimental files may use `_WIP_v###`, but WIP files never enter final delivery;
- `FINAL`, `FINAL2`, `LATEST`, `NEW`, `NEWEST`, `USE_THIS`, dates-only, or person-name-based versioning is prohibited.

Canonical control filenames remain stable; their changes are recorded in `VERSION_LOG.md` and Git history.

## 6. Resolution and aspect tokens

Use explicit tokens:

```text
_4K
_1080P
_2160P
_8K
_16X9
_21X9
_9X16
_4X5
_1X1
```

When ambiguity matters, include actual dimensions in metadata/manifest even when the filename uses a shorthand token.

## 7. Frame-rate tokens

Use:

```text
_24FPS
_25FPS
_30FPS
_48FPS
_60FPS
```

Do not omit frame rate from motion deliverables whose timing or validation depends on it.

## 8. Color / delivery tokens

Use only when needed:

```text
_SRGB
_REC709
_LINEAR
_ACESCG
_CMYK
_RGB
```

The technical delivery specification controls which are valid for a given export.

## 9. Texture-map naming

Format:

```text
BIELLA_ENGINE_<PART>_<MAP>_<RESOLUTION>_v###.<ext>
```

Map tokens:

```text
_BASECOLOR
_METALLIC
_ROUGHNESS
_NORMAL
_HEIGHT
_DISPLACEMENT
_EMISSION
_AO
_OPACITY
```

Example:

```text
BIELLA_ENGINE_CONNECTING_ROD_ROUGHNESS_4K_v002.png
```

## 10. Render-pass naming

Format:

```text
BIELLA_ENGINE_<SHOT>_<PASS>_<FRAME>_v###.<ext>
```

Pass tokens:

```text
_BEAUTY
_DIFFUSE
_SPECULAR
_REFLECTION
_EMISSION
_SHADOW
_AO
_DEPTH
_NORMAL
_MOTIONVECTORS
_CRYPTOMATTE
```

Frames are zero-padded:

```text
000001
000002
...
```

## 11. Prohibited characters and patterns

Do not use:

- spaces;
- tabs;
- slashes/backslashes inside filenames;
- `: * ? " < > |`;
- emoji;
- non-normalized Unicode look-alikes;
- leading/trailing dots;
- repeated separators;
- unbounded descriptive prose in filenames.

## 12. Case and extension rules

- Canonical asset stems: uppercase.
- Extensions: lowercase.
- Folder names: uppercase with numeric prefixes where ordering matters.
- Git and Drive names must match exactly, including case.

## 13. Duplicate rule

A file with the same semantic identity and version must not exist twice under different names.

When two files are byte-identical:

- keep one canonical asset;
- reference it from the manifest;
- do not create duplicate authorities.

When two files share a human-readable name but differ in bytes:

- keep versions distinct;
- record content identity/digest in `ASSET_MANIFEST.json`.

## 14. Delivery validation

Before packaging:

- every file must conform to this naming standard;
- every expected file must be present in `ASSET_MANIFEST.json`;
- no WIP, temporary, autosave, cache, or duplicate-authority files may be present;
- filenames in the ZIP must match manifest names byte-for-byte.
