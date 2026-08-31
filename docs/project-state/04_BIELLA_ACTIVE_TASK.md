# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

active_task:
  id: P3-07
  global_number: 38
  phase: P3
  title: Animation Production Pack
  state: ACTIVATED_PROMPT_NOT_LOADED_OR_COMPILED
  predecessor: P3-06
  predecessor_source_commit: e3c0ecb1ba70c2048f12198533f904da7e7504ed
  predecessor_result_commit: 78005b0a30fa7002eed8019a588731551e3d2c6b
  predecessor_result_tree: 6737d32d10feae0dcaeb4024ece00f3aa64b20f0
  predecessor_github_readback: EXACT_COMMIT_TREE_AND_SIX_BLOBS_CONFIRMED
  execution_authorized: true

exact_prompt:
  title: Animation Production Pack
  drive_id: 1GzQxmCrvIv10WVv0KdoPxlKi7l79J2J6cS-zvoOv-Dk
  status: NOT_LOADED_OR_COMPILED
  rule: obtain_exact_P3_07_prompt_body_only_when_execution_begins

P3_05_durable_close:
  source_commit: e228a7bb6db6f94af15dde4a8fb110b028eddbed
  result_commit: 929d2b3269b6fcc38c75d90aece802dfdaf9fadf
  result_tree: e9bc6bdb156f5ac82039a613b03cb9643ea1125a
  github_readback: EXACT_COMMIT_TREE_AND_ALL_NINE_BLOBS_CONFIRMED
  recovery_archive: REUSED_WITHOUT_REHASH
  validators:
    pack_contract: COMPLETE
    real_output_truth: COMPLETE
    isolation_recovery: COMPLETE
  final_gate: 72_TESTS_GREEN; STRICT_MYPY_9_PATHS_GREEN; COMPILEALL_GREEN; DIFF_CHECKS_GREEN; CLEAN_WHEEL_INSTALL_IMPORT_GREEN
  wheel: biella_engine-0.1.0-py3-none-any.whl
  wheel_sha256: fc09a1d9543b2111df4ed41ad17db796c0570d8c67d16e4f28ce3b261a9472dc
  real_runtime: Blender_5.0.1

P3_06_durable_close:
  source_commit: e3c0ecb1ba70c2048f12198533f904da7e7504ed
  result_commit: 78005b0a30fa7002eed8019a588731551e3d2c6b
  result_tree: 6737d32d10feae0dcaeb4024ece00f3aa64b20f0
  github_readback: EXACT_COMMIT_TREE_AND_SIX_BLOBS_CONFIRMED
  contract: 16_CHARACTER_CAPABILITIES_12_ROLES_CharacterSpecification_CharacterRigRef
  real_runtime: Blender_5.0.1
  real_proof: NON_HUMANOID_RIG_SKIN_DEFORM_EXPORT_REOPEN
  validators: STALE_MESH_SKELETON_WEIGHT_PROJECT_ISOLATION_WORKER_LOSS_EXACT_ONCE_RECOVERY
  final_gate: 25_TESTS_GREEN_IN_448.18_SECONDS; STRICT_MYPY_6_PATHS_GREEN; COMPILEALL_DIFF_CLEAN_WHEEL_IMPORT_GREEN
  wheel_sha256: 9ee31926b63b651561d723dfbd57c541ba38f4f6679429f7444bd7811c0bdf6a

owner_priority:
  standing_order: preserve_current_or_recoverable_long_running_productive_work_before_any_remote_sync_restore_reset_checkout_merge_or_host_replacement
  remote_newer_is_not_permission_to_replace_unpreserved_execution_work: true
  current_sequence:
    - retain_P3_05_and_P3_06_durable_close_evidence
    - load_and_compile_P3_07_exact_prompt_when_execution_begins

execution_host:
  current_host:
    provider: AWS
    instance_id: i-0056cad38b67415c1
    region: eu-west-3
    instance_type: t2.xlarge
    public_ipv4: 13.38.217.245
    private_ipv4: 172.31.47.69
    state: RUNNING
    os: Ubuntu_26.04.1_LTS
    kernel: 7.0.0-1011-aws
    resource_note: LOWER_RESOURCE_REPLACEMENT_HOST
  previous_host_state: DESTROYED
  previous_host_paths_are_authority: false
  canonical_root: /root/biella
  canonical_codex_home: /root/.codex
  canonical_checkout: /root/biella/repos/biella-engine
  checkout_observation:
    worktree_before_fetch: CLEAN
    head_before_fetch: e228a7bb6db6f94af15dde4a8fb110b028eddbed
    origin_main_after_fetch: ce10d326a56e46e9fbb51dd4ba22610ba7d9f011
    head_after_fast_forward: ce10d326a56e46e9fbb51dd4ba22610ba7d9f011
    worktree_after_fast_forward: UNKNOWN_NOT_REOBSERVED
    fast_forward_scope: ONLY_03_04_AND_BIELLA_DRIVE_LIVE_MANIFEST
  bootstrap_authorities:
    github_repository: patrickminitz-web/biella-engine
    github_branch: main
    drive_current_state_id: 1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4
    drive_active_task_id: 1liutA8evH6rPjk-U4tgR13l_kqBrx-DF
    drive_recovery_archive_id: 1Y7aEStdGbCK5a0N9iA8s41l2olTWOUAE
  rule: current_execution_state_is_preserved_first; GitHub_and_Drive_are_durable_authorities_but_do_not_override_unpreserved_newer_productive_work

