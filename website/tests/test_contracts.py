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
        html = (ROOT / 'src/live/theatre/index.html').read_text()
        loader = (ROOT / 'src/live/index.html').read_text()
        app = (ROOT / 'src/live/app.js').read_text()
        for token in ('MiniTZ OS', 'I can.', 'photo-hero', 'id="system"', 'id="locker"', 'id="final-film"', 'Play the film', 'I couldn’t code.'):
            self.assertIn(token, html)
        for token in ('/live-api/snapshot', '/live-api/events', 'EventSource', '/data/locker-index.json'):
            self.assertIn(token, app)
        for forbidden in ('<canvas', 'visual-grid', 'scanline', 'background-stack'):
            self.assertNotIn(forbidden, html)
        self.assertIn("const target='/live/theatre/index.html'", loader)
        self.assertNotIn("rootPath?'/portfolio/index.html'", loader)

    def test_public_origin_maps_minitz_deep_links_to_live_page(self):
        server = (ROOT / 'ops/static_server.py').read_text()
        for token in ("DASHBOARD_HOST='taghdisilabs.digital'", "'/locker'", "'/founder'", "'/system'", "'/experience'", "'/capabilities'", "'/final-film'", "self.path='/live/index.html'"):
            self.assertIn(token, server)

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
        html = (ROOT / 'dist/live/theatre/index.html').read_text()
        app_match = re.search(r'/live/app\.([0-9a-f]{12})\.js', html)
        css_match = re.search(r'/live/styles\.([0-9a-f]{12})\.css', html)
        self.assertIsNotNone(app_match)
        self.assertIsNotNone(css_match)
        self.assertTrue((ROOT / f'dist/live/app.{app_match.group(1)}.js').is_file())
        self.assertTrue((ROOT / f'dist/live/styles.{css_match.group(1)}.css').is_file())

    def test_portfolio_site_has_simple_five_destination_information_architecture(self):
        required = [
            'src/index.html','src/styles.css','src/app.js',
            'src/archive/index.html','src/archive/styles.css','src/archive/app.js',
            'content/portfolio-index.json','content/portfolio-media.json',
            'src/live/index.html','scripts/build.mjs','AGENTS.md',
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).is_file(), rel)
        index = (ROOT / 'src/index.html').read_text()
        for token in ('FOUR MONTHS.', 'Home', '4 Months', 'Projects', 'Visual Archive', 'Live MiniTZ'):
            self.assertIn(token, index)
        self.assertIn('/archive/', index)
        self.assertIn('/live/', index)
        self.assertNotIn('years of', index.lower())

    def test_portfolio_index_recovers_g01_g25_without_inventing_g26(self):
        data = json.loads((ROOT / 'content/portfolio-index.json').read_text())
        items = {item['id']: item for item in data['items']}
        for number in range(1, 26):
            self.assertIn(f'g{number:02d}', items)
        self.assertNotIn('g26', items)
        self.assertNotEqual(items['g22']['status'], 'OWNER_ACCEPTED_COMPLETE_GAME')
        self.assertNotEqual(items['g25']['status'], 'OWNER_ACCEPTED_COMPLETE_GAME')
        self.assertIn('four months', data['timeframe']['label'].lower())

    def test_portfolio_media_manifest_is_explicit_and_build_copies_every_item(self):
        manifest = json.loads((ROOT / 'content/portfolio-media.json').read_text())
        self.assertGreaterEqual(len(manifest['items']), 12)
        for item in manifest['items']:
            self.assertTrue(item['project_id'])
            self.assertTrue(item['source_path'])
            self.assertTrue(item['public_path'].startswith('/portfolio-media/'))
            self.assertIn(item['status'], {'VERIFIED','HISTORICAL_EVIDENCE','FAILED_ITERATION','PARTIALLY_VERIFIED'})
        subprocess.run(['node', 'scripts/build.mjs'], cwd=ROOT, check=True, capture_output=True, text=True)
        for item in manifest['items']:
            self.assertTrue((ROOT / 'dist' / item['public_path'].lstrip('/')).is_file(), item['public_path'])
        self.assertTrue((ROOT / 'dist/data/portfolio-index.json').is_file())
        self.assertTrue((ROOT / 'dist/data/portfolio-media.json').is_file())
        self.assertTrue((ROOT / 'dist/archive/index.html').is_file())


    def test_public_root_routes_to_minitz_while_portfolio_stays_separate(self):
        loader = (ROOT / 'src/live/index.html').read_text()
        theatre = (ROOT / 'src/live/theatre/index.html').read_text()
        build = (ROOT / 'scripts/build.mjs').read_text()
        self.assertIn("const target='/live/theatre/index.html'", loader)
        self.assertNotIn("rootPath?'/portfolio/index.html'", loader)
        self.assertIn('resolve(dist,"portfolio")', build)
        self.assertIn('MiniTZ OS', theatre)
        self.assertIn('I can.', theatre)
        self.assertIn('resolve(dist,"live","theatre","index.html")', build)

if __name__ == '__main__': unittest.main()
