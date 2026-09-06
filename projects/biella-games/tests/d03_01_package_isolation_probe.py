#!/usr/bin/env python3
"""Record package namespace facts before replacing this process with the runtime."""
import json
import os
from pathlib import Path
import sys


def main():
    hidden = ['/opt/unreal', '/root/biella', '/mnt/biella-extra',
              '/home/unreal/.cache/UnrealEngine']
    observations = {path: Path(path).exists() for path in hidden}
    report = dict(uid=os.getuid(), gid=os.getgid(), hidden_path_exists=observations,
                  cwd=os.getcwd(), package_readable=Path('/tmp/package/BiellaGames.sh').is_file(),
                  state_writable=os.access('/tmp/state', os.W_OK),
                  package_writable=os.access('/tmp/package', os.W_OK),
                  network_interfaces=sorted(line.split(':', 1)[0].strip()
                                            for line in Path('/proc/net/dev').read_text().splitlines()
                                            if ':' in line),
                  command=sys.argv[1:])
    Path('/tmp/evidence/isolation-probe.json').write_text(json.dumps(report, indent=2)+'\n')
    Path('/tmp/evidence/isolation-mounts.txt').write_text(Path('/proc/self/mountinfo').read_text())
    assert report['uid'] != 0 and not any(observations.values()), 'Source/editor/cache isolation failed'
    assert report['package_readable'] and report['state_writable'] and not report['package_writable'], 'Package mount policy failed'
    assert report['network_interfaces'] == ['lo'], 'Network namespace is not isolated'
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
