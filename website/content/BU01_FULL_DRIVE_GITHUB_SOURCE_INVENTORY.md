# BU-01 — Full Drive + GitHub Website Source Inventory

Task: `WEB-BU-01`
Observed UTC: `2026-09-01T15:20:41Z`
Scope: accessible website-relevant current GitHub + canonical Drive sources and manifest slots `01`–`60`.

## Authority and exact source snapshots

- Engine current program authority: `patrickminitz-web/biella-engine` `main` commit `3f73ddb5b7a22ed9f2678376f6457c87a6611bdf`, tree `b2331d6066e5af88ba17492a0c5e3ac87171cad7`.
- Website application source at inventory start: `patrickminitz-web/biella-engine` branch `website`, commit `453573f610f1ad49de6ac9ee8f6b78a15b7ef9cd`, tree `0cb18c4a8a9ea775b46b4b98341f535dddda24ff`; `website/` subtree `2c7ec71c6579dbbe4bb7495bc19becd6467c867c`.
- Game source relevant to Website game-media consumption: `patrickminitz-web/biella-games` `main` commit `0b8b4654819f53f6e3d5f65fb64d844d5c9a18a5`, tree `fe47d9f176cd213b5bc2c3aaea094f09741235b1`.
- Canonical Website Drive root: `BIELLA_WEBSITE`, folder ID `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V`.
- Canonical asset manifest Drive file: `BIELLA_WEBSITE_ASSET_MANIFEST.md`, ID `11skZ-wCs4fX2dG2Q-OzXAjcFufFX33-8`.

The Website branch fork predates current `main` edits to the master pack/cross-map. Current program authority therefore comes from `main`; the `website` branch remains the application source. BU-01 does not merge or rewrite either source.

## Current GitHub website-relevant source groups

| Source | Exact identity | Use in BU-01 |
|---|---|---|
| `docs/biellawebsite/BIELLA_UNIVERSE_36_TASK_MASTER_PACK.md` on `main` | blob `421535f54c25f1383b5b7e62898eb3b6e9c28659` | current BU program authority |
| `docs/biellawebsite/BIELLA_UNIVERSE_36x51_ENGINE_CROSSMAP.md` on `main` | blob `38cf0a4e3e860edbb980436b7da904689105abc9` | current Engine/Website ownership map |
| `docs/biellawebsite/BIELLA_WEBSITE_ASSET_MANIFEST.md` | blob `4704e5b0792835dd867782afe2e6ebbb1c7cdac8` | 60-slot registry |
| `website/` on branch `website` | tree `2c7ec71c6579dbbe4bb7495bc19becd6467c867c` | current Website application workspace |
| `website/content/website-visual-assets.csv` | blob `9b06346d688bf4a8fa5fe0785167e83f357a5ac8` | slots 01–50 filename/status ledger |
| `website/content/asset-resolution.json` | blob `eee8a2fb386d22ec465b94546b74967bf092ca38` | exact visual-source resolution state |
| `website/content/game-runtime-media.json` | blob `3eb4098ddcf631edc1fca7f68446dd1748f57584` | Game runtime-media consumption record |
| `docs/brand/preproduction/` | tree `448899af9e58f3c3dab72129b160a67f2f41705a` | brand/visual production source set; not automatic asset-slot bytes |
| `docs/business/` | tree `d00e7583dc667a68ca2426d7eb02f71dfab20683` | public product/business narrative source set |
| `docs/integration/BIELLA_POST_P4_06_GAME_WEBSITE_MAP.md` | blob `cf8a37861458c41e68dbb6fb00a67e95d191e314` | Engine/Game/Website integration reference |
| `docs/project-state/` on Website source snapshot | tree `5faa354d82ca172d21204784993a24b36ff1381d` | state evidence; current truth must be reconciled with current `main`/runtime |

## Canonical Drive website inventory

Direct active structure observed under Drive folder `1btVF8nJbwGWhuEA4N9vmgZVckVDNv07V`:

| Drive item | ID | Current role |
|---|---|---|
| `10_DOCUMENTATION_TOOLS` | `1NzYPCnF4VysGHWc7YPkKBz36ad6Vcqns` | active document-spec sources |
| `20_APPLICATION_WORKSPACE` | `1-PUKv3tflWzCEHSCJ1bl2o6Dmv0RXsTH` | Website application continuity |
| `30_VISUAL_MASTERS` | `1xfx0_Tcc4hw_sqA_T-2auH6yjSQPNBad` | visual-source resolution records |
| `40_GAME_RUNTIME_MEDIA` | `1WMPyb3Jr0shr5x_5IRzUic-_MH1svrWq` | accepted runtime-media lane |
| `90_ARCHIVE` | `11ndIoYHz6bM9xZnbp9Usd6xealzvR09A` | archived/superseded Website material |
| `BIELLA_WEBSITE_ASSET_MANIFEST.md` | `11skZ-wCs4fX2dG2Q-OzXAjcFufFX33-8` | canonical 60-slot control index |

