# 03 — BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v5
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-01

authority:
  if_conflict:
    - CURRENT_EXECUTION_STATE
    - CURRENT_GITHUB_SOURCE
    - CURRENT_CANONICAL_DRIVE
    - VERIFIED_HISTORICAL_EVIDENCE
    - REFERENCE_OR_PLAN
    - INFERENCE
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

engine:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine

durable_source:
  current_result:
    commit: d720e0979d6cf8c0e3644a25df8e8f08db0b2f22
    tree: 9e01b2cd528f0519346021889edf73c92e74e718
    github_readback: EXACT_COMMIT_TREE_CONFIRMED
  current_implementation_base:
    commit: b7a55142edea7de895f799b8bef074a2a02d916d
    tree: 6df2a4d4f04246713220aa2461a10e33ba1b93d1
    meaning: PRESERVED_ACCEPTED_SOURCE_AND_RESULT; NOT_FOUNDATION_COMPLETION_AUTHORITY
  current_execution_map:
    result_commit: d720e0979d6cf8c0e3644a25df8e8f08db0b2f22
    result_tree: 9e01b2cd528f0519346021889edf73c92e74e718
    file: docs/project-state/04_BIELLA_ACTIVE_TASK.md
    schema: biella.active_task/v6
    language: biella.codex.end_to_end/v2
    status: P3_09_ACTIVE_DURABLE_REPAIR
  branch_head_rule: continuity_commits_may_advance_after_this_record; preserve_current_productive_state_before_any_future_remote_mutation_then_reobserve_origin_main
  rejected_history:
    first_rejected_execution_time: "2026-08-30T10:44:52Z"
    rejected_post_boundary_completion_claims: P3_10_THROUGH_P3_09

numbered_execution:
  durable_prompts_complete: 44
  durable_prompts_total: 51
  progress: "44 / 51 durable; non-contiguous audited; repair frontier 40"
  phase: P3_DURABLE_REPAIR
  active_prompt: P3-09
  active_global_number: 40
  active_title: Rendering Production Pack
  active_drive_prompt_id: 1FYsaztU8wwjl_6k8Nx4xJII4wId-MPflkLFUNwW4gRM
  predecessor: P3-08
  successor: P3-10
  active_dependency: P3-08
  successor_execution_authorized: false_until_P3_09_durable_close
  active_execution_authorized: true
  future_activation_shells_prepared: false
  future_internal_graphs_precompiled: false
  future_graph_rule: activate_P3_10_only_after_P3_09_durable_close

execution_host_state:
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
    root_filesystem_gib_observed: 338.35
    resource_note: LOWER_RESOURCE_REPLACEMENT_HOST
  previous_host: DESTROYED
  previous_host_paths_are_current_state: false
  canonical_root: /root/biella
  canonical_codex_home: /root/.codex
  canonical_checkout: /root/biella/repos/biella-engine
  checkout_observation:
    branch: main
    current_result_commit: d720e0979d6cf8c0e3644a25df8e8f08db0b2f22
    current_result_tree: 9e01b2cd528f0519346021889edf73c92e74e718
    github_readback: EXACT_COMMIT_TREE_CONFIRMED
  current_restore_order: PRESERVE_LATER_SOURCE_THEN_DURABLY_REPAIR_P3_09

standing_owner_priority:
  highest_operational_rule: preserve_current_or_recoverable_long_running_productive_work_before_remote_sync_restore_reset_checkout_merge_or_host_replacement
  remote_newer_does_not_override_unpreserved_execution_work: true
  session_model_SSH_tmux_or_host_change_does_not_invalidate_verified_work: true
  current_required_order:
    - preserve_all_later_accepted_source_and_results
    - durably_repair_P3_09_under_standing_authorization
    - advance_to_P3_10_only_after_P3_09_durable_close

p3_05_recovery:
  status: REUSED_FOR_DURABLE_CLOSE_WITHOUT_REHASH
  valid_execution_through: "2026-08-30T10:08:48.575Z"
  reject_execution_beginning: "2026-08-30T10:44:52Z"
  recovery_archive_name: GPT56_EXACT_RECOVERY_2026-08-30.tar.gz
  recovery_archive_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  recovery_archive_size_bytes: 26490936
  recovery_archive_drive_id: 1Y7aEStdGbCK5a0N9iA8s41l2olTWOUAE
  recovery_archive_drive_readback: VERIFIED_EXACT_BYTES
  recovery_archive_drive_readback_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  reuse_rule: already_verified_archive_reused_without_rehash

