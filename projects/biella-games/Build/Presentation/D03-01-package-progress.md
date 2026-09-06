# D03-01 isolated Linux package qualification increment

**Task remains CONTINUE.** The current playable world now has a reproducible Linux Development build, isolated cook, exact archive readback, and six successful packaged runtime scenarios. The package launches with editor, project, original home, cook store and network unavailable. This qualifies the existing Vulkan **SM5** package and its TSR/NativeTAA profiles. It does not qualify the accepted SM6/Nanite production path or accept cold-start stutter or final art.

Canonical package: `/root/biella/artifacts/games/D03-01/BiellaGames-Linux-Development-D03-01-package-01.tar.zst` — 371,811,200 bytes; SHA256 `06510221abdcfa88e7fbb73dcbf31bb34de839101649aa83ffde2c3c1722b14a`. All positive runs use its same 33-member extraction. The archive and extracted bytes remain unchanged. Capture/package review status is `GENERATED_DRAFT`.

## Implementation and lineage

The editable `tests/*d03_01*package*.py` runners, `build_d03_01_game.py`, `repair_d03_01_engine_dependencies.py` and `repair_d03_01_cook_config.py` preserve prior attempts, require fresh workspaces, and retain native commands, logs and file hashes. No gameplay source, content, project configuration or production metadata changed in this increment.

`package-build-03/result.json` records the successful incremental native game build: 14 actions, 111.47 seconds, 85 source files unchanged and the installed-engine marker restored exactly. The installed distribution lacked required monolithic build inputs. The scoped repair restored missing mimalloc 2.0.0 source while preserving existing headers, built libsamplerate 0.2.2 with Unreal's Linux SDK, passed its 13 upstream tests, and added the exact Linux include/link rule. `package-toolchain-01/02` retain original archives, digests, licenses, build/test output and engine before/after identities. Both dependency notices are inside the game archive.

`package-cook-01/validation.json` records 317 exact project inputs and five matching binary/receipt files copied to a private snapshot. The `(Local)` DDC graph started empty. The 629.36-second cook compiled 9,294 shaders with zero shader-job DDC hits and no incrementally skipped packages: 668 packages cooked, 35 skipped by platform, 703 total. Native completion reports zero errors and warnings. Cooked output uses the task's Zen store; 29 loose files alone are not the complete cooked asset set.

Unreal appended Android editor defaults to the snapshot config. `package-cook-config-repair-01` verifies the precise append, keeps the generated original in a private recovery file, and restores exact canonical config bytes. No generated credential value is copied into this evidence. Staging then uses the supported Linux `UE_ZenSubprocessDataPath` spelling and task-local `uebp_EngineSavedFolder`/TMPDIR. `package-stage-07/validation.json` proves the selected preserved Zen store, native stage success, binary identity, archive creation and exact extracted-member readback. Earlier build/stage/fixture failures remain intact and are diagnosed in the failure ledger.

## Packaged runtime evidence

Each native process runs as `unreal` in a read-only package mount with isolated user/cache directories and a loopback-only network namespace. Host source, editor and prior DDC are masked. Cold means newly created task user/driver caches; warm reuses that exact state. OS page cache was not flushed. SDL dummy audio supports these rendering/gameplay checks; these runs make no new audible-mix quality claim.

| Profile / scenario | Result | Native frames | Captures | PSO creations over 20 ms | Largest creation ms |
| --- | --- | ---: | ---: | ---: | ---: |
| TSR cold surfaces | PASS | 1,289 | 43 | 235 | 346.25 |
| TSR warm surfaces | PASS | 1,277 | 43 | 1 | 22.47 |
| TSR environment | PASS | 1,473 | 5 | 9 | 32.02 |
| NativeTAA cold surfaces | PASS | 1,296 | 43 | 223 | 319.72 |
| NativeTAA warm surfaces | PASS | 1,331 | 43 | 9 | 28.31 |
| NativeTAA environment | PASS | 1,476 | 5 | 6 | 25.53 |

