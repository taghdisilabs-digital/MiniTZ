# BU-02 — Website Source Classification Using the Migration Firewall

Task: `WEB-BU-02`
Classification date: `2026-09-01`
Scope: exactly the accessible website-relevant source groups and manifest slots `01`–`60` inventoried by `WEB-BU-01`.

## Classification contract

BU-02 applies the existing Biella migration/firewall separation to Website source admission. It does **not** create another firewall, activate historical material, select visual masters, define public copy, or begin BU-03/BU-04.

Exactly one Website class is assigned to each BU-01 inventory item:

- `CANON` — current active authority or accepted control/source record for its stated Website purpose.
- `CANDIDATE` — relevant source that may inform a later Website canon/selection task but is not active canon for that output yet.
- `SUPERSEDED` — retained source replaced by a newer current authority.
- `DUPLICATE` — proven duplicate; never a second active authority.
- `HISTORICAL` — provenance/reference only; inactive for current Website implementation.
- `UNRELATED` — accessible source outside the Website corpus.
- `MISSING` — registered/required source whose exact source bytes or qualified source object are not available.

A `MISSING` visual slot does not revoke its manifest registration. It means the exact bytes required for selection/migration are unresolved and may not be guessed from UUID/generated images.

## Reobserved current source snapshot

- Engine `main`: commit `ebe8cec74008704321dedb9c8763c5dfaaccd94c`, tree `564c3573b0aa08bd3b54ef047f318c407fc9997f`.
- Website branch: commit `383393e8f8feaeed8f83d5e5512a204a12a12ca3`, tree `e22295189bdc917976d75e20fbde65fa3566a3b1`.
- Game `main`: commit `5f4304db91fc214138fb3b462545681db8685b20`, tree `c375a14c5ac93238737811d93d9197c6d5e4df41`.
- BU-01 GitHub inventory: `website/content/BU01_FULL_DRIVE_GITHUB_SOURCE_INVENTORY.md`, blob `8e586739982774b2006856a767eaf2440a878c9b`.
- BU-01 Drive inventory: `BU01_FULL_DRIVE_GITHUB_SOURCE_INVENTORY`, ID `14-_l459jzthNRGV2ILljbC90ioBKw9wX2sX4Fnpp4FY`.
- Canonical Website Drive root: `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V`.
- Canonical Website asset manifest Drive ID: `11skZ-wCs4fX2dG2Q-OzXAjcFufFX33-8`.

## Source-group classification

