# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P3-03
  global_number: 34
  phase: P3
  title: Engine-Neutral Game Production Pack
  state: READY_AFTER_P3_02_DURABLE_CLOSE
  exact_prompt:
    title: 34_P3-03_Engine_Neutral_Game_Production_Pack.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/34_P3-03_Engine_Neutral_Game_Production_Pack.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/34_P3-03_Engine_Neutral_Game_Production_Pack.md.docx
    drive_id: 1ZShgBxR5qDFBhLM38MEJCsYCxdlWRjpUgzEYmvQqHlw
    local_docx_sha256: fbe83c26ed4c12c4b399b90130341863059ee49caee649dc0f6585ba7c80e1c3
    live_drive_exported_docx_sha256: 62d993f5b1045bb7a20f4395310ac73c69a2d349edea6ad6af2ae267cecd4ab3
    canonical_text_sha256: 043a1842c4fa85f2f61dc321850b15ae5cea22a2e6eabb4098fdb16769ca3f17
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P3-02
    result_commit: dfe1adc8b198841b17cdb75266c42b318b1db2ef
    result_tree: dceceff0c80ed5128264b7c5d7ce2a0fe2ac2c1e
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_and_full_regression: VERIFIED
  numbered_successor: P3-04

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P3_03_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_ProductionPack_Software_Git_Workspace_Process_Validation_Artifact_Project_Graph_Scheduler_Resource_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P3_04_or_later_prompt_bodies_before_P3_03_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_Workspace_Validation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_call_ledger_and_checkpoint_contracts
    - P2_adapter_execution_isolation_retrieval_workspace_validation_fencing_durability_and_quarantine_firewall_contracts
    - P3_01_provider_neutral_ProductionPack_Software_pack_exact_repository_candidate_build_runtime_provenance_recovery_and_Project_isolation_contracts
    - P3_02_provider_neutral_web_pack_exact_repository_live_runtime_HTTP_browser_package_provenance_recovery_and_Project_isolation_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 34/51 - P3-03

  TITLE

  Engine-Neutral Game Production Pack

  PHASE

  P3 - Production capability packs

  GOAL

  Inspect, modify, build, run, test, profile, capture, export, and package real game Projects while Godot/Unity/Unreal/other engines remain replaceable adapters.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Prove the same kernel can produce real software, web, game, 3D, media, rendering, VFX, and packages without domain-specific kernel redesign.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 33/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Register game.inspect/import/modify/build/run/test/profile/capture/export/package/validate.

  - Define GameEngineAdapter detect/inspect/import/build/run/test/profile/capture/export/describeRuntime; implement one real adapter when available plus a second contract/reference implementation.

  - Bind exact Project source revision, engine/version/config, target and output identity; engine-generated import/build caches remain rebuildable.

  - Build success is not playable/runtime proof; run/capture required when Task asks.

  - Expose clean hooks for 3D/character/animation/environment/image/audio/VFX packs.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Register game.inspect/import/modify/build/run/test/profile/capture/export/package/validate.

  - Define GameEngineAdapter detect/inspect/import/build/run/test/profile/capture/export/describeRuntime; implement one real adapter when available plus a second contract/reference implementation.

  - Bind exact Project source revision, engine/version/config, target and output identity; engine-generated import/build caches remain rebuildable.

  - Build success is not playable/runtime proof; run/capture required when Task asks.

  - Expose clean hooks for 3D/character/animation/environment/image/audio/VFX packs.

  REQUIRED INTERFACES

  - GameEngineAdapter

  - Game ProductionPack descriptor

  - game Artifact/validation registrations

  DATA / STATE CHANGES

  - Persist only durable state required by this task; large payloads belong in content-addressed objects/Artifacts, not opaque database blobs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Detect/inspect exact engine Project; isolated candidate change; import/build/output verification; real/reference launch/capture/test/profile/export.

  - Cache deletion rebuilds without source loss.

  - Second engine adapter uses same semantic contract.

  - Worker loss retains verified build.

  KPI

  - game_engine_hardcoded_in_kernel=0

  - build_claimed_playable_without_run=0

  - engine_cache_used_as_only_authority=0

  - global_game_performance_threshold=0

  - domain_specific_kernel_changes=0

  RESTORED LONG-FORM REQUIREMENTS

  ENGINE-NEUTRAL GAME PACK

  Implement game production with replaceable engine adapters.

  No Godot/Unity/Unreal type belongs in kernel.

  Conceptual:

  GameEngineAdapter:

  detectProject

  inspectProject

  importProject

  build

  run

  test

  profile

  capture

  export

  describeRuntime

  At least one real engine implementation when available; otherwise strong reference adapter and REAL evidence = NOT_RUN.

  Architecture must support second engine without Task/Graph schema change.

  CAPABILITIES

  - game.inspect

  - game.import

  - game.modify

  - game.build

  - game.run

  - game.test

  - game.profile

  - game.capture

  - game.export

  - game.package

  - game.validate

  ENGINE IDENTITY

  Capture exact:

  - adapter;

  - engine version;

  - project config;

  - target;

  - build/export config digest;

  - toolchain/runtime.

  Do not store only "Unity project"/"Godot project".

  PROJECT DATA

  Engine choice/version/target/input/gameplay/performance/visual/asset requirements are Project data.

  Do not globalize.

  INSPECTION

  Exact source:

  - project type/config;

  - scripts/source;

  - scenes/levels;

  - assets;

  - build/export config;

  - tests;

  - plugins/dependencies;

  - entry scene.

  Do not infer from legacy donor history.

  WORKSPACE / CACHE

  Modify in candidate Workspace.

  Distinguish: authoritative Project source/assets vs engine-generated import/build/cache.

  Delete cache -> rebuild possible; Project source remains.

  IMPORT

  Execute actual engine import where applicable and capture failures/runtime identity.

  Import cache is not sole authority.

  BUILD

  Produce actual expected Artifact.

  Exit success + missing package = not PASS.

  RUN

  Launch exact project/build and observe:

  - process/runtime;

  - entry scene/state;

  - crash/errors;

  - required behavior.

  Build != playable/runtime proof.

  TEST / INPUT

  Use engine-native/software tests where available.

  Automated input/interaction may verify state but cannot invent gameplay requirements.

  CAPTURE

  Screenshot/video/log/state/performance metrics are evidence.

  Capture alone is not gameplay correctness unless Task says so.

  PROFILE

  When requested measure Project-defined FPS/frame time/CPU/GPU/RAM/VRAM/load/package.

  No universal FPS.

  EXPORT

  Bind exact candidate, target, engine/config, verify output.

  Export != publish.

  MULTI-ENGINE NEUTRALITY

  Use implementation A plus B/reference for same semantic game.build/run/export.

  Task contract unchanged.

  ASSET INTEGRATION SEAMS

  Accept exact 3D/character/animation/environment/image/audio/VFX Artifact refs when packs exist.

  Do not implement downstream packs here.

  RESOURCE / HEADLESS

  Engine implementation declares CPU/GPU/RAM/storage/headless/interactive support.

  No GUI/GPU assumption.

  RECOVERY / CONCURRENCY

  Runtime crash leaves source/build.

  Worker loss does not rebuild verified build unnecessarily.

  Independent tests/assets/build prep may overlap when safe.

  TESTS

  Project detect/inspect/exact source; candidate change; import; build Artifact; run; crash fixture; scene/state; capture; test; profile; export; cache deletion/rebuild; two engine implementations; no Task schema change; Project isolation; build not runtime; worker loss retains build; no engine-specific kernel.

  USEFUL EVIDENCE — NON-GATING

  - Game production is engine-neutral and runtime-evidenced; Project gameplay/visual/performance rules stay scoped.

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

  PROMPT: 34/51 - P3-03

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
