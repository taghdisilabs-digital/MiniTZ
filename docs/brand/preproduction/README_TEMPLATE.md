# Biella Engine Brand Package — README Template

> This file is a template. Before final release, replace every `{{TOKEN}}` with the verified release value and remove this notice.

## Biella Engine

**CONNECTING INTELLIGENCE TO EXECUTION**

Package version: `{{PACKAGE_VERSION}}`  
Release date: `{{RELEASE_DATE}}`  
Control revision: `{{CONTROL_REVISION}}`  
Archive: `{{ARCHIVE_FILENAME}}`

## 1. What this package is

This is the official Biella Engine brand production package.

It contains the approved brand identity, editable logo sources, production-ready 2D exports, separated 3D source, motion source, material definitions, loading / UI variants, physical-manufacturing assets, documentation and QA evidence required to reproduce the identity without redrawing it.

The identity is built around the mechanical meaning of **biella**: the connecting rod that transfers force between independent parts and turns isolated motion into coordinated output.

## 2. Brand authority

Use authority in this order:
1. founder-approved current direction;
2. `BRAND_MASTER_SPEC.md`;
3. `PRIMARY_REFERENCE.png`;
4. `02_LOGO/MASTER_LOGO_GEOMETRY.svg`;
5. construction, material, typography and motion specifications;
6. derived exports.

Once `MASTER_LOGO_GEOMETRY.svg` is approved, derived logo assets must be regenerated from that vector source rather than manually redrawn.

## 3. Quick start

### Dark digital background
Use the approved `_DARK` SVG or the required PNG size under `11_EXPORTS/`.

### Light background
Use the approved `_LIGHT` vector or raster derivative.

### Icon only
Use the `_SYMBOL` asset.

### Print
Start with `11_EXPORTS/PRINT/`. Prefer vector PDF, EPS or SVG.

### Engraving, embossing, signage or apparel
Start with `10_PHYSICAL/` and read `PHYSICAL_APPLICATION_LIST.md`.

### 3D
Use `04_3D/SOURCE/` for the authoritative editable scene and `04_3D/INTERCHANGE/` for GLB/GLTF/FBX/OBJ.

### Motion
Use `05_MOTION/SOURCE/` for editable source and `11_EXPORTS/MOTION/` for rendered masters and previews.

## 4. Package structure

```text
BIELLA_BRAND_PREPRODUCTION/
├── root control files
├── 01_REFERENCE/
├── 02_LOGO/
├── 03_BRAND_SYSTEM/
├── 04_3D/
├── 05_MOTION/
├── 06_RENDER/
├── 07_LOADING_SCREENS/
├── 08_UI/
├── 09_CORPORATE/
├── 10_PHYSICAL/
├── 11_EXPORTS/
├── 12_QA/
└── 13_DELIVERY/
```

See `FOLDER_STRUCTURE.txt` for the canonical tree.

## 5. Logo use

Do not:
- stretch;
- mirror;
- arbitrarily rotate;
- redraw;
- rebuild from screenshots;
- change the connecting-rod relationship;
- alter approved wordmark spelling or spacing;
- replace the identity with a generic AI/tech mark.

The static mark must remain recognizable without glow, texture or cinematic FX.

## 6. Color

Primary direction:
- Biella Violet;
- polished silver / warm white;
- deep navy / black;
- gunmetal / steel.

Technical cyan is secondary. Orange is industrial heat/spark support, not the main static brand accent.

Use `COLOR_TOKENS.json`, `MATERIAL_PALETTE.pdf` and `PBR_MATERIAL_SPEC.md`.

## 7. Typography

Read `TYPOGRAPHY_SPEC.md`.

The formal wordmark becomes authoritative vector artwork once locked. Do not reconstruct the approved wordmark from a live font when the vector exists.

## 8. 3D compatibility

Authoritative native DCC: `{{NATIVE_DCC}}`  
Authoritative native scene: `{{NATIVE_3D_FILENAME}}`

Interchange formats:
- GLB;
- GLTF;
- FBX;
- OBJ.

The native scene must retain separated production parts and working pivots.

## 9. Motion compatibility

Authoritative motion source: `{{MOTION_SOURCE_FILENAME}}`  
Primary motion master: `{{PRIMARY_MOTION_MASTER}}`  
Preview: `{{PRIMARY_MOTION_PREVIEW}}`

Primary target:
- 3840 × 2160;
- 60 fps;
- Rec.709 SDR;
- approximately 12 seconds.

## 10. Loading / UI use

Approved composition families:
- 16:9;
- 21:9;
- 9:16;
- 4:5;
- 1:1.

Do not crop one composition blindly into every format.

UI derivatives must not contain baked cinematic smoke, sparks or environmental effects unless the asset explicitly requires them.

## 11. Physical production

Use vector-first source.

Before production:
- read `PHYSICAL_APPLICATION_LIST.md`;
- verify the manufacturing derivative;
- obtain a process-specific proof;
- retain the vendor-ready derivative and proof with the production job.

A cinematic raster image is not a manufacturing master.

## 12. Source versus derivative

Authoritative source:
- master vector;
- native DCC source;
- native motion/compositing source;
- brand control documents.

Derived output:
- PNG/JPG;
- print derivatives;
- GLB/GLTF/FBX/OBJ;
- previews;
- rendered videos;
- loading-screen exports;
- manufacturing derivatives.

Never silently promote an edited derivative above its source.

## 13. File naming

Follow `FILE_NAMING_STANDARD.md`.

Approved working asset versions use `v001`, `v002`, `v003`, and so on.

## 14. Integrity

Release manifest: `ASSET_MANIFEST.json`  
Export specification: `11_EXPORTS/EXPORT_MATRIX.csv`  
QA control: `12_QA/QA_CHECKLIST.md`  
Final archive rules: `13_DELIVERY/FINAL_ZIP_SPEC.md`

Release hash record: `{{HASH_MANIFEST_FILENAME}}`

The archive is valid only after clean extraction and post-extraction hash verification.

## 15. Software compatibility

Vector:
- standards-compliant SVG/PDF/EPS workflows.

3D:
- authoritative native DCC: `{{NATIVE_DCC}}`;
- GLB/GLTF viewers and engines;
- FBX-compatible DCC/game engines;
- OBJ-compatible geometry tools.

Motion:
- `{{MOTION_EDITING_APPLICATIONS}}`;
- ProRes / DNxHR-capable professional workflows;
- H.264/H.265 previews.

Image:
- PNG/JPG/TIFF/EXR-capable professional tools.

## 16. Release verification

This package was verified using:
- manifest completeness;
- naming validation;
- file-open checks;
- vector validation;
- dimension validation;
- alpha validation;
- missing-texture validation;
- 3D source reopen;
- interchange import checks;
- motion playback;
- clean archive extraction;
- SHA-256 comparison.

QA report: `{{QA_REPORT_FILENAME}}`

## 17. Contact / authority

Brand owner: `{{BRAND_OWNER}}`  
Package release authority: `{{RELEASE_AUTHORITY}}`  
Website: `{{OFFICIAL_WEBSITE}}`

When a derived asset conflicts with current approved brand authority, use the approved authority and regenerate the affected derivative.
