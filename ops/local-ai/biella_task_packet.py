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
        "Preserve and continue any existing partial/uncommitted work for this same task; never reset or restart it from scratch. "
        "Repair or reroute internal/provider/tool failures and return CONTINUE while useful work remains; owner direction is already authoritative and is never a blocking result. "
        "Commit this task's implementation/evidence locally before returning COMPLETE; the Auto Feeder owns GitHub/Drive publication and canonical state transition. "
        "Do not edit 03/04 task identity or Project PRODUCTION status/next-task metadata. "
        "Do not probe quota/balance, do not inspect or manage Codex usage/resets/credits, and do not advance beyond this task."
    )


def section_plan_schema() -> dict[str, object]:
    classes = ["creation", "deep_memory", "hard", "hard_creation", "medium", "simple"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "required": ["section_id", "complete", "summary", "evidence", "tasks"],
        "properties": {
            "section_id": {"type": "string"}, "complete": {"type": "boolean"},
            "summary": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}},
            "tasks": {"type": "array", "maxItems": 50, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["class", "title"],
                "properties": {"class": {"type": "string", "enum": classes}, "title": {"type": "string", "minLength": 1, "maxLength": 240}},
            }},
        },
    }


def compile_section_packet(production: ProductionState, section, *, audit: bool) -> str:
    existing = "\n".join(f"{task.id} [{task.status}] {task.title}" for task in section.tasks[-50:]) or "none"
    mode = "Audit current source/evidence. Return complete=true only when this section is actually satisfied; otherwise return only missing delta tasks." if audit else "Plan incomplete work. Return 20-50 bounded tasks unless materially fewer are required by accepted scope."
    return (
        "Biella production section planning boundary.\n"
        f"PROJECT_ROOT: {production.project_root}\nSECTION: {section.id} | {section.title}\nMODE: {mode}\nEXISTING:\n{existing}\n"
        "Tasks must be non-overlapping, dependency-aware, execution-sized, and limited to this section. Preserve completed work. "
        "Use biella resource routing when specialized Resources reduce model work. Do not invent scope, duplicate semantic tasks, probe quotas, or reopen completed work without material invalidation evidence."
    )
