from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

from minitz_os.engine.artifact import (
    Artifact,
    ArtifactAuthorityError,
    ArtifactConflictError,
    ArtifactContentError,
    ArtifactDerivation,
    ArtifactIntegrityError,
    ArtifactRepresentation,
    ArtifactRef,
    ArtifactScopeError,
    ArtifactService,
    ContentRef,
    SourceRef,
    StorageLocation,
)
from minitz_os.engine.object_store import ContentLocation, MemoryObjectStorageBackend, ReplicaState
from minitz_os.engine.capability import Capability, CapabilityRef, CapabilityRegistry
from minitz_os.engine.migration import QuarantineRef
from minitz_os.engine.project import Project, ProjectAccess, ProjectRef, ProjectStore
from minitz_os.engine.run import RunService
from minitz_os.engine.runtime import ArtifactRef as RuntimeArtifactRef
from minitz_os.engine.task import Task, TaskIntegrityError, TaskRevisionService


ROOT = Path(__file__).resolve().parents[1]


class ArtifactIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "minitz.sqlite3"
        self.projects = ProjectStore(self.database_path)
        self.capabilities = CapabilityRegistry(self.database_path)
        self.tasks = TaskRevisionService(self.database_path)
        self.runs = RunService(self.database_path)
        self.artifacts = ArtifactService(self.database_path)
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
        self.capability_ref = self.capabilities.register(
            Capability(
                CapabilityRef("artifact.produce", "1.0.0"),
                "Produce an exact logical Artifact",
            )
        ).capability_ref
        self.task = self._create_task("artifact-task")
        self.content = ContentRef.from_bytes(b"same bytes", media_type="text/plain")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_task(self, idempotency_key: str) -> Task:
        return self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key=idempotency_key,
            task_type="artifact.produce",
            objective="Produce an exact Artifact",
            required_capabilities=(self.capability_ref,),
            input_refs=(),
            output_contract={},
            constraints={},
            side_effect_authority="CANDIDATE_WRITE",
            data_policy_ref=None,
            egress_policy_ref=None,
            evidence_requirements=(),
            acceptance_criteria=(),
            resource_hints={},
        )

    def _create_artifact(
        self,
        *,
        access: ProjectAccess | None = None,
        project: Project | None = None,
        content_ref: ContentRef | None = None,
        role: str = "document.source",
        source_refs: tuple[SourceRef, ...] = (),
        source_artifact_refs: tuple[ArtifactRef, ...] = (),
        source_content_refs: tuple[ContentRef, ...] = (),
    ) -> Artifact:
        selected_access = self.alpha_access if access is None else access
        selected_project = self.alpha if project is None else project
        return self.artifacts.create_artifact(
            selected_access,
            project_ref=selected_project.project_ref,
            role=role,
            content_ref=self.content if content_ref is None else content_ref,
            source_refs=source_refs,
            source_artifact_refs=source_artifact_refs,
            source_content_refs=source_content_refs,
            derivation_type="artifact.derived",
            metadata={},
        )

    def _location(self, label: str, content_ref: ContentRef | None = None) -> ContentLocation:
        content = self.content if content_ref is None else content_ref
        return ContentLocation(
            backend_id="memory",
            locator=f"memory://shared/{label}",
            content_digest=content.digest,
            size_bytes=content.size_bytes,
            created_at="2026-08-28T00:00:00+00:00",
        )

    def test_t01_content_ref_is_exact_sha256_size_and_media_type(self) -> None:
        expected = hashlib.sha256(b"same bytes").hexdigest()
        self.assertEqual(self.content.algorithm, "sha256")
        self.assertEqual(self.content.digest, expected)
        self.assertEqual(self.content.size_bytes, len(b"same bytes"))
        self.assertEqual(self.content.media_type, "text/plain")
        self.content.verify(b"same bytes")
        differently_annotated = ContentRef.from_bytes(
            b"same bytes",
            media_type="application/octet-stream",
        )
        self.assertEqual(self.content, differently_annotated)
        self.assertEqual(self.content.value, differently_annotated.value)

    def test_t02_changed_bytes_change_content_ref(self) -> None:
        changed = ContentRef.from_bytes(b"changed bytes", media_type="text/plain")
        self.assertNotEqual(self.content, changed)
        self.assertNotEqual(self.content.digest, changed.digest)

    def test_t03_same_content_has_distinct_logical_artifacts(self) -> None:
        first = self._create_artifact()
        second = self._create_artifact()
        self.assertNotEqual(first.artifact_ref, second.artifact_ref)
        self.assertEqual(first.content_ref, second.content_ref)
        assert first.content_ref is not None
        self.assertNotEqual(first.artifact_id, first.content_ref.digest)

    def test_t04_same_content_across_projects_preserves_authorization(self) -> None:
        alpha = self._create_artifact()
        beta = self._create_artifact(access=self.beta_access, project=self.beta)
        self.assertEqual(alpha.content_ref, beta.content_ref)
        self.assertNotEqual(alpha.artifact_ref, beta.artifact_ref)
        with self.assertRaises(ArtifactScopeError):
            self.artifacts.get_artifact(self.beta_access, alpha.artifact_ref)
        with self.assertRaises(ArtifactScopeError):
            self.artifacts.get_artifact(self.alpha_access, beta.artifact_ref)

    def test_t05_cross_project_sources_and_derivations_fail_privately(self) -> None:
        beta = self._create_artifact(access=self.beta_access, project=self.beta)
        foreign_source = SourceRef.git(
            self.beta.project_ref,
            repository="https://example.invalid/beta.git",
            commit="a" * 40,
            tree="b" * 40,
        )
        with self.assertRaises(ArtifactScopeError) as caught:
            self._create_artifact(source_artifact_refs=(beta.artifact_ref,))
        self.assertNotIn(self.beta.project_ref.value, str(caught.exception))
        with self.assertRaises(ArtifactScopeError):
            self._create_artifact(source_refs=(foreign_source,))

    def test_t06_derivation_chain_preserves_exact_sources(self) -> None:
        source = self._create_artifact(role="document.editable")
        git_source = SourceRef.git(
            self.alpha.project_ref,
            repository="https://example.invalid/source.git",
            commit="c" * 40,
            tree="d" * 40,
        )
        exported = self._create_artifact(
            role="document.export",
            source_artifact_refs=(source.artifact_ref,),
            source_content_refs=(source.content_ref,),  # type: ignore[arg-type]
            source_refs=(git_source,),
        )
        derivations = self.artifacts.list_derivations(
            self.alpha_access,
            exported.artifact_ref,
        )
        self.assertEqual(len(derivations), 1)
        derivation = derivations[0]
        self.assertIsInstance(derivation, ArtifactDerivation)
        self.assertEqual(derivation.output_ref, exported.artifact_ref)
        self.assertEqual(derivation.source_artifact_refs, (source.artifact_ref,))
        self.assertEqual(derivation.source_content_refs, (source.content_ref,))
        self.assertEqual(derivation.source_refs, (git_source,))

    def test_t07_new_revision_preserves_old_content_and_provenance(self) -> None:
        source = self._create_artifact(role="document.editable")
        revision_one = self._create_artifact(
            source_artifact_refs=(source.artifact_ref,),
        )
        changed = ContentRef.from_bytes(b"revision two", media_type="text/plain")
        revision_two = self.artifacts.create_revision(
            self.alpha_access,
            prior_ref=revision_one.artifact_ref,
            role=revision_one.role,
            content_ref=changed,
            source_refs=revision_one.source_refs,
            source_artifact_refs=revision_one.source_artifact_refs,
            source_content_refs=revision_one.source_content_refs,
            derivation_type="artifact.revised",
            metadata=revision_one.metadata,
        )
        self.assertEqual(revision_two.artifact_id, revision_one.artifact_id)
        self.assertEqual(revision_two.revision, 2)
        self.assertEqual(
            self.artifacts.get_artifact(self.alpha_access, revision_one.artifact_ref),
            revision_one,
        )
        self.assertEqual(revision_one.content_ref, self.content)
        self.assertEqual(revision_two.content_ref, changed)

    def test_t08_exact_git_source_round_trips(self) -> None:
        source = SourceRef.git(
            self.alpha.project_ref,
            repository="https://example.invalid/repo.git",
            commit="1" * 40,
            tree="2" * 40,
        )
        artifact = self._create_artifact(source_refs=(source,))
        restarted = ArtifactService(self.database_path)
        observed = restarted.get_artifact(self.alpha_access, artifact.artifact_ref)
        self.assertEqual(observed.source_refs, (source,))
        revision = source.exact_revision
        assert revision is not None
        self.assertIn("1" * 40, revision)
        self.assertIn("2" * 40, revision)

    def test_t08_file_database_and_remote_source_variants_are_exact(self) -> None:
        file_source = SourceRef.file(
            self.alpha.project_ref,
            locator="file:///workspace/input.txt",
            content_ref=self.content,
        )
        database_source = SourceRef.database(
            self.alpha.project_ref,
            locator="database://inventory/orders",
            revision="transaction:0000000000000042",
        )
        remote_source = SourceRef.remote_object(
            self.alpha.project_ref,
            locator="https://example.invalid/object",
            retrieved_at="2026-08-28T01:02:03+00:00",
        )
        self.assertEqual(file_source.content_ref, self.content)
        self.assertEqual(database_source.exact_revision, "transaction:0000000000000042")
        self.assertEqual(remote_source.retrieved_at, "2026-08-28T01:02:03+00:00")
        artifact = self._create_artifact(
            source_refs=(file_source, database_source, remote_source),
        )
        self.assertEqual(
            ArtifactService(self.database_path).get_artifact(
                self.alpha_access,
                artifact.artifact_ref,
            ).source_refs,
            tuple(
                sorted(
                    (file_source, database_source, remote_source),
                    key=lambda item: item.canonical_digest,
                )
            ),
        )

    def test_t09_mutable_branch_or_path_alone_is_rejected(self) -> None:
        for locator in (
            "https://example.invalid/repo.git#main",
            "file:///mutable/latest.txt",
        ):
            with self.subTest(locator=locator):
                with self.assertRaises(ArtifactContentError):
                    SourceRef(
                        project_ref=self.alpha.project_ref,
                        source_kind="source.mutable",
                        locator=locator,
                        exact_revision=None,
                        content_ref=None,
                        retrieved_at=None,
                    )
        with self.assertRaises(ArtifactContentError):
            SourceRef(
                project_ref=self.alpha.project_ref,
                source_kind="git.repository",
                locator="https://example.invalid/repo.git",
                exact_revision="main",
                content_ref=None,
                retrieved_at=None,
            )

    def test_t10_quarantine_cannot_masquerade_as_active_identity(self) -> None:
        quarantine = QuarantineRef(
            raw_sha256=self.content.digest,
            source_locator="fixture://quarantine",
            source_type="text/plain",
            source_manifest_identity=None,
            byte_size=self.content.size_bytes,
            acquisition_time="2026-08-28T00:00:00+00:00",
            immutable_metadata={},
        )
        self.assertNotIsInstance(quarantine, (ArtifactRef, ContentRef, SourceRef))
        with self.assertRaises(ArtifactContentError):
            self.artifacts.create_artifact(
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                role="document.source",
                content_ref=quarantine,  # type: ignore[arg-type]
                source_refs=(),
                source_artifact_refs=(),
                source_content_refs=(),
                derivation_type="artifact.derived",
                metadata={},
            )

    def test_t11_storage_location_is_not_artifact_or_content_identity(self) -> None:
        artifact_fields = {field.name for field in fields(Artifact)}
        content_fields = {field.name for field in fields(ContentRef)}
        prohibited = {"path", "filename", "storage_uri", "bucket", "object_key"}
        self.assertTrue(artifact_fields.isdisjoint(prohibited))
        self.assertTrue(content_fields.isdisjoint(prohibited))
        self.assertEqual(
            ContentRef.from_bytes(b"same bytes", media_type="text/plain"),
            self.content,
        )
        for key in (
            "path",
            "file_path",
            "location",
            "storage.uri",
            "source_url",
            "object_key",
            "directory",
            "mount_point",
            "storagepath",
        ):
            with self.subTest(key=key):
                with self.assertRaises(ArtifactContentError):
                    self.artifacts.create_artifact(
                        self.alpha_access,
                        project_ref=self.alpha.project_ref,
                        role="document.source",
                        content_ref=self.content,
                        source_refs=(), source_artifact_refs=(), source_content_refs=(),
                        derivation_type="artifact.derived",
                        metadata={key: "physical-location"},
                    )
        semantic = self.artifacts.create_artifact(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            role="document.source",
            content_ref=self.content,
            source_refs=(), source_artifact_refs=(), source_content_refs=(),
            derivation_type="artifact.derived",
            metadata={"schema_ref": "schema://document/v1"},
        )
        self.assertEqual(semantic.metadata["schema_ref"], "schema://document/v1")

    def test_t11_conflicting_media_annotations_cannot_destabilize_provenance(self) -> None:
        alternate = ContentRef.from_bytes(
            b"same bytes",
            media_type="application/octet-stream",
        )
        self.assertEqual(self.content, alternate)
        for source_contents in (
            (self.content, alternate),
            (alternate, self.content),
        ):
            with self.subTest(source_contents=source_contents):
                with self.assertRaises(ArtifactContentError):
                    self._create_artifact(source_content_refs=source_contents)

    def test_t12_task_input_binds_exact_authorized_artifact_identity(self) -> None:
        artifact = self._create_artifact()
        task_input = self.artifacts.create_task_input_ref(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            identity=artifact.artifact_ref,
        )
        task = self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key="artifact-task-input",
            task_type="artifact.consume",
            objective="Consume exact Artifact revision",
            required_capabilities=(self.capability_ref,),
            input_refs=(task_input,),
            output_contract={}, constraints={}, side_effect_authority="READ_ONLY",
            data_policy_ref=None, egress_policy_ref=None,
            evidence_requirements=(), acceptance_criteria=(), resource_hints={},
        )
        self.assertEqual(task.input_refs[0].source_ref, artifact.artifact_ref.value)
        self.assertEqual(task.input_refs[0].content_sha256, self.content.digest)

    def test_t12_all_exact_identity_forms_survive_task_restart(self) -> None:
        source = SourceRef.git(
            self.alpha.project_ref,
            repository="https://example.invalid/task-input.git",
            commit="7" * 40,
            tree="8" * 40,
        )
        artifact = self._create_artifact(source_refs=(source,))
        inputs = tuple(
            self.artifacts.create_task_input_ref(
                self.alpha_access,
                project_ref=self.alpha.project_ref,
                identity=identity,
            )
            for identity in (artifact.artifact_ref, source, self.content)
        )
        task = self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key="all-exact-task-inputs",
            task_type="artifact.consume",
            objective="Consume exact Artifact, Source, and Content identities",
            required_capabilities=(self.capability_ref,),
            input_refs=inputs,
            output_contract={}, constraints={}, side_effect_authority="READ_ONLY",
            data_policy_ref=None, egress_policy_ref=None,
            evidence_requirements=(), acceptance_criteria=(), resource_hints={},
        )
        self.assertEqual({item.input_kind for item in task.input_refs}, {"artifact", "source", "content"})
        restarted = TaskRevisionService(self.database_path)
        self.assertEqual(restarted.get_task(self.alpha_access, task.task_ref), task)

    def test_t12_active_identity_bridge_deletion_is_detected_on_task_read(self) -> None:
        artifact = self._create_artifact()
        task_input = self.artifacts.create_task_input_ref(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            identity=artifact.artifact_ref,
        )
        task = self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key="tampered-artifact-task-input",
            task_type="artifact.consume",
            objective="Detect a missing exact identity bridge",
            required_capabilities=(self.capability_ref,),
            input_refs=(task_input,),
            output_contract={}, constraints={}, side_effect_authority="READ_ONLY",
            data_policy_ref=None, egress_policy_ref=None,
            evidence_requirements=(), acceptance_criteria=(), resource_hints={},
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER artifact_task_inputs_no_delete")
            connection.execute(
                "DELETE FROM artifact_task_input_bindings WHERE project_id = ? AND record_id = ?",
                (self.alpha.project_ref.value, task_input.record_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(TaskIntegrityError):
            self.tasks.get_task(self.alpha_access, task.task_ref)

    def test_t13_current_run_authority_publishes_exact_output(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://producer",
            lease_seconds=10,
        )
        artifact = self.artifacts.publish_from_run(
            self.alpha_access,
            producer_attempt=attempt,
            expected_task_ref=self.task.task_ref,
            expected_task_digest=self.task.canonical_digest,
            role="build.output",
            content_ref=self.content,
            source_refs=(), source_artifact_refs=(), source_content_refs=(),
            derivation_type="run.output",
            metadata={},
        )
        self.assertEqual(artifact.producer_run_ref, run.run_ref)
        self.assertEqual(artifact.producer_attempt_id, attempt.attempt_id)
        self.assertEqual(artifact.producer_fence, attempt.fence)

    def test_t14_stale_fence_and_task_mismatch_cannot_publish(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        old = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://producer-a",
            lease_seconds=0.04,
        )
        time.sleep(0.08)
        current = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://producer-b",
            lease_seconds=10,
        )
        with self.assertRaises(ArtifactAuthorityError):
            self.artifacts.publish_from_run(
                self.alpha_access,
                producer_attempt=old,
                expected_task_ref=self.task.task_ref,
                expected_task_digest=self.task.canonical_digest,
                role="build.output", content_ref=self.content,
                source_refs=(), source_artifact_refs=(), source_content_refs=(),
                derivation_type="run.output", metadata={},
            )
        with self.assertRaises(ArtifactAuthorityError):
            self.artifacts.publish_from_run(
                self.alpha_access,
                producer_attempt=current,
                expected_task_ref=self.task.task_ref,
                expected_task_digest="0" * 64,
                role="build.output", content_ref=self.content,
                source_refs=(), source_artifact_refs=(), source_content_refs=(),
                derivation_type="run.output", metadata={},
            )

    def test_t14_publication_and_cancellation_are_one_atomic_authority_race(self) -> None:
        run = self.runs.create_run(self.alpha_access, task_ref=self.task.task_ref)
        attempt = self.runs.acquire_run_lease(
            self.alpha_access,
            run.run_ref,
            owner_ref="executor://racing-producer",
            lease_seconds=10,
        )
        barrier = threading.Barrier(2)

        def publish() -> str:
            barrier.wait(timeout=5)
            try:
                self.artifacts.publish_from_run(
                    self.alpha_access,
                    producer_attempt=attempt,
                    expected_task_ref=self.task.task_ref,
                    expected_task_digest=self.task.canonical_digest,
                    role="build.output", content_ref=self.content,
                    source_refs=(), source_artifact_refs=(), source_content_refs=(),
                    derivation_type="run.output", metadata={},
                )
            except ArtifactAuthorityError:
                return "rejected-after-cancellation"
            return "published-before-cancellation"

        def cancel() -> str:
            barrier.wait(timeout=5)
            self.runs.request_run_cancellation(self.alpha_access, run.run_ref)
            return "cancelled"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(
                future.result()
                for future in (
                    executor.submit(publish),
                    executor.submit(cancel),
                )
            )
        self.assertIn(outcomes[0], {"published-before-cancellation", "rejected-after-cancellation"})
        self.assertEqual(outcomes[1], "cancelled")
        self.assertEqual(self.runs.get_run(self.alpha_access, run.run_ref).status, "CANCELLED")
        connection = sqlite3.connect(self.database_path)
        try:
            published_count = connection.execute(
                "SELECT COUNT(*) FROM artifact_revisions WHERE project_id = ? AND producer_run_id = ?",
                (self.alpha.project_ref.value, run.run_id),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(
            published_count,
            1 if outcomes[0] == "published-before-cancellation" else 0,
        )

    def test_t15_digest_size_and_expected_content_mismatch_fail(self) -> None:
        with self.assertRaises(ArtifactContentError):
            self.content.verify(b"other bytes")
        with self.assertRaises(ArtifactContentError):
            ContentRef(
                algorithm="sha256",
                digest=self.content.digest,
                size_bytes=-1,
                media_type="text/plain",
            )

    def test_t16_guards_tamper_and_fault_roll_back(self) -> None:
        provenance = SourceRef.git(
            self.alpha.project_ref,
            repository="https://example.invalid/guarded.git",
            commit="5" * 40,
            tree="6" * 40,
        )
        artifact = self._create_artifact(source_refs=(provenance,))
        connection = sqlite3.connect(self.database_path)
        try:
            for table in ("artifact_revisions", "artifact_derivations"):
                with self.subTest(table=table, operation="update"):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"UPDATE {table} SET record_sha256 = ?", ("0" * 64,))
                    connection.rollback()
                with self.subTest(table=table, operation="delete"):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(f"DELETE FROM {table}")
                    connection.rollback()
            connection.execute("DROP TRIGGER artifact_revisions_no_update")
            connection.execute(
                "UPDATE artifact_revisions SET role = ? WHERE project_id = ? AND artifact_id = ? AND revision = ?",
                ("tampered.role", self.alpha.project_ref.value, artifact.artifact_id, artifact.revision),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ArtifactIntegrityError):
            self.artifacts.get_artifact(self.alpha_access, artifact.artifact_ref)

        fresh = ArtifactService(Path(self.temp_dir.name) / "fault.sqlite3")
        project = fresh.projects.create_project(namespace="fault", display_name="Fault")
        connection = sqlite3.connect(fresh.database_path)
        try:
            connection.executescript(
                """
                CREATE TRIGGER fail_artifact_derivation
                BEFORE INSERT ON artifact_derivations
                BEGIN SELECT RAISE(ABORT, 'injected derivation fault'); END;
                """
            )
        finally:
            connection.close()
        source = SourceRef.git(
            project.project.project_ref,
            repository="https://example.invalid/fault.git",
            commit="e" * 40,
            tree="f" * 40,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            fresh.create_artifact(
                project.access,
                project_ref=project.project.project_ref,
                role="fault.output", content_ref=self.content,
                source_refs=(source,), source_artifact_refs=(), source_content_refs=(),
                derivation_type="artifact.derived", metadata={},
            )
        check = sqlite3.connect(fresh.database_path)
        try:
            self.assertEqual(check.execute("SELECT COUNT(*) FROM artifact_revisions").fetchone()[0], 0)
            self.assertEqual(check.execute("SELECT COUNT(*) FROM artifact_heads").fetchone()[0], 0)
        finally:
            check.close()

    def test_t16_deleted_source_artifact_invalidates_derived_provenance(self) -> None:
        source = self._create_artifact(role="document.editable")
        derived = self._create_artifact(source_artifact_refs=(source.artifact_ref,))
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER artifact_revisions_no_delete")
            connection.execute(
                "DELETE FROM artifact_revisions WHERE project_id = ? AND artifact_id = ? AND revision = ?",
                (
                    source.project_ref.value,
                    source.artifact_id,
                    source.revision,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ArtifactIntegrityError):
            self.artifacts.get_artifact(self.alpha_access, derived.artifact_ref)

    def test_t16_tampered_artifact_fails_through_exact_task_bridge(self) -> None:
        artifact = self._create_artifact()
        task_input = self.artifacts.create_task_input_ref(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            identity=artifact.artifact_ref,
        )
        task = self.tasks.create_task(
            self.alpha_access,
            project_ref=self.alpha.project_ref,
            idempotency_key="tampered-artifact-record-task-input",
            task_type="artifact.consume",
            objective="Reject a tampered exact Artifact record",
            required_capabilities=(self.capability_ref,),
            input_refs=(task_input,),
            output_contract={}, constraints={}, side_effect_authority="READ_ONLY",
            data_policy_ref=None, egress_policy_ref=None,
            evidence_requirements=(), acceptance_criteria=(), resource_hints={},
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER artifact_revisions_no_update")
            connection.execute(
                "UPDATE artifact_revisions SET role = ? WHERE project_id = ? AND artifact_id = ? AND revision = ?",
                (
                    "tampered.role",
                    artifact.project_ref.value,
                    artifact.artifact_id,
                    artifact.revision,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ArtifactIntegrityError):
            self.artifacts.get_artifact(self.alpha_access, artifact.artifact_ref)
        with self.assertRaises(TaskIntegrityError):
            self.tasks.get_task(self.alpha_access, task.task_ref)

    def test_t17_restart_preserves_artifacts_sources_and_derivations(self) -> None:
        source = SourceRef.git(
            self.alpha.project_ref,
            repository="https://example.invalid/restart.git",
            commit="3" * 40,
            tree="4" * 40,
        )
        artifact = self._create_artifact(source_refs=(source,))
        restarted = ArtifactService(self.database_path)
        self.assertEqual(restarted.get_artifact(self.alpha_access, artifact.artifact_ref), artifact)
        self.assertEqual(len(restarted.list_derivations(self.alpha_access, artifact.artifact_ref)), 1)

    def test_t18_no_storage_provider_hardware_or_domain_kernel_coupling(self) -> None:
        self.assertIs(RuntimeArtifactRef, ArtifactRef)
        source = (ROOT / "src/minitz_os/engine/artifact.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name != "minitz.migration" for alias in node.names))
            elif isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "migration")
        prohibited = {"provider", "gpu", "bucket", "object_key", "game_engine"}
        self.assertTrue({field.name for field in fields(Artifact)}.isdisjoint(prohibited))

    def test_t19_backend_location_is_the_representation_storage_location(self) -> None:
        backend = MemoryObjectStorageBackend()
        content = backend.put(b"backend bytes", media_type="text/plain")
        artifact = self._create_artifact(content_ref=content)
        location = backend.location(content)
        self.assertIsInstance(location, StorageLocation)
        representation = self.artifacts.publish_representation(
            self.alpha_access, artifact_ref=artifact.artifact_ref,
            role="runtime", platform="linux", consumer="viewer", scope="project",
            content_ref=content, storage_locations=(location,),
        )
        self.assertEqual(representation.storage_locations, (location,))
        restarted = ArtifactService(self.database_path)
        persisted = restarted.get_current_representation(
            self.alpha_access, artifact.artifact_ref, role="runtime",
            platform="linux", consumer="viewer", scope="project",
        )
        self.assertIsInstance(persisted.storage_locations[0], ContentLocation)
        self.assertIs(persisted.storage_locations[0].state, ReplicaState.AVAILABLE)
        self.assertEqual(persisted.storage_locations, (location,))

    def test_t19_representation_heads_are_independent_by_all_key_dimensions(self) -> None:
        artifact = self._create_artifact()
        dimensions = (
            ("preview", "linux", "viewer", "project"),
            ("preview", "windows", "viewer", "project"),
            ("preview", "linux", "editor", "project"),
            ("preview", "linux", "viewer", "task-42"),
        )
        published = {
            key: self.artifacts.publish_representation(
                self.alpha_access,
                artifact_ref=artifact.artifact_ref,
                role=key[0],
                platform=key[1],
                consumer=key[2],
                scope=key[3],
                content_ref=self.content,
                storage_locations=(self._location("shared"),),
            )
            for key in dimensions
        }

        heads = self.artifacts.list_representation_heads(
            self.alpha_access, artifact.artifact_ref
        )
        self.assertEqual(len(heads), len(dimensions))
        self.assertEqual(
            {(head.role, head.platform, head.consumer, head.scope) for head in heads},
            set(dimensions),
        )
        for key, representation in published.items():
            with self.subTest(key=key):
                current = self.artifacts.get_current_representation(
                    self.alpha_access,
                    artifact.artifact_ref,
                    role=key[0], platform=key[1], consumer=key[2], scope=key[3],
                )
                self.assertIsInstance(current, ArtifactRepresentation)
                self.assertEqual(current.representation_ref, representation.representation_ref)

    def test_t20_rejected_representation_is_immutable_history_not_current(self) -> None:
        artifact = self._create_artifact()
        first = self.artifacts.publish_representation(
            self.alpha_access,
            artifact_ref=artifact.artifact_ref,
            role="preview", platform="linux", consumer="viewer", scope="project",
            content_ref=self.content, storage_locations=(self._location("v1"),),
        )
        changed = ContentRef.from_bytes(b"rejected bytes", media_type="text/plain")
        rejected = self.artifacts.publish_representation(
            self.alpha_access,
            artifact_ref=artifact.artifact_ref,
            role="preview", platform="linux", consumer="viewer", scope="project",
            content_ref=changed, storage_locations=(self._location("rejected", changed),),
            status="REJECTED",
        )
        self.assertEqual(rejected.revision, 2)
        self.assertEqual(
            self.artifacts.get_current_representation(
                self.alpha_access, artifact.artifact_ref,
                role="preview", platform="linux", consumer="viewer", scope="project",
            ),
            first,
        )
        third = self.artifacts.publish_representation(
            self.alpha_access,
            artifact_ref=artifact.artifact_ref,
            role="preview", platform="linux", consumer="viewer", scope="project",
            content_ref=changed, storage_locations=(self._location("v3", changed),),
        )
        self.assertEqual(third.revision, 3)
        self.assertEqual(
            [item.revision for item in self.artifacts.list_representations(
                self.alpha_access, artifact.artifact_ref,
            )],
            [1, 2, 3],
        )
        self.assertEqual(
            [head.representation_ref.revision for head in self.artifacts.list_representation_heads(
                self.alpha_access, artifact.artifact_ref,
            )],
            [1, 3],
        )
        connection = sqlite3.connect(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE artifact_representations SET status = 'ACCEPTED'"
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM artifact_representations")
            connection.rollback()
        finally:
            connection.close()

    def test_t21_shared_content_and_location_keep_project_authorization_distinct(self) -> None:
        alpha_artifact = self._create_artifact()
        beta_artifact = self._create_artifact(
            access=self.beta_access, project=self.beta,
        )
        location = self._location("same-object")
        alpha_representation = self.artifacts.publish_representation(
            self.alpha_access,
            artifact_ref=alpha_artifact.artifact_ref,
            role="preview", platform="linux", consumer="viewer", scope="project",
            content_ref=self.content, storage_locations=(location,),
        )
        beta_representation = self.artifacts.publish_representation(
            self.beta_access,
            artifact_ref=beta_artifact.artifact_ref,
            role="preview", platform="linux", consumer="viewer", scope="project",
            content_ref=self.content, storage_locations=(location,),
        )
        self.assertEqual(alpha_representation.content_ref, beta_representation.content_ref)
        self.assertEqual(alpha_representation.storage_locations, beta_representation.storage_locations)
        self.assertNotEqual(alpha_representation.representation_ref, beta_representation.representation_ref)
        with self.assertRaises(ArtifactScopeError):
            self.artifacts.get_representation(self.beta_access, alpha_representation.representation_ref)
        with self.assertRaises(ArtifactScopeError):
            self.artifacts.get_current_representation(
                self.alpha_access, beta_artifact.artifact_ref,
                role="preview", platform="linux", consumer="viewer", scope="project",
            )

    def test_t22_representation_and_head_digests_detect_tampering(self) -> None:
        artifact = self._create_artifact()
        representation = self.artifacts.publish_representation(
            self.alpha_access,
            artifact_ref=artifact.artifact_ref,
            role="tamper", platform="linux", consumer="viewer", scope="project",
            content_ref=self.content, storage_locations=(self._location("tamper"),),
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER artifact_representations_no_update")
            connection.execute(
                "UPDATE artifact_representations SET role = 'tampered' "
                "WHERE project_id = ? AND artifact_id = ? AND artifact_revision = ?",
                (artifact.project_ref.value, artifact.artifact_id, artifact.revision),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ArtifactIntegrityError):
            self.artifacts.get_representation(
                self.alpha_access, representation.representation_ref,
            )

        head_artifact = self._create_artifact()
        head_representation = self.artifacts.publish_representation(
            self.alpha_access,
            artifact_ref=head_artifact.artifact_ref,
            role="head-tamper", platform="linux", consumer="viewer", scope="project",
            content_ref=self.content, storage_locations=(self._location("head"),),
        )
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("DROP TRIGGER artifact_representation_heads_no_update")
            connection.execute(
                "UPDATE artifact_representation_heads SET record_sha256 = ? "
                "WHERE project_id = ? AND artifact_id = ? AND artifact_revision = ?",
                (
                    "0" * 64,
                    head_artifact.project_ref.value,
                    head_artifact.artifact_id,
                    head_artifact.revision,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ArtifactIntegrityError):
            self.artifacts.get_current_representation(
                self.alpha_access, head_representation.artifact_ref,
                role="head-tamper", platform="linux", consumer="viewer", scope="project",
            )

    def test_concurrent_conflicting_revision_has_one_winner(self) -> None:
        artifact = self._create_artifact()
        barrier = threading.Barrier(2)

        def revise(payload: bytes) -> str:
            barrier.wait(timeout=5)
            try:
                self.artifacts.create_revision(
                    self.alpha_access,
                    prior_ref=artifact.artifact_ref,
                    role=artifact.role,
                    content_ref=ContentRef.from_bytes(payload, media_type="text/plain"),
                    source_refs=(), source_artifact_refs=(), source_content_refs=(),
                    derivation_type="artifact.revised", metadata={},
                )
            except ArtifactConflictError:
                return "conflict"
            return "created"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(revise, (b"left", b"right")))
        self.assertEqual(outcomes.count("created"), 1)
        self.assertEqual(outcomes.count("conflict"), 1)

    def test_concurrent_independent_artifact_creation_both_complete(self) -> None:
        barrier = threading.Barrier(2)

        def create(payload: bytes) -> ArtifactRef:
            barrier.wait(timeout=5)
            artifact = self._create_artifact(
                content_ref=ContentRef.from_bytes(payload, media_type="text/plain")
            )
            return artifact.artifact_ref

        with ThreadPoolExecutor(max_workers=2) as executor:
            refs = tuple(executor.map(create, (b"independent-left", b"independent-right")))
        self.assertEqual(len(set(refs)), 2)
        self.assertTrue(
            all(
                self.artifacts.get_artifact(self.alpha_access, artifact_ref).artifact_ref
                == artifact_ref
                for artifact_ref in refs
            )
        )


if __name__ == "__main__":
    unittest.main()
