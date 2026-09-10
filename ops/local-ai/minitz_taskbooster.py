from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


_PATH_SUFFIXES = (
    ".cpp", ".cc", ".c", ".h", ".hpp", ".py", ".md", ".json",
    ".ini", ".yaml", ".yml", ".uasset", ".umap", ".wav", ".png",
)


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    reason: str
    evidence: tuple[str, ...] = ()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _candidate_path(token: str, scope_root: Path) -> Path | None:
    token = token.strip().strip('"\'')
    if not token or "://" in token or any(ch in token for ch in "*?{}"):
        return None
    if " " in token or not ("/" in token or token.lower().endswith(_PATH_SUFFIXES)):
        return None
    if token.startswith("/Game/"):
        rel = token[len("/Game/"):].strip("/")
        base = scope_root / "Content" / rel
        for candidate in (base, Path(str(base) + ".uasset"), Path(str(base) + ".umap")):
            if candidate.is_file() and _inside(candidate, scope_root):
                return candidate.resolve()
        return None
    candidate = Path(token)
    candidate = candidate if candidate.is_absolute() else scope_root / candidate
    if not candidate.is_file() or not _inside(candidate, scope_root):
        return None
    return candidate.resolve()


def extract_grounded_targets(text: str, scope_root: Path) -> tuple[str, ...]:
    root = Path(scope_root).resolve()
    result: list[str] = []
    for token in re.findall(r"`([^`\n]+)`", str(text or "")):
        candidate = _candidate_path(token, root)
        if candidate is None:
            continue
        result.append(candidate.relative_to(root).as_posix())
    return tuple(sorted(dict.fromkeys(result)))


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(encoded)


def compile_packet(*, task_id: str, task_state_digest: str, objective: str,
                   acceptance: Sequence[str], scope_root: Path,
                   local_assist: Mapping[str, Any], allowed_commands: Sequence[str] = ()) -> dict[str, Any]:
    root = Path(scope_root).resolve()
    assist_text = str(local_assist.get("text") or "")
    allowed_reads = []
    for relative in extract_grounded_targets(assist_text, root):
        path = root / relative
        allowed_reads.append({"path": relative, "sha256": _sha256_file(path), "size_bytes": path.stat().st_size})
    assist_digest = _canonical_digest(dict(local_assist))
    identity = {
        "schema": "minitz.taskbooster_packet/v1",
        "task_id": str(task_id),
        "task_state_digest": str(task_state_digest),
        "objective": str(objective).strip(),
        "acceptance": [str(item).strip() for item in acceptance if str(item).strip()],
        "scope_root": str(root),
        "allowed_reads": allowed_reads,
        "allowed_writes": [],
        "allowed_commands": [str(item).strip() for item in allowed_commands if str(item).strip()],
        "local_assist_digest": assist_digest,
        "local_assist_text": assist_text[:6000],
        "authority": "NONE",
        "execution_mode": "READ_ONLY_SPARK_MICROTASK",
    }
    packet = dict(identity)
    packet["booster_id"] = "TB::" + _canonical_digest(identity)
    return packet