`package-series-01.json` joins the six exact receipts, cache continuity, actual `SF_VULKAN_SM5` observations, native AA/view state, shader-library loading and timings. Global and game IoDispatcher shader libraries load 6,431 and 1,475 unique shaders respectively. Environment scenarios preserve weapon interaction, panel destruction, shared hazard damage, safe-switch behavior, stream-out/return and restart. Material fallback/error checks and gross stationary/pan image checks pass. Selected images in `package-visual-review-01.json` retain readable player, HUD, road, hazard and interaction cues; gray blockout structures and empty world margins remain visible.

The engine reports PSO precaching enabled but `PipelineFileCache=0`, with the Vulkan binary pipeline cache absent. Warm runs create/use the isolated driver cache; they do not establish a durable Unreal pipeline cache. PSO worker creation durations may overlap and are not additive wall-frame stalls. **Cold runtime PSO hitches remain a production gap.**

Screenshot-free native measurements at 1280×720, uncapped with VSync/dynamic resolution off, on the recorded L40S / driver 580.178.04 / Linux Development host:

| Profile / state / window | Samples | Wall p50 / p95 ms | GPU p50 ms |
| --- | ---: | ---: | ---: |
| TSR cold stationary | 285 | 12.276 / 14.901 | 3.659 |
| TSR cold pan | 254 | 13.703 / 15.585 | 3.714 |
| TSR warm stationary | 282 | 12.951 / 14.343 | 3.664 |
| TSR warm pan | 260 | 13.419 / 15.117 | 3.720 |
| NativeTAA cold stationary | 296 | 11.586 / 14.405 | 3.347 |
| NativeTAA cold pan | 249 | 13.825 / 15.492 | 3.363 |
| NativeTAA warm stationary | 281 | 12.908 / 14.599 | 3.305 |
| NativeTAA warm pan | 283 | 12.346 / 13.951 | 3.314 |

Generated frames are not used. These bounded windows do not measure total cold-start cost or establish fine ghosting/disocclusion quality.

## Negative control and preservation

`package-missing-shader-04/validation.json` passes the precise missing-cache control. A separate package copy is repacked without only `Engine/GlobalShaderCache-VULKAN_SM5.bin`; readback proves all other 1,728 logical pak files and the IoStore containers unchanged. It exits with code 1 in 1.67 seconds and identifies that exact missing global cache. It cannot borrow editor/source/cache/network data. The original archive and extraction are verified before/after.

Earlier controls retain their failures: private-copy ownership prevented launch; removing a whole IoStore index prevented pak mounting before shader initialization; UnrealPak extraction used a literal backslash in a Linux path; and a private response-file permission error yielded an empty pak despite tool exit zero. The final runner uses private path aliases and ownership, checks native error output, and compares extracted logical bytes. The engine and canonical package are never mutated by this control.

`D03-01-package-final-readback-01.json` passes 2,534 exact identities, native binary/build/cook/stage/runtime lineage, 8,142 positive frames, 182 decoded captures, and the precise negative mutation. Predecessor preservation and the file manifest accompany this receipt. Local commit and exact Git-object readback precede handoff. The Auto Feeder owns GitHub/Drive publication and canonical transitions; no remote publication is claimed here.

## Remaining D03 work

Current Linux inherits SM5 from engine configuration. `package-design-01/shader-platform-scope.json` shows the installed platform definition does not support Nanite on SM5. Prior requested Nanite/VSM console values must not be read as proof of executed capability. The accepted SM6 production path needs explicit configuration and its own native/cook/package/temporal evidence; preserve this fallback archive when doing that work.

Other gaps remain: cold PSO stutter treatment; final world/lighting/character/weapon/vehicle art; broader VFX/audio, directional interaction, transition/LOD/crowd coverage; fine ghosting/disocclusion, particles/reflections and high-speed motion; wider hardware and Shipping qualification. Do not advance beyond D03-01 or reopen passed contact/aim/action/defeat/vehicle/seat increments.
