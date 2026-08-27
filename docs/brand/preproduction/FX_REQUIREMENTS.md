# Biella Engine — FX Requirements

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Primary use: Biella Engine mechanical assembly, activation and reveal

## 1. FX objective

FX must support the story of mechanical connection becoming coordinated power.

Approved progression:

```text
separate
→ move
→ align
→ mechanical lock
→ sparks / energy fusion
→ activation
→ reveal
```

FX are secondary to the mechanism. The symbol must remain credible with every FX layer disabled.

## 2. Required independently controllable FX families

Provide independent source/control for:

```text
FX_SPARKS
FX_SMOKE
FX_DUST
FX_PURPLE_PARTICLES
FX_ELECTRICAL_ARCS
FX_FUSION_GLOW
FX_HEAT_DISTORTION
FX_LOCK_SHOCKWAVE
FX_LIGHT_SWEEPS
FX_ENERGY_PULSE
```

Where a final shot does not use every family, the source system may keep unused emitters disabled rather than deleted if they belong to the approved production setup.

## 3. Mechanical lock sparks

Purpose:
- communicate physical contact and energy release at seating.

Behavior:
- originate from upper/lower lock regions or a physically credible contact region;
- directional velocity follows contact mechanics;
- short-lived;
- small variation in size and lifetime;
- orange/white hot core allowed;
- `#F28A2E` is the approved heat-orange identity role.

Avoid:
- fireworks;
- full-frame showers;
- continuous sparks after the lock has settled.

## 4. Smoke

Purpose:
- add industrial depth and contact aftermath.

Behavior:
- subtle;
- low-density;
- reacts to local event;
- does not hide logo edges or wordmark;
- decay before final tagline hold.

Allowed:
- thin contact smoke;
- faint background atmosphere.

Prohibited:
- thick explosion clouds;
- fantasy fog engulfing the logo.

## 5. Dust / micro-debris

Purpose:
- reinforce scale and mechanical force.

Behavior:
- fine particles;
- localized response to motion/lock;
- low visual hierarchy;
- physically affected by movement/shock where practical.

No large destructive fragments unless a future approved scene explicitly requires them.

## 6. Purple particles

Purpose:
- visualize controlled activation/energy transfer.

Color:
- anchored to Biella violet/emission violet.

Behavior:
- concentrated near connection path;
- may travel from bearings through rod;
- restrained count;
- velocity follows mechanism;
- decay before corporate final hold.

Avoid:
- generic AI particle sphere;
- galaxy/starfield effect;
- random screen-filling floaters.

## 7. Electrical arcs

Purpose:
- accent energy fusion at real conductive/mechanical connection points.

Rules:
- short duration;
- localized;
- endpoints must attach to approved FX helpers or geometry points;
- arcs may bridge bearing/rod contact regions;
- no fantasy lightning storm;
- no uncontrolled branching across the whole symbol.

Electrical arcs are optional in clean corporate derivatives.

## 8. Fusion glow

Purpose:
- bridge mechanical lock into violet activation.

Behavior:
1. begins locally at contact;
2. expands along a defined mechanical/conductive path;
3. resolves into restrained active-state emission;
4. never obscures geometry.

Glow is a render/composite layer, not baked into Base Color.

## 9. Heat distortion

Purpose:
- support brief high-energy mechanical lock/ignition.

Behavior:
- localized near orange heat/spark region;
- subtle;
- short-lived;
- must not permanently warp the logo or wordmark.

Do not use during final static corporate state.

## 10. Lock shockwave

Purpose:
- communicate a decisive connection event.

Allowed forms:
- subtle air-pressure distortion;
- brief dust displacement;
- very restrained radial energy response;
- short camera/environment reaction when approved.

Prohibited:
- giant sci-fi ring dominating frame;
- destructive explosion.

The shockwave may be omitted from clean/minimal variants.

## 11. Light sweeps

Purpose:
- reveal machined form and transition toward final hero lighting.

Behavior:
- physically plausible/specularly useful;
- follows engineered surfaces;
- limited count;
- does not replace actual lighting;
- no continuous scanning-HUD effect.

## 12. Energy pulse

Purpose:
- express coordinated activation through the connecting mechanism.

Canonical direction:
- joint → rod → connected body system.

The production team may choose upper-to-lower, lower-to-upper or bilateral convergence per shot, provided:
- the path is mechanically coherent;
- the rod remains central;
- the final state resolves identically.

Pulse controls:
- start time;
- duration;
- path;
- intensity;
- width;
- color;
- falloff.

## 13. Intro timing

### 0.00–5.00
- no major FX;
- optional dust/atmosphere only;
- mechanism remains dormant.

### 5.00–6.25 — Lock
- contact sparks;
- optional micro-debris;
- optional short shock response;
- optional localized heat distortion.

### 6.25–7.75 — Fusion
- sparks decay;
- violet fusion glow starts;
- purple particles and short arcs may appear;
- energy begins traversing rod.

### 7.75–9.00 — Activation
- energy pulse reaches connected bodies;
- controlled emission grows;
- light sweep may reveal completed form;
- FX begin settling.

### 9.00–10.25 — Reveal
- particles/arcs decay;
- clean hero form becomes priority.

### 10.25–12.00 — Wordmark/tagline
- no distracting new FX events;
- only subtle residual glow/atmosphere allowed.

## 14. Layer separation

FX must remain independently controllable in source/compositing.

At minimum separate:

```text
sparks
smoke
dust
purple particles
arcs
glow/emission enhancement
heat distortion
shock response
light sweeps
energy pulse
```

Do not flatten all FX into the only available master before approval.

## 15. Render/pass requirements

Where supported, preserve useful separation through:
- beauty;
- emission;
- depth;
- motion vectors;
- object/material IDs or Cryptomatte;
- dedicated FX passes/layers where compositing requires them.

FX source must remain reproducible from editable project state.

## 16. Performance / implementation rule

FX may be implemented in:
- native DCC particles/simulation;
- renderer-native systems;
- compositing systems;
- real-time engine systems;
- a combination.

Implementation is flexible. Visual identity and editability are not.

Cache/simulation files are not the only authoritative source; settings and reproducible project state must be retained.

## 17. Variant behavior

### Cinematic
May use all approved FX within restraint.

### Minimal
- no sparks/smoke;
- limited violet activation only.

### Corporate
- zero or near-zero particles;
- no smoke;
- clean restrained emission.

### Loading loop
- no one-time destructive event required;
- use a repeatable energy pulse, controlled light sweep or subtle activation loop;
- loop seam must not expose geometry drift.

## 18. Prohibited drift

Never use:
- giant explosion;
- fantasy lightning storm;
- holographic grid takeover;
- code rain;
- generic AI particle globe;
- excessive lens flare;
- rainbow energy;
- full-object neon;
- arcade HUD effects;
- FX that hide incorrect geometry.

## 19. Validation

PASS when:

- each required FX family is independently controllable;
- disabling all FX leaves a valid logo scene;
- sparks originate from plausible lock/contact areas;
- orange remains heat support only;
- violet remains primary activation identity;
- energy path reinforces the connecting rod;
- final wordmark/tagline remain legible;
- clean/minimal/corporate variants can be produced without rebuilding the scene;
- FX survive source reopen/relink;
- no required result depends solely on a flattened preview.
