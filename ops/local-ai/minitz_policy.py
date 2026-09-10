"""MiniTZ-native policy identities and scoped candidate projections.

This module deliberately produces analysis-only projections.  It does not
admit semantic objects, choose a task head, mutate the MiniTZ Task Program,
or promote a policy projection into universal memory authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "minitz.policy_projection/v1"
AUTHORITY = "NONE_CANDIDATE_ANALYSIS"
GRAPH = "MiniTZ"
ACTIVE_HISTORICAL_STEERING_TARGET = 0
LEGACY_POLICY_RELATIVE = "docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md"

_GLOBAL_GATE_RE = re.compile(
    r"(?:\bP4-06\b|global[\s-]+gate|global[\s-]+qualification|universal[\s-]+gate)",
    re.IGNORECASE,
)


# These are semantic replacements, not deletion filters.  The old wording is
# retained in the historical source identity and, when encountered in a
# current source, in a provenance-only record.  These candidate rules define
# what the active MiniTZ projection means instead.
_SEMANTIC_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "historical-steering-target-zero",
        "scope_ref": "scope://minitz/system",
        "role": "historical_steering",
        "statement": (
            "Historical policy material has zero active MiniTZ steering authority; "
            "useful bytes remain available as provenance only."
        ),
    },
    {
        "rule_id": "p4-06-scoped-acceptance",
        "scope_ref": "scope://minitz/system",
        "role": "qualification_gate_replacement",
        "statement": (
            "The historical P4-06 global gate is semantically replaced by "
            "current task-specific acceptance and dependency-scoped validation; "
            "no global gate blocks unrelated work."
        ),
        "replaces": ["P4-06", "global-gate-residue"],
    },
    {
        "rule_id": "single-minitz-progression-authority",
        "scope_ref": "scope://minitz/system",
        "role": "progression_authority",
        "statement": (
            "The one living MiniTZ Task Program owns MiniTZ task order and status; "
            "ledgers, maps, helpers, sessions, and projections are non-authoritative."
        ),
    },
    {
        "rule_id": "project-agents-bootstrap-scope",
        "scope_ref": "scope://minitz/system",
        "role": "project_agents_boundary",
        "statement": (
            "A Project may maintain one current scoped AGENTS.md for new-session "
            "bootstrap and agent behavior, but it cannot own task order, status, "
            "progression authority, or universal memory truth."
        ),
    },
    {
        "rule_id": "historical-agents-provenance-only",
        "scope_ref": "scope://minitz/system",
        "role": "historical_provenance",
        "statement": (
            "Historical AGENTS.md revisions remain provenance; only the exact "
            "current scoped projection steers a new session."
        ),
    },
    {
        "rule_id": "donor-policy-no-duplicate-authority",
        "scope_ref": "scope://minitz/system",
        "role": "donor_policy_boundary",
        "statement": (
            "Donor policy task semantics may contribute preserved value and "
            "provenance, but they cannot create a duplicate MiniTZ policy task "
            "or second authority."
        ),
    },
    {
        "rule_id": "scoped-policy-digest-invalidation",
        "scope_ref": "scope://minitz/system",
        "role": "derived_context_invalidation",
        "statement": (
            "A scoped policy source digest change invalidates only derived context "
            "that declares a dependency on that same scope."
        ),
    },
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_ref(data: bytes) -> str:
    return "sha256:" + _sha(data)


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _digest_ref(encoded)


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _project_scope(repo_root: Path, project_root: Path) -> str:
    relative = _relative_path(project_root, repo_root).strip("/")
    if not relative:
        relative = project_root.name or "project"
    return "scope://project/" + relative


def _source_spec(path: Path, *, scope_ref: str, source_role: str, origin_kind: str) -> dict[str, Any]:
    return {
        "path": path,
        "scope_ref": scope_ref,
        "source_role": source_role,
        "origin_kind": origin_kind,
    }


def _active_specs(repo_root: Path, project_root: Path) -> list[dict[str, Any]]:
    system_scope = "scope://minitz/system"
    specs = [
        _source_spec(
            repo_root / "docs/project-state/00_BIELLA_PROJECT_OPERATING_CONTRACT.md",
            scope_ref=system_scope,
            source_role="OPERATING_CONTRACT",
            origin_kind="CURRENT_SOURCE",
        ),
        _source_spec(
            repo_root / "docs/project-state/BIELLA_ISOLATED_PROJECT_EXECUTION_BRIDGE.yaml",
            scope_ref=system_scope,
            source_role="ISOLATED_PROJECT_BRIDGE",
            origin_kind="CURRENT_SOURCE",
        ),
        _source_spec(
            repo_root / "docs/project-state/BIELLA_DURABLE_SOURCE_AND_SYNC_RULES.md",
            scope_ref=system_scope,
            source_role="DURABLE_SOURCE_RULES",
            origin_kind="CURRENT_SOURCE",
        ),
        _source_spec(
            repo_root / "ops/workstation/AGENTS.md",
            scope_ref=system_scope,
            source_role="CURRENT_SCOPED_AGENTS",
            origin_kind="CURRENT_SCOPED_PROJECTION",
        ),
        _source_spec(
            project_root / "AGENTS.md",
            scope_ref=_project_scope(repo_root, project_root),
            source_role="CURRENT_PROJECT_AGENTS",
            origin_kind="CURRENT_SCOPED_PROJECTION",
        ),
    ]
    return [spec for spec in specs if Path(spec["path"]).is_file()]


def _provenance_specs(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / LEGACY_POLICY_RELATIVE
    if not path.is_file():
        return []
    return [
        _source_spec(
            path,
            scope_ref="scope://minitz/system",
            source_role="LEGACY_POLICY_PROVENANCE",
            origin_kind="HISTORICAL_SOURCE",
        )
    ]


def _source_identity(spec: dict[str, Any], repo_root: Path, *, active: bool) -> dict[str, Any]:
    path = Path(spec["path"])
    data = path.read_bytes()
    return {
        "path": _relative_path(path, repo_root),
        "sha256": _sha(data),
        "bytes": len(data),
        "scope_ref": spec["scope_ref"],
        "source_role": spec["source_role"],
        "origin_kind": spec["origin_kind"],
        "active": active,
        "authority": AUTHORITY,
    }


def _chunks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def _normalized_rule_text(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def _candidate_rule_identity(scope_ref: str, text: str) -> str:
    return _digest_ref((scope_ref + "\0" + _normalized_rule_text(text)).encode("utf-8"))


def _semantic_rule_identity(rule_id: str, scope_ref: str) -> str:
    return _digest_ref(("semantic-rule\0" + scope_ref + "\0" + rule_id).encode("utf-8"))


def _scope_digest(source_rows: Iterable[dict[str, Any]]) -> str:
    values = [
        {
            "path": row["path"],
            "sha256": row["sha256"],
            "source_role": row["source_role"],
            "origin_kind": row["origin_kind"],
        }
        for row in source_rows
    ]
    return _canonical_digest(sorted(values, key=lambda item: (item["path"], item["source_role"])))


def _agents_digest(source_rows: Iterable[dict[str, Any]]) -> str | None:
    rows = [row for row in source_rows if "AGENTS" in str(row.get("source_role", ""))]
    if not rows:
        return None
    return _scope_digest(rows)


def _scope_metadata(active_sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in active_sources:
        grouped[str(source["scope_ref"])].append(source)
    result: dict[str, dict[str, Any]] = {}
    for scope_ref, rows in sorted(grouped.items()):
        effective_digest = _scope_digest(rows)
        agents_digest = _agents_digest(rows)
        result[scope_ref] = {
            "scope_ref": scope_ref,
            "effective_policy_identity": "candidate-policy:" + effective_digest,
            "effective_policy_digest": effective_digest,
            "agents_policy_identity": (
                "candidate-agents:" + agents_digest if agents_digest else None
            ),
            "agents_policy_digest": agents_digest,
            "active_source_paths": sorted(str(row["path"]) for row in rows),
            "derived_context_dependency": "scope-ref:" + scope_ref,
        }
    return result


def _semantic_rule_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for definition in _SEMANTIC_RULES:
        scope_ref = str(definition["scope_ref"])
        rule_id = str(definition["rule_id"])
        rows.append({
            "rule_id": rule_id,
            "rule_identity": _semantic_rule_identity(rule_id, scope_ref),
            "scope_ref": scope_ref,
            "role": definition["role"],
            "statement": definition["statement"],
            "source_ref": "minitz-policy:" + rule_id,
            "source_paths": [],
            "origin_kind": "GENERATED_CANDIDATE",
            "authority": AUTHORITY,
            "semantic_status": "ACTIVE_CANDIDATE",
            "active_projection_count": 1,
            "replaces": list(definition.get("replaces", [])),
        })
    return rows


def build_policy_projection(repo_root: Path, project_root: Path) -> dict[str, Any]:
    """Build the lossless, scoped MiniTZ policy projection for one compaction.

    Only exact current scoped sources are active.  The legacy policy source is
    represented by an identity in ``provenance_sources`` and contributes no
    active records or policy digest.
    """

    repo_root = Path(repo_root).resolve()
    project_root = Path(project_root).resolve()
    specs = _active_specs(repo_root, project_root)
    provenance_specs = _provenance_specs(repo_root)
    active_sources = [_source_identity(spec, repo_root, active=True) for spec in specs]
    provenance_sources = [_source_identity(spec, repo_root, active=False) for spec in provenance_specs]
    scopes = _scope_metadata(active_sources)
    # Semantic MiniTZ rules remain well-defined even when a reduced checkout
    # omits every current system source.  The empty-scope digest is still an
    # execution input; it does not invent source authority.
    system_scope = "scope://minitz/system"
    scopes.setdefault(system_scope, {
        "scope_ref": system_scope,
        "effective_policy_identity": "candidate-policy:" + _canonical_digest([]),
        "effective_policy_digest": _canonical_digest([]),
        "agents_policy_identity": None,
        "agents_policy_digest": None,
        "active_source_paths": [],
        "derived_context_dependency": "scope-ref:" + system_scope,
    })
    source_by_path = {str(row["path"]): row for row in active_sources}

    raw_rules: dict[tuple[str, str], dict[str, Any]] = {}
    raw_records: list[dict[str, Any]] = []
    for spec, source in zip(specs, active_sources):
        path = Path(spec["path"])
        scope_ref = str(source["scope_ref"])
        policy_digest = scopes[scope_ref]["effective_policy_digest"]
        for index, chunk in enumerate(_chunks(path)):
            rule_identity = _candidate_rule_identity(scope_ref, chunk)
            provenance_only = bool(_GLOBAL_GATE_RE.search(chunk))
            source_ref = f"{path}:chunk:{index}"
            key = (scope_ref, rule_identity)
            rule = raw_rules.setdefault(key, {
                "rule_id": "candidate-" + rule_identity.removeprefix("sha256:"),
                "rule_identity": rule_identity,
                "scope_ref": scope_ref,
                "role": "source_rule",
                "statement": chunk,
                "source_ref": source_ref,
                "source_paths": [],
                "source_refs": [],
                "origin_kind": source["origin_kind"],
                "authority": AUTHORITY,
                "semantic_status": "PROVENANCE_ONLY" if provenance_only else "ACTIVE_CANDIDATE",
                "active_projection_count": 0 if provenance_only else 1,
                "policy_digest": policy_digest,
            })
            if source["path"] not in rule["source_paths"]:
                rule["source_paths"].append(source["path"])
            if source_ref not in rule["source_refs"]:
                rule["source_refs"].append(source_ref)
            if provenance_only:
                rule["semantic_replacement_rule_ids"] = ["p4-06-scoped-acceptance"]
            raw_records.append({
                "category": "policy_provenance" if provenance_only else "instruction",
                "text": chunk,
                "source_ref": source_ref,
                "scope_ref": scope_ref,
                "rule_identity": rule_identity,
                "policy_digest": policy_digest,
                "authority": AUTHORITY,
                "origin_kind": source["origin_kind"],
                "semantic_status": "PROVENANCE_ONLY" if provenance_only else "ACTIVE_CANDIDATE",
                "replacement_rule_ids": ["p4-06-scoped-acceptance"] if provenance_only else [],
            })

    semantic_rules = _semantic_rule_rows()
    for rule in semantic_rules:
        raw_records.append({
            "category": "instruction",
            "text": rule["statement"],
            "source_ref": rule["source_ref"],
            "scope_ref": rule["scope_ref"],
            "rule_identity": rule["rule_identity"],
            "policy_digest": scopes[rule["scope_ref"]]["effective_policy_digest"],
            "authority": AUTHORITY,
            "origin_kind": rule["origin_kind"],
            "semantic_status": rule["semantic_status"],
            "replacement_rule_ids": [],
        })

    active_rule_index = [*raw_rules.values(), *semantic_rules]
    active_rule_index = [
        {
            **rule,
            "source_paths": sorted(set(rule.get("source_paths", []))),
            "source_refs": sorted(set(rule.get("source_refs", [rule.get("source_ref", "")])))
            if rule.get("source_refs", [rule.get("source_ref", "")])
            else [],
        }
        for rule in active_rule_index
    ]
    active_keys = [
        (str(rule["scope_ref"]), str(rule["rule_identity"]))
        for rule in active_rule_index
        if int(rule.get("active_projection_count", 0)) == 1
    ]
    authority_conflicts = sorted({key for key in active_keys if active_keys.count(key) > 1})
    if authority_conflicts:
        raise ValueError(f"duplicate active policy projection keys: {authority_conflicts}")

    legacy = []
    for source in provenance_sources:
        legacy.append({
            **source,
            "active_input": False,
            "active_record_count": 0,
            "provenance_only": True,
            "reason": "legacy policy bytes preserved without active MiniTZ steering",
        })

    return {
        "schema": SCHEMA,
        "graph": GRAPH,
        "authority": AUTHORITY,
        "active_historical_steering_target": ACTIVE_HISTORICAL_STEERING_TARGET,
        "active_source_paths": sorted(source_by_path),
        "active_sources": sorted(active_sources, key=lambda item: item["path"]),
        "provenance_sources": sorted(legacy, key=lambda item: item["path"]),
        "legacy_policy": legacy,
        "legacy_policy_active_input": False,
        "scopes": scopes,
        "execution_inputs": {
            scope_ref: {
                "effective_policy_identity": metadata["effective_policy_identity"],
                "effective_policy_digest": metadata["effective_policy_digest"],
                "agents_policy_identity": metadata["agents_policy_identity"],
                "agents_policy_digest": metadata["agents_policy_digest"],
            }
            for scope_ref, metadata in scopes.items()
        },
        "semantic_rules": semantic_rules,
        "semantic_replacements": [
            rule for rule in semantic_rules if rule.get("replaces")
        ],
        "active_rule_index": sorted(
            active_rule_index,
            key=lambda item: (str(item["scope_ref"]), str(item["rule_identity"])),
        ),
        "active_authority_conflicts": authority_conflicts,
        "active_authority_key_count": len(active_keys),
        "historical_agents_policy": {
            "current_projection_only": True,
            "historical_revisions_are_provenance": True,
            "authority": AUTHORITY,
        },
        "invalidation": {
            "basis": "exact source sha256 per scope",
            "rule": "only derived context dependent on a changed scope is invalidated",
            "scope_dependencies": {
                scope_ref: "scope-ref:" + scope_ref for scope_ref in sorted(scopes)
            },
        },
        "records": raw_records,
    }


def active_source_paths(projection: dict[str, Any]) -> set[str]:
    """Return active source paths as repository-relative strings."""

    return {str(item["path"]) for item in projection.get("active_sources", [])}
