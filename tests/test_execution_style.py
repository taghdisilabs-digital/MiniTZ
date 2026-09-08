from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))


def test_proven_execution_style_is_executable_and_quality_first():
    import biella_execution_style as style
    profile = style.proven_execution_style()
    assert profile["schema"] == "biella.proven_execution_style/v1"
    assert profile["quality"] == "HIGHEST_QUALITY_ELIGIBLE"
    assert profile["task_class"] == "COMPLEXITY_ONLY_NOT_A_GATE"
    assert profile["owner_acceptance"] == "FINAL_IMMEDIATE_TRANSITION"
    assert profile["optional_resources"] == "NONBLOCKING"
    assert profile["manual_progress_edit"] == "SLEEP_EDIT_VALIDATE_SYNC_RESUME"
    assert profile["cache"] == "QUALITY_FIRST_REUSE"
    assert profile["path_resolution"] == "LOOKUP_BEFORE_USE"
    assert profile["completion_boundary"] == "CLEAN_CANONICAL_WORKTREE"
    assert profile["dirty_during_task"] == "TASK_SCOPED_TEMPORARY_ONLY"
    assert profile["cycle"] == "EXECUTE_VALIDATE_COMMIT_COMPLETE_PERSIST_ADVANCE"
    assert profile["observer_authority"] == "READ_ONLY_ZERO_LIVENESS"


def test_proven_style_records_exact_forbidden_failure_patterns():
    import biella_execution_style as style
    forbidden = set(style.forbidden_execution_patterns())
    assert forbidden == {
        "post_acceptance_task_extension",
        "timer_executor_rotation",
        "no_progress_wait_state",
        "optional_local_ai_startup_gate",
        "installer_enablement_toggle",
        "concurrent_manual_progress_edit",
        "format_by_renaming",
        "guessed_path_without_lookup",
        "request_time_full_asset_scan",
        "missing_bootstrap_auth",
    }


def test_proven_style_prompt_is_compact_and_actionable():
    import biella_execution_style as style
    text = style.proven_execution_style_prompt()
    for token in (
        "PROVEN_EXECUTION_STYLE",
        "OWNER_ACCEPTANCE_IS_FINAL",
        "MODEL_SILENCE_IS_NOT_FAILURE",
        "EXACT_LOOKUP_BEFORE_PATH_USE",
        "OPTIONAL_RESOURCES_NEVER_BLOCK",
        "CACHE_REUSE_QUALITY_FIRST",
        "MANUAL_PROGRESS_EDIT_IS_TRANSACTIONAL",
        "CLEAN_TASK_BOUNDARY",
    ):
        assert token in text
    assert len(text) < 3000


def test_runner_uses_the_proven_style_function():
    runner = (LOCAL_AI / "biella_production_runner.py").read_text(encoding="utf-8")
    assert "import biella_execution_style as execution_style" in runner
    assert "execution_style.proven_execution_style_prompt()" in runner


def test_installer_deploys_proven_execution_style_module():
    installer = (LOCAL_AI / "install-biella-ai.sh").read_text(encoding="utf-8")
    assert '"$SOURCE_DIR/biella_execution_style.py"' in installer


def test_system_has_explicit_forbidden_and_proven_style_sections():
    system = (ROOT / "docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md").read_text(encoding="utf-8")
    assert "## HOW BIELLA WILL NOT WORK" in system
    assert "## PROVEN EXECUTION STYLE" in system
    assert "biella_execution_style.proven_execution_style" in system


def test_static_guard_detects_only_known_active_progress_killers():
    import biella_execution_style as style
    findings = style.active_progress_killer_findings(
        runner_text="BIELLA_EXECUTOR_STALL_ROTATION WAITING_FOR_STRONG_MODEL bounded_no_progress",
        unit_text="Requires=biella-ollama.service\nExecStartPre=/usr/local/lib/biella-workstation/biella-qwen-ready.sh",
        installer_text="systemctl disable biella-codex-production.service",
    )
    assert set(findings) == {
        "timer_executor_rotation",
        "no_progress_wait_state",
        "optional_local_ai_startup_gate",
        "installer_enablement_toggle",
    }


def test_current_active_controller_sources_pass_static_guard():
    import biella_execution_style as style
    assert style.active_progress_killer_findings(
        runner_text=(LOCAL_AI / "biella_production_runner.py").read_text(encoding="utf-8"),
        unit_text=(LOCAL_AI / "biella-codex-production.service").read_text(encoding="utf-8"),
        installer_text=(LOCAL_AI / "install-biella-ai.sh").read_text(encoding="utf-8"),
    ) == ()


def test_installer_runs_static_progress_killer_guard_before_install():
    installer = (LOCAL_AI / "install-biella-ai.sh").read_text(encoding="utf-8")
    assert "biella_execution_style.py\" audit" in installer


def test_governing_operator_surfaces_reference_forbidden_and_proven_style():
    surfaces = (
        ROOT / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md",
        ROOT / "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md",
        ROOT / "ops/workstation/AGENTS.md",
    )
    for path in surfaces:
        text = path.read_text(encoding="utf-8")
        assert "HOW_BIELLA_WILL_NOT_WORK" in text
        assert "PROVEN_EXECUTION_STYLE" in text
