from __future__ import annotations

import re
from collections.abc import Iterable

_CANONICAL_RE = re.compile(r"^D(?P<group>\d{2})-(?P<number>\d{2})$")
_LEGACY_D_RE = re.compile(r"^D(?P<group>\d{2})-(?P<number>\d{3})$")
_LEGACY_STAGE_RE = re.compile(r"^S(?P<group>\d{1,2})-(?P<number>\d{3})$")
_STAGE_SECTION_RE = re.compile(r"^stage(?P<group>\d{1,2})$")


def canonical_task_id(value: str) -> str:
    task_id = str(value).strip().strip("`")
    if _CANONICAL_RE.fullmatch(task_id):
        return task_id
    match = _LEGACY_D_RE.fullmatch(task_id)
    if match:
        number = int(match.group("number"))
        if 0 <= number <= 99:
            return f"D{int(match.group('group')):02d}-{number:02d}"
    match = _LEGACY_STAGE_RE.fullmatch(task_id)
    if match:
        number = int(match.group("number"))
        if 0 <= number <= 99:
            return f"D{int(match.group('group')):02d}-{number:02d}"
    return task_id


def section_group(section_id: str) -> int:
    if section_id == "demo01":
        return 1
    match = _STAGE_SECTION_RE.fullmatch(str(section_id).strip())
    if not match:
        raise ValueError(f"section has no canonical D group: {section_id}")
    group = int(match.group("group"))
    if not 0 <= group <= 99:
        raise ValueError(f"section D group out of range: {section_id}")
    return group


def next_task_id(section_id: str, existing_ids: Iterable[str]) -> str:
    group = section_group(section_id)
    maximum = 0
    for raw in existing_ids:
        canonical = canonical_task_id(raw)
        match = _CANONICAL_RE.fullmatch(canonical)
        if match and int(match.group("group")) == group:
            maximum = max(maximum, int(match.group("number")))
    if maximum >= 99:
        raise ValueError(f"no free canonical task id in D{group:02d}")
    return f"D{group:02d}-{maximum + 1:02d}"
