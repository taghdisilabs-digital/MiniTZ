# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v3

task:
  id: P2-03
  global_number: 22
  phase: P2
  title: Exact-Revision Git Repository Adapter
  state: READY_AFTER_P2_02_DURABLE_CLOSE
  exact_prompt:
    title: 22_P2-03_Exact_Revision_Git_Repository_Adapter.md.docx
    local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P2/22_P2-03_Exact_Revision_Git_Repository_Adapter.md.docx
    drive_path: gdrive:BiellaEngine/40_PROMPTS/P2/22_P2-03_Exact_Revision_Git_Repository_Adapter.md.docx
    drive_id: 1508K_PyL7nVdCdvlRUgg0h4L-_whON9Sbyx07u0wYQY
    local_docx_sha256: c39b2c17b8e5185b257a835efc337447a1f1b70ad94b08ffe832610be6ee098f
    live_drive_exported_docx_sha256: 83a3d2d6452779e115154909a61006a709857b75301c2674b795c9ca8ba72850
    canonical_text_sha256: dbd1c170af28df6546246e01a677dc687fce16d60ea6fc5343cded76ed29817e
    canonical_text_extraction: pandoc_plain_wrap_none
    local_and_live_drive_text_equal: true
  numbered_predecessor:
    id: P2-02
    result_commit: 0e61e36865339347ff52213e04ef22e21d44de6f
    result_tree: dafa639eee961daa89a04d3c69d0a88d2c27f6b3
    remote_readback: VERIFIED
    remote_required_paths_and_bytes: VERIFIED
    focused_type_build_installed_restart_predecessor_and_full_regression: VERIFIED
  numbered_successor: P2-04

execution_boundary:
  start_only_after_predecessor_durable_close: satisfied
  load_only:
    - exact_P2_03_canonical_prompt
    - current_state_and_active_task_continuity
    - accepted_Project_FilesystemRoot_ProcessExecutionRequest_ToolCall_Event_Artifact_ContentRef_and_repository_interfaces_directly_required
    - directly_touched_source_and_task_scoped_tests
  do_not_open:
    - P2_04_or_later_prompt_bodies_before_P2_03_durable_close
    - unrelated_historical_backup_or_legacy_material
  preserve:
    - exact_Project_Task_Run_Graph_Node_attempt_fence_Artifact_ContentRef_ToolCall_Event_ResourceAllocation_and_managed_process_identity
    - P2_01_authorized_root_path_streaming_atomic_IO_idempotency_and_Project_isolation_contracts
    - P2_02_direct_argv_explicit_shell_bounded_output_timeout_cancellation_process_ownership_and_truthful_policy_contracts
    - all_earlier_isolation_provenance_durability_routing_scheduler_and_quarantine_firewall_contracts

