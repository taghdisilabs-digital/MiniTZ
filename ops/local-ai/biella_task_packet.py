from __future__ import annotations

from pathlib import Path

from biella_production_state import ProductionState, TaskRecord, active_task_path


def compile_task_packet(repo_root: Path, production: ProductionState, task: TaskRecord) -> str:
    contract_path = active_task_path(repo_root)
    contract = contract_path.read_text(encoding="utf-8").strip()
    section = next(section for section in production.sections if section.id == task.section_id)
    return (
        "Biella canonical production task. Execute one task boundary only.\n"
        f"PRODUCTION_SOURCE_ROOT: {production.project_root}\n"
        f"PRODUCTION_PRIORITY: {production.priority_policy}; follow physical PRODUCTION.md order, not numeric task IDs.\n"
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
        "Resolve routine task needs autonomously: install/configure task-scoped dependencies, create missing local support files, use authorized Resources, and repair reversible environment/tool/provider issues when they are required by this task. "
        "Do not stop for confirmation, routine permission, design approval, or owner decision when the active task or prior owner direction already authorizes the work. If a genuinely destructive or irreversible external action is required and not already authorized, or a required authority/fact is truly unavailable, preserve progress, record the exact need, and return CONTINUE rather than inventing completion. "
        "For every final deliverable, preserve the exact canonical local file and publish it to the configured canonical destination defined by current Project/task authority; verify exact remote identity and bytes/digest when supported. Never invent a destination. The controller independently retries GitHub/Drive continuity publication from exact committed bytes; transport loss does not require another implementation turn. Actual deployment or remote-delivery task acceptance still requires its real external evidence. Record genuine delivery failures in `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` without fabricating success. "
        "Commit this task's implementation/evidence locally before returning COMPLETE; the Auto Feeder owns GitHub/Drive publication and canonical state transition. "
        "Do not edit 03/04 task identity or Project PRODUCTION status/next-task metadata. Never use exact 03/04 byte identity as a gameplay/runtime validation gate because those files are volatile continuity state. "
        "Do not probe quota/balance, do not inspect or manage Codex usage/resets/credits, and do not advance beyond this task."
    )


def _bounded_text(value: str, maximum: int) -> str:
    value = str(value).strip()
    return value if len(value) <= maximum else value[: maximum - 3] + "..."


def build_task_memory_capsule(task: TaskRecord, project_root: Path, *, session_id: str | None,
                              summary: str = "", evidence=(), dirty_paths=()) -> dict[str, object]:
    paths = sorted(dict.fromkeys(_bounded_text(str(item), 240) for item in dirty_paths if str(item).strip()))
    proof = [_bounded_text(str(item), 480) for item in evidence if str(item).strip()]
    return {
        "schema": "biella.task_memory/v1",
        "task_id": task.id,
        "task_class": task.task_class,
        "title": _bounded_text(task.title, 240),
        "project_root": str(Path(project_root)),
        "session_id": session_id,
        "summary": _bounded_text(summary, 3000),
        "evidence": proof[:24],
        "dirty_path_count": len(paths),
        "dirty_paths": paths[:80],
        "next_action": "Continue this task from preserved work; resolve the remaining validation/failure without redoing verified work.",
    }


def compile_resume_packet(task: TaskRecord, capsule_path: Path) -> str:
    return (
        "RESUME_EXISTING_TASK_SESSION\n"
        f"TASK: {task.id} [{task.task_class}] {task.title}\n"
        f"TASK_MEMORY: {Path(capsule_path)}\n"
        "Continue the same task from existing session memory and the current worktree. Read TASK_MEMORY first, then only the files/evidence needed for the next decision. "
        "The initial active contract and project authority remain in this session; re-read them only if current source indicates a material change. "
        "Preserve all dirty/verified work; never reset, clean, stash, or restart the task. Keep full local tool/Unreal/Git/Drive/resource capability. "
        "Prefer targeted local commands and bounded outputs over broad rereads. Resolve routine task needs autonomously, including install/configure task-scoped dependencies and reversible tool/environment repair. "
        "Do not stop for confirmation or routine permission when this task is already authorized. Final deliverables must remain at their canonical local path and be published/read back at any configured canonical destination; never invent a destination. Diagnose prior failures from `/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl` when relevant. Commit coherent task-owned implementation/evidence; the controller can finalize an omitted task-local commit without task replay. Return CONTINUE only for actual unmet task work, not a continuity publication retry. "
        "Do not advance beyond this task or manage Codex quota/usage.\n"
    )


