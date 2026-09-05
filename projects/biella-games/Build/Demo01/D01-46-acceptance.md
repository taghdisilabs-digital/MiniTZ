# D01-46 — Package acceptance

Status: `COMPLETE`

## Package

- Artifact: `/root/biella/artifacts/games/D01-46/BiellaGames-Linux-x64-D01-46.tar.zst`
- SHA256: `c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8`
- Archive size: `297346213` bytes
- Package format: UAT `BuildCookRun` Linux archive with `BiellaGames-Linux.pak`
- Target: `BiellaGames` / `Linux` / `Development` / `Game` / `x64`

## Evidence

- Build: `D01-46-build-source-final13.log` — source target build succeeded and produced `Binaries/Linux/BiellaGames`.
- Receipt: `Binaries/Linux/BiellaGames.target` — matching Linux Development Game receipt with launch path `$(ProjectDir)/Binaries/Linux/BiellaGames`.
- Cook: `D01-46-cook-legacy.log` — `565/565` packages processed, `530` cooked, `0` errors.
- Package: `D01-46-package-uat-canonical.log` — UAT staging, pak creation, archive, and `ExitCode=0`.
- Smoke: `D01-46-package-smoke.log` — exact archived layout mounted the pak, reached `GAME_INSTANCE_READY`, `WORLD_READY`, and `HUD_READY`, then exited with `SMOKE_RC=0` and no error/fatal entries.

Protected project-state and production metadata were not edited. D01-47 and later tasks were not advanced.
