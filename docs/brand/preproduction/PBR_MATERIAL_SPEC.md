# Biella Engine — PBR Material Specification

Status: APPROVED PRE-PRODUCTION CONTROL  
Version: 1.0  
Date: 2026-08-27  
Applies to: authoritative 3D Biella Engine logo source and derived renders

## 1. Purpose

Define a physically based material system that preserves the approved Biella identity across native DCC source, GLB/GLTF, FBX/OBJ workflows, cinematic rendering, stills, UI renders and future real-time implementations.

The material system must remain editable. A beauty render is never the material source.

## 2. Governing visual rules

Preserve:

- premium machined / forged metal;
- dominant Biella violet as the brand accent;
- dark gunmetal structural mass;
- brushed / forged steel connecting rod;
- polished bearing surfaces;
- controlled bevel highlights;
- localized purple activation/emission;
- restrained wear;
- physically plausible reflections.

Do not produce:

- plastic-looking metal;
- full-object neon;
- uncontrolled chrome;
- heavy rust/corrosion;
- baked beauty lighting in Base Color;
- irreversible flattened material appearance.

## 3. Required material families

Use stable material identities:

```text
BIELLA_MAT_UPPER_PURPLE_ANODIZED
BIELLA_MAT_LOWER_GUNMETAL
BIELLA_MAT_CONNECTING_ROD_STEEL
BIELLA_MAT_BEARING_POLISHED_STEEL
BIELLA_MAT_DARK_RECESS
BIELLA_MAT_EMISSION_VIOLET
BIELLA_MAT_WORDMARK_SILVER
BIELLA_MAT_WORDMARK_VIOLET
```

Optional fasteners/inserts may use additional materials, but may not redefine the core palette.

## 4. Core color anchors

| Material role | Base color anchor |
|---|---|
| Purple anodized / coated metal | `#7C3AED` |
| Violet emission | `#9B5CFF` |
| Gunmetal | `#1A1F27` |
| Steel | `#8E949E` |
| Polished silver | `#E4E7EC` |
| Carbon / dark recess | `#090B0F` |
| Deep environment black | `#050812` |
| Heat/spark support only | `#F28A2E` |

Color anchors define brand intent. Final rendered appearance depends on documented scene-linear color management and output transform.

## 5. PBR channel requirements

Where texture maps are used, support as applicable:

```text
Base Color / Albedo
Metallic
Roughness
Normal
Height / Displacement
Ambient Occlusion
Emission
Material ID / masks
Opacity only where genuinely required
```

Naming follows `FILE_NAMING_STANDARD.md`.

Example:

```text
BIELLA_ENGINE_CONNECTING_ROD_BASECOLOR_4K_v001.png
BIELLA_ENGINE_CONNECTING_ROD_METALLIC_4K_v001.png
BIELLA_ENGINE_CONNECTING_ROD_ROUGHNESS_4K_v001.png
BIELLA_ENGINE_CONNECTING_ROD_NORMAL_4K_v001.png
```

## 6. Channel interpretation

### Base Color

- sRGB source.
- Contains material color only.
- No baked direct light, reflections, AO shadow, bloom, sparks or emission.
- Metal surfaces may include subtle production variation but no painted fake specular highlights.

### Metallic

- linear / non-color data.
- Core exposed metals should be physically metallic.
- Dielectric coatings/paint layers may reduce exposed-metal response only when the shader model intentionally represents a coating.
- Do not use metallic merely to make a surface “shiny.”

### Roughness

- linear / non-color data.
- Must carry the primary distinction between brushed, polished and darker structural metal.
- Avoid uniform perfect mirrors.
- Micro-variation must remain subtle enough to read as premium manufacturing.

### Normal

- linear / non-color data.
- Use tangent-space normals unless a target pipeline explicitly requires another convention.
- Fine machining/brushing may be represented here.
- Do not use normal maps to fake major silhouette geometry.

### Height / Displacement

- linear / non-color data.
- Reserved for physically meaningful micro-detail or controlled macro detail that does not alter approved logo silhouette.
- Must be disableable without changing master geometry.

### AO

- linear / non-color data.
- May support real-time delivery.
- Must not be baked into Base Color master.

### Emission

