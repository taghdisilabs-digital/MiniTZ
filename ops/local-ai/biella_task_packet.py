from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from biella_production_state import ProductionState, TaskRecord, active_task_path


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?P<prefix>(?:[\"']?(?:api[_-]?key|password|passwd|login[_-]?token|refresh[_-]?token|"
    r"access[_-]?token|auth(?:entication)?[_-]?secret|private[_-]?key|credential(?:s)?|"
    r"authorization|bearer|token|secret)[\"']?\s*[:=]\s*[\"']?))(?P<value>[^,\s\"'};]+)"
)
_OBVIOUS_SECRET = re.compile(
    r"(?:\bbearer\s+[A-Za-z0-9._~+/=-]{16,}|\b(?:sk|ghp|github_pat|xox[baprs]-)[A-Za-z0-9._-]{12,})",
    re.IGNORECASE,
)
_SECRET_KEY = re.compile(
    r"(?:api[_-]?key|password|passwd|login[_-]?token|refresh[_-]?token|access[_-]?token|"
    r"auth(?:entication)?[_-]?secret|private[_-]?key|credential(?:s)?|authorization|bearer|token|secret)\Z",
    re.IGNORECASE,
)


def _redact_text(value: object) -> str:
    text = str(value)
    text = _SECRET_ASSIGNMENT.sub(lambda match: match.group("prefix") + "[REDACTED]", text)
    return _OBVIOUS_SECRET.sub("[REDACTED]", text)


def _safe_object(value: object, *, maximum: int = 4096, depth: int = 0) -> object:
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, child in value.items():
            name = str(key)
            if _SECRET_KEY.fullmatch(name) and not name.lower().endswith(("_ref", "_refs", "_sha256")):
                result[name] = "[REDACTED]"
            else:
                result[name] = _safe_object(child, maximum=maximum, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_object(child, maximum=maximum, depth=depth + 1) for child in value[:64]]
    if isinstance(value, str):
        return _bounded_text(_redact_text(value), maximum)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _bounded_text(_redact_text(value), maximum)


def _task_authority(task: TaskRecord, *, task_revision: int | None = None,
                    task_digest: str | None = None) -> dict[str, object] | None:
    revision = task_revision
    digest = task_digest
    for raw in task.evidence:
        marker = str(raw).strip()
        if marker.startswith("MINITZ_TASK_REVISION:"):
            candidate = marker.split(":", 1)[1].strip()
            if revision is None and candidate.isdigit():
                revision = int(candidate)
        elif marker.startswith("MINITZ_TASK_SHA256:"):
            candidate = marker.split(":", 1)[1].strip()
            if digest is None and _SHA256.fullmatch(candidate):
                digest = candidate
    if revision is None and digest is None:
        return None
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1 or not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise ValueError("MiniTZ task identity requires an exact positive revision and SHA-256 digest")
    return {
        "task_id": task.id,
        "task_revision": revision,
        "task_digest": digest,
        "scope_ref": f"task://minitz/{task.id}/{revision}",
        "progression_authority": "MINITZ_TASK_PROGRAM_ONLY",
    }


def compile_task_packet(repo_root: Path, production: ProductionState, task: TaskRecord) -> str:
    if production.priority_policy == "MINITZ_TASK_PROGRAM":
        authority = _task_authority(task)
        identity = ""
        if authority is not None:
            identity = (
                f"MINITZ_TASK_REVISION: {authority['task_revision']}\n"
                f"MINITZ_TASK_SHA256: {authority['task_digest']}\n"
                f"MINITZ_TASK_SCOPE_REF: {authority['scope_ref']}\n"
            )
        return (
            "MiniTZ OS canonical task. Execute exactly the current living Task Program boundary.\n"
            f"MINITZ_REPO_ROOT: {Path(repo_root).resolve()}\n"
            f"TASK: {task.id} [{task.task_class}] {task.title}\n"
            + identity
            + "TASK_AUTHORITY: /root/biella/analysis/live_audit/TASK_PROGRAM.json\n"
            "ACTIVE_GOAL: BUILD_MINITZ_OS_ONLY\n"
            "Preserve exact current task revision/digest, verified work, task/session memory, checkpoints, evidence and failures. "
            "Read only the smallest current OS source/evidence set needed for the next decision. "
            "Historical non-OS game/project, website, market, pilot, investor and old product-edition material is provenance only unless this exact OS task explicitly requires a migrated capability. "
            "Use task-fit deterministic/local/specialized resources first when quality is preserved; provider/model/resource selection never changes authority. "
            "Five Boost sections and thirty Commander lanes are non-independent derived execution support under this same canonical task; they cannot change task order/status/completion. "
            "Do not run the retired one/two TaskBooster workflow. "
            "Fresh provider sessions bootstrap only from the current MiniTZ OS policy and durable task memory; provider/model/helper changes cannot override the Task Program or create another progression authority. "
            "Raw API/login secrets must not enter prompts, semantic memory, general caches, ordinary logs, source, or public artifacts. "
            "Never start/stop/sleep/resume/reboot/power-transition MiniTZ or the host unless Mahdi explicitly ordered that lifecycle action. "
            "Repair the smallest failed boundary; never reset, clean, stash, or replay the whole task. "
            "Validate exact affected scope and return only evidence-grounded task status. Do not advance beyond this task.\n"
        )
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
    value = _redact_text(value).strip()
    return value if len(value) <= maximum else value[: maximum - 3] + "..."


def build_task_memory_capsule(task: TaskRecord, project_root: Path, *, session_id: str | None,
                              summary: str = "", evidence=(), dirty_paths=(),
                              task_revision: int | None = None, task_digest: str | None = None,
                              program_identity: Mapping[str, object] | None = None,
                              worktree_identity: Mapping[str, object] | None = None,
                              owner_lifecycle: Mapping[str, object] | None = None,
                              policy_ref: str | None = None,
                              checkpoint_identity: Mapping[str, object] | None = None) -> dict[str, object]:
    paths = sorted(dict.fromkeys(_bounded_text(str(item), 240) for item in dirty_paths if str(item).strip()))
    proof = [_bounded_text(str(item), 480) for item in evidence if str(item).strip()]
    capsule: dict[str, object] = {
        "schema": "biella.task_memory/v1",
        "task_id": task.id,
        "task_class": task.task_class,
        "title": _bounded_text(task.title, 240),
        "project_root": str(Path(project_root)),
        "session_id": _redact_text(session_id) if session_id is not None else None,
        "summary": _bounded_text(summary, 3000),
        "evidence": proof[:24],
        "dirty_path_count": len(paths),
        "dirty_paths": paths[:80],
        "next_action": "Continue this task from preserved work; resolve the remaining validation/failure without redoing verified work.",
    }
    authority = _task_authority(task, task_revision=task_revision, task_digest=task_digest)
    if authority is not None:
        capsule.update({
            "task_revision": authority["task_revision"],
            "task_digest": authority["task_digest"],
            "scope_ref": authority["scope_ref"],
            "progression_authority": "MINITZ_TASK_PROGRAM_ONLY",
            "provider_session_authority": False,
            "task_identity": dict(authority),
            "bootstrap": {
                "source": "CURRENT_MINITZ_OS_POLICY_AND_DURABLE_TASK_MEMORY",
                "policy_ref": _bounded_text(policy_ref or "ops/workstation/AGENTS.md", 512),
                "task_memory_ref": f"task-memory/{task.id}.json",
                "provider_session_override": False,
                "progression_authority": "MINITZ_TASK_PROGRAM_ONLY",
                "owner_resume_required": True,
            },
        })
        capsule["session_identity"] = {
            "task_id": task.id,
            "session_id": capsule["session_id"],
        }
        if program_identity is not None:
            capsule["program_identity"] = _safe_object(program_identity, maximum=1024)
        if worktree_identity is not None:
            capsule["worktree_identity"] = _safe_object(worktree_identity, maximum=2048)
        if owner_lifecycle is not None:
            capsule["owner_lifecycle"] = _safe_object(owner_lifecycle, maximum=1024)
        if checkpoint_identity is not None:
            capsule["checkpoint_identity"] = _safe_object(checkpoint_identity, maximum=2048)
        capsule["continuity"] = {
            "task": dict(authority),
            "session": capsule["session_identity"],
            "worktree": capsule.get("worktree_identity"),
            "checkpoint": capsule.get("checkpoint_identity"),
        }
    return capsule


def compile_resume_packet(task: TaskRecord, capsule_path: Path) -> str:
    packet = (
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
    authority = _task_authority(task)
    if authority is not None:
        packet += (
            f"MINITZ_TASK_REVISION: {authority['task_revision']}\n"
            f"MINITZ_TASK_SHA256: {authority['task_digest']}\n"
            f"MINITZ_TASK_SCOPE_REF: {authority['scope_ref']}\n"
            "Fresh provider sessions must bootstrap from the current MiniTZ OS policy and durable task memory in TASK_MEMORY. "
            "Provider/model/helper changes are replaceable Resources only; they cannot override MiniTZ authority or create another task-progression source. "
            "Owner sleep remains authoritative until Mahdi explicitly resumes MiniTZ; no helper, provider, installer, recovery flow, or session may imply resume.\n"
        )
    return packet


def _bounded_file_content(path: Path | None, maximum: int) -> str:
    if path is None or not Path(path).is_file():
        return "NONE"
    text = _redact_text(Path(path).read_text(encoding="utf-8", errors="replace")).strip()
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
