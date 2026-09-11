from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from biella.validation import (
    VALIDATION_COMPLETION_FAMILY_REVISION,
    ValidationCompletionEvidence,
    ValidationCompletionFamily,
)

ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "ops/local-ai"
sys.path.insert(0, str(LOCAL_AI))
SPEC = importlib.util.spec_from_file_location(
    "unify03_production_evidence", LOCAL_AI / "biella_production_evidence.py"
)
assert SPEC and SPEC.loader
production_evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = production_evidence
SPEC.loader.exec_module(production_evidence)

TASK_ID = "UNIFY-03"
DIGEST = "a" * 64
SCOPE = "task://minitz/UNIFY-03/5"


def _record(
    kind: str,
    *,
    revision: int = 5,
    digest: str = DIGEST,
    scope: str = SCOPE,
    criterion: str | None = None,
    accepted_criteria: tuple[str, ...] = (),
    implementation_ref: str = "implementation://validator/one",
    implementation_refs: tuple[str, ...] = (),
    authority_ref: str | None = None,
    verdict: str = "PASS",
) -> ValidationCompletionEvidence:
    return ValidationCompletionEvidence(
        kind=kind,
        task_id=TASK_ID,
        task_revision=revision,
        task_digest=digest,
        scope_ref=scope,
        evidence_ref=f"evidence://unify03/{kind.lower()}/{revision}/{abs(hash((criterion, implementation_ref))) % 100000}",
        evidence_sha256="b" * 64,
        implementation_ref=implementation_ref,
        verdict=verdict,
        criterion=criterion,
        family_revision=VALIDATION_COMPLETION_FAMILY_REVISION if kind == "FAMILY_RECEIPT" else None,
        authority_ref=authority_ref,
        accepted_criteria=accepted_criteria,
        implementation_refs=implementation_refs,
    )


def _result_file(path: Path, evidence: list[object], *, accepted: list[str] | None = None) -> Path:
    authority = ValidationCompletionFamily.completion_authority_ref(TASK_ID, 5, SCOPE)
    path.write_text(json.dumps({
        "task_id": TASK_ID,
        "status": "COMPLETE",
        "summary": "done",
        "evidence": evidence,
        "task_revision": 5,
        "task_digest": DIGEST,
        "scope_ref": SCOPE,
        "family_revision": VALIDATION_COMPLETION_FAMILY_REVISION,
        "authority_ref": authority,
        "accepted_criteria": accepted or [],
    }), encoding="utf-8")
    return path


def test_family_receipt_must_bind_declared_criteria() -> None:
    family = ValidationCompletionFamily()
    authority = family.completion_authority_ref(TASK_ID, 5, SCOPE)
    validation = _record("VALIDATION", criterion="criterion-a")
    receipt = _record(
        "FAMILY_RECEIPT",
        accepted_criteria=(),
        implementation_refs=(validation.implementation_ref,),
        authority_ref=authority,
    )
    decision = family.admit(
        TASK_ID, 5, DIGEST, SCOPE, "COMPLETE", (validation, receipt),
        required_criteria=("criterion-a",),
        allowed_criteria=("criterion-a", "criterion-b"),
        accepted_criteria=("criterion-a",),
        authority_ref=authority,
    )
    assert decision.accepted is False
    assert "family receipt" in decision.reason.lower()


def test_valid_acceptance_superset_of_minimum_is_allowed_when_task_supports_it() -> None:
    family = ValidationCompletionFamily()
    authority = family.completion_authority_ref(TASK_ID, 5, SCOPE)
    first = _record("VALIDATION", criterion="criterion-a", implementation_ref="implementation://validator/a")
    second = _record("VALIDATION", criterion="criterion-b", implementation_ref="implementation://validator/b")
    receipt = _record(
        "FAMILY_RECEIPT",
        accepted_criteria=("criterion-a", "criterion-b"),
        implementation_refs=(first.implementation_ref, second.implementation_ref),
        authority_ref=authority,
    )
    decision = family.admit(
        TASK_ID, 5, DIGEST, SCOPE, "COMPLETE", (first, second, receipt),
        required_criteria=("criterion-a",),
        allowed_criteria=("criterion-a", "criterion-b", "criterion-c"),
        accepted_criteria=("criterion-a", "criterion-b"),
        authority_ref=authority,
    )
    assert decision.accepted is True
    assert decision.accepted_criteria == ("criterion-a", "criterion-b")


