# Biella Engine — Technical Delivery Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Purpose: define required production formats, technical masters, interchange files and output standards

## 1. Delivery Philosophy

The package must preserve:
1. authoritative editable source;
2. clean interchange;
3. production-quality masters;
4. lightweight usage derivatives.

A preview is never a substitute for source.

## 2. 2D Logo Masters

Mandatory:
- `SVG` — authoritative vector geometry;
- `PDF` — print/vector delivery;
- `EPS` — legacy professional print/interchange;
- `PNG` — transparent raster exports;
- `JPG` — flattened preview/application exports where transparency is not needed.

### SVG
- scalable;
- real paths;
- no raster logo embedding;
- no external linked assets;
- UTF-8;
- viewBox required;
- monochrome-compatible.

### PDF
- vector-preserving;
- fonts embedded or converted as required by final typography decision;
- no unintended rasterization of logo paths;
- construction sheets use ISO A-series page sizes unless a specific presentation sheet requires another format.

### EPS
- vector artwork only for logo geometry;
- effects that cannot survive EPS must be omitted rather than flattened into the master logo.

### PNG
Required master sizes for symbol / lockup exports:
- 8192 px long edge — archival / large compositing;
- 4096 px long edge — 4K / presentation;
- 2048 px long edge — standard high-resolution;
- 1024 px;
- 512 px;
- 256 px;
- 128 px;
- 64 px;
- 32 px.

Transparent variants:
- 8-bit RGBA minimum;
- true alpha;
- sRGB output.

### JPG
- sRGB;
- quality 92 or higher;
- no JPG used as authoritative logo source.

## 3. 3D Source

Mandatory:
- original native DCC scene;
- `GLB` and/or `GLTF`;
- `FBX`;
- `OBJ` for basic geometry compatibility.

The native source format is determined by the production DCC actually used. If Blender is used, `.blend` is mandatory. If another DCC is used, its native source file must also be included.

### 3D scene requirements
- physically meaningful scale;
- separated production objects;
- stable object names;
- correct pivots;
- no unapplied destructive transforms that break motion;
- clean assembled state;
- clean exploded state;
- camera and lighting collections separated from logo geometry;
- render/FX assets logically grouped.

## 4. Required 3D Object Separation

Minimum independently controllable objects:
- `LOGO_UPPER_BODY`;
- `LOGO_LOWER_BODY`;
- `CONNECTING_ROD`;
- `UPPER_BEARING`;
- `LOWER_BEARING`;
- purple/anodized inserts where separate;
- emissive sections where separate;
- wordmark geometry if used in 3D;
- optional fasteners / mechanical detail as separate logical groups.

## 5. PBR Texture Delivery

Where textures are used, support the following maps as applicable:
- Base Color / Albedo;
- Metallic;
- Roughness;
- Normal;
- Height / Displacement;
- Ambient Occlusion where separately required;
- Emission;
- optional masks / material IDs.

Master texture resolution:
- 4096 × 4096 minimum for hero close-up materials where UV-based textures are required;
- 8192 × 8192 permitted for macro hero assets when justified;
- 2048 / 1024 derivatives may be generated.

Preferred formats:
- `PNG` / `TIFF` for standard texture maps;
- `EXR` for HDR / high-dynamic-range / compositing data.

Color interpretation:
- Base Color: sRGB;
- Emission color: sRGB source, transformed by render pipeline;
- Metallic / Roughness / Normal / Height / AO / masks: linear / non-color data.

No baked lighting in Base Color.

## 6. Color Management

3D / compositing working space:
- scene-linear workflow;
- ACEScg preferred for high-end rendering and compositing.

Delivery transforms:
- sRGB for still web/UI outputs;
- Rec.709 Gamma 2.4 for standard SDR video master/preview unless a later HDR spec is approved;
- print CMYK conversion is a derived output, not the color master.

The approved reference appearance must be reproduced under the documented output transform.

## 7. Still Render Masters

Primary still:
- 7680 × 4320 — 8K archival hero;
- 3840 × 2160 — 4K delivery;
- 2560 × 1440 — QHD;
- 1920 × 1080 — HD.

Additional aspect-ratio masters:
- 21:9 — 5120 × 2160;
- 9:16 — 2160 × 3840;
- 4:5 — 2160 × 2700;
- 1:1 — 2160 × 2160.