Current continuity records:

- `BU07_WEBSITE_APPLICATION_WORKSPACE_STATE` — Drive ID `1LGxsPaDip4fRYFb6bgXTXb9tH1kVkTnGPZc0POoRmeA`; binds Website source commit/tree `453573f610f1ad49de6ac9ee8f6b78a15b7ef9cd` / `0cb18c4a8a9ea775b46b4b98341f535dddda24ff`, CI success, and unresolved Cloudflare preview credentials.
- `WEBSITE_VISUAL_MASTER_RESOLUTION_01_50` — Drive ID `1tZs8oWUfXB9BOyYQe_-DaTk8tGcQpHLGTrwBVg4rq0k`; records `0/50` exact Drive filename matches and `SOURCE_BYTES_UNRESOLVED` without guessed promotion.
- `BU16_GAME_RUNTIME_MEDIA_CONSUMPTION_LANE` — Drive ID `16IT5vdWP73Ya4crV4K0HK_RdyMT-oIZAP1rgj0aEYtU`; records `0` accepted runtime-media items and requires real Game runtime provenance.
- Drive Option-C program records observed under archived program folder: master pack ID `1F5rxWBQ3wzbvW5vohTvhw5cFc0sToQ_-M-dB2Fvu7zo`; cross-map ID `15TsY-LRFm3MoT7IlS-TpCsGON8eU5aRCmAuEwsk1llM`. Current GitHub `main` remains the higher-current program source where content differs.

## Manifest reconciliation — slots 01–50

All 50 image slots have canonical registration filenames, but the current exact-source audit found zero matching canonical filenames in accessible Drive and no verified source bytes have been migrated. These slots are therefore reconciled to `UNRESOLVED_SOURCE_BYTES`; filename registration is not content identity.

| ID | Canonical filename | Exact source status |
|---:|---|---|
| 01 | `biella_engine_ui_system_poster.png` | `UNRESOLVED_SOURCE_BYTES` |
| 02 | `biella_engine_ai_orchestration_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 03 | `biella_engine_editor_ui_kit_sheet.png` | `UNRESOLVED_SOURCE_BYTES` |
| 04 | `biella_engine_asset_pipeline_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 05 | `neon_rendering_and_vfx_control_sheet.png` | `UNRESOLVED_SOURCE_BYTES` |
| 06 | `neon_multiplayer_live_ops_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 07 | `neon_npc_ai_simulation_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 08 | `neon_worldbuilding_missions_progression_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 09 | `biella_engine_hud_ux_system_design_sheet.png` | `UNRESOLVED_SOURCE_BYTES` |
| 10 | `futuristic_game_engine_hardware_catalog_sheet.png` | `UNRESOLVED_SOURCE_BYTES` |
| 11 | `biella_unified_ai_tool_hub_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 12 | `biella_google_drive_task_archive_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 13 | `biella_nvidia_compute_control_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 14 | `biella_openai_developers_workflow_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 15 | `biella_web_search_intelligence_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 16 | `biella_ai_image_pipeline_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 17 | `biella_visualization_studio_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 18 | `biella_task_execution_board_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 19 | `biella_prompt_pack_organizer_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 20 | `biella_asset_progress_tracker_transparent.png` | `UNRESOLVED_SOURCE_BYTES` |
| 21 | `biella_engine_neon_ide_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 22 | `neon_blueprint_visual_scripting_editor.png` | `UNRESOLVED_SOURCE_BYTES` |
| 23 | `biella_engine_shader_authoring_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 24 | `biella_engine_ui_designer_mockup.png` | `UNRESOLVED_SOURCE_BYTES` |
| 25 | `biella_engine_live_ops_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 26 | `biella_engine_profiling_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 27 | `biella_engine_neon_ci_cd_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 28 | `biella_engine_neon_plugin_marketplace_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 29 | `biella_engine_input_systems_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 30 | `biella_engine_cinematics_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 31 | `biella_engine_deep_research_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 32 | `biella_engine_neon_intelligence_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 33 | `biella_engine_orchestration_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 34 | `biella_engine_neon_analytics_dashboard_ui_kit.png` | `UNRESOLVED_SOURCE_BYTES` |
| 35 | `biella_knowledge_graph_nexus_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 36 | `biella_engine_neon_prompt_lab_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 37 | `biella_engine_cyberpunk_benchmark_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 38 | `neon_task_planning_command_board.png` | `UNRESOLVED_SOURCE_BYTES` |
| 39 | `biella_neon_reporting_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 40 | `neon_automation_pipeline_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 41 | `biella_engine_memory_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 42 | `biella_engine_research_dashboard_sheet_42.png` | `UNRESOLVED_SOURCE_BYTES` |
| 43 | `neon_multi_agent_control_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 44 | `neon_source_control_dashboard_sheet.png` | `UNRESOLVED_SOURCE_BYTES` |
| 45 | `biella_engine_build_farm_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 46 | `biella_engine_qa_automation_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 47 | `biella_engine_telemetry_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 48 | `cyberpunk_compute_resource_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 49 | `procedural_world_simulation_dashboard.png` | `UNRESOLVED_SOURCE_BYTES` |
| 50 | `neon_collaboration_dashboard_asset_sheet.png` | `UNRESOLVED_SOURCE_BYTES` |

