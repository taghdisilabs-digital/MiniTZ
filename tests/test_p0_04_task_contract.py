from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
import hashlib
import math
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

from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.migration import QuarantineRef
from minitz_os.engine.project import Project, ProjectAccess, ProjectScoped, ProjectStore
from minitz_os.engine.task import (
    Task,
    TaskConflictError,
    TaskContractError,
    TaskInputError,
    TaskInputRef,
    TaskIntegrityError,
    TaskRef,
    TaskRevisionService,
    TaskScopeError,
    TaskSideEffectError,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _record_id(value: str) -> str:
    return f"rec_{_sha256(value)[:32]}"


def _schema_ref(value: str) -> str:
    return f"schema://sha256/{_sha256(value)}"


class TaskContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "minitz.sqlite3"
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        alpha_registration = self.projects.create_project(
            namespace="alpha",
            display_name="Alpha",
        )
        beta_registration = self.projects.create_project(
            namespace="beta",
            display_name="Beta",
        )
        self.alpha = alpha_registration.project
        self.alpha_access = alpha_registration.access
        self.beta = beta_registration.project
        self.beta_access = beta_registration.access
        self.debug_ref = self._register_capability("software.debug")
        self.model_ref = self._register_capability("3d.model")
        self.alpha_input = self._create_input(self.alpha, self.alpha_access, "alpha-source")
        self.beta_input = self._create_input(self.beta, self.beta_access, "beta-source")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _register_capability(self, capability_id: str) -> CapabilityRef:
        return self.capabilities.register(
            Capability(
                CapabilityRef(capability_id, "1.0.0"),
                f"Semantic contract for {capability_id}",
            )
        ).capability_ref

    def _create_input(
        self,
        project: Project,
        access: ProjectAccess,
        name: str,
    ) -> TaskInputRef:
        record = ProjectScoped(
            project.project_ref,
            _record_id(name),
            _sha256(name),
        )
        self.projects.put_scoped_record(access, record)
        return TaskInputRef.from_project_scoped(record, input_kind="content")

    def _create_task(
        self,
        *,
        access: ProjectAccess | None = None,
        project: Project | None = None,
        idempotency_key: str = "task-alpha-001",
        task_type: str = "production.transform",
        objective: str = "Produce a verified candidate",
        capabilities: tuple[CapabilityRef, ...] | None = None,
        inputs: tuple[TaskInputRef, ...] | None = None,
        output_contract: dict[str, str] | None = None,
        constraints: dict[str, str | int | float | bool | None] | None = None,
        side_effect_authority: str = "CANDIDATE_WRITE",
        evidence_requirements: tuple[str, ...] = ("tests.pass",),
        acceptance_criteria: tuple[str, ...] = ("candidate.verified",),
        resource_hints: dict[str, str | int | float | bool | None] | None = None,
    ) -> Task:
        selected_project = self.alpha if project is None else project
        selected_access = self.alpha_access if access is None else access
        return self.tasks.create_task(
            selected_access,
            project_ref=selected_project.project_ref,
            idempotency_key=idempotency_key,
            task_type=task_type,
            objective=objective,
            required_capabilities=(self.debug_ref,) if capabilities is None else capabilities,
            input_refs=(self.alpha_input,) if inputs is None else inputs,
            output_contract=(
                {"candidate": _schema_ref("candidate")}
                if output_contract is None
                else output_contract
            ),
            constraints={} if constraints is None else constraints,
            side_effect_authority=side_effect_authority,
            data_policy_ref=None,
            egress_policy_ref=None,
            evidence_requirements=evidence_requirements,
            acceptance_criteria=acceptance_criteria,
            resource_hints={} if resource_hints is None else resource_hints,
        )

    def test_t01_create_and_read_minimal_valid_task(self) -> None:
        task = self._create_task()
        self.assertIsInstance(task, Task)
        self.assertIsInstance(task.task_ref, TaskRef)
        self.assertEqual(task.revision, 1)
        self.assertEqual(task.project_ref, self.alpha.project_ref)
        self.assertEqual(self.tasks.get_task(self.alpha_access, task.task_ref), task)

    def test_t02_multi_capability_task_uses_exact_versions(self) -> None:
        task = self._create_task(
            capabilities=(self.model_ref, self.debug_ref),
            idempotency_key="multi-capability",
        )
        self.assertEqual(
            task.required_capabilities,
            tuple(sorted((self.debug_ref, self.model_ref))),
        )

    def test_t03_input_binds_exact_authorized_project_record(self) -> None:
        task = self._create_task()
        self.assertEqual(task.input_refs, (self.alpha_input,))
        self.assertEqual(task.input_refs[0].project_ref, self.alpha.project_ref)
        self.assertEqual(task.input_refs[0].content_sha256, _sha256("alpha-source"))

    def test_t04_cross_project_input_binding_fails_privately(self) -> None:
        with self.assertRaises(TaskScopeError) as caught:
            self._create_task(inputs=(self.beta_input,), idempotency_key="cross-input")
        self.assertEqual(str(caught.exception), "Task Project scope mismatch")
        self.assertNotIn(self.beta.project_ref.value, str(caught.exception))

        with self.assertRaises(TaskScopeError):
            self._create_task(
                access=self.beta_access,
                project=self.alpha,
                idempotency_key="foreign-project",
            )

    def test_t05_quarantine_ref_is_rejected_as_active_input(self) -> None:
        quarantine = QuarantineRef(
            raw_sha256="0" * 64,
            source_locator="fixture://quarantine",
            source_type="text/plain",
            source_manifest_identity=None,
            byte_size=0,
            acquisition_time="2026-08-28T00:00:00+00:00",
            immutable_metadata={},
        )
        with self.assertRaises(TaskInputError):
            self.tasks.create_task(
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                idempotency_key="quarantine-input",
                task_type="production.transform",
                objective="Must reject quarantine",
                required_capabilities=(self.debug_ref,),
                input_refs=(quarantine,),  # type: ignore[arg-type]
                output_contract={},
                constraints={},
                side_effect_authority="READ_ONLY",
                data_policy_ref=None,
                egress_policy_ref=None,
                evidence_requirements=(),
                acceptance_criteria=(),
                resource_hints={},
            )

    def test_t06_unknown_capability_ref_is_rejected(self) -> None:
        with self.assertRaises(TaskContractError):
            self._create_task(
                capabilities=(CapabilityRef("unknown.future", "1.0.0"),),
                idempotency_key="unknown-capability",
            )

    def test_t07_canonical_digest_is_stable_for_semantic_set_order(self) -> None:
        first = self._create_task(
            capabilities=(self.debug_ref, self.model_ref),
            evidence_requirements=("tests.pass", "artifact.exists"),
            acceptance_criteria=("quality.met", "candidate.verified"),
            idempotency_key="stable-order",
        )
        duplicate = self._create_task(
            capabilities=(self.model_ref, self.debug_ref),
            evidence_requirements=("artifact.exists", "tests.pass"),
            acceptance_criteria=("candidate.verified", "quality.met"),
            idempotency_key="stable-order",
        )
        self.assertEqual(first.task_ref, duplicate.task_ref)
        self.assertEqual(first.canonical_digest, duplicate.canonical_digest)

    def test_t08_each_material_change_changes_digest(self) -> None:
        base = self._create_task(idempotency_key="digest-base")
        variants = (
            self._create_task(objective="Changed objective", idempotency_key="digest-objective"),
            self._create_task(inputs=(), idempotency_key="digest-input"),
            self._create_task(output_contract={"other": _schema_ref("other")}, idempotency_key="digest-output"),
            self._create_task(side_effect_authority="PROJECT_WRITE", idempotency_key="digest-side-effect"),
            self._create_task(acceptance_criteria=("different",), idempotency_key="digest-acceptance"),
        )
        for variant in variants:
            self.assertNotEqual(base.canonical_digest, variant.canonical_digest)

    def test_t09_revision_two_preserves_revision_one(self) -> None:
        revision_one = self._create_task(idempotency_key="revision-one")
        revision_two = self.tasks.create_revision(
            self.alpha_access,
            prior_ref=revision_one.task_ref,
            idempotency_key="revision-two",
            task_type=revision_one.task_type,
            objective="Materially revised objective",
            required_capabilities=revision_one.required_capabilities,
            input_refs=revision_one.input_refs,
            output_contract=revision_one.output_contract,
            constraints=revision_one.constraints,
            side_effect_authority=revision_one.side_effect_authority,
            data_policy_ref=revision_one.data_policy_ref,
            egress_policy_ref=revision_one.egress_policy_ref,
            evidence_requirements=revision_one.evidence_requirements,
            acceptance_criteria=revision_one.acceptance_criteria,
            resource_hints=revision_one.resource_hints,
        )
        self.assertEqual(revision_two.task_id, revision_one.task_id)
        self.assertEqual(revision_two.revision, 2)
        self.assertNotEqual(revision_two.canonical_digest, revision_one.canonical_digest)
        self.assertEqual(self.tasks.get_task(self.alpha_access, revision_one.task_ref), revision_one)

    def test_t10_structured_fields_round_trip_after_restart(self) -> None:
        task = self._create_task(
            constraints={"quality": 0.95, "timeout-seconds": 120, "required": True},
            resource_hints={"memory-mib": 512, "class": "general"},
            idempotency_key="restart-structured",
        )
        restarted = TaskRevisionService(self.database_path)
        self.assertEqual(restarted.get_task(self.alpha_access, task.task_ref), task)

    def test_t11_identical_idempotent_duplicate_returns_same_revision(self) -> None:
        first = self._create_task(idempotency_key="duplicate")
        second = self._create_task(idempotency_key="duplicate")
        self.assertEqual(first, second)

    def test_t12_conflicting_idempotent_duplicate_fails(self) -> None:
        self._create_task(idempotency_key="conflict")
        with self.assertRaises(TaskConflictError):
            self._create_task(idempotency_key="conflict", objective="Conflicting objective")

    def test_t13_side_effect_escalation_seam_fails_closed(self) -> None:
        task = self._create_task(side_effect_authority="CANDIDATE_WRITE")
        self.tasks.require_side_effect_within(task, "READ_ONLY")
        self.tasks.require_side_effect_within(task, "CANDIDATE_WRITE")
        with self.assertRaises(TaskSideEffectError):
            self.tasks.require_side_effect_within(task, "PROJECT_WRITE")

    def test_t14_software_and_3d_intents_use_same_task_schema(self) -> None:
        software = self._create_task(
            task_type="software.modify",
            objective="Modify exact repository revision and run tests",
            idempotency_key="software-task",
        )
        three_d = self._create_task(
            task_type="3d.asset-transform",
            objective="Modify exact scene and export editable asset",
            capabilities=(self.model_ref,),
            idempotency_key="3d-task",
        )
        self.assertIs(type(software), Task)
        self.assertIs(type(three_d), Task)
        self.assertEqual({field.name for field in fields(software)}, {field.name for field in fields(three_d)})

    def test_t15_task_has_no_provider_topology_or_domain_fields(self) -> None:
        field_names = {field.name for field in fields(Task)}
        prohibited = {
            "provider", "model", "gpu", "worker", "agent", "maker", "critic",
            "reviewer", "validator_chain", "pipeline", "game_engine",
        }
        self.assertTrue(field_names.isdisjoint(prohibited))
        source = (ROOT / "src/minitz_os/engine/task.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                self.assertTrue(
                    all(alias.name != "minitz.migration" for alias in node.names)
                )
            elif isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "migration")

    def test_t16_nonfinite_structured_values_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(TaskContractError):
                    self._create_task(
                        constraints={"invalid": value},
                        idempotency_key=f"nonfinite-{repr(value)}",
                    )

    def test_t17_update_delete_guards_and_record_digest_fail_closed(self) -> None:
        task = self._create_task(idempotency_key="immutability")
        with self.assertRaises(sqlite3.IntegrityError):
            self.projects.put_scoped_record(
                self.alpha_access,
                ProjectScoped(
                    self.alpha.project_ref,
                    self.alpha_input.record_id,
                    _sha256("overwritten-content"),
                ),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.projects.delete_scoped_record(
                self.alpha_access,
                ProjectScoped(
                    self.alpha.project_ref,
                    self.alpha_input.record_id,
                    self.alpha_input.content_sha256,
                ),
            )
        self.assertEqual(
            self.tasks.get_task(self.alpha_access, task.task_ref).input_refs,
            (self.alpha_input,),
        )
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 0)
            connection.execute(
                "UPDATE project_scoped_records SET content_sha256 = ? "
                "WHERE project_id = ? AND record_id = ?",
                (
                    _sha256("raw-fk-off-overwrite"),
                    self.alpha.project_ref.value,
                    self.alpha_input.record_id,
                ),
            )
            connection.commit()
            with self.assertRaises(TaskIntegrityError):
                self.tasks.get_task(self.alpha_access, task.task_ref)
            connection.execute(
                "UPDATE project_scoped_records SET content_sha256 = ? "
                "WHERE project_id = ? AND record_id = ?",
                (
                    self.alpha_input.content_sha256,
                    self.alpha.project_ref.value,
                    self.alpha_input.record_id,
                ),
            )
            connection.commit()
            connection.execute(
                "DELETE FROM project_scoped_records WHERE project_id = ? AND record_id = ?",
                (self.alpha.project_ref.value, self.alpha_input.record_id),
            )
            connection.commit()
            with self.assertRaises(TaskIntegrityError):
                self.tasks.get_task(self.alpha_access, task.task_ref)
            connection.execute(
                "INSERT INTO project_scoped_records "
                "(project_id, record_id, content_sha256) VALUES (?, ?, ?)",
                (
                    self.alpha.project_ref.value,
                    self.alpha_input.record_id,
                    self.alpha_input.content_sha256,
                ),
            )
            connection.commit()
            self.assertEqual(
                self.tasks.get_task(self.alpha_access, task.task_ref).input_refs,
                (self.alpha_input,),
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE task_revisions SET objective = ? WHERE project_id = ? AND task_id = ? AND revision = ?",
                    ("tampered", task.project_ref.value, task.task_id, task.revision),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM task_revisions WHERE project_id = ? AND task_id = ? AND revision = ?",
                    (task.project_ref.value, task.task_id, task.revision),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM task_input_bindings WHERE project_id = ? AND task_id = ? AND revision = ?",
                    (task.project_ref.value, task.task_id, task.revision),
                )
            connection.rollback()
            connection.execute("DROP TRIGGER task_revisions_no_update")
            connection.execute(
                "UPDATE task_revisions SET created_at = ? WHERE project_id = ? AND task_id = ? AND revision = ?",
                ("2030-01-01T00:00:00+00:00", task.project_ref.value, task.task_id, task.revision),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(TaskIntegrityError):
            self.tasks.get_task(self.alpha_access, task.task_ref)

    def test_idempotency_record_tampering_fails_integrity_verification(self) -> None:
        self._create_task(idempotency_key="idempotency-integrity")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER task_idempotency_no_update")
            connection.execute(
                "UPDATE task_idempotency SET canonical_digest = ? "
                "WHERE project_id = ? AND idempotency_key = ?",
                ("0" * 64, self.alpha.project_ref.value, "idempotency-integrity"),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(TaskIntegrityError):
            self._create_task(idempotency_key="idempotency-integrity")

    def test_t18_concurrent_conflicting_submission_has_one_winner(self) -> None:
        barrier = threading.Barrier(2)

        def submit(objective: str) -> str:
            service = TaskRevisionService(self.database_path)
            barrier.wait(timeout=5)
            try:
                service.create_task(
                    self.alpha_access,
                    project_ref=self.alpha.project_ref,
                    idempotency_key="concurrent",
                    task_type="production.transform",
                    objective=objective,
                    required_capabilities=(self.debug_ref,),
                    input_refs=(self.alpha_input,),
                    output_contract={},
                    constraints={},
                    side_effect_authority="READ_ONLY",
                    data_policy_ref=None,
                    egress_policy_ref=None,
                    evidence_requirements=(),
                    acceptance_criteria=(),
                    resource_hints={},
                )
            except TaskConflictError:
                return "conflict"
            return "registered"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(submit, ("Objective A", "Objective B")))
        self.assertEqual(outcomes.count("registered"), 1)
        self.assertEqual(outcomes.count("conflict"), 1)


if __name__ == "__main__":
    unittest.main()