| Inventoried source | Class | Reason / provenance |
|---|---|---|
| Engine `main` current source | `CANON` | Current Engine program/state upstream; commit/tree above. |
| `docs/biellawebsite/MINITZ_UNIVERSE_36_TASK_MASTER_PACK.md` | `CANON` | Current approved Option C program; blob `421535f54c25f1383b5b7e62898eb3b6e9c28659`. |
| `docs/biellawebsite/MINITZ_UNIVERSE_36x51_ENGINE_CROSSMAP.md` | `CANON` | Current Engine/Website ownership map; blob `38cf0a4e3e860edbb980436b7da904689105abc9`. |
| `docs/biellawebsite/MINITZ_WEBSITE_ASSET_MANIFEST.md` GitHub record | `CANON` | Active 60-slot control record; blob `4704e5b0792835dd867782afe2e6ebbb1c7cdac8`. |
| Website branch/application source | `CANON` | Current Website project source; branch commit/tree above. This does not imply deployment completion. |
| `website/content/website-visual-assets.csv` | `CANON` | Current slot/status ledger for visual slots 01–50; blob `9b06346d688bf4a8fa5fe0785167e83f357a5ac8`. |
| `website/content/asset-resolution.json` | `CANON` | Current exact visual-source resolution state: `SOURCE_BYTES_UNRESOLVED`, `0/50` exact Drive filename matches; blob `eee8a2fb386d22ec465b94546b74967bf092ca38`. |
| `website/content/game-runtime-media.json` | `CANON` | Current Website admission record for real Game runtime media; zero published items until provenance gate passes; blob `3eb4098ddcf631edc1fca7f68446dd1748f57584`. |
| `patrickminitz-web/biella-games` current `main` | `CANON` | Authoritative Game upstream for any future BU-16 runtime-media provenance; commit/tree above. |
| `docs/brand/preproduction/` | `CANDIDATE` | Relevant visual/brand production source, but BU-03 owns actual visual-master selection; tree `448899af9e58f3c3dab72129b160a67f2f41705a`. |
| `docs/business/` | `CANDIDATE` | Relevant product/narrative source, but BU-04 owns current public content/story canon; tree `d00e7583dc667a68ca2426d7eb02f71dfab20683`. |
| `docs/integration/MINITZ_POST_P4_06_GAME_WEBSITE_MAP.md` | `HISTORICAL` | Integration reference from an older post-P4-06 framing; not current execution authority; blob `cf8a37861458c41e68dbb6fb00a67e95d191e314`. |
| Website-branch `docs/project-state/` snapshot | `SUPERSEDED` | Older than current Engine `main`; may not define current implementation truth; tree `5faa354d82ca172d21204784993a24b36ff1381d`. |
| Drive `MINITZ_WEBSITE` root | `CANON` | Active Website Drive namespace; folder `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V`. |
| Drive `10_DOCUMENTATION_TOOLS` | `CANON` | Active document-spec lane; folder `1NzYPCnF4VysGHWc7YPkKBz36ad6Vcqns`. |
| Drive `20_APPLICATION_WORKSPACE` | `CANON` | Active Website application continuity lane; folder `1-PUKv3tflWzCEHSCJ1bl2o6Dmv0RXsTH`. |
| Drive `30_VISUAL_MASTERS` | `CANON` | Active visual-resolution/control lane; does not promote unresolved image bytes; folder `1xfx0_Tcc4hw_sqA_T-2auH6yjSQPNBad`. |
| Drive `40_GAME_RUNTIME_MEDIA` | `CANON` | Active runtime-media admission lane; current accepted-media count remains zero; folder `1WMPyb3Jr0shr5x_5IRzUic-_MH1svrWq`. |
| Drive `90_ARCHIVE` | `HISTORICAL` | Archive/superseded Website material; provenance only; folder `11ndIoYHz6bM9xZnbp9Usd6xealzvR09A`. |
| Drive `MINITZ_WEBSITE_ASSET_MANIFEST.md` | `CANON` | Canonical Drive-side 60-slot control index; file `11skZ-wCs4fX2dG2Q-OzXAjcFufFX33-8`. |
| Drive `BU07_WEBSITE_APPLICATION_WORKSPACE_STATE` | `CANON` | Current source/CI continuity record; explicitly preserves blocked preview state; file `1LGxsPaDip4fRYFb6bgXTXb9tH1kVkTnGPZc0POoRmeA`. |
| Drive `WEBSITE_VISUAL_MASTER_RESOLUTION_01_50` | `CANON` | Current durable proof of `0/50` verified visual masters and no guessed promotion; file `1tZs8oWUfXB9BOyYQe_-DaTk8tGcQpHLGTrwBVg4rq0k`. |
| Drive `BU16_GAME_RUNTIME_MEDIA_CONSUMPTION_LANE` | `CANON` | Current owner-directed runtime-media admission rule; accepted count `0`; file `16IT5vdWP73Ya4crV4K0HK_RdyMT-oIZAP1rgj0aEYtU`. |
| Archived Drive Option-C master pack | `SUPERSEDED` | Current GitHub `main` master pack is higher-current where content differs; file `1F5rxWBQ3wzbvW5vohTvhw5cFc0sToQ_-M-dB2Fvu7zo`. |
| Archived Drive 36×51 cross-map | `SUPERSEDED` | Current GitHub `main` cross-map is higher-current where content differs; file `15TsY-LRFm3MoT7IlS-TpCsGON8eU5aRCmAuEwsk1llM`. |
| BU-01 durable inventory result | `CANON` | Immediate predecessor defining BU-02's accessible corpus; GitHub blob `8e586739982774b2006856a767eaf2440a878c9b`, Drive `14-_l459jzthNRGV2ILljbC90ioBKw9wX2sX4Fnpp4FY`. |

## Manifest slots 01–60

Shared provenance for slots `01`–`50`: canonical manifest Drive `11skZ-wCs4fX2dG2Q-OzXAjcFufFX33-8`; GitHub visual ledger blob `9b06346d688bf4a8fa5fe0785167e83f357a5ac8`; resolution blob `eee8a2fb386d22ec465b94546b74967bf092ca38`; Drive resolution record `1tZs8oWUfXB9BOyYQe_-DaTk8tGcQpHLGTrwBVg4rq0k`. All fifty are individually `MISSING` at the exact-source-byte level because the current audit proves `0/50` exact Drive filename matches and no digest-qualified source promotion.

