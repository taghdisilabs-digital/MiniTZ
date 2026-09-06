# D03-01 — Authored street façades and native fallback

Six existing buildings in `BiellaOpenWorldMap` now use editable industrial façade meshes, replacing their cube presentation. Windows, frames, piers, spandrels, coping, canopies, vents and drainpipes execute in the existing streamed playable world. This increment is validated; **D03-01 remains CONTINUE** and the art remains **GENERATED_DRAFT**.

`SourceAssets/Architecture/StreetBlocks.blend`, six FBXs, the source manifest and `build_street_blocks.py` preserve the editable asset lineage. Three meshes have 71,252 triangles each and three have 90,428. `Content/Python/import_street_blocks.py` imports the meshes, authors the finish material and four instances, enables Nanite and retains 100% triangle fallback geometry. The existing concrete surface remains in use. Both master materials explicitly support Nanite.

The original six actor GUIDs, transforms, tags, streaming/HLOD settings and BlockAll collision profile are preserved. Each replacement retains a simple box matching the original cube envelope. Geometry is cosmetic to the authoritative gameplay world. The open-world authoring script reuses these assets when present. Native HLOD rebuilding preserves 13 HLOD actors and 58 instances, including six HLODs containing façade finishes.

Fresh Blender readback verifies six saved meshes, bounds, triangle counts, nondegenerate faces, material slots and FBX digests. `architecture-author-07` verifies saved Unreal meshes, actor invariants and readback without asset mutation. `architecture-hlod-02` verifies the rebuilt world and filtered surface materials in fresh native processes. The exact compiled module is reused: all 90 native build inputs are unchanged from `sm6-build-01`; no native rebuild is needed for these asset and authoring changes.

| Native runtime evidence | Profile | Frames | PNGs | Result |
| --- | --- | ---: | ---: | --- |
| `architecture-sm6-tsr-02` | Default SM6 / ProductionTSR | 1,187 | 43 | PASS |
| `architecture-sm5-taa-01` | Explicit SM5 / NativeTAA | 1,278 | 43 | PASS |
| `architecture-environment-sm6-01` | Default SM6 / ProductionTSR | 1,446 | 5 | PASS |
| `architecture-environment-sm5-01` | Explicit SM5 / NativeTAA | 1,441 | 5 | PASS |

All four runs share 344 exact runtime input identities and the same native module (`5354cd383cdf65e46c761e839e311d6003fa5a0a42cef82fb007e5055345b3a5`). The saved-content check binds 220 asset files. `architecture-series-precommit-01.json` independently replays the raw evidence against current bytes: **5,352 native frames and 96 PNGs**, without generated frames. The environment tests exercise real hazard damage, panel destruction, shots, switching, physics dormancy and state after streaming.

The SM6 primitive snapshot contains all six mesh identities with Nanite data and one active Nanite proxy per mesh across the detailed and distant representations. Four additional HLOD component rows report proxy zero. That field does not distinguish an absent proxy from a non-Nanite proxy, so the verifier requires per-mesh coverage and all detailed actor proxies rather than claiming every duplicate representation is simultaneously active. The explicit SM5 snapshot retains all six meshes with zero Nanite proxies. Native feature-level checks confirm the requested renderer paths; proxy counts alone do not establish visible-pixel coverage.

| Uncapped surface window | Wall p50 / p95, ms | GPU p50, ms |
| --- | --- | ---: |
| SM6 stationary, 250 frames | 14.104 / 16.519 | 6.156 |
| SM6 camera pan, 256 frames | 13.798 / 15.502 | 6.228 |
| SM5 stationary, 262 frames | 13.366 / 14.943 | 3.386 |
| SM5 camera pan, 275 frames | 12.705 / 14.622 | 3.405 |

Measurements are native Linux Vulkan Development editor frames on the existing L40S host at 1280×720 with existing caches. The surface measurement windows exclude capture-request frames and disable VSync/frame caps. These single runs are representative measurements, not a controlled hardware comparison. Environment runs use a 60 FPS cap for behavior validation. Forced SM5 establishes an explicit fallback path, not automatic detection of unsupported hardware.

Eight read-only negative checks reject incorrect claims: four façade checks against the unchanged old cube world, the actual missing-material-usage failure and opposite-platform observations, plus four opposite native feature-level claims. The earlier preimplementation negative control is also retained. No synthetic CSV rows substitute for native observations.

The first SM6 façade run failed because the concrete and finish masters lacked Nanite material usage. Its raw logs and captures remain under `architecture-sm6-tsr-01`. Enabling the usage flags, saving the assets and rebuilding affected HLODs produced the fresh passing run. Earlier Blender/import/readback failures and the overly strict duplicate-HLOD assertion remain preserved with their diagnostics; they are not positive evidence.

`architecture-visual-review-01.json` binds five directly inspected PNGs. Recessed façade detail, street edges, the player and gameplay cues remain visible in the selected SM6 and SM5 views. Gray workshop geometry, dark world margins and existing UI spacing still need work. Selected stills and gross temporal pixel deltas do not establish fine continuous ghosting or disocclusion quality.

`architecture-preservation-01.json` verifies all 267 prior SM6 manifest entries plus the manifest itself, and the exact prior 371,811,200-byte SM5 Development archive. The intentional tracked changes are the world map, master material, two authoring scripts, six building packages and 13 HLOD packages. No 03/04 or Project production metadata changes are part of this increment; Engine P4-06 remains INCOMPLETE_DEFERRED.

Local delivery is bound by `D03-01-architecture-file-manifest.json` and the post-commit Git readback under `/root/biella/artifacts/games/D03-01/architecture-git-readback-01.json`. The Auto Feeder owns GitHub/Drive publication and canonical transitions. No remote publication is claimed here.

Remaining D03 work includes a fresh SM6 cook, stage and package containing these exact assets; clean-launch shader/PSO behavior; finer motion/temporal qualification; and remaining production world, lighting, character, weapon, vehicle, animation, VFX/audio and crowd presentation. The prior packaged build is preserved evidence of its own source and does not qualify these new façades. This receipt does not advance the task.