def _bounded_file_content(path: Path | None, maximum: int) -> str:
    if path is None or not Path(path).is_file():
        return "NONE"
    text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    return text if len(text) <= maximum else text[: maximum - 1] + "…"


def compile_bounded_fallback_packet(task: TaskRecord, capsule_path: Path, projection_path: Path | None, guide_path: Path | None) -> str:
    projection = str(Path(projection_path)) if projection_path else "NONE"
    guide = str(Path(guide_path)) if guide_path else "NONE"
    memory_content = _bounded_file_content(Path(capsule_path), 6500)
    guide_content = _bounded_file_content(Path(guide_path) if guide_path else None, 9000)
    projection_content = _bounded_file_content(Path(projection_path) if projection_path else None, 8000)
    return (
        "BIELLA_BOUNDED_FALLBACK\n"
        f"TASK: {task.id} [{task.task_class}] {task.title}\n"
        f"TASK_MEMORY: {Path(capsule_path)}\nMEMORY_PROJECTION: {projection}\nTASK_GUIDE: {guide}\n"
        "--- TASK MEMORY CONTENT ---\n" + memory_content + "\n--- END TASK MEMORY CONTENT ---\n"
        "--- TASK GUIDE CONTENT ---\n" + guide_content + "\n--- END TASK GUIDE CONTENT ---\n"
        "--- MEMORY PROJECTION CONTENT ---\n" + projection_content + "\n--- END MEMORY PROJECTION CONTENT ---\n"
        "QUALITY ORDER: correctness/evidence > continuity > speed > token savings. Execute one bounded technical outcome as one coherent implementation-and-validation slice; do not artificially stop after a trivial edit while the same verified boundary still has executable task work. "
        "Read exact current source/evidence when implementation detail is needed. The embedded TASK_MEMORY and TASK_GUIDE are the bounded current recovery context; MEMORY_PROJECTION is derivative and never overrides current source. "
        "Use every task-fit configured Resource that materially helps this exact slice: resolve capabilities with `biella resource route <capability>` or the exact registered adapter, prefer deterministic/local/specialized resources when quality is preserved, and fall through configured alternatives on real provider/tool failure. Do not call irrelevant providers or duplicate equivalent work merely to increase fan-out. Independent resource operations may run concurrently only when dependencies, side effects, Project isolation, and capacity permit. "
        "Validate resource-produced code/data/analysis against current source and exact task evidence before integration. Helpers/resources never become task/completion/progression authority; do not lower acceptance because a preferred strong model is unavailable. Preserve failure evidence, credentials/project isolation, and the quota-probe prohibition. "
        "Do not broad-reread history, redo verified work, reset/clean/stash/restart the task, or create a second queue/memory/workflow. "
        "Do not create planning/status/summary artifacts merely to show progress; create or change files only when the bounded technical outcome requires them. "
        "Prefer substantive executable changes plus exact tests/diagnostics/evidence over prose. Reuse current task-owned bytes and passed evidence aggressively so a later authoritative strong route can inspect, repair only the remaining delta, perform full unchanged acceptance verification, and finalize without restarting the task. If no useful bounded action can be completed from current evidence, return CONTINUE immediately with the exact blocker and do not repeat exploration. "
        "Preserve all existing dirty/verified work. Do not edit task ordering, 03/04, Project production status, task guides, or project authority files. Do not git commit, push, publish, or manage/probe quota or credits. "
        "Do not declare the whole task complete from this fallback packet; return CONTINUE with concise exact evidence even when the bounded increment itself passes.\n"
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
        f"PRODUCTION_PRIORITY: {production.priority_policy}. Preserve this owner priority and current canonical task order.\n"
        f"PROJECT_ROOT: {production.project_root}\nSECTION: {section.id} | {section.title}\nMODE: {mode}\nEXISTING:\n{existing}\n"
        "Tasks must be non-overlapping, dependency-aware, execution-sized, and limited to this section. Preserve completed work. "
        "Use biella resource routing when specialized Resources reduce model work. Do not create approval or owner-decision gate tasks for already-authorized work; express executable missing work directly and provision routine task needs as part of execution. "
        "Do not invent scope, duplicate semantic tasks, probe quotas, or reopen completed work without material invalidation evidence."
    )
