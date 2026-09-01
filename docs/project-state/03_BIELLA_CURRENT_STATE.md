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
  current_implementation_base:
    commit: 5a261f021c3c743e68910c5f0f61f5ab7b12b471
    tree: 2b377a9bbff0d720b69c6179b562ee67e81a5211
    meaning: P4_02_durably_closed
  current_execution_map:
    source_commit: 7c48244f2aea833f32ea6d3b774fa473aeae5772
    source_tree: cd39defcd2aa7272940974c3f1863a9218b1ab8a
    result_commit: 5a261f021c3c743e68910c5f0f61f5ab7b12b471
    result_tree: 2b377a9bbff0d720b69c6179b562ee67e81a5211
    file: docs/project-state/04_BIELLA_ACTIVE_TASK.md
    schema: biella.active_task/v6
    language: biella.codex.end_to_end/v2
    status: P4_02_COMPLETE_P4_03_ACTIVATED_PROMPT_NOT_LOADED
  branch_head_rule: continuity_commits_may_advance_after_this_record; preserve_current_productive_state_before_any_future_remote_mutation_then_reobserve_origin_main
  rejected_history:
    first_rejected_execution_time: "2026-08-30T10:44:52Z"
    rejected_post_boundary_completion_claims: P3_10_THROUGH_P3_09

numbered_execution:
  durable_prompts_complete: 47
  durable_prompts_total: 51
  progress: "47 / 51"
  phase: P4
  active_prompt: P4-03
  active_global_number: 48
  active_title: Conditional Reversible Evidence-Based Routing Learning
  predecessor: P4-02
  successor_execution_authorized: true
  active_execution_authorized: true
  future_activation_shells_prepared: P4_03_THROUGH_P4_06
  future_internal_graphs_precompiled: false
  future_graph_rule: compile_each_from_exact_prompt_and_current_source_only_when_activated

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
    worktree_before_fetch: CLEAN
    head_before_fetch: e228a7bb6db6f94af15dde4a8fb110b028eddbed
    origin_main_after_fetch: ce10d326a56e46e9fbb51dd4ba22610ba7d9f011
    head_after_fast_forward: ce10d326a56e46e9fbb51dd4ba22610ba7d9f011
    fast_forward_files_changed:
      - docs/project-state/03_BIELLA_CURRENT_STATE.md
      - docs/project-state/04_BIELLA_ACTIVE_TASK.md
      - docs/project-state/BIELLA_DRIVE_LIVE_MANIFEST.md
    worktree_after_fast_forward: UNKNOWN_NOT_REOBSERVED
  current_restore_order: P3_05_RECOVERY_ARCHIVE_REUSED_WITHOUT_REHASH_FOR_DURABLE_CLOSE

standing_owner_priority:
  highest_operational_rule: preserve_current_or_recoverable_long_running_productive_work_before_remote_sync_restore_reset_checkout_merge_or_host_replacement
  remote_newer_does_not_override_unpreserved_execution_work: true
  session_model_SSH_tmux_or_host_change_does_not_invalidate_verified_work: true
  current_required_order:
    - retain_P4_02_durable_close_evidence
    - load_and_compile_P4_03_only_from_its_exact_prompt_when_execution_begins

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

p3_13_durable_close:
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
  status: COMPLETE; P3_READY_FOR_P4
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

approved_execution_program:
  language: biella.codex.end_to_end/v2
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  active_graph_location: docs/project-state/04_BIELLA_ACTIVE_TASK.md
  active_graph: P4_03_AUTHORIZED_PROMPT_NOT_LOADED_OR_COMPILED
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
    - exact_active_numbered_prompt
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
  P3_14_durable_close: VERIFIED
  P3_READY_FOR_P4: VERIFIED
  P4_01_durable_close: VERIFIED
  P4_02_durable_close: VERIFIED
  P3_08_or_later_completion_claims_from_rejected_execution: REJECTED
  exact_recovered_P3_05_worktree_contents: REUSED_FOR_DURABLE_CLOSE_WITHOUT_REHASH
  multi_AI_execution_map_approved_by_user: true
  future_numbered_activation_queue_prepared: true
  previous_VPS_destroyed: VERIFIED_USER_REPORT
  current_execution_host_exists: true
  Drive_recovery_archive_exact_readback: VERIFIED_FRESH_2026_08_31
```
