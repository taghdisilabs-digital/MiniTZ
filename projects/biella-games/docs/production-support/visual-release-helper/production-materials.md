# Production Material — Finish the Playable Slice

Basis: current D17 visual assessment and final-layer acceptance contract. Re-read live assessment before execution.

## Highest-value visual work
1. **Industrial density:** extend the Street01-to-service-bay approach with authored foreground/midground structure, catwalk/gantry depth, functional barriers and route-preserving props. Store editable construction in `SourceAssets/Environment`; imported/runtime assets in `Content/Environment`.
2. **Focal actors:** replace mannequin/prototype-looking player, rival, infected and block-like weapon presentation with production-readable silhouettes while preserving accepted combat behavior. Use `SourceAssets/Characters` and `Content/Characters` for character art.
3. **Scene-wide materials:** keep the existing service-ground/switch/panel work, but propagate credible metal/concrete classes, nonuniform roughness, wear, dirt, localized moisture and damage across the focal route. Existing editable shader sources are in `SourceAssets/Materials`.
4. **Infection takeover:** move from isolated repetitive lobes to attached organic invasion that visibly deforms/occupies engineered surfaces, varies scale, branches, and communicates cause/effect without becoming floating decoration.
5. **Storm/practical lighting:** preserve the cooler overcast base and warm service lamps, then establish readable depth, shadow hierarchy, volumetric separation and stable exposure through ordinary gameplay motion.

## Existing material sources to reuse
- `SourceAssets/Materials/ServiceGround.hlsl`
- `SourceAssets/Materials/ServicePanel.hlsl`
- `SourceAssets/Materials/ServiceSurface.hlsl`
- `SourceAssets/Materials/ServiceSwitch.hlsl`
- `SourceAssets/Materials/ProductionSurface.hlsl`

## Proof after each affected layer
Capture ordinary gameplay at the normal camera, compare the same route/state against the previous candidate, reject any major visual defect, and retain exact editable-source/build/package identity. Do not use beauty-only or editor-only frames as slice acceptance.

## Packaging bridge
Once the visual layer is actually qualified, preserve D17 raw evidence and use the existing D08 exact-member package/install lineage. Do not create a new package format. D08 currently proves Linux Development diagnostics; Win64 Shipping requires its separate real Windows package/play qualification.
