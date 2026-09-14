from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

_FORBIDDEN = (
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
)


def forbidden_execution_patterns() -> tuple[str, ...]:
    return _FORBIDDEN


def proven_execution_style() -> dict[str, Any]:
    return {
        "schema": "minitz.proven_execution_style/v1",
        "quality": "HIGHEST_QUALITY_ELIGIBLE",
        "task_class": "COMPLEXITY_ONLY_NOT_A_GATE",
        "owner_acceptance": "FINAL_IMMEDIATE_TRANSITION",
        "optional_resources": "NONBLOCKING",
        "manual_progress_edit": "DIRECT_EDIT_VALIDATE_SYNC_CONTINUE",
        "cache": "QUALITY_FIRST_REUSE",
        "path_resolution": "LOOKUP_BEFORE_USE",
        "completion_boundary": "CLEAN_CANONICAL_WORKTREE",
        "dirty_during_task": "TASK_SCOPED_TEMPORARY_ONLY",
        "cycle": "EXECUTE_VALIDATE_COMMIT_COMPLETE_PERSIST_ADVANCE",
        "publication": "INDEPENDENT_DURABLE_RETRY",
        "drive_publication": "OWNER_EXPLICIT_ONLY",
        "source_difference": "REPAIR_INLINE_PRESERVE_SESSION",
        "observer_authority": "READ_ONLY_ZERO_LIVENESS",
        "model_silence": "NOT_FAILURE",
        "task_progression": "AUTO_ADVANCE_AFTER_ACCEPTED_COMPLETION",
        "project_isolation": "STRICT",
        "repetitive_failure_recovery": "FINGERPRINT_ROOT_CAUSE_BOUNDED_REPAIR",
        "repair_regression_policy": "PRESERVE_WORKING_CAPABILITIES",
        "context_preservation": "DETAIL_SCOPED_HORIZON_PROJECT_AWARENESS",
        "creation_functions": "PRESERVE_CREATE_BUILD_MODIFY_EXECUTE",
        "forbidden": list(_FORBIDDEN),
    }


def proven_execution_style_prompt() -> str:
    return (
        "PROVEN_EXECUTION_STYLE:\n"
        "- OWNER_ACCEPTANCE_IS_FINAL: accepted current work closes immediately; do not extend it.\n"
        "- MODEL_SILENCE_IS_NOT_FAILURE: never rotate or terminate a healthy model turn because it is quiet.\n"
        "- EXACT_LOOKUP_BEFORE_PATH_USE: retrieve/search exact source paths and formats before commands or edits; never guess.\n"
        "- OPTIONAL_RESOURCES_NEVER_BLOCK: local AI, GPU residency, website, observers, helpers and optional providers cannot gate production.\n"
        "- CACHE_REUSE_QUALITY_FIRST: reuse verified work, persistent session context and compact cached context when correctness is preserved.\n"
        "- MANUAL_PROGRESS_EDIT_IS_TRANSACTIONAL: sleep/freeze, edit, validate, sync/readback, then resume the exact task/session.\n"
        "- CLEAN_TASK_BOUNDARY: dirty task-scoped work is temporary; commit task-owned implementation/proof directly; unrelated dirty files and publication retries do not reopen passed work.\n"
        "- AUTO_ADVANCE_AFTER_ACCEPTED_COMPLETION: commit local output/continuity and immediately select the next canonical task; remote publication retries independently.\n"
        "- TASK_CLASS_IS_NOT_A_BLOCKER: hard/deep labels describe complexity only and never create approval or waiting stages.\n"
        "- DO_NOT_EXPAND_ACCEPTANCE_SCOPE: use only the exact current Task/Project contract and latest owner direction.\n"
        "- CONTINUE_REQUIRES_EXACT_UNMET_CRITERION: CONTINUE must name the unmet criterion and smallest executable next action.\n"
        "- NO_MONITOR_ONLY_STALL: never spend turns merely polling or narrating a productive resource.\n"
        "- EXECUTOR_OWNS_ROUTINE_BLOCKER_RESOLUTION: resolve routine implementation, environment, tooling and resource blockers with existing authorized Resources, reversible setup, bounded routing, or canonical deferral; never ask the owner to perform setup the executor can do. Surface only a genuine owner product decision, unavailable credential/entitlement, or new paid/external authority, while independent work continues.\n"
        "- FORMAT_IDENTITY_MUST_BE_VERIFIED: never convert an artifact by renaming an extension; verify actual format/magic/contract.\n"
        "- PROJECT_BOUNDARIES_STAY_ISOLATED: caching and delegation never leak project/customer source, credentials or authority.\n"
        "- REPETITIVE_FAILURE_IS_A_REPAIR_SIGNAL: correlate repeats, fix the smallest root cause, then add targeted anti-regression coverage.\n"
        "- NEVER_BREAK_WORKING_CAPABILITIES_TO_FIX_ONE_ERROR: preserve verified paths; rerun affected validation plus dependent regression checks.\n"
        "- PRESERVE_DETAIL_SCOPED_HORIZON_AND_PROJECT_AWARENESS: compact duplicate/rebuildable noise only; retain current objective, scope, identities, unfinished delta, acceptance and provenance.\n"
        "- PRESERVE_CREATION_FUNCTIONS: repair/simplification must retain working create/build/generate/edit/execute/test/package paths.\n"
    )

_FORBIDDEN_ACTIVE_LITERALS = {
    "timer_executor_rotation": ("MINITZ_EXECUTOR_STALL_ROTATION", "task.executor_stall_recovery"),
    "no_progress_wait_state": ("WAITING_FOR_STRONG_MODEL", "bounded_no_progress"),
    "optional_local_ai_startup_gate": (
        "Requires=minitz-ollama.service",
        "ExecStartPre=/usr/local/lib/minitz-workstation/minitz-qwen-ready.sh",
    ),
    "installer_enablement_toggle": ("systemctl disable minitz-production.service",),
}


def active_progress_killer_findings(*, runner_text: str, unit_text: str, installer_text: str) -> tuple[str, ...]:
    surfaces = {"runner": runner_text, "unit": unit_text, "installer": installer_text}
    findings: list[str] = []
    for name, literals in _FORBIDDEN_ACTIVE_LITERALS.items():
        if any(literal in text for literal in literals for text in surfaces.values()):
            findings.append(name)
    return tuple(findings)


def _audit_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="minitz-execution-style")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--runner", type=Path, required=True)
    audit.add_argument("--unit", type=Path, required=True)
    audit.add_argument("--installer", type=Path, required=True)
    args = parser.parse_args(argv)
    findings = active_progress_killer_findings(
        runner_text=args.runner.read_text(encoding="utf-8"),
        unit_text=args.unit.read_text(encoding="utf-8"),
        installer_text=args.installer.read_text(encoding="utf-8"),
    )
    if findings:
        print("FORBIDDEN_ACTIVE_PROGRESS_KILLERS=" + ",".join(findings))
        return 2
    print("ACTIVE_PROGRESS_KILLER_AUDIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_audit_cli())
