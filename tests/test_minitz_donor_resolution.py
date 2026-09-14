from __future__ import annotations
import pytest


def extraction():
    return {
        "schema": "minitz.donor-extraction/v1",
        "input_digest": "a" * 64,
        "files": [
            {"path": "ops/x.py", "classification": "DIVERGENT_REQUIRES_SEMANTIC_RESOLUTION"},
            {"path": "tests/old.py", "classification": "UNMAPPED_DONOR_VALUE"},
            {"path": "secret.test", "classification": "PROTECTED_CONTENT_REQUIRES_CREDENTIAL_REVIEW"},
            {"path": "missing", "classification": "MISSING_FROM_DONOR_WORKTREE"},
            {"path": "big.zip", "classification": "LARGE_DONOR_OBJECT_REQUIRES_SCOPED_TRANSFER"},
            {"path": "same.py", "classification": "BYTE_EQUIVALENT_PRESENT"},
        ],
    }


def complete_resolution():
    return {
        "schema": "minitz.donor-resolution/v1", "authority": "EVIDENCE_ONLY",
        "extraction_input_digest": "a" * 64, "active_donor_authority": False,
        "lineage": {"donor_head": "1" * 40, "current_head": "2" * 40, "donor_head_is_ancestor": True},
        "resolutions": [
            {"path": "ops/x.py", "classification": "DIVERGENT_REQUIRES_SEMANTIC_RESOLUTION", "disposition": "CURRENT_CANONICAL_DESCENDANT", "destination_ref": "repo://minitz/ops/x.py"},
            {"path": "tests/old.py", "classification": "UNMAPPED_DONOR_VALUE", "disposition": "SEMANTIC_EQUIVALENT_DESTINATION", "destination_ref": "repo://minitz/tests/new.py"},
            {"path": "secret.test", "classification": "PROTECTED_CONTENT_REQUIRES_CREDENTIAL_REVIEW", "disposition": "PROTECTED_REFERENCE_ONLY", "destination_ref": "credential-boundary://minitz"},
            {"path": "missing", "classification": "MISSING_FROM_DONOR_WORKTREE", "disposition": "NO_DONOR_BYTES"},
            {"path": "big.zip", "classification": "LARGE_DONOR_OBJECT_REQUIRES_SCOPED_TRANSFER", "disposition": "HISTORICAL_BINARY_REFERENCE", "destination_ref": "provenance://minitz/big.zip"},
        ],
    }


def test_resolution_closes_only_when_every_non_equivalent_row_is_accounted():
    from minitz_os.provenance import validate_resolution
    closed = validate_resolution(extraction(), complete_resolution())
    assert closed["semantic_transfer_complete"] is True
    assert closed["retirement_allowed"] is True
    assert closed["active_donor_authority"] is False
    assert closed["resolved_count"] == 5


def test_resolution_rejects_missing_or_duplicate_disposition():
    from minitz_os.provenance import validate_resolution
    missing = complete_resolution(); missing["resolutions"] = missing["resolutions"][:-1]
    with pytest.raises(ValueError, match="exactly once"):
        validate_resolution(extraction(), missing)
    duplicate = complete_resolution(); duplicate["resolutions"].append(dict(duplicate["resolutions"][0]))
    with pytest.raises(ValueError, match="exactly once"):
        validate_resolution(extraction(), duplicate)


def test_resolution_rejects_fake_descendant_and_raw_protected_content():
    from minitz_os.provenance import validate_resolution
    stale = complete_resolution(); stale["lineage"]["donor_head_is_ancestor"] = False
    with pytest.raises(ValueError, match="ancestor"):
        validate_resolution(extraction(), stale)
    leaked = complete_resolution(); leaked["resolutions"][2]["raw_content"] = "secret"
    with pytest.raises(ValueError, match="unsupported"):
        validate_resolution(extraction(), leaked)


def test_resolution_rejects_wrong_class_or_disposition():
    from minitz_os.provenance import validate_resolution
    bad = complete_resolution(); bad["resolutions"][1]["classification"] = "DIVERGENT_REQUIRES_SEMANTIC_RESOLUTION"
    with pytest.raises(ValueError, match="classification"):
        validate_resolution(extraction(), bad)
    bad = complete_resolution(); bad["resolutions"][1]["disposition"] = "NO_DONOR_BYTES"
    with pytest.raises(ValueError, match="disposition"):
        validate_resolution(extraction(), bad)
