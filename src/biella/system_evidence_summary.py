"""Pointer-only P0-P4 system evidence summaries.

The summary is an optional Artifact payload. It indexes durable evidence; it
does not reinterpret that evidence, select a winner, or become an approval
gate.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Mapping, Self


_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SECRET_TEXT = re.compile(
    r"(?:cfat_|sk-(?:proj-)?|token\s*[=:]|password\s*[=:]|secret\s*[=:]|"
    r"aws_access_key_id\s*[=:]|aws_secret_access_key\s*[=:])",
    re.IGNORECASE,
)
_FORBIDDEN_SUMMARY_FIELDS = frozenset(
    {"winner", "routing", "gate", "passed", "failed", "history", "transcript"}
)


class SystemEvidenceSummaryError(ValueError):
    """Raised when a pointer-only summary violates its contract."""


class EvidenceClassification(str, Enum):
    """Why an evidence pointer is useful to the summary."""

    DURABLE_CLOSE = "DURABLE_CLOSE"
    QUALIFICATION = "QUALIFICATION"
    REAL_EVIDENCE = "REAL_EVIDENCE"
    REFERENCE_EVIDENCE = "REFERENCE_EVIDENCE"


class EvidenceReality(str, Enum):
    """Reality classification asserted by the referenced evidence itself."""

    REAL = "REAL"
    REFERENCE = "REFERENCE"
    NOT_RUN = "NOT_RUN"


def _require_safe_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemEvidenceSummaryError(f"{name} must be non-empty text")
    if "\n" in value or "\r" in value or _SECRET_TEXT.search(value):
        raise SystemEvidenceSummaryError(f"{name} is not a safe evidence pointer")
    return value


def _require_hex(name: str, value: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise SystemEvidenceSummaryError(f"{name} has invalid digest syntax")
    return value


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SystemEvidenceRef:
    """One exact durable evidence pointer, without copied evidence content."""

    layer: str
    component: str
    result_commit: str
    result_tree: str
    evidence_ref: str
    evidence_sha256: str
    classification: EvidenceClassification
    reality: EvidenceReality

    def __post_init__(self) -> None:
        if self.layer not in {"P0", "P1", "P2", "P3", "P4"}:
            raise SystemEvidenceSummaryError("layer must be P0 through P4")
        _require_safe_text("component", self.component)
        _require_hex("result_commit", self.result_commit, _HEX40)
        _require_hex("result_tree", self.result_tree, _HEX40)
        _require_safe_text("evidence_ref", self.evidence_ref)
        _require_hex("evidence_sha256", self.evidence_sha256, _HEX64)
        if not isinstance(self.classification, EvidenceClassification):
            raise SystemEvidenceSummaryError("classification must be EvidenceClassification")
        if not isinstance(self.reality, EvidenceReality):
            raise SystemEvidenceSummaryError("reality must be EvidenceReality")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "classification": self.classification.value,
            "component": self.component,
            "evidence_ref": self.evidence_ref,
            "evidence_sha256": self.evidence_sha256,
            "layer": self.layer,
            "reality": self.reality.value,
            "result_commit": self.result_commit,
            "result_tree": self.result_tree,
        }


@dataclass(frozen=True, slots=True)
class SystemEvidenceSummary:
    """Immutable, pointer-only evidence index with no aggregate verdict."""

    summary_id: str
    version: int
    scope_ref: str
    created_at: str
    evidence_refs: tuple[SystemEvidenceRef, ...]
    validation_refs: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_safe_text("summary_id", self.summary_id)
        _require_safe_text("scope_ref", self.scope_ref)
        _require_safe_text("created_at", self.created_at)
        if self.version < 1:
            raise SystemEvidenceSummaryError("version must be positive")
        ordered = tuple(
            sorted(
                self.evidence_refs,
                key=lambda ref: (
                    ref.layer,
                    ref.component,
                    ref.evidence_ref,
                    ref.evidence_sha256,
                ),
            )
        )
        if len({(ref.layer, ref.component, ref.evidence_ref) for ref in ordered}) != len(
            ordered
        ):
            raise SystemEvidenceSummaryError("duplicate evidence pointer")
        validations = tuple(
            sorted({_require_safe_text("validation_ref", ref) for ref in self.validation_refs})
        )
        object.__setattr__(self, "evidence_refs", ordered)
        object.__setattr__(self, "validation_refs", validations)
        _require_hex("canonical_digest", self.canonical_digest, _HEX64)
        if self.canonical_digest != _digest(self._core_payload()):
            raise SystemEvidenceSummaryError("summary digest does not match payload")
        forbidden = _FORBIDDEN_SUMMARY_FIELDS.intersection(field.name for field in fields(self))
        if forbidden:
            raise SystemEvidenceSummaryError("summary contains an authority field")

    def _core_payload(self) -> dict[str, object]:
        return {
            "created_at": self.created_at,
            "evidence_refs": [ref.canonical_payload() for ref in self.evidence_refs],
            "schema": "biella.system_evidence_summary/v1",
            "scope_ref": self.scope_ref,
            "summary_id": self.summary_id,
            "validation_refs": list(self.validation_refs),
            "version": self.version,
        }

    def canonical_payload(self) -> dict[str, object]:
        payload = self._core_payload()
        payload["canonical_digest"] = self.canonical_digest
        return payload

    @classmethod
    def from_canonical_payload(cls, payload: Mapping[str, object]) -> Self:
        if payload.get("schema") != "biella.system_evidence_summary/v1":
            raise SystemEvidenceSummaryError("unsupported summary schema")
        raw_refs = payload.get("evidence_refs")
        raw_validations = payload.get("validation_refs")
        if not isinstance(raw_refs, list) or not isinstance(raw_validations, list):
            raise SystemEvidenceSummaryError("summary collections are malformed")
        evidence_refs: list[SystemEvidenceRef] = []
        for raw in raw_refs:
            if not isinstance(raw, dict):
                raise SystemEvidenceSummaryError("evidence pointer is malformed")
            evidence_refs.append(
                SystemEvidenceRef(
                    layer=str(raw.get("layer", "")),
                    component=str(raw.get("component", "")),
                    result_commit=str(raw.get("result_commit", "")),
                    result_tree=str(raw.get("result_tree", "")),
                    evidence_ref=str(raw.get("evidence_ref", "")),
                    evidence_sha256=str(raw.get("evidence_sha256", "")),
                    classification=EvidenceClassification(str(raw.get("classification", ""))),
                    reality=EvidenceReality(str(raw.get("reality", ""))),
                )
            )
        validations = tuple(str(value) for value in raw_validations)
        return cls(
            summary_id=str(payload.get("summary_id", "")),
            version=int(str(payload.get("version", 0))),
            scope_ref=str(payload.get("scope_ref", "")),
            created_at=str(payload.get("created_at", "")),
            evidence_refs=tuple(evidence_refs),
            validation_refs=validations,
            canonical_digest=str(payload.get("canonical_digest", "")),
        )


def build_system_evidence_summary(
    summary_id: str,
    version: int,
    scope_ref: str,
    evidence_refs: tuple[SystemEvidenceRef, ...],
    validation_refs: tuple[str, ...],
    *,
    created_at: str | None = None,
) -> SystemEvidenceSummary:
    """Build a deterministic pointer index; referenced records remain authoritative."""

    ordered = tuple(
        sorted(
            evidence_refs,
            key=lambda ref: (ref.layer, ref.component, ref.evidence_ref, ref.evidence_sha256),
        )
    )
    validations = tuple(sorted(set(validation_refs)))
    observed_at = created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    core: dict[str, object] = {
        "created_at": observed_at,
        "evidence_refs": [ref.canonical_payload() for ref in ordered],
        "schema": "biella.system_evidence_summary/v1",
        "scope_ref": scope_ref,
        "summary_id": summary_id,
        "validation_refs": list(validations),
        "version": version,
    }
    return SystemEvidenceSummary(
        summary_id=summary_id,
        version=version,
        scope_ref=scope_ref,
        created_at=observed_at,
        evidence_refs=ordered,
        validation_refs=validations,
        canonical_digest=_digest(core),
    )


__all__ = [
    "EvidenceClassification",
    "EvidenceReality",
    "SystemEvidenceRef",
    "SystemEvidenceSummary",
    "SystemEvidenceSummaryError",
    "build_system_evidence_summary",
]
