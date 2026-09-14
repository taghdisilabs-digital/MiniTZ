#!/usr/bin/env python3
"""Read-only D01-50 pre-transition Drive/closure verification; emits a receipt."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[3]
PROJECT = "projects/minitz-games"
PUBLICATIONS = (
    ("docs/project-state/03_BIELLA_CURRENT_STATE.md", "Biella/CURRENT", "1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4"),
    ("docs/project-state/04_BIELLA_ACTIVE_TASK.md", "Biella/CURRENT", "1liutA8evH6rPjk-U4tgR13l_kqBrx-DF"),
    (f"{PROJECT}/docs/PRODUCTION.md", "Biella/PROJECTS/GAMES", "1LUVUz0iG_xL7eOkF1OEBtJ2R9a455eqx"),
)
FOLDERS = (
    ("Biella", "CURRENT", "1GbPXqefsuU7Uf6U4f4yrGetQTcphOLI3"),
    ("Biella/PROJECTS", "GAMES", "1SgvztxBMthMRbr6BPS-n9OXa2RYyXXDb"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], timeout=30)


def rclone(*args):
    return subprocess.check_output(["rclone", *args, "--log-level", "ERROR"], timeout=90)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def single_entry(entries, name, expected_id, is_dir):
    matches = [entry for entry in entries if entry["Name"] == name]
    require(len(matches) == 1, f"Missing or duplicate Drive identity: {name}")
    item = matches[0]
    require(item.get("ID") == expected_id and item["IsDir"] == is_dir,
            f"Wrong Drive identity/type: {name}")
    return item


def list_folder(path, dirs=False):
    flags = ["--dirs-only"] if dirs else ["--files-only"]
    return json.loads(rclone("lsjson", f"gdrive:{path}", "--max-depth", "1", *flags))


def read_publication(publication, source_commit):
    relative, folder, expected_id = publication
    name = Path(relative).name
    target = f"gdrive:{folder}/{name}"
    before = single_entry(list_folder(folder), name, expected_id, False)
    remote = rclone("cat", target)
    after = single_entry(list_folder(folder), name, expected_id, False)
    local = (ROOT / relative).read_bytes()
    require(remote == local == git("show", f"{source_commit}:{relative}"),
            f"Drive/local/source-commit bytes differ: {relative}")
    require(before["Size"] == after["Size"] == len(remote)
            and before["ModTime"] == after["ModTime"],
            f"Drive file changed during readback: {relative}")
    return {"local_path": relative, "drive_path": target, "file_id": expected_id,
            "metadata_before": before, "metadata_after": after,
            "local_bytes": len(local), "remote_bytes": len(remote),
            "local_sha256": sha(local), "remote_sha256": sha(remote), "exact_bytes": True}


def verify():
    started = datetime.now(timezone.utc).isoformat()
    source_commit = git("rev-parse", "HEAD").decode().strip()
    source_tree = git("rev-parse", "HEAD^{tree}").decode().strip()
    production = (ROOT / PUBLICATIONS[2][0]).read_text()
    demo = production.split("## Section: demo01 |", 1)[1].split("## Remaining sections", 1)[0]
    rows = re.findall(r"^- \[([x ])\] (D01-\d+) \| [^|]+ \| [^|]+ \| ([^|]+) \| (.*)$", demo, re.M)
    require([row[1] for row in rows] == [f"D01-{i:02}" for i in range(1, 51)],
            "Demo queue must contain exactly the ordered 50 canonical IDs")
    require(all(row[0] == "x" and row[2].strip() in {"COMPLETE", "COMPLETE_ALREADY"}
                for row in rows[:49]), "Completed predecessor changed")
    require(rows[49][0] == " " and rows[49][2].strip() == "PENDING"
            and "Current task: `D01-50`" in production, "Not the D01-50 pre-transition boundary")
    state = (ROOT / PUBLICATIONS[0][0]).read_text()
    active = (ROOT / PUBLICATIONS[1][0]).read_text()
    require("  P4-06: INCOMPLETE_DEFERRED" in state, "Engine deferral changed")
    require(re.search(r"active_execution:\s+id: D01-50\b", state)
            and re.search(r"task:\s+id: D01-50\b", active)
            and "status: PENDING" in active, "Active task identity changed")

    evidence_paths = [f"{PROJECT}/Build/Demo01/{name}" for name in (
        "D01-46-acceptance.md", "D01-47-acceptance.md", "D01-048-acceptance.md",
        "D01-048-validation.json", "D01-048-independent-replay.json")]
    evidence = []
    for relative in evidence_paths:
        data = (ROOT / relative).read_bytes()
        require(data == git("show", f"{source_commit}:{relative}"), f"Uncommitted evidence: {relative}")
        evidence.append({"path": relative, "bytes": len(data), "sha256": sha(data),
                         "source_commit": source_commit})
    report = json.loads((ROOT / evidence_paths[3]).read_text())
    require(report["task_id"] == "D01-48" and report["result"] == "PASS", "Missing packaged acceptance")
    package = identity(report["package"]["path"])
    require(package == report["package"], "Package identity changed")
    require(package["path"] in rows[45][3] and package["sha256"] in rows[45][3],
            "Published production does not bind the accepted package")
    for number, name in ((46, "D01-47-acceptance.md"), (47, "D01-048-acceptance.md")):
        require(name in rows[number][3], f"Missing published predecessor evidence pointer: {name}")
    require(report["source_before"] == report["source_after"] and len(report["source_after"]) == 73,
            "Packaged acceptance source snapshot differs")
    for item in report["source_after"]:
        require(identity(item["path"]) == item, f"Gameplay bytes changed: {item['path']}")
    gameplay_paths = [f"{PROJECT}/{part}" for part in ("Source", "Config", "Content", "BiellaGames.uproject")]
    require(not git("diff", "--name-only", report["package_source_commit"], source_commit, "--", *gameplay_paths),
            "Current gameplay source differs from qualified package source")
    require(report["protected_before"] == report["protected_after"], "Historical protected snapshot differs")
    for item in report["protected_after"]:
        relative = str(Path(item["path"]).relative_to(ROOT))
        data = git("show", f"{report['revision']['head']}:{relative}")
        require(sha(data) == item["sha256"] and len(data) == item["bytes"],
                f"Historical acceptance metadata identity differs: {relative}")
    predecessor = re.search(r"commit ([0-9a-f]{40}), tree ([0-9a-f]{40})", rows[48][3])
    require(predecessor, "Missing D01-49 GitHub readback identity")
    commit, tree = predecessor.groups()
    require(git("rev-parse", f"{commit}^{{tree}}").decode().strip() == tree, "D01-49 tree differs")
    git("merge-base", "--is-ancestor", commit, source_commit)

    folders = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(list_folder, parent, True) for parent, _, _ in FOLDERS]
        for (parent, name, expected_id), future in zip(FOLDERS, futures):
            entry = single_entry(future.result(), name, expected_id, True)
            folders.append({"drive_path": f"gdrive:{parent}/{name}", "file_id": entry["ID"]})
        receipts = list(pool.map(lambda item: read_publication(item, source_commit), PUBLICATIONS))
    require(git("rev-parse", "HEAD").decode().strip() == source_commit, "Source HEAD changed during readback")
    for receipt in receipts:
        require(sha((ROOT / receipt["local_path"]).read_bytes()) == receipt["local_sha256"],
                "Protected metadata changed during verification")
    return {"task_id": "D01-50", "result": "PASS", "boundary": "PRE_TRANSITION",
            "started_utc": started, "verified_utc": datetime.now(timezone.utc).isoformat(),
            "source_commit": source_commit, "source_tree": source_tree, "verifier": identity(__file__),
            "publication_owner": "Auto Feeder", "drive_mutations": 0,
            "canonical_folders": folders, "drive_readback": receipts,
            "queue": {"completed_predecessors": 49, "total_demo_tasks": 50,
                      "active_task": "D01-50", "active_status": "PENDING",
                      "authority": PUBLICATIONS[2][0], "stale_03_aggregate_preserved": True},
            "predecessor_github_readback": {"commit": commit, "tree": tree, "contained_in_source": True},
            "evidence": evidence, "package": package,
            "package_source_commit": report["package_source_commit"],
            "package_members": [{"name": Path(item["path"]).name, "sha256": item["sha256"],
                                 "bytes": item["bytes"]} for item in report["runs"][0]["package_members_before"]],
            "gameplay_source_hashes_matched": 73, "historical_protected_metadata": "EXACT_GIT_REVISION_MATCH",
            "historical_acceptance_revision": report["revision"],
            "engine_P4_06": "INCOMPLETE_DEFERRED", "visual_status": report["visual_status"],
            "scope": "Existing Linux x64 Development automated acceptance; no new gameplay or performance run. "
                     "This receipt verifies already-published continuity. The Auto Feeder owns the later completion publication."}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
