from __future__ import annotations

from pathlib import Path

from biella_production_state import ProductionState, TaskRecord, active_task_path


def compile_task_packet(repo_root: Path, production: ProductionState, task: TaskRecord) -> str:
    contract_path = active_task_path(repo_root)
    contract = contract_path.read_text(encoding="utf-8").strip()
    section = next(section for section in production.sections if section.id == task.section_id)
    return (
        "Biella canonical production task. Execute one task boundary only.\n"
        f"PROJECT_ROOT: {production.project_root}\n"
        f"SECTION: {section.id} | {section.title}\n"
        f"TASK: {task.id} [{task.task_class}] {task.title}\n"
        "ACTIVE_CONTRACT: docs/project-state/04_BIELLA_ACTIVE_TASK.md\n"
        "--- ACTIVE CONTRACT ---\n"
        f"{contract}\n"
        "--- END ACTIVE CONTRACT ---\n"
        "Preserve all completed work and return COMPLETE_ALREADY if current evidence already satisfies this task. "
        "Use real editable outputs and task-derived validation. Before expensive general-model work, use "
        "`biella resource route <capability>` and configured specialized Resources when they materially reduce time/tokens or improve quality. "
        "Free/trial/prepaid and paid Resources are authorized when useful; use one provider by default and validate its output. "
        "Runner owns canonical state transition: do not edit 03/04 task identity or Project PRODUCTION status/next-task metadata. "
        "Do not probe quota/balance, do not inspect or manage Codex usage/resets/credits, and do not advance beyond this task."
    )
