# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-01
  global_number: 20
  phase: P2
  title: Universal Filesystem Capability Adapter
  state: READY_AFTER_P1_09_DURABLE_CLOSE
  exact_prompt:
    title: 20_P2-01_Universal_Filesystem_Capability_Adapter.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/20_P2-01_Universal_Filesystem_Capability_Adapter.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/20_P2-01_Universal_Filesystem_Capability_Adapter.md.docx
    drive_id: 1cNVwywxtOOlbmNkiZRBZn6jhP_WlnTleDVTieWRXw5U
    local_docx_sha256: 7b0adb20f74effd0b20f1f55b3220b6da11dac3bec3c521258a3f2e2063d9a41
    live_drive_exported_docx_sha256: f4e6dfdf6c3bc9059c33384f72fa79f4837b314deee91a7e7acffba26eae0b8d
    canonical_text_sha256: a9a7f0c5246eec864eae3f44f6171ef389129b602141f7fb74d33f8655c34534
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P1-09
    result_commit: 3508942cb7527dd0db43d19ae6ce31d937434192
    result_tree: 9126aa1f965b027c4f922e95f52ce35d2b3c0988
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_functional_type_build_installed_restart_and_full_regression: VERIFIED
  numbered_successor: P2-02

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_01_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_Task_Run_Graph_Node_attempt_Artifact_ContentRef_ToolCall_Event_CapabilityImplementation_RoutingDecision_Scheduler_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_02_or_later_prompt_bodies_before_P2_01_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_and_Resource_identity
    - P1_09_provider_neutral_layered_routing_policy_egress_decision_and_scheduler_revalidation_contracts
    - all_earlier_isolation_provenance_durability_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 20/51 - P2-01

  TITLE

  Universal Filesystem Capability Adapter

  PHASE

  P2 - Universal execution fabric

  GOAL

  Give Biella bounded real filesystem I/O through replaceable adapters while preserving authorized roots, exact byte identity, Project scope, streaming, cancellation, and Artifact provenance.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 19/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Register filesystem.read/write/list/stat/mkdir/copy/move/remove capabilities.

  - Define authorized FilesystemRoot with canonical path, Project/global scope, and READ_ONLY/READ_WRITE/TEMPORARY modes.

  - Reject traversal, absolute-root escape, symlink/junction escape, unsafe special targets, and cross-project root binding.

  - Stream large reads/writes; durable outputs become ContentRefs/Artifacts, never paths-as-authority.

  - Attribute operations through ToolCall/Event and integrate cancellation/partial-output handling.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Register filesystem.read/write/list/stat/mkdir/copy/move/remove capabilities.

  - Define authorized FilesystemRoot with canonical path, Project/global scope, and READ_ONLY/READ_WRITE/TEMPORARY modes.

  - Reject traversal, absolute-root escape, symlink/junction escape, unsafe special targets, and cross-project root binding.

  - Stream large reads/writes; durable outputs become ContentRefs/Artifacts, never paths-as-authority.

  - Attribute operations through ToolCall/Event and integrate cancellation/partial-output handling.

  REQUIRED INTERFACES

  - FilesystemAdapter

  - FilesystemRoot

  - filesystem CapabilityImplementations

  DATA / STATE CHANGES

  - Registered roots and ToolCall/Artifact evidence.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Valid read/write/copy/move/remove/list/stat.

  - Traversal and symlink escapes rejected.

  - Read-only root rejects write.

  - Large streaming file path.

  - Cancellation/partial output not accepted.

  - Project Beta cannot access Alpha root.

  KPI

  - authorized_root_escapes=0

  - unauthorized_writes=0

  - digest_mismatches_accepted=0

  - partial_writes_claimed_success=0

  - large_files_forced_full_memory=0

  - unattributed_filesystem_operations=0

  RESTORED LONG-FORM REQUIREMENTS

  FILESYSTEM AS A CAPABILITY ADAPTER

  Implement filesystem work behind a Project/Run/Node-attributed FilesystemAdapter, not direct arbitrary host filesystem access from agents/models.

  Representative operations:

  read

  write

  list

  stat

  mkdir

  copy

  move

  remove

  Keep the interface extensible without leaking one OS filesystem API into kernel contracts.

  CONTROLLED ROOT

  Define FilesystemRoot or equivalent:

  - project_id / execution scope;

  - logical root identity;

  - physical path/mount hidden behind adapter;

  - mode: read-only/read-write as appropriate;

  - policy/ownership metadata.

  A Node receives authorized roots, not arbitrary host path authority.

  PATH CANONICALIZATION

  Before I/O:

  - reject traversal outside root (..);

  - normalize separators safely;

  - handle absolute paths;

  - reject NUL/malformed paths;

  - consider case sensitivity/normalization on supported platforms.

  Do not use simple string prefix checks as the sole sandbox.

  SYMLINK / JUNCTION / RACE SAFETY

  Protect against:

  - symlink escape;

  - junction/reparse-point escape where platform applies;

  - symlink swapped between validation and open;

  - parent directory replaced.

  Use secure open/realpath/dirfd-style techniques available on the target platform and document unsupported protections honestly.

  READ

  Read should:

  - enforce authorized root;

  - stat/size bound;

  - stream large content;

  - optionally place durable output into Content Store/Artifact when Task requires durability;

  - record ToolCall/operation evidence.

  Do not load arbitrarily large files into memory.

  WRITE

  Support safe atomic write semantics where required:

  - write temp within authorized target;

  - fsync/close as appropriate;

  - verify bytes/digest;

  - atomic replace/rename;

  - create Artifact/ContentRef when durable output.

  Partial write must not be reported as accepted final Artifact.

  COPY/MOVE/REMOVE

  Enforce source and destination roots independently.

  External/Project-authoritative deletion/mutation follows Task side-effect authority.

  Do not let candidate Workspace tooling delete protected Project source unintentionally.

  ARTIFACT INTEGRATION

  Filesystem path is execution location, not Artifact identity.

  Durable meaningful output: path -> exact bytes -> ContentRef -> Artifact.

  CANCELLATION

  Long copy/read/write operations should be cancellable where practical. Cancellation must leave output state explicit; partial file is not valid final output unless Task explicitly accepts partial evidence.

  PROJECT ISOLATION

  Beta cannot use Alpha root/path even if underlying host paths are guessable.

  TESTS

  - permitted read/write/list/stat;

  - path traversal;

  - absolute escape;

  - symlink escape;

  - symlink race where testable;

  - cross-Project root;

  - read-only root mutation rejected;

  - atomic write;

  - interrupted write;

  - large streamed file;

  - exact ContentRef/Artifact;

  - copy/move between authorized roots;

  - unauthorized remove;

  - cancellation;

  - restart/workspace rematerialization path changes do not alter Artifact identity.

  The filesystem adapter must be useful for real work while remaining subordinate to Project/Task authority.

  USEFUL EVIDENCE — NON-GATING

  - Real controlled filesystem work produces exact Artifacts while OS/path mechanics remain adapter-local.

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

  PROMPT: 20/51 - P2-01

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
