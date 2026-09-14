from pathlib import Path
import json
import pytest


def test_donor_inventory_preserves_unique_and_changed_work(tmp_path):
    from minitz_os.provenance import inventory
    source=tmp_path/"source";donor=tmp_path/"donor"
    source.mkdir();donor.mkdir()
    (donor/"same.py").write_text("def same(): return 1\n")
    (source/"same.py").write_text((donor/"same.py").read_text())
    (donor/"different.py").write_text("class UsefulDonor: pass\n")
    (source/"different.py").write_text("class Native: pass\n")
    (donor/"unique.py").write_text("def reusable(): return True\n")
    result=inventory(donor,source,tmp_path/"evidence.json")
    rows={r["path"]:r for r in result["files"]}
    assert rows["same.py"]["classification"]=="BYTE_EQUIVALENT_PRESENT"
    assert rows["different.py"]["classification"]=="DIVERGENT_REQUIRES_SEMANTIC_RESOLUTION"
    assert rows["unique.py"]["classification"]=="UNMAPPED_DONOR_VALUE"
    assert rows["unique.py"]["symbols"][0]["name"]=="reusable"
    assert all(r["semantic_validation"]=="PENDING" for r in rows.values())
    assert result["retirement_allowed"] is False
    assert (donor/"unique.py").is_file()


def test_inventory_never_reads_external_symlink_or_credential_content(tmp_path):
    from minitz_os.provenance import inventory
    source=tmp_path/"source";donor=tmp_path/"donor"
    source.mkdir();donor.mkdir()
    (donor/"auth.json").write_text('{"secret":"DO_NOT_INCLUDE"}')
    (tmp_path/"outside").write_text("OUTSIDE_SECRET")
    (donor/"linked.py").symlink_to(tmp_path/"outside")
    result=inventory(donor,source,tmp_path/"evidence.json")
    data=json.dumps(result)
    assert "DO_NOT_INCLUDE" not in data and "OUTSIDE_SECRET" not in data
    assert {r["classification"] for r in result["files"]}=={"PROTECTED_CREDENTIAL_REFERENCE", "SYMLINK_REFERENCE_ONLY"}


def test_inventory_parsing_is_content_cached_not_task_or_session_bound(tmp_path):
    from minitz_os.provenance import inventory
    source=tmp_path/"source";donor=tmp_path/"donor"
    source.mkdir();donor.mkdir()
    (donor/"one.py").write_text("def one(): pass\n")
    output=tmp_path/"evidence.json"
    first=inventory(donor,source,output)
    second=inventory(donor,source,output)
    assert first["parses_created"]==1 and second["parses_reused"]==1
    assert first["input_digest"]==second["input_digest"]
