#!/usr/bin/env python3
"""Verify the D01-41 visual index against project bytes and the inspector catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
INDEX_PATH = PROJECT / "Build/Demo01/D01-041-visual-index.json"
REPORT_PATH = PROJECT / "Build/Demo01/D01-041-validation.json"
ARTIFACT_ROOT = Path("/root/biella/artifacts/games")
METADATA_PATH = ARTIFACT_ROOT / "D01-040/metadata.json"
PRODUCER_COMMIT = "600fdda86b6f1b1845966a7d24312eada9593548"
EXPECTED_SOURCE_CLASS = "GENERATED_DRAFT"


def fail(message: str) -> None:
    raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n" or payload[12:16] != b"IHDR":
        fail(f"not a PNG with an IHDR: {path}")
    width = int.from_bytes(payload[16:20], "big")
    height = int.from_bytes(payload[20:24], "big")
    if width < 1 or height < 1:
        fail(f"invalid PNG dimensions: {path}")
    return width, height


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=REPO, text=True, stderr=subprocess.STDOUT
    ).strip()


def verify() -> dict[str, object]:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if index.get("schema") != "biella.games.visual-index/v1":
        fail("unexpected visual index schema")
    if index.get("task_id") != "D01-41" or index.get("section") != "demo01":
        fail("visual index is not scoped to D01-41/demo01")
    if index.get("status") != EXPECTED_SOURCE_CLASS:
        fail("visual index must preserve GENERATED_DRAFT status")
    if index.get("source_class") != EXPECTED_SOURCE_CLASS:
        fail("visual index must preserve GENERATED_DRAFT source class")
    if index.get("owner_accepted") is not False or index.get("canonical") is not False:
        fail("generated visuals were incorrectly promoted")
    inspection = index.get("inspection")
    if not isinstance(inspection, dict):
        fail("inspection routing metadata is missing")
    if inspection.get("lane") != "Games" or inspection.get("root_id") != "games-generated":
        fail("visual index is not routed to the Games generated root")
    if inspection.get("root_source_class") != EXPECTED_SOURCE_CLASS:
        fail("inspection root lost GENERATED_DRAFT classification")

    producer = index.get("producer")
    if not isinstance(producer, dict) or producer.get("commit") != PRODUCER_COMMIT:
        fail("D01-40 producer identity is missing or changed")
    current_commit = git("rev-parse", "HEAD")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", PRODUCER_COMMIT, current_commit],
        cwd=REPO,
    ).returncode != 0:
        fail("D01-40 producer commit is not an ancestor of the current source")

    captures = index.get("captures")
    if not isinstance(captures, list) or len(captures) != 12:
        fail("expected exactly the 12 final D01-40 captures")
    if index.get("counts", {}).get("captures") != len(captures):
        fail("capture count does not match the visible index")

    seen_project: set[str] = set()
    seen_inspector: set[str] = set()
    seen_digests: set[str] = set()
    observed_assets: list[dict[str, object]] = []
    for capture in captures:
        if not isinstance(capture, dict):
            fail("capture entry is not an object")
        for key in ("project_path", "inspector_path", "sha256", "size_bytes", "width", "height"):
            if key not in capture:
                fail(f"capture is missing {key}")
        project_relative = str(capture["project_path"])
        inspector_relative = str(capture["inspector_path"])
        if project_relative in seen_project or inspector_relative in seen_inspector:
            fail("visual index contains duplicate paths")
        seen_project.add(project_relative)
        seen_inspector.add(inspector_relative)
        if capture.get("kind") != "image" or capture.get("previewable") is not True:
            fail(f"capture is not previewable image media: {project_relative}")
        if capture.get("status") != EXPECTED_SOURCE_CLASS or capture.get("source_class") != EXPECTED_SOURCE_CLASS:
            fail(f"capture lost GENERATED_DRAFT classification: {project_relative}")
        if capture.get("root_id") != "games-generated":
            fail(f"capture is not routed to games-generated: {project_relative}")
        project_path = PROJECT / project_relative
        inspector_path = ARTIFACT_ROOT / inspector_relative
        if not project_path.is_file():
            fail(f"project capture is missing: {project_path}")
        if not inspector_path.is_file():
            fail(f"inspector capture is missing: {inspector_path}")
        project_digest = sha256(project_path)
        inspector_digest = sha256(inspector_path)
        expected_digest = str(capture["sha256"])
        if project_digest != expected_digest or inspector_digest != expected_digest:
            fail(f"project/inspector bytes do not match indexed digest: {project_relative}")
        if expected_digest in seen_digests:
            fail("visual index contains duplicate content identities")
        seen_digests.add(expected_digest)
        project_size = project_path.stat().st_size
        inspector_size = inspector_path.stat().st_size
        if project_size != int(capture["size_bytes"]) or inspector_size != int(capture["size_bytes"]):
            fail(f"project/inspector size does not match index: {project_relative}")
        project_dimensions = png_dimensions(project_path)
        inspector_dimensions = png_dimensions(inspector_path)
        indexed_dimensions = (int(capture["width"]), int(capture["height"]))
        if project_dimensions != indexed_dimensions or inspector_dimensions != indexed_dimensions:
            fail(f"project/inspector dimensions do not match index: {project_relative}")
        observed_assets.append(
            {
                "project_path": project_relative,
                "inspector_path": inspector_relative,
                "sha256": expected_digest,
                "size_bytes": project_size,
                "dimensions": list(project_dimensions),
            }
        )

    if not METADATA_PATH.is_file():
        fail(f"external inspector metadata is missing: {METADATA_PATH}")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if metadata.get("status") != EXPECTED_SOURCE_CLASS or metadata.get("source_class") != EXPECTED_SOURCE_CLASS:
        fail("external inspector metadata did not preserve GENERATED_DRAFT")
    if metadata.get("visual_index") != "projects/minitz-games/Build/Demo01/D01-041-visual-index.json":
        fail("external inspector metadata does not point to the canonical index")
    if metadata.get("captures") != sorted(seen_inspector):
        fail("external inspector metadata does not enumerate the visible captures")

    sys.path.insert(0, str(REPO))
    from ops.control_gateway.biella_control_assets import AssetCatalog, AssetRoot

    catalog = AssetCatalog(
        {
            "Games": [
                AssetRoot("games-generated", ARTIFACT_ROOT, EXPECTED_SOURCE_CLASS),
            ]
        }
    )
    catalog_payload = catalog.list_assets(
        "Games", kind="image", source_class=EXPECTED_SOURCE_CLASS, limit=200
    )
    if catalog_payload["scan_truncated"] is not False:
        fail("inspector catalog scan was truncated")
    catalog_by_path = {str(item["path"]): item for item in catalog_payload["items"]}
    for capture in captures:
        inspector_relative = str(capture["inspector_path"])
        item = catalog_by_path.get(inspector_relative)
        if item is None:
            fail(f"inspector catalog did not expose {inspector_relative}")
        if item.get("source_class") != EXPECTED_SOURCE_CLASS or item.get("kind") != "image":
            fail(f"inspector catalog classification mismatch: {inspector_relative}")
        if item.get("sha256") != capture["sha256"] or item.get("size_bytes") != capture["size_bytes"]:
            fail(f"inspector catalog identity mismatch: {inspector_relative}")
        resolved = catalog.resolve_asset("Games", "games-generated", inspector_relative)
        if resolved != ARTIFACT_ROOT / inspector_relative:
            fail(f"inspector resolver returned an unexpected path: {inspector_relative}")

    protected = {}
    for relative in (
        "docs/project-state/03_BIELLA_CURRENT_STATE.md",
        "docs/project-state/04_BIELLA_ACTIVE_TASK.md",
        "projects/minitz-games/docs/PRODUCTION.md",
    ):
        path = REPO / relative
        protected[relative] = sha256(path)

    return {
        "task_id": "D01-41",
        "result": "PASS",
        "boundary": "Local visual index and allowlisted inspector-root exposure only; generated media remains unaccepted.",
        "source_revision": {
            "current_commit": current_commit,
            "current_tree": git("rev-parse", "HEAD^{tree}"),
            "producer_commit": PRODUCER_COMMIT,
        },
        "index": {
            "path": "projects/minitz-games/Build/Demo01/D01-041-visual-index.json",
            "sha256": sha256(INDEX_PATH),
            "capture_count": len(captures),
            "status": EXPECTED_SOURCE_CLASS,
            "owner_accepted": False,
        },
        "inspection": {
            "lane": "Games",
            "root_id": "games-generated",
            "source_class": EXPECTED_SOURCE_CLASS,
            "catalog_count": catalog_payload["count"],
            "indexed_count": len(captures),
            "all_indexed_assets_resolved": True,
            "all_indexed_bytes_read_back": True,
            "scan_truncated": catalog_payload["scan_truncated"],
        },
        "assets": observed_assets,
        "external_metadata": {
            "path": "/root/biella/artifacts/games/D01-040/metadata.json",
            "sha256": sha256(METADATA_PATH),
            "status": EXPECTED_SOURCE_CLASS,
        },
        "protected_files": protected,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=f"write the deterministic report to {REPORT_PATH}",
    )
    args = parser.parse_args()
    report = verify()
    if args.write_report:
        REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
