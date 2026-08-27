# Biella Engine — Lighting Presets

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27

## 1. Purpose

Define reproducible lighting states for dormant, activation, industrial, studio, corporate and cinematic presentation while preserving one consistent Biella material identity.

Lighting is an expression layer. It must never become part of authoritative logo geometry or Base Color.

## 2. Global lighting rules

Preserve:

- readable premium metal;
- rich blacks without crushed structural detail;
- dominant violet identity;
- restrained emission/bloom;
- controlled specular highlights;
- believable light direction;
- separation between upper body, lower body, rod and bearings.

Avoid:

- flat ambient wash;
- full-scene purple fog;
- orange/blue arcade lighting;
- excessive rim lights;
- clipped white speculars;
- permanent beauty-light information baked into textures.

## 3. Color-temperature guidance

These temperatures are production targets and may be adjusted to preserve the approved appearance under the actual renderer.

```text
neutral/corporate key: 5000–6500 K
cool industrial edge:  6500–9000 K
warm industrial heat:  2200–3500 K
```

Violet brand lighting should use the approved color role rather than color-temperature approximation.

## 4. PRESET_DARK_OFF

Purpose:
- dormant state;
- material credibility before activation.

Characteristics:
- very low environment;
- narrow cool key/reflection strip;
- subtle opposite rim for silhouette;
- violet spill absent or near-zero;
- emission disabled;
- background: `#050812` family.

Exposure:
- preserve metal shape and bearing edges;
- deep shadows remain above unrecoverable crush.

Use:
- first 0.00–3.25 seconds;
- off-state product stills.

## 5. PRESET_PURPLE_ACTIVATION

Purpose:
- visual identity transition during 6.25–9.00 seconds.

Characteristics:
- base metal lighting remains visible;
- localized violet practical/emission near bearings and conductive path;
- controlled violet bounce;
- cool neutral key prevents all surfaces becoming purple;
- optional fine volumetric haze only if it improves beam/particle readability.

Rules:
- purple activation must appear to originate from mechanism;
- bloom remains controlled;
- emission does not erase material.

## 6. PRESET_ORANGE_INDUSTRIAL

Purpose:
- support mechanical lock, sparks, heat and industrial energy.

Characteristics:
- warm local sources near contact event;
- orange `#F28A2E` restricted to heat/sparks/support;
- neutral/cool metal key remains dominant enough to protect brand colors;
- violet may coexist only after activation begins.

Prohibited:
- orange as logo base color;
- orange replacing violet identity;
- orange/blue esports palette.

## 7. PRESET_NEUTRAL_STUDIO

Purpose:
- material/geometry validation;
- construction documentation;
- catalog-style clean renders.

Suggested rig:
- large soft key;
- controlled fill;
- separate rim/top strip;
- neutral environment;
- no cinematic smoke or sparks;
- emission off unless specifically validating active-state material.

Requirements:
- upper purple, lower gunmetal, steel rod and bearings remain distinguishable;
- useful for comparing revisions.

## 8. PRESET_POLISHED_CORPORATE

Purpose:
- enterprise, investor, website, presentation and business uses.

Characteristics:
- dark premium background;
- polished but restrained highlight structure;
- violet identity visible;
- minimal FX;
- clean wordmark readability;
- no industrial dirt/smoke unless extremely subtle.

Desired feel:
- international technology/product company;
- credible outside gaming;
- high-end product launch rather than sci-fi poster.

## 9. PRESET_HERO_CINEMATIC

Purpose:
- final hero render and end-state intro reveal.

Suggested layering:
1. large controlled key defining primary volume;
2. cooler fill preserving dark surfaces;
3. precise rim/strip highlights along engineered bevels;
4. localized violet activation practical;
5. optional warm micro-support near lock history;
6. subtle background separation;
7. controlled atmosphere.

Final frame:
- symbol readable;
- materials believable;
- wordmark clean;
- violet dominant;
- particles/FX subordinate.

## 10. Object-light interaction

### Upper purple body
- avoid overexposure that turns violet to white/pink;
- maintain surface metal response.

### Lower gunmetal
- give enough edge/specular information to avoid black silhouette loss.

### Connecting rod
- lighting should reveal directional brushing/forging;
- must remain readable even when energy travels along it.

### Bearings
- use small controlled highlight sources to communicate precision;
- avoid mirror clipping.

## 11. Emission and bloom

Emission:
- independent from lighting preset;
- preset may set default intensity state but not bake it.

Bloom:
- post/render effect;
- restrained;
- must not expand the logo silhouette substantially;
- disabled in geometry/QA reference renders.

## 12. Environment

Allowed:
- deep navy/graphite studio;
- dark industrial space;
- subtle premium reflective floor/surface;
- restrained environment geometry.

Environment must not become a fixed logo component.

## 13. Naming

Use:

```text
LIGHT_DARK_OFF
LIGHT_PURPLE_ACTIVATION
LIGHT_ORANGE_INDUSTRIAL
LIGHT_NEUTRAL_STUDIO
LIGHT_POLISHED_CORPORATE
LIGHT_HERO_CINEMATIC
```

## 14. Validation

For each preset, capture a controlled comparison render from `CAM_FRONT_HERO` and, where relevant, `CAM_THREE_QUARTER_HERO`.

PASS when:

- logo geometry remains readable without FX;
- materials remain physically plausible;
- purple identity is preserved;
- orange remains support-only;
- no preset requires texture rebaking;
- presets can be switched in editable source;
- final corporate preset works with zero particles/smoke;
- neutral studio preset exposes geometry/material defects rather than hiding them.
