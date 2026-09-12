from __future__ import annotations

import importlib
import json
from pathlib import Path
import tempfile
import unittest

from biella.isolated_runtime import RuntimeRef
from biella.project import ProjectStore
from biella.workspace import WorkspaceRef

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/biella/isolation_family.py"


def family_module():
    if not MODULE.is_file():
        raise AssertionError("MiniTZ isolation family is not implemented")
    return importlib.import_module("biella.isolation_family")


def cell_records(project_ref: str, project_id: str = "customer-a") -> tuple[dict, dict, dict]:
    run_id = "run_" + "2" * 32
    checkpoint_id = "chk_" + "3" * 32
    manifest = {
        "schema": "biella.project_cell_manifest/v1", "project_id": project_id,
        "workspace_root": f"/srv/project-sandboxes/{project_id}/workspace",
        "project_memory_namespace": f"project-cell://{project_id}/memory",
        "run_memory_namespace": f"project-cell://{project_id}/runs",
        "engine_binding": {
            "project_ref": project_ref,
            "task_ref": f"task://{project_ref}/tsk_{'1' * 32}/1",
            "task_digest": "a" * 64,
            "run_ref": f"run://{project_ref}/{run_id}",
        },
    }
    envelope = {
        "schema": "biella.task_envelope/v1", "project_id": project_id,
        "run_id": run_id, "task_id": "UNVERIFIED", "objective": "UNVERIFIED",
        "current_checkpoint_id": checkpoint_id,
        "forbidden_scope": {"cross_project_cells": True, "credentials_in_remote_context": True},
    }
    pointer = {
        "schema": "biella.project_cell_checkpoint_pointer/v1", "project_id": project_id,
        "checkpoint_id": checkpoint_id, "checkpoint_sha256": "b" * 64,
        "path": f"/state/{project_id}/checkpoints/{checkpoint_id}.json",
    }
    return manifest, envelope, pointer


class IsolationFamilyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def registered(self, namespace: str = "customer-a"):
        database = self.root / "engine.sqlite3"
        registration = ProjectStore(database).create_project(namespace=namespace, display_name=namespace)
        return database, registration

    def test_family_module_exists_as_attachment_not_controller(self) -> None:
        mod = family_module()
        self.assertFalse(mod.IsolationFamilyService.progression_authority)
        self.assertFalse(hasattr(mod.IsolationFamilyService, "advance_task"))
        self.assertFalse(hasattr(mod.IsolationFamilyService, "complete_task"))

    def test_preserves_distinct_workspace_runtime_and_project_cell_layers(self) -> None:
        mod = family_module(); database, registration = self.registered()
        project_ref = registration.project.project_ref
        manifest, envelope, pointer = cell_records(project_ref.value)
        cell = mod.ProjectCellIsolationBinding.from_records(
            manifest, envelope, pointer, manifest_sha256="c" * 64, task_envelope_sha256="d" * 64,
        )
        workspaces = (
            WorkspaceRef(project_ref, "wsp_" + "1" * 32),
            WorkspaceRef(project_ref, "wsp_" + "2" * 32),
        )
        runtimes = (
            RuntimeRef(project_ref, "rt_" + "4" * 32, 1),
            RuntimeRef(project_ref, "rt_" + "5" * 32, 3),
        )
        receipt = mod.IsolationFamilyService(database).attach(
            registration.access, workspace_refs=workspaces, runtime_refs=runtimes,
            project_cells=(cell,), evidence_refs=("evidence://unify-10/live-cell-readback",),
            idempotency_key="unify-10-family",
        )
        self.assertEqual(receipt.project_ref, project_ref)
        self.assertEqual(receipt.project_namespace, "customer-a")
        self.assertEqual(receipt.workspace_refs, workspaces)
        self.assertEqual(receipt.runtime_refs, runtimes)
        self.assertEqual(receipt.project_cells, (cell,))
        self.assertFalse(receipt.progression_authority)
        self.assertFalse(receipt.execution_authority)

    def test_unverified_cell_task_identity_stays_unverified(self) -> None:
        mod = family_module(); _database, registration = self.registered()
        manifest, envelope, pointer = cell_records(registration.project.project_ref.value)
        cell = mod.ProjectCellIsolationBinding.from_records(
            manifest, envelope, pointer, manifest_sha256="c" * 64, task_envelope_sha256="d" * 64,
        )
        self.assertEqual(cell.task_identity_state, "UNVERIFIED")
        self.assertEqual(cell.cell_task_id, "UNVERIFIED")
        self.assertTrue(cell.native_task_ref.endswith("/1"))
        self.assertNotIn("UNVERIFIED", cell.native_task_ref)
        self.assertEqual(cell.checkpoint_id, pointer["checkpoint_id"])
        self.assertEqual(cell.checkpoint_sha256, pointer["checkpoint_sha256"])

    def test_cross_project_layers_fail_closed(self) -> None:
        mod = family_module(); database = self.root / "engine.sqlite3"
        alpha = ProjectStore(database).create_project(namespace="alpha", display_name="Alpha")
        beta = ProjectStore(database).create_project(namespace="beta", display_name="Beta")
        with self.assertRaisesRegex(mod.IsolationFamilyScopeError, "Project"):
            mod.IsolationFamilyService(database).attach(
                alpha.access,
                workspace_refs=(WorkspaceRef(beta.project.project_ref, "wsp_" + "7" * 32),),
                idempotency_key="cross-project",
            )

    def test_cell_namespace_must_match_native_project_namespace(self) -> None:
        mod = family_module(); database, registration = self.registered("native-a")
        manifest, envelope, pointer = cell_records(registration.project.project_ref.value, "different-cell")
        cell = mod.ProjectCellIsolationBinding.from_records(
            manifest, envelope, pointer, manifest_sha256="c" * 64, task_envelope_sha256="d" * 64,
        )
        with self.assertRaisesRegex(mod.IsolationFamilyScopeError, "namespace"):
            mod.IsolationFamilyService(database).attach(
                registration.access, project_cells=(cell,), idempotency_key="namespace-mismatch"
            )

    def test_project_cell_binding_rejects_secret_material_and_scope_weakening(self) -> None:
        mod = family_module(); _database, registration = self.registered()
        manifest, envelope, pointer = cell_records(registration.project.project_ref.value)
        hostile = json.loads(json.dumps(manifest)); hostile["token"] = "raw-secret-value"
        with self.assertRaisesRegex(mod.IsolationFamilyContractError, "secret"):
            mod.ProjectCellIsolationBinding.from_records(
                hostile, envelope, pointer, manifest_sha256="c" * 64, task_envelope_sha256="d" * 64,
            )
        weak = json.loads(json.dumps(envelope)); weak["forbidden_scope"]["cross_project_cells"] = False
        with self.assertRaisesRegex(mod.IsolationFamilyAuthorityError, "cross-project"):
            mod.ProjectCellIsolationBinding.from_records(
                manifest, weak, pointer, manifest_sha256="c" * 64, task_envelope_sha256="d" * 64,
            )

    def test_attachment_is_idempotent_and_immutable(self) -> None:
        mod = family_module(); database, registration = self.registered()
        service = mod.IsolationFamilyService(database)
        workspace = WorkspaceRef(registration.project.project_ref, "wsp_" + "8" * 32)
        first = service.attach(
            registration.access, workspace_refs=(workspace,),
            evidence_refs=("evidence://unify-10/workspace",), idempotency_key="same-family",
        )
        second = service.attach(
            registration.access, workspace_refs=(workspace,),
            evidence_refs=("evidence://unify-10/workspace",), idempotency_key="same-family",
        )
        self.assertEqual(second, first)
        with self.assertRaisesRegex(mod.IsolationFamilyConflictError, "idempotency"):
            service.attach(
                registration.access,
                runtime_refs=(RuntimeRef(registration.project.project_ref, "rt_" + "9" * 32, 1),),
                evidence_refs=("evidence://unify-10/runtime",), idempotency_key="same-family",
            )

    def test_public_runtime_exports_isolation_family(self) -> None:
        import biella
        mod = family_module()
        self.assertIs(biella.IsolationFamilyService, mod.IsolationFamilyService)
        self.assertIs(biella.ProjectCellIsolationBinding, mod.ProjectCellIsolationBinding)
        self.assertIn("IsolationFamilyService", biella.__all__)
        self.assertIn("ProjectCellIsolationBinding", biella.__all__)


if __name__ == "__main__":
    unittest.main()