completion_audit_2026_09_01:
  authority: SUPERSEDES_CONFLICTING_COMPLETION_LABELS_AND_RECORDED_ASSERTIONS
  preservation_rule: preserve_all_later_source_and_results; invalidate_only_unsupported_durable_claims
  FOUNDATION_COMPLETE: INVALIDATED
  P3_06:
    functional_source: COMPLETE
    durable_close: COMPLETE
  P3_07:
    durable_close: COMPLETE
  P3_08:
    durable_close: COMPLETE
  P3_09:
    durable_close: INCOMPLETE
    missing: generic_renderer_adapter_final_recovery_and_durable_evidence
  P3_10:
    durable_close: INCOMPLETE
    missing: full_simulation_adapter_ENOSPC_1_through_300_recovery_and_durable_evidence
  P3_11:
    durable_close: INCOMPLETE
    missing: durable_evidence
  P3_12:
    durable_close: INCOMPLETE
    missing: durable_evidence
  P3_13:
    durable_close: INCOMPLETE
    missing: six_KPI_report_correction_and_durable_evidence
  P3_14:
    durable_close: INCOMPLETE
    missing: phase_exit_provenance_and_Event_evidence
  P4_01_through_P4_05:
    durable_close: COMPLETE
  P4_06:
    preserved_source_result:
      commit: b7a55142edea7de895f799b8bef074a2a02d916d
      tree: 6df2a4d4f04246713220aa2461a10e33ba1b93d1
    durable_close: INCOMPLETE
    missing: authoritative_Engine_evidence_and_combined_failure_scenario

p3_06_durable_close:
  implementation:
    commit: 78005b0a30fa7002eed8019a588731551e3d2c6b
    tree: 6737d32d10feae0dcaeb4024ece00f3aa64b20f0
  result:
    commit: 1d74abff81c9588aecfd933ec7733fb9afd098e4
    tree: 93326e98e57c1efc16fd05c4dcd938b2314e4c89
  github_readback: EXACT_COMMIT_TREE_AND_TEST_BLOB_CONFIRMED
  qualification:
    real_tests: 6
    engine_evidence_tests: 1
    installed_wheel_tests: 3
    six_kpis: ALL_ZERO
  engine_evidence:
    project: prj_145a1cb379234d329bcef9016e33220c
    run: run_6cd6de862c704e7395a99988429fd135
    run_status: SUCCEEDED
    graph: graph://prj_145a1cb379234d329bcef9016e33220c/gph_7788383d1e5f42d396717878cfadeea2/1
    node: node://prj_145a1cb379234d329bcef9016e33220c/gph_7788383d1e5f42d396717878cfadeea2/1/nod_42db888aef7b4cd780159cd2cda4d694
    node_status: SUCCEEDED
    artifacts: 11
    validation_aggregate_sha256: a6ca97ee816c1393b29008dc028ac613cf0385d588245b457abf5aee86a65f1
    validation_status: PASS
  drive_evidence:
    qualification_id: 17JiKtO0V-bauEAqtsvF9v1dSIVHexYbP
    qualification_sha256: 993294df8b4860ceb1a5e3d7f13bc9f899df258c8549c6d54b95a8758fdb616c
    l40s_id: 1WAG4vM7EDZTM_Y1ytCxgGjcoe6TN9ryn
    l40s_sha256: 51b11696bfbf6cb13f330f4451aec98080187cd1670ef126c6b987ca5422c089
    engine_id: 1-J1e56nCoXjLxO5-lye4hfZiNBsdRw9J
    engine_sha256: d51a123e76aee974671395c45778667aef01ab10fc58a46752325dc74896a204
    wheel_id: 1ALALJp4HtVb3jZ3bJcVLwiMuBX5dYFN8
    wheel_sha256: de1ff7ab4d1aafe06a8d4ee7ae3799e6ce1a23b1aee10f8cdf3e27223735cb98
    exact_raw_readback: FOUR_OF_FOUR

