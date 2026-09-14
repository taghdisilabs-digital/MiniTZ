from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minitz_os.engine.capability import (
    Capability,
    CapabilityConflictError,
    CapabilityContractError,
    CapabilityIntegrityError,
    CapabilityNotFoundError,
    CapabilityRef,
    CapabilityRegistry,
)
from minitz_os.engine.project import ProjectStore


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _schema_ref(value: str) -> str:
    return f"schema://sha256/{_sha256(value)}"


def _capability(
    capability_id: str,
    version: str = "1.0.0",
    *,
    description: str | None = None,
    input_contract: dict[str, str] | None = None,
    output_contract: dict[str, str] | None = None,
    side_effects: tuple[str, ...] = (),
) -> Capability:
    return Capability(
        capability_ref=CapabilityRef(capability_id, version),
        description=description or f"Semantic contract for {capability_id}",
        input_contract={} if input_contract is None else input_contract,
        output_contract={} if output_contract is None else output_contract,
        side_effects=side_effects,
    )


class _FailingCapabilityRegistry(CapabilityRegistry):
    def _after_capability_insert(
        self,
        connection: sqlite3.Connection,
        capability: Capability,
    ) -> None:
        del connection, capability
        raise RuntimeError("injected post-insert failure")


class CapabilityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "minitz.sqlite3"
        self.registry = CapabilityRegistry(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_t01_register_software_debug_namespaced_version(self) -> None:
        capability = _capability(
            "software.debug",
            input_contract={"candidate": _schema_ref("source-candidate")},
            output_contract={"evidence": _schema_ref("debug-evidence")},
        )
        registered = self.registry.register(capability)

        self.assertEqual(registered, capability)
        self.assertEqual(registered.capability_ref.value, "software.debug@1.0.0")
        self.assertEqual(registered.namespace, "software")
        self.assertEqual(registered.name, "debug")
        self.assertEqual(self.registry.get(registered.capability_ref), registered)

    def test_t02_register_3d_model_namespaced_version(self) -> None:
        registered = self.registry.register(
            _capability(
                "3d.model",
                input_contract={"brief": _schema_ref("modeling-brief")},
                output_contract={"asset": _schema_ref("3d-asset")},
            )
        )
        self.assertEqual(registered.namespace, "3d")
        self.assertEqual(registered.name, "model")
        self.assertEqual(
            self.registry.list_versions("3d.model"),
            (registered,),
        )

    def test_t03_unknown_future_capability_is_data_not_kernel_change(self) -> None:
        before_schema = self.registry.schema_fingerprint()
        future = self.registry.register(
            _capability(
                "quantum.simulate",
                "7.4.2",
                input_contract={"system": _schema_ref("quantum-system")},
                output_contract={"result": _schema_ref("simulation-result")},
            )
        )
        after_schema = self.registry.schema_fingerprint()

        self.assertEqual(future.capability_ref.value, "quantum.simulate@7.4.2")
        self.assertEqual(before_schema, after_schema)
        source = (ROOT / "src/minitz_os/engine/capability.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        self.assertFalse(
            any(
                isinstance(node, ast.ClassDef)
                and any(
                    isinstance(base, ast.Name) and base.id in {"Enum", "StrEnum"}
                    for base in node.bases
                )
                for node in ast.walk(syntax)
            )
        )

    def test_t04_same_version_conflicting_contract_is_rejected(self) -> None:
        original = self.registry.register(_capability("software.debug"))
        conflicting = _capability(
            "software.debug",
            description="A destructively changed meaning",
        )

        with self.assertRaises(CapabilityConflictError):
            self.registry.register(conflicting)
        self.assertEqual(self.registry.get(original.capability_ref), original)

    def test_t05_new_version_preserves_old_contract(self) -> None:
        version_one = self.registry.register(_capability("software.debug", "1.0.0"))
        version_two = self.registry.register(
            _capability(
                "software.debug",
                "2.0.0",
                description="Second immutable semantic contract",
                output_contract={"evidence": _schema_ref("debug-evidence-v2")},
            )
        )

        self.assertNotEqual(version_one.contract_sha256, version_two.contract_sha256)
        self.assertEqual(self.registry.get(version_one.capability_ref), version_one)
        self.assertEqual(self.registry.get(version_two.capability_ref), version_two)
        self.assertEqual(
            tuple(item.capability_ref for item in self.registry.list_versions("software.debug")),
            (version_one.capability_ref, version_two.capability_ref),
        )

    def test_t06_core_contract_requires_no_executor_or_resource_fields(self) -> None:
        field_names = {field.name for field in fields(Capability)}
        prohibited = {
            "provider",
            "model",
            "tool",
            "worker",
            "gpu",
            "hardware",
            "command",
            "agent_role",
            "implementation",
            "resource",
            "availability",
            "deployment_health",
        }
        self.assertTrue(field_names.isdisjoint(prohibited))
        self.assertTrue(fields(CapabilityRef))

    def test_t07_existence_is_independent_from_zero_availability(self) -> None:
        capability = self.registry.register(_capability("render.frame"))
        implementation_fixture: dict[CapabilityRef, tuple[str, ...]] = {}
        resource_fixture: dict[str, tuple[str, ...]] = {}

        self.assertEqual(implementation_fixture.get(capability.capability_ref, ()), ())
        self.assertEqual(resource_fixture, {})
        self.assertEqual(self.registry.get(capability.capability_ref), capability)
        self.assertFalse(hasattr(capability, "available"))

    def test_t08_generic_contracts_validate_copy_freeze_and_round_trip(self) -> None:
        inputs = {"content": _schema_ref("content")}
        outputs = {"vector": _schema_ref("vector")}
        capability = _capability(
            "model.embed",
            input_contract=inputs,
            output_contract=outputs,
        )
        inputs["hostile"] = _schema_ref("mutated-after-construction")
        registered = self.registry.register(capability)

        self.assertEqual(registered.input_contract, {"content": _schema_ref("content")})
        with self.assertRaises(TypeError):
            registered.input_contract["other"] = _schema_ref("other")  # type: ignore[index]
        restarted = CapabilityRegistry(self.database_path)
        self.assertEqual(restarted.get(registered.capability_ref), registered)

        invalid_contracts = (
            {"Bad Role": _schema_ref("bad-key")},
            {"role": "not an absolute contract reference"},
            {"role": "a" * 10_000 + "://x"},
            {f"role-{index}": _schema_ref(str(index)) for index in range(65)},
        )
        for invalid_contract in invalid_contracts:
            with self.subTest(invalid_contract=invalid_contract):
                with self.assertRaises(CapabilityContractError):
                    _capability("invalid.contract", input_contract=invalid_contract)

    def test_t09_side_effect_metadata_is_semantic_not_authority(self) -> None:
        capability = self.registry.register(
            _capability(
                "filesystem.write",
                side_effects=("filesystem.mutate", "workspace.mutate"),
            )
        )
        external_authorizations: set[str] = set()

        self.assertEqual(
            capability.side_effects,
            ("filesystem.mutate", "workspace.mutate"),
        )
        self.assertEqual(external_authorizations, set())
        self.assertEqual(
            CapabilityRegistry(self.database_path).get(capability.capability_ref),
            capability,
        )

    def test_t10_deprecation_and_supersession_preserve_history(self) -> None:
        version_one = self.registry.register(_capability("software.debug", "1.0.0"))
        version_two = self.registry.register(_capability("software.debug", "2.0.0"))
        deprecated = self.registry.deprecate(
            version_one.capability_ref,
            superseded_by=version_two.capability_ref,
        )

        self.assertTrue(deprecated.deprecated)
        self.assertEqual(deprecated.superseded_by, version_two.capability_ref)
        self.assertEqual(deprecated.contract_sha256, version_one.contract_sha256)
        self.assertEqual(
            self.registry.get(version_two.capability_ref).contract_sha256,
            version_two.contract_sha256,
        )
        history = self.registry.lifecycle_history(version_one.capability_ref)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].event_type, "deprecated")
        self.assertEqual(history[0].superseded_by, version_two.capability_ref)
        self.assertFalse(hasattr(self.registry, "delete"))

    def test_t11_project_preference_cannot_mutate_global_capability(self) -> None:
        global_capability = self.registry.register(_capability("software.debug"))
        project_store = ProjectStore(self.database_path)
        registration = project_store.create_project(
            namespace="alpha",
            display_name="Alpha",
            metadata={"preferred-capability": global_capability.capability_ref.value},
        )
        project_store.update_project(
            registration.access,
            registration.project.project_ref,
            metadata={"preferred-capability": "quantum.simulate@7.4.2"},
        )

        observed = self.registry.get(global_capability.capability_ref)
        self.assertEqual(observed, global_capability)
        self.assertEqual(observed.contract_sha256, global_capability.contract_sha256)
        self.assertNotIn("project", CapabilityRegistry.register.__annotations__)

    def test_t12_identical_registration_is_idempotent_and_restart_durable(self) -> None:
        capability = _capability("browser.navigate")
        first = self.registry.register(capability)
        duplicate = _capability("browser.navigate")
        second = self.registry.register(duplicate)

        self.assertEqual(first, second)
        self.assertEqual(first.created_at, second.created_at)
        self.assertEqual(
            CapabilityRegistry(self.database_path).get(first.capability_ref),
            first,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM capabilities WHERE capability_id = ? AND version = ?",
                (first.capability_id, first.version),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)

    def test_t13_malformed_and_nonexistent_identity_fails_closed(self) -> None:
        invalid_refs = (
            ("software", "1.0.0"),
            ("Software.Debug", "1.0.0"),
            ("software..debug", "1.0.0"),
            ("software.debug", "1"),
            ("software.debug", "01.0.0"),
            ("software.debug", "1.0.0.0"),
        )
        for capability_id, version in invalid_refs:
            with self.subTest(capability_id=capability_id, version=version):
                with self.assertRaises(CapabilityContractError):
                    CapabilityRef(capability_id, version)

        missing = CapabilityRef("software.missing", "1.0.0")
        with self.assertRaises(CapabilityNotFoundError):
            self.registry.get(missing)

    def test_t14_concurrent_conflicting_registration_has_one_winner(self) -> None:
        barrier = threading.Barrier(2)
        candidates = (
            _capability("robotics.plan", description="Contract A"),
            _capability("robotics.plan", description="Contract B"),
        )

        def attempt(candidate: Capability) -> tuple[str, str]:
            registry = CapabilityRegistry(self.database_path)
            barrier.wait(timeout=5)
            try:
                registered = registry.register(candidate)
            except CapabilityConflictError:
                return ("conflict", candidate.contract_sha256)
            return ("registered", registered.contract_sha256)

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(attempt, candidates))

        self.assertEqual([status for status, _ in outcomes].count("registered"), 1)
        self.assertEqual([status for status, _ in outcomes].count("conflict"), 1)
        winner = self.registry.get(CapabilityRef("robotics.plan", "1.0.0"))
        self.assertIn(winner.contract_sha256, {item.contract_sha256 for item in candidates})
        self.assertEqual(
            CapabilityRegistry(self.database_path).get(winner.capability_ref),
            winner,
        )

    def test_atomic_failure_rolls_back_inserted_capability(self) -> None:
        failing_path = Path(self.temp_dir.name) / "failing.sqlite3"
        registry = _FailingCapabilityRegistry(failing_path)
        capability = _capability("biology.sequence-analyze")

        with self.assertRaises(RuntimeError):
            registry.register(capability)
        connection = sqlite3.connect(failing_path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM capabilities").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)

    def test_durable_contract_tampering_fails_integrity_verification(self) -> None:
        capability = self.registry.register(_capability("software.debug"))
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER capabilities_no_update")
            connection.execute(
                "UPDATE capabilities SET description = ? WHERE capability_id = ? AND version = ?",
                ("tampered", capability.capability_id, capability.version),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(CapabilityIntegrityError):
            self.registry.get(capability.capability_ref)

    def test_append_only_sqlite_guards_reject_history_rewrite_and_delete(self) -> None:
        version_one = self.registry.register(_capability("software.debug", "1.0.0"))
        version_two = self.registry.register(_capability("software.debug", "2.0.0"))
        self.registry.deprecate(
            version_one.capability_ref,
            superseded_by=version_two.capability_ref,
        )
        connection = sqlite3.connect(self.database_path)
        guarded_mutations = (
            (
                "UPDATE capabilities SET created_at = ? "
                "WHERE capability_id = ? AND version = ?",
                (
                    "2030-01-01T00:00:00+00:00",
                    version_one.capability_id,
                    version_one.version,
                ),
            ),
            (
                "UPDATE capability_lifecycle SET superseded_by_version = ? "
                "WHERE capability_id = ? AND version = ?",
                (
                    version_one.version,
                    version_one.capability_id,
                    version_one.version,
                ),
            ),
            (
                "DELETE FROM capability_lifecycle "
                "WHERE capability_id = ? AND version = ?",
                (version_one.capability_id, version_one.version),
            ),
            (
                "DELETE FROM capabilities WHERE capability_id = ? AND version = ?",
                (version_two.capability_id, version_two.version),
            ),
        )
        try:
            for statement, parameters in guarded_mutations:
                with self.subTest(statement=statement):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(statement, parameters)
                    connection.rollback()
        finally:
            connection.close()
        self.assertEqual(
            self.registry.get(version_one.capability_ref).superseded_by,
            version_two.capability_ref,
        )

    def test_record_digest_detects_valid_timestamp_rewrite_if_guard_is_removed(self) -> None:
        capability = self.registry.register(_capability("software.debug"))
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER capabilities_no_update")
            connection.execute(
                "UPDATE capabilities SET created_at = ? "
                "WHERE capability_id = ? AND version = ?",
                (
                    "2030-01-01T00:00:00+00:00",
                    capability.capability_id,
                    capability.version,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(CapabilityIntegrityError):
            self.registry.get(capability.capability_ref)

    def test_lifecycle_digest_and_successor_existence_detect_tampering(self) -> None:
        version_one = self.registry.register(_capability("software.debug", "1.0.0"))
        version_two = self.registry.register(_capability("software.debug", "2.0.0"))
        version_three = self.registry.register(_capability("software.debug", "3.0.0"))
        self.registry.deprecate(
            version_one.capability_ref,
            superseded_by=version_two.capability_ref,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER capability_lifecycle_no_update")
            connection.execute(
                "UPDATE capability_lifecycle SET superseded_by_version = ? "
                "WHERE capability_id = ? AND version = ?",
                (
                    version_three.version,
                    version_one.capability_id,
                    version_one.version,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(CapabilityIntegrityError):
            self.registry.get(version_one.capability_ref)

        missing_successor_path = Path(self.temp_dir.name) / "missing-successor.sqlite3"
        missing_successor_registry = CapabilityRegistry(missing_successor_path)
        predecessor = missing_successor_registry.register(
            _capability("render.frame", "1.0.0")
        )
        successor = missing_successor_registry.register(
            _capability("render.frame", "2.0.0")
        )
        missing_successor_registry.deprecate(
            predecessor.capability_ref,
            superseded_by=successor.capability_ref,
        )
        connection = sqlite3.connect(missing_successor_path)
        try:
            connection.execute("DROP TRIGGER capabilities_no_delete")
            connection.execute(
                "DELETE FROM capabilities WHERE capability_id = ? AND version = ?",
                (successor.capability_id, successor.version),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(CapabilityIntegrityError):
            missing_successor_registry.get(predecessor.capability_ref)

    def test_capability_module_has_no_project_quarantine_or_runtime_availability_dependency(self) -> None:
        source = (ROOT / "src/minitz_os/engine/capability.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        forbidden_modules = {
            "minitz.migration",
            "minitz.project",
            "minitz.runtime",
            "migration",
            "project",
            "runtime",
        }
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                self.assertTrue(
                    all(alias.name not in forbidden_modules for alias in node.names)
                )
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, forbidden_modules)


if __name__ == "__main__":
    unittest.main()
