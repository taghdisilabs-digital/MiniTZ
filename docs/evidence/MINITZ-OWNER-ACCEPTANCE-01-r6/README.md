# MiniTZ OS owner acceptance — revision 6

The current artifact passes the predecessor's nonboot qualification, and a newly supplied external boot receipt matches its exact source, image and path. Final daily-operation behavior and explicit owner acceptance remain outstanding. This packet is evidence only; it does not complete or advance the Task Program.

## Exact artifact for review

- Source SHA-256: `07fc3844ab80c41d8bc6e4825386a3491a8de0347428b56eeabb2cc838d781e9` (195 source files).
- Image SHA-256: `2353fbe2c932c43120938bcd27ca103f231825f2f978741078e9ce12f73a1080`.
- Image path: `/root/attached-storage/minitz-os-sandbox/output/images/MiniTZ-OS-07fc3844ab80c41d.raw`.
- Image size: 3,758,096,384 bytes; raw GPT disk with EFI and ext4, verified against the current build and validation records.
- Current task: `MINITZ-OWNER-ACCEPTANCE-01`, revision 6, digest `21dd149a0495522c194507c4e047725bb1526e909a2973926f91a8fc0b34b8e5`.

The [input readback](readback.json) checks current source, image bytes, records, format signatures and reused evidence. The [predecessor report](../MINITZ-SYSTEM-QUALIFY-01.validation.json) describes the completed qualification. Evidence-only additions here do not change the packaged source identity. Two [fixture checks](checks.json) passed for rejection of model acceptance and tampered boot logs; these are software checks, not human acceptance.

## Newly received boot evidence

During this readback, `/root/attached-storage/minitz-os-sandbox/state/image-build/runtime-boot.json` appeared with the method `EXTERNAL_CLEAN_TARGET_OWNER_AUTHORIZED`. Its 48,413-byte external log matches SHA-256 `37264bc8dfbef6465d795b66faf1c343e7b122823d7cbe0ffc53f08de81136ea` and contains the exact source boot marker. The image was not booted by this executor and must not be booted again merely to repeat this proof. The receipt's method label records authorization provenance; it grants no new target-control permission.

The log records MiniTZ source verification, a registry containing 25 providers, a dashboard with 10 sections and 8 capabilities, and 4 doctor checks with overall availability **Needs Attention**. The source boot hook confirms these are registry/dashboard/diagnostic checks. They do not demonstrate actual local AI/provider execution, desktop interaction, or a full daily-use workflow.

## What the owner can assess now

| Area | Verified evidence | Remaining runtime scope |
| --- | --- | --- |
| Clean installation and usability | Signed full-source installation, idempotent reapply, seven CLI calls in a disposable Ubuntu 26.04 target; exact-image external boot and basic product checks | Observe desktop and ordinary operation on the booted target |
| Capabilities and local AI/resources | Capability/routing/integration checks and unchanged implementation bindings | Execute required capabilities with actual resources on the clean target; no live local-model readiness is claimed |
| Durable memory and task continuity | Signed install/recovery preserves source and task/checkpoint mechanisms; prior integration evidence reused only for unchanged files | Observe task/memory persistence during real target operation and authorized recovery |
| Browser/computer work | Real Chromium local-fixture navigation, typing, selection, click, upload/download and screenshot behavior; fixture integration evidence | Observe the installed image's browser/computer workflow |
| Updates and recovery | Signed idempotent reapply and fresh-process recovery | Booted-target update/recovery behavior; machine power-cycle proof is absent |
| Owner control | Existing acceptance mechanism binds source SHA-256, image SHA-256 and exact path; model completion cannot supply owner acceptance | Explicit human decision after runtime evidence; any lifecycle action requires its own owner command |

The disposable offline target reported **Needs Attention** for absent task authority and **Needs Setup** for absent qualification/resources. Live desktop, local AI, VPN enforcement and machine restart were not exercised by that qualification. These limits remain visible in [nonboot observations](../MINITZ-SYSTEM-QUALIFY-01-r7/nonboot-observations.json). The new boot log adds startup proof; it does not establish those remaining workflows.

## Next authorized boundary

The smallest next action is to obtain a connection/reference for the external Linux target that produced the boot log, or its existing workflow evidence. Its current availability is unproven. The supplied boot receipt contains a log reference but no target connection or workflow handoff. Routine setup and testing remain executor work once that input is available. Preserve the qualified image and verified boot proof, capture the remaining runtime observations, then request final artifact acceptance.

Any new boot remains subject to [the shared policy](../../../ops/workstation/AGENTS.md), `RAW_IMAGE_BOOT_REQUIRES_EXPLICIT_OWNER_COMMAND`: “A .raw MiniTZ image must never be booted, emulated, or started unless the current owner instruction explicitly commands booting that image.” The current task separately requires: “Only an explicit owner acceptance action may complete this task.” No new boot is needed merely to reproduce the receipt now present.

After actual owner acceptance, the canonical writer must retain the owner's exact instruction and bind `OWNER_ACCEPTED_SOURCE_SHA256`, `OWNER_ACCEPTED_IMAGE_SHA256` and `OWNER_ACCEPTED_IMAGE_PATH` to the identities above. Revalidate the current source/image/path before recording that decision. No accepted markers or human receipt have been manufactured in this packet.

The existing production `accept` CLI stops production and selects the successor, including with `--no-resume`; it must not be invoked under this turn's no-lifecycle/no-advance boundary. This task adds no new acceptance mechanism or task authority.

## Reproduce the material readback

From the canonical repository, run:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B docs/evidence/MINITZ-OWNER-ACCEPTANCE-01-r6/verify_acceptance_inputs.py
```

This reads the exact revision-6 inputs and prints observations. It never boots, rebuilds, substitutes, accepts or advances anything. A changed task/program/source/image causes the pinned readback to fail instead of reusing stale evidence.