p3_07_durable_close:
  result:
    commit: d5dfe8eaa8c58f6a55a86adf1050d20195413666
    tree: b40b6d121573a46cfa04e751be52c64a46b63b04
  github_readback: EXACT_COMMIT_TREE_CONFIRMED
  qualification:
    focused_real_blender: 1_PASS_IN_39_815_SECONDS
    full_real_suite: 10_PASS_IN_85_691_SECONDS
    durable_engine_import: 1_PASS_IN_10_03_SECONDS
    strict_mypy: 9_FILES_NO_ISSUES
    installed_wheel_local: 8_PASS
    installed_wheel_real_blender: 1_PASS_IN_38_790_SECONDS
    p3_05_real_portability_recheck: 1_PASS_IN_57_951_SECONDS
    affected_regression_unchanged: 24_PASS
    five_prompt_kpis: ALL_ZERO
  engine_evidence:
    project: prj_0740cfbce71545a7aa680a3fe59d0517
    task: tsk_15cf533b4ec4468bb9aaa6fe15482491
    run: run_22af562941d041afaf150ecf2ca3b19e
    run_status: SUCCEEDED
    run_state_sha256: e94f6827a7dab075cc13b863cf2969b9136e3e1894b041b9de5adf6afffaa0bf
    graph: graph://prj_0740cfbce71545a7aa680a3fe59d0517/gph_f305ead7cce44a3581068facb496e0a2/1
    graph_sha256: 01600fae25147f64301fead5c069cfbffa6ab9925fa9eaf37937e1e972e4b295
    validation_plan: validation-plan://prj_0740cfbce71545a7aa680a3fe59d0517/vplan_6d45462b4be946dd96dce15a841dea54
    validation_verdict: PASS
    validation_evidence_state: CURRENT
    validation_aggregate_sha256: b6a2373866266b4b620bb3b070b4250a31e7d6849dc0bf9db664b6d3ae813952
    artifacts: 30
    event: event://prj_0740cfbce71545a7aa680a3fe59d0517/evt_3299da6da85444c98f5f8825aece393b
    independent_nodes:
      - node: node://prj_0740cfbce71545a7aa680a3fe59d0517/gph_f305ead7cce44a3581068facb496e0a2/nod_122bd6030edc41559e606bf71ef5816b
        attempt: natt_ab5c63b0c65f45e1893d17e1f2c635b9
        allocation: ral_6bd89d31406a4321bb2f02ac9dff6fec
        status: SUCCEEDED
      - node: node://prj_0740cfbce71545a7aa680a3fe59d0517/gph_f305ead7cce44a3581068facb496e0a2/nod_a66982f13bd645db87fca0e09f72ad5c
        attempt: natt_397d25ef29c1474ba9f94e9a4c466285
        allocation: ral_81b7c6987549420980a84fbfeae1bedc
        status: SUCCEEDED_AFTER_ISOLATED_FAILURE
  drive_evidence:
    real_l40s_id: 1DeCs9CK6_S6hM3YFp74U08ktYCvkgn4e
    real_l40s_sha256: a99db777c0d8e9d6c6a02ec4c13b80d42b7da800d0285c4b7c71d9981d1c4111
    engine_id: 1jpMZ1hFzoSQLCbJLz2ytyZJ5ORBdrwfv
    engine_sha256: 5e59d7370ede28d917739153e1bed2337196a1aa0ae883d8296f3b88e0fac26a
    wheel_id: 1q9UvAoGzkI9H94U5nhwxK8czWw6MU3fS
    wheel_sha256: a1a54232bbb308d56aab445700c02f32615e2c369868e1f3ca6ce0a214116d9d
    installed_wheel_real_id: 12Sc4iD8-FoyjjZKDm1u5vjK7jtl7-Ayh
    installed_wheel_real_sha256: 1eb47d5aa5c7da4adb2cf03761ff7278758f4d56390045dac56120c819850c71
    affected_regression_id: 1hCdxwm6YCnmo-9Kteg2dpREyplJ6aWDN
    affected_regression_sha256: 0c735aa32bd24e5b04ad7bb0b83553600ddc846a67a756c5c86daae4bbc8233d
    qualification_id: 10JUEcm3eVgijyCDpfWXadyGXya6C1rvh
    exact_readback: SIX_OF_SIX

