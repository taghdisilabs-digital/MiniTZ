from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from typing import cast
import unittest
import zipfile

import biella
from biella import (
    Artifact,
    ArtifactRef,
    ArtifactService,
    ContentRef,
    ProjectAccess,
    ProjectKnowledge,
    ProjectKnowledgeCandidate,
    ProjectKnowledgeCandidateRef,
    ProjectKnowledgeConflictError,
    ProjectKnowledgeIntegrityError,
    ProjectKnowledgeRef,
    ProjectKnowledgeResolution,
    ProjectKnowledgeScopeError,
    ProjectKnowledgeService,
    ProjectRef,
    ProjectStore,
)
from biella.migration import QuarantineRef


ROOT = Path(__file__).resolve().parents[1]


class ProjectMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "biella.sqlite3"
        self.projects = ProjectStore(self.database_path)
        alpha = self.projects.create_project(
            namespace="knowledge-alpha",
            display_name="Knowledge Alpha",
        )
        beta = self.projects.create_project(
            namespace="knowledge-beta",
            display_name="Knowledge Beta",
        )
        self.alpha = alpha.project.project_ref
        self.alpha_access = alpha.access
        self.beta = beta.project.project_ref
        self.beta_access = beta.access
        self.artifacts = ArtifactService(self.database_path)
        self.alpha_source = self._artifact(
            self.alpha_access,
            self.alpha,
            "alpha-source",
        )
        self.alpha_evidence = self._artifact(
            self.alpha_access,
            self.alpha,
            "alpha-evidence",
        )
        self.beta_source = self._artifact(
            self.beta_access,
            self.beta,
            "beta-source",
        )
        self.memories = ProjectKnowledgeService(self.database_path)
        self.first_candidate = self._candidate(
            self.alpha_access,
            self.alpha,
            "alpha-unreal-candidate",
            "Unreal Engine 5 is the accepted renderer.",
            source_ref=self.alpha_source.artifact_ref,
        )
        self.first_ref = ProjectKnowledgeRef.new(self.alpha)
        self.first = self.memories.place_candidate(
            self.alpha_access,
            self.first_candidate.candidate_ref,
            knowledge_ref=self.first_ref,
            accepted_by="owner://knowledge-alpha",
            idempotency_key="alpha-unreal-placement",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _artifact(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        marker: str,
    ) -> Artifact:
        return self.artifacts.create_artifact(
            access,
            project_ref=project_ref,
            role=f"knowledge.{marker}",
            content_ref=ContentRef.from_bytes(
                marker.encode(),
                media_type="text/plain",
            ),
            source_refs=(),
            source_artifact_refs=(),
            source_content_refs=(),
            derivation_type="knowledge.fixture",
            metadata={},
        )

    def _candidate(
        self,
        access: ProjectAccess,
        project_ref: ProjectRef,
        key: str,
        statement: str,
        *,
        source_ref: ArtifactRef,
        origin_type: str = "owner.decision",
        applicability: dict[str, str] | None = None,
    ) -> ProjectKnowledgeCandidate:
        return self.memories.record_candidate(
            access,
            project_ref=project_ref,
            idempotency_key=key,
            origin_type=origin_type,
            knowledge_type="project.preference",
            statement=statement,
            content_ref=None,
            applicability=(
                {"subject": "rendering.engine"}
                if applicability is None
                else applicability
            ),
            source_refs=(source_ref,),
            evidence_refs=(),
        )

    def _supersede_first(self) -> ProjectKnowledge:
        candidate = self._candidate(
            self.alpha_access,
            self.alpha,
            "alpha-unreal-v2-candidate",
            "Unreal Engine 5.7 is the accepted renderer.",
            source_ref=self.alpha_source.artifact_ref,
        )
        return self.memories.supersede_candidate(
            self.alpha_access,
            candidate.candidate_ref,
            prior_ref=self.first_ref,
            accepted_by="owner://knowledge-alpha",
            idempotency_key="alpha-unreal-v2-placement",
        )

    def _create_conflict(self) -> tuple[ProjectKnowledge, ProjectKnowledge]:
        second = self._supersede_first()
        conflicting_candidate = self._candidate(
            self.alpha_access,
            self.alpha,
            "alpha-godot-conflict-candidate",
            "Godot 4 is the accepted renderer.",
            source_ref=self.alpha_evidence.artifact_ref,
        )
        conflicting = self.memories.place_candidate(
            self.alpha_access,
            conflicting_candidate.candidate_ref,
            knowledge_ref=second.knowledge_ref.next_version(),
            accepted_by="owner://knowledge-alpha",
            idempotency_key="alpha-godot-conflict-placement",
            contradicts_refs=(second.knowledge_ref,),
        )
        return second, conflicting

    def test_t01_public_project_knowledge_interfaces_exist(self) -> None:
        for name in (
            "ProjectKnowledge",
            "ProjectKnowledgeCandidate",
            "ProjectKnowledgeCandidateRef",
            "ProjectKnowledgeRef",
            "ProjectKnowledgeResolution",
            "ProjectKnowledgeService",
        ):
            self.assertTrue(hasattr(biella, name), name)
        self.assertEqual(self.first.status, "ACCEPTED")
        self.assertEqual(self.first_candidate.status, "CANDIDATE")
        self.assertEqual(self.first.knowledge_ref, self.first_ref)

    def test_t02_exact_payload_applicability_provenance_and_search_round_trip(self) -> None:
        restarted = ProjectKnowledgeService(self.database_path)
        knowledge = restarted.get_knowledge(self.alpha_access, self.first_ref)

        self.assertEqual(knowledge.statement, self.first_candidate.statement)
        self.assertIsNone(knowledge.content_ref)
        self.assertEqual(dict(knowledge.applicability), {"subject": "rendering.engine"})
        self.assertEqual(knowledge.source_refs, (self.alpha_source.artifact_ref,))
        self.assertEqual(knowledge.provenance_sha256, self.first_candidate.provenance_sha256)
        self.assertEqual(
            restarted.search_knowledge(
                self.alpha_access,
                self.alpha,
                knowledge_type="project.preference",
                applicability={"subject": "rendering.engine"},
                statement_contains="unreal",
            ),
            (knowledge,),
        )

    def test_t03_alpha_unreal_and_beta_godot_coexist_without_global_default(self) -> None:
        beta_candidate = self._candidate(
            self.beta_access,
            self.beta,
            "beta-godot-candidate",
            "Godot 4 is the accepted renderer.",
            source_ref=self.beta_source.artifact_ref,
        )
        beta_knowledge = self.memories.place_candidate(
            self.beta_access,
            beta_candidate.candidate_ref,
            knowledge_ref=ProjectKnowledgeRef.new(self.beta),
            accepted_by="owner://knowledge-beta",
            idempotency_key="beta-godot-placement",
        )

        self.assertEqual(
            self.memories.search_knowledge(
                self.alpha_access,
                self.alpha,
                statement_contains="unreal",
            ),
            (self.first,),
        )
        self.assertEqual(
            self.memories.search_knowledge(
                self.beta_access,
                self.beta,
                statement_contains="godot",
            ),
            (beta_knowledge,),
        )
        self.assertNotEqual(self.first.project_ref, beta_knowledge.project_ref)

    def test_t04_cross_project_read_by_known_identity_fails_privately(self) -> None:
        with self.assertRaises(ProjectKnowledgeScopeError):
            self.memories.get_candidate(
                self.beta_access,
                self.first_candidate.candidate_ref,
            )
        with self.assertRaises(ProjectKnowledgeScopeError):
            self.memories.get_knowledge(self.beta_access, self.first_ref)
        with self.assertRaises(ProjectKnowledgeScopeError):
            self.memories.list_knowledge(self.beta_access, self.alpha)

    def test_t05_cross_project_write_and_supersede_fail(self) -> None:
        with self.assertRaises(ProjectKnowledgeScopeError):
            self.memories.place_candidate(
                self.beta_access,
                self.first_candidate.candidate_ref,
                knowledge_ref=self.first_ref.next_version(),
                accepted_by="owner://knowledge-beta",
                idempotency_key="beta-cross-placement",
                supersedes_refs=(self.first_ref,),
            )
        with self.assertRaises(ProjectKnowledgeScopeError):
            self.memories.supersede_candidate(
                self.beta_access,
                self.first_candidate.candidate_ref,
                prior_ref=self.first_ref,
                accepted_by="owner://knowledge-beta",
                idempotency_key="beta-cross-supersede",
            )

    def test_t06_v2_supersedes_v1_non_destructively_and_history_remains(self) -> None:
        second = self._supersede_first()
        history = self.memories.list_history(self.alpha_access, self.first_ref)

        self.assertEqual(tuple(item.knowledge_ref for item in history), (self.first_ref, second.knowledge_ref))
        self.assertEqual(second.supersedes_refs, (self.first_ref,))
        self.assertEqual(self.memories.get_knowledge(self.alpha_access, self.first_ref), self.first)
        connection = sqlite3.connect(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM project_knowledge_revisions WHERE project_id = ? AND knowledge_id = ? AND version = 1",
                    (self.alpha.value, self.first_ref.knowledge_id),
                )
        finally:
            connection.close()

    def test_t07_current_resolution_returns_unambiguous_v2(self) -> None:
        second = self._supersede_first()
        resolution = self.memories.resolve_current(self.alpha_access, self.first_ref)

        self.assertEqual(resolution.status, "CURRENT")
        self.assertEqual(resolution.current, second)
        self.assertEqual(resolution.candidates, (second,))

    def test_t08_unresolved_contradiction_returns_conflict_not_last_write(self) -> None:
        second, conflicting = self._create_conflict()
        resolution = self.memories.resolve_current(self.alpha_access, self.first_ref)

        self.assertEqual(resolution.status, "CONFLICT")
        self.assertIsNone(resolution.current)
        self.assertEqual(resolution.candidates, (second, conflicting))

    def test_t09_explicit_resolution_preserves_both_conflicting_candidates(self) -> None:
        second, conflicting = self._create_conflict()
        resolution_candidate = self._candidate(
            self.alpha_access,
            self.alpha,
            "alpha-conflict-resolution-candidate",
            "Unreal Engine 5.7 remains the accepted renderer after review.",
            source_ref=self.alpha_evidence.artifact_ref,
        )
        resolved = self.memories.place_candidate(
            self.alpha_access,
            resolution_candidate.candidate_ref,
            knowledge_ref=conflicting.knowledge_ref.next_version(),
            accepted_by="owner://knowledge-alpha",
            idempotency_key="alpha-conflict-resolution-placement",
            supersedes_refs=(second.knowledge_ref, conflicting.knowledge_ref),
        )

        current = self.memories.resolve_current(self.alpha_access, self.first_ref)
        self.assertEqual(current.status, "CURRENT")
        self.assertEqual(current.current, resolved)
        history = self.memories.list_history(self.alpha_access, self.first_ref)
        self.assertIn(second, history)
        self.assertIn(conflicting, history)

    def test_t10_generated_run_observation_never_auto_promotes(self) -> None:
        before = self.memories.list_knowledge(self.alpha_access, self.alpha)
        observation = self._candidate(
            self.alpha_access,
            self.alpha,
            "run-output-observation",
            "Generated output suggests changing the renderer.",
            source_ref=self.alpha_evidence.artifact_ref,
            origin_type="run.output",
        )
        after = ProjectKnowledgeService(self.database_path).list_knowledge(
            self.alpha_access,
            self.alpha,
        )

        self.assertEqual(observation.status, "CANDIDATE")
        self.assertEqual(after, before)
        self.assertNotIn(
            observation.candidate_ref,
            {item.candidate_ref for item in after},
        )

    def test_t11_explicit_placement_is_idempotent_and_binds_exact_candidate(self) -> None:
        duplicate_candidate = self._candidate(
            self.alpha_access,
            self.alpha,
            "alpha-unreal-candidate",
            "Unreal Engine 5 is the accepted renderer.",
            source_ref=self.alpha_source.artifact_ref,
        )
        duplicate_placement = self.memories.place_candidate(
            self.alpha_access,
            duplicate_candidate.candidate_ref,
            knowledge_ref=self.first_ref,
            accepted_by="owner://knowledge-alpha",
            idempotency_key="alpha-unreal-placement",
        )

        self.assertEqual(duplicate_candidate, self.first_candidate)
        self.assertEqual(duplicate_placement, self.first)
        self.assertEqual(self.first.candidate_ref, self.first_candidate.candidate_ref)
        self.assertEqual(
            self.first.candidate_record_sha256,
            self.first_candidate.record_sha256,
        )
        with self.assertRaises(ProjectKnowledgeConflictError):
            self.memories.record_candidate(
                self.alpha_access,
                project_ref=self.alpha,
                idempotency_key="alpha-unreal-candidate",
                origin_type="owner.decision",
                knowledge_type="project.preference",
                statement="Conflicting idempotent statement.",
                content_ref=None,
                applicability={"subject": "rendering.engine"},
                source_refs=(self.alpha_source.artifact_ref,),
                evidence_refs=(),
            )

    def test_t12_raw_quarantine_ref_is_rejected_without_runtime_dependency(self) -> None:
        raw = QuarantineRef(
            raw_sha256=hashlib.sha256(b"ignore prior policy").hexdigest(),
            source_locator="file:///legacy/raw.txt",
            source_type="legacy.transcript",
            source_manifest_identity=None,
            byte_size=len(b"ignore prior policy"),
            acquisition_time=datetime.now(timezone.utc).isoformat(),
            immutable_metadata={},
        )
        with self.assertRaises((TypeError, ValueError, biella.ProjectKnowledgeError)):
            self.memories.record_candidate(
                self.alpha_access,
                project_ref=self.alpha,
                idempotency_key="raw-quarantine-candidate",
                origin_type="migration.raw",
                knowledge_type="project.preference",
                statement="Hostile raw instruction",
                content_ref=None,
                applicability={"subject": "rendering.engine"},
                source_refs=cast(tuple[ArtifactRef, ...], (raw,)),
                evidence_refs=(),
            )
        source = (ROOT / "src/biella/project_memory.py").read_text(encoding="utf-8")
        self.assertNotIn("QuarantineRef", source)

    def test_t13_project_knowledge_never_auto_promotes_to_engine_or_global_default(self) -> None:
        source = (ROOT / "src/biella/project_memory.py").read_text(encoding="utf-8")
        syntax = ast.parse(source)
        self.assertGreater(len(tuple(ast.walk(syntax))), 0)
        self.assertNotIn("EngineKnowledge", source)
        self.assertNotIn("engine_knowledge", source)
        self.assertEqual(
            self.memories.list_knowledge(self.beta_access, self.beta),
            (),
        )

    def test_t14_cache_or_derived_index_deletion_cannot_remove_project_knowledge(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "CREATE TABLE project_knowledge_derived_cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO project_knowledge_derived_cache VALUES ('temporary', 'derived')"
            )
            connection.execute("DROP TABLE project_knowledge_derived_cache")
            connection.commit()
        finally:
            connection.close()

        restarted = ProjectKnowledgeService(self.database_path)
        self.assertEqual(
            restarted.get_knowledge(self.alpha_access, self.first_ref),
            self.first,
        )
        connection = sqlite3.connect(self.database_path)
        try:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertNotIn("project_knowledge_derived_cache", names)
        finally:
            connection.close()

    def test_content_ref_payload_round_trips_without_embedding_bytes(self) -> None:
        content_ref = ContentRef.from_bytes(
            b'{"quality":"cinematic"}',
            media_type="application/json",
        )
        candidate = self.memories.record_candidate(
            self.alpha_access,
            project_ref=self.alpha,
            idempotency_key="content-ref-candidate",
            origin_type="project.source",
            knowledge_type="project.requirement",
            statement=None,
            content_ref=content_ref,
            applicability={"subject": "rendering.quality"},
            source_refs=(self.alpha_source.artifact_ref,),
            evidence_refs=(self.alpha_evidence.artifact_ref,),
        )
        knowledge = self.memories.place_candidate(
            self.alpha_access,
            candidate.candidate_ref,
            knowledge_ref=ProjectKnowledgeRef.new(self.alpha),
            accepted_by="owner://knowledge-alpha",
            idempotency_key="content-ref-placement",
        )

        restarted = ProjectKnowledgeService(self.database_path).get_knowledge(
            self.alpha_access,
            knowledge.knowledge_ref,
        )
        self.assertEqual(restarted.content_ref, content_ref)
        self.assertIsNone(restarted.statement)
        self.assertFalse(hasattr(restarted, "content_bytes"))

    def test_mutable_inputs_are_copied_before_durable_candidate_creation(self) -> None:
        applicability = {"subject": "rendering.mutable"}
        sources = [self.alpha_source.artifact_ref]
        candidate = self.memories.record_candidate(
            self.alpha_access,
            project_ref=self.alpha,
            idempotency_key="mutable-input-candidate",
            origin_type="owner.decision",
            knowledge_type="project.preference",
            statement="Immutable accepted candidate input.",
            content_ref=None,
            applicability=applicability,
            source_refs=sources,
            evidence_refs=(),
        )
        applicability["subject"] = "changed"
        sources.clear()

        self.assertEqual(
            dict(candidate.applicability),
            {"subject": "rendering.mutable"},
        )
        self.assertEqual(candidate.source_refs, (self.alpha_source.artifact_ref,))

    def test_deleted_relation_or_provenance_binding_fails_integrity(self) -> None:
        second = self._supersede_first()
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER project_knowledge_relations_no_delete")
            connection.execute(
                """
                DELETE FROM project_knowledge_relations
                WHERE project_id = ? AND knowledge_id = ? AND from_version = ?
                """,
                (self.alpha.value, self.first_ref.knowledge_id, second.knowledge_ref.version),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(ProjectKnowledgeIntegrityError):
            self.memories.list_history(self.alpha_access, self.first_ref)

    def test_concurrent_conflicting_supersessions_have_one_winner(self) -> None:
        candidates = tuple(
            self._candidate(
                self.alpha_access,
                self.alpha,
                f"concurrent-candidate-{index}",
                f"Concurrent accepted renderer {index}.",
                source_ref=self.alpha_evidence.artifact_ref,
            )
            for index in range(2)
        )

        def place(index: int) -> ProjectKnowledge | Exception:
            try:
                return ProjectKnowledgeService(self.database_path).place_candidate(
                    self.alpha_access,
                    candidates[index].candidate_ref,
                    knowledge_ref=self.first_ref.next_version(),
                    accepted_by=f"owner://concurrent-{index}",
                    idempotency_key=f"concurrent-placement-{index}",
                    supersedes_refs=(self.first_ref,),
                )
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = tuple(executor.map(place, range(2)))
        winners = tuple(item for item in outcomes if isinstance(item, ProjectKnowledge))
        conflicts = tuple(item for item in outcomes if isinstance(item, ProjectKnowledgeConflictError))
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(
            self.memories.resolve_current(self.alpha_access, self.first_ref).current,
            winners[0],
        )

    def test_candidate_and_knowledge_tables_are_append_only_and_restart_verified(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE project_knowledge_candidates SET statement = 'rewrite' WHERE project_id = ?",
                    (self.alpha.value,),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM project_knowledge_revisions WHERE project_id = ?",
                    (self.alpha.value,),
                )
        finally:
            connection.close()
        restarted = ProjectKnowledgeService(self.database_path)
        self.assertEqual(
            restarted.resolve_current(self.alpha_access, self.first_ref).current,
            self.first,
        )

    def test_complete_revision_history_deletion_cannot_hide_accepted_knowledge(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DROP TRIGGER project_knowledge_revisions_no_delete")
            connection.execute(
                """
                DELETE FROM project_knowledge_revisions
                WHERE project_id = ? AND knowledge_id = ?
                """,
                (self.alpha.value, self.first_ref.knowledge_id),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(ProjectKnowledgeIntegrityError):
            self.memories.get_knowledge(self.alpha_access, self.first_ref)
        with self.assertRaises(ProjectKnowledgeIntegrityError):
            self.memories.list_knowledge(self.alpha_access, self.alpha)

    def test_t15_predecessor_typecheck_build_and_installed_restart_gate(self) -> None:
        source = (ROOT / "tests/test_p1_03_project_memory.py").read_text(
            encoding="utf-8"
        )
        prohibited_markers = (
            "TO" "DO",
            "FIX" "ME",
            "place" "holder",
            "@unittest." "skip",
            "pytest.mark." "skip",
            "self." "skipTest",
            "Not" "Implemented",
        )
        for marker in prohibited_markers:
            self.assertNotIn(marker, source, marker)
        ast.parse(source)

        typecheck = subprocess.run(
            (sys.executable, "-m", "mypy", "--strict", "src"),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            typecheck.returncode,
            0,
            f"{typecheck.stdout}\n{typecheck.stderr}",
        )

        loader = unittest.TestLoader()
        predecessor = unittest.TestSuite(
            (
                loader.discover(str(ROOT / "tests"), pattern="test_p0_*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_01*.py"),
                loader.discover(str(ROOT / "tests"), pattern="test_p1_02*.py"),
            )
        )
        self.assertEqual(predecessor.countTestCases(), 267)

        with tempfile.TemporaryDirectory() as temporary_directory:
            qualification_root = Path(temporary_directory)
            wheel_root = qualification_root / "wheel"
            wheel_root.mkdir()
            build = subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    ".",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(wheel_root),
                ),
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, f"{build.stdout}\n{build.stderr}")
            wheels = tuple(wheel_root.glob("biella_engine-*.whl"))
            self.assertEqual(len(wheels), 1)
            wheel_path = wheels[0]
            source_paths = tuple(sorted((ROOT / "src/biella").glob("*.py")))
            with zipfile.ZipFile(wheel_path) as archive:
                source_names = {f"biella/{path.name}" for path in source_paths}
                wheel_names = {
                    name
                    for name in archive.namelist()
                    if name.startswith("biella/") and name.endswith(".py")
                }
                self.assertEqual(wheel_names, source_names)
                for path in source_paths:
                    self.assertEqual(
                        archive.read(f"biella/{path.name}"),
                        path.read_bytes(),
                    )

            installed = qualification_root / "installed"
            install = subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--target",
                    str(installed),
                    str(wheel_path),
                ),
                cwd=qualification_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                install.returncode,
                0,
                f"{install.stdout}\n{install.stderr}",
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "BIELLA_DATABASE": str(
                        qualification_root / "project-memory-restart.sqlite3"
                    ),
                    "BIELLA_INSTALLED": str(installed),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(installed),
                }
            )
            writer_script = inspect.cleandoc(
                """
                import json
                import os
                from pathlib import Path
                import biella
                from biella import ArtifactService, ContentRef, ProjectKnowledgeRef, ProjectKnowledgeService, ProjectStore

                installed = Path(os.environ["BIELLA_INSTALLED"]).resolve()
                assert Path(biella.__file__).resolve().is_relative_to(installed)
                database = Path(os.environ["BIELLA_DATABASE"])
                registration = ProjectStore(database).create_project(namespace="wheel-project-memory", display_name="Wheel Project Memory")
                artifact = ArtifactService(database).create_artifact(registration.access, project_ref=registration.project.project_ref, role="wheel.project.source", content_ref=ContentRef.from_bytes(b"wheel-source", media_type="text/plain"), source_refs=(), source_artifact_refs=(), source_content_refs=(), derivation_type="wheel.project", metadata={})
                memories = ProjectKnowledgeService(database)
                first_candidate = memories.record_candidate(registration.access, project_ref=registration.project.project_ref, idempotency_key="wheel-candidate-one", origin_type="owner.decision", knowledge_type="project.preference", statement="Wheel preference one.", content_ref=None, applicability={"subject": "wheel.preference"}, source_refs=(artifact.artifact_ref,), evidence_refs=())
                first_ref = ProjectKnowledgeRef.new(registration.project.project_ref)
                first = memories.place_candidate(registration.access, first_candidate.candidate_ref, knowledge_ref=first_ref, accepted_by="owner://wheel-project-memory", idempotency_key="wheel-placement-one")
                second_candidate = memories.record_candidate(registration.access, project_ref=registration.project.project_ref, idempotency_key="wheel-candidate-two", origin_type="owner.decision", knowledge_type="project.preference", statement="Wheel preference two.", content_ref=None, applicability={"subject": "wheel.preference"}, source_refs=(artifact.artifact_ref,), evidence_refs=())
                second = memories.supersede_candidate(registration.access, second_candidate.candidate_ref, prior_ref=first_ref, accepted_by="owner://wheel-project-memory", idempotency_key="wheel-placement-two")
                resolution = memories.resolve_current(registration.access, first_ref)
                assert resolution.current == second and first in memories.list_history(registration.access, first_ref)
                print(json.dumps({"project_id": registration.project.project_ref.value, "token": registration.access.token, "knowledge_id": first_ref.knowledge_id, "current_record": second.record_sha256, "source_ref": artifact.artifact_ref.value}))
                """
            )
            writer = subprocess.run(
                (sys.executable, "-c", writer_script),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                writer.returncode,
                0,
                f"{writer.stdout}\n{writer.stderr}",
            )
            identity = json.loads(writer.stdout)
            environment.update(
                {
                    "BIELLA_PROJECT_ID": identity["project_id"],
                    "BIELLA_TOKEN": identity["token"],
                    "BIELLA_KNOWLEDGE_ID": identity["knowledge_id"],
                    "BIELLA_CURRENT_RECORD": identity["current_record"],
                    "BIELLA_SOURCE_REF": identity["source_ref"],
                }
            )
            reader_script = inspect.cleandoc(
                """
                import os
                from pathlib import Path
                import biella
                from biella import ProjectAccess, ProjectKnowledgeRef, ProjectKnowledgeService, ProjectRef

                installed = Path(os.environ["BIELLA_INSTALLED"]).resolve()
                assert Path(biella.__file__).resolve().is_relative_to(installed)
                project_ref = ProjectRef(os.environ["BIELLA_PROJECT_ID"])
                access = ProjectAccess(project_ref, os.environ["BIELLA_TOKEN"])
                reference = ProjectKnowledgeRef(project_ref, os.environ["BIELLA_KNOWLEDGE_ID"], 1)
                memories = ProjectKnowledgeService(Path(os.environ["BIELLA_DATABASE"]))
                history = memories.list_history(access, reference)
                resolution = memories.resolve_current(access, reference)
                assert len(history) == 2 and history[0].statement == "Wheel preference one."
                assert resolution.status == "CURRENT" and resolution.current == history[1]
                assert history[1].record_sha256 == os.environ["BIELLA_CURRENT_RECORD"]
                assert history[1].source_refs[0].value == os.environ["BIELLA_SOURCE_REF"]
                assert memories.search_knowledge(access, project_ref, applicability={"subject": "wheel.preference"}) == history
                """
            )
            reader = subprocess.run(
                (sys.executable, "-c", reader_script),
                cwd=qualification_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                reader.returncode,
                0,
                f"{reader.stdout}\n{reader.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
