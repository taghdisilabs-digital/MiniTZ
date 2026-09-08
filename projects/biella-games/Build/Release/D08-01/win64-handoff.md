# D08-01 Win64 execution handoff

Status: `PREPARED_NOT_EXECUTED`; required resource classification: `REQUIRES_OTHER_RESOURCE`.

The accepted deliverable is Windows PC x64, UE 5.8.2, DX12/SM6, with a Shipping distributable. The Linux Development archive and its tests establish only the recorded diagnostic lineage. No store, launcher, signing service or remote package destination has been selected by this handoff.

`resources/routing.json` records the actual routing result. `D08-01-resource-observation.json` records the unsuitable known Windows node. Do not reinstall its already registered Visual Studio/SDK or repeat launch/install attempts without a changed resource boundary. The smallest next action is to acquire/route to an actually compatible Windows build/play Resource, then inspect its exact Unreal installation, SDK validity, free storage and hardware GPU immediately before execution.

The newer canonical `windows-setup-observation.json` records a real compiler/link/run probe PASS at 2026-09-08 08:47 UTC and verified setup/build scripts installed at `C:\ProgramData\Biella\Win64Build`. It still reports no discovered Unreal 5.8.2, no UBT SDK validation, 3,446,833,152 bytes free and Microsoft remote/basic display adapters. The script digests match repository `ops/workstation/setup-unreal-win64.ps1` and `build-unreal-win64.ps1`; `resources/routing.json` binds that readback. Reuse this setup work. Use actually available authorized Unreal media or a preinstalled exact engine on adequate storage and a compatible GPU resource; no installer media or custom engine path has been observed here.

Use the committed Project source and `source-build-manifest.json` material-input hashes. Preserve the Linux proof. Windows builds produce their own source/build/cook/package identities and receipts; they cannot reuse Linux binary hashes or declare Linux evidence to be Windows evidence.

The following PowerShell command forms use explicit paths supplied by the observed Resource. `$EngineRoot` is the directory containing `Engine`; `$ProjectFile` is the exact editable `BiellaGames.uproject`; `$ArchiveDirectory` is a fresh task-scoped local output directory on that Resource. These are inputs, not claims that paths/resources exist. Validate `Engine/Build/Build.version` as 5.8.2 first.

```powershell
& "$EngineRoot\Engine\Build\BatchFiles\Build.bat" -Mode=ValidatePlatforms -Platforms=Win64 -OutputSDKs
```

Require the actual `##PlatformValidate: Win64 VALID` marker with its SDK version. The locally inspected UE `ValidatePlatformsMode.cs` returns zero even for INVALID, so exit code alone is insufficient.

```powershell
& "$EngineRoot\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun `
  "-project=$ProjectFile" -noP4 -unattended -platform=Win64 `
  -clientconfig=Development -build -cook -stage -pak -iostore `
  -archive "-archivedirectory=$ArchiveDirectory"
```

Retain full UBT/UAT diagnostics and exact editor/game receipts, cooked file set, source/config/content hashes and archive extraction readback. Use the resulting Development package for native diagnostic evidence. Build a separate fresh Shipping archive with `-clientconfig=Shipping` and its own identities; the Development automation probe is intentionally excluded from Shipping.

Launch the actual packaged Windows entry point outside the editor on a clean per-user state with source/DDC absent. Observe actual DX12/SM6, input/player/camera, gameplay state, rivals/infected/pressure, current environment interactions, audio/VFX, UI and watched/skipped cinematic handoff, process teardown, content diagnostics and frame/resource evidence. Shipping acceptance requires real play evidence on its exact bytes; a Development automation pass or compile cannot qualify Shipping.

For the Windows update lineage, preserve an actual runnable old Windows package and its runtime-created per-user settings, verify an exact full update, launch the new package, and prove supported settings reconstruction across separate native processes. Exercise incomplete/mixed/incompatible update rejection while retaining the old runnable version. Do not install the Linux update base on Windows. There is currently no world SaveGame implementation to claim as migrated; arbitrary future schema compatibility is unproved.

The portable Python installer in `tests/run_d08_01_release.py` validates byte membership and PE/ELF platform identity and retains old versions before atomic activation. Its Windows locking/path branch still requires execution on the real Windows Resource. The native launch driver and `verify_d08_01_release.py` are explicitly Linux diagnostic tooling. The D08 Development settings probe also checks the Linux sandbox's `/tmp/state/user/` path; adapt that assertion to the actually isolated Windows per-user path along with the native driver. Preserve feature checks without making diagnostic automation a Shipping prerequisite.

The configured `package.installer.windows` capability supplies NSIS (`makensis -V2`) for installer assembly once the exact Win64 payload exists. Author its task-local `.nsi` from that manifest, preserve per-user settings, and verify the setup PE format and extracted payload digests. NSIS on Linux can assemble a Windows installer; it cannot produce the missing Win64 Unreal payload or establish Windows install/play/update/uninstall behavior. Preserve large payloads as separate installation data if the NSIS container limit requires it. The Linux diagnostic `.deb` uses the separate task-local `tests/build_d08_01_installer.py` recipe and does not satisfy this Windows criterion.

Publish only to the canonical destination actually supplied by Project/task authority, with exact remote identity and readback. Auto Feeder owns routine GitHub/Drive continuity publication from exact committed task bytes. No remote delivery is claimed here.
