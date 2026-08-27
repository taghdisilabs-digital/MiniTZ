# Biella Engine — Camera Shot List

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Primary master: 3840×2160, 16:9, 60 fps, 12-second intro

## 1. Camera language

The camera system must communicate:

- premium industrial product-film quality;
- physical scale and mass;
- precision engineering;
- mechanical connection;
- restrained cinematic confidence.

Preferred behavior:
- deliberate motion;
- stable axes;
- macro mechanical detail;
- controlled low-angle authority;
- shallow depth of field during assembly;
- stronger readability at final reveal.

Avoid:
- random orbiting;
- excessive handheld shake;
- fisheye distortion;
- generic motion-template pushes;
- impossible camera clipping through geometry.

## 2. Lens convention

Lens values below are starting production targets on a full-frame-equivalent basis. Equivalent fields of view may be used in another camera model.

```text
macro/detail: 85–120 mm
hero 3/4:     50–70 mm
front hero:   65–85 mm
side:         70–100 mm
low angle:    40–60 mm
top:          50–85 mm
```

Do not use extreme wide-angle distortion on the final logo.

## 3. Required shot set

### CAM_01_FRONT_HERO

Purpose:
- authoritative geometry/readability view.

Target:
- near-orthographic feel without becoming flat;
- symbol centered;
- upper/lower relationship immediately readable;
- wordmark safe area preserved;
- neutral reference for geometry/lighting checks.

Suggested:
- 70–85 mm;
- minimal perspective distortion;
- no roll.

Deliverables:
- dormant/off;
- active;
- clean studio;
- transparent/background-isolated render where required.

### CAM_02_THREE_QUARTER_HERO

Purpose:
- primary premium 3D presentation.

Target:
- reveal depth of upper/lower bodies, rod and bearings;
- strong material response;
- rod remains readable as central bridge.

Suggested:
- 50–70 mm;
- horizontal angle ~25–40° from front;
- vertical angle restrained, typically 5–15°.

This is the preferred cinematic final reveal unless founder-approved direction selects front hero.

### CAM_03_MACRO_UPPER_BEARING

Purpose:
- show upper connection precision.

Suggested:
- 90–120 mm macro-equivalent;
- shallow depth of field;
- focus on bearing seat, bevels and rod eye;
- show physically plausible material/FX contact.

Use during alignment/lock or as a secondary still.

### CAM_04_MACRO_LOWER_BEARING

Purpose:
- show lower connection precision and load transfer.

Same optical discipline as CAM_03.

### CAM_05_CONNECTING_ROD

Purpose:
- make the “Biella” semantic center explicit.

Target:
- connecting rod occupies the visual hierarchy;
- both endpoints or their implied relationship remain understandable;
- brushed/forged steel reads clearly;
- purple energy path may be shown during activation without obscuring metal.

Suggested:
- 70–100 mm.

### CAM_06_SIDE_PROFILE

Purpose:
- inspect thickness, part separation and pivot integrity.

Target:
- side silhouette readable;
- exposes any mesh collision or fake assembly;
- useful for QA and technical presentation.

Suggested:
- 70–100 mm;
- little/no roll.

### CAM_07_LOW_ANGLE_POWER

Purpose:
- premium high-torque hero attitude.

Target:
- visually heavier lower body;
- upper body retains clarity;
- no exaggerated esports/aggressive distortion.

Suggested:
- 40–60 mm;
- modest low angle.

Use sparingly; not the geometry authority view.

### CAM_08_TOP_TECHNICAL

Purpose:
- verify planar alignment and mechanical relationship.

Target:
- technical clarity;
- useful for construction/QA supporting renders;
- may use a flatter lighting preset.

Suggested:
- 50–85 mm.

### CAM_09_FINAL_REVEAL

Purpose:
- final cinematic lockup from 9.00–12.00 seconds.

Sequence:
- resolve from prior assembly camera motion;
- settle to front or 3/4 hero;
- allow particles to decay;
- preserve readable symbol;
- wordmark at 10.25–11.25;
- tagline at 11.25–12.00.

Suggested:
- 55–75 mm;
- final motion eases to a stable hold;
- no camera shake after wordmark begins.

## 4. Intro timeline camera requirements

### 0.00–1.50 — Separate parts

- establish dark industrial space;
- use a macro or 3/4 composition;
- do not reveal the final full silhouette too early.

### 1.50–3.25 — Movement

- camera may truck/dolly with heavy part motion;
- keep movement subordinate to mechanical action.

### 3.25–5.00 — Alignment

- tighten framing toward joints/rod;
- precision becomes more important than spectacle.

### 5.00–6.25 — Mechanical lock

- camera should provide a clear contact event;
- use macro insert or controlled hero angle;
- no cut that hides an impossible connection.

### 6.25–7.75 — Energy fusion

- maintain visibility of the actual connection points;
- allow sparks/energy to read in depth.

### 7.75–9.00 — Activation

- transition toward full-symbol readability.

### 9.00–10.25 — Reveal

- settle final hero camera.

### 10.25–12.00 — Wordmark/tagline

- camera movement becomes minimal or static;
- typography legibility has priority.

## 5. Depth of field

Assembly:
- shallow-to-moderate DOF allowed;
- always keep the active mechanical event readable.

Final:
- enough depth for full symbol and wordmark clarity;
- avoid focus breathing that distracts during tagline.

## 6. Aspect-ratio adaptation

Required safe compositions:

```text
16:9
21:9
9:16
4:5
1:1
```

Rules:

- geometry does not change;
- camera may reframe/recompose;
- wordmark/tagline may move according to layout;
- do not crop critical bearings/rod in hero state;
- vertical formats should prioritize symbol first, typography second.

## 7. Camera naming

Use:

```text
CAM_FRONT_HERO
CAM_THREE_QUARTER_HERO
CAM_MACRO_UPPER_BEARING
CAM_MACRO_LOWER_BEARING
CAM_CONNECTING_ROD
CAM_SIDE_PROFILE
CAM_LOW_ANGLE_POWER
CAM_TOP_TECHNICAL
CAM_FINAL_REVEAL
```

## 8. Validation

PASS when:

- every required camera exists in editable source;
- names are stable;
- no camera intersects geometry on approved motion path;
- final reveal is readable without FX;
- macro shots preserve focus on mechanical detail;
- front hero provides a clean geometry-check view;
- 3/4 hero shows depth without silhouette drift;
- vertical/wide adaptations reframe rather than redesign;
- the camera list can be reproduced after clean source reopen.
