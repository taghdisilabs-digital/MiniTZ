# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v6

active_task:
  id: P4-04
  global_number: 49
  phase: P4
  title: Cache, Locality, Residency and Resource Placement Learning
  state: ACTIVATED_PROMPT_NOT_LOADED_OR_COMPILED
  predecessor: P4-03
  predecessor_result_commit: ad2f46a242e6fca216b767fb7e46aaacc1e2ca17
  predecessor_result_tree: c33516fad72499d9ba8af434f1a23741d63c3386
  predecessor_github_readback: EXACT_COMMIT_TREE_AND_EIGHT_BLOBS_CONFIRMED
  execution_authorized: true
  standing_authorization: true
  supersedes_continuity: false
  legacy_spark_prep_dependency: false

exact_prompt:
  title: Cache, Locality, Residency and Resource Placement Learning
  drive_id: 1ND5zkrv09Jwxs8EDIRQwJ_QGRWAKP0u8lzfjA0ZJ0D4
  status: NOT_LOADED_OR_COMPILED
  rule: obtain_exact_P4_04_prompt_body_only_when_execution_begins

prior_durable_through_P3_08:
  status: VERIFIED
  latest_result_commit: 0da64ebea6aeb0a69fb73ae8c67317fd8d86c109
  latest_result_tree: da7860a8c0890d3ae82b0ae3d4c9b545efa85759

prior_durable_through_P3_09:
  status: VERIFIED
  latest_result_commit: b23195b82e20a568f22b8ebc7be401d5bb95c97e
  latest_result_tree: c35e5a1f38d6c938828ec0556706a3ed0e3ca93a

prior_durable_through_P3_10:
  status: VERIFIED
  latest_result_commit: b7fe1a20caabeda053b1fb8c42d01a7da999b34e
  latest_result_tree: 5b94821f1fb98a9993d384e9a2d034bcff843376

prior_durable_through_P3_11:
  status: VERIFIED
  latest_result_commit: 72bd7d78f7fe5ff53cac003cfeddcd91188fcfe3
  latest_result_tree: 21ed73b5e2f55ce21a77ce28f40d5b415f159c0b

prior_durable_through_P3_12:
  status: VERIFIED
  latest_result_commit: 3dcc194253bb54d2a171cf7230877af95231ebe7
  latest_result_tree: 8835d92e6651ea13ec5f02b87487f0520fb7bae6

P3_13_durable_close:
  result_commit: 27f8958aa3f6a2847b5d506580f04bcc904db98e
  result_tree: c92b5e322259ccd7619a7d51dbe94f270942b10e
  github_readback: EXACT_COMMIT_TREE_AND_EIGHT_PATHS_CONFIRMED
  final_gate: 12_TESTS_GREEN_IN_147.41_SECONDS; STRICT_MYPY_7_FILES_SUCCESS; FIVE_PROMPT_KPIS_ZERO
  optional_generative_path: NOT_RUN
  wheel_sha256: abd3933d701e7dd33c0f6b2d40bc947e2d84ac565a90bf76af3aad46008f2810

P3_14_durable_close:
  result_commit: 68c00a4e1464206c2a69e14f8b8049fe29438fb8
  result_tree: 2516591d9c3f893c9da583c06a9e7e9eb6bb0882
  github_readback: EXACT_COMMIT_TREE_AND_EIGHT_PATHS_CONFIRMED
  status: COMPLETE; P3_READY_FOR_P4
  qualification: 17_TESTS_GREEN_IN_59.01_SECONDS_WITH_LIVE_CLOUDFLARE_KV_ENABLED; STRICT_MYPY_8_FILES_SUCCESS; SIX_PROMPT_KPIS_ZERO
  wheel_sha256: 4a1f4de335a505707b38f991f9fd83cd60c9bfc8dfa9f2e9d62dbc488f46409c
  delivery_contract: DELIVERY_AT_1_0_0_15_CAPABILITIES_LAZY_EXPORTS_DETERMINISTIC_PACKAGES_FULL_REOPEN_DIGEST_PATH_PERMISSION_SYMLINK_VALIDATION_BOUNDED_SECRET_SCAN_SECRET_REF_HMAC_POST_VERIFY
  external_authority: EXACT_TASK_NODE_RUN_FENCE_IMMUTABLE_IDEMPOTENT_REMOTE_KEYS_FULL_SHA_READBACK_VERIFICATION_FAILURE_OUTCOME_UNKNOWN_DURABLE_RECEIPT
  cloudflare_kv_namespace: biella-p3-14-delivery
  cloudflare_kv_namespace_id: f35ac3a280eb4b1387f5d2d403fc3266
  real_cross_domain_proof:
    software_project: prj_3cc1bf23fc5546e19379b1f8c2baeff9
    software_package_key: biella/packages/2ff85b54f0909de58f477b49d42f3b6585b2fa296dc7fc9abf589c8bcab4ce83
    software_receipt_digest: f5089f4ee6f12785fd9a443e52bc9c32f47a7230fa97bc58b317a7c3c84021e8
    video_project: prj_c4ab734ec30b4db482b30bd5b35cb77b
    video_package_key: biella/packages/8efefe37f544462f24ead38938b703eb2a1dad22f72f2b3609691d02363df45e
    video_receipt_digest: 274801d7eaeffea49d34780e8a14e1e61511eeecefb30a7de336c9b3f58c1b9a
    proof: BOTH_VERIFIED_BY_REAL_PUT_AND_FULL_GET; LOCAL_PACKAGES_RETAINED; NO_DELETE; CROSS_PROJECT_USE_REJECTED

