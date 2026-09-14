from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from minitz_os.engine.project import ProjectRef
from minitz_os.engine.run import RunRef

FIXTURES = Path(__file__).parent / "fixtures" / "p4_04_l40s"
HASHES = {"locality_evidence_spec.json":"4d1a1caf3f7cac4d21fe93582a6c69a160cb1986924002bf3f1c5f6b0f1c1745","locality_evidence_results.json":"978d907094c0ead0d70687ffe194d13310a7900410f2dd6d8c7d1202d169cbed","locality_evidence_manifest.json":"e3c17f7991caf24ae320d6ca899e098ff608e2ccce6eef3d8b75b379d9088d87","post_run_resource.json":"ad302a331e445a7f3f5edbc5ef2cd4f8c6aca8e2a556c6096df86c501f2f92d9"}
def test_real_locality_evidence_import_contract() -> None:
    from minitz_os.engine.placement_learning_evidence import ExternalLocalityArtifacts, LocalityEvidenceBinding, import_p4_04_l40s_evidence
    payload = {name:(FIXTURES/name).read_bytes() for name in HASHES}
    assert {name:hashlib.sha256(value).hexdigest() for name,value in payload.items()} == HASHES
    project = ProjectRef.new()
    artifacts = ExternalLocalityArtifacts(**payload)
    binding = LocalityEvidenceBinding(project, RunRef(project, "run_" + hashlib.sha256(payload["locality_evidence_results.json"]).hexdigest()[:32]))
    imported = import_p4_04_l40s_evidence(**payload, binding=binding)
    assert imported.structural_checks == 26
    assert imported.post_run_processes == 0 and imported.post_run_residency is False
    assert {"cold_warm_match","overload","artifact_transfer","stale_workspace","stale_toolchain","render_rebuild","retention_pressure"} <= set(imported.cases)
    assert imported.reality == "REAL" and imported.identity_binding == "REFERENCE"
    assert imported.routing_allowed is False and imported.promotion_allowed is False
    with pytest.raises(Exception): LocalityEvidenceBinding(ProjectRef.new(), binding.run_ref)
def test_locality_evidence_forgery_rejects() -> None:
    from minitz_os.engine.placement_learning_evidence import EvidenceImportError, import_p4_04_l40s_evidence
    payload = {name:(FIXTURES/name).read_bytes() for name in HASHES}; payload["locality_evidence_results.json"] += b" "
    with pytest.raises(EvidenceImportError): import_p4_04_l40s_evidence(**payload)
