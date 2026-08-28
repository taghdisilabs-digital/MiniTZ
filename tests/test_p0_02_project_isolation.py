from __future__ import annotations

import ast
from dataclasses import fields
import hashlib
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from biella.migration import QuarantineRef
from biella.project import (
    Project,
    ProjectAccess,
    ProjectConflictError,
    ProjectCreationError,
    ProjectNamespaceError,
    ProjectRef,
    ProjectRetentionError,
    ProjectScopeError,
    ProjectScoped,
    ProjectStore,
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _record_id(value: str) -> str:
    return f"rec_{_sha256(value)[:32]}"


def _configuration_ref(value: str) -> str:
    return f"config://sha256/{_sha256(value)}"


class _FailingRootProjectStore(ProjectStore):
    def _insert_required_roots(
        self,
        connection: sqlite3.Connection,
        project_ref: ProjectRef,
    ) -> None:
        super()._insert_required_roots(connection, project_ref)
        raise RuntimeError("injected root creation failure")


class _FailingAccessProjectStore(ProjectStore):
    def _insert_project_access(
        self,
        connection: sqlite3.Connection,
        access: ProjectAccess,
        created_at: str,
    ) -> None:
        super()._insert_project_access(connection, access, created_at)
        raise RuntimeError("injected access creation failure")


class ProjectIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "projects.sqlite3"
        self.store = ProjectStore(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_alpha_beta(
        self,
    ) -> tuple[Project, ProjectAccess, Project, ProjectAccess]:
        alpha_registration = self.store.create_project(
            namespace="alpha",
            display_name="Project Alpha",
            metadata={"owner": "alpha-team"},
            configuration_refs={"default": _configuration_ref("alpha")},
        )
        beta_registration = self.store.create_project(
            namespace="beta",
            display_name="Project Beta",
            metadata={"owner": "beta-team"},
            configuration_refs={"default": _configuration_ref("beta")},
        )
        return (
            alpha_registration.project,
            alpha_registration.access,
            beta_registration.project,
            beta_registration.access,
        )

    def _scoped_record(
        self,
        project: Project,
        *,
        name: str = "shared-name",
        digest_seed: str = "shared-content",
    ) -> ProjectScoped:
        return ProjectScoped(
            project_ref=project.project_ref,
            record_id=_record_id(name),
            content_sha256=_sha256(digest_seed),
        )

    def _project_count(self) -> int:
        connection = sqlite3.connect(self.database_path)
        try:
            return int(connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])
        finally:
            connection.close()

    def test_t01_alpha_beta_have_unique_stable_ids_and_namespaces(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()

        self.assertIsInstance(alpha.project_ref, ProjectRef)
        self.assertIsInstance(beta.project_ref, ProjectRef)
        self.assertNotEqual(alpha.project_ref, beta.project_ref)
        self.assertEqual({alpha.namespace, beta.namespace}, {"alpha", "beta"})
        self.assertNotEqual(alpha.artifact_namespace, beta.artifact_namespace)
        self.assertEqual(
            self.store.get_project(alpha_access, alpha.project_ref),
            alpha,
        )
        self.assertEqual(
            self.store.get_project(beta_access, beta.project_ref),
            beta,
        )

    def test_t02_duplicate_namespace_is_rejected(self) -> None:
        alpha_registration = self.store.create_project(
            namespace="alpha",
            display_name="Alpha",
        )
        with self.assertRaises(ProjectConflictError):
            self.store.create_project(namespace="alpha", display_name="Other Alpha")
        self.assertEqual(
            [
                project.namespace
                for project in self.store.list_projects(alpha_registration.access)
            ],
            ["alpha"],
        )

    def test_t03_malformed_and_reserved_namespaces_are_rejected(self) -> None:
        invalid_namespaces = (
            "",
            "A",
            "Alpha",
            "-alpha",
            "alpha-",
            "alpha_beta",
            "alpha--beta",
            "quarantine",
            "migration-quarantine",
            "a" * 64,
        )
        for namespace in invalid_namespaces:
            with self.subTest(namespace=namespace):
                with self.assertRaises(ProjectNamespaceError):
                    self.store.create_project(
                        namespace=namespace,
                        display_name="Invalid",
                    )
        self.assertEqual(self._project_count(), 0)

    def test_t04_scoped_persistence_requires_project_identity(self) -> None:
        alpha_registration = self.store.create_project(
            namespace="alpha",
            display_name="Alpha",
        )
        alpha = alpha_registration.project
        record = self._scoped_record(alpha)
        with self.assertRaises(TypeError):
            self.store.put_scoped_record(None, record)  # type: ignore[arg-type]

        connection = sqlite3.connect(self.database_path)
        try:
            columns = {
                row[1]: row
                for row in connection.execute("PRAGMA table_info(project_scoped_records)")
            }
            self.assertEqual(columns["project_id"][3], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO project_scoped_records "
                    "(project_id, record_id, content_sha256) VALUES (NULL, ?, ?)",
                    (record.record_id, record.content_sha256),
                )
        finally:
            connection.close()

    def test_t05_beta_cannot_read_alpha_record_by_known_id(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        alpha_record = self._scoped_record(alpha)
        self.store.put_scoped_record(alpha_access, alpha_record)

        with self.assertRaises(ProjectScopeError) as caught:
            self.store.read_scoped_record(beta_access, alpha_record)
        self.assertEqual(str(caught.exception), "Project scope mismatch")
        self.assertNotIn(alpha.namespace, str(caught.exception))
        self.assertNotIn(alpha.project_ref.value, str(caught.exception))

    def test_t06_beta_cannot_write_or_update_alpha_record(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        alpha_record = self._scoped_record(alpha)
        with self.assertRaises(ProjectScopeError):
            self.store.put_scoped_record(beta_access, alpha_record)

        self.store.put_scoped_record(alpha_access, alpha_record)
        changed = ProjectScoped(
            project_ref=alpha.project_ref,
            record_id=alpha_record.record_id,
            content_sha256=_sha256("changed"),
        )
        with self.assertRaises(ProjectScopeError):
            self.store.put_scoped_record(beta_access, changed)
        self.assertEqual(
            self.store.read_scoped_record(alpha_access, alpha_record).content_sha256,
            alpha_record.content_sha256,
        )

    def test_t07_beta_cannot_delete_alpha_record(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        alpha_record = self._scoped_record(alpha)
        self.store.put_scoped_record(alpha_access, alpha_record)

        with self.assertRaises(ProjectScopeError):
            self.store.delete_scoped_record(beta_access, alpha_record)
        self.assertEqual(
            self.store.read_scoped_record(alpha_access, alpha_record),
            alpha_record,
        )

    def test_t08_alpha_reference_cannot_bind_to_beta_scope(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        alpha_record = self._scoped_record(alpha)
        with self.assertRaises(ProjectScopeError):
            self.store.bind_scoped_record(beta_access, alpha_record)

    def test_t09_beta_cannot_resolve_alpha_configuration(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        with self.assertRaises(ProjectScopeError):
            self.store.resolve_configuration(
                beta_access,
                alpha.project_ref,
                "default",
            )
        self.assertEqual(
            self.store.resolve_configuration(
                alpha_access,
                alpha.project_ref,
                "default",
            ),
            _configuration_ref("alpha"),
        )

    def test_t10_beta_cannot_use_alpha_artifact_namespace(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        with self.assertRaises(ProjectScopeError):
            self.store.resolve_artifact_namespace(
                beta_access,
                alpha.project_ref,
            )
        self.assertEqual(
            self.store.resolve_artifact_namespace(
                alpha_access,
                alpha.project_ref,
            ),
            alpha.artifact_namespace,
        )

    def test_t11_shared_digest_does_not_collapse_authorization(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        alpha_record = self._scoped_record(alpha, name="asset")
        beta_record = self._scoped_record(beta, name="asset")
        self.assertEqual(alpha_record.record_id, beta_record.record_id)
        self.assertEqual(alpha_record.content_sha256, beta_record.content_sha256)

        self.store.put_scoped_record(alpha_access, alpha_record)
        self.store.put_scoped_record(beta_access, beta_record)
        self.assertEqual(
            self.store.read_scoped_record(alpha_access, alpha_record).project_ref,
            alpha.project_ref,
        )
        self.assertEqual(
            self.store.read_scoped_record(beta_access, beta_record).project_ref,
            beta.project_ref,
        )

    def test_t12_quarantine_is_not_a_project_or_project_scoped_record(self) -> None:
        quarantine_ref = QuarantineRef(
            raw_sha256="0" * 64,
            source_locator="fixture://quarantine",
            source_type="text/plain",
            source_manifest_identity=None,
            byte_size=0,
            acquisition_time="2026-08-28T00:00:00+00:00",
            immutable_metadata={},
        )
        with self.assertRaises(TypeError):
            ProjectScoped(
                project_ref=quarantine_ref,  # type: ignore[arg-type]
                record_id=_record_id("quarantine"),
                content_sha256="0" * 64,
            )
        with self.assertRaises(ProjectNamespaceError):
            self.store.create_project(
                namespace="quarantine",
                display_name="Quarantine",
            )
        self.assertEqual(self._project_count(), 0)

        project_source = (ROOT / "src/biella/project.py").read_text(encoding="utf-8")
        syntax = ast.parse(project_source)
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                self.assertFalse(
                    any(alias.name.startswith("biella.migration") for alias in node.names)
                )
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse(
                    node.module == "biella.migration"
                    or (node.level > 0 and node.module == "migration")
                    or (
                        node.module == "biella"
                        and any(alias.name == "migration" for alias in node.names)
                    )
                    or (
                        node.level > 0
                        and node.module is None
                        and any(alias.name == "migration" for alias in node.names)
                    )
                )

    def test_t13_metadata_update_preserves_project_identity(self) -> None:
        alpha_registration = self.store.create_project(
            namespace="alpha",
            display_name="Alpha",
            metadata={"revision": "one"},
        )
        alpha = alpha_registration.project
        updated = self.store.update_project(
            alpha_registration.access,
            alpha.project_ref,
            display_name="Alpha Renamed",
            metadata={"revision": "two"},
            configuration_refs={"default": _configuration_ref("updated")},
        )
        self.assertEqual(updated.project_ref, alpha.project_ref)
        self.assertEqual(updated.namespace, alpha.namespace)
        self.assertEqual(updated.created_at, alpha.created_at)
        self.assertEqual(updated.display_name, "Alpha Renamed")
        self.assertEqual(updated.metadata, {"revision": "two"})
        self.assertEqual(
            updated.configuration_refs,
            {"default": _configuration_ref("updated")},
        )

    def test_t14_injected_creation_failure_rolls_back_all_project_rows(self) -> None:
        failure_stores = (
            (
                Path(self.temp_dir.name) / "failing-roots.sqlite3",
                _FailingRootProjectStore,
            ),
            (
                Path(self.temp_dir.name) / "failing-access.sqlite3",
                _FailingAccessProjectStore,
            ),
        )
        for failing_database, store_type in failure_stores:
            with self.subTest(store_type=store_type.__name__):
                failing_store = store_type(failing_database)
                with self.assertRaises(ProjectCreationError):
                    failing_store.create_project(
                        namespace="alpha",
                        display_name="Alpha",
                    )
                connection = sqlite3.connect(failing_database)
                try:
                    project_count = connection.execute(
                        "SELECT COUNT(*) FROM projects"
                    ).fetchone()[0]
                    root_count = connection.execute(
                        "SELECT COUNT(*) FROM project_roots"
                    ).fetchone()[0]
                    access_count = connection.execute(
                        "SELECT COUNT(*) FROM project_access"
                    ).fetchone()[0]
                finally:
                    connection.close()
                self.assertEqual(project_count, 0)
                self.assertEqual(root_count, 0)
                self.assertEqual(access_count, 0)

    def test_t15_restart_preserves_alpha_beta_and_required_roots(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        restarted = ProjectStore(self.database_path)
        self.assertEqual(
            restarted.get_project(alpha_access, alpha.project_ref),
            alpha,
        )
        self.assertEqual(
            restarted.get_project(beta_access, beta.project_ref),
            beta,
        )

        script = """
import sys
from pathlib import Path
from biella.project import ProjectAccess, ProjectRef, ProjectStore
store = ProjectStore(Path(sys.argv[1]))
project_ref = ProjectRef(sys.argv[2])
access = ProjectAccess(project_ref, sys.argv[3])
print(store.get_project(access, project_ref).namespace)
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(self.database_path),
                alpha.project_ref.value,
                alpha_access.token,
            ],
            check=True,
            cwd=ROOT,
            env={"PYTHONPATH": str(SRC)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.stdout.strip(), "alpha")

        connection = sqlite3.connect(self.database_path)
        try:
            roots = connection.execute(
                "SELECT root_kind FROM project_roots WHERE project_id = ? ORDER BY root_kind",
                (alpha.project_ref.value,),
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(roots, [("artifact",), ("configuration",)])

    def test_t16_deletion_restricts_records_then_removes_roots_atomically(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        record = self._scoped_record(alpha)
        beta_record = self._scoped_record(beta)
        self.assertEqual(record.record_id, beta_record.record_id)
        self.assertEqual(record.content_sha256, beta_record.content_sha256)
        self.store.put_scoped_record(alpha_access, record)
        self.store.put_scoped_record(beta_access, beta_record)
        with self.assertRaises(ProjectRetentionError):
            self.store.delete_project(alpha_access, alpha.project_ref)

        self.assertEqual(
            self.store.read_scoped_record(alpha_access, record),
            record,
        )
        self.store.delete_scoped_record(alpha_access, record)
        self.store.delete_project(alpha_access, alpha.project_ref)
        with self.assertRaises(ProjectScopeError):
            self.store.get_project(alpha_access, alpha.project_ref)
        self.assertEqual(
            self.store.get_project(beta_access, beta.project_ref),
            beta,
        )
        self.assertEqual(
            self.store.read_scoped_record(beta_access, beta_record),
            beta_record,
        )
        self.assertEqual(self.store.list_projects(beta_access), (beta,))

        connection = sqlite3.connect(self.database_path)
        try:
            orphan_roots = connection.execute(
                "SELECT COUNT(*) FROM project_roots WHERE project_id = ?",
                (alpha.project_ref.value,),
            ).fetchone()[0]
            beta_roots = connection.execute(
                "SELECT COUNT(*) FROM project_roots WHERE project_id = ?",
                (beta.project_ref.value,),
            ).fetchone()[0]
            foreign_key_failures = connection.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            connection.close()
        self.assertEqual(orphan_roots, 0)
        self.assertEqual(beta_roots, 2)
        self.assertEqual(foreign_key_failures, [])

    def test_foreign_project_id_cannot_be_reconstructed_as_authority(self) -> None:
        alpha, alpha_access, beta, beta_access = self._create_alpha_beta()
        alpha_record = self._scoped_record(alpha)
        self.store.put_scoped_record(alpha_access, alpha_record)
        forged_alpha_access = ProjectAccess(alpha.project_ref, beta_access.token)

        attacks = (
            lambda: self.store.list_projects(forged_alpha_access),
            lambda: self.store.get_project(forged_alpha_access, alpha.project_ref),
            lambda: self.store.update_project(
                forged_alpha_access,
                alpha.project_ref,
                display_name="Compromised",
            ),
            lambda: self.store.resolve_configuration(
                forged_alpha_access,
                alpha.project_ref,
                "default",
            ),
            lambda: self.store.resolve_artifact_namespace(
                forged_alpha_access,
                alpha.project_ref,
            ),
            lambda: self.store.bind_scoped_record(forged_alpha_access, alpha_record),
            lambda: self.store.put_scoped_record(forged_alpha_access, alpha_record),
            lambda: self.store.read_scoped_record(forged_alpha_access, alpha_record),
            lambda: self.store.delete_scoped_record(forged_alpha_access, alpha_record),
            lambda: self.store.delete_project(forged_alpha_access, alpha.project_ref),
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                with self.assertRaises(ProjectScopeError) as caught:
                    attack()
                self.assertEqual(str(caught.exception), "Project scope mismatch")
                self.assertNotIn(alpha.project_ref.value, str(caught.exception))

        with self.assertRaises(TypeError):
            self.store.get_project(
                ProjectRef(alpha.project_ref.value),  # type: ignore[arg-type]
                alpha.project_ref,
            )
        self.assertEqual(
            self.store.read_scoped_record(alpha_access, alpha_record),
            alpha_record,
        )
        self.assertEqual(
            self.store.get_project(alpha_access, alpha.project_ref).display_name,
            "Project Alpha",
        )
        self.assertEqual(self.store.list_projects(beta_access), (beta,))
        self.assertNotIn(alpha_access.token, repr(alpha_access))
        self.assertNotIn(
            alpha_access.token.encode("utf-8"),
            self.database_path.read_bytes(),
        )

    def test_project_primitive_has_no_domain_provider_or_hardware_fields(self) -> None:
        field_names = {field.name for field in fields(Project)}
        prohibited = {
            "engine",
            "model",
            "provider",
            "gpu",
            "game_mode",
            "agent",
            "legacy_donor",
            "drive",
            "repository_provider",
        }
        self.assertTrue(field_names.isdisjoint(prohibited))


if __name__ == "__main__":
    unittest.main()
