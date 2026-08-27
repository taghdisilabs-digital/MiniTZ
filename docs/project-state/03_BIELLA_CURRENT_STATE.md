# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v2
state_timestamp_local: "2026-08-28 01:57 Europe/Amsterdam"
state_timestamp_iso: "2026-08-28T01:57:05+02:00"
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history

authority:
  if_conflict:
    - CURRENT_EXECUTION_STATE
    - CURRENT_GITHUB_SOURCE
    - CURRENT_CANONICAL_DRIVE
    - VERIFIED_HISTORICAL_EVIDENCE
    - REFERENCE_OR_PLAN
    - INFERENCE
  correction_rule: invalidate_conflicting_assumption; recompute_only_affected_state; preserve_independently_valid_work

engine:
  repository: patrickminitz-web/biella-engine
  branch: main

  observed_remote:
    commit: 272ff5d70a45912ffc5ccf694752c6a2a79c2b91
    tree: 083cf48c342ee448176de69ebadc7c4acc163444
    observed_date: 2026-08-27
    evidence: CURRENT_GITHUB_SOURCE
    observation_context: codex_handoff_reference_repair_prepublication
    src_present: false
    root_package_json_present: false
    volatile_reobserve_before_next_write: true

  local:
    checkout_path: /root/biella/repos/biella-engine
    checkout_exists: UNKNOWN
    branch: UNKNOWN
    head: UNKNOWN
    tree: UNKNOWN
    upstream: UNKNOWN
    worktree_status: UNKNOWN
    newer_valid_work_present: UNKNOWN

  implementation:
    durable_prompts_complete: 0
    durable_prompts_total: 51
    phase: P0
    active_prompt: P0-01
    active_prompt_title: Clean-Room Migration Firewall
    p0_01_status: NOT_DURABLY_IMPLEMENTED_ON_RECORDED_REMOTE
    historical_spot_local_p0_01_counts_as_current: false
    reconstruct_historical_p0_01_from_prose: false

host:
  execution_root: /root/biella
  codex_home: /root/.codex
  canonical_checkout_path: /root/biella/repos/biella-engine

  recorded_identity:
    provider: AWS
    instance_id: i-077ab197788b547b0
    region: eu-west-3
    instance_type: c5a.4xlarge
    public_ip: 13.38.71.149
    private_ip: 172.31.13.170

  recorded_resources:
    os: Ubuntu_26.04.1_LTS
    kernel: 7.0.0-1011-aws
    logical_cpu: 16
    ram_gib: 30
    root_ebs_gib: 350
    swap_gib: 64
    swappiness: 10
    local_gpu_present: false
    gpu_capability_semantic_effect: none

  workstation_initialized: true
  reinstall_required: false

  volatile:
    reachable: UNKNOWN
    ssh_state: UNKNOWN
    github_push_auth: UNKNOWN

drive:
  canonical_root_id: 1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7

  required_live_paths:
    start_here: 00_START_HERE
    architecture: 10_ARCHITECTURE
    current_state: 20_CURRENT_STATE
    execution: 30_EXECUTION
    prompts: 40_PROMPTS
    migration: 50_MIGRATION
    website: biellawebsite

  active_prompt_identity:
    id: P0-01
    title: Clean-Room Migration Firewall
    drive_id: 1Rqj1Vs-V_6xhq90NJRS2hnjIQiVYkER6xG2dJ5CJ2oI
    restored_from_drive_revision: "1"

  inactive_reference_candidates:
    - title: Legacy Productive Reuse
      drive_id: 1P4uv74n0UI0JROi5J83ehrg9wDyWPg7FCt5dMMi9HTc
      state: INACTIVE_UNTIL_AFTER_P0_10_DURABLE_CLOSE
      active_authority: false
      default_retrieval_allowed: false

  prompt_inventory:
    P0: 10
    P1: 9
    P2: 12
    P3: 14
    P4: 6
    total: 51

migration:
  stage: PRE_P0_01
  firewall_implemented: false
  raw_history_active: false
  real_corpus_registered: false
  broad_extraction_allowed: false
  normal_retrieval_may_access_raw_history: false
  engine_memory_may_access_raw_history: false
  project_memory_may_access_raw_history: false

  after_p0_01:
    permitted:
      - register_verified_historical_multipart_objects_as_immutable_quarantine_inputs
      - record_part_identity_size_digest_provenance
    broad_extraction_allowed: false

  after_p0_10:
    permitted:
      - bounded_resumable_semantic_extraction
      - classification
      - contamination_removal
      - normalized_candidate_generation

  historical_material_rule:
    scope: HISTORICAL_EVIDENCE_OR_QUARANTINE
    direct_activation: false
    direct_copy_to_active_biella: false
    mechanical_rename_to_biella: false

website:
  program: BIELLA_UNIVERSE_OPTION_C
  public_target: biellagames.dev
  execution_state: WAITING_FOR_P0_01_CLOSE
  first_separate_task_after_p0_01: BU-01
  run_in_same_p0_01_session: false
  universal_engine_kernel_scope: false

volatile_reobserve_before_next_write:
  - current_host_reachability
  - current_ssh_state
  - canonical_checkout_existence
  - local_branch
  - local_head_tree_upstream
  - local_worktree_status
  - newer_valid_local_implementation
  - current_remote_main_commit_tree
  - github_push_auth_when_publication_required

next_boundary:
  id: P0-01
  title: Clean-Room Migration Firewall
  prompt_drive_id: 1Rqj1Vs-V_6xhq90NJRS2hnjIQiVYkER6xG2dJ5CJ2oI

next_transition:
  - connect_to_existing_workstation
  - preserve_/root/biella_exactly
  - inspect_checkout_state_once
  - if_canonical_checkout_absent_create_exactly_one_checkout_from_canonical_github_repo
  - preserve_genuine_newer_valid_local_work_if_present
  - otherwise_use_current_observed_github_main
  - execute_P0_01_only
  - run_required_focused_tests_regressions_typecheck_build
  - commit_and_push
  - remotely_read_back_exact_commit_and_tree
  - update_Drive_continuity_and_current_state
  - stop_at_P0_01_boundary

prohibited_next_transition:
  - reinstall_host
  - rerun_vps_configurator
  - create_or_migrate_to_/srv/biella
  - duplicate_checkout
  - broad_historical_backup_extraction
  - raw_MiniTZ_activation
  - start_P0_02_before_P0_01_durable_close
  - start_BU_01_in_same_P0_01_session
  - install_gpu_stack_on_cpu_host_for_completeness
  - add_unrequested_security_architecture
  - add_approval_or_reviewer_systems
  - treat_research_or_prompt_pack_documents_as_implemented_engine_code
```
