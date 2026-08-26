# BIELLA WEBSITE ASSET MANIFEST

Status: ACTIVE WEBSITE ASSET CONTROL  
Scope: Biella Engine / Biella Games website visual and document album  
Canonical GitHub path: `docs/biellawebsite/BIELLA_WEBSITE_ASSET_MANIFEST.md`  
Canonical Drive folder: `BiellaEngine/biellawebsite/`

## 1. Purpose

This manifest is the control index for Biella website assets. It prevents generated visuals, document surfaces, prototypes, and superseded variants from being mixed together without an explicit status.

Every album slot must record:
- album ID
- title/purpose
- canonical filename when known
- media type
- visual-lock status
- Drive status
- GitHub status
- website-use status
- notes/provenance

## 2. BIELLA VISUAL LOCK

Website visual assets must use:
- transparent background
- no surrounding scenery
- no giant mechanical frame
- no blue/orange arcade-HUD treatment
- deep graphite/navy component surfaces
- Biella violet as dominant accent
- electric cyan as secondary accent
- green/amber/red only for semantic status
- thin precision borders
- subtle glass and emissive edge lighting
- restrained bloom
- dense professional workstation UI
- compact typography
- production-grade game-engine/editor aesthetic
- modular components suitable for real implementation
- consistent product identity across the entire album

## 3. Status vocabulary

- `APPROVED_REFERENCE` — accepted as a visual/product reference.
- `VISUAL_LOCK_FINAL` — generated to the current Biella Visual Lock and suitable for website placement after file transfer.
- `DOC_FINAL` — final Markdown specification/document.
- `CANONICAL_FILENAME_PENDING` — album concept exists but final individual filename is not yet locked.
- `DRIVE_PRESENT` — raw canonical file exists in `BiellaEngine/biellawebsite`.
- `GITHUB_PRESENT` — canonical file exists in `docs/biellawebsite`.
- `TRANSFER_PENDING` — generated asset exists outside the website archive and still needs canonical placement.
- `SUPERSEDED` — do not use for website implementation.
- `NOT_CREATED` — required concept/file has not yet been created.

## 4. Album registry

