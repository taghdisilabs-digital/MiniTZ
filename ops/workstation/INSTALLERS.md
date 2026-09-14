# Installer assembly — Linux Debian and Windows

Scope: `INSTALLER_ASSEMBLY_ONLY`. These are free local deterministic tools for
wrapping an already-built, target-correct application payload. They are not
an OS installer, Unreal cross-compiler, new scheduler or game qualification gate.

## Available capabilities

| Capability | Provider / command | Output |
| --- | --- | --- |
| `package.installer.debian` | `dpkg-deb` | Debian `.deb` |
| `package.installer.windows` | NSIS / `makensis` | Windows setup `.exe` |

Discover through the existing router:

```sh
minitz resource route package.installer.debian
minitz resource route package.installer.windows
```

On Debian/Ubuntu builder hosts, run `ops/workstation/install-package-tools.sh`
only when tools are absent. It installs missing `dpkg`, `nsis`, `nsis-common`
without desktop packages, broad upgrades, model changes or service controls.
No extra account, cloud subscription or login is required for installer assembly.

## Execution instructions

For Debian, stage the accepted Linux payload and actual Project metadata in a
package tree with `DEBIAN/control`, preserving executable bits and dependencies.
Use `dpkg-deb --root-owner-group --build` with the real staged tree and output
paths. Read back package metadata with `dpkg-deb --info` and extract with
`dpkg-deb --extract`; compare every required payload byte/digest. Package runtime
dependencies are determined from the actual binary and target Debian version,
never from an invented compatibility promise.

For Windows, author the task-local `.nsi` from the real Windows build manifest
and compile it with `makensis -V2`. NSIS can create Windows installers on Linux
without Windows or Wine; it does not convert Linux ELF binaries/cooked content
into Windows PE game binaries. Use an already built Win64 payload. Verify the
installer PE signature and extracted payload bytes; real Windows install,
launch, update and uninstall behavior still require target execution evidence.
NSIS embedded installers have a size ceiling; large game payloads can remain
separate installation data rather than being silently truncated. The 3.8-GB
Drive transfer-part policy is separate from installer container limits.

Keep product/version/entrypoint/dependency choices in the originating Project.
Preserve game saves/settings during install/update/uninstall. No authentication,
OS image, desktop, Steam configuration, automatic restart or driver changes are
introduced by adding these capabilities. Installer-tool tests use explicitly
labeled fixtures and never imply game release acceptance.

## Primary tool references
- https://manpages.debian.org/trixie/dpkg/dpkg-deb.1.en.html
- https://nsis.sourceforge.io/Features
- https://nsis.sourceforge.io/Docs/Chapter3.html
- https://nsis.sourceforge.io/License
