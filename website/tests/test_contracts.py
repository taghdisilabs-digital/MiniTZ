import csv
import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class WebsiteContractTests(unittest.TestCase):
    def test_visual_asset_registry_has_exact_50_slots_and_no_false_migration(self):
        with (ROOT / 'content/website-visual-assets.csv').open(newline='') as f:
            assets = list(csv.DictReader(f))
        self.assertEqual([a['id'] for a in assets], [f'{i:02d}' for i in range(1, 51)])
        self.assertEqual(len(assets), 50)
        self.assertTrue(all(a['migration_status'] == 'SOURCE_BYTES_UNRESOLVED' for a in assets))
        audit = json.loads((ROOT / 'content/asset-resolution.json').read_text())
        self.assertEqual(audit['exact_drive_filename_matches'], 0)
        self.assertEqual(audit['requested_canonical_filenames'], 50)

    def test_game_runtime_media_lane_only_publishes_runtime_accepted_media(self):
        data = json.loads((ROOT / 'content/game-runtime-media.json').read_text())
        self.assertEqual(data['lane'], 'BU-16_GAME_RUNTIME_MEDIA')
        for item in data['published_items']:
            self.assertEqual(item['status'], 'ACCEPTED_RUNTIME_MEDIA')
            self.assertTrue(item['game_source_commit'])
            self.assertTrue(item['game_source_tree'])
            self.assertTrue(item['runtime_build_id'])
            self.assertTrue(item['artifact_sha256'])
            self.assertEqual(item['acceptance_authority'], 'Mahdi Taghdisi')

    def test_live_page_is_minitz_i_can_brand_campaign(self):
        html = (ROOT / 'src/live/index.html').read_text()
        app = (ROOT / 'src/live/app.js').read_text()
        for token in ('MiniTZ OS', 'I can.', 'photo-hero', 'id="system"', 'id="locker"', 'id="final-film"', 'Play the film', 'I couldn’t code.'):
            self.assertIn(token, html)
        for token in ('/live-api/snapshot', '/live-api/events', 'EventSource', '/data/locker-index.json'):
            self.assertIn(token, app)
        for forbidden in ('<canvas', 'visual-grid', 'scanline', 'background-stack'):
            self.assertNotIn(forbidden, html)

    def test_minitz_public_subdomain_routes_to_live_theatre_without_replacing_apex(self):
        server = (ROOT / 'ops/static_server.py').read_text()
        tunnel = (ROOT / 'ops/biella-public.yml').read_text()
        self.assertIn('minitz.taghdisilabs.digital', server)
        self.assertIn('/live/', server)
        self.assertIn('hostname: minitz.taghdisilabs.digital', tunnel)
        self.assertIn('^/live-api/.*', tunnel)
        self.assertIn('hostname: biellagames.dev', tunnel)

    def test_build_fingerprints_live_assets_so_browser_cache_cannot_hide_updates(self):
        subprocess.run(['node', 'scripts/build.mjs'], cwd=ROOT, check=True, capture_output=True, text=True)
        html = (ROOT / 'dist/live/index.html').read_text()
        app_match = re.search(r'/live/app\.([0-9a-f]{12})\.js', html)
        css_match = re.search(r'/live/styles\.([0-9a-f]{12})\.css', html)
        self.assertIsNotNone(app_match)
        self.assertIsNotNone(css_match)
        self.assertTrue((ROOT / f'dist/live/app.{app_match.group(1)}.js').is_file())
        self.assertTrue((ROOT / f'dist/live/styles.{css_match.group(1)}.css').is_file())

    def test_bu07_scaffold_has_real_entrypoint_build_and_governance(self):
        required = ['src/index.html','src/styles.css','src/app.js','src/live/index.html','src/live/styles.css','src/live/app.js','scripts/build.mjs','package.json','AGENTS.md','wrangler.jsonc','content/website-visual-assets.csv','content/asset-resolution.json','content/game-runtime-media.json']
        for rel in required: self.assertTrue((ROOT / rel).is_file(), rel)
        index = (ROOT / 'src/index.html').read_text()
        app = (ROOT / 'src/app.js').read_text()
        self.assertIn('/live/', index)
        self.assertIn('READ-ONLY VPS SHOWCASE', index)
        self.assertLessEqual(index.count('<section'), 3)
        self.assertIn('/live-api/snapshot', app)
        self.assertIn('/live-api/events', app)
        self.assertIn('EventSource', app)
        self.assertNotIn('setInterval(refreshLive,60000)', app)
        self.assertNotIn('POST', app)
        self.assertIn('resolve(dist,"live")', (ROOT / 'scripts/build.mjs').read_text())

if __name__ == '__main__': unittest.main()