| ID | Title / Surface | Canonical filename | Type | Visual / Doc status | Drive | GitHub | Website use |
|---:|---|---|---|---|---|---|---|
| 01 | Core Engine Command Center | `biella_engine_ui_system_poster.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 02 | AI Agent Orchestration & Workflow | `biella_engine_ai_orchestration_dashboard.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 03 | 3D Editor, Viewports & Scene Tools | `biella_engine_editor_ui_kit_sheet.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 04 | Asset Pipeline, Materials & Animation | `biella_engine_asset_pipeline_dashboard.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 05 | Rendering, Lighting, Shaders & VFX | `neon_rendering_and_vfx_control_sheet.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 06 | Multiplayer, Networking & Live Ops | `neon_multiplayer_live_ops_dashboard.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 07 | NPC AI, Behavior & Simulation | `neon_npc_ai_simulation_dashboard.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 08 | Worldbuilding, Missions & Progression | `neon_worldbuilding_missions_progression_dashboard.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 09 | HUD, UX, Typography & Icons | `biella_engine_hud_ux_system_design_sheet.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 10 | Devices, Props, Drones & Hardware | `futuristic_game_engine_hardware_catalog_sheet.png` | image | APPROVED_REFERENCE | TRANSFER_PENDING | TRANSFER_PENDING | reference |
| 11 | Unified AI Tool Hub | `biella_unified_ai_tool_hub_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 12 | Google Drive Task Archive | `biella_google_drive_task_archive_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 13 | NVIDIA Compute Control | `biella_nvidia_compute_control_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 14 | OpenAI Developers Workflow | `biella_openai_developers_workflow_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 15 | Web Search Intelligence | `biella_web_search_intelligence_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 16 | AI Image Pipeline | `biella_ai_image_pipeline_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 17 | Visualization Studio | `biella_visualization_studio_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 18 | Task Execution Board | `biella_task_execution_board_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 19 | Prompt Pack Organizer | `biella_prompt_pack_organizer_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 20 | Asset Progress Tracker | `biella_asset_progress_tracker_transparent.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 21 | Code, Script & IDE Workspace | `biella_engine_neon_ide_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 22 | Blueprint / Visual Scripting | `neon_blueprint_visual_scripting_editor.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 23 | Shader, Material & Texture Authoring | `biella_engine_shader_authoring_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 24 | UI / HUD / Menu Designer | `biella_engine_ui_designer_mockup.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 25 | Networking, Multiplayer & Live Ops | `biella_engine_live_ops_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 26 | Profiling, Debugging & Optimization | `biella_engine_profiling_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 27 | Build, Test & CI/CD Center | `biella_engine_neon_ci_cd_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 28 | Plugins, Extensions & Marketplace | `biella_engine_neon_plugin_marketplace_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 29 | Input, Gameplay & Controller Systems | `biella_engine_input_systems_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 30 | Cinematics & Sequencer | `biella_engine_cinematics_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 31 | Deep Research Command Center | `biella_engine_deep_research_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 32 | Intelligence / Web Analysis | `biella_engine_neon_intelligence_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 33 | Execution Orchestration | `biella_engine_orchestration_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 34 | Analytics / Visualization | `biella_engine_neon_analytics_dashboard_ui_kit.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 35 | Knowledge Graph Nexus | `biella_knowledge_graph_nexus_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 36 | Prompt Lab | `biella_engine_neon_prompt_lab_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 37 | Benchmark & Evaluation Center | `biella_engine_cyberpunk_benchmark_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 38 | Task Planning Command Board | `neon_task_planning_command_board.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 39 | Reporting Dashboard | `biella_neon_reporting_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 40 | Automation Pipeline | `neon_automation_pipeline_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 41 | Memory Dashboard | `biella_engine_memory_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 42 | Research Workspace | `biella_engine_research_dashboard_sheet_42.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 43 | Multi-Agent Control | `neon_multi_agent_control_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 44 | Source Control | `neon_source_control_dashboard_sheet.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 45 | Build Farm | `biella_engine_build_farm_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 46 | QA Automation | `biella_engine_qa_automation_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 47 | Telemetry & Observability | `biella_engine_telemetry_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 48 | Compute Resource Control | `cyberpunk_compute_resource_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 49 | Procedural World Simulation | `procedural_world_simulation_dashboard.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 50 | Collaboration Workspace | `neon_collaboration_dashboard_asset_sheet.png` | image | VISUAL_LOCK_FINAL | TRANSFER_PENDING | TRANSFER_PENDING | candidate |
| 51 | Markdown & Notes Workspace | `51_BIELLA_MARKDOWN_NOTES_WORKSPACE.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 52 | Technical Specification Editor | `52_BIELLA_TECHNICAL_SPEC_EDITOR.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 53 | Project Documentation Hub | `53_BIELLA_PROJECT_DOCUMENTATION_HUB.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 54 | Knowledge Notes & Linking | `54_BIELLA_KNOWLEDGE_NOTES_LINKING.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 55 | Task Handoff & Continuation Notes | `55_BIELLA_TASK_HANDOFF_CONTINUATION_NOTES.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 56 | Research Notebook | `56_BIELLA_RESEARCH_NOTEBOOK.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 57 | Markdown Diff & Version History | `57_BIELLA_MARKDOWN_DIFF_VERSION_HISTORY.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 58 | Structured Markdown Template Builder | `58_BIELLA_STRUCTURED_MD_TEMPLATE_BUILDER.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 59 | Document Search, Index & Retrieval | `59_BIELLA_DOCUMENT_SEARCH_INDEX_RETRIEVAL.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |
| 60 | Document Export & Publishing | `60_BIELLA_DOCUMENT_EXPORT_PUBLISHING.md` | markdown | DOC_FINAL | DRIVE_PRESENT | GITHUB_PRESENT | implementation spec |

## 5. Superseded assets

The following earlier transparent/dashboard variants are explicitly excluded from website implementation because they drifted into a blue/orange arcade-HUD or chunky mechanical-frame treatment:

- `google_drive_task_archive_hud.png`
- `nvidia_compute_control_hud.png`
- `openai_developers_workflow_dashboard.png`
- `web_search_intelligence_hud_dashboard.png`
- `neon_ai_image_pipeline_dashboard.png`
- `futuristic_visualization_studio_dashboard.png`
- `neon_task_execution_board.png`
- `prompt_pack_organizer_dashboard.png`
- `asset_progress_tracker_hud_dashboard.png`
- `unified_ai_tool_hub_dashboard.png`

Status: `SUPERSEDED` — never use as a visual reference or website production asset.

## 6. Website repository target

When the image archive is transferred, use:

```text
website/
  assets/
    images/
      album/
        01-10/
        11-20/
        21-30/
        31-40/
        41-50/
  docs/
```

The current Markdown specifications remain under:

```text
docs/biellawebsite/
```

## 7. Required next actions

1. Copy canonical image assets 01–50 into the Drive `biellawebsite` archive.
2. Preserve original source/generated bytes; do not silently re-render during transfer.
3. Create canonical GitHub image paths under `website/assets/images/album/`.
4. Record SHA-256 digest and final dimensions for every transferred image.
5. Mark transparent-background compliance per asset after inspecting the actual file.
6. Keep superseded files outside production website paths.
7. Add website implementation files only after their associated asset IDs are registered here.
8. Update this manifest whenever an asset is replaced, superseded, renamed, or published.

## 8. Current completeness

- Album slots registered: 60 / 60
- Visual slots: 01–50
- Document slots: 51–60
- Document specs archived on Drive: 10 / 10
- Document specs present on GitHub: 10 / 10
- Visual assets transferred to website Drive archive: 0 / 50
- Visual assets transferred to GitHub website asset tree: 0 / 50
- Superseded visual set explicitly excluded: yes

This manifest is the canonical control record for website asset placement until superseded by a newer accepted revision.
