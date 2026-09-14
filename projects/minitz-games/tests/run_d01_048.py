#!/usr/bin/env python3
"""Qualify the immutable D01-46 package through the full Demo 01 playable loop.

Each suite launches a fresh archive extraction, outside the editable project.
No cooking, source mutation, publication or production-state changes occur here.
All attempts and runtime media are retained for independent evidence replay.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import tempfile
import time

from run_d01_039 import PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output

PACKAGE = Path('/root/biella/artifacts/games/D01-46/BiellaGames-Linux-x64-D01-46.tar.zst')
PACKAGE_SHA = 'c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8'
PACKAGE_COMMIT = '00c7243077403d9ebfb812318cd23a3a5b13641f'
SUITES = (
    ('core-nullrhi', 'DeterministicPlaytest', 'nullrhi'),
    ('core-vulkan', 'DeterministicPlaytest', 'vulkan'),
    ('shared', 'SharedInteraction', 'vulkan'),
    ('pressure', 'PressureResponses', 'vulkan'),
    ('navigation', 'RivalNavigation', 'vulkan'),
    ('visual', 'VisualReadability', 'vulkan'),
    ('feedback', 'EventFeedback', 'vulkan'),
)


def source_identities():
    tracked = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', 'Source', 'Config', 'Content', 'Plugins', 'BiellaGames.uproject'],
        cwd=PROJECT).decode().split('\0')
    paths = {PROJECT / name for name in tracked if name}
    return [file_identity(path) for path in sorted(paths) if path.is_file()]


def package_members(extraction):
    return [file_identity(extraction / name) for name in (
        'Linux/BiellaGames.sh', 'Linux/BiellaGames/Binaries/Linux/BiellaGames',
        'Linux/BiellaGames/Content/Paks/BiellaGames-Linux.pak')]


def launch(command, cwd, output, timeout):
    start = time.monotonic()
    timed_out = False
    with output.open('xb') as stream:
        process = subprocess.Popen(command, cwd=cwd, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            rc = process.wait(timeout=10)
    return {'command': command, 'cwd': str(cwd), 'pid': process.pid,
            'returncode': rc, 'timed_out': timed_out, 'timeout_seconds': timeout,
            'elapsed_seconds': round(time.monotonic() - start, 3), 'log': file_identity(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    if not 0 < args.timeout <= 240:
        parser.error('timeout must be positive and at most 240 seconds')
    account = pwd.getpwnam('unreal') if os.geteuid() == 0 else pwd.getpwuid(os.geteuid())
    prefix = ['runuser', '-u', account.pw_name, '--'] if os.geteuid() == 0 else []
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    attempt = PROJECT / 'Build/Demo01/D01-048-runs' / stamp
    media = Path('/root/biella/artifacts/games/D01-048') / stamp
    ensure_runtime_output(attempt, account)
    ensure_runtime_output(media, account)
    protected = [PROJECT.parents[1] / 'docs/project-state/03_BIELLA_CURRENT_STATE.md',
                 PROJECT.parents[1] / 'docs/project-state/04_BIELLA_ACTIVE_TASK.md',
                 PROJECT / 'docs/PRODUCTION.md']
    report = {'task_id': 'D01-48', 'result': 'FAIL', 'created_utc': stamp,
              'visual_status': 'GENERATED_DRAFT', 'package': file_identity(args.package.resolve()),
              'package_source_commit': PACKAGE_COMMIT, 'revision': source_revision(),
              'runner': file_identity(Path(__file__)),
              'source_before': source_identities(),
              'protected_before': [file_identity(path) for path in protected],
              'runs': [], 'scope': 'Linux x64 Development package; fixed 60 Hz core simulation; no native FPS or Windows shipping claim'}
    report['package_source_diff'] = subprocess.check_output(
        ['git', 'diff', '--name-only', PACKAGE_COMMIT, '--', 'Source', 'Config', 'Content', 'Plugins', 'BiellaGames.uproject'],
        cwd=PROJECT, text=True).splitlines()
    report_path = attempt / 'validation.json'
    print(f'D01-48 evidence: {report_path}', flush=True)

    def save():
        write_json(report_path, report)

    save()
    try:
        assert report['package']['sha256'] == PACKAGE_SHA, 'Package differs from completed D01-46/47 identity'
        assert not report['package_source_diff'], 'Gameplay inputs changed since packaged source commit'
        for name, suite, renderer in SUITES:
            output = attempt / name
            ensure_runtime_output(output, account)
            extraction = Path(tempfile.mkdtemp(prefix=f'biella-d01-48-{name}-'))
            extraction.chmod(0o755)
            subprocess.run(['tar', '--zstd', '-xf', str(args.package.resolve()), '-C', str(extraction)], check=True, timeout=60)
            # The runtime needs its own Saved/ tree. Ownership change is confined
            # to this invocation's freshly created archive extraction.
            if os.geteuid() == 0:
                subprocess.run(['chown', '-R', f'{account.pw_uid}:{account.pw_gid}', str(extraction)], check=True, timeout=30)
            run = {'name': name, 'suite': suite, 'renderer': renderer,
                   'extraction': str(extraction), 'package_members_before': package_members(extraction), 'captures': []}
            report['runs'].append(run)
            command = prefix + (['xvfb-run', '-a', '-s', '-screen 0 1280x720x24'] if renderer == 'vulkan' else [])
            command += [str(extraction / 'Linux/BiellaGames.sh')]
            command += ['-nullrhi'] if renderer == 'nullrhi' else [
                '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720']
            command += ['-unattended', '-nosplash', '-NoAsyncLoadingThread', '-stdout', '-FullStdOutLogOutput',
                        f'-AbsLog={output}/engine.log',
                        f'-ExecCmds=Automation RunTests BiellaGames.Demo01.{suite}; SoftQuit']
            # Time-dependent AI/navigation suites use their normal runtime tick.
            # Only the core and short feedback effects require fixed simulation.
            if name.startswith('core-'):
                command += [f'-BiellaTelemetry={output}/telemetry.jsonl', '-BiellaPlaytestSeed=1337', '-UseFixedTimeStep', '-FPS=60']
            if name in ('visual', 'feedback'):
                captures = media / name
                ensure_runtime_output(captures, account)
                option = 'BiellaReadabilityOutput' if name == 'visual' else 'BiellaFeedbackOutput'
                command += [f'-{option}={captures}']
            if name == 'feedback':
                command += ['-AudioMixer', '-DeterministicAudio', '-UseFixedTimeStep', '-FPS=60']
            else:
                command += ['-nosound']
            write_json(output / 'command.json', {'command': command, 'cwd': str(extraction)})
            save()
            run['runtime'] = launch(command, extraction, output / 'stdout.log', args.timeout)
            run['engine_log'] = file_identity(output / 'engine.log') if (output / 'engine.log').exists() else None
            run['package_members_after'] = package_members(extraction)
            if (output / 'telemetry.jsonl').exists():
                run['telemetry'] = file_identity(output / 'telemetry.jsonl')
            if name in ('visual', 'feedback'):
                run['captures'] = [file_identity(path) for path in sorted(captures.iterdir()) if path.suffix in ('.png', '.wav')]
            save()
            print(f'{name}: process exit={run["runtime"]["returncode"]}, media={len(run["captures"])}', flush=True)
        report['source_after'] = source_identities()
        report['protected_after'] = [file_identity(path) for path in protected]
        assert report['runner'] == file_identity(Path(__file__)), 'Runner changed during execution'
        report['verification_tools'] = [file_identity(PROJECT / 'tests' / name) for name in (
            'verify_d01_048.py', 'verify_d01_031.py', 'verify_d01_033.py',
            'verify_d01_039.py', 'run_d01_039.py', 'run_d01_042.py')]
        from verify_d01_048 import verify
        report['verification'] = verify(report)
        report['result'] = 'PASS'
    except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    finally:
        save()
    print(json.dumps({'task_id': 'D01-48', 'result': report['result'], 'validation': str(report_path), 'error': report.get('error')}, indent=2))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
