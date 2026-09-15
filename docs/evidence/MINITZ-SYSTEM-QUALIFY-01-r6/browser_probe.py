"""Exercise current browser adapter against an isolated headless Chromium fixture."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from minitz_os.source import source_manifest

repo = Path('/workspace/repo')
source = source_manifest(repo)
path = repo / 'tests/test_p2_07_browser_adapter.py'
spec = importlib.util.spec_from_file_location('qualification_real_browser', path)
test = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = test
spec.loader.exec_module(test)
assert os.environ['MINITZ_TEST_BROWSER_IMAGE_ID'] == test._REAL_IMAGE_DIGEST

@contextmanager
def controller(_temporary):
    yield os.environ['MINITZ_TEST_BROWSER_ORIGIN']

test._webdriver_container = controller
started = time.monotonic()
with tempfile.TemporaryDirectory(prefix='minitz-browser-qualification-') as temporary:
    test.test_t11_real_pinned_chromium_navigation_actions_upload_download_screenshot_and_submit(Path(temporary))
assert source_manifest(repo)['source_sha256'] == source['source_sha256']
print(json.dumps({'state': 'PASS', 'source_sha256': source['source_sha256'],
    'source_unchanged': True, 'test_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'browser_image_id': test._REAL_IMAGE_DIGEST, 'browser_version_asserted': '151.0.7922.108',
    'elapsed_seconds': time.monotonic() - started, 'image_boot_executed': False,
    'scope': 'Isolated headless browser and local fixture site; navigation, DOM inspection, typing, selection, click, upload, screenshot bytes, download, missing-target rejection, single submission, close; no user browser or external website'}, indent=2))
