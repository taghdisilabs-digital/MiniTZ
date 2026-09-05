# D01-46 packaging checkpoint

Status: `COMPLETE` — current Linux playable build is packaged and smoke-validated.

Source revision: local D01-46 task commit (see acceptance evidence and git history)
Engine: `/opt/unreal/UE_5.8.2`
Target: `Linux x64 Development`

## Evidence

- Source game-target build succeeded with UE 5.8.2 and produced `Binaries/Linux/BiellaGames` plus the matching receipt. Log: `D01-46-build-source-final13.log`.
- Cook completed for the current project with `565/565` packages processed, `530` cooked, and `0` errors. Log: `D01-46-cook-legacy.log`.
- UAT `BuildCookRun` staged the current executable and cooked content, created `BiellaGames-Linux.pak`, archived the Linux package, and exited with `ExitCode=0`. Log: `D01-46-package-uat-canonical.log`.
- Final archive: `/root/biella/artifacts/games/D01-46/BiellaGames-Linux-x64-D01-46.tar.zst`; SHA256 `c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8`.
- Exact-package smoke validation mounted the pak, reached the Demo 01 game instance/world/HUD readiness signals, exited with `SMOKE_RC=0`, and reported no error/fatal entries. Evidence: `D01-46-package-smoke.log`.

## Resume condition

The current package and digest are recorded in `D01-46-acceptance.md`.

Protected task/state/production metadata was not edited. D01-47 and later tasks were not advanced.