P4_01_durable_close:
  source_boundary_commit: ede6095fbf2b3712e46e5a06711eb240453136fc
  source_boundary_tree: 9e6d7da30a3f8db51493999c56ff569369852a18
  implementation_commit: 84f26c8f8eb7bd83a2b9d175944f39ba7341e018
  implementation_tree: 4a0ead0e7bc5e5732595c503d7d735052d64e2da
  result_commit: 3fc7f1eeecbf2b6fb7b4754c31939c5e8aa7e22f
  result_tree: a87e9219ca2b27448a4de9e75412d22d00be977e
  github_readback: EXACT_INSTRUCTION_AND_ELEVEN_P4_PATHS_CONFIRMED
  qualification: 17_TESTS_GREEN_IN_4.32_SECONDS; STRICT_MYPY_7_FILES_SUCCESS; SIX_PROMPT_KPIS_ZERO
  wheel_sha256: c97e1ff514dbc98df69cb9fd96c5702ee9f8f93ff2bee5a07bd17a7a2a547423
  wheel_surface: CORE_AND_LAZY_EXPORTS_VERIFIED
  contract: EXACT_VERSIONED_SUITE_TASKSET_PROFILE_RUN_RESULT_STATISTICS_PAIRWISE_KNOWLEDGE_CANDIDATE_DURABLE_MATRIX_SKIP_SUCCEEDED_CELLS_SEPARATE_OUTCOMES_UNKNOWN_METRICS_NONE_NO_PROMOTION_OR_UNIVERSAL_WINNER
  real_l40s_evidence: QWEN2_5_0_5B_7ae557604adf67be50417f59c2c2f167def9a775_QWEN2_5_1_5B_989aa7980e4cf806f80c7fef2b1adb7bc71aa306_SAME_L40S_CUDA12_6_PYTORCH2_7_1_CU126_TRANSFORMERS4_53_2_FP16_WARM_30_OF_30_INFRA_3_OF_15_VS_12_OF_15_SEMANTIC_0_9_6_PAIRED_DESCRIPTIVE_ONLY
  fixture_result_sha256: 7928b7a5e23c1e8dd6b64734c1503f517b123e4910a24b4dc7c04de2ab0bc3fb
  fixture_spec_sha256: 0c8af78b5f57d9ac3899af842f3867dfec05cbd9cbbd0d0769c8bdb76f70858f
  evidence_classification: REAL_RAW_ARTIFACTS_REFERENCE_LOCAL_BINDINGS_QUASI_CONTROLLED_HISTORICAL_EXTERNAL_EXECUTION_WITHOUT_NATIVE_ENGINE_AUTHORITY_AND_PROCESS_WIDE_VRAM
  unknown_metrics: COST_QUEUE_REMOTE_RESOURCE_TIMEOUT
  post_run_l40s: 0_MIB_NO_RESIDENCY

P4_02_durable_close:
  source_boundary_commit: 7c48244f2aea833f32ea6d3b774fa473aeae5772
  source_boundary_tree: cd39defcd2aa7272940974c3f1863a9218b1ab8a
  result_commit: 5a261f021c3c743e68910c5f0f61f5ab7b12b471
  result_tree: 2b377a9bbff0d720b69c6179b562ee67e81a5211
  github_readback: EXACT_ELEVEN_PATHS_PASS
  qualification: P4_01_AND_P4_02_31_TESTS_GREEN_IN_7.14_SECONDS; REPAIRED_P4_02_14_TESTS_GREEN_IN_3.35_SECONDS; STRICT_MYPY_7_FILES_PASS; ALL_KPIS_ZERO
  wheel_sha256: 98dea755f9a2917f6415df086e5f645cf6b5564b5e36005397b61f441b3f9567
  implementation: STRATEGY_EVALUATION_CONTRACTS_RUNTIME_EVIDENCE_THREE_TESTS_FOUR_REAL_FIXTURES_ROOT_EXPORTS_NO_MIGRATION
  real_l40s: 120_OF_120_INFRASTRUCTURE_69_PASS_51_FAIL_138_MODEL_INVOCATIONS_15_TOOLS_SIX_MATRICES_RAW_REAL_BINDING_REFERENCE_IMPORTED_QUASI_CONTROLLED
  artifact_digests: SPEC_5e06acd_RESULTS_c231296e_MANIFEST_4c68e6_POST_9669aa3
  post_run: VRAM_0_MIB_PROCESSES_0
  kpis_zero: MISSING_VERSION_IDENTITY_MODEL_STRATEGY_EFFECT_MISLABELS_HIERARCHY_VALIDATION_OVERRIDE_UNRECORDED_PROMPT_TOOL_CHANGES
  limitations: SMALL_EXACT_TASKSET_EXTERNAL_NON_NATIVE_ENGINE_AUTHORITY_PADDED_BATCHING_PROCESS_WIDE_VRAM_DESCRIPTIVE_NO_SIGNIFICANCE_OR_UNIVERSAL_WINNER
  unresolved: NONE

