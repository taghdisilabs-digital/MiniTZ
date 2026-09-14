from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from minitz_os.engine.evidence_graph import (
    EVIDENCE_AUTHORITY,
    EvidenceConflictError,
    EvidenceContractError,
    EvidenceGraph,
    EvidenceProvenance,
    EvidenceRecord,
    EvidenceRelationType,
    derived_provenance,
)
from minitz_os.engine.event import EventLedger, EventScopeError
from minitz_os.engine.project import ProjectRef, ProjectStore


def _provenance(scope_ref: str, source_ref: str) -> EvidenceProvenance:
    return derived_provenance(
        source_identity=source_ref,
        source_revision_or_observation="UNIFY-06-test-observation",
        source_sha256_or_private_receipt="a" * 64,
        origin_kind="TEST_FIXTURE",
        observed_at_or_unknown="2026-09-11T00:00:00+00:00",
        extraction_or_derivation_ref=source_ref,
        scope_ref=scope_ref,
    )


def test_normalization_keeps_kinds_distinct_and_rejects_competing_truth() -> None:
    scope = "prj_evidence_family"
    provenance = _provenance(scope, "test://unify-06/source")
    event = EvidenceGraph.record(
        record_kind="EVENT",
        exact_ref="event://prj_evidence_family/evt-1",
        project_ref=scope,
        payload={"event_type": "MODEL_CALL"},
        provenance=provenance,
    )
    call = EvidenceGraph.record(
        record_kind="CALL",
        exact_ref="call://prj_evidence_family/call-1",
        project_ref=scope,
        payload={"call_subtype": "MODEL_CALL"},
        provenance=provenance,
    )
    failure = EvidenceGraph.record(
        record_kind="FAILURE",
        exact_ref="failure://prj_evidence_family/failure-1",
        project_ref=scope,
        payload={"failure_type": "PROCESS_FAILED"},
        provenance=provenance,
    )
    relation = EvidenceGraph.relation(
        relation_type=EvidenceRelationType.REALIZES,
        left_exact_ref=call.exact_ref,
        right_exact_ref=event.exact_ref,
        project_ref=scope,
        scope_ref=scope,
        evidence_refs=(event.exact_ref,),
        qualification={"phase": "START"},
        provenance=provenance,
    )

    records, relations = EvidenceGraph.normalize(
        (event, event, call, failure),
        (relation, relation),
    )
    assert {record.record_kind for record in records} == {"EVENT", "CALL", "FAILURE"}
    assert len(relations) == 1
    assert all(record.authority == EVIDENCE_AUTHORITY for record in records)
    assert all(not record.projection_authority and not record.progression_authority for record in records)

    competing = EvidenceGraph.record(
        record_kind="EVENT",
        exact_ref=event.exact_ref,
        project_ref=scope,
        payload={"event_type": "TOOL_CALL"},
        provenance=provenance,
    )
    with pytest.raises(EvidenceConflictError):
        EvidenceGraph.normalize((event, competing))


@pytest.mark.parametrize("payload", [{"raw_output": "provider output"}, {"api_key": "excluded"}])
def test_semantic_records_reject_raw_provider_values_and_credentials(payload: dict[str, str]) -> None:
    with pytest.raises(EvidenceContractError):
        EvidenceGraph.record(
            record_kind="REJECTION",
            exact_ref="rejection://prj_evidence_family/rejection-1",
            project_ref="prj_evidence_family",
            payload=payload,
            provenance=_provenance("prj_evidence_family", "test://unify-06/rejected"),
        )


def test_semantic_records_reject_alternate_family_identity() -> None:
    provenance = _provenance("prj_evidence_family", "test://unify-06/family-boundary")
    with pytest.raises(EvidenceContractError):
        EvidenceRecord(
            record_kind="EVENT",
            exact_ref="event://prj_evidence_family/family-boundary",
            project_ref="prj_evidence_family",
            payload={"event_type": "agent.message"},
            provenance=provenance,
            semantic_graph="OtherGraph",
        )


def test_event_ledger_persists_immutable_relation_without_progression_authority(tmp_path: Path) -> None:
    database_path = tmp_path / "evidence.sqlite3"
    registration = ProjectStore(database_path).create_project(
        namespace="evidence-family",
        display_name="Evidence Family",
    )
    project_ref = registration.project.project_ref
    relation = EvidenceGraph.relation(
        relation_type="REALIZES",
        left_exact_ref=f"call://{project_ref.value}/call-1",
        right_exact_ref=f"event://{project_ref.value}/event-1",
        project_ref=project_ref.value,
        scope_ref=project_ref.value,
        evidence_refs=(f"journal-evidence://{project_ref.value}/line-1",),
        qualification={"phase": "START", "authority": "NONE"},
        provenance=_provenance(project_ref.value, "test://unify-06/journal"),
    )
    ledger = EventLedger(database_path)
    persisted = ledger.append_evidence_relation(registration.access, relation)
    assert persisted == relation
    assert ledger.append_evidence_relation(registration.access, relation) == relation
    assert ledger.list_evidence_relations(
        registration.access,
        project_ref,
        left_exact_ref=relation.left_exact_ref,
        relation_type="realizes",
    ) == (relation,)
    assert ledger.get_evidence_relation(
        registration.access,
        project_ref,
        relation.relation_id,
    ) == relation
    with pytest.raises(EventScopeError):
        ledger.list_evidence_relations(
            registration.access,
            ProjectRef("prj_" + "0" * 32),
        )

    connection = sqlite3.connect(database_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE evidence_relations SET scope_ref = ? WHERE relation_id = ?",
                ("changed", relation.relation_id),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM evidence_relations WHERE relation_id = ?",
                (relation.relation_id,),
            )
        connection.rollback()
    finally:
        connection.close()
