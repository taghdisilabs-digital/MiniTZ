# Biella Engine — Render Pass Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Purpose: define required beauty and technical render passes for production, compositing, QA and derivative delivery

## 1. Core rule

The render pipeline must preserve enough image data to:

- reproduce the approved beauty result;
- adjust major lighting/material/FX contributions without rerendering unrelated work when practical;
- isolate objects and emissions;
- validate motion and geometry;
- perform high-quality compositing.

The beauty render is a delivery result, not the only technical evidence.

## 2. Master format

Preferred pass master:

```text
OpenEXR
```

Requirements:

- scene-linear data;
- half-float minimum for standard passes unless a pass requires full float;
- lossless or approved production-grade EXR compression;
- consistent frame numbering;
- explicit channel naming;
- no display-referred clipping in scene-linear technical passes.

Multilayer EXR is allowed where the pipeline and downstream software support it reliably.

Separate EXR files are also allowed.

## 3. Required pass set

Final hero/cinematic production must be capable of producing:

```text
BEAUTY
DIFFUSE
SPECULAR
REFLECTION
EMISSION
SHADOW
AO
DEPTH
NORMAL
MOTION_VECTORS
OBJECT_ID / CRYPTOMATTE
```

If the actual renderer exposes semantically different components, map them explicitly rather than pretending names match.

## 4. Beauty

### `BEAUTY`

Purpose:
- canonical combined render before or after approved compositor integration, as documented.

Requirements:
- correct geometry;
- approved materials;
- approved lighting;
- motion blur according to shot;
- no unintended missing pass contribution;
- scene-linear master retained before final display transform where pipeline supports it.

The delivered PNG/JPG/video is derived from the beauty/composite master.

## 5. Diffuse

### `DIFFUSE`

Purpose:
- isolate diffuse/base-light contribution.

Where the renderer separates direct/indirect diffuse, preserve both or document the recombination.

Do not use the diffuse pass as a replacement for Base Color texture/source.

## 6. Specular

### `SPECULAR`

Purpose:
- isolate specular response from machined/polished materials.

Useful for:
- highlight control;
- bearing polish adjustment;
- metal readability.

Where direct/indirect specular are separate, preserve them when practical.

## 7. Reflection

### `REFLECTION`

Purpose:
- isolate environment/reflection contribution where the renderer provides it distinctly.

Do not double-add a reflection pass if the renderer's beauty/specular model already includes it and the pipeline cannot correctly recombine it. Record renderer semantics.

## 8. Emission

### `EMISSION`

Purpose:
- isolate violet activation/emissive contribution.

Requirements:
- no bloom baked into the raw emission pass unless explicitly documented;
- purple activation remains adjustable;
- heat/spark emission may be separated further where practical.

Recommended subpasses when complexity justifies:

```text
EMISSION_VIOLET
EMISSION_HEAT
EMISSION_SPARKS
```

## 9. Shadow

### `SHADOW`

Purpose:
- retain contact/environment shadow control.

Requirements:
- appropriate for shadow catchers or composite control;
- alpha/matte behavior documented;
- no loss of clean transparent-logo delivery.

## 10. Ambient occlusion

### `AO`

Purpose:
- technical/contact-depth support.

Rules:
- AO is not baked into authoritative Base Color.
- AO may be used subtly in compositing or real-time derivatives.
- Excessive AO that makes premium metal look dirty is prohibited.

## 11. Depth

### `DEPTH`

Purpose:
- depth-of-field adjustment;
- atmosphere;
- compositing isolation;
- QA.

Requirements:
- scene-linear numeric depth;
- near/far interpretation documented;
- no display gamma;
- unclamped range when practical.

Preferred:
- EXR float channel.

## 12. Normal

### `NORMAL`

Purpose:
- geometry/lighting QA and controlled relighting support.

Document:
- world-space or camera-space;
- channel orientation;
- normalization convention.

Do not deliver a color-managed display transform on raw normal vectors.

## 13. Motion vectors

### `MOTION_VECTORS`