P4_03_durable_close:
  coherent_result_commit: dcfadf6c71b314c499f94f2adc541984c469c1c6
  coherent_result_tree: d352e5df5f1479ddef454f13b085d8d7d2c31cbe
  reconciled_pushed_head: ad2f46a242e6fca216b767fb7e46aaacc1e2ca17
  reconciled_pushed_tree: c33516fad72499d9ba8af434f1a23741d63c3386
  github_readback: EXACT_COMMIT_TREE_AND_FIFTEEN_CHANGED_PATHS_PASS
  qualification: 15_FOCUSED_TESTS_PASS_INITIAL_FINAL_GATE_60_PASS_1_PREDECESSOR_FAILURE_EXACT_P0_PROVIDER_NEUTRAL_REPAIR_PASS_39_INVALIDATED_P4_TESTS_PASS_STRICT_MYPY_173_PASS
  wheel_sha256: 41eeb7783ecc1b99d2c138e13b0966e4e3710dbd01f588525855179bcb4be52f
  wheel_import: VERIFIED
  runtime_contract: HARD_CONSTRAINTS_CURRENT_RESOURCES_FIRST_VERSIONED_ESTIMATES_OBJECTIVES_EXPLANATIONS_COLD_START_SAFE_BOUNDED_SHADOW_SUPERSESSION_ROLLBACK_FALLBACK_SCHEDULER_REVALIDATION_IMMUTABLE_RECEIPTS_FAIL_CLOSED_REAL_IMPORTER
  real_l40s: 12_CASES_22_OF_22_CHECKS_4_REJECTIONS_QUALITY_M15_TOOL_ON_LATENCY_M15_SPECIALIST_UNAVAILABLE_NO_ELIGIBLE_CANDIDATE_RECOVERED_FALLBACK_M15_S1_QUALITY_MAE_0_LATENCY_MAE_0_0016360651332888755_SECONDS
  artifact_digests: SPEC_e0a4ccd_RESULTS_9b592360_MANIFEST_73c067dc_POST_7e767a9a
  post_run: VRAM_0_MIB_PROCESSES_0_MODEL_RESIDENCY_0
  evidence_classification: REAL_L40S_RAW_REFERENCE_BINDING_IMPORTED_QUASI_CONTROLLED
  limitations: CONTROLLED_REPLAY_EXACT_P4_TASKSET_PROCESS_SCOPED_CUDA_HIDING_NOT_PHYSICAL_REMOVAL_NO_ONLINE_DISTRIBUTION_NETWORK_QUEUE_COST_EVIDENCE_DESCRIPTIVE_ONLY
  unresolved: NONE

owner_priority:
  standing_order: preserve_current_or_recoverable_long_running_productive_work_before_any_remote_sync_restore_reset_checkout_merge_or_host_replacement
  remote_newer_is_not_permission_to_replace_unpreserved_execution_work: true
  current_sequence:
    - retain_predecessor_P4_03_durable_close_evidence
    - load_and_compile_P4_04_exact_prompt_when_execution_begins

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
  state: P4_04_ACTIVATED_NOT_STARTED
  P3_05_durable_close_complete: true
  P3_06_durable_close_complete: true
  P3_07_durable_close_complete: true
  P3_13_durable_close_complete: true
  P3_14_durable_close_complete: true
  P4_03_durable_close_complete: true
  P4_04_prompt_loaded: false
  P4_04_prompt_compiled: false
  P4_04_execution_started: false
  P4_04_execution_authorized: true

activation_boundary:
  P4_04_authorized: true
  P4_04_prompt_loaded: false
  P4_04_graph_compiled: false
  P4_04_execution_started: false
  legacy_spark_prep_dependency: false
  rule: compile_only_from_exact_P4_04_prompt_and_accepted_source
  predecessor_evidence: P4_03_durable_close_mapping_above
```