def booster_result_schema() -> dict[str, Any]:
    evidence_ref = {
        "type": "object", "additionalProperties": False,
        "required": ["path", "sha256", "line_start", "line_end", "quote", "symbol"],
        "properties": {
            "path": {"type": "string"}, "sha256": {"type": "string"},
            "line_start": {"type": "integer", "minimum": 1},
            "line_end": {"type": "integer", "minimum": 1},
            "quote": {"type": "string"}, "symbol": {"type": ["string", "null"]},
        },
    }
    action = {
        "type": "object", "additionalProperties": False,
        "required": ["target_path", "action", "rationale", "symbol"],
        "properties": {
            "target_path": {"type": "string"}, "action": {"type": "string"},
            "rationale": {"type": "string"}, "symbol": {"type": ["string", "null"]},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "required": ["booster_id", "status", "finding", "evidence_refs", "candidate_actions",
                     "candidate_patch", "recommended_commands", "uncertainties"],
        "properties": {
            "booster_id": {"type": "string"},
            "status": {"type": "string", "enum": ["USEFUL", "NO_ACTION"]},
            "finding": {"type": "string"},
            "evidence_refs": {"type": "array", "items": evidence_ref},
            "candidate_actions": {"type": "array", "items": action},
            "candidate_patch": {"type": "string"},
            "recommended_commands": {"type": "array", "items": {"type": "string"}},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
        },
    }


def _reject(reason: str, *evidence: str) -> ValidationResult:
    return ValidationResult(False, reason, tuple(evidence))


def _allowed_reads(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in packet.get("allowed_reads", []) if isinstance(packet.get("allowed_reads"), list) else []:
        if isinstance(item, Mapping) and isinstance(item.get("path"), str):
            result[str(item["path"])] = item
    return result


def _patch_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for raw in str(text or "").splitlines():
        match = re.match(r"^(?:---|\+\+\+)\s+(?:a|b)/(.+)$", raw.strip())
        if match and match.group(1) != "/dev/null":
            paths.add(match.group(1).strip())
    return paths


def _validate_actual_inputs(packet: Mapping[str, Any], scope_root: Path) -> ValidationResult | None:
    root = Path(scope_root).resolve()
    for relative, expected in _allowed_reads(packet).items():
        path = (root / relative).resolve()
        if not _inside(path, root) or not path.is_file():
            return _reject("STALE_INPUT_DIGEST", relative)
        if _sha256_file(path) != str(expected.get("sha256") or ""):
            return _reject("STALE_INPUT_DIGEST", relative)
    return None


def _evidence_quote(path: Path, start: int, end: int) -> str | None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if start < 1 or end < start or end > len(lines):
        return None
    return "\n".join(lines[start - 1:end])


def validate_result(packet: Mapping[str, Any], result: Mapping[str, Any], scope_root: Path,
                    *, current_task_state_digest: str) -> ValidationResult:
    if str(packet.get("task_state_digest") or "") != str(current_task_state_digest):
        return _reject("STALE_INPUT_DIGEST", "task_state_digest")
    if str(result.get("booster_id") or "") != str(packet.get("booster_id") or ""):
        return _reject("STALE_INPUT_DIGEST", "booster_id")
    stale = _validate_actual_inputs(packet, scope_root)
    if stale is not None:
        return stale
    allowed = _allowed_reads(packet)
    commands = tuple(str(item) for item in packet.get("allowed_commands", []) if isinstance(item, str))
    recommended = result.get("recommended_commands") if isinstance(result.get("recommended_commands"), list) else []
    if any(str(item) not in commands for item in recommended):
        return _reject("FAILED_COMMAND", *[str(item) for item in recommended])
    status = str(result.get("status") or "")
    refs = result.get("evidence_refs") if isinstance(result.get("evidence_refs"), list) else []
    if status == "USEFUL" and not refs:
        return _reject("UNSUPPORTED_CLAIM", str(result.get("finding") or ""))
    root = Path(scope_root).resolve()
    for ref in refs:
        if not isinstance(ref, Mapping):
            return _reject("UNSUPPORTED_CLAIM", "invalid evidence ref")
        relative = str(ref.get("path") or "")
        if relative not in allowed:
            return _reject("UNSUPPORTED_PATH", relative)
        path = (root / relative).resolve()
        if str(ref.get("sha256") or "") != str(allowed[relative].get("sha256") or ""):
            return _reject("STALE_INPUT_DIGEST", relative)
        try:
            start = int(ref.get("line_start")); end = int(ref.get("line_end"))
        except (TypeError, ValueError):
            return _reject("UNSUPPORTED_CLAIM", relative)
        quote = _evidence_quote(path, start, end)
        if quote is None or quote != str(ref.get("quote") or ""):
            return _reject("UNSUPPORTED_CLAIM", relative)
        symbol = str(ref.get("symbol") or "").strip()
        if symbol and symbol not in path.read_text(encoding="utf-8", errors="replace"):
            return _reject("INVENTED_SYMBOL", symbol)
    actions = result.get("candidate_actions") if isinstance(result.get("candidate_actions"), list) else []
    for action in actions:
        if not isinstance(action, Mapping):
            return _reject("UNSUPPORTED_CLAIM", "invalid candidate action")
        target = str(action.get("target_path") or "")
        if target not in allowed:
            return _reject("SCOPE_ESCAPE", target)
        symbol = str(action.get("symbol") or "").strip()
        if symbol and symbol not in (root / target).read_text(encoding="utf-8", errors="replace"):
            return _reject("INVENTED_SYMBOL", symbol)
    patch_paths = _patch_paths(str(result.get("candidate_patch") or ""))
    if any(path not in allowed for path in patch_paths):
        return _reject("SCOPE_ESCAPE", *sorted(patch_paths - set(allowed)))
    if status not in {"USEFUL", "NO_ACTION"}:
        return _reject("UNSUPPORTED_CLAIM", f"status={status}")
    return ValidationResult(True, "ACCEPTED", tuple(sorted(allowed)))


def failure_evidence(reason: str, raw_output: str) -> dict[str, Any]:
    raw = str(raw_output)
    return {
        "schema": "minitz.taskbooster_failure/v1",
        "authority": "NONE",
        "reason": str(reason),
        "raw_sha256": _sha256_bytes(raw.encode("utf-8")),
        "preserve_raw": True,
    }
