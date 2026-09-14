import json
import os
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parent
COMPLETE = {'COMPLETE', 'COMPLETE_ALREADY', 'COMPLETE_REUSE_REQUIRED'}

class InvestorDeckTests(unittest.TestCase):
    def test_build_emits_live_snapshot_from_canonical_ledger(self):
        env = os.environ | {'MINITZ_SOURCE_COMMIT':'abc123def456','MINITZ_SOURCE_TREE':'tree123'}
        subprocess.run(['node','scripts/build.mjs'], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
        snapshot = json.loads((ROOT/'dist/data/investor-snapshot.json').read_text())
        ledger = json.loads((REPO/'docs/task-program/D_TASK_LEDGER.json').read_text())
        tasks = ledger['tasks']
        self.assertEqual(snapshot['program']['total_tasks'], len(tasks))
        self.assertEqual(snapshot['program']['completed_tasks'], sum(t['status'] in COMPLETE for t in tasks))
        self.assertEqual(snapshot['first_playable'], {'completed_tasks':50,'total_tasks':50,'status':'VERIFIED_COMPLETE'})
        import re
        active_text = (REPO/'docs/project-state/04_MINITZ_ACTIVE_TASK.md').read_text()
        active_id = re.search(r'^\s*id:\s*(\S+)', active_text, re.M).group(1)
        self.assertEqual(snapshot['active_task']['id'], active_id)
        self.assertEqual(snapshot['source']['commit'], 'abc123def456')
        self.assertIn('docs/task-program/D_TASK_LEDGER.json', snapshot['evidence_sources'])

    def test_public_investor_route_is_live_not_pixel_metric_copy(self):
        page = (ROOT/'src/investors/index.html').read_text()
        app = (ROOT/'src/investors/app.js').read_text()
        self.assertNotIn('105 / 219', page)
        self.assertNotIn('14h 55m', page)
        self.assertIn('data-live="program-complete"', page)
        self.assertIn('investor-snapshot.json', app)
        self.assertIn('cache:\'no-store\'', app)
        self.assertIn('/live-api/snapshot', app)
        self.assertIn('/live-api/events', app)
        self.assertIn('EventSource', app)
        self.assertNotRegex(app, r'setInterval\([^,]+,\s*60000\)')


    def test_public_fundraising_copy_is_achievement_first_and_production_true(self):
        home = (ROOT/'src/index.html').read_text()
        investor = (ROOT/'src/investors/index.html').read_text()
        public = home + '\n' + investor
        banned = (
            'does not manufacture it','without pretending','EVIDENCE-GATED','RUNTIME-GATED',
            'Registered, not fabricated','Remote identity or no claim','ACCEPTANCE BOUNDARY',
            'evidence before claims','remain evidence-gated','without inventing a speed claim',
            'No fabricated ARR','pre-commercial','not currently bound to canonical live evidence',
        )
        for phrase in banned: self.assertNotIn(phrase, public)
        self.assertIn('FOUR MONTHS.', home)
        for phrase in (
            'Founder-directed company execution engine',
            'Product proof established. Commercial expansion is the next multiplier.',
            'Capital accelerates an operating system already producing',
        ): self.assertIn(phrase, investor)

    def test_live_deploy_source_is_in_single_repo_and_has_no_external_copy_overlay(self):
        deployer = (ROOT/'ops/deploy_live.py').read_text()
        self.assertNotIn('last_overlay_digest', deployer)
        self.assertNotRegex(deployer, r'\boverlay\b')
        self.assertIn("REPO=Path('/root/biella/repos/biella-engine')", deployer)
        self.assertIn('FUNDRAISING_COPY', deployer)
        self.assertNotIn('website-fundraising-overlay', deployer)
        self.assertNotIn('codex', deployer.lower())
        self.assertNotIn('ollama', deployer.lower())
        service = (ROOT/'ops/biella-website-live-deploy.service').read_text()
        self.assertIn('RequiresMountsFor=/mnt/biella-extra', service)

    def test_live_deploy_handles_missing_remote_main_without_crashing(self):
        deployer = (ROOT/'ops/deploy_live.py').read_text()
        self.assertIn('REMOTE_MAIN_MISSING', deployer)
        self.assertNotIn("run(['git','ls-remote','origin','refs/heads/main']).split()[0]", deployer)

    def test_live_deploy_remote_status_does_not_turn_transport_loss_into_local_deploy_stall(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("website_deploy_live", ROOT/'ops/deploy_live.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        original = module.run
        try:
            module.run = lambda args, cwd=module.REPO, env=None: "" if args[:2] == ['git','ls-remote'] else original(args, cwd=cwd, env=env)
            status, reason, remote = module.remote_sync_state("local-head")
        finally:
            module.run = original
        self.assertEqual((status, reason, remote), ('NEEDS_MODIFICATION', 'REMOTE_MAIN_MISSING', None))
        deployer = (ROOT/'ops/deploy_live.py').read_text()
        self.assertIn('LOCAL_CANONICAL_DEPLOY_CONTINUES', deployer)

    def test_visual_reference_manifest_is_exact_and_non_authoritative_for_metrics(self):
        manifest = json.loads((ROOT/'content/investor-deck-manifest.json').read_text())
        self.assertEqual(manifest['status'], 'ACCEPTED_VISUAL_REFERENCE')
        self.assertEqual(len(manifest['visual_assets']), 10)
        self.assertFalse(manifest['content_policy']['pixel_text_is_metric_authority'])
        for item in manifest['visual_assets']:
            path = ROOT/'reference/investor-deck-v1'/item['filename']
            self.assertTrue(path.is_file(), item['filename'])
            import hashlib
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['sha256'])

    def test_production_workflow_refreshes_after_durable_evidence_commits(self):
        workflow = (REPO/'.github/workflows/website-production.yml').read_text()
        self.assertIn('branches: [main]', workflow)
        self.assertIn("'website/**'", workflow)
        for source in ('docs/project-state/03_MINITZ_CURRENT_STATE.md','docs/project-state/04_MINITZ_ACTIVE_TASK.md','projects/minitz-games/docs/PRODUCTION.md'):
            self.assertNotIn(source, workflow)

if __name__ == '__main__': unittest.main()