p3_08_durable_close:
  result:
    commit: d720e0979d6cf8c0e3644a25df8e8f08db0b2f22
    tree: 9e01b2cd528f0519346021889edf73c92e74e718
  github_readback: EXACT_COMMIT_TREE_CONFIRMED
  qualification:
    environment_focused: 9_PASS
    game_bridge: 3_PASS
    durable_importer: 5_PASS
    strict_mypy: 8_FILES_NO_ISSUES
    affected_real_l40s: 3_PASS_IN_125_65_SECONDS
    installed_wheel_real_l40s: 7_PASS_IN_176_39_SECONDS
    five_prompt_kpis:
      environment_style_globalized: 0
      untracked_placed_asset_sources: 0
      engine_specific_world_structure_in_kernel: 0
      global_environment_budget: 0
      stale_environment_integration_accepted: 0
  engine_evidence:
    project: prj_aa4c818900a14ad388837d4ff2245ad8
    task: tsk_c2ee396069594ea69f4d53a2362bcbf6/1
    run: run_393952a2c2924c22be088e6c69609d54
    run_status: SUCCEEDED
    graph: graph://prj_aa4c818900a14ad388837d4ff2245ad8/gph_9393af0e00c146d0b6cc33517ed10a3c/1
    validation_plan: validation-plan://prj_aa4c818900a14ad388837d4ff2245ad8/vplan_68d54162582548eeb0736b3b63c5de63
    validation_verdict: PASS
    validation_aggregate_sha256: 8406ef52f77e87f88952973a941e7b5ce9c215bd280e879a5cc8a24c28a1efa6
    integration_artifact: artifact://prj_aa4c818900a14ad388837d4ff2245ad8/art_28b96667e0cd478ba8485fedce15e5ef/1
    event: event://prj_aa4c818900a14ad388837d4ff2245ad8/evt_2c5bba65863f4df8b257b26fa3602240
  l40s:
    parallel_four_branch_gate: RESOURCE_UNAVAILABLE_BOUNDED_NONBLOCKING
    exact_boundary: BLENDER_EXIT_134_PTHREAD_CREATE_RESOURCE_TEMPORARILY_UNAVAILABLE
    authoritative_independent_branch_graph: PASS
    sequential_affected_real: PASS
    sequential_installed_wheel_real: PASS
    post_state: BLENDER_GODOT_GPU_PROCESSES_ZERO; VRAM_ZERO
  drive_evidence:
    final_real_id: 1RQduTD8PMrR5ujy3EXpSKmy_iJxvw57Q
    final_real_sha256: f83534d1a48628b016fe0622320f8998f42ed08efddeb137bc59ae777050eb57
    engine_id: 1mkggvv8-IxavDQkN9iPFns6Dv5kkxpkO
    engine_sha256: 72011411bfc31b92bf777d6003f5ad3287a9faa5234cfd10aed3717286b20061
    affected_regression_id: 1EWHmfXwSFBc7hgKkzsCGF-tCe8LDWhNO
    affected_regression_sha256: 8c23c499f14c808e71bd2c27e5d07a81f3537bf4bf00915a61280bb07f74cfd8
    installed_wheel_real_id: 1dMhdqmW4nrLmFXLtUisC3Pxr37YbJIia
    installed_wheel_real_sha256: 38539e9bd23352963750633279823ab9a0679ee788d0f435e1ce6171217c68a9
    wheel_id: 1awHzPmaBPNF4cZ2x7LHIbFiD0MilQ5X2
    wheel_sha256: bc3b3725442401d416e4c63c948d470a0695d7e5280872e14bf3d97ee0adee52
    resource_limit_id: 1wzgx4MNaEZV-7C-JSFQ_zhPqtTZB1wLu
    resource_limit_sha256: bbba651f26ffb95415c09bd1cb6d3111d6adebd4a9231b5042aaa265ed883706
    qualification_id: 1lXzDOvEzAjAHbP6u7mnKwONajMo_snod
    exact_readback: SEVEN_OF_SEVEN

prior_durable_through_P3_08:
  status: PRESERVED_RESULT; DURABLE_CLAIM_INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  latest_result_commit: 0da64ebea6aeb0a69fb73ae8c67317fd8d86c109
  latest_result_tree: da7860a8c0890d3ae82b0ae3d4c9b545efa85759

prior_durable_through_P3_09:
  status: PRESERVED_RESULT; DURABLE_CLAIM_INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  latest_result_commit: b23195b82e20a568f22b8ebc7be401d5bb95c97e
  latest_result_tree: c35e5a1f38d6c938828ec0556706a3ed0e3ca93a

prior_durable_through_P3_10:
  status: PRESERVED_RESULT; DURABLE_CLAIM_INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  latest_result_commit: b7fe1a20caabeda053b1fb8c42d01a7da999b34e
  latest_result_tree: 5b94821f1fb98a9993d384e9a2d034bcff843376

prior_durable_through_P3_11:
  status: PRESERVED_RESULT; DURABLE_CLAIM_INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  latest_result_commit: 72bd7d78f7fe5ff53cac003cfeddcd91188fcfe3
  latest_result_tree: 21ed73b5e2f55ce21a77ce28f40d5b415f159c0b

prior_durable_through_P3_12:
  status: PRESERVED_RESULT; DURABLE_CLAIM_INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  latest_result_commit: 3dcc194253bb54d2a171cf7230877af95231ebe7
  latest_result_tree: 8835d92e6651ea13ec5f02b87487f0520fb7bae6

p3_13_durable_close:
  completion_audit_status: PRESERVED_RESULT; SIX_KPI_REPORT_CORRECTION_AND_DURABLE_EVIDENCE_MISSING
  result_commit: 27f8958aa3f6a2847b5d506580f04bcc904db98e
  result_tree: c92b5e322259ccd7619a7d51dbe94f270942b10e
  github_readback: EXACT_COMMIT_TREE_AND_EIGHT_PATHS_CONFIRMED
  contract: REAL_FFMPEG_8_0_1_FULL_PROBE_DECODE_MANAGED_PROCESS_MEDIA_FRAMES_IMMUTABLE_SOURCE_ORDERED_P3_11_FRAMES_P3_12_AUDIO_SUBTITLE_MUX_COMPOSE_ENCODE_PROXY_SESSION_GAME_HANDOFF_FAILURE_CANCEL_REPLAY_RECOVERY
  final_gate: 12_TESTS_GREEN_IN_147.41_SECONDS; STRICT_MYPY_7_FILES_SUCCESS; FIVE_PROMPT_KPIS_ZERO
  optional_generative_path: NOT_RUN
  wheel_sha256: abd3933d701e7dd33c0f6b2d40bc947e2d84ac565a90bf76af3aad46008f2810
  wheel_import: BASE_IMPORT_AND_PILLOW_LAZY_VERIFIED

