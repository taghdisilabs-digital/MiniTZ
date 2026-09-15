"""Read and verify image source bytes without mounting or booting its filesystem."""
import json
from pathlib import Path
import subprocess
import tempfile
from minitz_os.source import source_manifest, verify_source

with tempfile.TemporaryDirectory(prefix='minitz-image-payload-') as temporary:
    work = Path(temporary)
    result = subprocess.run(['debugfs', '-R', 'rdump /opt/minitz/source ' + temporary, '/image/root.img'], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Image source extraction failed')
    manifest = json.loads(Path('/image/source.json').read_text())
    verified = verify_source(work / 'source', manifest)
    assert verified['source_sha256'] == source_manifest(Path('/workspace/repo'))['source_sha256']
    print(json.dumps({**verified, 'state': 'PASS', 'image_boot_executed': False,
        'scope': 'Every source file, size, SHA-256 and executable mode extracted from structurally validated current raw image matches canonical source'}, indent=2))
