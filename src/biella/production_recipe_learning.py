"""Evidence-bound learning of optional provider-neutral production recipes.

Recipes are advisory normalized Graph patterns. They instantiate ordinary
immutable Graph objects and never become scheduling, routing, validation, or
Task authority.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast

from .capability import CapabilityRef
from .graph import (
    Graph,
    GraphRef,
    GraphSideEffectError,
    Node,
    NodeInputBinding,
    NodeRef,
)
from .project import ProjectRef
from .run import RunRef
from .task import Task


_ZERO_DIGEST = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_TEXT = re.compile(
    r"(?:\b(?:prj|run|gra|nod|tsk|art|atm|exe)_[A-Za-z0-9_-]+\b|"
    r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b)",
    re.IGNORECASE,
)
_RAW_HISTORICAL = re.compile(
    r"(?:quarantine://|raw://|raw[_ -]?historical|raw[_ -]?source)", re.IGNORECASE
)
_SECRET_TEXT = re.compile(
    r"(?:cfat_|sk-(?:proj-)?|api[_ -]?token\s*[=:]|password\s*[=:]|"
    r"secret(?:_access_key)?\s*[=:]|access_key_id\s*[=:])",
    re.IGNORECASE,
)
_PATH_TEXT = re.compile(r"(?:^|\s)(?:/[^\s]+|[A-Za-z]:\\[^\s]+)")
_DROP_KEY_PARTS = (
    "provider",
    "worker_id",
    "host",
    "hostname",
    "machine",
    "path",
    "project_id",
    "project_name",
    "asset_name",
    "run_id",
    "node_id",
    "graph_id",
    "task_id",
    "credential",
    "password",
    "secret",
    "api_token",
    "access_key",
)
_SIDE_EFFECT_RANK = {
    "NONE": 0,
    "READ_ONLY": 0,
    "CANDIDATE_WRITE": 1,
    "REVERSIBLE_WRITE": 1,
    "WRITE": 1,
    "IRREVERSIBLE_WRITE": 2,
}
_KPI_NAMES = (
    "recipes_with_Project_ids_in_Engine_scope",
    "recipe_becomes_mandatory_global_pipeline",
    "recipe_without_source_evidence",
    "failed_recipe_runs_hidden",
    "recipe_escalates_Task_authority",
    "active_raw_historical_content",
    "accepted_stale_results",
    "cross_project_context_leaks",
    "global_heavyweight_resource_lock",
    "learned_routing_bypasses_hard_constraints",
    "unproven_root_causes_stored_as_fact",
)


class RecipeLearningError(RuntimeError):
    """Base error for fail-closed production recipe learning."""


class RecipeContractError(RecipeLearningError):
    """The proposed recipe does not satisfy the semantic contract."""


class RecipeIntegrityError(RecipeLearningError):
    """Durable recipe state is missing, reordered, or tampered."""


class RecipeScopeError(RecipeLearningError):
    """A Project-scoped recipe crossed its owning Project boundary."""


class RecipeStaleError(RecipeLearningError):
    """A stale recipe version, digest, or execution fence was supplied."""


class RecipeSideEffectError(GraphSideEffectError, RecipeLearningError):
    """Recipe extraction or instantiation would escalate Task authority."""


class RecipeScope(str, Enum):
    PROJECT = "PROJECT"
    ENGINE = "ENGINE"


class RecipeStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    SUPERSEDED = "SUPERSEDED"
    CONTRADICTED = "CONTRADICTED"
    REJECTED = "REJECTED"


class RecipeMatchState(str, Enum):
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NO_MATCH = "NO_MATCH"


class RecipeRunOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    return value


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        frozen = {
            str(key): _freeze(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return cast(Mapping[str, object], _freeze(value))


def _canonical_json(value: object) -> str:
    return json.dumps(_thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text_digest(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def _project_key(project_ref: ProjectRef) -> str:
    return f"project:{_text_digest(project_ref)}"


def _identity(value: object) -> str:
    return repr(value)


def _assert_no_raw_or_secret(value: object) -> None:
    serialized = _canonical_json(value)
    if _RAW_HISTORICAL.search(serialized):
        raise RecipeContractError("active raw historical content cannot enter a recipe")
    if _SECRET_TEXT.search(serialized):
        raise RecipeContractError("secret-like content cannot enter a recipe")


def _safe_semantic_text(value: str, *, key: str = "") -> str:
    _assert_no_raw_or_secret(value)
    lowered_key = key.lower()
    if any(part in lowered_key for part in _DROP_KEY_PARTS):
        return "<environment-identity>"
    if _IDENTITY_TEXT.search(value):
        return _IDENTITY_TEXT.sub("<identity>", value)
    if _PATH_TEXT.search(value):
        return "<path-role>"
    return value


def _normalize_value(value: object, *, key: str = "") -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise RecipeContractError("non-finite numeric recipe value")
        return value
    if isinstance(value, str):
        return _safe_semantic_text(value, key=key)
    if isinstance(value, Enum):
        return _safe_semantic_text(str(value.value), key=key)
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for raw_key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            item_key = str(raw_key)
            if any(part in item_key.lower() for part in _DROP_KEY_PARTS):
                continue
            result[item_key] = _normalize_value(item, key=item_key)
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_normalize_value(item, key=key) for item in value]
    return _safe_semantic_text(str(value), key=key)


def _evidence_token(value: object) -> str:
    _assert_no_raw_or_secret(value)
    text = str(value)
    if _HEX64.fullmatch(text):
        return text
    return f"evi_{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _capability_payload(value: object) -> dict[str, object]:
    capability_id = getattr(value, "capability_id", None)
    version = getattr(value, "version", None)
    if capability_id is not None and version is not None:
        return {
            "capability_id": _safe_semantic_text(str(capability_id), key="capability"),
            "version": _safe_semantic_text(str(version), key="capability_version"),
        }
    if isinstance(value, Mapping):
        raw_id = value.get("capability_id", value.get("id", value.get("name", "")))
        return {
            "capability_id": _safe_semantic_text(str(raw_id), key="capability"),
            "version": _safe_semantic_text(
                str(value.get("version", "*")), key="capability_version"
            ),
        }
    text = _safe_semantic_text(str(value), key="capability")
    if "@" in text:
        capability, version_text = text.rsplit("@", 1)
        return {"capability_id": capability, "version": version_text}
    return {"capability_id": text, "version": "*"}


def _capability_key(value: object) -> str:
    payload = _capability_payload(value)
    return f"{payload['capability_id']}@{payload['version']}"


def _normalize_task_profile(task_profile: object) -> dict[str, object]:
    if isinstance(task_profile, Mapping):
        normalized = cast(dict[str, object], _normalize_value(task_profile))
        capabilities = task_profile.get("required_capabilities", ())
        if isinstance(capabilities, Iterable) and not isinstance(capabilities, (str, bytes)):
            normalized["required_capabilities"] = sorted(
                _capability_key(value) for value in capabilities
            )
        optional = task_profile.get("optional_capabilities", ())
        if isinstance(optional, Iterable) and not isinstance(optional, (str, bytes)):
            normalized["optional_capabilities"] = sorted(
                _capability_key(value) for value in optional
            )
        return normalized
    if not isinstance(task_profile, Task):
        raise RecipeContractError("task profile must be a Task or mapping")
    return {
        "acceptance_criteria": sorted(str(value) for value in task_profile.acceptance_criteria),
        "constraints": cast(dict[str, object], _normalize_value(task_profile.constraints)),
        "data_policy": "required" if task_profile.data_policy_ref else "none",
        "egress_policy": "required" if task_profile.egress_policy_ref else "none",
        "evidence_requirements": sorted(
            str(value) for value in task_profile.evidence_requirements
        ),
        "input_roles": sorted(value.input_kind for value in task_profile.input_refs),
        "output_contract": cast(
            dict[str, object], _normalize_value(task_profile.output_contract)
        ),
        "required_capabilities": sorted(
            _capability_key(value) for value in task_profile.required_capabilities
        ),
        "resource_hints": cast(
            dict[str, object], _normalize_value(task_profile.resource_hints)
        ),
        "side_effect_authority": str(task_profile.side_effect_authority),
        "task_type": _safe_semantic_text(task_profile.task_type, key="task_type"),
    }


def _mapping_id(value: object, index: int) -> str:
    if isinstance(value, Mapping):
        for key in ("id", "node_id", "name", "ref", "role"):
            if key in value:
                return str(value[key])
    if isinstance(value, str):
        return value
    return f"source-node-{index}"


def _binding_payload(binding: object) -> dict[str, object]:
    result: dict[str, object] = {}
    source_items: Iterable[tuple[object, object]]
    if isinstance(binding, Mapping):
        source_items = binding.items()
    elif is_dataclass(binding):
        source_items = ((item.name, getattr(binding, item.name)) for item in fields(binding))
    else:
        return {"role": _safe_semantic_text(str(binding), key="input_role")}
    for key, value in source_items:
        name = str(key)
        class_name = value.__class__.__name__ if value is not None else ""
        if class_name == "NodeRef":
            result["source_node"] = _identity(value)
        elif class_name == "TaskInputRef":
            result["task_input_kind"] = str(getattr(value, "input_kind", "input"))
        elif name in {"source_ref", "content_sha256", "identity_ref", "project_ref"}:
            result[name] = "<identity>"
        elif value is None or isinstance(value, (str, bool, int, float, Enum)):
            result[name] = _normalize_value(value, key=name)
    return result


def _actual_graph_mapping(graph: Graph) -> dict[str, object]:
    raw_nodes: list[dict[str, object]] = []
    edges: list[list[str]] = []
    for node in graph.nodes:
        node_id = _identity(node.node_ref)
        dependencies = [_identity(value) for value in node.dependencies]
        edges.extend([[dependency, node_id] for dependency in dependencies])
        raw_nodes.append(
            {
                "capabilities": [
                    _capability_payload(value) for value in node.required_capabilities
                ],
                "condition_ref": node.condition_ref,
                "dependencies": dependencies,
                "evidence_requirements": list(node.evidence_requirements),
                "executor_kind": node.executor_kind,
                "id": node_id,
                "input_bindings": [
                    _binding_payload(value) for value in node.input_bindings
                ],
                "output_contract": dict(node.output_contract),
                "resource_hints": dict(node.resource_hints),
                "side_effect_requirement": node.side_effect_requirement,
            }
        )
    return {"edges": edges, "nodes": raw_nodes}


def _normalize_graph_pattern(graph_pattern: object) -> dict[str, object]:
    if isinstance(graph_pattern, Graph):
        graph_pattern = _actual_graph_mapping(graph_pattern)
    if not isinstance(graph_pattern, Mapping):
        raise RecipeContractError("graph pattern must be a Graph or mapping")
    raw_nodes_value = graph_pattern.get("nodes", ())
    raw_edges_value = graph_pattern.get("edges", ())
    if not isinstance(raw_nodes_value, Iterable) or isinstance(
        raw_nodes_value, (str, bytes)
    ):
        raise RecipeContractError("graph pattern nodes must be a sequence")
    raw_nodes = list(raw_nodes_value)
    identities = [_mapping_id(value, index) for index, value in enumerate(raw_nodes)]
    if len(set(identities)) != len(identities):
        raise RecipeContractError("graph pattern node identities must be unique")
    raw_by_id = dict(zip(identities, raw_nodes, strict=True))
    dependencies: dict[str, set[str]] = {identity: set() for identity in identities}
    if isinstance(raw_edges_value, Iterable) and not isinstance(
        raw_edges_value, (str, bytes)
    ):
        for raw_edge in raw_edges_value:
            if (
                not isinstance(raw_edge, Sequence)
                or isinstance(raw_edge, (str, bytes))
                or len(raw_edge) != 2
            ):
                raise RecipeContractError("graph edge must contain source and target")
            source, target = str(raw_edge[0]), str(raw_edge[1])
            if source not in dependencies or target not in dependencies:
                raise RecipeContractError("graph edge references an unknown node")
            dependencies[target].add(source)
    for identity, raw_node in raw_by_id.items():
        if not isinstance(raw_node, Mapping):
            continue
        raw_dependencies = raw_node.get("dependencies", ())
        if isinstance(raw_dependencies, Iterable) and not isinstance(
            raw_dependencies, (str, bytes)
        ):
            for dependency in raw_dependencies:
                dependency_id = str(dependency)
                if dependency_id not in dependencies:
                    raise RecipeContractError("node dependency references an unknown node")
                dependencies[identity].add(dependency_id)
    remaining = set(identities)
    ordered: list[str] = []
    while remaining:
        ready = [
            identity
            for identity in remaining
            if dependencies[identity].issubset(ordered)
        ]
        if not ready:
            raise RecipeContractError("graph pattern must be acyclic")
        ready.sort(
            key=lambda identity: (
                _canonical_json(
                    _normalize_value(
                        {
                            key: value
                            for key, value in cast(
                                Mapping[str, object], raw_by_id[identity]
                            ).items()
                            if key
                            not in {
                                "id",
                                "node_id",
                                "name",
                                "ref",
                                "dependencies",
                                "input_bindings",
                            }
                        }
                    )
                )
                if isinstance(raw_by_id[identity], Mapping)
                else "",
                identity,
            )
        )
        ordered.extend(ready)
        remaining.difference_update(ready)
    roles = {
        identity: f"node_{index + 1:03d}" for index, identity in enumerate(ordered)
    }
    nodes: list[dict[str, object]] = []
    for identity in ordered:
        raw_node = raw_by_id[identity]
        mapping = (
            cast(Mapping[str, object], raw_node)
            if isinstance(raw_node, Mapping)
            else {}
        )
        capabilities_value = mapping.get(
            "capabilities", mapping.get("required_capabilities", ())
        )
        capabilities = (
            sorted(
                (
                    _capability_payload(value)
                    for value in cast(Iterable[object], capabilities_value)
                ),
                key=_canonical_json,
            )
            if isinstance(capabilities_value, Iterable)
            and not isinstance(capabilities_value, (str, bytes))
            else []
        )
        bindings_value = mapping.get("input_bindings", ())
        bindings: list[dict[str, object]] = []
        if isinstance(bindings_value, Iterable) and not isinstance(
            bindings_value, (str, bytes)
        ):
            for value in bindings_value:
                binding = _binding_payload(value)
                source_node = binding.get("source_node")
                if isinstance(source_node, str) and source_node in roles:
                    binding["source_role"] = roles[source_node]
                    del binding["source_node"]
                bindings.append(
                    cast(dict[str, object], _normalize_value(binding))
                )
        executor = _safe_semantic_text(
            str(mapping.get("executor_kind", "capability")), key="executor_kind"
        )
        condition = mapping.get("condition_ref")
        node_payload: dict[str, object] = {
            "capabilities": capabilities,
            "condition_ref": (
                _normalize_value(condition, key="condition_ref") if condition else None
            ),
            "dependencies": sorted(
                roles[value] for value in dependencies[identity]
            ),
            "evidence_requirements": sorted(
                str(value)
                for value in cast(
                    Iterable[object], mapping.get("evidence_requirements", ())
                )
            ),
            "executor_kind": executor,
            "input_bindings": bindings,
            "optional": bool(mapping.get("optional", condition is not None)),
            "output_contract": cast(
                dict[str, object],
                _normalize_value(mapping.get("output_contract", {})),
            ),
            "resource_hints": cast(
                dict[str, object],
                _normalize_value(mapping.get("resource_hints", {})),
            ),
            "role": roles[identity],
            "side_effect_requirement": str(
                mapping.get("side_effect_requirement", "READ_ONLY")
            ),
        }
        nodes.append(node_payload)
    normalized: dict[str, object] = {
        "nodes": nodes,
        "pattern_type": _safe_semantic_text(
            str(graph_pattern.get("kind", "dag")), key="kind"
        ),
    }
    _assert_no_raw_or_secret(normalized)
    return normalized


def _extract_sequence(
    profile: Mapping[str, object], key: str
) -> tuple[str, ...]:
    value = profile.get(key, ())
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ()
    return tuple(sorted(str(item) for item in value))


def _side_effect_within(requirement: str, authority: str) -> bool:
    if requirement == authority:
        return True
    requirement_rank = _SIDE_EFFECT_RANK.get(requirement)
    authority_rank = _SIDE_EFFECT_RANK.get(authority)
    return (
        requirement_rank is not None
        and authority_rank is not None
        and requirement_rank <= authority_rank
    )


def _validate_side_effects(
    task_profile: Mapping[str, object],
    patterns: Sequence[Mapping[str, object]],
) -> None:
    authority = str(task_profile.get("side_effect_authority", "READ_ONLY"))
    for pattern in patterns:
        nodes = pattern.get("nodes", ())
        if not isinstance(nodes, Iterable):
            continue
        for raw_node in nodes:
            if not isinstance(raw_node, Mapping):
                continue
            requirement = str(
                raw_node.get("side_effect_requirement", "READ_ONLY")
            )
            if not _side_effect_within(requirement, authority):
                raise RecipeSideEffectError(
                    "recipe node exceeds Task side-effect authority"
                )


@dataclass(frozen=True, slots=True)
class ProductionRecipe:
    recipe_id: str
    version: int
    scope: RecipeScope
    status: RecipeStatus
    task_profile: Mapping[str, object]
    applicability: Mapping[str, object]
    normalized_graph_pattern: tuple[Mapping[str, object], ...]
    parameter_schema: Mapping[str, object]
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...]
    input_roles: tuple[str, ...]
    output_roles: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    resource_hints: Mapping[str, object]
    learning_evidence: tuple[str, ...]
    failure_evidence: tuple[str, ...]
    p4_evidence_refs: tuple[str, ...]
    metrics: Mapping[str, object]
    prior_recipe_digest: str | None
    semantic_digest: str
    canonical_digest: str
    created_at: str
    _scope_key: str = field(repr=False)

    @property
    def semantic_payload(self) -> Mapping[str, object]:
        """Provider-neutral semantics only; source identities remain evidence."""

        return cast(
            Mapping[str, object],
            _thaw(
                {
                "applicability": _thaw(self.applicability),
                "normalized_graph_pattern": [
                    _thaw(value) for value in self.normalized_graph_pattern
                ],
                "parameter_schema": _thaw(self.parameter_schema),
                "required_capabilities": list(self.required_capabilities),
                "optional_capabilities": list(self.optional_capabilities),
                "input_roles": list(self.input_roles),
                "output_roles": list(self.output_roles),
                "resource_hints": _thaw(self.resource_hints),
                "scope": self.scope.value,
                "task_profile": _thaw(self.task_profile),
                "validation_requirements": list(
                    self.validation_requirements
                ),
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class RecipeMatch:
    recipe_id: str
    recipe_version: int
    recipe_digest: str
    state: RecipeMatchState
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecipeRunEvidence:
    evidence_id: str
    recipe_id: str
    recipe_version: int
    recipe_digest: str
    run_ref: str
    outcome: RecipeRunOutcome
    output_evidence: tuple[str, ...]
    validation_evidence: tuple[str, ...]
    expected_fence: int
    observed_fence: int
    created_at: str
    canonical_digest: str
    _scope_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RecipeInstantiation:
    recipe_id: str
    recipe_version: int
    recipe_digest: str
    graph: Graph


@dataclass(frozen=True, slots=True)
class RecipeLearningEvidenceSummary:
    scope_key: str
    recipe_digests: tuple[str, ...]
    run_evidence_digests: tuple[str, ...]
    kpi_results: Mapping[str, int]
    canonical_digest: str


class ProductionRecipeLearningService:
    """SQLite-backed immutable recipe and run-evidence service."""

    _SCHEMA_VERSION = 1
    _NORMALIZER_VERSION = "production-recipe-normalizer/v1"
    _MATCHER_VERSION = "production-recipe-matcher/v1"

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._database_path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS production_recipe_versions (
                scope_key TEXT NOT NULL,
                recipe_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                semantic_digest TEXT NOT NULL,
                prior_recipe_digest TEXT,
                record_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                PRIMARY KEY (scope_key, recipe_id, version)
            );
            CREATE TABLE IF NOT EXISTS recipe_run_evidence (
                scope_key TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                recipe_id TEXT NOT NULL,
                recipe_version INTEGER NOT NULL,
                recipe_digest TEXT NOT NULL,
                record_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                PRIMARY KEY (scope_key, evidence_id),
                FOREIGN KEY (scope_key, recipe_id, recipe_version)
                    REFERENCES production_recipe_versions(scope_key, recipe_id, version)
            );
            CREATE TABLE IF NOT EXISTS production_recipe_ledger (
                scope_key TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                record_kind TEXT NOT NULL,
                record_ref TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                previous_entry_sha256 TEXT NOT NULL,
                entry_sha256 TEXT NOT NULL,
                PRIMARY KEY (scope_key, sequence)
            );
            CREATE TABLE IF NOT EXISTS production_recipe_heads (
                scope_key TEXT PRIMARY KEY,
                sequence INTEGER NOT NULL,
                entry_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recipe_match_cache (
                cache_key TEXT PRIMARY KEY,
                scope_key TEXT NOT NULL,
                recipe_digest TEXT NOT NULL,
                query_digest TEXT NOT NULL,
                matcher_version TEXT NOT NULL,
                result_json TEXT NOT NULL,
                derivation_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS production_recipe_versions_no_update
            BEFORE UPDATE ON production_recipe_versions
            BEGIN SELECT RAISE(ABORT, 'immutable recipe'); END;
            CREATE TRIGGER IF NOT EXISTS production_recipe_versions_no_delete
            BEFORE DELETE ON production_recipe_versions
            BEGIN SELECT RAISE(ABORT, 'immutable recipe'); END;
            CREATE TRIGGER IF NOT EXISTS recipe_run_evidence_no_update
            BEFORE UPDATE ON recipe_run_evidence
            BEGIN SELECT RAISE(ABORT, 'immutable recipe evidence'); END;
            CREATE TRIGGER IF NOT EXISTS recipe_run_evidence_no_delete
            BEFORE DELETE ON recipe_run_evidence
            BEGIN SELECT RAISE(ABORT, 'immutable recipe evidence'); END;
            CREATE TRIGGER IF NOT EXISTS production_recipe_ledger_no_update
            BEFORE UPDATE ON production_recipe_ledger
            BEGIN SELECT RAISE(ABORT, 'immutable recipe ledger'); END;
            CREATE TRIGGER IF NOT EXISTS production_recipe_ledger_no_delete
            BEFORE DELETE ON production_recipe_ledger
            BEGIN SELECT RAISE(ABORT, 'immutable recipe ledger'); END;
            """
        )
        self._connection.commit()
        self._verify_integrity()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> ProductionRecipeLearningService:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @staticmethod
    def _semantic_payload(
        *,
        scope: RecipeScope,
        task_profile: Mapping[str, object],
        applicability: Mapping[str, object],
        patterns: Sequence[Mapping[str, object]],
        parameter_schema: Mapping[str, object],
    ) -> dict[str, object]:
        return {
            "applicability": _thaw(applicability),
            "normalizer_version": ProductionRecipeLearningService._NORMALIZER_VERSION,
            "normalized_graph_pattern": [
                _thaw(pattern) for pattern in patterns
            ],
            "parameter_schema": _thaw(parameter_schema),
            "scope": scope.value,
            "task_profile": _thaw(task_profile),
        }

    @staticmethod
    def _recipe_core(recipe: ProductionRecipe) -> dict[str, object]:
        return {
            "applicability": _thaw(recipe.applicability),
            "created_at": recipe.created_at,
            "failure_evidence": list(recipe.failure_evidence),
            "input_roles": list(recipe.input_roles),
            "learning_evidence": list(recipe.learning_evidence),
            "metrics": _thaw(recipe.metrics),
            "normalized_graph_pattern": [
                _thaw(value) for value in recipe.normalized_graph_pattern
            ],
            "optional_capabilities": list(recipe.optional_capabilities),
            "output_roles": list(recipe.output_roles),
            "p4_evidence_refs": list(recipe.p4_evidence_refs),
            "parameter_schema": _thaw(recipe.parameter_schema),
            "prior_recipe_digest": recipe.prior_recipe_digest,
            "recipe_id": recipe.recipe_id,
            "required_capabilities": list(recipe.required_capabilities),
            "resource_hints": _thaw(recipe.resource_hints),
            "schema_version": ProductionRecipeLearningService._SCHEMA_VERSION,
            "scope": recipe.scope.value,
            "scope_key": recipe._scope_key,
            "semantic_digest": recipe.semantic_digest,
            "status": recipe.status.value,
            "task_profile": _thaw(recipe.task_profile),
            "validation_requirements": list(recipe.validation_requirements),
            "version": recipe.version,
        }

    @classmethod
    def _recipe_record(cls, recipe: ProductionRecipe) -> dict[str, object]:
        payload = cls._recipe_core(recipe)
        payload["canonical_digest"] = recipe.canonical_digest
        return payload

    @staticmethod
    def _recipe_from_record(
        payload: Mapping[str, object],
    ) -> ProductionRecipe:
        raw_patterns = payload.get("normalized_graph_pattern", [])
        if not isinstance(raw_patterns, list):
            raise RecipeIntegrityError("recipe graph pattern is malformed")
        return ProductionRecipe(
            recipe_id=str(payload["recipe_id"]),
            version=int(str(payload["version"])),
            scope=RecipeScope(str(payload["scope"])),
            status=RecipeStatus(str(payload["status"])),
            task_profile=_freeze_mapping(
                cast(Mapping[str, object], payload["task_profile"])
            ),
            applicability=_freeze_mapping(
                cast(Mapping[str, object], payload["applicability"])
            ),
            normalized_graph_pattern=tuple(
                _freeze_mapping(cast(Mapping[str, object], value))
                for value in raw_patterns
            ),
            parameter_schema=_freeze_mapping(
                cast(Mapping[str, object], payload["parameter_schema"])
            ),
            required_capabilities=tuple(
                str(value)
                for value in cast(list[object], payload["required_capabilities"])
            ),
            optional_capabilities=tuple(
                str(value)
                for value in cast(list[object], payload["optional_capabilities"])
            ),
            input_roles=tuple(
                str(value)
                for value in cast(list[object], payload["input_roles"])
            ),
            output_roles=tuple(
                str(value)
                for value in cast(list[object], payload["output_roles"])
            ),
            validation_requirements=tuple(
                str(value)
                for value in cast(list[object], payload["validation_requirements"])
            ),
            resource_hints=_freeze_mapping(
                cast(Mapping[str, object], payload["resource_hints"])
            ),
            learning_evidence=tuple(
                str(value)
                for value in cast(list[object], payload["learning_evidence"])
            ),
            failure_evidence=tuple(
                str(value)
                for value in cast(list[object], payload["failure_evidence"])
            ),
            p4_evidence_refs=tuple(
                str(value)
                for value in cast(list[object], payload["p4_evidence_refs"])
            ),
            metrics=_freeze_mapping(
                cast(Mapping[str, object], payload["metrics"])
            ),
            prior_recipe_digest=(
                str(payload["prior_recipe_digest"])
                if payload.get("prior_recipe_digest") is not None
                else None
            ),
            semantic_digest=str(payload["semantic_digest"]),
            canonical_digest=str(payload["canonical_digest"]),
            created_at=str(payload["created_at"]),
            _scope_key=str(payload["scope_key"]),
        )

    @staticmethod
    def _run_core(evidence: RecipeRunEvidence) -> dict[str, object]:
        return {
            "created_at": evidence.created_at,
            "evidence_id": evidence.evidence_id,
            "expected_fence": evidence.expected_fence,
            "observed_fence": evidence.observed_fence,
            "outcome": evidence.outcome.value,
            "output_evidence": list(evidence.output_evidence),
            "recipe_digest": evidence.recipe_digest,
            "recipe_id": evidence.recipe_id,
            "recipe_version": evidence.recipe_version,
            "run_ref": evidence.run_ref,
            "scope_key": evidence._scope_key,
            "validation_evidence": list(evidence.validation_evidence),
        }

    @classmethod
    def _run_record(cls, evidence: RecipeRunEvidence) -> dict[str, object]:
        payload = cls._run_core(evidence)
        payload["canonical_digest"] = evidence.canonical_digest
        return payload

    @staticmethod
    def _run_from_record(
        payload: Mapping[str, object],
    ) -> RecipeRunEvidence:
        return RecipeRunEvidence(
            evidence_id=str(payload["evidence_id"]),
            recipe_id=str(payload["recipe_id"]),
            recipe_version=int(str(payload["recipe_version"])),
            recipe_digest=str(payload["recipe_digest"]),
            run_ref=str(payload["run_ref"]),
            outcome=RecipeRunOutcome(str(payload["outcome"])),
            output_evidence=tuple(
                str(value)
                for value in cast(list[object], payload["output_evidence"])
            ),
            validation_evidence=tuple(
                str(value)
                for value in cast(list[object], payload["validation_evidence"])
            ),
            expected_fence=int(str(payload["expected_fence"])),
            observed_fence=int(str(payload["observed_fence"])),
            created_at=str(payload["created_at"]),
            canonical_digest=str(payload["canonical_digest"]),
            _scope_key=str(payload["scope_key"]),
        )

    def _verify_integrity(self) -> None:
        try:
            recipes: dict[tuple[str, str], str] = {}
            for row in self._connection.execute(
                "SELECT scope_key, recipe_id, version, record_json, "
                "record_sha256 FROM production_recipe_versions"
            ):
                payload = json.loads(str(row["record_json"]))
                if not isinstance(payload, dict):
                    raise RecipeIntegrityError("recipe record is malformed")
                recipe = self._recipe_from_record(payload)
                digest = _sha256(self._recipe_core(recipe))
                if not hmac.compare_digest(
                    digest, str(row["record_sha256"])
                ) or not hmac.compare_digest(digest, recipe.canonical_digest):
                    raise RecipeIntegrityError("recipe record digest mismatch")
                reference = f"{row['recipe_id']}:{row['version']}"
                recipes[(str(row["scope_key"]), reference)] = digest
            evidence_records: dict[tuple[str, str], str] = {}
            for row in self._connection.execute(
                "SELECT scope_key, evidence_id, record_json, record_sha256 "
                "FROM recipe_run_evidence"
            ):
                payload = json.loads(str(row["record_json"]))
                if not isinstance(payload, dict):
                    raise RecipeIntegrityError(
                        "recipe evidence record is malformed"
                    )
                evidence = self._run_from_record(payload)
                digest = _sha256(self._run_core(evidence))
                if not hmac.compare_digest(
                    digest, str(row["record_sha256"])
                ) or not hmac.compare_digest(
                    digest, evidence.canonical_digest
                ):
                    raise RecipeIntegrityError(
                        "recipe evidence digest mismatch"
                    )
                evidence_records[
                    (str(row["scope_key"]), str(row["evidence_id"]))
                ] = digest
            seen: set[tuple[str, str, str]] = set()
            rows = self._connection.execute(
                "SELECT scope_key, sequence, record_kind, record_ref, "
                "record_sha256, previous_entry_sha256, entry_sha256 "
                "FROM production_recipe_ledger ORDER BY scope_key, sequence"
            ).fetchall()
            state: dict[str, tuple[int, str]] = {}
            for row in rows:
                scope_key = str(row["scope_key"])
                prior_sequence, prior_digest = state.get(
                    scope_key, (0, _ZERO_DIGEST)
                )
                sequence = int(row["sequence"])
                if sequence != prior_sequence + 1 or not hmac.compare_digest(
                    str(row["previous_entry_sha256"]), prior_digest
                ):
                    raise RecipeIntegrityError(
                        "recipe ledger has a gap or reordered entry"
                    )
                entry_core = {
                    "previous_entry_sha256": prior_digest,
                    "record_kind": str(row["record_kind"]),
                    "record_ref": str(row["record_ref"]),
                    "record_sha256": str(row["record_sha256"]),
                    "scope_key": scope_key,
                    "sequence": sequence,
                }
                entry_digest = _sha256(entry_core)
                if not hmac.compare_digest(
                    entry_digest, str(row["entry_sha256"])
                ):
                    raise RecipeIntegrityError(
                        "recipe ledger entry digest mismatch"
                    )
                key = (scope_key, str(row["record_ref"]))
                expected = (
                    recipes.get(key)
                    if row["record_kind"] == "RECIPE"
                    else evidence_records.get(key)
                )
                if expected is None or not hmac.compare_digest(
                    expected, str(row["record_sha256"])
                ):
                    raise RecipeIntegrityError(
                        "recipe ledger references missing durable state"
                    )
                marker = (
                    scope_key,
                    str(row["record_kind"]),
                    str(row["record_ref"]),
                )
                if marker in seen:
                    raise RecipeIntegrityError(
                        "recipe ledger contains duplicate authority"
                    )
                seen.add(marker)
                state[scope_key] = (sequence, entry_digest)
            expected_markers = {
                (scope, "RECIPE", reference)
                for scope, reference in recipes
            } | {
                (scope, "EVIDENCE", reference)
                for scope, reference in evidence_records
            }
            if seen != expected_markers:
                raise RecipeIntegrityError(
                    "authoritative recipe state is absent from the ledger"
                )
            heads = {
                str(row["scope_key"]): (
                    int(row["sequence"]),
                    str(row["entry_sha256"]),
                )
                for row in self._connection.execute(
                    "SELECT scope_key, sequence, entry_sha256 "
                    "FROM production_recipe_heads"
                )
            }
            if heads != state:
                raise RecipeIntegrityError(
                    "recipe ledger head does not match durable history"
                )
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise RecipeIntegrityError(
                "recipe store contains malformed durable state"
            ) from exc

    def _append_record(
        self,
        *,
        scope_key: str,
        record_kind: str,
        record_ref: str,
        record_sha256: str,
        insert_sql: str,
        insert_values: tuple[object, ...],
    ) -> None:
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(insert_sql, insert_values)
            head = connection.execute(
                "SELECT sequence, entry_sha256 FROM production_recipe_heads "
                "WHERE scope_key = ?",
                (scope_key,),
            ).fetchone()
            sequence = int(head["sequence"]) + 1 if head is not None else 1
            previous = (
                str(head["entry_sha256"])
                if head is not None
                else _ZERO_DIGEST
            )
            entry_core = {
                "previous_entry_sha256": previous,
                "record_kind": record_kind,
                "record_ref": record_ref,
                "record_sha256": record_sha256,
                "scope_key": scope_key,
                "sequence": sequence,
            }
            entry_sha256 = _sha256(entry_core)
            connection.execute(
                "INSERT INTO production_recipe_ledger "
                "(scope_key, sequence, record_kind, record_ref, record_sha256, "
                "previous_entry_sha256, entry_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    scope_key,
                    sequence,
                    record_kind,
                    record_ref,
                    record_sha256,
                    previous,
                    entry_sha256,
                ),
            )
            connection.execute(
                "INSERT INTO production_recipe_heads"
                "(scope_key, sequence, entry_sha256) VALUES (?, ?, ?) "
                "ON CONFLICT(scope_key) DO UPDATE SET "
                "sequence=excluded.sequence, entry_sha256=excluded.entry_sha256",
                (scope_key, sequence, entry_sha256),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def extract_recipe(
        self,
        project_ref: ProjectRef,
        task_profile: object,
        graph_patterns: Sequence[object],
        failure_refs: Sequence[object],
        p4_refs: Sequence[object],
        *,
        scope: RecipeScope = RecipeScope.PROJECT,
        applicability: Mapping[str, object],
        parameter_schema: Mapping[str, object],
        learning_evidence: Sequence[object],
    ) -> ProductionRecipe:
        self._verify_integrity()
        if not isinstance(scope, RecipeScope):
            scope = RecipeScope(str(scope))
        if (
            isinstance(task_profile, Task)
            and task_profile.task_ref.project_ref != project_ref
        ):
            raise RecipeScopeError("source Task belongs to another Project")
        normalized_task = _freeze_mapping(
            _normalize_task_profile(task_profile)
        )
        normalized_patterns = tuple(
            _freeze_mapping(_normalize_graph_pattern(value))
            for value in graph_patterns
        )
        for value in graph_patterns:
            if (
                isinstance(value, Graph)
                and value.graph_ref.project_ref != project_ref
            ):
                raise RecipeScopeError("source Graph belongs to another Project")
        normalized_applicability = _freeze_mapping(
            cast(Mapping[str, object], _normalize_value(applicability))
        )
        normalized_parameters = _freeze_mapping(
            cast(Mapping[str, object], _normalize_value(parameter_schema))
        )
        _validate_side_effects(normalized_task, normalized_patterns)
        evidence_values = list(learning_evidence)
        if isinstance(task_profile, Task):
            evidence_values.append(task_profile.canonical_digest)
        for value in graph_patterns:
            if isinstance(value, Graph):
                evidence_values.append(value.record_sha256)
        evidence = tuple(
            sorted({_evidence_token(value) for value in evidence_values})
        )
        failures = tuple(
            sorted({_evidence_token(value) for value in failure_refs})
        )
        p4_evidence = tuple(
            sorted({_evidence_token(value) for value in p4_refs})
        )
        scope_key = (
            "ENGINE"
            if scope is RecipeScope.ENGINE
            else _project_key(project_ref)
        )
        semantic = self._semantic_payload(
            scope=scope,
            task_profile=normalized_task,
            applicability=normalized_applicability,
            patterns=normalized_patterns,
            parameter_schema=normalized_parameters,
        )
        _assert_no_raw_or_secret(semantic)
        serialized_semantic = _canonical_json(semantic)
        if scope is RecipeScope.ENGINE and (
            _IDENTITY_TEXT.search(serialized_semantic)
            or _PATH_TEXT.search(serialized_semantic)
        ):
            raise RecipeContractError(
                "Engine recipe contains a source identity"
            )
        semantic_digest = _sha256(semantic)
        existing = self._connection.execute(
            "SELECT record_json FROM production_recipe_versions "
            "WHERE scope_key = ? AND semantic_digest = ? "
            "AND prior_recipe_digest IS NULL",
            (scope_key, semantic_digest),
        ).fetchone()
        if existing is not None:
            payload = json.loads(str(existing["record_json"]))
            if not isinstance(payload, dict):
                raise RecipeIntegrityError("stored recipe is malformed")
            return self._recipe_from_record(payload)
        required = _extract_sequence(
            normalized_task, "required_capabilities"
        )
        optional = _extract_sequence(
            normalized_task, "optional_capabilities"
        )
        inputs = _extract_sequence(normalized_task, "input_roles")
        output_contract = normalized_task.get("output_contract", {})
        outputs = (
            tuple(sorted(str(key) for key in output_contract))
            if isinstance(output_contract, Mapping)
            else ()
        )
        validation = tuple(
            sorted(
                set(
                    _extract_sequence(
                        normalized_task, "evidence_requirements"
                    )
                )
                | set(
                    _extract_sequence(
                        normalized_task, "acceptance_criteria"
                    )
                )
            )
        )
        resources = normalized_task.get("resource_hints", {})
        recipe_id = f"rcp_{semantic_digest[:24]}"
        provisional = ProductionRecipe(
            recipe_id=recipe_id,
            version=1,
            scope=scope,
            status=RecipeStatus.CANDIDATE,
            task_profile=normalized_task,
            applicability=normalized_applicability,
            normalized_graph_pattern=normalized_patterns,
            parameter_schema=normalized_parameters,
            required_capabilities=required,
            optional_capabilities=optional,
            input_roles=inputs,
            output_roles=outputs,
            validation_requirements=validation,
            resource_hints=(
                cast(Mapping[str, object], resources)
                if isinstance(resources, Mapping)
                else MappingProxyType({})
            ),
            learning_evidence=evidence,
            failure_evidence=failures,
            p4_evidence_refs=p4_evidence,
            metrics=_freeze_mapping(
                {
                    "failed_source_runs": len(failures),
                    "source_evidence_count": len(evidence),
                }
            ),
            prior_recipe_digest=None,
            semantic_digest=semantic_digest,
            canonical_digest=_ZERO_DIGEST,
            created_at=_utc_now(),
            _scope_key=scope_key,
        )
        digest = _sha256(self._recipe_core(provisional))
        recipe_values = {
            info.name: getattr(provisional, info.name)
            for info in fields(provisional)
            if info.name != "canonical_digest"
        }
        recipe = ProductionRecipe(
            **recipe_values,
            canonical_digest=digest,
        )
        self._append_record(
            scope_key=scope_key,
            record_kind="RECIPE",
            record_ref=f"{recipe.recipe_id}:{recipe.version}",
            record_sha256=digest,
            insert_sql=(
                "INSERT INTO production_recipe_versions "
                "(scope_key, recipe_id, version, semantic_digest, "
                "prior_recipe_digest, record_json, record_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            insert_values=(
                scope_key,
                recipe.recipe_id,
                recipe.version,
                recipe.semantic_digest,
                recipe.prior_recipe_digest,
                _canonical_json(self._recipe_record(recipe)),
                digest,
            ),
        )
        return recipe

    def extract_from_graph(
        self,
        project_ref: ProjectRef,
        task: Task,
        graph: Graph,
        *,
        scope: RecipeScope = RecipeScope.PROJECT,
        applicability: Mapping[str, object],
        parameter_schema: Mapping[str, object],
        learning_evidence: Sequence[object],
    ) -> ProductionRecipe:
        return self.extract_recipe(
            project_ref,
            task,
            (graph,),
            (),
            (),
            scope=scope,
            applicability=applicability,
            parameter_schema=parameter_schema,
            learning_evidence=learning_evidence,
        )

    def _require_scope(
        self, project_ref: ProjectRef, recipe: ProductionRecipe
    ) -> None:
        if (
            recipe.scope is RecipeScope.PROJECT
            and recipe._scope_key != _project_key(project_ref)
        ):
            raise RecipeScopeError(
                "Project recipe cannot cross Project scope"
            )

    def _require_current_recipe(self, recipe: ProductionRecipe) -> None:
        row = self._connection.execute(
            "SELECT record_sha256 FROM production_recipe_versions "
            "WHERE scope_key = ? AND recipe_id = ? AND version = ?",
            (recipe._scope_key, recipe.recipe_id, recipe.version),
        ).fetchone()
        if row is None or not hmac.compare_digest(
            str(row["record_sha256"]), recipe.canonical_digest
        ):
            raise RecipeIntegrityError(
                "recipe identity does not match durable state"
            )
        latest = self._connection.execute(
            "SELECT MAX(version) AS version "
            "FROM production_recipe_versions "
            "WHERE scope_key = ? AND recipe_id = ?",
            (recipe._scope_key, recipe.recipe_id),
        ).fetchone()
        if latest is None or int(latest["version"]) != recipe.version:
            raise RecipeStaleError("recipe version has been superseded")

    def get_recipe(
        self,
        project_ref: ProjectRef,
        recipe_id: str,
        version: int | None = None,
    ) -> ProductionRecipe:
        self._verify_integrity()
        project_key = _project_key(project_ref)
        if version is None:
            row = self._connection.execute(
                "SELECT record_json FROM production_recipe_versions "
                "WHERE recipe_id = ? AND scope_key IN (?, 'ENGINE') "
                "ORDER BY version DESC LIMIT 1",
                (recipe_id, project_key),
            ).fetchone()
        else:
            row = self._connection.execute(
                "SELECT record_json FROM production_recipe_versions "
                "WHERE recipe_id = ? AND version = ? "
                "AND scope_key IN (?, 'ENGINE')",
                (recipe_id, version, project_key),
            ).fetchone()
        if row is None:
            raise RecipeScopeError(
                "recipe is absent from accessible scope"
            )
        payload = json.loads(str(row["record_json"]))
        if not isinstance(payload, dict):
            raise RecipeIntegrityError("stored recipe is malformed")
        return self._recipe_from_record(payload)

    def match_recipe(
        self,
        project_ref: ProjectRef,
        recipe: ProductionRecipe,
        task_profile: object,
    ) -> RecipeMatch:
        self._verify_integrity()
        self._require_scope(project_ref, recipe)
        self._require_current_recipe(recipe)
        query = _normalize_task_profile(task_profile)
        reasons: list[str] = []
        hard_keys = ("kind", "task_type", "domain")
        for key in hard_keys:
            expected = recipe.task_profile.get(key)
            observed = query.get(key)
            if (
                expected is not None
                and observed is not None
                and expected != observed
            ):
                return RecipeMatch(
                    recipe.recipe_id,
                    recipe.version,
                    recipe.canonical_digest,
                    RecipeMatchState.NO_MATCH,
                    0.0,
                    (f"incompatible {key}",),
                )
        reserved_profile_keys = {
            "acceptance_criteria",
            "constraints",
            "evidence_requirements",
            "input_roles",
            "optional_capabilities",
            "output_contract",
            "required_capabilities",
            "resource_hints",
            "side_effect_authority",
        }
        for key, expected in recipe.task_profile.items():
            if (
                key not in hard_keys
                and key not in reserved_profile_keys
                and key in query
                and query[key] != expected
            ):
                reasons.append(f"semantic profile value {key} differs")
        query_required = set(
            _extract_sequence(query, "required_capabilities")
        )
        missing_required = set(recipe.required_capabilities) - query_required
        if missing_required and "required_capabilities" in query:
            return RecipeMatch(
                recipe.recipe_id,
                recipe.version,
                recipe.canonical_digest,
                RecipeMatchState.NO_MATCH,
                0.0,
                ("missing required capabilities",),
            )
        query_optional = set(
            _extract_sequence(query, "optional_capabilities")
        ) | query_required
        if set(recipe.optional_capabilities) - query_optional:
            reasons.append("optional capabilities unavailable")
        for key, expected in recipe.applicability.items():
            if key not in query:
                if key.endswith("_required"):
                    reasons.append(
                        f"required applicability value {key} not supplied"
                    )
            elif query[key] != expected:
                if key in hard_keys or key.endswith("_required"):
                    return RecipeMatch(
                        recipe.recipe_id,
                        recipe.version,
                        recipe.canonical_digest,
                        RecipeMatchState.NO_MATCH,
                        0.0,
                        (f"incompatible applicability {key}",),
                    )
                reasons.append(f"applicability value {key} differs")
        optional_branch = any(
            bool(node.get("optional"))
            for pattern in recipe.normalized_graph_pattern
            for node in cast(
                Iterable[Mapping[str, object]],
                pattern.get("nodes", ()),
            )
            if isinstance(node, Mapping)
        )
        if optional_branch and not bool(
            query.get(
                "include_optional",
                query.get("optional_branch", True),
            )
        ):
            reasons.append("optional branch not required")
        state = (
            RecipeMatchState.PARTIAL_MATCH
            if reasons
            else RecipeMatchState.MATCH
        )
        score = max(0.0, 1.0 - (0.1 * len(reasons)))
        result = RecipeMatch(
            recipe.recipe_id,
            recipe.version,
            recipe.canonical_digest,
            state,
            score,
            tuple(reasons),
        )
        query_digest = _sha256(query)
        cache_key = _sha256(
            {
                "matcher": self._MATCHER_VERSION,
                "query": query_digest,
                "recipe": recipe.canonical_digest,
            }
        )
        result_json = _canonical_json(
            {
                "reasons": list(result.reasons),
                "score": result.score,
                "state": result.state.value,
            }
        )
        derivation = _sha256(
            {
                "query": query_digest,
                "recipe": recipe.canonical_digest,
                "result": result_json,
            }
        )
        self._connection.execute(
            "INSERT OR IGNORE INTO recipe_match_cache "
            "(cache_key, scope_key, recipe_digest, query_digest, "
            "matcher_version, result_json, derivation_sha256, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cache_key,
                recipe._scope_key,
                recipe.canonical_digest,
                query_digest,
                self._MATCHER_VERSION,
                result_json,
                derivation,
                _utc_now(),
            ),
        )
        self._connection.commit()
        return result

    def supersede_recipe(
        self,
        project_ref: ProjectRef,
        recipe: ProductionRecipe,
        *,
        applicability: Mapping[str, object],
        parameter_schema: Mapping[str, object],
        learning_evidence: Sequence[object],
    ) -> ProductionRecipe:
        self._verify_integrity()
        self._require_scope(project_ref, recipe)
        self._require_current_recipe(recipe)
        normalized_applicability = _freeze_mapping(
            cast(
                Mapping[str, object],
                _normalize_value(applicability),
            )
        )
        normalized_parameters = _freeze_mapping(
            cast(
                Mapping[str, object],
                _normalize_value(parameter_schema),
            )
        )
        evidence = tuple(
            sorted(
                set(recipe.learning_evidence)
                | {
                    _evidence_token(value)
                    for value in learning_evidence
                }
            )
        )
        semantic = self._semantic_payload(
            scope=recipe.scope,
            task_profile=recipe.task_profile,
            applicability=normalized_applicability,
            patterns=recipe.normalized_graph_pattern,
            parameter_schema=normalized_parameters,
        )
        provisional = ProductionRecipe(
            recipe_id=recipe.recipe_id,
            version=recipe.version + 1,
            scope=recipe.scope,
            status=(
                RecipeStatus.SUPPORTED
                if evidence
                else RecipeStatus.CANDIDATE
            ),
            task_profile=recipe.task_profile,
            applicability=normalized_applicability,
            normalized_graph_pattern=recipe.normalized_graph_pattern,
            parameter_schema=normalized_parameters,
            required_capabilities=recipe.required_capabilities,
            optional_capabilities=recipe.optional_capabilities,
            input_roles=recipe.input_roles,
            output_roles=recipe.output_roles,
            validation_requirements=recipe.validation_requirements,
            resource_hints=recipe.resource_hints,
            learning_evidence=evidence,
            failure_evidence=recipe.failure_evidence,
            p4_evidence_refs=recipe.p4_evidence_refs,
            metrics=_freeze_mapping(
                {
                    **cast(dict[str, object], _thaw(recipe.metrics)),
                    "superseded_version": recipe.version,
                }
            ),
            prior_recipe_digest=recipe.canonical_digest,
            semantic_digest=_sha256(semantic),
            canonical_digest=_ZERO_DIGEST,
            created_at=_utc_now(),
            _scope_key=recipe._scope_key,
        )
        digest = _sha256(self._recipe_core(provisional))
        successor_values = {
            info.name: getattr(provisional, info.name)
            for info in fields(provisional)
            if info.name != "canonical_digest"
        }
        successor = ProductionRecipe(
            **successor_values,
            canonical_digest=digest,
        )
        self._append_record(
            scope_key=successor._scope_key,
            record_kind="RECIPE",
            record_ref=f"{successor.recipe_id}:{successor.version}",
            record_sha256=digest,
            insert_sql=(
                "INSERT INTO production_recipe_versions "
                "(scope_key, recipe_id, version, semantic_digest, "
                "prior_recipe_digest, record_json, record_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            insert_values=(
                successor._scope_key,
                successor.recipe_id,
                successor.version,
                successor.semantic_digest,
                successor.prior_recipe_digest,
                _canonical_json(self._recipe_record(successor)),
                digest,
            ),
        )
        return successor

    def record_recipe_run(
        self,
        recipe: ProductionRecipe,
        run_ref: object,
        outcome: RecipeRunOutcome,
        output_evidence: Sequence[object],
        expected_recipe_digest: str,
        expected_fence: int,
        observed_fence: int,
        *,
        validation_evidence: Sequence[object] = (),
    ) -> RecipeRunEvidence:
        self._verify_integrity()
        self._require_current_recipe(recipe)
        if (
            isinstance(run_ref, RunRef)
            and recipe.scope is RecipeScope.PROJECT
            and _project_key(run_ref.project_ref) != recipe._scope_key
        ):
            raise RecipeScopeError("Run belongs to another Project")
        if not isinstance(outcome, RecipeRunOutcome):
            outcome = RecipeRunOutcome(str(outcome))
        if not hmac.compare_digest(
            expected_recipe_digest, recipe.canonical_digest
        ):
            raise RecipeStaleError("expected recipe digest is stale")
        if (
            expected_fence < 0
            or observed_fence < 0
            or expected_fence != observed_fence
        ):
            raise RecipeStaleError(
                "recipe run evidence has a stale execution fence"
            )
        outputs = tuple(
            sorted({_evidence_token(value) for value in output_evidence})
        )
        validations = tuple(
            sorted({_evidence_token(value) for value in validation_evidence})
        )
        if (
            outcome is RecipeRunOutcome.SUCCEEDED
            and (not outputs or not validations)
        ):
            raise RecipeContractError(
                "successful recipe run requires output and validation evidence"
            )
        run_token = _evidence_token(run_ref)
        identity_payload = {
            "expected_fence": expected_fence,
            "outcome": outcome.value,
            "outputs": list(outputs),
            "recipe": recipe.canonical_digest,
            "run": run_token,
            "validations": list(validations),
        }
        provisional = RecipeRunEvidence(
            evidence_id=f"rpe_{_sha256(identity_payload)[:24]}",
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.version,
            recipe_digest=recipe.canonical_digest,
            run_ref=run_token,
            outcome=outcome,
            output_evidence=outputs,
            validation_evidence=validations,
            expected_fence=expected_fence,
            observed_fence=observed_fence,
            created_at=_utc_now(),
            canonical_digest=_ZERO_DIGEST,
            _scope_key=recipe._scope_key,
        )
        digest = _sha256(self._run_core(provisional))
        evidence_values = {
            info.name: getattr(provisional, info.name)
            for info in fields(provisional)
            if info.name != "canonical_digest"
        }
        evidence = RecipeRunEvidence(
            **evidence_values,
            canonical_digest=digest,
        )
        existing = self._connection.execute(
            "SELECT record_json, record_sha256 FROM recipe_run_evidence "
            "WHERE scope_key = ? AND evidence_id = ?",
            (evidence._scope_key, evidence.evidence_id),
        ).fetchone()
        if existing is not None:
            if hmac.compare_digest(
                str(existing["record_sha256"]),
                evidence.canonical_digest,
            ):
                payload = json.loads(str(existing["record_json"]))
                if isinstance(payload, dict):
                    return self._run_from_record(payload)
            raise RecipeIntegrityError(
                "recipe run idempotency conflict"
            )
        self._append_record(
            scope_key=evidence._scope_key,
            record_kind="EVIDENCE",
            record_ref=evidence.evidence_id,
            record_sha256=digest,
            insert_sql=(
                "INSERT INTO recipe_run_evidence "
                "(scope_key, evidence_id, recipe_id, recipe_version, "
                "recipe_digest, record_json, record_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            insert_values=(
                evidence._scope_key,
                evidence.evidence_id,
                evidence.recipe_id,
                evidence.recipe_version,
                evidence.recipe_digest,
                _canonical_json(self._run_record(evidence)),
                digest,
            ),
        )
        return evidence

    def list_recipe_run_evidence(
        self,
        project_ref: ProjectRef,
        recipe_id: str,
    ) -> tuple[RecipeRunEvidence, ...]:
        self._verify_integrity()
        rows = self._connection.execute(
            "SELECT record_json FROM recipe_run_evidence "
            "WHERE recipe_id = ? AND scope_key IN (?, 'ENGINE') "
            "ORDER BY rowid",
            (recipe_id, _project_key(project_ref)),
        ).fetchall()
        result: list[RecipeRunEvidence] = []
        for row in rows:
            payload = json.loads(str(row["record_json"]))
            if not isinstance(payload, dict):
                raise RecipeIntegrityError(
                    "stored recipe evidence is malformed"
                )
            result.append(self._run_from_record(payload))
        return tuple(result)

    def instantiate_graph(
        self,
        project_ref: ProjectRef,
        recipe: ProductionRecipe,
        task: Task,
        run_ref: RunRef,
        graph_ref: GraphRef,
        *,
        input_bindings: (
            Mapping[str, NodeInputBinding]
            | Sequence[NodeInputBinding]
        ) = (),
    ) -> RecipeInstantiation:
        self._verify_integrity()
        self._require_scope(project_ref, recipe)
        self._require_current_recipe(recipe)
        if (
            task.task_ref.project_ref != project_ref
            or run_ref.project_ref != project_ref
        ):
            raise RecipeScopeError(
                "Task or Run belongs to another Project"
            )
        if graph_ref.project_ref != project_ref:
            raise RecipeScopeError("target Graph belongs to another Project")
        match = self.match_recipe(project_ref, recipe, task)
        if match.state is RecipeMatchState.NO_MATCH:
            raise RecipeContractError("recipe does not apply to Task")
        task_validations = set(task.evidence_requirements) | set(
            task.acceptance_criteria
        )
        if not set(recipe.validation_requirements).issubset(
            task_validations
        ):
            raise RecipeContractError(
                "Task validation requirements would be removed"
            )
        if not recipe.normalized_graph_pattern:
            raise RecipeContractError(
                "recipe has no Graph pattern to instantiate"
            )
        raw_nodes = recipe.normalized_graph_pattern[0].get("nodes", ())
        if not isinstance(raw_nodes, Iterable):
            raise RecipeContractError(
                "recipe Graph pattern is malformed"
            )
        node_records = [
            value for value in raw_nodes if isinstance(value, Mapping)
        ]
        role_refs = {
            str(value["role"]): NodeRef.new(graph_ref)
            for value in node_records
        }
        supplied_by_name: dict[str, NodeInputBinding] = {}
        supplied_sequence: tuple[NodeInputBinding, ...] = ()
        if isinstance(input_bindings, Mapping):
            supplied_by_name = dict(input_bindings)
        else:
            supplied_sequence = tuple(input_bindings)
        nodes: list[Node] = []
        for record in node_records:
            role = str(record["role"])
            dependency_refs = tuple(
                role_refs[str(value)]
                for value in cast(
                    Iterable[object], record.get("dependencies", ())
                )
            )
            capabilities: list[CapabilityRef] = []
            for raw_capability in cast(
                Iterable[object], record.get("capabilities", ())
            ):
                if not isinstance(raw_capability, Mapping):
                    continue
                capability_id = str(
                    raw_capability.get("capability_id", "")
                )
                version = str(raw_capability.get("version", ""))
                if not capability_id or version == "*":
                    raise RecipeContractError(
                        "recipe capability must have an exact semantic version"
                    )
                capabilities.append(
                    CapabilityRef(
                        capability_id=capability_id,
                        version=version,
                    )
                )
            reconstructed: list[NodeInputBinding] = []
            for raw_binding in cast(
                Iterable[object], record.get("input_bindings", ())
            ):
                if not isinstance(raw_binding, Mapping):
                    continue
                input_name = str(
                    raw_binding.get(
                        "input_name",
                        raw_binding.get("name", "input"),
                    )
                )
                source_role = raw_binding.get("source_role")
                output_key = str(
                    raw_binding.get(
                        "output_key",
                        raw_binding.get(
                            "source_output_key", "output"
                        ),
                    )
                )
                if (
                    isinstance(source_role, str)
                    and source_role in role_refs
                ):
                    reconstructed.append(
                        NodeInputBinding.from_node_output(
                            input_name,
                            role_refs[source_role],
                            output_key,
                        )
                    )
                elif input_name in supplied_by_name:
                    reconstructed.append(
                        supplied_by_name[input_name]
                    )
            if not reconstructed and supplied_sequence:
                reconstructed.extend(supplied_sequence)
            requirement = str(
                record.get(
                    "side_effect_requirement", "READ_ONLY"
                )
            )
            if not _side_effect_within(
                requirement, str(task.side_effect_authority)
            ):
                raise RecipeSideEffectError(
                    "instantiated Node exceeds Task side-effect authority"
                )
            output_contract_value = record.get(
                "output_contract", {}
            )
            resource_hints_value = record.get("resource_hints", {})
            nodes.append(
                Node(
                    node_ref=role_refs[role],
                    executor_kind=str(
                        record.get(
                            "executor_kind", "capability"
                        )
                    ),
                    required_capabilities=tuple(capabilities),
                    dependencies=dependency_refs,
                    input_bindings=tuple(reconstructed),
                    output_contract=(
                        {
                            str(key): str(value)
                            for key, value
                            in output_contract_value.items()
                        }
                        if isinstance(
                            output_contract_value, Mapping
                        )
                        else {}
                    ),
                    condition_ref=(
                        str(record["condition_ref"])
                        if record.get("condition_ref")
                        is not None
                        else None
                    ),
                    side_effect_requirement=requirement,
                    resource_hints=(
                        {
                            str(key): value
                            for key, value
                            in resource_hints_value.items()
                            if value is None
                            or isinstance(
                                value,
                                (str, int, float, bool),
                            )
                        }
                        if isinstance(resource_hints_value, Mapping)
                        else {}
                    ),
                    evidence_requirements=tuple(
                        str(value)
                        for value in cast(
                            Iterable[object],
                            record.get(
                                "evidence_requirements", ()
                            ),
                        )
                    ),
                )
            )
        graph = Graph.build(
            graph_ref=graph_ref,
            task_ref=task.task_ref,
            task_digest=task.canonical_digest,
            run_ref=run_ref,
            nodes=nodes,
            created_at=_utc_now(),
        )
        return RecipeInstantiation(
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.version,
            recipe_digest=recipe.canonical_digest,
            graph=graph,
        )

    def build_system_evidence_summary(
        self,
        project_ref: ProjectRef,
        recipes_or_evidence: Sequence[
            ProductionRecipe | RecipeRunEvidence
        ],
    ) -> RecipeLearningEvidenceSummary:
        self._verify_integrity()
        if not recipes_or_evidence:
            raise RecipeContractError(
                "system evidence summary requires exact evidence pointers"
            )
        recipe_digests: set[str] = set()
        evidence_digests: set[str] = set()
        for value in recipes_or_evidence:
            if isinstance(value, ProductionRecipe):
                self._require_scope(project_ref, value)
                recipe_digests.add(value.canonical_digest)
            elif isinstance(value, RecipeRunEvidence):
                if value._scope_key not in {
                    _project_key(project_ref),
                    "ENGINE",
                }:
                    raise RecipeScopeError(
                        "evidence belongs to another Project"
                    )
                evidence_digests.add(value.canonical_digest)
            else:
                raise RecipeContractError(
                    "unsupported evidence summary input"
                )
        kpis = self.kpi_results()
        core = {
            "kpi_results": kpis,
            "recipe_digests": sorted(recipe_digests),
            "run_evidence_digests": sorted(evidence_digests),
            "scope_key": _project_key(project_ref),
        }
        return RecipeLearningEvidenceSummary(
            scope_key=_project_key(project_ref),
            recipe_digests=tuple(sorted(recipe_digests)),
            run_evidence_digests=tuple(sorted(evidence_digests)),
            kpi_results=cast(Mapping[str, int], _freeze(kpis)),
            canonical_digest=_sha256(core),
        )

    def kpi_results(self) -> dict[str, int]:
        self._verify_integrity()
        results = {name: 0 for name in _KPI_NAMES}
        rows = self._connection.execute(
            "SELECT scope_key, record_json "
            "FROM production_recipe_versions"
        ).fetchall()
        for row in rows:
            text = str(row["record_json"])
            if (
                str(row["scope_key"]) == "ENGINE"
                and _IDENTITY_TEXT.search(text)
            ):
                results[
                    "recipes_with_Project_ids_in_Engine_scope"
                ] += 1
            if _RAW_HISTORICAL.search(text):
                results["active_raw_historical_content"] += 1
            payload = json.loads(text)
            if (
                isinstance(payload, dict)
                and payload.get("status")
                == RecipeStatus.SUPPORTED.value
            ):
                learning = payload.get("learning_evidence")
                if not isinstance(learning, list) or not learning:
                    results["recipe_without_source_evidence"] += 1
            if "mandatory_global_pipeline" in text:
                results[
                    "recipe_becomes_mandatory_global_pipeline"
                ] += 1
            if "global_heavyweight_resource_lock" in text:
                results[
                    "global_heavyweight_resource_lock"
                ] += 1
            if (
                "routing_override" in text
                or "bypass_hard_constraints" in text
            ):
                results[
                    "learned_routing_bypasses_hard_constraints"
                ] += 1
            if "root_cause_fact" in text:
                results[
                    "unproven_root_causes_stored_as_fact"
                ] += 1
        stale = self._connection.execute(
            "SELECT COUNT(*) AS count FROM recipe_run_evidence "
            "WHERE json_extract(record_json, '$.expected_fence') != "
            "json_extract(record_json, '$.observed_fence')"
        ).fetchone()
        if stale is not None:
            results["accepted_stale_results"] = int(stale["count"])
        return results