p3_14_durable_close:
  result_commit: 68c00a4e1464206c2a69e14f8b8049fe29438fb8
  result_tree: 2516591d9c3f893c9da583c06a9e7e9eb6bb0882
  github_readback: EXACT_COMMIT_TREE_AND_EIGHT_PATHS_CONFIRMED
  status: PRESERVED_RESULT; PHASE_EXIT_PROVENANCE_AND_EVENT_EVIDENCE_MISSING
  qualification: 17_TESTS_GREEN_IN_59.01_SECONDS_WITH_LIVE_CLOUDFLARE_KV_ENABLED; STRICT_MYPY_8_FILES_SUCCESS; SIX_PROMPT_KPIS_ZERO
  wheel: DELIVERY_AT_1_0_0_15_CAPABILITIES_AND_LAZY_EXPORTS_VERIFIED
  wheel_sha256: 4a1f4de335a505707b38f991f9fd83cd60c9bfc8dfa9f2e9d62dbc488f46409c
  package_integrity: DETERMINISTIC_EXACT_PACKAGES_FULL_REOPEN_DIGEST_PATH_PERMISSION_SYMLINK_VALIDATION_BOUNDED_SECRET_SCAN_SECRET_REF_HMAC_POST_VERIFY
  publication_authority: EXACT_TASK_NODE_RUN_FENCE_EXTERNAL_AUTHORITY_IMMUTABLE_IDEMPOTENT_REMOTE_KEYS_FULL_SHA_READBACK_VERIFICATION_FAILURE_OUTCOME_UNKNOWN_TRUTH_DURABLE_RECEIPT
  cloudflare_kv:
    namespace: biella-p3-14-delivery
    namespace_id: f35ac3a280eb4b1387f5d2d403fc3266
  cross_domain_real_proof:
    software_project:
      project: prj_3cc1bf23fc5546e19379b1f8c2baeff9
      package_key: biella/packages/2ff85b54f0909de58f477b49d42f3b6585b2fa296dc7fc9abf589c8bcab4ce83
      receipt_digest: f5089f4ee6f12785fd9a443e52bc9c32f47a7230fa97bc58b317a7c3c84021e8
      proof: RUNNABLE_BACKEND_VERIFIED_BY_REAL_PUT_AND_FULL_GET
    video_project:
      project: prj_c4ab734ec30b4db482b30bd5b35cb77b
      package_key: biella/packages/8efefe37f544462f24ead38938b703eb2a1dad22f72f2b3609691d02363df45e
      receipt_digest: 274801d7eaeffea49d34780e8a14e1e61511eeecefb30a7de336c9b3f58c1b9a
      proof: REAL_DECODABLE_MP4_VERIFIED_BY_REAL_PUT_AND_FULL_GET
    retention: NO_DELETE; LOCAL_PACKAGES_RETAINED
    isolation: SAME_GENERIC_KERNEL; CROSS_PROJECT_USE_REJECTED

p4_01_durable_close:
  source_boundary:
    commit: ede6095fbf2b3712e46e5a06711eb240453136fc
    tree: 9e6d7da30a3f8db51493999c56ff569369852a18
  implementation:
    commit: 84f26c8f8eb7bd83a2b9d175944f39ba7341e018
    tree: 4a0ead0e7bc5e5732595c503d7d735052d64e2da
  result:
    commit: 3fc7f1eeecbf2b6fb7b4754c31939c5e8aa7e22f
    tree: a87e9219ca2b27448a4de9e75412d22d00be977e
  github_readback: EXACT_INSTRUCTION_AND_ELEVEN_P4_PATHS_CONFIRMED
  qualification: 17_TESTS_GREEN_IN_4.32_SECONDS; STRICT_MYPY_7_FILES_SUCCESS; SIX_PROMPT_KPIS_ZERO
  wheel_sha256: c97e1ff514dbc98df69cb9fd96c5702ee9f8f93ff2bee5a07bd17a7a2a547423
  wheel_surface: CORE_AND_LAZY_EXPORTS_VERIFIED
  contract: EXACT_VERSIONED_SUITE_TASKSET_PROFILE_RUN_RESULT_STATISTICS_PAIRWISE_AND_KNOWLEDGE_CANDIDATE; DURABLE_GRAPH_SCHEDULER_CHECKPOINT_MATRIX_SKIPS_SUCCEEDED_CELLS; SEPARATE_TRANSPORT_SEMANTIC_INFRASTRUCTURE_OUTCOMES; UNKNOWN_METRICS_NONE; NO_PROMOTION_OR_UNIVERSAL_WINNER
  real_l40s_evidence:
    model_revisions:
      qwen2_5_0_5b: 7ae557604adf67be50417f59c2c2f167def9a775
      qwen2_5_1_5b: 989aa7980e4cf806f80c7fef2b1adb7bc71aa306
    controlled_conditions: SAME_L40S_CUDA_12_6_PYTORCH_2_7_1_CU126_TRANSFORMERS_4_53_2_FP16_WARM
    infrastructure: 30_OF_30
    semantic: 0_5B_3_OF_15; 1_5B_12_OF_15
    pairwise_from_0_5b_perspective: 0_WINS_9_LOSSES_6_TIES
    fixture_result_sha256: 7928b7a5e23c1e8dd6b64734c1503f517b123e4910a24b4dc7c04de2ab0bc3fb
    fixture_spec_sha256: 0c8af78b5f57d9ac3899af842f3867dfec05cbd9cbbd0d0769c8bdb76f70858f
    classification: REAL_RAW_ARTIFACTS; REFERENCE_LOCAL_IDENTITY_BINDINGS; QUASI_CONTROLLED_HISTORICAL_EXTERNAL_EXECUTION_LACKS_NATIVE_ENGINE_AUTHORITY_AND_VRAM_IS_PROCESS_WIDE
    unknowns: COST_QUEUE_REMOTE_RESOURCE_TIMEOUT
    post_run: L40S_0_MIB_NO_RESIDENCY

