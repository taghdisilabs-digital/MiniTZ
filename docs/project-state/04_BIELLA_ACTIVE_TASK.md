# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P3-04
  global_number: 35
  phase: P3
  title: Large-Scale / AAA Multi-Domain Production Orchestration Pack
  state: READY_AFTER_P3_03_DURABLE_CLOSE
  exact_prompt:
    title: 35_P3-04_Large_Scale_AAA_Multi_Domain_Production_Orchestration_Pack.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/35_P3-04_Large_Scale_AAA_Multi_Domain_Production_Orchestration_Pack.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/35_P3-04_Large_Scale_AAA_Multi_Domain_Production_Orchestration_Pack.md.docx
    drive_id: 1NLikJ8cPQ3-4ybpMr8FvHN2sn43fPVw_trMet-Wx_HQ
    local_docx_sha256: 8c154f2b89085ff294f4ca35887d65fca3533c6f06e043f9fde6a04fd9737d42
    live_drive_exported_docx_sha256: 3133cdbbdc5d26131061b6122b36b764ec2dadd64d196b08e300739f1932e324
    canonical_text_sha256: f7a4cd3552b2a2d889826eed6baedbc48131f8be270ed9244bf4884d07cf574a
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P3-03
    result_commit: f665445e1771b98f34e1d82746c5d4a9686e3138
    result_tree: 6a8c47f70fcd5df900381e05a93169a9aed25205
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_real_type_build_installed_and_relevant_regression: VERIFIED
  numbered_successor: P3-05

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P3_04_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_ProductionPack_Software_Game_Project_Task_Run_Graph_Node_Scheduler_ResourceAllocation_Artifact_Checkpoint_Workspace_Validation_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P3_05_or_later_prompt_bodies_before_P3_04_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_revision_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_Workspace_Checkpoint_Validation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_call_ledger_checkpoint_and_resource_contracts
    - P2_adapter_execution_isolation_retrieval_workspace_validation_fencing_durability_and_quarantine_firewall_contracts
    - P3_01_provider_neutral_ProductionPack_Software_pack_exact_repository_candidate_build_runtime_provenance_recovery_and_Project_isolation_contracts
    - P3_02_provider_neutral_web_pack_exact_repository_live_runtime_HTTP_browser_package_provenance_recovery_and_Project_isolation_contracts
    - P3_03_provider_neutral_game_pack_exact_engine_candidate_asset_build_runtime_validation_atomicity_worker_recovery_and_Project_isolation_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 35/51 - P3-04

  TITLE

  Large-Scale / AAA Multi-Domain Production Orchestration Pack

  PHASE

  P3 - Production capability packs

  GOAL

  Prove complex long-lived multi-domain production composes through the same Graph/Scheduler without a separate AAA controller, global lock, or permanent specialist hierarchy.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Prove the same kernel can produce real software, web, game, 3D, media, rendering, VFX, and packages without domain-specific kernel redesign.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 34/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Provide composition recipes/bundle metadata spanning software/game/3D/character/animation/environment/render/VFX/image/audio/video/package capabilities; reference downstream packs if not yet implemented.

  - Represent real dependency fan-out/fan-in and independent branches; resource scheduler remains sole allocation authority.

  - Persist component Artifacts and ProductionIntegrationManifest with exact refs; integration never resolves ambiguous latest assets.

  - Checkpoint long Runs, retain completed branches through worker/branch failure, and use new Graph revision for bounded repair.

  - Project quality/art direction/performance remain Project data.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Provide composition recipes/bundle metadata spanning software/game/3D/character/animation/environment/render/VFX/image/audio/video/package capabilities; reference downstream packs if not yet implemented.

  - Represent real dependency fan-out/fan-in and independent branches; resource scheduler remains sole allocation authority.

  - Persist component Artifacts and ProductionIntegrationManifest with exact refs; integration never resolves ambiguous latest assets.

  - Checkpoint long Runs, retain completed branches through worker/branch failure, and use new Graph revision for bounded repair.

  - Project quality/art direction/performance remain Project data.

  REQUIRED INTERFACES

  - Large-scale ProductionPack descriptor

  - ProductionIntegrationManifest

  - multi-domain graph recipes

  DATA / STATE CHANGES

  - Persist only durable state required by this task; large payloads belong in content-addressed objects/Artifacts, not opaque database blobs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - At least four independent branches with productive concurrency >1 when resources allow.

  - Kill one worker/branch; completed branches remain; recover only affected branch.

  - Graph v2 changes one branch while unaffected historical outputs remain exact.

  - Second Project runs concurrently without data leakage.

  - Static/runtime check for no AAA/global heavy lock or manager authority.

  KPI

  - domain_specific_second_scheduler=0

  - global_production_lock=0

  - independent_branches_serialized_without_reason=0

  - whole_Run_restarted_after_one_branch_failure=0

  - ambiguous_latest_artifact_integration=0

  RESTORED LONG-FORM REQUIREMENTS

  PURPOSE: PROVE NORMAL GRAPH/SCHEDULER SCALES

  "AAA" here means large-scale, multi-domain, dependency-rich, resource-intensive, long-running production.

  It does not mean a visual style, engine, permanent team hierarchy, or second orchestrator.

  Do not create:

  - AAAController;

  - AAAFactoryManager;

  - AAAApprovalPipeline;

  - permanent worker hierarchy.

  Use normal Task -> Graph -> Nodes -> Scheduler -> Capabilities -> Artifacts -> Validation.

  COMPOSITION

  Prepare composition across: software, game, 3D, character, animation, environment, render, VFX, image, audio, video, package.

  Downstream not-yet-implemented capabilities may use REFERENCE implementations for orchestration tests only.

  Never claim reference branch as real production.

  REPRESENTATIVE GRAPH

  Support dynamic pattern similar to:

  requirements

  ├─ software/gameplay

  ├─ environment/materials/lighting

  ├─ character/rig/animation

  └─ audio/VFX

  ↓

  integration

  ↓

  build

  ├─ runtime QA

  └─ performance

  ↓

  package

  This is an example recipe, not mandatory global workflow.

  PARALLEL BRANCHES

  Required proof: at least 4 independent productive branches where resources permit.

  Examples: software, environment, character, audio, texture.

  Record max_concurrent_productive_nodes > 1 when adequate resources exist.

  RESOURCE CONTENTION

  Use P1 scheduler:

  - GPU-heavy Nodes contend only for GPU capacity;

  - CPU Nodes continue;

  - storage/network work overlaps;

  - multi-resource requirements respected.

  No AAA-specific scheduler/reservation hierarchy.

  DURABILITY

  Exercise:

  - checkpoints;

  - Workspace snapshots;

  - completed Artifacts;

  - long branch execution;

  - worker lease expiry;

  - Run reconstruction;

  - Graph revision.

  A failed character branch must not erase succeeded software/environment or independent running audio.

  BOUNDED GRAPH REVISION

  If one branch needs a new approach: create Graph v2 changing bounded region.

  Preserve:

  - unaffected completed branches;

  - failed v1 history;

  - exact new branch;

  - integration dependency changes.

  Do not restart whole Run.

  EXACT INTEGRATION

  Create ProductionIntegrationManifest or equivalent:

  - Project/Task/Run/Graph;

  - exact component Artifacts/versions;

  - integration refs;

  - build;

  - validation refs;

  - digest.

  Integration may not resolve "latest character/environment".

  Changed upstream Artifact invalidates or creates new integration.

  VALIDATION

  Compose domain-specific validation: software tests, character deformation, render checks, runtime, performance.

  No universal final critic.

  AGENTS

  Specialists are optional dynamic execution strategies only.

  PERFORMANCE

  Measure actual Project budgets; no generic AAA threshold.

  FAILURE INJECTION

  Required:

  1.  multi-branch Graph;

  2.  ≥4 branches;

  3.  complete ≥2;

  4.  kill/fail worker in another;

  5.  prove completed retained;

  6.  recover/reassign;

  7.  revise Graph if needed;

  8.  integrate exact Artifacts;

  9.  validate final integrated output.

  GLOBAL LOCK CHECK

  Static/runtime check finds no heavyweight:global, AAA:global, production:global.

  Only real resource/mutable-target conflicts serialize.

  MULTI-PROJECT

  Run Project Alpha large production while Beta unrelated Task runs.

  Shared scheduler/resource does not mean shared data.

  P3-04 passes only when normal Biella architecture, not a new AAA authority, handles this.

  USEFUL EVIDENCE — NON-GATING

  - Complex production uses normal Task/Graph/Run/Scheduler/Artifact semantics and demonstrates bounded failure recovery.

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

  PROMPT: 35/51 - P3-04

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
