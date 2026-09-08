# Biella Games — Final Visual Layer Acceptance

Status: `OWNER_DIRECTED_ACTIVE_EXECUTION_CONTRACT`
Scope: D17 final playable visual layer. This is Project-specific visual acceptance, not Engine policy.

## Authority and quality bar
`AAA_REALISTIC_RUNTIME_BAR`: final playable output follows the accepted realistic AAA runtime contract in `docs/runtime-contracts/AAA_TPP_RUNTIME_CONTRACTS_01_10.md` §03–04 and production-asset/runtime evidence requirements in Contracts 39–49. The owner-current reference direction is a dense vertical industrial survival arena overtaken by biologically unstable red infection, with cold storm ambience, warm practical lighting, wet physically responsive materials, layered routes, and readable third-person combat. Reference branding/text/exact protected expression is never copied.

## Current baseline classification
`BASELINE_NOT_VISUAL_ACCEPTANCE`: the following D08 captures are valid runtime/mechanics evidence but are explicitly rejected as the final visual-quality bar:
- `Build/Release/D08-01/runtime/new-feedback-01/dense_combat.png` — SHA-256 `491727db1b654ce26d41ebae9e569bf16e1b94426042bf01f97c3f477fb2eade`.
- `Build/Release/D08-01/runtime/new-environment-02/captures/hazard_active.png` — SHA-256 `6053ade350e41e4cc746694c3cc8757b77ccc0bccb083ead203de407b8534b60`.

Observed baseline gaps to close in D17: sparse/blockout composition, primitive focal geometry, mannequin/placeholder-looking actors, flat/default-like surfaces, weak roughness/wetness/material breakup, little atmospheric depth, weak engineered-vs-infected environmental identity, low prop/set-dressing density, and HUD/debug presentation that dominates the image. These baseline defects must not be normalized as "style" or inherited as the D17 acceptance reference.

## Hard visual requirements
- `NO_PLACEHOLDER_OR_PRIMITIVE_FOCAL_ART`: canonical slice foreground/midground may not read as blockout boxes, default primitives, mannequin substitutes, debug colors, or temporary test art.
- `PHYSICALLY_COHERENT_PBR`: focal surfaces show credible material class, roughness/specular response, depth, wear, moisture/dirt and damage; wet ground/reflections are coherent with lighting and geometry rather than a uniform glossy filter.
- `DENSE_VERTICAL_WORLD`: playable composition has authored foreground/midground/background depth, layered routes, structures, barriers, props and vertical silhouettes while preserving collision, navigation and combat readability.
- `INFECTION_ARCHITECTURE_INTEGRATION`: infection visibly invades/changes the engineered arena through coherent organic growth/state response; it is not represented only by red actor colors or floating decals.
- `LIGHTING_ATMOSPHERE_DEPTH`: motivated practical lights, readable shadow structure, exposure, reflections and atmospheric depth create the cold-storm/warm-task-light contrast without hiding gameplay.
- `PLAYER_RIVAL_INFECTED_ARENA_PRESSURE`: player, rival, infected and arena-pressure consequence are visually distinguishable and can coexist in one readable evolving encounter.
- `GAMEPLAY_DISTANCE_READABILITY`: silhouettes, threats, routes, hazards, interactables and state feedback remain legible from the normal gameplay camera during motion and combat.
- HUD/UI must be compact, hierarchy-led and gameplay-integrated; debug/status panels or oversized text may not dominate the canonical proof frame.
- Animation/VFX/audio feedback must arise from real events and support consequence/readability; no post-produced fake gameplay or disconnected beauty scene.

## Major-defect rejection
`VISUAL_DEFECT_BUDGET_ZERO_MAJOR`: any major defect keeps the task incomplete. Major defects include placeholder focal art; sparse empty arena composition; fused/floating/unsupported geometry; implausible scale/access; broken skinning/anatomy/contact; obvious cloned actor presentation in the focal encounter; flat/default/missing materials; contradictory lighting/reflections; severe exposure loss; no visible infection/world takeover; HUD obscuring combat; temporal shimmer/ghosting/popping that breaks readability; screenshot-only/cinematic substitution; or a visible result materially below the accepted runtime AAA-realistic contract.

`REJECT_AND_FIX_MAJOR_VISUAL_DEFECTS`: do not explain a major defect away, relabel it as style, reduce the target, or pass because mechanics/tests succeeded. Fix/regenerate/re-author the smallest affected visual boundary and validate again.

## Execution loop
`CREATE_FIX_VALIDATE_REPEAT`:
1. Capture current raw runtime at the normal gameplay camera.
2. Compare against this contract and list concrete gaps by environment/material/lighting/character-animation/VFX-HUD/readability.
3. Reuse accepted assets/systems; create or fix only the missing layer.
4. Build only the affected scope; run real gameplay with the same mechanics.
5. Capture the same type of states again and compare `COMPARE_BASELINE_TO_FINAL`.
6. Reject outputs with any major defect; keep only materially improved, buildable, runtime-coherent results.
7. Repeat until every required characteristic is observable and no major defect remains.

`DO_NOT_LOWER_QUALITY_TO_PASS`: performance optimization may use explicit scalability/LOD/streaming, but it may not silently reduce the final visual target or turn a low-quality fallback into the accepted canonical slice.

## Evidence and completion
`RAW_GAMEPLAY_CAPTURE_REQUIRED`: D17 evidence must include real-runtime captures tied to exact source/build identity from at least traversal/spatial composition, dense combat with player+rival+infected, and arena-pressure/environment consequence states. Capture at gameplay distance; use 1280x720 and 1920x1080 where the existing harness supports both without inventing a new platform promise.

`NO_SCREENSHOT_ONLY_PASS`: screenshots support visual judgment but do not prove implementation. Completion also requires editable source/assets, build/runtime execution, relevant interaction/state evidence, and task-derived logs/measurements. A generated still, beauty render, config toggle, successful compile or agent statement alone cannot pass.

`NO_PASS_ON_CURRENT_D08_BASELINE`: D17 cannot close using only the two explicitly classified baseline captures or visually equivalent placeholder/blockout output.

`NO_REVIEW_ONLY_LOOP`: D17-05/06/07 are creation tasks first and qualification tasks second. The strong authoritative executor is expected to make the fixes rather than merely report them.

`VISUAL_QUALITY_IS_EXECUTION_WORK_NOT_OWNER_WAIT`: do not create an owner-approval pause, review meeting, or separate gate. Execute against this explicit contract; Mahdi may override any result, but ordinary D17 iteration proceeds automatically.