p4_02_durable_close:
  source_boundary:
    commit: 7c48244f2aea833f32ea6d3b774fa473aeae5772
    tree: cd39defcd2aa7272940974c3f1863a9218b1ab8a
  result:
    commit: 5a261f021c3c743e68910c5f0f61f5ab7b12b471
    tree: 2b377a9bbff0d720b69c6179b562ee67e81a5211
  github_readback: EXACT_ELEVEN_PATHS_PASS
  implementation: STRATEGY_EVALUATION_CONTRACTS_RUNTIME_EVIDENCE_THREE_TESTS_FOUR_REAL_FIXTURES_AND_ROOT_EXPORTS; NO_MIGRATION
  qualification: P4_01_AND_P4_02_31_TESTS_GREEN_IN_7.14_SECONDS; REPAIRED_P4_02_14_TESTS_GREEN_IN_3.35_SECONDS; STRICT_MYPY_7_FILES_PASS; ALL_KPIS_ZERO
  wheel_sha256: 98dea755f9a2917f6415df086e5f645cf6b5564b5e36005397b61f441b3f9567
  wheel_imports: VERIFIED
  real_l40s:
    infrastructure: 120_OF_120
    semantic: 69_OF_120_PASS_51_OF_120_FAIL
    model_invocations: 138
    tool_calls: 15
    matrices: 6
    artifact_digests: SPEC_5e06acd_RESULTS_c231296e_MANIFEST_4c68e6_POST_9669aa3
    post_run: VRAM_0_MIB_PROCESSES_0
    evidence_classification: RAW_REAL_BINDING_REFERENCE_IMPORTED_QUASI_CONTROLLED
  kpis_zero:
    - missing_version_identity
    - model_or_strategy_effect_mislabels
    - hierarchy
    - validation_override
    - unrecorded_prompt_or_tool_changes
  limitations: SMALL_EXACT_TASKSET_EXTERNAL_NON_NATIVE_ENGINE_AUTHORITY_PADDED_BATCHING_PROCESS_WIDE_VRAM_DESCRIPTIVE_NO_SIGNIFICANCE_OR_UNIVERSAL_WINNER
  unresolved: NONE

p4_03_durable_close:
  coherent_result:
    commit: dcfadf6c71b314c499f94f2adc541984c469c1c6
    tree: d352e5df5f1479ddef454f13b085d8d7d2c31cbe
  reconciled_pushed_head:
    commit: ad2f46a242e6fca216b767fb7e46aaacc1e2ca17
    tree: c33516fad72499d9ba8af434f1a23741d63c3386
  github_readback: EXACT_COMMIT_TREE_AND_FIFTEEN_CHANGED_PATHS_PASS
  qualification: 15_FOCUSED_TESTS_PASS; INITIAL_FINAL_GATE_60_PASS_1_PREDECESSOR_FAILURE; EXACT_P0_PROVIDER_NEUTRAL_REPAIR_PASS; 39_INVALIDATED_P4_TESTS_PASS; STRICT_MYPY_173_PASS
  wheel_sha256: 41eeb7783ecc1b99d2c138e13b0966e4e3710dbd01f588525855179bcb4be52f
  wheel_import: VERIFIED
  runtime_contract: HARD_CONSTRAINTS_AND_CURRENT_RESOURCES_FIRST_VERSIONED_ESTIMATES_OBJECTIVES_EXPLANATIONS_COLD_START_BASELINE_ELIGIBILITY_SAFE_BOUNDED_SHADOW_EXPLORATION_SUPERSESSION_ROLLBACK_FALLBACK_SCHEDULER_REVALIDATION_IMMUTABLE_RECEIPTS_FAIL_CLOSED_REAL_EVIDENCE_IMPORTER
  real_l40s:
    cases: 12
    checks: 22_OF_22
    rejections: 4
    routes: QUALITY_M15_TOOL_ON_LATENCY_M15_SPECIALIST_UNAVAILABLE_NO_ELIGIBLE_CANDIDATE_RECOVERED_FALLBACK_M15_S1
    quality_mae: 0
    latency_mae_seconds: 0.0016360651332888755
    artifact_digests: SPEC_e0a4ccd_RESULTS_9b592360_MANIFEST_73c067dc_POST_7e767a9a
    post_run: VRAM_0_MIB_PROCESSES_0_MODEL_RESIDENCY_0
  evidence_classification: REAL_L40S_RAW_REFERENCE_BINDING_IMPORTED_QUASI_CONTROLLED
  limitations: CONTROLLED_REPLAY_EXACT_P4_TASKSET_PROCESS_SCOPED_CUDA_HIDING_NOT_PHYSICAL_REMOVAL_NO_ONLINE_DISTRIBUTION_NETWORK_QUEUE_COST_EVIDENCE_DESCRIPTIVE_ONLY
  unresolved: NONE

