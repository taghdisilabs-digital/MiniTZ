# Windows Unreal build setup

Scope: existing Windows Resource setup and command-line build/cook/package; no OS replacement, desktop, virtual machine, new scheduler or production service.

## Scripts
- `ops/workstation/setup-unreal-win64.ps1`: discover existing Visual Studio C++ tools, compile/link/run a real Win32 probe, discover the requested Unreal version, and require the actual UBT Win64 VALID marker. Process exit zero alone cannot qualify the SDK. Runs return a durable setup-result.json; missing engine returns INCOMPLETE, not readiness.
- `ops/workstation/build-unreal-win64.ps1`: use supplied real EngineRoot, ProjectFile, ArchiveDirectory, RequiredEngineVersion and Development/Shipping Configuration. Invoke UAT BuildCookRun for Win64, preserve logs and exact package file digests. A created package never implies gameplay/release qualification.

## Setup on the observed Windows node
The scripts are installed at `C:\ProgramData\MiniTZ\Win64Build`. This is tool/runtime storage, not a duplicate Project checkout. Run the following only on that Windows node:

```powershell
& 'C:\ProgramData\MiniTZ\Win64Build\setup-unreal-win64.ps1' -RequiredEngineVersion '5.8.2' -InstallMissing
```

Existing C++ tools are reused without reinstalling. To install missing tools, the script accepts the actual authorized local BuildToolsInstaller. To install Unreal, it accepts an authorized local Unreal Engine MSI and explicit EngineRoot; no download URL, license entitlement, installer file or destination is fabricated. MSI installation is silent with no automatic restart. Offline MSI access depends on Epic-provided entitlement/media; a preinstalled matching engine is equally valid. Choose actual suitable storage before a large engine installation, not a repeated attempt against the unchanged small browser node.

## Observed boundary
Read the task-scoped `Build/Release/D08-01/windows-setup-observation.json` in the Games Project. Windows native C++ compile/link/run passed. Unreal 5.8.2 was not found in the checked locations, Win64 UBT SDK validation was not possible, and only about 3.45 GB was free. Graphics adapters were Microsoft remote/basic display. This observation does not establish Unreal, Win64 package, or native game-play readiness. No compiler reinstall, new Windows machine, paid resource, disk expansion, GPU or Unreal download occurred.

## Continuation
This is required D08 setup work inside the existing task, not a second queue. Keep Linux work and accepted game evidence intact. Record the exact missing Windows engine/media/storage/runtime boundary and continue independent work; do not repeat unchanged probes, reopen predecessors, or use NSIS as a compiler. Once a compatible Windows engine exists, run the build script with observed real paths and preserve its original receipts for D15/D16 reuse. Its parameters are required inputs, not executable placeholders.

Linux Debian packaging remains dpkg-deb; Windows installer wrapping remains NSIS after target-correct game binaries exist. Existing per-task GitHub and five-task/3.8-GB Drive publication remain unchanged.

## References
- https://dev.epicgames.com/documentation/en-us/unreal-engine/offline-installer-of-unreal-engine
- https://learn.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio
