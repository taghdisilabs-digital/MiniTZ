# 04 - BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v13

task:
  id: D03-01
  project: Biella Games
  section: post_d01
  class: hard_creation
  title: Production rendering, animation, VFX, and audio quality
  status: RUNNING
  runner: ACTIVE

  authority:
    - Mahdi Taghdisi latest explicit instruction
    - current observed execution state
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - projects/biella-games/docs/PRODUCTION.md

  continuity:
    git_identity_source: LIVE_GIT_READ_REQUIRED
    source_alignment_gate: VERIFIED_GITHUB_MAIN_PRE_EXECUTION_AND_POST_TURN_FAIL_CLOSED
    current_attempt: 299
    authoritative_task_session_id: 01a07de9-3d4f-79d3-bfe0-80bd52a21807
    model: gpt-reserve
    reasoning: max
    current_increment: STABLE_PSO_BUNDLE_COOK_AND_LOADING_DISPLAY_COLD_START_QUALIFICATION
    task_memory: /mnt/biella-extra/biella-runtime/codex-production/task-memory/D03-01.json
    task_memory_sha256: e6f178707cccaa1873108532cd1399ac41af1578fec34ba8cd5d3983e5321429
    compact_projection_sha256: c71f655c8766c22400507d6e326d88792d1e3affbae279c262eafdd3500030b1
    customer_handoff_running_customer_count: 0
    project_cell_execution_model: ISOLATED_PROJECT_CELL
    website_live_projection: DETERMINISTIC_READ_ONLY_NO_PERMANENT_AGENT

  preserve:
    - all completed predecessor tasks and exact accepted evidence
    - all independently verified D03-01 increments already achieved
    - current D03-01 source changes, PSO/loading outputs, native cook state and diagnostic evidence
    - exact current persistent task session and task memory
    - Engine P4-06 as INCOMPLETE_DEFERRED
    - one repository, one controller, one current task

  execution_directive:
    mode: RUN_D03_01_GPT_RESERVE_MAX
    execution: Continue the existing D03-01 session on GPT-Reserve max. Do not restart, reset, clean, stash, rollback, duplicate or broad-rerun verified work.
    current_operation: "Continuing the same native cook to completion before package/runtime validation."
    current_frontier: stable PSO bundle generation plus native loading-display cold-start qualification
    task_guide: projects/biella-games/docs/task-guides/D03-01.md
    acceptance: Preserve no-crash, exact lineage/handoff, no unmeasured loading frames and longest sampled loading-display static interval <1.0s. Diagnostic timeout controls never qualify production.
    next: After the current native cook finishes, inspect its exact validation/stable-key outputs, then stage/runtime-qualify only the smallest supported next boundary.
    progression: Advance only after real D03-01 durable closure to the earliest unfinished canonical task.

  routing:
    strong_route: gpt-reserve
    reasoning: max
    bounded_fallback: Spark then local Qwen for one small fresh-session technical outcome only when strong routing is unavailable
    bounded_whole_task_completion: FORBIDDEN
    quota_probe: FORBIDDEN

  external_project_isolation:
    running_customer_count: 0
    customer_cells: PAUSED_FOR_BIELLA_PRODUCTION
    broker_role: REPLACEABLE_PROJECT_CELL_RESOURCE_NOT_AUTHORITY
    cross_project_data_leakage: FORBIDDEN

  stop: Continue D03-01 until durable task closure, a new customer lease, or a newer Mahdi instruction changes execution state.
```