p4_04_durable_close:
  result_commit: 6892628a9f48114755ec02f3aa8728399312b163
  result_tree: f33654a9471aa66da1aa1aa06cf4cfd6bbf07b8c
  github_readback: EXACT_TEN_OF_TEN_PATHS_CONFIRMED
  qualification: FOCUSED_8_OF_8; STRICT_MYPY_178_FILES; P4_54_OF_54; NEUTRAL_RESOURCE_ROUTING_31_OF_31; PREDECESSOR_BUILD_INSTALL_RESTART_1_OF_1
  real_l40s:
    cases: 7_OF_7
    checks: 26_OF_26
    results_sha256: 978d907094c0ead0d70687ffe194d13310a7900410f2dd6d8c7d1202d169cbed
    post_run: GPU_PROCESS_AND_RESIDENCY_ZERO
  drive_evidence:
    spec_id: 1fNSBejzpq5Ci1OYkyDyvHlpGHagm5mqW
    results_id: 1IkoJj9FGXC07MHHk-UlJl2jNCJLaLC31
    manifest_id: 1ju6IkWQXsPtDXatgM23DtuV19jHsUKAT
    post_id: 18uKbLweyte4Hwha4ZKe7-V-sLzgRuIjt

p4_05_durable_close:
  result_commit: 4140f584d4994895b46b7b35ec43c4535844348d
  result_tree: 579c4ce1f8e4171aca12a4bb659b4c502950acfd
  github_readback: EXACT_NINE_OF_NINE_PATHS_CONFIRMED
  qualification: FOCUSED_11_OF_11; STRICT_MYPY_181_FILES; P4_65_OF_65; TASK_EXECUTION_AUTHORITY_44_PLUS_3_SUBTESTS; NEUTRAL_1_OF_1; WHEEL_BUILD_INSTALL_RESTART_PASS
  kpis: ALL_SIX_ZERO
  reality: REAL_SQLITE_DURABILITY_AND_KNOWLEDGE_PROJECTION; PRIOR_P3_CASES_REFERENCE_ONLY
  l40s: NOT_USED_NO_PROMPT_MATRIX_OR_MATERIAL_GPU_WORK
  drive_evidence:
    qualification_id: 1DubjS-3HHUoOpkL7vg5PP5tMlkyHud1T
    qualification_sha256: 0f0e5a7d953dab0103d9c6b10234443742c867a037607d44b4bf93e68d37bc9c
    reference_manifest_id: 1tzVOlqpgXuHDKny-DwtMhivA3-d5vmrt
    reference_manifest_sha256: 89739140899c24a9499f9ee64d216c4c29a7e7f9f1c5d421c47d2b6c5f6c3bcf
    exact_readback: TWO_OF_TWO
  limitations: SIMILARITY_INDEX_DERIVED_NON_AUTHORITATIVE; MODEL_SCORE_NEVER_IDENTITY; REPAIR_PROPOSAL_REQUIRES_TASK_GRAPH_AUTHORITY
  unresolved: NONE

