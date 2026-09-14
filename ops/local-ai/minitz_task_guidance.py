from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _task_map(program: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    tasks = program.get("tasks") if isinstance(program.get("tasks"), list) else []
    return {str(task.get("task_id")): task for task in tasks if isinstance(task, Mapping) and task.get("task_id")}


def _safe_task_name(task_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", str(task_id))


def guidance_path(root: Path, task_id: str) -> Path:
    return Path(root) / f"{_safe_task_name(task_id)}.json"


def build_guidance_for_task(task: Mapping[str, Any]) -> dict[str, Any]:
    required = [str(value) for value in task.get("required_capabilities", []) if str(value).strip()]
    candidates = [str(value) for value in task.get("candidate_capabilities", []) if str(value).strip()]
    return {
        "schema": "minitz.task_guidance_projection/v1",
        "authority": "NONE",
        "progression_authority": False,
        "canonical_write_authority": "MINITZ_TASK_PROGRAM_ONLY",
        "task_id": str(task.get("task_id") or ""),
        "task_revision": task.get("revision"),
        "task_record_sha256": str(task.get("task_record_sha256") or ""),
        "status": task.get("status"),
        "title": task.get("title"),
        "objective": task.get("objective") or {},
        "acceptance": list(task.get("acceptance") or []),
        "required_evidence": list(task.get("required_evidence") or []),
        "dependencies": list(task.get("dependencies") or []),
        "inputs": list(task.get("inputs") or []),
        "source_refs": list(task.get("source_refs") or []),
        "resource_requirements": list(task.get("resource_requirements") or []),
        "negative_controls": list(task.get("negative_controls") or []),
        "write_scope": task.get("write_scope") or {},
        "execution_guidance": task.get("execution_guidance") or {},
        "capability_context": {
            "required": required, "candidates": candidates,
            "consume_for_execution": True, "promotion": "VALIDATED_CANDIDATE_ONLY",
            "system_promotion_authority": False,
        },
    }


def helper_view(document: Mapping[str, Any]) -> dict[str, Any]:
    execution = document.get("execution_guidance") if isinstance(document.get("execution_guidance"), Mapping) else {}
    return {
        "schema": "minitz.task_guidance_helper_view/v1",
        "authority": "NONE",
        "progression_authority": False,
        "task_id": document.get("task_id"),
        "task_revision": document.get("task_revision"),
        "task_record_sha256": document.get("task_record_sha256"),
        "title": document.get("title"),
        "objective": document.get("objective") or {},
        "acceptance": list(document.get("acceptance") or []),
        "required_evidence": list(document.get("required_evidence") or []),
        "negative_controls": list(document.get("negative_controls") or []),
        "capability_context": document.get("capability_context") or {},
        "execution_guidance": {
            key: execution.get(key) for key in (
                "authority", "procedure", "validation", "recovery", "completion_state", "failure_states"
            ) if execution.get(key) is not None
        },
        "capability_learning_rule": (
            "Use this task-scoped guidance to improve task execution and propose capability candidates only. "
            "Durable System/Engine capability or knowledge promotion requires current MiniTZ validation and canonical admission."
        ),
    }


def _current_task_id(program: Mapping[str, Any]) -> str:
    current = program.get("current_execution") if isinstance(program.get("current_execution"), Mapping) else {}
    return str(current.get("task_id") or "")


def _start_task_id(program: Mapping[str, Any], start_offset: int) -> tuple[str, str]:
    tasks = [task for task in program.get("tasks", []) if isinstance(task, Mapping)]
    current_id = _current_task_id(program)
    ids = [str(task.get("task_id") or "") for task in tasks]
    if current_id not in ids:
        raise ValueError("current MiniTZ task is absent from Task Program")
    start_index = ids.index(current_id) + int(start_offset)
    if start_index >= len(tasks):
        raise ValueError("guidance start offset is beyond the Task Program")
    return current_id, ids[start_index]


def build_guidance_documents(
    program: Mapping[str, Any], *, start_offset: int = 6, start_task_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    tasks = [task for task in program.get("tasks", []) if isinstance(task, Mapping)]
    ids = [str(task.get("task_id") or "") for task in tasks]
    if start_task_id is None:
        _origin, start_task_id = _start_task_id(program, start_offset)
    if start_task_id not in ids:
        raise ValueError("guidance activation task is absent from Task Program")
    start_index = ids.index(start_task_id)
    return {
        str(task["task_id"]): build_guidance_for_task(task)
        for task in tasks[start_index:]
    }


def load_task_guidance(
    program: Mapping[str, Any], task_id: str, root: Path,
) -> dict[str, Any] | None:
    task = _task_map(program).get(str(task_id))
    if task is None:
        return None
    path = guidance_path(root, task_id)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    if str(document.get("task_id") or "") != str(task_id):
        return None
    if document.get("task_revision") != task.get("revision"):
        return None
    if str(document.get("task_record_sha256") or "") != str(task.get("task_record_sha256") or ""):
        return None
    if document.get("authority") != "NONE" or document.get("progression_authority") is not False:
        return None
    return document


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(dict(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def _read_manifest(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((Path(root) / "MANIFEST.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_guidance_documents(
    program_path: Path, *, output_root: Path | None = None, start_offset: int = 6,
) -> dict[str, Any]:
    program_path = Path(program_path).resolve()
    raw = program_path.read_bytes()
    program = json.loads(raw)
    root = Path(output_root) if output_root is not None else program_path.parent / "task_guidance"
    root.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(root)
    persisted_start = str(manifest.get("activation_start_task_id") or "")
    ids = [str(task.get("task_id") or "") for task in program.get("tasks", []) if isinstance(task, Mapping)]
    origin_current = str(manifest.get("origin_current_task_id") or "")
    try:
        persisted_offset = int(manifest.get("origin_offset"))
    except (TypeError, ValueError):
        persisted_offset = None
    if persisted_start in ids and persisted_offset == int(start_offset):
        start_task_id = persisted_start
        origin_offset = int(start_offset)
    elif origin_current in ids:
        start_index = ids.index(origin_current) + int(start_offset)
        if start_index >= len(ids):
            raise ValueError("guidance start offset is beyond the Task Program origin")
        start_task_id = ids[start_index]
        origin_offset = int(start_offset)
    else:
        origin_current, start_task_id = _start_task_id(program, start_offset)
        origin_offset = int(start_offset)
    documents = build_guidance_documents(program, start_offset=start_offset, start_task_id=start_task_id)
    for task_id, document in documents.items():
        _atomic_json(guidance_path(root, task_id), document)
    desired = {guidance_path(root, task_id).name for task_id in documents}
    for path in root.glob("*.json"):
        if path.name != "MANIFEST.json" and path.name not in desired:
            path.unlink()
    program_sha = hashlib.sha256(raw).hexdigest()
    manifest = {
        "schema": "minitz.task_guidance_manifest/v1",
        "authority": "NONE",
        "progression_authority": False,
        "canonical_task_program": str(program_path),
        "canonical_program_revision": program.get("revision"),
        "canonical_program_sha256": program_sha,
        "origin_current_task_id": origin_current,
        "origin_offset": origin_offset,
        "activation_start_task_id": start_task_id,
        "guide_count": len(documents),
        "task_ids": list(documents),
        "capability_promotion": "VALIDATED_CANDIDATE_ONLY",
    }
    _atomic_json(root / "MANIFEST.json", manifest)
    return {
        "schema": "minitz.task_guidance_write_receipt/v1",
        "authority": "NONE",
        "program_sha256": program_sha,
        "first_guided_task": start_task_id,
        "guide_count": len(documents),
        "output_root": str(root.resolve()),
        "manifest": str((root / "MANIFEST.json").resolve()),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(prog="minitz-task-guidance")
    parser.add_argument("--program", required=True)
    parser.add_argument("--output-root")
    parser.add_argument("--start-offset", type=int, default=6)
    args = parser.parse_args()
    receipt = write_guidance_documents(
        Path(args.program),
        output_root=Path(args.output_root) if args.output_root else None,
        start_offset=args.start_offset,
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


def task_is_in_guided_range(
    program: Mapping[str, Any], task_id: str, root: Path, *, start_offset: int = 6,
) -> bool:
    ids = [str(task.get("task_id") or "") for task in program.get("tasks", []) if isinstance(task, Mapping)]
    if task_id not in ids:
        return False
    manifest = _read_manifest(root)
    start_task_id = str(manifest.get("activation_start_task_id") or "")
    if start_task_id not in ids:
        try:
            _origin, start_task_id = _start_task_id(program, start_offset)
        except ValueError:
            return False
    return ids.index(task_id) >= ids.index(start_task_id)
