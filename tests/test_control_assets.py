from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ops.control_gateway.biella_control_assets import AssetCatalog, AssetRoot


class AssetCatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.current = base / "current"
        self.history = base / "history"
        self.current.mkdir()
        self.history.mkdir()
        (self.current / "shot.png").write_bytes(b"\x89PNG\r\nasset")
        (self.current / "arena.umap").write_bytes(b"unreal-map")
        (self.current / "ignore.txt").write_text("not an asset")
        (self.history / "old.blend").write_bytes(b"blend")
        self.catalog = AssetCatalog({
            "Games": [
                AssetRoot("games-current", self.current, "CURRENT"),
                AssetRoot("games-history", self.history, "HISTORICAL_RECOVERY"),
            ]
        })

    def tearDown(self):
        self.tmp.cleanup()
    def test_lists_only_supported_assets_with_explicit_source_class(self):
        payload = self.catalog.list_assets("Games", limit=20)
        items = payload["items"]
        self.assertEqual({item["name"] for item in items}, {"shot.png", "arena.umap", "old.blend"})
        by_name = {item["name"]: item for item in items}
        self.assertEqual(by_name["shot.png"]["kind"], "image")
        self.assertTrue(by_name["shot.png"]["previewable"])
        self.assertEqual(by_name["shot.png"]["source_class"], "CURRENT")
        self.assertEqual(by_name["old.blend"]["source_class"], "HISTORICAL_RECOVERY")
        self.assertFalse(by_name["old.blend"]["previewable"])
        self.assertRegex(by_name["shot.png"]["sha256"], r"^[0-9a-f]{64}$")

    def test_filters_and_limit_are_bounded(self):
        payload = self.catalog.list_assets("Games", kind="image", source_class="CURRENT", limit=1)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["name"], "shot.png")
        with self.assertRaises(ValueError):
            self.catalog.list_assets("Games", limit=1000)

    def test_asset_resolution_rejects_traversal_and_unknown_roots(self):
        self.assertEqual(
            self.catalog.resolve_asset("Games", "games-current", "shot.png"),
            self.current / "shot.png",
        )
        with self.assertRaises(ValueError):
            self.catalog.resolve_asset("Games", "games-current", "../history/old.blend")
        with self.assertRaises(ValueError):
            self.catalog.resolve_asset("Games", "missing", "shot.png")
        with self.assertRaises(ValueError):
            self.catalog.resolve_asset("Legacy", "games-current", "shot.png")


if __name__ == "__main__":
    unittest.main()
