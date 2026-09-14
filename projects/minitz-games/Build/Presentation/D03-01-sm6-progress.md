# D03-01 — Linux SM6 and SM5 fallback increment

D03-01 remains **CONTINUE**. Linux now targets SM6 alongside the engine's inherited SM5 target. On the recorded host, the default launch selects SM6 and enables the Nanite/VSM renderer paths; an explicit `-sm5` launch retains the tested temporal reconstruction, gameplay visibility and environment behavior. This qualifies the shader-platform/profile boundary, not final production geometry or art.

## Implementation and native lineage

The opt-in game-view observer records the actual shader platform and renderer eligibility through Unreal's native API, alongside the existing reconstruction fields. Requested CVars alone cannot establish feature availability. The world-surface fixture separately records static-mesh Nanite data and scene-proxy types once before measured phases. Both observations are read-only; collision, movement, damage and streaming remain authoritative in the existing runtime.

The source parent is `c6f12d589a2d22d86739523f92fe1bf4b933ef57`. `sm6-build-01` succeeded in 54.615 seconds with 90 unchanged build inputs. Native module `Binaries/Linux/libUnrealEditor-BiellaGames.so` is 2,319,856 bytes, SHA-256 `5354cd383cdf65e46c761e839e311d6003fa5a0a42cef82fb007e5055345b3a5`. All six runs share 332 byte-identical runtime/source/configuration/content/verifier identities, including that module; the series verifier matched those inputs against the build and current disk.

The first launch (`sm6-default-tsr-01`) reached SM6 initialization but failed to load the generated module because its root-owned mode was 0700. `sm6-permission-repair-01` changed only its mode to 0755, verified identical bytes and readability as the runtime user, then the fresh launch passed. Failed logs and the repair receipt remain preserved. No successful native run was overwritten.

## Runtime matrix

All six scenarios passed on UE 5.8.2, Linux Vulkan Development editor runtime, 1280×720, the recorded L40S workstation and existing development caches. No feature-level flag is supplied for the SM6 rows. Automatic fallback on unsupported hardware is not exercised by `-sm5`.

| Evidence directory | Platform selection | Profile / scenario | Native frames | Captures |
| --- | --- | --- | ---: | ---: |
| `sm6-default-tsr-02` | SM6 (automatic default) | ProductionTSR / surfaces | 1289 | 43 |
| `sm6-default-taa-01` | SM6 (automatic default) | NativeTAA / surfaces | 1465 | 43 |
| `sm5-fallback-tsr-01` | SM5 (explicit -sm5) | ProductionTSR / surfaces | 1271 | 43 |
| `sm5-fallback-taa-01` | SM5 (explicit -sm5) | NativeTAA / surfaces | 1348 | 43 |
| `sm6-environment-tsr-01` | SM6 (automatic default) | ProductionTSR / environment | 1450 | 5 |
| `sm5-environment-taa-01` | SM5 (explicit -sm5) | NativeTAA / environment | 1459 | 5 |

The matrix totals **8,282 native frames and 182 PNG captures**. Surface tests verify all four production surface materials, actual view AA/resolution, movement, stationary capture and camera pan. Environment tests verify hazard damage, rival/infected reactions, switching, panel breakage and return after world streaming. `sm6-series-01.json` independently replayed each scenario and shader observation. Each of six unmodified native outputs also correctly rejected the opposite shader-platform claim. The preimplementation control rejected old SM5 evidence without the new capability fields.

The sampled surface world contains **163 static-mesh components and zero meshes with Nanite data or Nanite scene proxies** in each platform/profile run. SM6 eligibility and enabled CVars therefore do not establish Nanite geometry integration or visible pixel coverage. The current blockout cannot satisfy final art requirements merely by targeting SM6.

## Measured native frame times

These are uncapped surface windows with VSync disabled and screenshot request frames excluded. Wall time includes development runtime and observer overhead. GPU samples come from the existing native frame recorder. This is one host/run per configuration, with existing caches; it is not a controlled cross-platform benchmark, cold-start result or Shipping qualification. Environment runs are capped at 60 and are used for gameplay checks, not this comparison. No generated frames were used.

| Platform / profile | Window | Frames | Wall p50 ms | Wall p95 ms | GPU p50 ms |
| --- | --- | ---: | ---: | ---: | ---: |
| SM6 / ProductionTSR | stationary | 278 | 12.703 | 14.395 | 4.560 |
| SM6 / ProductionTSR | camera_pan | 274 | 12.600 | 14.417 | 4.611 |
| SM6 / NativeTAA | stationary | 288 | 12.339 | 14.005 | 4.159 |
| SM6 / NativeTAA | camera_pan | 283 | 12.323 | 13.872 | 4.180 |
| SM5 / ProductionTSR | stationary | 263 | 13.310 | 14.939 | 3.642 |
| SM5 / ProductionTSR | camera_pan | 272 | 13.000 | 15.008 | 3.690 |
| SM5 / NativeTAA | stationary | 295 | 11.959 | 14.102 | 3.290 |
| SM5 / NativeTAA | camera_pan | 269 | 12.996 | 14.609 | 3.302 |

## Review, preservation and delivery

`sm6-visual-review-01.json` records direct inspection of five native images with exact digests. The character, lane markings, curb, workshop entrance, hazard and HUD remain readable in those samples; shadow sharpness differs between SM6 and SM5. Gray blockout structures and empty black world margins remain. The captures are `GENERATED_DRAFT`. Selected stills and gross image-delta checks do not establish continuous fine ghosting or disocclusion quality.

`sm6-preservation-01.json` verifies all 364 entries in the previous package manifest, that manifest's exact committed bytes (365 files in total), and the canonical SM5 package archive. The earlier package remains qualified only against its preserved source; it is not an SM6 package and is not requalified by this matrix.

The exact implementation and evidence paths are recorded in `D03-01-sm6-increment.json` and `D03-01-sm6-file-manifest.json`. Final local hashes are in `D03-01-sm6-final-readback-01.json`; the post-commit Git readback is preserved at `/root/biella/artifacts/games/D03-01/sm6-git-readback-01.json`. The local task commit is the delivery checkpoint. Auto Feeder owns GitHub/Drive publication and canonical state transition; neither publication nor D03-01 completion is claimed here.

## Remaining D03-01 work

- Integrate representative authored production geometry with Nanite and verify loaded proxies plus actual runtime visibility; the current 163-component static-mesh snapshot has zero Nanite data/proxies.
- Build/cook/stage and independently qualify a fresh SM6 package from its exact current source; retain the preserved SM5 package and evidence.
- Resolve and measure cold runtime PSO stutter; the previous SM5 package reports 235/223 events above 20 ms and maxima 346/319 ms, with no application pipeline cache.
- Qualify fine motion ghosting/disocclusion beyond gross image deltas and selected PNG review.
- Complete production world/lighting/character/weapon/vehicle art and remaining animation, VFX/audio, LOD and crowd presentation coverage.
- Broader hardware/platform, automatic hardware fallback and Shipping qualification remain untested.

Continue from this source and evidence. The next bounded implementation should integrate representative project-owned production geometry in the existing playable world, preserving collision/traversal, and prove Nanite data/proxies and corresponding visible runtime geometry on SM6 plus visibility on SM5. Reuse the six passed runs as this configuration checkpoint; rerun only evidence affected by the next material change. Do not reopen the completed foot-contact, action, driver, audio or predecessor checkpoints without material invalidation.
