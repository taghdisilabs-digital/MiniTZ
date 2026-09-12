import json
import pathlib
import socket
import subprocess
import sys
import time
from contextlib import closing
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIST = ROOT / 'dist'
assert (DIST / 'index.html').is_file()
assert json.loads((DIST / 'deployment.json').read_text())['schema'] == 'biella.website.deployment/v1'
snapshot = json.loads((DIST / 'data' / 'investor-snapshot.json').read_text())
live = {
    'schema': 'biella.public_live_snapshot/v1', 'mode': 'READ_ONLY_OBSERVER',
    'connection': {'state': 'LIVE'},
    'production': {
        'task_id': snapshot['active_task']['id'], 'task_title': snapshot['active_task']['title'],
        'state': 'WAITING', 'active_coder': 'local-qwen',
        'main_coders': {'codex': 'OUT_OF_CREDIT', 'agr': 'NEEDS_MODIFICATION'},
        'progress': {'completed': snapshot['program']['completed_tasks'], 'total': snapshot['program']['total_tasks']},
    },
}

def free_port():
    with closing(socket.socket()) as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

port = free_port()
server = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', str(DIST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(0.4)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for viewport in ({'width': 1440, 'height': 900}, {'width': 390, 'height': 844}):
            page = browser.new_page(viewport=viewport)
            page.route('**/live-api/snapshot', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(live)))
            response = page.goto(f'http://127.0.0.1:{port}/', wait_until='networkidle')
            assert response and response.ok
            assert 'FOUR MONTHS.' in page.locator('h1').inner_text()
            assert page.locator('[data-primary-nav] a').count() == 5
            for month in ('MAY','JUNE','JULY','AUGUST','SEPTEMBER'):
                assert page.locator(f'[data-month="{month}"]').count() == 1
            assert page.locator('[data-project-card]').count() >= 35
            page.get_by_role('button', name='Games').click()
            assert page.locator('[data-project-card]:visible').count() >= 25
            assert page.locator('[data-project-id="g01"]:visible').count() == 1
            assert page.locator('[data-live-state]').inner_text() == 'LIVE · WAITING'
            assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
            page.close()
        archive = browser.new_page(viewport={'width': 1440, 'height': 900})
        r = archive.goto(f'http://127.0.0.1:{port}/archive/', wait_until='networkidle')
        assert r and r.ok
        assert archive.locator('h1').inner_text().startswith('VISUAL ARCHIVE')
        assert archive.locator('[data-media-card]').count() >= 12
        assert archive.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
        archive.close(); browser.close()
    print('BROWSER_QUALIFICATION_PASS desktop=1440x900 mobile=390x844 archive=1')
finally:
    server.terminate(); server.wait(timeout=5)
