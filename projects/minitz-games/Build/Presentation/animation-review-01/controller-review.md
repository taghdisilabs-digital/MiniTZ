# D03-01 animation increment — bounded controller review

This is a review by the canonical controller. The configured local Qwen
`unreal.assist` route was attempted for both design assistance and code review;
both returned a request timeout. Their exact requests and responses remain in
`animation-design-01` and this directory. No independent provider approval is
claimed. Native Unreal and deterministic validation provide the acceptance
evidence for this implementation increment.

- Movement authority remains the existing APawn/capsule and gameplay jump
  clock. The native animation instance samples actual displacement, including
  the NPC movement path; it does not infer NPC speed from an unused movement
  component velocity. `IgnoreRootMotion` prevents imported rifle clip root
  motion from moving the gameplay pawn.
- Gameplay UObject reads occur in proxy `PreUpdate` on the game thread. The
  worker update consumes a copied sample. Locomotion and jump assets have hard
  UObject references; standalone animation nodes supply a native graph without
  a Blueprint constant table.
- Dormancy, wake, seat entry/exit and defeat refresh visibility, component tick
  and motion sampling. The actual native lifecycle scenario exercises these
  transitions. Existing blockout geometry remains only as the fitted seated
  fallback. No skeletal seated pose is claimed.
- Skeletal meshes, the hand-attached placeholder weapon and bone-attached
  role marks are cosmetic and do not affect collision or navigation. Front and
  back marks use the actual reference-pose spine transform; native vertex
  measurements exposed and resolved two fit errors before the final candidate.
- Streamed actors rebuild cosmetic components without accumulating old role
  components. Unreal's installed `UPrimitiveComponent::CreateDynamicMaterialInstance`
  implementation reuses an existing MID, so repeated BeginPlay does not create
  a chain of dynamic material parents. Source inspected at
  `/opt/unreal/UE_5.8.2/Engine/Source/Runtime/Engine/Private/Components/PrimitiveComponent.cpp`.
- The shadow correction derives the source material and both material
  instances. It adds textured base color times a bounded fill to the existing
  emissive expression while preserving the original surface inputs and texture
  inheritance. Native graph readback and actual image checks are required;
  a parameter value alone did not establish visual success.

No launch or full animation-system qualification is claimed. Remaining work
includes final character and weapon art, terrain foot placement/IK, action,
aim, hit and defeat layers, skeletal vehicle presentation, broader directional
and transition coverage, offscreen/LOD and crowd budgets, and shipping platform
validation. These remain inside unfinished D03-01 alongside world rendering,
VFX and audio quality.
