# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P3-05
  global_number: 36
  phase: P3
  title: 3D Modeling and Scene Production Pack
  state: READY_AFTER_P3_04_DURABLE_CLOSE
  exact_prompt:
    title: 36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
    drive_id: 1TIG3GggwGdu3ma1e5MeeIontVUO4pmSP4aggJKps0Kg
    local_docx_sha256: abb4255869736f571329e3e55409fc8675f927a4ab09bc50bbb6556bbd48c050
    live_drive_exported_docx_sha256: d411b17a37fc988eda9a563c0285515e9be478a12ba024c23dc6696da2c8c8e6
    canonical_text_sha256: e8688b4e820c7df1096f4a88a9e0bcda792fbe17c3e1690839a689bbcf6f46ed
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P3-04
    result_commit: 28fde1e9224236ce7b37b74434727463e96d9893
    result_tree: d7efcc21cab8dc86488ef91963f48791dbe0dca0
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_scheduler_provenance_recovery_isolation_type_build_installed_and_relevant_regression: VERIFIED
  numbered_successor: P3-06

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P3_05_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_ProductionPack_Project_Task_Run_Graph_Node_Scheduler_ResourceAllocation_Workspace_Artifact_Validation_Process_and_Game_adapter_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P3_06_or_later_prompt_bodies_before_P3_05_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_revision_Node_attempt_fence_Artifact_ContentRef_SourceRef_Event_ResourceAllocation_Workspace_Checkpoint_Validation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_call_ledger_checkpoint_and_resource_contracts
    - P2_adapter_execution_isolation_retrieval_workspace_validation_fencing_durability_and_quarantine_firewall_contracts
    - P3_01_provider_neutral_ProductionPack_Software_pack_exact_repository_candidate_build_runtime_provenance_recovery_and_Project_isolation_contracts
    - P3_02_provider_neutral_web_pack_exact_repository_live_runtime_HTTP_browser_package_provenance_recovery_and_Project_isolation_contracts
    - P3_03_provider_neutral_game_pack_exact_engine_candidate_asset_build_runtime_validation_atomicity_worker_recovery_and_Project_isolation_contracts
    - P3_04_large_scale_normal_Graph_Scheduler_exact_Artifact_manifest_classification_provenance_recovery_concurrency_and_Project_isolation_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 36/51 - P3-05

  TITLE

  3D Modeling and Scene Production Pack

  PHASE

  P3 - Production capability packs

  GOAL

  Produce and modify real editable 3D assets/scenes through replaceable DCC/tool implementations with exact source/tool/export identity and technical validation.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Prove the same kernel can produce real software, web, game, 3D, media, rendering, VFX, and packages without domain-specific kernel redesign.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 35/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Register 3d.inspect/model/mesh_edit/topology/uv/material/scene/convert/optimize/validate/preview and extensible additions.

  - Define ThreeDToolAdapter and at least one real/reference implementation; DCC SDK stays adapter-local.

  - Preserve tool-native/editable source where meaningful plus exact interchange exports/derivation.

  - Structured inspection covers hierarchy, mesh/topology/UV/material/texture/transforms/scale/dependencies; no binary dump into model context.

  - Technical validators parse/reopen exports; Project-specific style/poly/scale requirements remain scoped; independent assets may run concurrently.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Register 3d.inspect/model/mesh_edit/topology/uv/material/scene/convert/optimize/validate/preview and extensible additions.

  - Define ThreeDToolAdapter and at least one real/reference implementation; DCC SDK stays adapter-local.

  - Preserve tool-native/editable source where meaningful plus exact interchange exports/derivation.

  - Structured inspection covers hierarchy, mesh/topology/UV/material/texture/transforms/scale/dependencies; no binary dump into model context.

  - Technical validators parse/reopen exports; Project-specific style/poly/scale requirements remain scoped; independent assets may run concurrently.

  REQUIRED INTERFACES

  - ThreeDToolAdapter

  - 3D ProductionPack descriptor

  - 3D pack-level Artifact roles/validators

  DATA / STATE CHANGES

  - Persist only durable state required by this task; large payloads belong in content-addressed objects/Artifacts, not opaque database blobs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Ingest/create editable mesh, inspect, modify geometry/material, save source, export, reopen/validate, generate preview.

  - Invalid topology/dependency/UV cases.

  - DCC unavailable affects route, not Capability.

  - Two implementations share contract; Project isolation.

  KPI

  - dcc_specific_kernel_fields=0

  - render_only_used_as_3D_source_proof=0

  - editable_source_missing_when_required=0

  - invalid_export_claimed_valid=0

  - global_polygon_budget=0

  - domain_specific_kernel_changes=0

  RESTORED LONG-FORM REQUIREMENTS

  REAL EDITABLE 3D SOURCE

  A rendered PNG is not proof of 3D production.

  For modeling/scene Tasks preserve real editable/native source where appropriate, plus verified exports and derivation.

  PACK

  pack_id = 3d.

  Capabilities:

  - 3d.inspect

  - 3d.model

  - 3d.mesh_edit

  - 3d.topology

  - 3d.uv

  - 3d.material

  - 3d.scene

  - 3d.convert

  - 3d.optimize

  - 3d.validate

  - 3d.preview

  Optional later sculpt/retopo/LOD/collision.

  No domain kernel changes.

  TOOL ADAPTER

  Generic ThreeDToolAdapter: inspectAsset, inspectScene, createAsset, modifyAsset, executeOperation, validate, export, preview, describeRuntime.

  Tool-specific implementation may be Blender/Houdini/Maya/etc., but tool SDK types stay adapter-local.

  Use real DCC if available; otherwise reference and label NOT_RUN for real 3D.

  RUNTIME IDENTITY

  Capture tool/version/plugins/runtime/source/operation config/output exact identity.

  ARTIFACT ROLES

  Extensible roles: MESH, SCENE, MATERIAL, TEXTURE_SET, UV_DATA, LOD_SET, COLLISION_MESH, INTERCHANGE_EXPORT, PREVIEW.

  Not universal closed enum.

  FORMATS

  Support native editable and interchange: glTF/GLB, FBX when supported, OBJ, USD, etc.

  No mandatory format.

  INSPECTION

  Bounded structured: object hierarchy/count, mesh counts, vertices/edges/faces, materials/textures, UV layers, cameras/lights, transforms, dimensions, units/scale, missing dependencies.

  Do not put binary file in model context.

  MODELING / TOPOLOGY

  Geometry may be procedural/deterministic/model-assisted/DCC-scripted.

  Model text alone is not final asset.

  Validate normals, non-manifold, duplicate vertices, degenerate faces, cleanup, metrics.

  No universal "good topology" or polygon budget.

  UV / MATERIAL

  UVs only when Task requires.

  Materials bind exact texture Artifacts and preserve provenance.

  P3-11 creates texture content later.

  SCENE / COORDINATES

  Support hierarchy, placement, transforms, camera/light refs, linked assets.

  Record units/axis conversions. No global Blender/engine convention.

  EXPORT / CONVERSION

  Bind exact source, target format, exporter/version/settings digest.

  After export:

  - exists;

  - exact ContentRef;

  - reopen/parse/inspect where possible;

  - derivation.

  Process exit alone not success.

  OPTIMIZATION

  Decimation/LOD/dedupe/etc. preserve high-quality source and use Project targets/tolerances.

  PREVIEW

  Viewport/turntable/wireframe/material preview is secondary evidence, not editable source.

  RESOURCE / WORKSPACE / CACHE

  Use P2 Workspace and Resource scheduler.

  Missing DCC affects routing, not 3d.model existence.

  DCC caches/thumbnails/shaders are rebuildable unless explicit output.

  CONCURRENCY

  Independent assets concurrently.

  Conflicting same-scene edits use isolated Workspaces/integration.

  GAME INTEGRATION

  Preserve source 3D, export exact game-compatible Artifact, import via Game adapter, validate if required.

  Game engine is not source authority.

  REAL TASK

  Create/ingest editable mesh -> inspect -> modify -> material -> save source -> export -> reopen -> validate -> preview -> persist provenance.

  Do not count JSON pretending to be 3D as real.

  SECOND IMPLEMENTATION

  Real adapter A + reference/real B proves tool neutrality.

  Project Alpha/Beta style/topology/material rules remain isolated.

  USEFUL EVIDENCE — NON-GATING

  - Real/reference editable 3D source and verified export exist with exact provenance; preview is evidence, not source.

  DELIVERABLES

  - Real implementation source and task-scoped tests; schema/migrations/config only when this prompt requires them.

  - Durable evidence/Artifacts required by the task.

  - A coherent commit in clean Biella history when repository write access is available and the implementation is complete.

  EVIDENCE TO REPORT

  - Exact commands/tests and pass/fail counts.

  - Exact files/modules/migrations/interfaces changed.

  - Observed KPI values and REAL/REFERENCE/MOCK/NOT_RUN classifications.

  - Exact source commit, result commit/tree, known limitations, unresolved facts, and next dependency.

  Use this result block:

  PROMPT: 36/51 - P3-05

  STATUS: COMPLETE / PARTIAL / BLOCKED

  SOURCE COMMIT:

  RESULT COMMIT:

  RESULT TREE:

  IMPLEMENTED:

  INTERFACES CREATED/CHANGED:

  MIGRATIONS/STATE CHANGES:

  TESTS EXECUTED:

  KPI RESULTS:

  REALITY CLASSIFICATION:

  PROJECT ISOLATION / CONTAMINATION / DURABILITY CHECKS:

  KNOWN LIMITATIONS:

  UNRESOLVED FACTS:

  NEXT DEPENDENCY:

  CONTINUATION STATE

  - Continue dependency-safe productive work when useful. Continue with the next dependency-safe task when useful.

  - Leave the repository/worktree in an understood state and report any intentional dirty/uncommitted files.

  - The next prompt must verify this handoff from actual repository state before editing.
```
