"""Observe repaired attachment path without restarting MiniTZ or starting a task."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

repo = Path('/workspace/repo')
sys.path.insert(0, str(repo / 'src'))
from minitz_os.source import source_manifest
path = repo / 'ops/workstation/minitz-os-sandbox/attachments.py'
spec = importlib.util.spec_from_file_location('qualification_attachments', path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
program_path = Path(os.environ['MINITZ_TASK_PROGRAM_PATH'])
before = hashlib.sha256(program_path.read_bytes()).hexdigest()
source = source_manifest(repo)
server, control = api.attach_control({})
assert server is None and control['state'] == 'EXISTING_GATEWAY_ATTACHED'
coder = api.CoderTransport(Path(os.environ['MINITZ_CODEX_BIN']), Path('/state/runtime/codex'), subprocess.DEVNULL)
try:
    protocol = api.qualify_coder_protocol(coder.rpc, coder.notify)
finally:
    coder.close()
assert protocol['state'] in {'PROTOCOL_AUTH_ATTACHED', 'PROTOCOL_LOCAL_READY'}
result = {
    'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'state': 'TASK_LOCAL_ATTACHMENTS_PASSED', 'control': control, 'coder': protocol,
    'source_sha256': source['source_sha256'], 'attachments_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'installed_runtime_source_sha256': json.loads(Path('/etc/minitz/source.json').read_text())['source_sha256'],
    'task_program_sha256_before': before,
    'task_program_sha256_after': hashlib.sha256(program_path.read_bytes()).hexdigest(),
    'source_unchanged': source_manifest(repo)['source_sha256'] == source['source_sha256'],
    'image_boot_executed': False, 'runtime_restarted': False,
    'scope': 'Current canonical attachment implementation in existing Ubuntu 26.04 runtime; prior startup failure retained separately',
}
assert result['task_program_sha256_after'] == before and result['source_unchanged']
print(json.dumps(result, indent=2))