p4_06_durable_close:
  initial_source_commit: 5f9e69318d3d690201661e2ff76cdff65b251b05
  result_commit: b7a55142edea7de895f799b8bef074a2a02d916d
  result_tree: 6df2a4d4f04246713220aa2461a10e33ba1b93d1
  github_readback: EXACT_SEVEN_OF_SEVEN_THEN_REPAIR_TWO_OF_TWO_CONFIRMED
  qualification: P4_79_OF_79; FOCUSED_14_OF_14; NEUTRAL_INVALIDATED_1_OF_1; STRICT_MYPY_186
  wheel_sha256: 87b5f4c314ef77d75de02e7f79ee966a933b5ec2fc3c487abf2896e4aba26000
  drive_evidence:
    runtime_qualification_id: 1aPBlo32W0lXj_d2Fkfw4QeYhHk5cOFbl
    runtime_qualification_sha256: bb6501aa312e071685b59f6b04172294a3d78926b4e711201415c76c174889bf
    recipe_store_id: 1sRgvPljcCKiNdTO3EsqGxdF2SSRtWcc_
    recipe_store_sha256: e865a29a5cd4a50071eb54d911a92ddcd721f1f972a1b1feeefc4a2a70952b6f
    system_summary_id: 13kCHinR5a-TW7SiIbPESdQZz-Ygjj9MS
    system_summary_file_sha256: eeb3fd11a2e2e1adf3df17c505921d687c809aa42eef57d184bbab457ff64079
    system_summary_payload_digest: a5c83cf3bde04647b6009445d07b986abe4c99c23991c0770680366271069c66
    exact_readback: THREE_OF_THREE
  status: PRESERVED_SOURCE_RESULT; AUTHORITATIVE_ENGINE_EVIDENCE_AND_COMBINED_FAILURE_SCENARIO_INCOMPLETE

approved_execution_program:
  language: biella.codex.end_to_end/v2
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  active_graph_location: docs/project-state/04_BIELLA_ACTIVE_TASK.md
  active_graph: P3_09_RENDERING_PRODUCTION_PACK
  duplicate_prevention:
    exact_Node_identity_and_claim: required
    one_current_owner_per_Node: true
    overlapping_live_write_paths: forbidden
    validators_read_only: true
    repairs_derive_from_exact_failure_and_original_owner_boundary: true
  checkpoints:
    - CP0_RESTORED
    - CP1_GAP_MAP
    - CP2_INTEGRATED
    - CP3_REAL_WORKFLOW
    - CP4_REPAIR_CONVERGENCE
    - CP5_FINAL_VALIDATION
    - CP6_DURABLE_CLOSE
  token_efficiency:
    inspect_once_then_reobserve_only_invalidated_facts: true
    compact_worker_result_envelopes: true
    full_worker_transcript_handoffs: forbidden
    irrelevant_tools_and_skill_bundles_default_off: true
    usage_low_starts_no_new_Node: true
  superpowers_alignment:
    used_for_plan_decomposition_and_self_review: true
    runtime_dependency: false
    generic_subagent_or_reviewer_ceremony_overrides_Biella: false

context_policy:
  normal_load:
    - docs/project-state/03_BIELLA_CURRENT_STATE.md
    - docs/project-state/04_BIELLA_ACTIVE_TASK.md
    - directly_touched_source_and_interfaces
  read_only_if_required:
    - 00_operational_edge_cases
    - 01_architecture_or_semantic_scope
    - 02_sequence_or_plan_ambiguity
    - 05_exact_prompt_location
    - 06_source_evidence_or_migration_resolution
  prohibited_default_reloads:
    - unchanged_files
    - all_51_prompt_bodies
    - historical_recovery_sessions_after_restoration
    - broad_Drive_Git_or_filesystem_audits
    - raw_MiniTZ_history

truth:
  P3_04_durable_close: VERIFIED
  P3_05_durable_close: VERIFIED
  P3_06_durable_close: VERIFIED
  P3_07_durable_close: VERIFIED
  P3_08_durable_close: VERIFIED
  P3_09_durable_close: ACTIVE; GENERIC_RENDERER_ADAPTER_FINAL_RECOVERY_AND_DURABLE_EVIDENCE_MISSING
  P3_14_durable_close: PHASE_EXIT_PROVENANCE_AND_EVENT_EVIDENCE_MISSING
  P3_READY_FOR_P4: INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  P4_01_durable_close: VERIFIED
  P4_02_durable_close: VERIFIED
  P4_03_durable_close: VERIFIED
  P4_04_durable_close: VERIFIED
  P4_05_durable_close: VERIFIED
  P4_06_durable_close: AUTHORITATIVE_ENGINE_EVIDENCE_AND_COMBINED_FAILURE_SCENARIO_INCOMPLETE
  P0_THROUGH_P4_COMPLETE: INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  FOUNDATION_COMPLETE: INVALIDATED_BY_COMPLETION_AUDIT_2026_09_01
  P3_08_or_later_completion_claims_from_rejected_execution: REJECTED
  exact_recovered_P3_05_worktree_contents: REUSED_FOR_DURABLE_CLOSE_WITHOUT_REHASH
  multi_AI_execution_map_approved_by_user: true
  future_numbered_activation_queue_prepared: false
  previous_VPS_destroyed: VERIFIED_USER_REPORT
  current_execution_host_exists: true
  Drive_recovery_archive_exact_readback: VERIFIED_FRESH_2026_08_31
```
