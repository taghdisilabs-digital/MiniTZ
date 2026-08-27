# Biella Engine — Locked vs Flexible

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Authority: Founder-approved Biella Engine brand direction and `BRAND_MASTER_SPEC.md`

## Purpose

This document separates identity decisions that production must preserve exactly from execution choices that may vary while remaining faithful to the brand.

A flexible choice never overrides a locked rule.

## Locked

The following require founder approval before they may change.

### Identity

- Canonical company/product name: `Biella Engine`.
- Approved tagline: `CONNECTING INTELLIGENCE TO EXECUTION`.
- The identity is based on the mechanical meaning of *biella*: a connecting rod that transfers force and turns independent capability into coordinated execution.
- The symbol must express a load-bearing mechanical connection, not a generic AI motif.
- The connecting rod is the semantic center of the symbol, not decoration.
- The approved upper-body / lower-body / connecting-rod / bearing relationship must be preserved.
- Once `MASTER_LOGO_GEOMETRY.svg` is approved, that vector geometry becomes the single authoritative geometry for every derivative.

### Geometry and construction

- Do not redesign, mirror, rotate, round, stretch, distort, simplify, or reinterpret the approved symbol geometry.
- Do not substitute a different silhouette because it is easier to model, animate, print, or fit into UI.
- Bearings, connection points, negative space, and the visual load path must remain coherent with the approved construction.
- The symbol must remain viable as:
  - clean vector geometry;
  - monochrome mark;
  - one-color manufacturing mark;
  - physical engraving/emboss/deboss;
  - 3D mechanical object;
  - active cinematic expression.

### Core brand color and material identity

Initial locked production tokens:

| Role | Token |
|---|---|
| Primary brand violet | `#7C3AED` |
| Emission violet | `#9B5CFF` |
| Deep navy black | `#050812` |
| Gunmetal | `#1A1F27` |
| Steel | `#8E949E` |
| Polished silver | `#E4E7EC` |
| Carbon black | `#090B0F` |

Locked treatment principles:

- Violet is the dominant brand accent.
- Premium engineered metal is the primary material language.
- Purple emission is restrained and localized.
- Heat orange `#F28A2E` is cinematic support only; it must not become the primary brand or general UI accent.
- The identity must work without glow, texture, lighting, or metallic shading.

### Brand character

Preserve:

- premium industrial engineering;
- believable mechanical construction;
- machined-metal credibility;
- controlled, high-torque precision;
- restrained futuristic styling;
- AAA-quality production finish;
- enterprise/international business credibility;
- dark premium presentation.

Never drift into:

- AI brain or neural-network imagery;
- chatbot/robot/cloud iconography;
- generic cube/hexagon/infinity/crypto marks;
- esports mascot styling;
- arcade HUD branding;
- toy-like sci-fi;
- fantasy emblem styling;
- flame/lightning identity;
- rainbow/RGB branding;
- orange-and-blue game-UI branding.

### Wordmark rules

- Primary wordmark hierarchy is `BIELLA` with `ENGINE`.
- Wordmark typography must remain engineered, uppercase, premium, restrained, and highly legible.
- Decorative FX must remain separate from authoritative wordmark geometry.
- Unlicensed typefaces must never be embedded in authoritative source.

## Flexible

These may vary per deliverable provided every locked rule remains intact.

### Camera and composition

- hero camera angle;
- front / side / top / low / macro framing;
- camera focal length and depth of field;
- crop and framing per aspect ratio;
- symbol-above-wordmark or symbol-left-of-wordmark composition;
- secondary composition for presentation, loading, UI, social, print, and physical use.

### Cinematic effects

- spark density and direction;
- smoke amount;
- dust intensity;
- particle count;
- electrical-arc frequency;
- fusion-glow duration;
- heat treatment;
- shockwave strength;
- light-sweep timing;
- energy-pulse timing;
- purple glow intensity within the restrained brand envelope.

FX must never alter master geometry or become required for recognition.

### Lighting and environment

Flexible:

- dark/off lighting;
- purple activation lighting;
- controlled industrial-orange support lighting;
- neutral studio lighting;
- polished corporate lighting;
- cinematic hero lighting;
- supporting backgrounds and environments.

The environment may support the brand but must not become part of the logo.

### Material micro-variation

Allowed when physically credible:

- brushed versus finely machined steel response;
- roughness variation;
- subtle edge polish;
- controlled anisotropy;
- subtle premium wear;
- background surface selection.

Not flexible:

- turning metal into plastic;
- excessive corrosion/damage;
- full-object neon;
- material changes that obscure construction.

### Production implementation

Flexible:

- DCC, renderer, compositor, editor, or layout tool;
- render engine;
- intermediate exchange format;
- procedural versus manual construction method;
- implementation-specific node graphs;
- non-authoritative helper rigs;
- delivery-specific compression settings where the technical delivery specification allows a range.

Tool choice must not change authoritative geometry, brand semantics, required editability, or export validity.

### Typography implementation

Until `TYPOGRAPHY_SPEC.md` locks the exact typeface family:

- candidate typeface;
- fallback typeface;
- exact weight within approved direction;
- tracking adjustments for a specific layout.

Typeface licensing and substitution must remain explicit.

## Change rule

For any proposed change:

1. Identify whether the affected item is locked or flexible.
2. If locked, do not change it without founder approval.
3. If flexible, verify that the change does not alter a locked invariant.
4. Update `VERSION_LOG.md` for every approved revision.
5. Regenerate dependent assets from the corrected authority rather than manually patching downstream exports.

## Authority order

1. Founder-approved current instruction.
2. `BRAND_MASTER_SPEC.md`.
3. `PRIMARY_REFERENCE.png`.
4. Approved `MASTER_LOGO_GEOMETRY.svg` once it exists.
5. Construction/material/type/motion specifications.
6. Derived exports.

When a higher authority changes, lower derived assets must be regenerated or revalidated.
