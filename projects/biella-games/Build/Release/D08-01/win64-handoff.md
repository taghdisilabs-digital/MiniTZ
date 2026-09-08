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

The configured `package.installer.windows` capability supplies NSIS (`makensis -V2`). The editable `tests/build_d08_01_windows_installer.py` now generates the task-local `.nsi` from an exact Win64 manifest, rejects Linux bytes, and verifies the setup PE format and complete extracted payload digests. It installs each identity under its own per-user package directory, rejects an existing version without overwriting it, and generates an uninstaller with explicit file membership. It does not install UE prerequisites, alter saves/settings, configure a store, or replace the portable D08 update qualifier. Its embedded-data limit is 1.8 billion bytes; larger actual payloads require a separately qualified external-data recipe rather than truncation.

`tool-tests/nsis-04/validation.json` records successful assembly/extraction of two explicitly labeled **INSTALLER_TEST_FIXTURE_NOT_GAME** payloads, including native x64 PE format, Unicode/dollar-sign paths, and rejection of Linux input, corrupted bytes, altered identity and fixture input without opt-in. The small fixture was built with the existing local LLVM tools; this is not Unreal compilation and did not repeat the Windows compiler setup. The NSIS wrapper is PE32 x86; its contained fixture is PE32+ x64. Neither fixture is a game package or an update compatibility result.

Native installer install/launch/uninstall checks are prepared in `tests/test_d08_01_windows_installer.ps1`, bound by `tool-tests/nsis-04/native-plan.json`. They remain **NOT_EXECUTED**: three bounded Windows connector reads returned HTTP 504. The native test uses only the explicit fixture installations and separate fixture state, never real player saves. After connector recovery, transfer the two exact setup artifacts, `native-plan.json` and the script to a fresh task-local directory on the observed Windows node, compare their SHA-256 values with the plan, execute the script with `-FixtureDirectory` set to that directory, and retrieve/verify `native-validation.json`. This still cannot qualify the missing game payload.

`resources/windows-route-review.json` retains the current empty Win64 route, official Modal/Saturn image-capability findings and connector failures. No newly compatible Windows build/play Resource was observed. Preserve the original Linux diagnostic qualification and its resource receipt: the new review supplements it without changing those accepted bytes. The Linux diagnostic `.deb` uses `tests/build_d08_01_installer.py` and does not satisfy the Windows criterion.

Publish only to the canonical destination actually supplied by Project/task authority, with exact remote identity and readback. Auto Feeder owns routine GitHub/Drive continuity publication from exact committed task bytes. No remote delivery is claimed here.