canonical_prompt_text: |-
  PROMPT 22/51 - P2-03

  TITLE

  Exact-Revision Git Repository Adapter

  PHASE

  P2 - Universal execution fabric

  GOAL

  Operate on Git repositories from exact revisions, preserve dirty/unrelated user state, use isolated candidate workspaces, and record exact diff/commit/tree identities without implicit push.

  CURRENT VERIFIED STATE

  - Inspect the actual Biella repository/worktree before editing: repo, branch, source commit/tree, dirty state, migrations, tests, AGENTS/policy/instruction files, and accepted interfaces.

  - Reuse valid earlier implementation/results. Inspect only dependencies actually needed by this task; missing handoff paperwork is not a blocker.

  - If expected interface names differ from accepted existing equivalents, reconcile by semantics and record the mapping rather than duplicating architecture.

  SOURCE ARCHITECTURE

  - Execute real filesystem/process/Git/runtime/network/model/browser/database/retrieval/workspace work through replaceable adapters with Task-derived validation.

  - Apply current Biella project instructions and the kernel semantics relevant to this task. Do not add legacy blockers, hard QA gates, or artificial limits.

  DEPENDENCIES

  - Prompt 21/51 implemented result/interfaces when required by this task; missing paperwork is not a blocker.

  - All earlier accepted contracts used by this task; inspect the repository instead of assuming interface names.

  INPUTS

  - Current Biella source and durable state.

  - The exact Task/prompt requirements below.

  - Previous prompt continuation evidence and exact IDs/refs needed by this task.

  - Available real infrastructure/tools; unavailable integrations must be classified honestly rather than mocked as real.

  IN SCOPE

  - Define RepositoryRef/RepositoryWorkspaceRef with exact full commit/tree.

  - Inspect HEAD/status/dirty state; candidate changes use isolated worktree/workspace rather than destructive reset.

  - Use managed process adapter and control hooks, filters, external diff/textconv, credential prompts, submodules/LFS/symlinks according to supported policy.

  - Capture diffs/untracked Artifact refs; commits record parent/new commit/tree; push is a separate explicit external side effect.

  - Revalidate stale source where current-base authority matters.

  OUT OF SCOPE

  - Do not implement later numbered prompts, unrelated architecture, or optional domain/provider specializations.

  - Do not weaken earlier isolation, migration, exact-identity, fencing, durability, validation, or evidence guarantees.

  REQUIRED IMPLEMENTATION

  - Define RepositoryRef/RepositoryWorkspaceRef with exact full commit/tree.

  - Inspect HEAD/status/dirty state; candidate changes use isolated worktree/workspace rather than destructive reset.

  - Use managed process adapter and control hooks, filters, external diff/textconv, credential prompts, submodules/LFS/symlinks according to supported policy.

  - Capture diffs/untracked Artifact refs; commits record parent/new commit/tree; push is a separate explicit external side effect.

  - Revalidate stale source where current-base authority matters.

  REQUIRED INTERFACES

  - RepositoryRef

  - GitAdapter

  - candidate workspace/worktree APIs

  - diff/commit/push receipts

  DATA / STATE CHANGES

  - Repository/workspace refs and commit/tree/diff evidence.

  FAILURE BEHAVIOR

  - Fail closed on scope/identity/authority/integrity mismatch. Preserve durable evidence, report the real cause, and do not fabricate success or missing facts.

  - If a dependency/infrastructure limitation blocks only one subpath, record it and continue unaffected required work when safe.

  CONCURRENCY / RECOVERY REQUIREMENTS

  - Use the existing Graph/Scheduler/resource model; independent work may proceed concurrently only when dependencies, side effects, and resource constraints permit.

  - Recovery must preserve already verified durable work and reject stale owners/results.

  TESTS

  - Clean/dirty repo preservation.

  - Exact commit checkout/candidate change/diff/commit.

  - Stale base explicit.

  - Unsafe hooks/filters/path traversal/.git mutation rejected.

  - Explicit safe test push only when Task authorizes.

  - Project isolation.

  KPI

  - repo_mutations_without_exact_base=0

  - unrelated_dirty_state_destroyed=0

  - source_checkout_modified_by_candidate=0

  - unsafe_Git_config_execution=0

  - implicit_pushes=0

  - unobserved_commit_claims=0

  RESTORED LONG-FORM REQUIREMENTS

  EXACT REPOSITORY IDENTITY

  Implement Git as a replaceable repository capability.

  Represent repository/source identity with exact:

  - repository ref/location;

  - commit SHA;

  - tree SHA where useful;

  - submodule refs where relevant;

  - worktree/candidate identity;

  - Project scope.

  Do not use mutable branch alone as Task source authority.

  ADAPTER CAPABILITIES

  Support bounded operations equivalent to:

  - inspect repository;

  - status;

  - diff;

  - read exact source;

  - create candidate worktree;

  - apply/edit candidate;

  - commit candidate;

  - fetch when Task/network policy permits;

  - push only under explicit external/Project side-effect authority.

  Git CLI may be used through P2-02; Git itself remains adapter implementation.

  DIRTY STATE

  Before creating candidate:

  - detect tracked/staged/unstaged/untracked state;

  - preserve unrelated user work;

  - do not reset/clean/rebase user state silently.

  If exact base cannot be materialized safely from dirty shared checkout, use isolated worktree/clone/candidate workspace.

  CANDIDATE WORKTREE

  Preferred mutation: exact base commit/tree -> isolated worktree -> changes.

  Capture:

  - base commit/tree;

  - current HEAD;

  - staged diff;

  - unstaged diff;

  - untracked files;

  - resulting candidate tree/commit.

  Do not mutate protected source checkout unless Task explicitly authorizes Project write.

  PATCH / APPLY SAFETY

  Bind patches/diffs to expected base when possible.

  Reject stale/context-mismatched patch rather than applying partially and claiming success.

  GIT CONFIG / HOOKS / FILTERS

  Repository behavior may be affected by:

  - hooks;

  - clean/smudge filters;

  - .gitattributes diff/textconv;

  - LFS;

  - submodules;

  - symlinks.

  Do not execute uncontrolled hooks/filters from untrusted repository merely because git supports them. Use safe config/environment and record limitations.

  SUBMODULES / LFS

  If Task/repository relies on them:

  - preserve exact identities;

  - obey network/credential policy;

  - do not silently omit required content.

  If unsupported/unavailable, fail/mark limitation honestly.

  COMMIT

  When Task requires commit:

  - exact candidate tree;

  - coherent message;

  - author identity according to Project/runtime policy;

  - verify commit/tree after creation.

  No push is implied.

  PUSH

  git push is external side effect.

  Require explicit Task authority and destination/ref identity.

  Do not force-push unless explicitly authorized.

  TESTS

  - inspect exact commit/tree;

  - dirty repository preserved;

  - isolated candidate worktree;

  - changed file and untracked file captured;

  - stale patch rejection;

  - commit exact tree;

  - hook/filter safety fixture;

  - symlink path behavior;

  - submodule/LFS fixture where practical;

  - fetch governed by network policy;

  - push denied on read-only Task;

  - Project Beta cannot use Alpha repository ref;

  - worker/process loss does not lose persisted candidate diff/commit.

  Git source history is Project data. legacy donor Git ancestry must not become Biella history.

  USEFUL EVIDENCE — NON-GATING

  - Repository production is exact-revision and candidate-safe; commit/push claims require observation.

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

  PROMPT: 22/51 - P2-03

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