Purpose:
- motion blur support;
- temporal compositing;
- QA.

Document:
- pixel-space or normalized-space convention;
- forward/backward direction;
- scale.

Motion-vector pass must correspond to the actual rendered frame timing/shutter convention.

## 14. Object ID / Cryptomatte

Preferred:
```text
CRYPTOMATTE
```

Minimum selectable object families:

- upper body;
- lower body;
- connecting rod;
- upper bearing;
- lower bearing;
- inserts/emissive sections;
- wordmark;
- tagline where rendered in 3D;
- major FX groups where useful.

Fallback:
- deterministic object/material ID pass if Cryptomatte is unavailable.

IDs must be stable across the same shot/version.

## 15. Optional useful passes

Where supported and justified:

```text
TRANSMISSION
REFRACTION
VOLUME
VOLUME_EMISSION
POSITION
UV
MATERIAL_ID
LIGHT_GROUPS
MIST
WIRE / GEOMETRY_QA
```

Optional passes must not become mandatory merely because one renderer provides them.

## 16. Light groups

For hero/cinematic work, preserve light-group separation when practical:

```text
KEY
FILL
RIM
VIOLET_ACTIVATION
HEAT_SUPPORT
BACKGROUND
```

This enables controlled adjustment without changing source lighting identity.

## 17. FX pass separation

Recommended independent output where the effect matters:

```text
FX_SPARKS
FX_SMOKE
FX_DUST
FX_PURPLE_PARTICLES
FX_ARCS
FX_GLOW_SOURCE
```

This can be achieved by render layers, collections, holdouts, AOVs, mattes or equivalent production technique.

## 18. Alpha

Where alpha is required:

- retain valid alpha in beauty/FX outputs as applicable;
- straight/unassociated alpha is preferred unless the pipeline requires premultiplied;
- document premultiplication;
- no baked checkerboard/matte;
- edges must composite cleanly over black, white and mid-gray.

## 19. Color management

Working:
- scene-linear;
- ACEScg preferred for high-end rendering/compositing.

Passes:
- technical data passes remain data, not display-transformed color.
- beauty/color passes use the documented scene-linear transform pipeline.

Delivery:
- sRGB still/UI;
- Rec.709 Gamma 2.4 SDR motion unless later approved delivery overrides.

## 20. Frame naming

Follow `FILE_NAMING_STANDARD.md`.

Pattern:

```text
BIELLA_ENGINE_<SHOT>_<PASS>_<FRAME>_v###.exr
```

Example:

```text
BIELLA_ENGINE_FINAL_REVEAL_BEAUTY_000240_v003.exr
BIELLA_ENGINE_FINAL_REVEAL_EMISSION_000240_v003.exr
```

Frame numbers are zero-padded.

## 21. Directory layout

Recommended:

```text
06_RENDER/
|-- BEAUTY/
|-- PASSES/
|   |-- DIFFUSE/
|   |-- SPECULAR/
|   |-- REFLECTION/
|   |-- EMISSION/
|   |-- SHADOW/
|   |-- AO/
|   |-- DEPTH/
|   |-- NORMAL/
|   |-- MOTION_VECTORS/
|   `-- CRYPTOMATTE/
`-- PREVIEWS/
```

## 22. Recombination rule

If a renderer/pipeline claims the component passes can reconstruct beauty:

- test an actual frame;
- compare recombined result with native beauty;
- record known differences.

Do not claim mathematically exact recombination when the renderer's integrator/AOV semantics do not support it.

## 23. Validation

PASS when:

1. required passes exist for the approved final production where supported by the chosen renderer;
2. EXR files open successfully;
3. technical passes have correct data interpretation;
4. emission isolates violet activation;
5. depth is usable;
6. normals have documented convention;
7. motion vectors correspond to motion;
8. object ID/Cryptomatte can isolate required logo components;
9. beauty remains visually correct;
10. alpha composites cleanly where specified;
11. frame sequences contain no missing required frames;
12. pass names and frame numbers follow naming standard;
13. source project can reproduce the pass configuration.
