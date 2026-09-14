#!/usr/bin/env python3
"""D17-01 raw route observation using an exact verified installed package.

This creates evidence, not an acceptance verdict. A short probe, terminal screen,
or successful capture never qualifies the required 10–20 minute AAA slice.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import pwd
import shutil
import subprocess

from run_d08_01_release import current, digest, identity, now, write, LEDGER, source_manifest
from run_d01_039 import PROJECT, source_revision
from run_d01_042 import ensure_runtime_output
from run_d01_044 import monitor, host_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-id', choices=('D17-01', 'D17-02'), default='D17-01')
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--width', type=int, choices=(1280, 1920), default=1280)
    parser.add_argument('--install-root', type=Path,
                        default=Path('/mnt/biella-extra/biella-runtime/d08-01-install'))
    parser.add_argument('--native-build', type=Path,
                        help='Passing task-scoped native build; unchanged cooked content is reused')
    args = parser.parse_args()
    assert 5 <= args.seconds <= 1200
    output = args.output.resolve()
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(output, account)
    height = 720 if args.width == 1280 else 1080
    state = Path('/mnt/biella-extra/biella-runtime') / args.task_id.lower() / output.name
    ensure_runtime_output(state, account)
    for name in ('home', 'xdg-cache', 'xdg-config', 'user'):
        ensure_runtime_output(state / name, account)
    try:
        directory, manifest = current(args.install_root)
        resolved = dict(schema='biella.d17.resolved_runtime/v1',
                        base_package_id=manifest['package_id'], files=manifest['files'])
        native = None
        if args.native_build:
            source = source_manifest(args.native_build.resolve(), output / 'native-source.json')
            source.update(task_id=args.task_id, schema='biella.d17.source_build/v1')
            write(output / 'native-source.json', source)
            baseline = ('Build/AAA/D17-01/build/package-16/source-build.json' if args.task_id == 'D17-02'
                        else 'Build/Release/D08-01/source-build-manifest.json')
            previous = json.loads((PROJECT / baseline).read_text())
            before = {r['path']: r for r in previous['material_inputs']}
            after = {r['path']: r for r in source['material_inputs']}
            changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
            permitted = ({'Source/BiellaGames/Private/BiellaPlaytestTelemetry.cpp',
                          'Source/BiellaGames/Private/BiellaTraversalTelemetry.cpp',
                          'Source/BiellaGames/Public/BiellaPlaytestTelemetry.h',
                          'Source/BiellaGames/Private/BiellaGamesCharacter.cpp',
                          'Source/BiellaGames/Private/BiellaWorldContinuity.cpp'} if args.task_id == 'D17-02'
                         else {'Source/BiellaGames/Private/BiellaGameplayHUD.cpp'})
            assert changed and set(changed) <= permitted, changed
            if args.task_id == 'D17-02':
                assert manifest['package_id'] == '3434ab980ea68750798b9276a135d06b8b50adeb33faf02ef7c714cfc88e8849'
            native = Path('/root/biella/artifacts/games') / args.task_id / source['binary']['sha256'] / 'BiellaGames'
            native.parent.mkdir(parents=True, exist_ok=True)
            if not native.exists():
                shutil.copy2(source['binary']['path'], native)
            binary_identity = identity(native)
            assert binary_identity['sha256'] == source['binary']['sha256']
            resolved.update(native_build=identity(args.native_build / 'result.json'),
                            native_source=identity(output / 'native-source.json'),
                            changed_material_inputs=changed,
                            cook_reuse='Content, configuration, serialized properties and shaders unchanged; native methods and nonserialized telemetry only',
                            native_delta=binary_identity,
                            files=[dict(binary_identity, path=manifest['binary'], executable=True)
                                   if row['path'] == manifest['binary'] else row for row in manifest['files']])
        if args.task_id == 'D17-02' and not native:
            package_source = manifest['source_manifest']
            assert identity(package_source['path']) == package_source, 'Installed source receipt changed'
            shutil.copy2(package_source['path'], output / 'native-source.json')
            source = json.loads((output / 'native-source.json').read_text())
            assert source['material_input_digest'] == manifest['source_material_digest']
            resolved['native_source'] = identity(output / 'native-source.json')
        resolved['runtime_id'] = digest(resolved)
        write(output / 'resolved-package.json', resolved)
        write(output / 'package-verification.json', {
            'status': 'EXACT_MEMBERSHIP_BYTES_PERMISSIONS_VERIFIED',
            'verified_at': now(), 'installed_payload': str(directory / 'payload'),
            'package_id': manifest['package_id'],
            'manifest': identity(directory / 'manifest.json'),
            'binary': identity(directory / 'payload' / manifest['binary']),
            'configuration': manifest['configuration'], 'platform': manifest['platform'],
            'source_revision_at_capture': source_revision(),
            'scope': 'Byte-verified Linux Development package; not visual acceptance or Win64 Shipping'})
        driver = PROJECT / 'tests/d17_01_raw_input.py'
        inputs = {'driver': identity(driver), 'plan': identity(args.plan),
                  'runner': identity(Path(__file__))}
        if args.task_id == 'D17-02':
            inputs['route_controller'] = identity(PROJECT / 'tests/d17_02_route_input.py')
        snapshots = output / 'input-source'
        snapshots.mkdir()
        for item in inputs.values():
            source_path = Path(item['path'])
            snapshot = snapshots / source_path.name
            shutil.copy2(source_path, snapshot)
            item['snapshot'] = identity(snapshot)
        write(output / 'inputs.json', inputs)
        write(output / 'host.json', host_identity())
        command = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--dev-bind', '/dev', '/dev',
                   '--tmpfs', '/root', '--tmpfs', '/opt', '--tmpfs', '/home', '--tmpfs', '/mnt',
                   '--tmpfs', '/tmp', '--chmod', '1777', '/tmp',
                   '--tmpfs', '/var/tmp', '--chmod', '1777', '/var/tmp',
                   '--tmpfs', '/var/cache', '--tmpfs', '/run', '--unshare-net', '--unshare-ipc',
                   '--ro-bind', str(directory / 'payload'), '/tmp/package',
                   '--bind', str(state), '/tmp/state', '--bind', str(state / 'home'), '/home/unreal',
                   '--bind', str(output), '/tmp/evidence',
                   '--ro-bind', str(driver), '/tmp/raw-input.py',
                   '--ro-bind', str(args.plan.resolve()), '/tmp/input-plan.json',
                   '--ro-bind', str(output / 'resolved-package.json'), '/tmp/resolved-package.json']
        if args.task_id == 'D17-02':
            command += ['--ro-bind', str(PROJECT / 'tests/d17_02_route_input.py'), '/tmp/d17_02_route_input.py']
        if native:
            command += ['--ro-bind', str(native), '/tmp/package/' + manifest['binary']]
        command += ['--chdir', '/tmp/package', '--', 'runuser', '-u', 'unreal', '--',
                   'env', 'SDL_AUDIODRIVER=dummy', 'XDG_CACHE_HOME=/tmp/state/xdg-cache',
                   'XDG_CONFIG_HOME=/tmp/state/xdg-config', 'xvfb-run', '-a', '-s',
                   f'-screen 0 {args.width}x{height}x24', 'python3', '/tmp/raw-input.py',
                   '--width', str(args.width), '--height', str(height), '--seconds', str(args.seconds)]
        write(output / 'command.json', command)
        execution = monitor(command, output, timeout=args.seconds+180, process_names=('BiellaGames',))
        write(output / 'execution.json', execution)
        result = json.loads((output / 'input-result.json').read_text())
        video = output / 'raw-gameplay.mkv'
        if video.exists():
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                                    '-show_format', '-of', 'json', str(video)],
                                   capture_output=True, text=True, check=True)
            metadata = json.loads(probe.stdout)
            write(output / 'video.json', {'identity': identity(video), 'probe': metadata})
            stream = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
            assert (stream['width'], stream['height']) == (args.width, height)
            assert int(stream['nb_read_frames']) > 30
        telemetry = output / 'telemetry.jsonl'
        rows = [json.loads(line) for line in telemetry.read_text().splitlines()] if telemetry.exists() else []
        write(output / 'observation.json', {
            'task_id': args.task_id, 'capture': result,
            'telemetry_events': dict(Counter(row['event'] for row in rows)),
            'sessions': sorted({row['session'] for row in rows}),
            'restart_counts': sorted({row['restart_count'] for row in rows}),
            'maps': sorted({row['map'] for row in rows}),
            'acceptance': 'NOT_QUALIFIED: raw observation requires route/duration/visual review'})
        if result['status'] != 'CAPTURED':
            raise RuntimeError(result.get('error', 'capture incomplete'))
        print(json.dumps({'output': str(output), 'capture': result}, sort_keys=True))
    except Exception as exc:
        with LEDGER.open('a') as stream:
            stream.write(json.dumps({'task_id': args.task_id, 'time': now(),
                                     'type': 'raw_runtime_capture', 'status': 'FAILED',
                                     'diagnostics': str(exc)[:1000], 'evidence': str(output)}) + '\n')
        raise


if __name__ == '__main__':
    main()
