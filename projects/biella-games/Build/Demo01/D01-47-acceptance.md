# D01-47 — Clean packaged launch evidence

Status: `PASS`

## Package identity

- Artifact: `/root/biella/artifacts/games/D01-46/BiellaGames-Linux-x64-D01-46.tar.zst`
- SHA256: `c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8`
- Archive size: `297346213` bytes
- Package layout: Linux x64 Development game with `BiellaGames-Linux.pak`

## Fresh packaged launches

Each run extracted the exact archive into a new temporary directory, verified the
packaged executable and pak, and launched `Linux/BiellaGames.sh` as the `unreal`
runtime user. The package was not run from the editable project directory.

| Run | Runtime result | Observed evidence |
|---|---:|---|
| NullRHI launch | `PACKAGED_RC=0` | pak mounted; `GAME_INSTANCE_READY`, `WORLD_READY`, `HUD_READY`, and `CONTROLLER_READY`; `LogExit: Exiting.` |
| Vulkan/Xvfb launch at 1280x720 | `PACKAGED_RC=0` | pak mounted; `/Game/Maps/BiellaGameplayMap` loaded; same runtime readiness signals; Vulkan swapchain created; `LogExit: Exiting.` |

The NullRHI capture is [D01-47-package-runtime.log](D01-47-package-runtime.log)
with SHA256 `f6a2dbf7e96664b918dfe1835b7147fa781ef97ed71105f94cee95b162bff5e2`.
The rendered Vulkan capture is
[D01-47-package-vulkan-runtime.log](D01-47-package-vulkan-runtime.log); its
SHA256 is `5c9419e005a88b834dc399144d295f7623979b5974bc0596e92b63b02fc5ff8c`.

## Qualification boundary

This task establishes that the recorded D01-46 Linux package launches from a
clean extraction and reaches the packaged Demo 01 map, runtime world, HUD and
controller readiness paths. It does not execute the end-to-end combat/restart
acceptance reserved for D01-48, or publication reserved for D01-49/50.

Known authored navigation-registration/crowd warnings remain in the runtime
logs. The Vulkan run also retains the known shutdown `Found 1 unfreed
allocations!` diagnostic seen in predecessor Vulkan evidence. No runtime
`Error`, `Fatal`, assertion, segmentation fault, or unhandled-exception
signature was observed, and both process exit codes were zero.

Protected project-state files and the production task metadata were not edited;
D01-48 and later tasks were not advanced.
