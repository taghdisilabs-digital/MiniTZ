"""Durable, provider-neutral production-pack descriptors.

Production packs are immutable data registrations over the universal Biella
substrate.  They describe capabilities, graph recipes, validators, artifact
roles, adapter bindings, and resource profiles without introducing a
domain-specific task, run, or worker hierarchy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from typing import cast

from .capability import Capability, CapabilityError, CapabilityRef, CapabilityRegistry


_PACK_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,63}")
_VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_ROLE_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_ABSOLUTE_REF_PATTERN = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x00-\x1f]{1,512}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ProductionPackError(Exception):
    """Base class for production-pack contract failures."""


class ProductionPackContractError(ProductionPackError):
    """A production-pack descriptor is malformed."""


class ProductionPackConflictError(ProductionPackError):
    """An immutable pack or idempotency identity conflicts."""


class ProductionPackNotFoundError(ProductionPackError):
    """A requested production pack has not been registered."""


class ProductionPackIntegrityError(ProductionPackError):
    """Persisted production-pack evidence failed integrity verification."""


def _validate_text_ref(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 576
        or _ABSOLUTE_REF_PATTERN.fullmatch(value) is None
    ):
        raise ProductionPackContractError(
            f"{field_name} must be a bounded absolute reference"
        )
    return value


def _validate_timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise ProductionPackContractError("created_at must be serialized text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProductionPackContractError(
            "created_at must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductionPackContractError(
            "created_at must be a timezone-aware ISO-8601 timestamp"
        )
    return value


@dataclass(frozen=True, order=True)
class ProductionPackRef:
    """Stable production-pack identity and immutable semantic version."""

    pack_id: str
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.pack_id, str) or _PACK_ID_PATTERN.fullmatch(self.pack_id) is None:
            raise ProductionPackContractError("pack_id is malformed")
        if not isinstance(self.version, str) or _VERSION_PATTERN.fullmatch(self.version) is None:
            raise ProductionPackContractError("version must be semantic x.y.z")

    @property
    def value(self) -> str:
        return f"{self.pack_id}@{self.version}"


@dataclass(frozen=True)
class GraphRecipeStepRegistration:
    """A capability step referenced by a pack-owned graph recipe."""

    step_id: str
    capability_ref: CapabilityRef
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or _ROLE_PATTERN.fullmatch(self.step_id) is None:
            raise ProductionPackContractError("graph recipe step_id is malformed")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        if isinstance(self.depends_on, (str, bytes)) or not isinstance(
            self.depends_on, Sequence
        ):
            raise ProductionPackContractError("depends_on must be a sequence")
        dependencies = tuple(self.depends_on)
        if len(dependencies) > 64 or len(set(dependencies)) != len(dependencies):
            raise ProductionPackContractError("depends_on is duplicated or unbounded")
        for dependency in dependencies:
            if not isinstance(dependency, str) or _ROLE_PATTERN.fullmatch(dependency) is None:
                raise ProductionPackContractError("graph dependency is malformed")
            if dependency == self.step_id:
                raise ProductionPackContractError("graph recipe step cannot depend on itself")
        object.__setattr__(self, "depends_on", tuple(sorted(dependencies)))


@dataclass(frozen=True)
class GraphRecipeRegistration:
    """Optional graph-recipe data; it does not impose a global hierarchy."""

    recipe_ref: str
    steps: tuple[GraphRecipeStepRegistration, ...]

    def __post_init__(self) -> None:
        _validate_text_ref(self.recipe_ref, "recipe_ref")
        if isinstance(self.steps, (str, bytes)) or not isinstance(self.steps, Sequence):
            raise ProductionPackContractError("graph recipe steps must be a sequence")
        steps = tuple(self.steps)
        if not steps or len(steps) > 64 or not all(
            isinstance(item, GraphRecipeStepRegistration) for item in steps
        ):
            raise ProductionPackContractError("graph recipe steps are malformed or unbounded")
        step_ids = {item.step_id for item in steps}
        if len(step_ids) != len(steps):
            raise ProductionPackContractError("graph recipe step IDs must be unique")
        if any(set(item.depends_on) - step_ids for item in steps):
            raise ProductionPackContractError("graph recipe dependency does not exist")
        self._validate_acyclic(steps)
        object.__setattr__(self, "steps", steps)

    @staticmethod
    def _validate_acyclic(steps: tuple[GraphRecipeStepRegistration, ...]) -> None:
        dependencies = {item.step_id: set(item.depends_on) for item in steps}
        resolved: set[str] = set()
        while dependencies:
            ready = {step_id for step_id, needs in dependencies.items() if needs <= resolved}
            if not ready:
                raise ProductionPackContractError("graph recipe must be acyclic")
            resolved.update(ready)
            for step_id in ready:
                del dependencies[step_id]


@dataclass(frozen=True)
class ValidatorRegistration:
    """Optional validator binding associated with a pack capability."""

    registration_ref: str
    capability_ref: CapabilityRef
    validator_ref: str
    required: bool = False

    def __post_init__(self) -> None:
        _validate_text_ref(self.registration_ref, "registration_ref")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise TypeError("capability_ref must be CapabilityRef")
        _validate_text_ref(self.validator_ref, "validator_ref")
        if not isinstance(self.required, bool):
            raise ProductionPackContractError("required must be boolean")


def _freeze_string_tuple(value: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ProductionPackContractError(f"{field_name} must be a sequence")
    copied = tuple(value)
    if not copied or len(copied) > 128 or len(set(copied)) != len(copied):
        raise ProductionPackContractError(f"{field_name} is duplicated, empty, or unbounded")
    for item in copied:
        if not isinstance(item, str) or _ROLE_PATTERN.fullmatch(item) is None:
            raise ProductionPackContractError(f"{field_name} contains a malformed role")
    return tuple(sorted(copied))


def _freeze_bindings(
    value: Mapping[str, Sequence[str]],
) -> Mapping[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        raise ProductionPackContractError("adapter_bindings must be a mapping")
    copied: dict[str, tuple[str, ...]] = {}
    if not value or len(value) > 128:
        raise ProductionPackContractError("adapter_bindings is empty or unbounded")
    for capability_value, references in value.items():
        if not isinstance(capability_value, str) or len(capability_value) > 256:
            raise ProductionPackContractError("adapter binding key is malformed")
        if isinstance(references, (str, bytes)) or not isinstance(references, Sequence):
            raise ProductionPackContractError("adapter binding value must be a sequence")
        frozen_references = tuple(references)
        if not frozen_references or len(frozen_references) > 32 or len(
            set(frozen_references)
        ) != len(frozen_references):
            raise ProductionPackContractError("adapter binding is duplicated or unbounded")
        for reference in frozen_references:
            _validate_text_ref(reference, "adapter binding")
        copied[capability_value] = tuple(sorted(frozen_references))
    return MappingProxyType(dict(sorted(copied.items())))


def _freeze_resource_profiles(
    value: Mapping[str, str],
) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or not value or len(value) > 128:
        raise ProductionPackContractError("resource_profiles is empty or unbounded")
    copied = dict(value)
    for capability_value, reference in copied.items():
        if not isinstance(capability_value, str) or len(capability_value) > 256:
            raise ProductionPackContractError("resource profile key is malformed")
        _validate_text_ref(reference, "resource profile")
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True)
class ProductionPack:
    """Immutable domain pack descriptor registered on the universal substrate."""

    pack_ref: ProductionPackRef
    capability_definitions: tuple[Capability, ...]
    graph_recipes: tuple[GraphRecipeRegistration, ...]
    validators: tuple[ValidatorRegistration, ...]
    artifact_roles: tuple[str, ...]
    adapter_bindings: Mapping[str, tuple[str, ...]]
    resource_profiles: Mapping[str, str]
    created_at: str = field(default_factory=_now_utc)
    semantic_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.pack_ref, ProductionPackRef):
            raise TypeError("pack_ref must be ProductionPackRef")
        if not isinstance(self.capability_definitions, tuple):
            raise ProductionPackContractError(
                "capability_definitions must be a bounded tuple"
            )
        if not isinstance(self.graph_recipes, tuple):
            raise ProductionPackContractError("graph_recipes must be a bounded tuple")
        if not isinstance(self.validators, tuple):
            raise ProductionPackContractError("validators must be a bounded tuple")
        capabilities = self.capability_definitions
        recipes = self.graph_recipes
        validators = self.validators
        if not capabilities or len(capabilities) > 128 or not all(
            isinstance(item, Capability) for item in capabilities
        ):
            raise ProductionPackContractError("capability_definitions are malformed")
        capability_refs = {item.capability_ref for item in capabilities}
        if len(capability_refs) != len(capabilities):
            raise ProductionPackContractError("capability definitions must be unique")
        if len(recipes) > 64 or not all(
            isinstance(item, GraphRecipeRegistration) for item in recipes
        ):
            raise ProductionPackContractError("graph_recipes are malformed or unbounded")
        if len(validators) > 128 or not all(
            isinstance(item, ValidatorRegistration) for item in validators
        ):
            raise ProductionPackContractError("validators are malformed or unbounded")
        if len({item.recipe_ref for item in recipes}) != len(recipes):
            raise ProductionPackContractError("graph recipe refs must be unique")
        if len({item.registration_ref for item in validators}) != len(validators):
            raise ProductionPackContractError("validator registrations must be unique")
        referenced = {
            step.capability_ref for recipe in recipes for step in recipe.steps
        } | {item.capability_ref for item in validators}
        if not referenced <= capability_refs:
            raise ProductionPackContractError("pack data references an undefined capability")
        bindings = _freeze_bindings(self.adapter_bindings)
        profiles = _freeze_resource_profiles(self.resource_profiles)
        expected_keys = {item.capability_ref.value for item in capabilities}
        if set(bindings) != expected_keys or set(profiles) != expected_keys:
            raise ProductionPackContractError(
                "every capability must have exact adapter and resource-profile data"
            )
        _validate_timestamp(self.created_at)
        object.__setattr__(self, "capability_definitions", capabilities)
        object.__setattr__(self, "graph_recipes", recipes)
        object.__setattr__(self, "validators", validators)
        object.__setattr__(self, "artifact_roles", _freeze_string_tuple(self.artifact_roles, "artifact_roles"))
        object.__setattr__(self, "adapter_bindings", bindings)
        object.__setattr__(self, "resource_profiles", profiles)
        object.__setattr__(self, "semantic_digest", self._semantic_digest())

    @property
    def graph_recipe_refs(self) -> tuple[str, ...]:
        return tuple(item.recipe_ref for item in self.graph_recipes)

    @property
    def validator_refs(self) -> tuple[str, ...]:
        return tuple(item.validator_ref for item in self.validators)

    @property
    def validator_registration_refs(self) -> tuple[str, ...]:
        return tuple(item.registration_ref for item in self.validators)

    def _semantic_payload(self) -> dict[str, object]:
        return {
            "adapter_bindings": {
                key: list(value) for key, value in self.adapter_bindings.items()
            },
            "artifact_roles": list(self.artifact_roles),
            "capabilities": [
                {
                    "capability_ref": item.capability_ref.value,
                    "contract_sha256": item.contract_sha256,
                }
                for item in sorted(
                    self.capability_definitions,
                    key=lambda capability: capability.capability_ref,
                )
            ],
            "graph_recipes": [
                {
                    "recipe_ref": recipe.recipe_ref,
                    "steps": [
                        {
                            "capability_ref": step.capability_ref.value,
                            "depends_on": list(step.depends_on),
                            "step_id": step.step_id,
                        }
                        for step in recipe.steps
                    ],
                }
                for recipe in self.graph_recipes
            ],
            "pack_ref": self.pack_ref.value,
            "resource_profiles": dict(self.resource_profiles),
            "validators": [
                {
                    "capability_ref": item.capability_ref.value,
                    "registration_ref": item.registration_ref,
                    "required": item.required,
                    "validator_ref": item.validator_ref,
                }
                for item in self.validators
            ],
        }

    def _semantic_digest(self) -> str:
        canonical = json.dumps(
            self._semantic_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class ProductionPackRegistry:
    """SQLite registry for immutable pack descriptors and replay identities."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS production_packs (
                    pack_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    descriptor_json TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (pack_id, version)
                );

                CREATE TABLE IF NOT EXISTS production_pack_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    pack_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (pack_id, version)
                        REFERENCES production_packs(pack_id, version) ON DELETE RESTRICT
                );

                CREATE TRIGGER IF NOT EXISTS production_packs_no_update
                BEFORE UPDATE ON production_packs
                BEGIN
                    SELECT RAISE(ABORT, 'ProductionPack records are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS production_packs_no_delete
                BEFORE DELETE ON production_packs
                BEGIN
                    SELECT RAISE(ABORT, 'ProductionPack history cannot be deleted');
                END;

                CREATE TRIGGER IF NOT EXISTS production_pack_idempotency_no_update
                BEFORE UPDATE ON production_pack_idempotency
                BEGIN
                    SELECT RAISE(ABORT, 'ProductionPack replay evidence is immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS production_pack_idempotency_no_delete
                BEFORE DELETE ON production_pack_idempotency
                BEGIN
                    SELECT RAISE(ABORT, 'ProductionPack replay history cannot be deleted');
                END;
                """
            )
        finally:
            connection.close()

    def register(self, pack: ProductionPack, *, idempotency_key: str) -> ProductionPack:
        if not isinstance(pack, ProductionPack):
            raise TypeError("ProductionPack is required")
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key
            or len(idempotency_key) > 256
            or any(ord(character) < 33 for character in idempotency_key)
        ):
            raise ProductionPackContractError("idempotency_key is malformed")

        capabilities = CapabilityRegistry(self.database_path)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay_row = connection.execute(
                "SELECT * FROM production_pack_idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if replay_row is not None:
                if (
                    replay_row["pack_id"] != pack.pack_ref.pack_id
                    or replay_row["version"] != pack.pack_ref.version
                    or not hmac.compare_digest(
                        cast(str, replay_row["semantic_digest"]), pack.semantic_digest
                    )
                ):
                    raise ProductionPackConflictError(
                        "idempotency_key already identifies a different immutable pack"
                    )
                persisted = self._get_from_connection(connection, pack.pack_ref)
                self._verify_capabilities(connection, capabilities, persisted)
                connection.commit()
                return persisted

            row = connection.execute(
                "SELECT * FROM production_packs WHERE pack_id = ? AND version = ?",
                (pack.pack_ref.pack_id, pack.pack_ref.version),
            ).fetchone()
            if row is not None:
                persisted = self._from_row(row)
                if not hmac.compare_digest(persisted.semantic_digest, pack.semantic_digest):
                    raise ProductionPackConflictError(
                        "ProductionPack version already has a different descriptor"
                    )
                self._verify_capabilities(connection, capabilities, persisted)
            else:
                canonical_definitions = tuple(
                    capabilities._register_with_connection(connection, capability)
                    for capability in pack.capability_definitions
                )
                pack = replace(
                    pack,
                    capability_definitions=canonical_definitions,
                )
                descriptor_json = self._serialize(pack)
                connection.execute(
                    """
                    INSERT INTO production_packs (
                        pack_id, version, descriptor_json, semantic_digest,
                        record_sha256, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pack.pack_ref.pack_id,
                        pack.pack_ref.version,
                        descriptor_json,
                        pack.semantic_digest,
                        self._record_sha256(pack, descriptor_json),
                        pack.created_at,
                    ),
                )
                persisted = pack
            connection.execute(
                """
                INSERT INTO production_pack_idempotency (
                    idempotency_key, pack_id, version, semantic_digest, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    pack.pack_ref.pack_id,
                    pack.pack_ref.version,
                    pack.semantic_digest,
                    _now_utc(),
                ),
            )
            connection.commit()
            return persisted
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _verify_capabilities(
        connection: sqlite3.Connection,
        registry: CapabilityRegistry,
        pack: ProductionPack,
    ) -> None:
        """Verify that every bundled Capability still has its exact contract."""

        try:
            persisted = tuple(
                registry._get_with_connection(connection, item.capability_ref)
                for item in pack.capability_definitions
            )
        except CapabilityError as exc:
            raise ProductionPackIntegrityError(
                "ProductionPack references missing or invalid Capability evidence"
            ) from exc
        for expected, observed in zip(pack.capability_definitions, persisted, strict=True):
            if not hmac.compare_digest(
                expected.contract_sha256,
                observed.contract_sha256,
            ):
                raise ProductionPackIntegrityError(
                    "ProductionPack Capability contract differs from its descriptor"
                )

    def get(self, pack_ref: ProductionPackRef) -> ProductionPack:
        if not isinstance(pack_ref, ProductionPackRef):
            raise TypeError("pack_ref must be ProductionPackRef")
        capabilities = CapabilityRegistry(self.database_path)
        connection = self._connect()
        try:
            pack = self._get_from_connection(connection, pack_ref)
            self._verify_capabilities(connection, capabilities, pack)
            return pack
        finally:
            connection.close()

    def list_packs(self) -> tuple[ProductionPack, ...]:
        capabilities = CapabilityRegistry(self.database_path)
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM production_packs ORDER BY pack_id, version"
            ).fetchall()
            packs = tuple(self._from_row(row) for row in rows)
            for pack in packs:
                self._verify_capabilities(connection, capabilities, pack)
            return packs
        finally:
            connection.close()

    def _get_from_connection(
        self,
        connection: sqlite3.Connection,
        pack_ref: ProductionPackRef,
    ) -> ProductionPack:
        row = connection.execute(
            "SELECT * FROM production_packs WHERE pack_id = ? AND version = ?",
            (pack_ref.pack_id, pack_ref.version),
        ).fetchone()
        if row is None:
            raise ProductionPackNotFoundError(
                f"ProductionPack {pack_ref.value} was not found"
            )
        return self._from_row(row)

    @staticmethod
    def _serialize(pack: ProductionPack) -> str:
        payload = pack._semantic_payload()
        payload["capability_definitions"] = [
            {
                "capability_id": item.capability_id,
                "created_at": item.created_at,
                "description": item.description,
                "input_contract": dict(item.input_contract),
                "output_contract": dict(item.output_contract),
                "side_effects": list(item.side_effects),
                "version": item.version,
            }
            for item in pack.capability_definitions
        ]
        payload["created_at"] = pack.created_at
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _record_sha256(pack: ProductionPack, descriptor_json: str) -> str:
        canonical = json.dumps(
            {
                "created_at": pack.created_at,
                "descriptor_json": descriptor_json,
                "pack_id": pack.pack_ref.pack_id,
                "semantic_digest": pack.semantic_digest,
                "version": pack.pack_ref.version,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> ProductionPack:
        try:
            descriptor_json = cast(str, row["descriptor_json"])
            decoded = cast(object, json.loads(descriptor_json))
            if not isinstance(decoded, dict):
                raise ProductionPackIntegrityError("Pack descriptor is not an object")
            data = cast(dict[str, object], decoded)
            capabilities = tuple(
                Capability(
                    capability_ref=CapabilityRef(
                        cast(str, item["capability_id"]), cast(str, item["version"])
                    ),
                    description=cast(str, item["description"]),
                    input_contract=cast(dict[str, str], item["input_contract"]),
                    output_contract=cast(dict[str, str], item["output_contract"]),
                    side_effects=tuple(cast(list[str], item["side_effects"])),
                    created_at=cast(str, item["created_at"]),
                )
                for item in cast(list[dict[str, object]], data["capability_definitions"])
            )
            capability_by_value = {
                item.capability_ref.value: item.capability_ref for item in capabilities
            }
            graph_recipes = tuple(
                GraphRecipeRegistration(
                    recipe_ref=cast(str, recipe["recipe_ref"]),
                    steps=tuple(
                        GraphRecipeStepRegistration(
                            step_id=cast(str, step["step_id"]),
                            capability_ref=capability_by_value[
                                cast(str, step["capability_ref"])
                            ],
                            depends_on=tuple(cast(list[str], step["depends_on"])),
                        )
                        for step in cast(list[dict[str, object]], recipe["steps"])
                    ),
                )
                for recipe in cast(list[dict[str, object]], data["graph_recipes"])
            )
            validators = tuple(
                ValidatorRegistration(
                    registration_ref=cast(str, item["registration_ref"]),
                    capability_ref=capability_by_value[
                        cast(str, item["capability_ref"])
                    ],
                    validator_ref=cast(str, item["validator_ref"]),
                    required=cast(bool, item["required"]),
                )
                for item in cast(list[dict[str, object]], data["validators"])
            )
            pack_ref_value = cast(str, data["pack_ref"])
            pack_id, version = pack_ref_value.rsplit("@", 1)
            pack = ProductionPack(
                pack_ref=ProductionPackRef(pack_id, version),
                capability_definitions=capabilities,
                graph_recipes=graph_recipes,
                validators=validators,
                artifact_roles=tuple(cast(list[str], data["artifact_roles"])),
                adapter_bindings={
                    key: tuple(cast(list[str], value))
                    for key, value in cast(
                        dict[str, object], data["adapter_bindings"]
                    ).items()
                },
                resource_profiles=cast(dict[str, str], data["resource_profiles"]),
                created_at=cast(str, data["created_at"]),
            )
        except ProductionPackIntegrityError:
            raise
        except (
            CapabilityError,
            KeyError,
            ProductionPackContractError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ProductionPackIntegrityError("Persisted pack descriptor is malformed") from exc

        persisted_digest = row["semantic_digest"]
        persisted_record_digest = row["record_sha256"]
        if (
            row["pack_id"] != pack.pack_ref.pack_id
            or row["version"] != pack.pack_ref.version
            or row["created_at"] != pack.created_at
            or not isinstance(persisted_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_digest) is None
            or not hmac.compare_digest(pack.semantic_digest, persisted_digest)
            or not isinstance(persisted_record_digest, str)
            or _SHA256_PATTERN.fullmatch(persisted_record_digest) is None
            or not hmac.compare_digest(
                cls._record_sha256(pack, descriptor_json), persisted_record_digest
            )
        ):
            raise ProductionPackIntegrityError(
                "Persisted ProductionPack integrity verification failed"
            )
        return pack