This is a complete reconciliation result for the current corpus: unresolved is an exact state, not permission to guess a candidate.

## Manifest reconciliation — slots 51–60

Slots 51–60 resolve to exact active Drive files and exact GitHub blobs.

| ID | Canonical file | Drive ID | GitHub blob (`docs/biellawebsite/`) | Result |
|---:|---|---|---|---|
| 51 | `51_BIELLA_MARKDOWN_NOTES_WORKSPACE.md` | `1Go9pe7gUdcuRiq068h2icpZGHO7fJOeo` | `ecd78aec6207f6e68e0df69a3794352d7554ffe2` | `RESOLVED_EXACT_SOURCE` |
| 52 | `52_BIELLA_TECHNICAL_SPEC_EDITOR.md` | `19Crm4lsePhUPbd6QEPuprBCsu3W0cj5S` | `ff859f72932388dff8a658e425162ae37f495d39` | `RESOLVED_EXACT_SOURCE` |
| 53 | `53_BIELLA_PROJECT_DOCUMENTATION_HUB.md` | `1x0uMhTOuDWb_2A_bzmsGkLeCREt1khzH` | `18f0617b4879011d7f0c5fe5b9bef46528d1f107` | `RESOLVED_EXACT_SOURCE` |
| 54 | `54_BIELLA_KNOWLEDGE_NOTES_LINKING.md` | `1OOMrvq_5cvItoG8vTOV9T_bA4iDS8k_e` | `5caa27073d0381b11862e990e7504ba1e5630114` | `RESOLVED_EXACT_SOURCE` |
| 55 | `55_BIELLA_TASK_HANDOFF_CONTINUATION_NOTES.md` | `1vIs_8P9fqTkI5StrlM5HG4OVRla_YObz` | `226195a66cd3346252f5b1d62a0dc81674eb5b5d` | `RESOLVED_EXACT_SOURCE` |
| 56 | `56_BIELLA_RESEARCH_NOTEBOOK.md` | `1q2BBst4OzQg2uxCaxtkQNOzJz1-Xt9EV` | `7d8d56138bd758907389f4fb394b96722f9ac4ab` | `RESOLVED_EXACT_SOURCE` |
| 57 | `57_BIELLA_MARKDOWN_DIFF_VERSION_HISTORY.md` | `1eRWXicPCyYqdCMI4fOJPVSy-5fgwx0ZM` | `6fbc0a4723aa0e18659b970827a2e3001d8caeb2` | `RESOLVED_EXACT_SOURCE` |
| 58 | `58_BIELLA_STRUCTURED_MD_TEMPLATE_BUILDER.md` | `1Bn2ALGuzTsTWmdQsx0wWex73zxk5VifS` | `9736e825c2ad328942f797f32800565b34a9ca75` | `RESOLVED_EXACT_SOURCE` |
| 59 | `59_BIELLA_DOCUMENT_SEARCH_INDEX_RETRIEVAL.md` | `1FsgccrcOkE2ZZ_e4q8qEXO-o74enZ-PQ` | `dd1a8720269cdb7015296ef05d73b6abc71c26b2` | `RESOLVED_EXACT_SOURCE` |
| 60 | `60_BIELLA_DOCUMENT_EXPORT_PUBLISHING.md` | `1xl-L5mHrxplVa453Q1YP2K-hH1FMQfyh` | `07d89edfa86c002080dc39be4cba5e424854e79b` | `RESOLVED_EXACT_SOURCE` |

The Drive and GitHub copies are separately identified. Cross-store byte equality is not inferred from matching filenames or equal sizes. Drive sizes observed for 51–53 differ from their GitHub blobs, so those cross-store copies are explicitly not treated as byte-identical.

## BU-01 result

- Accessible Website Drive hierarchy inventoried at the current canonical root.
- Current Engine `main`, Website application branch, and Game source identities recorded.
- Current website-relevant source groups recorded by exact Git tree/blob or Drive file/folder identity.
- Manifest slots `01`–`50`: `50/50` reconciled as `UNRESOLVED_SOURCE_BYTES`; zero candidate promotions performed.
- Manifest slots `51`–`60`: `10/10` reconciled to exact Drive file IDs and GitHub blobs.
- Superseded/archive material remains non-active; no raw historical material was activated.
- No Website/Engine/Game boundary was changed.

BU-01 is an inventory result only. Asset selection/migration/classification and later BU implementation tasks remain separate work.