| Slot | Class | Slot | Class | Slot | Class | Slot | Class | Slot | Class |
|---:|---|---:|---|---:|---|---:|---|---:|---|
| 01 | `MISSING` | 11 | `MISSING` | 21 | `MISSING` | 31 | `MISSING` | 41 | `MISSING` |
| 02 | `MISSING` | 12 | `MISSING` | 22 | `MISSING` | 32 | `MISSING` | 42 | `MISSING` |
| 03 | `MISSING` | 13 | `MISSING` | 23 | `MISSING` | 33 | `MISSING` | 43 | `MISSING` |
| 04 | `MISSING` | 14 | `MISSING` | 24 | `MISSING` | 34 | `MISSING` | 44 | `MISSING` |
| 05 | `MISSING` | 15 | `MISSING` | 25 | `MISSING` | 35 | `MISSING` | 45 | `MISSING` |
| 06 | `MISSING` | 16 | `MISSING` | 26 | `MISSING` | 36 | `MISSING` | 46 | `MISSING` |
| 07 | `MISSING` | 17 | `MISSING` | 27 | `MISSING` | 37 | `MISSING` | 47 | `MISSING` |
| 08 | `MISSING` | 18 | `MISSING` | 28 | `MISSING` | 38 | `MISSING` | 48 | `MISSING` |
| 09 | `MISSING` | 19 | `MISSING` | 29 | `MISSING` | 39 | `MISSING` | 49 | `MISSING` |
| 10 | `MISSING` | 20 | `MISSING` | 30 | `MISSING` | 40 | `MISSING` | 50 | `MISSING` |

Slots `51`–`60` are `CANON`: the canonical manifest marks each `DOC_FINAL`, and BU-01 records exact Drive IDs plus GitHub blobs. Cross-store byte equality is not inferred.

| Slot | Class | Drive ID | GitHub blob |
|---:|---|---|---|
| 51 | `CANON` | `1Go9pe7gUdcuRiq068h2icpZGHO7fJOeo` | `ecd78aec6207f6e68e0df69a3794352d7554ffe2` |
| 52 | `CANON` | `19Crm4lsePhUPbd6QEPuprBCsu3W0cj5S` | `ff859f72932388dff8a658e425162ae37f495d39` |
| 53 | `CANON` | `1x0uMhTOuDWb_2A_bzmsGkLeCREt1khzH` | `18f0617b4879011d7f0c5fe5b9bef46528d1f107` |
| 54 | `CANON` | `1OOMrvq_5cvItoG8vTOV9T_bA4iDS8k_e` | `5caa27073d0381b11862e990e7504ba1e5630114` |
| 55 | `CANON` | `1vIs_8P9fqTkI5StrlM5HG4OVRla_YObz` | `226195a66cd3346252f5b1d62a0dc81674eb5b5d` |
| 56 | `CANON` | `1q2BBst4OzQg2uxCaxtkQNOzJz1-Xt9EV` | `7d8d56138bd758907389f4fb394b96722f9ac4ab` |
| 57 | `CANON` | `1eRWXicPCyYqdCMI4fOJPVSy-5fgwx0ZM` | `6fbc0a4723aa0e18659b970827a2e3001d8caeb2` |
| 58 | `CANON` | `1Bn2ALGuzTsTWmdQsx0wWex73zxk5VifS` | `9736e825c2ad328942f797f32800565b34a9ca75` |
| 59 | `CANON` | `1FsgccrcOkE2ZZ_e4q8qEXO-o74enZ-PQ` | `dd1a8720269cdb7015296ef05d73b6abc71c26b2` |
| 60 | `CANON` | `1xl-L5mHrxplVa453Q1YP2K-hH1FMQfyh` | `07d89edfa86c002080dc39be4cba5e424854e79b` |

## Existing explicit superseded visual names

The canonical manifest already excludes these from Website implementation; they remain `SUPERSEDED` and are not promoted here: `google_drive_task_archive_hud.png`, `nvidia_compute_control_hud.png`, `openai_developers_workflow_dashboard.png`, `web_search_intelligence_hud_dashboard.png`, `neon_ai_image_pipeline_dashboard.png`, `futuristic_visualization_studio_dashboard.png`, `neon_task_execution_board.png`, `prompt_pack_organizer_dashboard.png`, `asset_progress_tracker_hud_dashboard.png`, `unified_ai_tool_hub_dashboard.png`.

## Validation result

- BU-01 source groups/control records: `26/26` classified exactly once.
- Manifest slots: `60/60` classified exactly once.
- Total BU-01 classification items: `86/86`.
- Totals: `CANON=29`, `CANDIDATE=2`, `SUPERSEDED=3`, `DUPLICATE=0`, `HISTORICAL=2`, `UNRELATED=0`, `MISSING=50`.
- No `DUPLICATE` is asserted because BU-01 did not prove exact duplicate identity for separate source objects.
- No `UNRELATED` is asserted because BU-01 already bounded its inventory to website-relevant sources.
- No raw history, unresolved image bytes, UUID/generated-image candidates, Website deployment state, Game runtime claims, or stale project-state snapshots were promoted.

## Next dependency

`WEB-BU-03` and `WEB-BU-04` may become `READY` only after this BU-02 result is durably published and the canonical ledger marks `WEB-BU-02` `COMPLETE`. Neither task is started here.
