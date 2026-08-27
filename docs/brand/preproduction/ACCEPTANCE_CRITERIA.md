# Biella Engine — Acceptance Criteria

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Purpose: objective pass/fail definition for the final Biella Engine brand production package

A deliverable is not “finished” because it looks correct in one preview. It is finished only when the required source, structure, exports and verification below exist.

## 1. Global Pass Rule

**PASS** requires every mandatory criterion to pass.

Any missing mandatory source, placeholder, broken link, fake transparency, flattened-only deliverable, invalid vector, unverified export or incorrect dimension is a **FAIL**.

## 2. Brand Identity

PASS when:
- company name is exactly `Biella Engine`;
- approved tagline is exactly `CONNECTING INTELLIGENCE TO EXECUTION`;
- final symbol matches approved master geometry;
- all derived logo expressions come from one master geometry;
- no alternate unauthorized logo geometry exists in final production folders;
- core color / material treatment follows the Brand Master Spec;
- monochrome version remains recognizable;
- logo works without glow or background.

FAIL when:
- geometry is redrawn differently for different applications;
- wordmark spelling/tracking is inconsistent;
- symbol becomes a generic AI/tech mark;
- logo requires FX to remain recognizable.

## 3. Vector Master

PASS when:
- `MASTER_LOGO_GEOMETRY.svg` contains real vector paths;
- no raster image is embedded as the logo geometry;
- paths are closed and clean;
- no stray points or invisible placeholder objects remain;
- fills/strokes expand predictably;
- gradients, if used, are optional expressions rather than structural requirements;
- document opens without repair in at least two independent vector-capable applications;
- monochrome conversion is possible without reconstructing the logo.

FAIL when:
- SVG is only a wrapper around PNG/JPG;
- geometry depends on clipping a raster image;
- text is required to display the symbol;
- malformed SVG requires application-specific recovery.

## 4. Alpha / Transparency

PASS when:
- PNG assets marked `_ALPHA` contain true alpha;
- transparent pixels have no baked checkerboard or matte;
- edges are clean against black, white and mid-gray test backgrounds;
- no dark or bright fringe is visible at normal presentation scale.

FAIL when:
- transparency is simulated with a background color;
- checkerboard is baked into image pixels;
- premultiplication creates visible edge halos.

## 5. 3D Source

PASS when:
- native editable 3D source is included;
- upper body is a separate object;
- lower body is a separate object;
- connecting rod is a separate object;
- upper bearing / insert is independently addressable;
- lower bearing / insert is independently addressable;
- illuminated sections can be controlled independently;
- meaningful object names are used;
- transforms are intentional;
- scene opens without missing critical data.

FAIL when:
- final logo is one destructive merged mesh with no production reason;
- motion depends on hidden placeholder geometry;
- the only deliverable is GLB/FBX/OBJ with no native editable scene.

## 6. Pivots and Connectors

PASS when:
- upper joint pivot is positioned at the real upper bearing center;
- lower joint pivot is positioned at the real lower bearing center;
- connecting rod can rotate / articulate from correct endpoints;
- assembled state can be reached from exploded state through transforms;
- no object penetrations occur in the approved motion path;
- reset-to-assembled transform is deterministic.

FAIL when:
- objects rotate around arbitrary world origin;
- bearings visually drift during rotation;
- the lock sequence is faked only in compositing.

## 7. Materials and Textures

PASS when:
- material assignments are editable;
- required PBR maps are present or procedurally reproducible;
- no missing external texture references remain;
- color-space interpretation is documented;
- metal reads as metal without relying on a baked beauty texture;
- purple emission is independently controllable;
- texture resolution satisfies delivery spec.

FAIL when:
- materials break after file relocation;
- metal / roughness values are baked irreversibly into a flattened image;
- unsupported texture paths are left unresolved.

## 8. Motion Source

PASS when:
- source animation is editable;
- object motion, camera, text, glow and major FX remain separately controllable;
- animation can be rerendered at a different resolution without rebuilding the scene;
- master timeline is reproducible from source;
- final assembled frame matches approved geometry.

FAIL when:
- only final MP4 exists;
- logo pieces are baked into one video layer with no editable motion source.

## 9. Renders and Video

PASS when:
- master resolution and FPS match Technical Delivery Spec;
- no dropped or duplicated frames exist unless intentional;
- final frame is clean;
- render sequence has no missing frames;
- alpha deliverables contain valid alpha where specified;
- preview video opens and plays in at least two independent players;
- color appearance is consistent with documented output transform.

FAIL when:
- preview is the only master;
- render has missing frames, corruption or unintended black frames;
- alpha is missing from a file named `_ALPHA`.

## 10. File Naming

PASS when:
- filenames follow `FILE_NAMING_STANDARD.md`;
- version suffixes are consistent;
- no files named `final_final`, `new`, `test2`, `untitled`, `copy`, `temp` or equivalent exist in final package;
- master files are unambiguous.

## 11. Placeholders

Final package must contain:
- zero placeholder geometry;
- zero placeholder textures;
- zero placeholder text;
- zero TODO/TBD production files unless the file is explicitly a control document defining future work;
- zero watermarked stock assets;
- zero unresolved external references.

## 12. Export Validation

Every mandatory export must:
- exist;
- be non-zero bytes;
- match declared extension and actual file format;
- open in a compatible application;
- match required dimensions / page size;
- match expected color space where testable;
- match expected alpha behavior;
- be listed in `ASSET_MANIFEST.json` / `EXPORT_MATRIX.csv`.

## 13. Integrity

Before final packaging:
- calculate SHA-256 for every final file;
- record file size;
- detect duplicate bytes;
- verify no required file is missing;
- verify archive after creation;
- extract archive into a clean temporary directory;
- rerun structural checks on extracted copy.

## 14. ZIP Acceptance

PASS when:
- archive name matches `FINAL_ZIP_SPEC.md`;
- root structure matches approved folder structure;
- no parent-directory junk exists;
- no OS metadata folders are included unless required;
- no temp renders / caches / autosaves are included;
- archive opens cleanly;
- full extraction succeeds;
- extracted hashes match pre-compression hashes;
- required root README and manifest are present.

## 15. Cross-Application Checks

Minimum:
- SVG: two vector-capable applications;
- PDF: two PDF readers;
- PNG/JPG: two image viewers;
- GLB/GLTF: one independent viewer plus source DCC;
- FBX/OBJ: import validation;
- video: two players;
- native 3D source: source application reopen test.

## 16. Approval State

Only assets passing all mandatory criteria may be labeled:
- `APPROVED_MASTER`;
- `APPROVED_EXPORT`;
- `APPROVED_PACKAGE`.

A visually attractive but structurally incomplete asset must remain `CANDIDATE`.
