# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-04
  global_number: 23
  phase: P2
  title: Replaceable Container and Isolated Runtime Adapter
  state: READY_AFTER_P2_03_DURABLE_CLOSE
  exact_prompt:
    title: 23_P2-04_Replaceable_Container_and_Isolated_Runtime_Adapter.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/23_P2-04_Replaceable_Container_and_Isolated_Runtime_Adapter.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/23_P2-04_Replaceable_Container_and_Isolated_Runtime_Adapter.md.docx
    drive_id: 1ulpsBImXNT3HyP7G0GUfEjNjPXqCknY0uLdjoEn4xyA
    local_docx_sha256: 89aeaa4968876b693987bebbf65c5977743733c1f34a809854d0c7043ea1b01f
    live_drive_exported_docx_sha256: ddf2ed556ca28e7a51510048e36f9985d2fa6f8bc611ff1b5ad68a90fd094022
    canonical_text_sha256: c825ff36626451ea5eeefdaa5141f825204408db6b5528b905b7ba9ff087e61e
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-03
    result_commit: d71c08a6da61713a1859bd9d1b8bb94652c41550
    result_tree: abc9e6001d2b079b53c49850062d9d38bbbc3a55
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_predecessor_and_full_regression: VERIFIED
  numbered_successor: P2-05

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_04_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_FilesystemRoot_ProcessExecutionRequest_ResourceAllocation_ToolCall_Event_Artifact_ContentRef_and_runtime_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_05_or_later_prompt_bodies_before_P2_04_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ToolCall_Event_ResourceAllocation_and_managed_process_identity
    - P2_01_authorized_root_path_streaming_atomic_IO_idempotency_and_Project_isolation_contracts
    - P2_02_direct_argv_explicit_shell_bounded_output_timeout_cancellation_process_ownership_and_truthful_policy_contracts
    - P2_03_exact_revision_dirty_source_preservation_candidate_isolation_Git_safety_diff_commit_and_explicit_push_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 23/51 - P2-04

  TITLE

  Replaceable Container and Isolated Runtime Adapter

  PHASE

  P2 - Universal execution fabric

  GOAL

  Execute Nodes inside bounded isolated/container runtimes without making Docker/Podman/Kubernetes/provider sandboxes part of kernel architecture.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 22/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Define IsolatedRuntimeSpec with immutable image/artifact ref, entrypoint/args, mounts, network policy, CPU/RAM/GPU/process limits, environment/secret refs, timeout.

  - Implement replaceable adapter create/start/execute/cancel/stop/inspect/collect/cleanup and at least one real/reference implementation.

  - Capture exact runtime/image/host/resource identity; enforce and separately report requested vs actually enforced limits.

  - Persist required outputs before cleanup; cancellation/cleanup releases resources; restart orphan reconciliation affects only proven-owned runtimes.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Define IsolatedRuntimeSpec with immutable image/artifact ref, entrypoint/args, mounts, network policy, CPU/RAM/GPU/process limits, environment/secret refs, timeout.

  - Implement replaceable adapter create/start/execute/cancel/stop/inspect/collect/cleanup and at least one real/reference implementation.

  - Capture exact runtime/image/host/resource identity; enforce and separately report requested vs actually enforced limits.

  - Persist required outputs before cleanup; cancellation/cleanup releases resources; restart orphan reconciliation affects only proven-owned runtimes.

  REQUIRED INTERFACES

  - IsolatedRuntimeSpec

  - IsolatedRuntimeAdapter

  - runtime identity/receipt

  DATA / STATE CHANGES

  - Runtime ownership/status/output refs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Valid isolated execution and output Artifact.

  - Forbidden mount/network policy, secret injection/redaction, resource limits, timeout/cancel/crash.

  - Cleanup and resource release.

  - Restart reconciles owned orphan and does not kill unknown runtime.

  - Reference adapter satisfies same contract.

  KPI

  - forbidden_mount_access=0

  - network_policy_bypasses=0

  - secrets_in_normal_evidence=0

  - resource_leaks_after_terminal=0

  - unknown_runtimes_killed=0

  - provider_runtime_types_in_kernel=0

  RESTORED LONG-FORM REQUIREMENTS

  ISOLATED RUNTIME AS REPLACEABLE TOOL

  Implement a generic IsolatedRuntimeAdapter for container/sandbox execution.

  Representative interface:

  create(spec)

  start(runtime)

  execute(runtime, request)

  cancel(execution/runtime)

  stop(runtime)

  inspect(runtime)

  collect_outputs(runtime)

  cleanup(runtime)

  describeRuntime()

  Do not put Docker/Kubernetes/provider SDK objects in kernel contracts.

  RUNTIME IDENTITY

  Persist enough runtime identity to distinguish generations:

  - adapter/implementation;

  - image/runtime digest;

  - runtime instance ID;

  - generation;

  - executor/Resource;

  - start time.

  Container ID is supplementary, not durable Run authority.

  IMMUTABLE IMAGE / ENVIRONMENT

  When image-based: bind image digest, not mutable tag alone.

  Record runtime/tool versions needed for evidence.

  MOUNTS

  Mount only authorized:

  - Workspace roots;

  - input Artifacts/content;

  - output roots;

  - secret mounts.

  Enforce read-only vs read-write.

  Do not expose host root, Docker socket, credential directories, or another Project.

  NETWORK POLICY

  Support semantic modes:

  NONE

  RESTRICTED

  PROJECT_POLICY

  Report actual enforcement.

  If a backend cannot enforce requested policy, it is not a compatible implementation.

  Do not label network disabled if DNS/host networking still escapes.

  RESOURCE LIMITS

  Record:

  - requested;

  - enforced;

  - observed

  for CPU/RAM/GPU/storage/process limits where supported.

  Unsupported limit must be explicit.

  SECRETS

  Use secret refs/mounts/runtime injection.

  Do not bake secrets into images, command lines, Events, checkpoints, or output Artifacts.

  OUTPUT CAPTURE

  Before runtime cleanup:

  - collect required output files;

  - hash/store;

  - create Artifact/Workspace receipt;

  - collect bounded logs/evidence.

  Cleanup must never run first and destroy uncaptured required outputs.

  CANCELLATION / TIMEOUT

  Terminate only owned runtime/processes, release resources, preserve already durable outputs.

  Late output from stale runtime generation must pass current fence/Run/Node authority before acceptance.

  ORPHAN RECOVERY

  After controller restart, inspect runtimes carrying Biella ownership labels/identities.

  Recover/cleanup only runtimes provably owned by the expected Project/Run/Node generation.

  Never kill unknown containers/processes "because they look old."

  TESTS

  - create/start/execute/stop;

  - exact image digest;

  - read-only and writable mounts;

  - cross-Project mount attempt;

  - network NONE verified where backend claims it;

  - unsupported network mode rejected;

  - CPU/RAM limits;

  - GPU visibility if available;

  - secret absent from output/metadata;

  - output capture before cleanup;

  - timeout/cancel;

  - orphan recovery after process restart;

  - unknown runtime not killed;

  - stale generation output rejected;

  - adapter replacement does not alter Task/Graph schema.

  This prompt provides the isolation mechanism used later by Workspace/production packs.

  USEFUL EVIDENCE — NON-GATING

  - Isolation is replaceable, outputs durable before cleanup, and enforcement claims match observed reality.

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

  PROMPT: 23/51 - P2-04

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
