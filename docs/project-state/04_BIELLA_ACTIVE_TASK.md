# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-02
  global_number: 21
  phase: P2
  title: Bounded Shell and Managed Process Execution
  state: READY_AFTER_P2_01_DURABLE_CLOSE
  exact_prompt:
    title: 21_P2-02_Bounded_Shell_and_Managed_Process_Execution.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/21_P2-02_Bounded_Shell_and_Managed_Process_Execution.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/21_P2-02_Bounded_Shell_and_Managed_Process_Execution.md.docx
    drive_id: 1FqsA8OT0qgDpNfGobSJcDudPVNpVkzAyCEeD1Ad0Ba8
    local_docx_sha256: 524b90ead900a0152e23f84d5ba34ca88cb9d6125fa33dc46f035c5717669f10
    live_drive_exported_docx_sha256: 28a7f420cf8c56096245889a10f9fed229deaa603b5510e718ddfb63909165a6
    canonical_text_sha256: c522c2ac560d615e5aab10dd9288da3faa0b11aeaa54cfb139a7c2e8e3f31e9f
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-01
    result_commit: bc728ce53160c8bbc0cad8ec0bbf9fb09db6b737
    result_tree: d8b6f53385b35e77e4a8bb01d2e734568107137f
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_predecessor_and_full_regression: VERIFIED
  numbered_successor: P2-03

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_02_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_FilesystemRoot_Project_Task_Run_Graph_Node_attempt_Artifact_ContentRef_ToolCall_Event_ResourceAllocation_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_03_or_later_prompt_bodies_before_P2_02_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ToolCall_Event_and_ResourceAllocation_identity
    - P2_01_authorized_root_path_streaming_atomic_IO_idempotency_and_Project_isolation_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 21/51 - P2-02

  TITLE

  Bounded Shell and Managed Process Execution

  PHASE

  P2 - Universal execution fabric

  GOAL

  Execute real tools/processes with executable+argv semantics, bounded output, timeout, cancellation, process ownership, resource policy, and exact ToolCall evidence.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 20/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Prefer executable + argument array over arbitrary shell strings; shell interpreter is explicit capability when required.

  - Define ProcessExecutionRequest with working root, environment allowlist/overrides, stdin ref, time/output limits, network policy, resource allocation.

  - Track durable process execution identity beyond PID; stream stdout/stderr to bounded ContentRefs with truncation evidence.

  - Cancellation terminates only owned process tree with escalation and truthful status; do not claim unsupported isolation enforcement.

  - Keep secrets out of environment evidence.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Prefer executable + argument array over arbitrary shell strings; shell interpreter is explicit capability when required.

  - Define ProcessExecutionRequest with working root, environment allowlist/overrides, stdin ref, time/output limits, network policy, resource allocation.

  - Track durable process execution identity beyond PID; stream stdout/stderr to bounded ContentRefs with truncation evidence.

  - Cancellation terminates only owned process tree with escalation and truthful status; do not claim unsupported isolation enforcement.

  - Keep secrets out of environment evidence.

  REQUIRED INTERFACES

  - ProcessExecutionRequest

  - managed process adapter

  - process result/status/failure taxonomy

  DATA / STATE CHANGES

  - ToolCall/process execution evidence and output refs.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Success/nonzero/missing executable.

  - Timeout and graceful/forced cancellation including child process.

  - Output overflow/truncation and large streaming output.

  - Environment secret filtering, working-directory escape, Project isolation.

  - Network/resource enforcement classified REAL/unsupported honestly.

  KPI

  - unbounded_process_output=0

  - timeouts_reported_success=0

  - cancelled_processes_reported_success=0

  - wrong_process_terminated=0

  - secret_environment_values_persisted=0

  - unsupported_isolation_claimed_enforced=0

  RESTORED LONG-FORM REQUIREMENTS

  MANAGED PROCESS CONTRACT

  Implement process execution through a bounded ProcessAdapter/managed process capability.

  Prefer request shape based on:

  executable

  argv[]

  working_directory_ref

  environment / secret refs

  stdin ref?

  stdout/stderr capture policy

  timeout

  resource limits

  network policy classification

  project/run/node attribution

  cancellation

  Avoid a shell command string unless an explicit shell capability is required.

  EXECUTABLE + ARGV

  Default to direct executable + argv to avoid quoting/injection ambiguity.

  If shell execution is supported, make it an explicit implementation/capability with exact shell/runtime identity.

  WORKING DIRECTORY

  Working directory must resolve through authorized FilesystemRoot/Workspace.

  Do not accept arbitrary host CWD.

  ENVIRONMENT

  Use allowlisted/inherited environment policy.

  Secrets should be injected through secret refs at runtime and must not be recorded in ToolCall/Event/log metadata.

  Record which non-secret environment/config identity affected execution when reproducibility requires it.

  STDOUT / STDERR

  Capture bounded output.

  Support:

  - streaming to Content Object for large output;

  - bounded preview/tail;

  - truncation metadata;

  - exact exit status;

  - timestamps.

  Do not keep unbounded output in database memory.

  Truncation must be explicit, not silent.

  TIMEOUT

  Timeout should terminate the owned process/process tree as supported.

  Record:

  - timeout fired;

  - termination method;

  - final/unknown child state.

  Do not mark timeout success because the parent shell exited.

  CANCELLATION

  Cancellation should terminate only processes owned by the current execution identity.

  Avoid PID-reuse attacks:

  - bind process start time/runtime identity/process group/job object;

  - never kill a new unrelated process merely because PID matches stale record.

  PROCESS TREE

  Where applicable, create process group/job/cgroup/container ownership so child processes do not escape cancellation/cleanup.

  Verify orphan behavior.

  RESOURCE LIMITS

  Integrate requested/enforced/observed:

  - CPU;

  - RAM;

  - GPU visibility where runtime adapter supplies it;

  - file size/process count;

  - timeout.

  Truthfully report unsupported limits.

  NETWORK POLICY

  If local process adapter cannot enforce network=NONE or RESTRICTED, report enforcement unsupported and use isolated runtime when Task requires it.

  Do not claim network isolation from convention.

  OUTPUT ARTIFACTS

  Generated files become Artifacts through Workspace/Filesystem capture, not merely stdout claims.

  FAILURE TYPES

  Support categories such as:

  - EXECUTABLE_NOT_FOUND;

  - SPAWN_FAILED;

  - EXIT_NONZERO;

  - TIMEOUT;

  - CANCELLED;

  - OUTPUT_LIMIT;

  - RESOURCE_LIMIT;

  - POLICY_DENIED.

  Preserve actual exit code/signal as metadata.

  TESTS

  - argv with spaces/metacharacters not shell-interpreted;

  - shell path only through explicit shell capability;

  - stdout/stderr;

  - output truncation;

  - large streamed output;

  - timeout;

  - cancellation;

  - child process tree termination;

  - PID reuse/ownership;

  - secret env absent from ledger;

  - unauthorized working directory;

  - resource limits;

  - network-policy enforcement classification;

  - concurrent processes;

  - generated Artifact verification;

  - process restart does not become durable Run authority.

  Process is a Tool implementation, not the execution state machine.

  USEFUL EVIDENCE — NON-GATING

  - Biella can run real tools safely enough for later Git/build/DCC/media adapters with truthful evidence.

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

  PROMPT: 21/51 - P2-02

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