def extract_from_graph(
    project_ref: ProjectRef,
    task: Task,
    graph: Graph,
    *,
    scope: RecipeScope = RecipeScope.PROJECT,
    applicability: Mapping[str, object],
    parameter_schema: Mapping[str, object],
    learning_evidence: Sequence[object],
) -> ProductionRecipe:
    """Pure convenience adapter for one Graph; durable callers use the service."""

    with ProductionRecipeLearningService(":memory:") as service:
        return service.extract_from_graph(
            project_ref,
            task,
            graph,
            scope=scope,
            applicability=applicability,
            parameter_schema=parameter_schema,
            learning_evidence=learning_evidence,
        )


def instantiate_graph(
    project_ref: ProjectRef,
    recipe: ProductionRecipe,
    task: Task,
    run_ref: RunRef,
    graph_ref: GraphRef,
    *,
    input_bindings: (
        Mapping[str, NodeInputBinding] | Sequence[NodeInputBinding]
    ) = (),
) -> Graph:
    """Instantiate an extracted recipe as an ordinary immutable Graph."""

    with ProductionRecipeLearningService(":memory:") as service:
        service._append_record(
            scope_key=recipe._scope_key,
            record_kind="RECIPE",
            record_ref=f"{recipe.recipe_id}:{recipe.version}",
            record_sha256=recipe.canonical_digest,
            insert_sql=(
                "INSERT INTO production_recipe_versions "
                "(scope_key, recipe_id, version, semantic_digest, "
                "prior_recipe_digest, record_json, record_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            insert_values=(
                recipe._scope_key,
                recipe.recipe_id,
                recipe.version,
                recipe.semantic_digest,
                recipe.prior_recipe_digest,
                _canonical_json(service._recipe_record(recipe)),
                recipe.canonical_digest,
            ),
        )
        return service.instantiate_graph(
            project_ref,
            recipe,
            task,
            run_ref,
            graph_ref,
            input_bindings=input_bindings,
        ).graph


__all__ = [
    "ProductionRecipe",
    "ProductionRecipeLearningService",
    "RecipeContractError",
    "RecipeInstantiation",
    "RecipeIntegrityError",
    "RecipeLearningError",
    "RecipeLearningEvidenceSummary",
    "RecipeMatch",
    "RecipeMatchState",
    "RecipeRunEvidence",
    "RecipeRunOutcome",
    "RecipeScope",
    "RecipeScopeError",
    "RecipeSideEffectError",
    "RecipeStaleError",
    "RecipeStatus",
    "extract_from_graph",
    "instantiate_graph",
]
