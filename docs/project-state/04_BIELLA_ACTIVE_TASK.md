# 04 — BIELLA ACTIVE TASK

```yaml
schema: biella.active_task/v4

active_task:
  id: P3-05
  global_number: 36
  phase: P3
  title: 3D Modeling and Scene Production Pack
  state: RESTORE_GPT_5_6_THEN_EXECUTE_END_TO_END
  predecessor: P3-04
  predecessor_result_commit: 28fde1e9224236ce7b37b74434727463e96d9893
  predecessor_result_tree: d7efcc21cab8dc86488ef91963f48791dbe0dca0
  predecessor_remote_readback: VERIFIED
  successor: P3-06
  successor_authorized_before_close: false

exact_prompt:
  title: 36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
  local_path: /root/biella/import/canon/BiellaEngine/40_PROMPTS/P3/36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
  drive_path: gdrive:BiellaEngine/40_PROMPTS/P3/36_P3-05_3D_Modeling_and_Scene_Production_Pack.md.docx
  drive_id: 1TIG3GggwGdu3ma1e5MeeIontVUO4pmSP4aggJKps0Kg
  local_docx_sha256: abb4255869736f571329e3e55409fc8675f927a4ab09bc50bbb6556bbd48c050
  live_drive_exported_docx_sha256: d411b17a37fc988eda9a563c0285515e9be478a12ba024c23dc6696da2c8c8e6
  canonical_text_sha256: e8688b4e820c7df1096f4a88a9e0bcda792fbe17c3e1690839a689bbcf6f46ed
  canonical_text_extraction: pandoc_plain_wrap_none
  local_and_live_drive_text_equal: true

recovery_boundary:
  durable_git_base: e228a7bb6db6f94af15dde4a8fb110b028eddbed
  durable_git_base_tree: b407138ac05af441487aa6005700da98b8016906
  preserve_execution_through: "2026-08-30T10:08:48.575Z"
  reject_execution_beginning: "2026-08-30T10:44:52Z"
  recovery_archive: GPT56_EXACT_RECOVERY_2026-08-30.tar.gz
  recovery_archive_sha256: 73052d6cffea8017bebee64750d8de532654ca6c7e8dffff62caa554efe30f0d
  restore_status: PENDING_NEXT_BOOT
  rule: restore_exact_pre_boundary_file_contents; never_replay_rejected_session_mutations

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
  language: biella.codex.end_to_end/v1
  mode: SINGLE_END_TO_END_NUMBERED_EXECUTION
  objective: maximize_durable_P3_05_progress_per_model_token_without_lowering_validation_quality
  model_guard:
    intended_model: user_selected_non_Spark_Codex_model
    forbidden_silent_substitution: gpt-5.3-codex-spark
    if_intended_model_unavailable: stop_before_repository_write
  normal_context:
    - 03_BIELLA_CURRENT_STATE.md
    - 04_BIELLA_ACTIVE_TASK.md
    - exact_P3_05_canonical_prompt
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
    AWS_MCP_default: OFF_FOR_NORMAL_P3_05_CODE_EXECUTION
    Cloudflare_MCP_default: OFF
    NVIDIA_skill_bundle_default: OFF_UNLESS_REAL_GPU_SUBPATH_REQUIRES_IT
    generic_template_and_workflow_bundles_default: OFF
  agent_policy:
    default_subagents: 0
    parallel_agents_only_if: independent_work_and_material_wall_clock_benefit_exceeds_duplicated_context_cost
    prohibited_default_chains:
      - planner_implementer_reviewer
      - maker_critic_validator_repair
      - permanent_manager_hierarchy
  observation_policy:
    inspect_exact_state_once: true
    reuse_verified_outputs: true
    reread_unchanged_files: false
    reobserve_only_if_materially_invalidated: true
  output_policy:
    prefer_exact_ranges_and_symbols: true
    bound_terminal_output: true
    prohibit_binary_asset_dump_into_model_context: true
    prohibit_full_large_diff_dump_unless_required: true
  validation_policy:
    development_funnel:
      - exact_new_or_failing_test
      - focused_P3_05_module
      - directly_affected_regression
    final_task_derived_gate: ONCE_AFTER_IMPLEMENTATION_STABILIZES
    after_final_failure: fix_smallest_affected_boundary_then_rerun_only_invalidated_gates
  usage_policy:
    check_status_before_execution: true
    usage_low_behavior: finish_current_coherent_boundary; persist_valid_work; record_exact_remaining_gap; do_not_expand_scope
    usage_exhaustion_is_not_invalidation: true

execution_graph:
  T0_RECOVER:
    - boot_or_connect_to_canonical_host
    - reobserve_HEAD_branch_upstream_and_dirty_state
    - verify_execution_source_base
    - restore_exact_GPT_5_6_P3_05_file_contents_from_recovery_evidence
    - verify_expected_dirty_path_set
    - reject_post_10_44_52_mutations
  T1_MINIMUM_INSPECTION:
    - read_03_04_and_exact_P3_05_prompt_once
    - inspect_only_recovered_P3_05_and_direct_dependencies
    - derive_short_already_satisfied_remaining_blocked_gap_set
  T2_EXECUTE:
    - preserve_valid_recovered_GPT_5_6_work
    - implement_only_missing_P3_05_requirements
    - no_kernel_redesign
    - no_P3_06_work
  T3_FOCUSED_VALIDATE:
    - run_narrowest_affected_tests_while_editing
    - fix_smallest_failure_boundary
    - avoid_repeated_full_suite_runs
  T4_FINAL_VALIDATE:
    required_semantics:
      - editable_native_3D_source_when_required
      - exact_source_tool_runtime_export_identity
      - structured_inspection
      - geometry_topology_UV_material_scene_operations
      - export_reopen_parse_and_derivation
      - preview_as_secondary_evidence_only
      - real_and_reference_adapter_contract_neutrality
      - Project_isolation
      - recovery_fencing_idempotency_and_durability
      - no_DCC_specific_kernel_fields
      - no_global_polygon_budget
    evidence_rule: exact_commands_and_observed_counts_only
  T5_PERSIST:
    - coherent_implementation_commit
    - push_main
    - remote_commit_tree_and_required_path_readback
  T6_CONTINUITY:
    - replace_03_with_exact_closed_state
    - replace_04_with_P3_06_packet_only_after_P3_05_durable_close
    - publish_matching_Drive_continuity
    - stop_execution_boundary

P3_05_required_scope:
  capabilities:
    - 3d.inspect
    - 3d.model
    - 3d.mesh_edit
    - 3d.topology
    - 3d.uv
    - 3d.material
    - 3d.scene
    - 3d.convert
    - 3d.optimize
    - 3d.validate
    - 3d.preview
  interfaces:
    - ThreeDToolAdapter
    - 3D_ProductionPack_descriptor
    - 3D_pack_Artifact_roles_and_validators
  invariants:
    - DCC_SDK_types_stay_adapter_local
    - native_editable_source_is_preserved_where_meaningful
    - exports_bind_exact_source_target_exporter_version_settings_and_ContentRef
    - process_exit_alone_is_not_success
    - render_or_preview_is_not_editable_source_proof
    - Project_style_poly_scale_rules_remain_Project_scoped
    - missing_DCC_affects_route_not_Capability
    - independent_assets_may_run_concurrently_under_existing_scheduler
    - game_engine_is_not_3D_source_authority
    - no_domain_kernel_changes

completion_contract:
  software_and_adapter_source: required
  task_scoped_tests: required
  typecheck_build_runtime_or_DCC_evidence: task_derived_and_required_where_applicable
  exact_Git_commit_and_tree: required
  remote_readback_after_push: required
  current_Drive_continuity_readback: required
  completion_claim_without_matching_evidence: forbidden
```
