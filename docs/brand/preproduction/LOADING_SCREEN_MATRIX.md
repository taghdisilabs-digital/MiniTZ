# Biella Engine — Loading Screen Matrix

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Purpose: define required Biella Engine loading/splash compositions across aspect ratios and presentation variants

## 1. Core rule

Every loading-screen composition must derive from the same Biella master identity.

Allowed adaptation:

- camera reframing;
- layout;
- typography position;
- loading/status UI position;
- background crop/environment;
- FX intensity.

Not allowed:

- alternate logo geometry;
- altered symbol proportions;
- different connecting-rod construction;
- aspect-ratio-specific redesign of the mark.

## 2. Required aspect ratios and master dimensions

| Ratio | Master dimensions | Primary use |
|---|---:|---|
| 16:9 | 3840×2160 | Standard desktop/game/video |
| 21:9 | 5120×2160 | Ultrawide |
| 9:16 | 2160×3840 | Vertical/mobile/social |
| 4:5 | 2160×2700 | Portrait/social/promo |
| 1:1 | 2160×2160 | Square/app/social |

The package may additionally provide 1920×1080 and other derivatives, but these masters define the required design-safe compositions.

## 3. Required variant families

For each aspect ratio, prepare or support these variants:

```text
CLEAN
CINEMATIC
MINIMAL
LOADING_BAR
STATUS
```

That produces a required design matrix of 25 compositions.

## 4. Matrix

| Ratio | Clean | Cinematic | Minimal | Loading bar | Status |
|---|---|---|---|---|---|
| 16:9 | required | required | required | required | required |
| 21:9 | required | required | required | required | required |
| 9:16 | required | required | required | required | required |
| 4:5 | required | required | required | required | required |
| 1:1 | required | required | required | required | required |

## 5. CLEAN variant

Purpose:
- premium general loading/splash use.

Requirements:

- logo/wordmark primary;
- dark premium field;
- little or no FX;
- no loading UI unless specifically combined;
- enterprise-quality finish;
- strong small-screen readability.

Recommended:
- symbol + wordmark;
- tagline optional based on available safe area.

## 6. CINEMATIC variant

Purpose:
- AAA/game/hero loading state.

May include:
- hero 3D material treatment;
- restrained purple emission;
- sparks;
- dust;
- subtle smoke;
- industrial environment.

Requirements:
- effects never obscure symbol;
- orange remains support-only;
- enough negative space for any loading/status overlay;
- final geometry remains readable with FX removed.

## 7. MINIMAL variant

Purpose:
- fast boot, compact system surface, clean corporate fallback.

Requirements:
- flat or lightly dimensional mark;
- no smoke/sparks;
- optional restrained violet accent;
- minimal background;
- high contrast;
- fast decoding/rendering.

Suitable for:
- application boot;
- installer;
- technical recovery;
- lightweight UI.

## 8. LOADING_BAR variant

Purpose:
- provide visible progress affordance without changing brand identity.

Required elements:

```text
logo or icon
loading bar track
loading fill
optional percentage
optional short loading label
```

Rules:

- loading bar is UI, not part of logo;
- bar may use violet as progress accent;
- heat orange is not the progress color;
- bar remains readable at all required ratios;
- progress 0–100% must not move the logo.

Recommended labels:

```text
LOADING
INITIALIZING
PREPARING
```

Do not hardcode runtime states that Biella does not actually expose.

## 9. STATUS variant

Purpose:
- pair Biella identity with bounded system/task status.

Required layout supports:

```text
primary status
secondary detail
optional progress indicator
optional short identifier
```

Examples of neutral presentational states:

```text
INITIALIZING
LOADING RESOURCES
PREPARING WORKSPACE
READY
```

Do not present a simulated/fictional backend state as real runtime telemetry in product implementation.

## 10. Safe-area rules

### 16:9
- protect center logo zone;
- reserve lower 10–18% for loading/status when used;
- keep critical text inside 5% edge inset minimum.

### 21:9
- do not stretch logo to fill width;
- use wider environment/negative space;
- keep logo around central safe region;
- loading/status can span wider but remains visually subordinate.

### 9:16
- stack symbol/wordmark vertically;
- keep logo above midline or centered according to composition;
- loading/status area generally lower third;
- avoid tiny tagline.

### 4:5
- prioritize symbol + wordmark;
- tagline optional;
- loading/status lower quarter.

### 1:1
- symbol may lead;
- wordmark below or beside only if readable;
- loading UI remains compact;
- avoid overcrowding.

## 11. Logo scale guidance

Do not set one fixed percentage for every ratio.

Use optical scale while preserving:

- clear space;
- recognizable rod/bearings;
- wordmark legibility;
- room for status UI.

For small derivatives, omit tagline before reducing logo below legible size.

## 12. Background system

Allowed:

- deep navy black;
- graphite/gunmetal;
- neutral studio;
- controlled industrial;
- transparent source where required.

Backgrounds may include subtle:
- gradients;
- material texture;
- atmosphere;
- engineering pattern.

Avoid:
- giant scenery competing with mark;
- arcade HUD;
- random code;
- generic AI graphics.

## 13. Motion behavior

Loading versions may be:

- static;
- subtle active-state loop;
- controlled energy pulse;
- restrained light sweep;
- small mechanical idle if mechanically valid.

Loop requirements:
- seamless;
- no geometry drift;
- no one-time destructive lock event in a repeating loop unless cycle is deliberately reset;
- low-distraction;
- stable text/UI.

## 14. Loading bar behavior

Recommended progress model:

```text
track = neutral dark
fill = Biella violet
complete state = violet or approved success semantic color where product UI requires
```

The visual spec does not define actual progress semantics. Application code must bind the bar only to real progress data or clearly label indeterminate mode.

## 15. Status typography

Use the current `TYPOGRAPHY_SPEC.md`.

Hierarchy:

```text
logo / wordmark
status primary
status detail
progress / metadata
```

Do not use glitch text.

## 16. Filename convention

Examples:

```text
BIELLA_ENGINE_LOADING_CLEAN_16X9_4K_v001.png
BIELLA_ENGINE_LOADING_CINEMATIC_21X9_v001.png
BIELLA_ENGINE_LOADING_MINIMAL_9X16_v001.png
BIELLA_ENGINE_LOADING_BAR_4X5_v001.png
BIELLA_ENGINE_LOADING_STATUS_1X1_v001.png
```

Motion example:

```text
BIELLA_ENGINE_LOADING_ACTIVE_16X9_4K_60FPS_v001.mp4
```

## 17. Required source/editability

The matrix is not complete from 25 flattened images alone.

Retain:
- editable composition source;
- linked master logo source;
- editable text;
- editable loading/status UI;
- background source;
- motion source where applicable.

## 18. Validation matrix

For every required composition verify:

- exact dimensions;
- correct aspect ratio;
- no stretched geometry;
- no logo crop;
- wordmark legible;
- tagline omitted if too small rather than rendered illegibly;
- loading/status region clear;
- violet identity preserved;
- FX not required for recognition;
- export opens correctly;
- source composition remains editable.

## 19. Completion report

Track final production in `EXPORT_MATRIX.csv` and `ASSET_MANIFEST.json`.

Recommended fields per composition:

```text
ratio
dimensions
variant
static_or_motion
source_path
export_path
sha256
status
```
