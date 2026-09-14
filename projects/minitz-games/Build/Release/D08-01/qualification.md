# D08-01 delivery qualification

**CONTINUE — Win64 Shipping release candidate remains unqualified.**

Linux Development diagnostic lineage passed for package `fbb3a496dd5b4cbcf103354d44e0f5b3c554c90e8d2d459ef628579abd0eee4c`.
The exact archive is `/root/biella/artifacts/games/D08-01/BiellaGames-Linux-Development-D08-01-probe-fix.tar.zst` (SHA-256 `7ceb504983c6a5609fa4d6da77531388d1388d5f6ccf50b54d6bfd763bf451d0`).

An isolated cook and UAT archive readback bind editable source/config/content and the native binary. The installer preserved the exact old version, rejected missing content and incompatible metadata, and activated the verified current version atomically.

Outside-editor package processes exercised core gameplay twice, population/pressure, world interactions, cooked content/version rejection, audio/VFX, UI/settings and watched/skipped cinematic handoff. Three separate native processes exercised legacy settings, preference write and preference reconstruction after teardown.

Each run retains commands, final logs, native PID/resource samples and feature-derived raw evidence. See qualification.json for exact hashes, diagnostics and limits. D07 evidence is preserved with its original scope.

The Debian diagnostic installer `/root/biella/artifacts/games/D08-01/biella-games-d08-diagnostic_0.1.0-demo01+d08.fbb3a496dd5b_amd64.deb` passed container/control and complete payload extraction readback (SHA-256 `7243b21834b40ca17356510e2161a774a27eb931849a3d9321d7632197ecbcab`). This is installer assembly evidence, not native dpkg lifecycle or Windows qualification.

## Remaining criterion

Accepted Win64 Shipping distributable and exact Windows old-build/update/native-play qualification.

Route to an actually verified Windows UE 5.8.2 build/play Resource with adequate storage and DX12 SM6 GPU, then execute the retained Win64 UBT/UAT package recipe and native qualification on its exact package bytes.

## Known limits

- Linux Vulkan on one shared L40S host, 1280x720 Xvfb; Development diagnostic automation is compiled out of Shipping.
- D07 measurements retain their original editor binary and all recorded risks. They are not package-specific Win64 performance acceptance.
- Approved quantitative hardware/frame-time/input-latency budgets remain UNKNOWN; raw hitches and warnings are retained, not converted into a budget pass.
- Audio evidence decodes actual runtime mixer captures through a dummy output device; physical speaker/device fidelity remains unmeasured.
- No world SaveGame system is implemented. This lineage exercises the actual supported GameUserSettings file and new custom preferences.
- The retained D03 file contains runtime-created default resolution/window settings. Arbitrary old customized settings or future schema migrations are not established.
- Installer hashes detect byte mismatch; they do not provide publisher authentication or a store/launcher/signing protocol.
- Debian assembly/extraction matches the same Linux diagnostic payload. Dependencies derive from Ubuntu 24.04 ELF metadata; native dpkg install/update/uninstall and other Linux distributions are unqualified.
- Generated runtime captures remain evidence, not newly accepted art content.

Exact canonical local archive retained. Auto Feeder owns GitHub/Drive continuity publication from the task commit. No Win64 package, remote delivery or remote readback is claimed.
