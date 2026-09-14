from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from minitz_os.engine.system_evidence_summary import (
    EvidenceClassification,
    EvidenceReality,
    SystemEvidenceRef,
    SystemEvidenceSummary,
    build_system_evidence_summary,
)


_SHA256 = "a" * 64


def _ref(
    *,
    layer: str = "P4",
    component: str = "routing-learning",
    classification: EvidenceClassification = EvidenceClassification.REAL_EVIDENCE,
    reality: EvidenceReality = EvidenceReality.REAL,
) -> SystemEvidenceRef:
    return SystemEvidenceRef(
        layer=layer,
        component=component,
        result_commit="1" * 40,
        result_tree="2" * 40,
        evidence_ref="artifact://external/p4/example",
        evidence_sha256=_SHA256,
        classification=classification,
        reality=reality,
    )


def test_pointer_only_summary_is_frozen_and_deterministic() -> None:
    first = build_system_evidence_summary(
        summary_id="p4-system-evidence",
        version=1,
        scope_ref="scope://p4/qualification",
        evidence_refs=(
            _ref(component="failure-repair"),
            _ref(component="routing-learning"),
        ),
        validation_refs=("validation://p4/cross-layer",),
    )
    second = build_system_evidence_summary(
        summary_id="p4-system-evidence",
        version=1,
        scope_ref="scope://p4/qualification",
        evidence_refs=tuple(reversed(first.evidence_refs)),
        validation_refs=("validation://p4/cross-layer",),
    )

    assert isinstance(first, SystemEvidenceSummary)
    assert first.canonical_digest == second.canonical_digest
    assert first.evidence_refs == second.evidence_refs
    with pytest.raises(FrozenInstanceError):
        first.version = 2  # type: ignore[misc]


def test_evidence_ref_rejects_invalid_layer_pointer_digest_and_secret_text() -> None:
    with pytest.raises(ValueError):
        _ref(layer="P5")
    with pytest.raises(ValueError):
        SystemEvidenceRef(
            layer="P4",
            component="routing-learning",
            result_commit="not-a-commit",
            result_tree="2" * 40,
            evidence_ref="artifact://external/p4/example",
            evidence_sha256=_SHA256,
            classification=EvidenceClassification.REFERENCE_EVIDENCE,
            reality=EvidenceReality.REFERENCE,
        )
    with pytest.raises(ValueError):
        SystemEvidenceRef(
            layer="P4",
            component="token=secret",
            result_commit="1" * 40,
            result_tree="2" * 40,
            evidence_ref="artifact://external/p4/example",
            evidence_sha256=_SHA256,
            classification=EvidenceClassification.REFERENCE_EVIDENCE,
            reality=EvidenceReality.REFERENCE,
        )


def test_summary_keeps_reality_and_classification_explicit_without_gate_or_winner_fields() -> None:
    summary = build_system_evidence_summary(
        summary_id="p0-through-p4",
        version=1,
        scope_ref="scope://p4/qualification",
        evidence_refs=(
            _ref(layer="P0", component="neutral-kernel", classification=EvidenceClassification.QUALIFICATION, reality=EvidenceReality.REFERENCE),
            _ref(layer="P3", component="gpu-evidence", classification=EvidenceClassification.REFERENCE_EVIDENCE, reality=EvidenceReality.NOT_RUN),
            _ref(),
        ),
        validation_refs=("validation://p4/neutral", "validation://p4/wheel"),
    )

    assert {item.layer for item in summary.evidence_refs} == {"P0", "P3", "P4"}
    assert {(item.classification, item.reality) for item in summary.evidence_refs} == {
        (EvidenceClassification.QUALIFICATION, EvidenceReality.REFERENCE),
        (EvidenceClassification.REFERENCE_EVIDENCE, EvidenceReality.NOT_RUN),
        (EvidenceClassification.REAL_EVIDENCE, EvidenceReality.REAL),
    }
    names = {item.name for item in fields(SystemEvidenceSummary)} | {
        item.name for item in fields(SystemEvidenceRef)
    }
    assert not names & {"winner", "routing", "gate", "passed", "failed", "history", "transcript"}


def test_canonical_payload_round_trip_when_supported() -> None:
    summary = build_system_evidence_summary(
        summary_id="round-trip",
        version=1,
        scope_ref="scope://p4/qualification",
        evidence_refs=(_ref(),),
        validation_refs=("validation://p4/round-trip",),
    )
    payload = summary.canonical_payload()
    restored = SystemEvidenceSummary.from_canonical_payload(payload)

    assert restored == summary
    assert restored.canonical_digest == summary.canonical_digest