def test_unsupported_acceptance_claim_is_rejected() -> None:
    family = ValidationCompletionFamily()
    authority = family.completion_authority_ref(TASK_ID, 5, SCOPE)
    validation = _record("VALIDATION", criterion="criterion-a")
    receipt = _record(
        "FAMILY_RECEIPT",
        accepted_criteria=("criterion-a", "invented-criterion"),
        implementation_refs=(validation.implementation_ref,),
        authority_ref=authority,
    )
    decision = family.admit(
        TASK_ID, 5, DIGEST, SCOPE, "COMPLETE", (validation, receipt),
        required_criteria=("criterion-a",),
        allowed_criteria=("criterion-a", "criterion-b"),
        accepted_criteria=("criterion-a", "invented-criterion"),
        authority_ref=authority,
    )
    assert decision.accepted is False
    assert "unsupported acceptance criteria" in decision.reason.lower()


def test_object_completion_evidence_obeys_serialization_bound(tmp_path: Path) -> None:
    huge = "x" * 500
    record = _record("VALIDATION", accepted_criteria=tuple(f"{i}-{huge}" for i in range(40)))
    path = _result_file(tmp_path / "result.json", [record.payload()])
    with pytest.raises(ValueError, match="unbounded"):
        production_evidence.parse_result(path, TASK_ID)


def test_complete_already_accepts_independently_proven_prior_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    current_revision = 5
    prior_revision = 4
    prior_digest = "c" * 64
    prior_scope = f"task://minitz/{TASK_ID}/{prior_revision}"
    family = ValidationCompletionFamily()
    prior_authority = family.completion_authority_ref(TASK_ID, prior_revision, prior_scope)
    prior_validation = _record(
        "VALIDATION", revision=prior_revision, digest=prior_digest, scope=prior_scope,
        criterion="criterion-a",
    )
    prior_receipt = _record(
        "FAMILY_RECEIPT", revision=prior_revision, digest=prior_digest, scope=prior_scope,
        accepted_criteria=("criterion-a",),
        implementation_refs=(prior_validation.implementation_ref,), authority_ref=prior_authority,
    )
    persisted = [
        prior_validation.to_json(), prior_receipt.to_json(),
        f"MINITZ_TRANSITION_PREDECESSOR_TASK_ID:{TASK_ID}",
        f"MINITZ_TRANSITION_PREDECESSOR_TASK_REVISION:{prior_revision}",
        f"MINITZ_TRANSITION_PREDECESSOR_TASK_SHA256:{prior_digest}",
    ]
    contract = {
        "task_id": TASK_ID,
        "task_revision": current_revision,
        "task_digest": DIGEST,
        "scope_ref": f"task://minitz/{TASK_ID}/{current_revision}",
        "required_criteria": ("criterion-a",),
        "allowed_criteria": ("criterion-a", "criterion-b"),
    }
    row = {"revision": current_revision, "completion": {"evidence": persisted}}
    monkeypatch.setattr(production_evidence, "_minitz_completion_contract", lambda task_id: (contract, row))
    result = production_evidence.TaskResult(
        TASK_ID, "COMPLETE_ALREADY", "already accepted", tuple(persisted), current_revision,
        DIGEST, contract["scope_ref"], VALIDATION_COMPLETION_FAMILY_REVISION,
        family.completion_authority_ref(TASK_ID, current_revision, contract["scope_ref"]),
        ("criterion-a",),
    )
    production_evidence._admit_minitz_result(result, SimpleNamespace(status="PENDING"))


def test_legacy_completion_text_parses_but_never_admits_minitz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _result_file(tmp_path / "legacy.json", ["runtime pass"])
    result = production_evidence.parse_result(path, TASK_ID)
    assert result.evidence == ("runtime pass",)
    contract = {
        "task_id": TASK_ID, "task_revision": 5, "task_digest": DIGEST, "scope_ref": SCOPE,
        "required_criteria": (), "allowed_criteria": (),
    }
    monkeypatch.setattr(production_evidence, "_minitz_completion_contract", lambda task_id: (contract, {"revision": 5, "completion": {"evidence": []}}))
    with pytest.raises(Exception, match="typed evidence"):
        production_evidence._admit_minitz_result(result, SimpleNamespace(status="PENDING"))


def test_cited_failed_validation_vetoes_completion() -> None:
    family = ValidationCompletionFamily()
    authority = family.completion_authority_ref(TASK_ID, 5, SCOPE)
    failed = _record(
        "VALIDATION", criterion="criterion-a", verdict="FAILED",
        implementation_ref="implementation://validator/failed",
    )
    receipt = _record(
        "FAMILY_RECEIPT", accepted_criteria=("criterion-a",),
        implementation_refs=(failed.implementation_ref,), authority_ref=authority,
    )
    decision = family.admit(
        TASK_ID, 5, DIGEST, SCOPE, "COMPLETE", (failed, receipt),
        required_criteria=("criterion-a",), allowed_criteria=("criterion-a",),
        accepted_criteria=("criterion-a",), authority_ref=authority,
    )
    assert decision.accepted is False
    assert "fail/failed" in decision.reason.lower()
