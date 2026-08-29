# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-11
  global_number: 30
  phase: P2
  title: Durable Candidate Workspace and Sandbox Execution
  state: READY_AFTER_P2_10_DURABLE_CLOSE
  exact_prompt:
    title: 30_P2-11_Durable_Candidate_Workspace_and_Sandbox_Execution.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/30_P2-11_Durable_Candidate_Workspace_and_Sandbox_Execution.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/30_P2-11_Durable_Candidate_Workspace_and_Sandbox_Execution.md.docx
    drive_id: 1iwOAJYyXNdyqdqEc5g3l6hq4ms8wmHaP14eG60ivWFI
    local_docx_sha256: 768bb462d4de0e8f2e0b3a522f417a054ba68364aa4e9967754157faa4636e94
    live_drive_exported_docx_sha256: 5f199cb7f1a8acc95fabc20489944d3791d350c4cc0766c7e344ebfb1233e458
    canonical_text_sha256: dd3de5b57be4b8d0583a1c7f3caf3f0840aea1ed9abc4049855093a5fae87498
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-10
    result_commit: df3b6987865aae2f94eaa9650636fae131e4e167
    result_tree: 354127377184cc5901e58a2581fafadc17577e95
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_and_full_regression: VERIFIED
  numbered_successor: P2-12

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_11_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Task_Run_Graph_Node_Artifact_ContentRef_Workspace_adapter_resource_ToolCall_checkpoint_and_quarantine_firewall_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_12_or_later_prompt_bodies_before_P2_11_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ModelCall_ToolCall_Event_ResourceAllocation_and_managed_runtime_identity
    - P1_ContentRef_object_storage_Project_Engine_Run_memory_graph_event_scheduler_routing_and_checkpoint_contracts
    - P2_01_through_P2_04_real_execution_adapter_isolation_streaming_fencing_and_durability_contracts
    - P2_05_destination_egress_credential_redirect_streaming_timeout_cancellation_TLS_and_transport_evidence_contracts
    - P2_06_provider_neutral_model_deployment_execution_health_tool_policy_fencing_and_provenance_contracts
    - P2_07_browser_session_generation_egress_origin_side_effect_upload_download_wait_secret_and_durable_evidence_contracts
    - P2_08_Project_database_scope_parameterization_bounded_streaming_transaction_truth_TLS_secret_and_internal_database_firewall_contracts
    - P2_09_ContentRef_replica_state_streaming_independent_verification_corruption_fallback_repair_deletion_Project_egress_secret_and_stale_owner_contracts
    - P2_10_Project_scoped_retrieval_context_budget_provenance_rebuildability_and_quarantine_firewall_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |
  PROMPT 30/51 - P2-11

  TITLE

  Durable Candidate Workspace and Sandbox Execution

  PHASE

  P2 - Universal execution fabric

  GOAL

  Create Project/Run-scoped candidate workspaces that materialize exact sources, execute all tools through Biella adapters, capture/snapshot meaningful changes, and can be reconstructed after local workspace loss.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 29/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Define Workspace and WorkspaceExecutionPolicy with exact base refs/revision, roots, network/tool/resource/secret/side-effect constraints.

  - Materialize through Object/Git/Filesystem adapters into isolated local high-speed storage; original/protected source remains unchanged.

  - All tool execution goes through Process/Git/Runtime/Model tool pathways; no direct spawn bypass.

  - Capture diffs/changed files/generated Artifacts into a durable Workspace receipt/snapshot before cleanup.

  - Resume reuses validated local workspace or reconstructs from base + durable snapshot; uncaptured lost work is reported honestly.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Define Workspace and WorkspaceExecutionPolicy with exact base refs/revision, roots, network/tool/resource/secret/side-effect constraints.

  - Materialize through Object/Git/Filesystem adapters into isolated local high-speed storage; original/protected source remains unchanged.

  - All tool execution goes through Process/Git/Runtime/Model tool pathways; no direct spawn bypass.

  - Capture diffs/changed files/generated Artifacts into a durable Workspace receipt/snapshot before cleanup.

  - Resume reuses validated local workspace or reconstructs from base + durable snapshot; uncaptured lost work is reported honestly.

  REQUIRED INTERFACES

  - Workspace

  - WorkspaceExecutionPolicy

  - materialize/capture/snapshot/reconstruct/cleanup APIs

  - CandidateWorkspaceReceipt

  DATA / STATE CHANGES

  - Workspace logical records and snapshot/candidate refs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Create/materialize/mutate/capture workspace.

  - Two independent workspaces from same source remain separate.

  - Path/symlink/network/Project isolation.

  - Snapshot -> delete local directory -> restart -> exact reconstruction.

  - Uncaptured mutation loss produces explicit failure.

  - Cancellation preserves already captured outputs and releases resources.

  KPI

  - workspace_loss_causes_persisted_candidate_loss=0

  - candidate_changes_mutate_protected_source=0

  - ambiguous_base_revision=0

  - cross_project_workspace_access=0

  - direct_tool_execution_bypassing_adapter=0

  - global_single_workspace_lock=0

  RESTORED LONG-FORM REQUIREMENTS

  WORKSPACE IS MATERIALIZED EXECUTION STATE, NOT RUN AUTHORITY

  Implement durable logical Workspace identity separate from local path.

  Conceptual:

  Workspace

  workspace_id

  project_id

  task_id

  run_id

  graph_revision

  node/graph ownership

  workspace_type

  base_source_refs

  base_revision

  execution_policy_ref

  resource_allocation_ref?

  local materialization ref?

  status

  timestamps

  Local path may disappear.

  TYPES

  Extensible examples:

  - REPOSITORY;

  - FILES;

  - ASSET;

  - BUILD;

  - TEMPORARY.

  Do not hardcode game/3D in universal Workspace.

  LIFECYCLE

  Technical lifecycle:

  CREATE -> MATERIALIZE -> EXECUTE -> CAPTURE -> PERSIST -> CLEAN

  These are workspace lifecycle semantics, not necessarily separate Graph Nodes.

  CREATE

  Bind exact Project/Task/Run/Graph/base sources and execution policy.

  Mutation Tasks requiring reproducibility cannot use ambiguous "current source".

  MATERIALIZE

  Use Object Store/Filesystem/Git to materialize exact base.

  Verify source digest/commit and Project ownership.

  Do not silently mutate original checkout.

  EXECUTION POLICY

  Represent:

  - filesystem roots/modes;

  - network NONE/RESTRICTED/PROJECT_POLICY;

  - allowed tools/capabilities;

  - process/resource limits;

  - CPU/RAM/GPU budget refs;

  - secret refs;

  - side-effect boundary;

  - timeout.

  Do not create one universal sandbox policy that blocks legitimate Project work.

  TOOL EXECUTION

  All tool/process/Git/container actions go through P2 adapters/ToolCall accounting.

  No direct spawn()/filesystem bypass.

  CANDIDATE MUTATION

  Models/tools may mutate candidate Workspace, not protected Project/engine/another Project source unless Task explicitly grants write.

  Candidate change is not automatically Project-authoritative.

  CAPTURE

  Before cleanup capture meaningful state.

  Repository:

  - base commit;

  - HEAD;

  - staged/unstaged diff;

  - untracked files;

  - generated Artifacts;

  - tests/log refs.

  File/asset:

  - changed/generated file ContentRefs;

  - derivation;

  - output manifest.

  SNAPSHOT

  Durable Workspace snapshot should capture authoritative candidate state:

  - manifest;

  - base refs;

  - changed file ContentRefs;

  - Git diff/status;

  - relevant continuation refs.

  Do not archive huge rebuildable caches unnecessarily.

  CHECKPOINT

  RunCheckpoint can reference Workspace ID/latest snapshot/base/candidate refs.

  Resume:

  - reuse valid local Workspace if still exact;

  - otherwise reconstruct from base + snapshot.

  Same local disk is not required.

  MANDATORY LOSS TEST

  1.  create;

  2.  change candidate;

  3.  capture/snapshot;

  4.  delete local Workspace;

  5.  restart;

  6.  reconstruct;

  7.  verify exact candidate bytes/state;

  8.  continue Run.

  Persisted work must survive.

  If Workspace disappears before capture, report lost current attempt honestly; do not fabricate state.

  FILESYSTEM / NETWORK ISOLATION

  Reject traversal/symlink/another Project/host root/credentials.

  Network enforcement must be truthful.

  CONCURRENT WORKSPACES

  Independent Nodes may have independent Workspaces from same base concurrently.

  No global Workspace.

  Merging/integration is explicit Graph work.

  STALE SOURCE

  If authoritative source changes after creation, Workspace remains valid candidate based on original exact base. Do not silently rebase/relabel.

  Revalidate before Project merge/write.

  CLEANUP / CANCEL

  Persist outputs/snapshot before cleanup.

  Cleanup failure remains visible.

  Cancellation stops tools, captures already-valid durable outputs when policy permits, rejects late stale result, releases resources.

  SECRET EXCLUSION

  Snapshots must exclude SSH keys, OAuth tokens, provider creds, arbitrary secret mounts.

  RECEIPT

  Produce CandidateWorkspaceReceipt/manifest with exact base, candidate refs, diffs, tests/tool refs, snapshot, digest.

  This is later validation/finalization evidence.

  TESTS

  Create/materialize/mutate/source unchanged/tools/isolation/path+symlink escape/capture/snapshot/delete+reconstruct/uncaptured loss/stale source/cancel/cleanup/concurrent Workspaces/no global lock.

  USEFUL EVIDENCE — NON-GATING

  - Candidate production is durable/reconstructable and never depends on one local path or shared mutable checkout.

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

  PROMPT: 30/51 - P2-11

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