Still master formats:
- `EXR` for render/compositing master;
- `PNG` for lossless delivered still;
- `JPG` for preview only.

## 8. Motion Master

Primary cinematic master:
- 3840 × 2160;
- 16:9;
- 60 fps;
- progressive;
- 12-second target intro duration;
- Rec.709 SDR delivery;
- motion blur physically coherent.

Cinematic alternate:
- 24 fps derivative may be produced from a properly retimed / rerendered source; do not simply discard frames from the 60 fps master if it creates poor cadence.

### Master codecs
Preferred:
- ProRes 4444 / 4444 XQ for high-quality master and alpha-capable delivery;
- DNxHR 444 as compatible alternative;
- EXR image sequence for highest-fidelity compositing master.

### Preview codecs
- H.264 High Profile;
- H.265/HEVC where required;
- high-bitrate visually clean preview.

No delivery shall rely only on H.264/H.265.

## 9. Alpha Motion

Where transparent motion is required:
- ProRes 4444 with alpha or equivalent;
- and/or EXR sequence with alpha;
- straight/unassociated alpha preferred unless pipeline requires premultiplied;
- alpha convention must be documented.

## 10. Render Passes

Final 3D production must be capable of exporting:
- Beauty;
- Diffuse;
- Specular;
- Reflection;
- Emission;
- Shadow;
- Ambient Occlusion;
- Depth / Z;
- Normal;
- Motion Vector;
- Object ID / Cryptomatte where supported.

Exact pass list may be reduced for a particular render only if the final `RENDER_PASS_SPEC.md` explicitly permits it.

## 11. Motion Source

At least one authoritative editable motion source is mandatory:
- native 3D scene with animation;
- plus compositing/editing source when post-production adds meaningful layers.

If After Effects, Resolve/Fusion, Blender compositor or another application is used, the original project source must be retained with relinkable assets.

Separately controllable:
- logo objects;
- wordmark;
- tagline;
- glow/emission;
- shadows;
- sparks;
- particles;
- smoke/dust;
- background;
- mattes/masks;
- grading layers where practical.

## 12. Audio

If an audio ident is produced later:
- WAV;
- 48 kHz;
- 24-bit;
- stereo master minimum;
- stems retained when multiple designed layers are used.

Compressed audio is preview-only.

## 13. Aspect Ratios

Required design-safe compositions:
- 16:9;
- 21:9;
- 9:16;
- 4:5;
- 1:1.

All must derive from the same master identity. Crops may recompose camera and text; they must not alter logo geometry.

## 14. Print Delivery

Required:
- vector PDF;
- EPS;
- SVG;
- 300 ppi raster proof where rasterized proof is needed;
- CMYK print proof derived from approved color management;
- one-color black;
- one-color white;
- engraving-ready monochrome geometry.

No metallic gradient is required for manufacturing marks.

## 15. UI / Game Delivery

At minimum:
- transparent logo lockup;
- icon-only mark;
- monochrome mark;
- light-background variant;
- dark-background variant;
- 4K splash;
- loading-screen-safe composition;
- small icon derivatives.

UI exports must not include baked cinematic smoke/sparks unless specifically required.

## 16. File Integrity

All final files require:
- exact byte size;
- SHA-256 digest;
- extension/type validation;
- open/read test;
- required-dimension test;
- alpha test where applicable;
- cross-reference in `ASSET_MANIFEST.json`;
- cross-reference in `EXPORT_MATRIX.csv`.

## 17. Compression / Archive

Final ZIP:
- lossless;
- no conversion during compression;
- source directory must remain intact;
- archive must be test-extracted before approval;
- extracted file hashes must match pre-compression hashes.

## 18. Minimum Final Technical Set

A final approved brand package cannot be considered complete without:

1. clean vector master;
2. transparent raster exports;
3. monochrome exports;
4. print vector outputs;
5. native separated 3D source;
6. GLB/GLTF;
7. FBX;
8. OBJ;
9. PBR texture sources where used;
10. working pivots;
11. editable motion source;
12. 4K motion master;
13. compositing master / render sequence;
14. preview video;
15. construction/component documentation;
16. manifests, hashes and QA evidence.
