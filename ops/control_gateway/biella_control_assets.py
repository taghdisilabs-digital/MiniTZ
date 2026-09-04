from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SUPPORTED = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".gif"},
    "video": {".mp4", ".webm", ".mov"},
    "audio": {".wav", ".mp3", ".ogg", ".flac"},
    "3d": {".blend", ".fbx", ".obj", ".gltf", ".glb"},
    "unreal": {".uasset", ".umap"},
}
PREVIEWABLE = SUPPORTED["image"] | SUPPORTED["video"] | SUPPORTED["audio"]
MAX_RESULT_LIMIT = 200
DIGEST_LIMIT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class AssetRoot:
    root_id: str
    path: Path
    source_class: str


def asset_kind(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for kind, suffixes in SUPPORTED.items():
        if suffix in suffixes:
            return kind
    return None


def _sha256(path: Path) -> str | None:
    try:
        if path.stat().st_size > DIGEST_LIMIT_BYTES:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


class AssetCatalog:
    def __init__(self, roots: dict[str, list[AssetRoot]], max_scan_files: int = 5000):
        self.roots = {
            lane: [AssetRoot(item.root_id, Path(item.path).resolve(), item.source_class) for item in items]
            for lane, items in roots.items()
        }
        self.max_scan_files = max_scan_files

    def _root(self, lane: str, root_id: str) -> AssetRoot:
        for root in self.roots.get(lane, []):
            if root.root_id == root_id:
                return root
        raise ValueError("asset root unavailable")

    def resolve_asset(self, lane: str, root_id: str, relative_path: str) -> Path:
        root = self._root(lane, root_id)
        candidate = (root.path / relative_path).resolve()
        try:
            candidate.relative_to(root.path)
        except ValueError as exc:
            raise ValueError("asset path outside root") from exc
        if not candidate.is_file() or asset_kind(candidate) is None:
            raise ValueError("asset unavailable")
        return candidate

    def _item(self, lane: str, root: AssetRoot, path: Path) -> dict[str, object]:
        stat = path.stat()
        rel = path.relative_to(root.path).as_posix()
        kind = asset_kind(path)
        return {
            "lane": lane,
            "root_id": root.root_id,
            "path": rel,
            "name": path.name,
            "kind": kind,
            "source_class": root.source_class,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "previewable": path.suffix.lower() in PREVIEWABLE,
            "sha256": _sha256(path),
        }

    def list_assets(self, lane: str, *, kind: str | None = None,
                    source_class: str | None = None, limit: int = 100) -> dict[str, object]:
        if lane not in self.roots:
            raise ValueError("asset lane unavailable")
        if limit < 1 or limit > MAX_RESULT_LIMIT:
            raise ValueError("invalid asset result limit")
        items: list[dict[str, object]] = []
        scanned = 0
        for root in self.roots[lane]:
            if not root.path.is_dir():
                continue
            for path in root.path.rglob("*"):
                if scanned >= self.max_scan_files:
                    break
                if not path.is_file():
                    continue
                scanned += 1
                item_kind = asset_kind(path)
                if item_kind is None:
                    continue
                if kind and item_kind != kind:
                    continue
                if source_class and root.source_class != source_class:
                    continue
                try:
                    items.append(self._item(lane, root, path))
                except OSError:
                    continue
            if scanned >= self.max_scan_files:
                break
        items.sort(key=lambda item: (str(item["modified_at"]), str(item["path"])), reverse=True)
        return {
            "lane": lane,
            "count": min(len(items), limit),
            "scan_count": scanned,
            "scan_truncated": scanned >= self.max_scan_files,
            "items": items[:limit],
        }
