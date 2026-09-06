#!/usr/bin/env python3
"""Incremental Linux Development game build using the verified source-engine route.

UE 5.8.2's installed distribution omits monolithic precompiled manifests.
Keep all objects and source; temporarily preserve its installed marker while
using the source build, then restore and verify it even on build failure.
Run serially with other Unreal builds/cooks on this workstation.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import time
from run_d01_039 import PROJECT, file_identity, source_revision, write_json

ENGINE = Path('/opt/unreal/UE_5.8.2/Engine')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    marker = ENGINE/'Build/InstalledBuild.txt'
    held = ENGINE/'Build/InstalledBuild.txt.D03-01-preserved'
    lock = Path('/mnt/biella-extra/biella-runtime/codex-production/D03-01-unreal-build.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert marker.is_file() and not held.exists(), 'Installed marker must be present and not already held'
    before = [file_identity(f) for f in sorted((PROJECT/'Source').rglob('*')) if f.is_file()]
    write_json(out/'inputs-before.json', before)
    report = dict(task_id='D03-01', result='FAIL', revision=source_revision(),
                  marker_before=file_identity(marker), started=datetime.now(timezone.utc).isoformat())
    write_json(out/'result.json', report)
    command = [str(ENGINE/'Build/BatchFiles/Linux/Build.sh'), 'BiellaGames', 'Linux', 'Development',
               f'-Project={PROJECT}/BiellaGames.uproject', '-WaitMutex', '-NoUBA',
               '-NoHotReloadFromIDE', '-NoUBTMakefiles']
    write_json(out/'command.json', command)
    start = time.monotonic()
    try:
        marker.rename(held)
        with (out/'build.log').open('xb') as stream:
            result = subprocess.run(command, cwd=PROJECT, stdout=stream, stderr=subprocess.STDOUT)
        report['returncode'] = result.returncode
        assert result.returncode == 0, 'Native game build failed; inspect build.log'
        binary = PROJECT/'Binaries/Linux/BiellaGames'
        binary.chmod(0o755)
        report['binary'] = file_identity(binary)
        report['receipt'] = file_identity(PROJECT/'Binaries/Linux/BiellaGames.target')
        report['result'] = 'PASS'
    except (AssertionError, OSError) as error:
        report['error'] = str(error)
    finally:
        if held.exists():
            assert not marker.exists(), 'Unexpected concurrent marker recreation; preserve both identities'
            held.rename(marker)
        report['marker_after'] = file_identity(marker)
        after = [file_identity(f) for f in sorted((PROJECT/'Source').rglob('*')) if f.is_file()]
        write_json(out/'inputs-after.json', after)
        report['inputs_unchanged'] = before == after
        report['elapsed_seconds'] = time.monotonic()-start
        if before != after or report['marker_before'] != report['marker_after']:
            report.update(result='FAIL', error='Source or installed marker changed')
        write_json(out/'result.json', report)
        if report['result'] != 'PASS':
            with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(task_id='D03-01', time=datetime.now(timezone.utc).isoformat(),
                                            type='native_game_build', status='CONTINUE',
                                            diagnostics=report.get('error'), evidence=str(out)))+'\n')
    print(json.dumps(dict(result=report['result'], output=str(out), error=report.get('error'))))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