- color source may use sRGB authoring and scene-linear transform in render.
- Emission is independently controllable.
- Default/off state intensity = zero.
- Active state uses localized violet emission, primarily at bearings, inserts, conductive paths and selected bevel/energy accents.
- Full-object emission is prohibited.

## 7. Material targets

These are production target ranges, not immutable shader-engine constants. Equivalent physical appearance may be achieved through different DCC/renderer models.

### Upper body — purple anodized/coated metal

```yaml
material: BIELLA_MAT_UPPER_PURPLE_ANODIZED
base_color: "#7C3AED"
metallic_target: 0.75-1.00
roughness_target: 0.20-0.38
normal_detail: fine_machined_or_anodized_microtexture
emission: off_by_default
```

Intent:
- premium purple metal;
- retains metal response;
- not glossy plastic;
- controlled highlights;
- optional localized activation separate from base material.

### Lower body — dark gunmetal

```yaml
material: BIELLA_MAT_LOWER_GUNMETAL
base_color: "#1A1F27"
metallic_target: 0.90-1.00
roughness_target: 0.28-0.48
normal_detail: subtle_machining
emission: none
```

Intent:
- dense structural weight;
- darker than connecting rod;
- readable under low-key lighting.

### Connecting rod — brushed / forged steel

```yaml
material: BIELLA_MAT_CONNECTING_ROD_STEEL
base_color: "#8E949E"
metallic_target: 1.00
roughness_target: 0.22-0.42
anisotropy: allowed_when_supported
normal_detail: directional_brush_or_forging_microtexture
emission: none_or_separate_energy_path_only
```

Intent:
- central load-transfer component;
- mechanically credible;
- visually distinct from polished bearings.

### Bearings — polished steel

```yaml
material: BIELLA_MAT_BEARING_POLISHED_STEEL
base_color: "#E4E7EC"
metallic_target: 1.00
roughness_target: 0.08-0.22
normal_detail: minimal
emission: separate_inner_or_ring_element_only
```

Intent:
- precision joint;
- bright controlled highlights;
- never a featureless mirror.

### Recess / internal shadow material

```yaml
material: BIELLA_MAT_DARK_RECESS
base_color: "#090B0F"
metallic_target: 0.00-0.80
roughness_target: 0.40-0.75
```

Used only where mechanically/materially justified to create depth and component separation.

## 8. Texture resolution

Hero UV-based textures:

- 4096×4096 minimum;
- 8192×8192 allowed for macro hero assets when justified;
- 2048 and 1024 derivatives allowed.

Procedural materials are allowed and preferred where they improve editability. Procedural source must remain included in the native DCC file or material source.

## 9. Color management

Working/rendering:

- scene-linear workflow;
- ACEScg preferred for high-end rendering/compositing.

Delivery:

- sRGB for still/UI/web exports;
- Rec.709 Gamma 2.4 for SDR motion preview/master unless another approved delivery spec overrides;
- CMYK is a derived print conversion, never the PBR color master.

## 10. Material grouping and portability

Native scene must keep:

- geometry;
- shader graphs;
- image textures;
- procedural texture sources;
- emission controls

relinkable and organized.

All external texture paths must be package-relative at final delivery.

No missing external textures are permitted.

## 11. Activation material behavior

Off state:
- no emission;
- materials read from reflection and controlled lighting.

Activation state:
1. localized violet begins at joint/bearing regions;
2. energy may travel along the connecting rod through a separate emission/mask system;
3. selected upper/lower inserts or bevel accents may respond;
4. metal remains visible beneath/around the energy response;
5. bloom is a render/composite effect, not baked into the material texture.

## 12. Validation

PASS when:

- all material assignments are editable;
- metal reads as metal without beauty-light baking;
- purple identity matches the approved color role;
- emission can be switched independently;
- texture color spaces are correct;
- no missing texture references exist;
- required maps are present or procedurally reproducible;
- moving the project package does not break material links;
- materials survive a clean source-DCC reopen test;
- GLB/GLTF export preserves a reasonable real-time approximation without replacing the native master.

## 13. Authority

1. Founder-approved direction.
2. `BRAND_MASTER_SPEC.md`.
3. `PRIMARY_REFERENCE.png`.
4. Approved master geometry.
5. This specification.
6. Renderer/DCC-specific implementation.