expected_recovered_path_set:
  modified_tracked:
    - src/biella/__init__.py
    - src/biella/process.py
    - src/biella/production_pack.py
    - tests/test_p2_02_process.py
  untracked_p3_05:
    - src/biella/_blender_three_d_driver.py
    - src/biella/three_d_pack.py
    - src/biella/three_d_tool.py
    - tests/test_p3_05_three_d_pack.py
    - tests/test_p3_05_three_d_real.py
  rule: path_set_is_integrity_expectation_only; recovery_evidence_controls_bytes

codex_execution_contract:
  language: biella.codex.end_to_end/v2
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  objective: maximize_durable_progress_per_model_token_without_lowering_engineering_or_validation_quality
  planning_method:
    superpowers_used_for: decomposition_and_plan_quality
    superpowers_is_runtime_dependency: false
    biella_authority_overrides_generic_skill_workflow: true
    no_permanent_reviewer_or_manager_hierarchy: true
  normal_context:
    - 03_BIELLA_CURRENT_STATE.md
    - 04_BIELLA_ACTIVE_TASK.md
    - exact_active_numbered_prompt
    - directly_touched_source_and_interfaces
  context_expansion_only_when_required:
    00: operational_edge_case
    01: architecture_or_semantic_scope
    02: sequence_or_plan_ambiguity
    05: exact_prompt_location
    06: source_evidence_or_migration_resolution
  do_not_preload:
    - old_Codex_sessions_after_recovery_is_complete
    - recovery_archive_after_exact_worktree_restoration
    - unrelated_prompt_bodies
    - historical_MiniTZ_material
    - broad_Drive_Git_or_filesystem_inventory
  tool_policy:
    use_only_task_relevant_tools: true
    AWS_MCP_default: OFF_FOR_NORMAL_CODE_EXECUTION
    Cloudflare_MCP_default: OFF
    NVIDIA_skill_bundle_default: OFF_UNLESS_REAL_GPU_SUBPATH_REQUIRES_IT
    generic_template_and_unrelated_workflow_bundles_default: OFF
  observation_policy:
    inspect_exact_state_once: true
    reuse_verified_outputs: true
    reread_unchanged_files: false
    reobserve_only_if_materially_invalidated: true
  output_policy:
    prefer_exact_ranges_symbols_paths_and_digests: true
    bound_terminal_output: true
    prohibit_binary_asset_dump_into_model_context: true
    prohibit_full_large_diff_dump_unless_required: true
    worker_handoffs_are_compact_structured_results_not_transcripts: true
  validation_policy:
    development_funnel:
      - exact_new_or_failing_test
      - focused_active_task_module
      - directly_affected_regression
    final_task_derived_gate: ONCE_AFTER_IMPLEMENTATION_STABILIZES
    after_final_failure: fix_smallest_affected_boundary_then_rerun_only_invalidated_gates
  usage_policy:
    check_status_before_execution: true
    usage_low_behavior: finish_current_node; run_its_exact_validation; persist_coherent_work; record_ready_blocked_nodes; do_not_start_new_node
    usage_exhaustion_is_not_invalidation: true
    session_or_model_restart_is_not_invalidation: true

multi_ai_execution:
  principle: workers_execute_exact_Graph_Nodes; workers_do_not_independently_consume_an_informal_TODO_list
  controller_authority:
    - exactly_one_numbered_prompt_active
    - compile_or_revise_Graph_from_exact_prompt_and_current_source
    - allocate_READY_nodes
    - enforce_dependency_resource_and_side_effect_constraints
    - integrate_results
    - authorize_durable_close
  worker_identity:
    exact_fields:
      - task_ref
      - graph_ref
      - graph_revision
      - node_ref
      - objective
      - required_capabilities
      - dependencies
      - exact_inputs
      - readable_context
      - owned_write_paths
      - allowed_tools
      - resource_requirements
      - side_effect_authority
      - output_contract
      - evidence_requirements
      - validation_command
      - idempotency_key
      - lease_owner
      - fence
  duplicate_prevention:
    one_current_owner_per_node: true
    atomic_claim_lease_fence_required: true
    overlapping_live_write_ownership: forbidden
    already_completed_exact_node: reuse_unless_invalidated
    validator_nodes_are_read_only: true
    repair_nodes_are_created_from_exact_failures_only: true
  graph_revision_policy:
    revisions_are_immutable: true
    discovered_required_work: compile_new_revision
    preserve_unaffected_completed_nodes: true
    later_prompt_work: record_for_future; do_not_execute
  agent_policy:
    default_parallel_workers: 0
    fan_out_only_after_M0_gap_map: true
    parallel_workers_only_if: independent_dependencies_and_nonoverlapping_side_effects_and_material_wall_clock_benefit
    no_mandatory_planner_critic_validator_chain: true
    no_permanent_named_agent_hierarchy: true

current_frontier:
  state: P3_07_ACTIVATED_NOT_STARTED
  P3_05_durable_close_complete: true
  P3_06_durable_close_complete: true
  P3_07_prompt_loaded: false
  P3_07_prompt_compiled: false
  P3_07_execution_authorized: true

activation_boundary:
  P3_07_authorized: true
  P3_07_prompt_loaded: false
  P3_07_graph_compiled: false
  rule: compile_only_from_exact_P3_07_prompt_and_accepted_source
  predecessor_evidence: P3_06_durable_close_mapping_above
```
