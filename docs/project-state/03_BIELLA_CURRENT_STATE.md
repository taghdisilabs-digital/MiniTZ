# 03 - BIELLA CURRENT STATE

```yaml
schema: biella.current_state/v7
state_class: VOLATILE
update_rule: replace_stale_values; do_not_append_history
observed_date: 2026-09-05

authority:
  if_conflict: [CURRENT_EXECUTION_STATE, CURRENT_GITHUB_SOURCE, CURRENT_CANONICAL_DRIVE, VERIFIED_HISTORICAL_EVIDENCE, REFERENCE_OR_PLAN, INFERENCE]
  correction_rule: invalidate_only_conflicting_state; preserve_independently_valid_work

repository:
  repository: patrickminitz-web/biella-engine
  branch: main
  canonical_checkout: /root/biella/repos/biella-engine
  structure: ONE_REPOSITORY_MONOREPO
  implementation_commit: f69bcd04fa1b8cd27704c67338eb5cc562eb1403
  implementation_tree: 115beb43a7db4a7b953b2eb17d56854e67501242
  github_readback: VERIFIED_EXACT_MAIN_AND_REQUIRED_PATHS
  active_remote_branches: [main]
  historical_branch_refs: 15_REMOTE_ARCHIVE_TAGS

active_execution:
  id: D01-45
  project: Biella Games
  section: demo01
  state: PENDING
  controller: biella-codex
  consolidation_state: COMPLETE_VERIFIED

  runner: READY
  runner_implementation_commit: d9f4360a4430cd663f37c064db42d803917aea64
  runner_implementation_tree: f233e4e212625aaa9ca06685f3d3b8c32e0886cc
  runner_service_commit: f0521d0df75db5352fb6e9cd12ee67cdf309e7de
  controller_auth_fix_commit: 51f5712542de016a429a4450bf1884ac649e03b7
games:
  project_path: projects/biella-games
  production_source: projects/biella-games/docs/PRODUCTION.md
  section: demo01
  completed_demo_tasks: 44
  total_demo_tasks: 50
  queued_successor: D01-45
  latest_preservation_commit: f7e74205988cb48946e62efeffe5c5330ec6437b
  latest_preservation_tree: 1324b3dd942927352abaa2ef70a463cbdfca53db
  late_delta_import: 9_OF_9_CHANGED_PATHS_IMPORTED
  migration_qualification: VERIFIED_BUILD_AND_HEADLESS_RUNTIME
  navigation_qualification: D01_029_RECAST_POSITIONING_BUILD_AND_LIVE_RUNTIME_PASS
  navigation_evidence: projects/biella-games/Build/Demo01/D01-029-acceptance.md
  combat_qualification: D01_030_WEAPON_COLLISION_DAMAGE_RESPONSE_BUILD_AND_LIVE_RUNTIME_PASS
  combat_evidence: projects/biella-games/Build/Demo01/D01-030-acceptance.md
  shared_interaction_qualification: D01_031_SIX_DIRECTED_DAMAGE_EDGES_30_120_FPS_PASS
  shared_interaction_evidence: projects/biella-games/Build/Demo01/D01-031-acceptance.md
  pressure_state_qualification: D01_032_AUTHORITATIVE_PRESSURE_TRANSITIONS_PASS
  pressure_state_evidence: projects/biella-games/Build/Demo01/D01-032-acceptance.md
  d01_033_recovery_checkpoint: 6582d4bcbc5a86dc87495a21e9f4f4c6187b8fc7
  task_boundary: D01-45_PENDING

engine_numbered_execution:
  P4_01_through_P4_05: COMPLETE_REUSE_REQUIRED
  P4-06: INCOMPLETE_DEFERRED
  P4-06_missing: authoritative_Engine_evidence_and_combined_failure_scenario
  FOUNDATION_COMPLETE: false
  deferred_reason: MAHDI_EXPLICIT_WORKFLOW_CONSOLIDATION_AND_GAMES_EXECUTION_DIRECTION

resources:
  dispatcher: /usr/local/bin/biella resource
  free_credit_preferred: true
  paid_allowed: true
  quota_probe_forbidden: true
  verified_live_operations: [Tavily_search, Exa_semantic_search, Groq_fast_llm]
  configured_connected: [Cloudflare, Saturn, Groq, Cerebras, OpenRouter, Mistral, Tavily, Exa, Pinecone, Qdrant, Deepgram, AssemblyAI, ElevenLabs, StabilityAI, Supabase, Neon, Upstash, Cloudinary, Axiom, Pexels, Modal]
  needs_locator: []
  restricted_or_unresolved: [Axiom]
  qdrant_endpoint: CONFIGURED_RUNTIME_RESOURCE

drive:
  canonical_root_name: Biella
  canonical_root_id: 1Z6_qwN9hfHIheXZ_9pYCG8dRDMuRN-l7
  current_folder_id: 1GbPXqefsuU7Uf6U4f4yrGetQTcphOLI3
  projects_folder_id: 1hQ2IR00sxHdXiMAMiyzxadXstiPnMoz9
  outputs_folder_id: 1O1F5DT-zIbWTAjtJlhVJslodG7rDVUEW
  archive_folder_id: 1dn3IEwDf_cPO7l5Zd0mZ84b_IOG0GsU3
  current_state_file_id: 1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4
  active_task_file_id: 1liutA8evH6rPjk-U4tgR13l_kqBrx-DF
  production_map_doc_id: 1aRnEdxQwe-Dn3VRh29CMkTXlxHOjcCjtfR-GNxQpp6s
  games_project_folder_id: 1SgvztxBMthMRbr6BPS-n9OXa2RYyXXDb
  provenance_file_id: 156sYJpCS_aVo62hSyir4Kfc5gDe_aTc0
  qualification_file_id: 1_Mlg42DpKmLIcaF02QOeJJ2xXYXzNGvk
  production_file_id: 1LUVUz0iG_xL7eOkF1OEBtJ2R9a455eqx
  navigation_state: VERIFIED

control:
  url: https://control.biellagames.dev/control/
  source: website/src/control
  views: [Control, Work, Outputs, System]
  public_readback: VERIFIED_HTTP_200_EXACT_INSTALLED_INDEX

workspace:
  active_repo_roots: [/root/biella/repos/biella-engine]
  old_games_repo: /root/biella/archive/repos/biella-games-preserved-20260905
  spark_recovery: /root/biella/archive/recovery/spark-biella-games
  obsolete_recovery_backups_checkpoints: REMOVED
  legacy_games_production_json_sha256: e23bd1634ae14cad059a8196f4e82dd6de982014c4892616348c2393ada18ecd
  legacy_games_production_json: REMOVED_SUPERSEDED_BY_PROJECT_PRODUCTION_MD
  legacy_feeder_runtime_archive: /root/biella/archive/runtime/codex-feeder/biella-games-production-20260905
  legacy_feeder_runtime_manifest_sha256: f819eafba2ad62ce002cb88e98bc3a32a5847e47a1309ad54fc7c5c63d8970a3

archived_repositories:
  patrickminitz-web/biella-games: ARCHIVED_READ_ONLY
  patrickminitz-web/capability_preparation: ARCHIVED_READ_ONLY

evidence:
  migration_provenance: docs/migration/ONE_REPO_PROVENANCE_2026-09-05.md
  games_monorepo_qualification: docs/migration/evidence/MONOREPO_GAMES_QUALIFICATION_2026-09-05.md
  prior_durable_state: GIT_HISTORY_ARCHIVE_TAGS_AND_DEDICATED_EVIDENCE
```
