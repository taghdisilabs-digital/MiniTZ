# Biella Engine — Motion Layer Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Purpose: define the editable layer structure required for Biella Engine motion, compositing and derivative production

## 1. Core rule

The Biella motion package must remain editable.

The final intro, loading sequence, active-state loop and derived motion assets may be rendered flat for delivery, but the authoritative production source must preserve independent control of geometry, typography, lighting-dependent elements, FX, backgrounds, masks and finishing layers.

A flattened video is never the motion source.

## 2. Required independently controllable layer families

At minimum preserve separate control for:

```text
logo upper body
logo lower body
connecting rod
upper bearing
lower bearing
separate inserts / illuminated sections where present
BIELLA wordmark
ENGINE wordmark
tagline
base material render
emission / glow
shadows
sparks
purple particles
smoke
dust
electrical arcs
fusion glow
heat distortion
shock response
light sweeps
energy pulse
background
foreground atmosphere
mattes
masks
depth effects
grading / finishing
```

Where the production tool uses 3D objects rather than compositing layers, the same independence requirement applies through objects, collections, render layers, passes, groups or equivalent native constructs.

## 3. Authoritative source hierarchy

Recommended hierarchy:

```text
MOTION_MASTER
|
|-- LOGO
|   |-- LOGO_UPPER_BODY
|   |-- LOGO_LOWER_BODY
|   |-- CONNECTING_ROD
|   |-- UPPER_BEARING
|   |-- LOWER_BEARING
|   |-- INSERTS
|   `-- EMISSIVE_SECTIONS
|
|-- TYPE
|   |-- WORDMARK_BIELLA
|   |-- WORDMARK_ENGINE
|   `-- TAGLINE
|
|-- FX
|   |-- SPARKS
|   |-- SMOKE
|   |-- DUST
|   |-- PURPLE_PARTICLES
|   |-- ELECTRICAL_ARCS
|   |-- FUSION_GLOW
|   |-- HEAT_DISTORTION
|   |-- LOCK_SHOCK
|   |-- LIGHT_SWEEPS
|   `-- ENERGY_PULSE
|
|-- LIGHT_AND_SHADOW
|   |-- BASE_LIGHTING
|   |-- EMISSION_ENHANCEMENT
|   `-- SHADOW_CONTROL
|
|-- BACKGROUND
|   |-- ENVIRONMENT
|   |-- BACKPLATE
|   `-- ATMOSPHERE
|
|-- MATTES_AND_MASKS
|-- COLOR_AND_FINISHING
`-- OUTPUT_CONTROLS
```

Equivalent native grouping is allowed. Semantic separation is mandatory.

## 4. Motion source requirements

At least one authoritative editable source is required:

- native 3D scene containing object animation;
- plus compositing/editing source when meaningful post-production layers exist.

Examples of acceptable source applications include Blender, After Effects, Resolve/Fusion or other professional tools. Tool choice is flexible.

The source must retain:

- animation curves/keyframes;
- object hierarchy;
- pivots/connectors;
- camera animation;
- light animation;
- emission controls;
- FX parameters;
- masks/mattes;
- typography timing;
- final color/finishing controls where practical.

## 5. Timeline authority

Primary intro timing follows `INTRO_SCENE_BRIEF.md`:

```text
0.00–1.50   separate parts
1.50–3.25   movement
3.25–5.00   alignment
5.00–6.25   mechanical lock
6.25–7.75   sparks / energy fusion
7.75–9.00   activation
9.00–10.25  camera reveal
10.25–11.25 wordmark
11.25–12.00 tagline
```

These events may be represented by markers in the master timeline.

Recommended marker names:

```text
EVENT_SEPARATE_START
EVENT_MOVEMENT_START
EVENT_ALIGNMENT_START
EVENT_LOCK
EVENT_FUSION_START
EVENT_ACTIVATION_START
EVENT_REVEAL_START
EVENT_WORDMARK
EVENT_TAGLINE
EVENT_END
```

## 6. Object motion separation

The following may not be baked into one inseparable layer in the authoritative source:

- upper body;
- lower body;
- connecting rod;
- bearings;
- wordmark;
- camera.

The mechanical lock must remain reproducible from actual object transforms/constraints and valid pivots.

Do not replace mechanical assembly with a dissolve or 2D-only reveal.

## 7. Typography separation

Keep independently controllable:

```text
WORDMARK_BIELLA
WORDMARK_ENGINE
TAGLINE
```

Requirements:

- timing can be changed without rerendering logo geometry when the pipeline allows;
- tracking/opacity/position remain editable;
- no destructive rasterization in the only authoritative source;
- FX do not become part of wordmark geometry.

## 8. Glow and emission separation

Distinguish:

```text
physical/material emission
rendered emission pass
compositing bloom/glow enhancement
```

They are not interchangeable.

Requirements:

- material emission can be disabled at source;
- compositing glow can be independently disabled;
- clean/off deliverable can be produced without rebuilding the scene;
- glow must not permanently alter alpha or logo silhouette.

## 9. Shadow separation

Where the renderer/pipeline supports it, retain:

- shadow pass or shadow-catching layer;
- contact shadow control;
- environment shadow control.

A clean transparent logo export must be possible without a baked opaque background.

## 10. FX separation

Follow `FX_REQUIREMENTS.md`.

Each major FX family must have independent on/off/intensity control.

Do not merge sparks, smoke, purple particles and glow into one irreversible precomp/render unless the source of those elements remains retained separately.

## 11. Background separation

Background/environment is never part of logo geometry.

Keep independent:

- dark premium environment;
- studio/corporate background;
- loading-screen background;
- transparent/alpha mode where required.

The same animated logo must be reusable across different backgrounds.

## 12. Mattes and masks

Retain meaningful masks/mattes separately:

- logo/object mattes;
- emission masks;
- text mattes;
- FX holdouts;
- depth/occlusion masks;
- transition masks.

Cryptomatte/object-ID outputs may satisfy some compositing selection requirements when supported.

Do not rely on destructive hand-painted masking if an object/pass identity can provide the same control more reliably.

## 13. Motion blur

Motion blur must be:

- physically coherent;
- renderer/source controlled where possible;
- separately reducible/disabled for technical inspection;
- not a destructive bake into the only geometry/motion source.

## 14. Color and grading layers

Keep finishing distinct from source color/material authority.

Recommended:

```text
BASE_SCENE_TRANSFORM
LOOK_ADJUSTMENT
CONTRAST
VIOLET_BALANCE
HIGHLIGHT_CONTROL
GRAIN_OPTIONAL
OUTPUT_TRANSFORM
```

Do not use grading to repair incorrect material colors that should be fixed at source.

## 15. Derived motion variants

The master source must support:

- 12-second cinematic intro;
- 8-second ident;
- 5-second splash;
- 3-second quick boot;
- active-state loop;
- loading loop;
- clean corporate motion;
- alpha logo motion where required.

Cutdowns may retime or omit events but must preserve final master geometry.

## 16. Aspect ratios

Required design-safe compositions:

```text
16:9
21:9
9:16
4:5
1:1
```

Adapt by:

- camera reframing;
- typography layout;
- background composition;
- FX safe area.

Do not alter logo geometry per aspect ratio.

## 17. Naming

Use clear layer/group prefixes:

```text
GEO_
TYPE_
FX_
LIGHT_
SHADOW_
BG_
MATTE_
MASK_
GRADE_
OUT_
```

Examples:

```text
GEO_CONNECTING_ROD
TYPE_TAGLINE
FX_SPARKS_LOCK
MATTE_LOGO
BG_DARK_STUDIO
OUT_16X9_4K
```

## 18. Interchange / handoff

When handing motion between tools:

- preserve source application file;
- consolidate/relink used assets;
- document frame rate;
- document color management;
- document alpha convention;
- document any baked simulation/cache dependencies;
- preserve the source version used for the handoff.

Baked interchange is allowed as a delivery mechanism but cannot replace the editable master.

## 19. Validation

PASS when:

1. required logo parts remain independently controllable;
2. wordmark and tagline remain independently controllable;
3. camera can be adjusted independently;
4. glow/emission can be disabled independently;
5. shadow/background can be disabled or replaced independently;
6. major FX families can be independently disabled;
7. masks/mattes remain accessible;
8. 16:9, 21:9, 9:16, 4:5 and 1:1 can derive from one identity;
9. source can be reopened without broken dependencies;
10. clean/corporate and cinematic variants can be produced from the same authoritative source;
11. a flattened preview is not the only surviving motion representation.
