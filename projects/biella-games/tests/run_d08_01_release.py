#!/usr/bin/env python3
"""D08 exact package and transactional update qualification (no RC inference).

This is a qualification tool, not a shipping launcher or a store protocol.
Manifests identify bytes; their hashes do not provide publisher authentication.
Source/build/cook/stage receipts and real runtime evidence remain required.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
ENGINE = Path('/opt/unreal/UE_5.8.2/Engine')
ROOT = PROJECT / 'Build/Release/D08-01'
LEDGER = Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def identity(path):
    path = Path(path)
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': sha, 'bytes': path.stat().st_size}


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path):
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def read(path):
    return json.loads(Path(path).read_text())


def safe_path(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            'Invalid portable package path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and all(x not in ('.', '..') for x in p.parts),
            'Noncanonical or escaping package path')
    for part in p.parts:
        require(not part.endswith((' ', '.')) and not re.search(r'[\x00-\x1f<>"|?*]', part),
                'Nonportable package path')
        require(part.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))},
                'Windows reserved path')
    return p


def members(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'Package root must be a real directory')
    result = []
    seen = set()
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), f'Package symlink rejected: {path}')
        if path.is_dir():
            continue
        require(path.is_file(), f'Nonregular package member: {path}')
        relative = path.relative_to(root).as_posix()
        safe_path(relative)
        require(relative.casefold() not in seen, 'Case-colliding package members')
        seen.add(relative.casefold())
        record = identity(path)
        record.update(path=relative, executable=bool(path.stat().st_mode & 0o111))
        result.append(record)
    require(result, 'Empty package')
    return result


def executable_format(path):
    with Path(path).open('rb') as stream:
        header = stream.read(64)
        if len(header) == 64 and header[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', header, 18)[0] == 62:
            return 'ELF64-x86_64'
        if header[:2] == b'MZ' and len(header) == 64:
            stream.seek(struct.unpack_from('<I', header, 60)[0])
            pe = stream.read(26)
            if len(pe) == 26 and pe[:4] == b'PE\0\0' and struct.unpack_from('<H', pe, 4)[0] == 0x8664 and struct.unpack_from('<H', pe, 24)[0] == 0x20b:
                return 'PE32+-x86_64'
    raise ValueError('Binary is not a verified x64 PE/ELF executable')


def seal(manifest):
    return dict(manifest, package_id=digest({k: v for k, v in manifest.items() if k != 'package_id'}))


def validate_manifest(manifest):
    require(manifest.get('schema') == 'biella.d08.package/v1', 'Unsupported manifest version')
    require(re.fullmatch('[0-9a-f]{64}', manifest.get('package_id', '')) is not None,
            'Invalid package identity')
    require(seal(manifest) == manifest, 'Manifest digest mismatch')
    require(manifest.get('platform') in ('Linux', 'Win64'), 'Unsupported platform')
    require(manifest.get('configuration') in ('Development', 'Shipping'), 'Unsupported configuration')
    seen = set()
    for row in manifest['files']:
        safe_path(row['path'])
        require(row['path'].casefold() not in seen, 'Duplicate/case-colliding manifest member')
        seen.add(row['path'].casefold())
        require(re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None and
                isinstance(row['bytes'], int) and row['bytes'] >= 0 and isinstance(row['executable'], bool),
                'Invalid member identity')
    for key in ('entrypoint', 'binary'):
        safe_path(manifest[key])
        require(manifest[key] in {f['path'] for f in manifest['files']}, 'Missing entrypoint or binary')
    require(any(f['path'].endswith(('.pak', '.utoc')) for f in manifest['files']), 'Missing cooked content')


def verify_package(root, manifest):
    validate_manifest(manifest)
    actual = members(root)
    require(actual == manifest['files'], 'Package bytes, membership or executable permissions differ')
    expected = 'PE32+-x86_64' if manifest['platform'] == 'Win64' else 'ELF64-x86_64'
    require(executable_format(Path(root) / manifest['binary']) == manifest['binary_format'] == expected,
            'Binary format does not match declared platform')
    return {'result': 'PASS', 'package_id': manifest['package_id'], 'files': len(actual),
            'bytes': sum(f['bytes'] for f in actual), 'binary_format': expected}


@contextlib.contextmanager
def install_lock(root):
    require(not root.is_symlink(), 'Symlink install root rejected')
    root.mkdir(parents=True, exist_ok=True)
    require(not (root / '.install.lock').is_symlink(), 'Symlink lock rejected')
    with (root / '.install.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0)
            stream.write(b'0')
            stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def current(root):
    require(not (root / 'CURRENT.json').is_symlink(), 'Symlink current pointer rejected')
    pointer = read(root / 'CURRENT.json')
    package_id = pointer['package_id']
    require(re.fullmatch('[0-9a-f]{64}', package_id) is not None, 'Invalid installed package id')
    directory = root / 'versions' / package_id
    require(not directory.is_symlink() and not (directory / 'manifest.json').is_symlink(),
            'Symlink installed version rejected')
    manifest = read(directory / 'manifest.json')
    require(manifest['package_id'] == package_id, 'Current pointer and manifest disagree')
    verify_package(directory / 'payload', manifest)
    return directory, manifest


def install(payload, manifest, root, expected_current=None):
    """Never modify old versions or the game's external per-user state.

    Interrupted copies leave an unreferenced .partial directory. A retry creates
    a new directory, validates it, and switches CURRENT only after full readback.
    """
    payload, root = Path(payload).absolute(), Path(root).absolute()
    require(not any(p.is_symlink() for p in (root, *root.parents, payload, *payload.parents)),
            'Symlink payload/install ancestry rejected')
    require(root != payload and root not in payload.parents and payload not in root.parents,
            'Install and payload trees must be disjoint')
    with install_lock(root):
        versions = root / 'versions'
        require(not versions.is_symlink(), 'Symlink versions root rejected')
        versions.mkdir(exist_ok=True)
        before = None
        if (root / 'CURRENT.json').exists():
            _, before = current(root)
            require(expected_current == before['package_id'], 'Update base does not match installed package')
            require(all(manifest.get(key) == before.get(key) for key in
                        ('platform', 'configuration', 'engine_version', 'project')),
                    'Incompatible update platform/configuration/engine/project')
        else:
            require(expected_current is None, 'Expected update base is absent')
        verify_package(payload, manifest)
        version = versions / manifest['package_id']
        if version.exists():
            # A process may have died after the rename and before CURRENT was
            # replaced. Resume only the exact independently verified version.
            require(not version.is_symlink() and not (version / 'manifest.json').is_symlink() and
                    read(version / 'manifest.json') == manifest,
                    'Existing version has different manifest')
            verify_package(version / 'payload', manifest)
            write(root / 'CURRENT.json', {'schema': 'biella.d08.installed/v1', 'package_id': manifest['package_id']})
            current(root)
            return {'result': 'PASS', 'from_package': before['package_id'] if before else None,
                    'to_package': manifest['package_id'], 'installed': str(version), 'recovered_verified_version': True}
        partial = versions / (manifest['package_id'] + '.' + uuid.uuid4().hex + '.partial')
        partial.mkdir()
        shutil.copytree(payload, partial / 'payload', symlinks=True)
        # Portable distribution permissions: a different, unprivileged account
        # must be able to read the package. Preserve executable intent only.
        for path in (partial / 'payload', *(partial / 'payload').rglob('*')):
            require(not path.is_symlink(), 'Copied symlink rejected')
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
        verify_package(partial / 'payload', manifest)
        for row in manifest['files']:
            with (partial / 'payload' / row['path']).open('rb') as stream:
                os.fsync(stream.fileno())
        write(partial / 'manifest.json', manifest)
        for directory in sorted((p for p in partial.rglob('*') if p.is_dir()), reverse=True):
            sync_directory(directory)
        sync_directory(partial)
        os.rename(partial, version)
        sync_directory(versions)
        write(root / 'CURRENT.json', {'schema': 'biella.d08.installed/v1', 'package_id': manifest['package_id']})
        _, observed = current(root)
        require(observed == manifest, 'Committed install readback differs')
        return {'result': 'PASS', 'from_package': before['package_id'] if before else None,
                'to_package': manifest['package_id'], 'installed': str(version),
                'scope': 'Byte-exact installation only; native launch/settings compatibility require separate evidence.'}


def source_manifest(build, output):
    from cook_d03_01_package import project_inputs
    report = read(build / 'result.json')
    require(report['result'] == 'PASS' and report['inputs_unchanged'], 'Game build did not pass')
    rows = [identity(p) for p in project_inputs()]
    recorded = read(build / 'inputs-after.json')
    require([r for r in rows if '/Source/' in r['path']] == recorded, 'Source changed since build')
    for key in ('binary', 'receipt'):
        require(identity(report[key]['path']) == report[key], f'Build {key} changed')
    receipt = read(report['receipt']['path'])
    require(receipt['Platform'] == 'Linux' and receipt['Configuration'] == 'Development',
            'Unexpected diagnostic build target')
    relative = [dict(row, path=str(Path(row['path']).relative_to(PROJECT))) for row in rows]
    value = {'schema': 'biella.d08.source_build/v1', 'task_id': 'D08-01', 'observed': now(),
             'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROJECT, text=True).strip(),
             'git_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=PROJECT, text=True).strip(),
             'material_inputs': relative, 'material_input_digest': digest(relative),
             'engine': identity(ENGINE / 'Build/Build.version'), 'build': identity(build / 'result.json'),
             'binary': report['binary'], 'receipt': report['receipt'],
             'scope': 'Exact working-tree material inputs; volatile 03/04 excluded. Linux Development diagnostic build.'}
    write(output, value)
    return value


def package_manifest(stage_path, source_path, output):
    stage, source = read(stage_path), read(source_path)
    require(stage['result'] == 'PASS', 'UAT stage/archive validation did not pass')
    require(identity(stage['archive']['path']) == stage['archive'], 'Archive differs from stage readback')
    cook = read(stage['cook']['path'])
    require(identity(stage['cook']['path']) == stage['cook'] and cook['result'] == 'PASS', 'Cook receipt differs')
    relative = [dict(row, path=str(Path(row['path']).relative_to(PROJECT))) for row in cook['inputs_before']]
    require(relative == source['material_inputs'], 'Cook and build material inputs differ')
    payload = Path(stage['archive_readback']) / 'Linux'
    actual_members = members(payload)
    expected_members = [dict(row, path=str(Path(row['path']).relative_to(payload)))
                        for row in stage['readback_members']]
    require([{k: row[k] for k in ('path', 'sha256', 'bytes')} for row in actual_members] == expected_members,
            'Package extraction changed after UAT archive readback')
    binary = 'BiellaGames/Binaries/Linux/BiellaGames'
    require(identity(payload / binary)['sha256'] == source['binary']['sha256'], 'Cooked package binary differs from build')
    manifest = seal({'schema': 'biella.d08.package/v1', 'project': 'BiellaGames',
                     'platform': 'Linux', 'configuration': 'Development', 'engine_version': '5.8.2',
                     'entrypoint': 'BiellaGames.sh', 'binary': binary,
                     'binary_format': executable_format(payload / binary),
                     'files': actual_members, 'source_manifest': identity(source_path),
                     'source_material_digest': source['material_input_digest'],
                     'archive': stage['archive'], 'stage_receipt': identity(stage_path),
                     'qualification': 'DIAGNOSTIC_ONLY_NOT_WIN64_RC'})
    verify_package(payload, manifest)
    write(output, manifest)
    return {'package_id': manifest['package_id'], 'payload': str(payload), 'output': str(output)}


def predecessor_manifest(stage_path, output):
    stage = read(stage_path)
    require(stage['result'] == 'PASS' and stage['task_id'] == 'D03-01', 'Expected retained accepted D03 stage')
    require(identity(stage['archive']['path']) == stage['archive'], 'Retained archive changed')
    extraction = Path(stage['archive_readback'])
    for record in stage['readback_members']:
        require(identity(record['path']) == record, 'Retained package extraction changed')
    expected = {str(Path(row['path']).relative_to(extraction)) for row in stage['readback_members']}
    require({str(p.relative_to(extraction)) for p in extraction.rglob('*') if p.is_file()} == expected,
            'Retained package extraction membership changed')
    require(identity(stage['cook']['path']) == stage['cook'], 'Retained cook receipt changed')
    payload = extraction / 'Linux'
    binary = 'BiellaGames/Binaries/Linux/BiellaGames'
    manifest = seal({'schema': 'biella.d08.package/v1', 'project': 'BiellaGames',
                     'platform': 'Linux', 'configuration': 'Development', 'engine_version': '5.8.2',
                     'entrypoint': 'BiellaGames.sh', 'binary': binary,
                     'binary_format': executable_format(payload / binary), 'files': members(payload),
                     'retained_source_cook': stage['cook'], 'archive': stage['archive'],
                     'stage_receipt': identity(stage_path), 'qualification': 'RETAINED_D03_DIAGNOSTIC_UPDATE_BASE'})
    verify_package(payload, manifest)
    write(output, manifest)
    return {'package_id': manifest['package_id'], 'payload': str(payload), 'output': str(output)}


def negative_update(root, workspace, output):
    root, workspace = root.resolve(), workspace.absolute()
    directory, manifest = current(root)
    require(not workspace.exists(), 'Fresh negative-control workspace required')
    before = identity(root / 'CURRENT.json')
    payload = workspace / 'incomplete-payload'
    shutil.copytree(directory / 'payload', payload)
    missing = next(row for row in manifest['files'] if row['path'].endswith('.pak'))
    (payload / missing['path']).unlink()
    cases = []
    for name, candidate, candidate_manifest, expected_error in (
            ('incomplete_real_package', payload, manifest, 'differ'),
            ('incompatible_engine_manifest', payload,
             seal(dict(manifest, engine_version='INCOMPATIBLE_NEGATIVE_CONTROL')), 'Incompatible')):
        if name == 'incompatible_engine_manifest':
            shutil.copy2(directory / 'payload' / missing['path'], payload / missing['path'])
            verify_package(payload, manifest)
        try:
            install(candidate, candidate_manifest, root, manifest['package_id'])
        except ValueError as error:
            require(expected_error in str(error), f'Unexpected rejection reason: {error}')
            cases.append({'case': name, 'result': 'EXPECTED_REJECTION', 'diagnostic': str(error),
                          'candidate_id': candidate_manifest['package_id']})
        else:
            raise ValueError('Negative update unexpectedly accepted')
        require(identity(root / 'CURRENT.json') == before and current(root)[1] == manifest,
                'Rejected update altered installed version')
    report = {'task_id': 'D08-01', 'result': 'PASS', 'observed': now(), 'cases': cases,
              'base_package_id': manifest['package_id'], 'removed_member': missing,
              'current_before': before, 'current_after': identity(root / 'CURRENT.json'),
              'workspace': str(workspace),
              'scope': 'Actual packaged-file removal and incompatible update metadata; native content-version rejection is checked separately.'}
    write(output, report)
    return report


SCENARIOS = {
    'content': ('D04.ContentRegistry', 'BiellaOpenWorldMap', 'BiellaContentOutput'),
    'population': ('D02.Population', 'BiellaOpenWorldMap', 'BiellaPopulationOutput'),
    'environment': ('D02.Environment', 'BiellaOpenWorldMap', 'BiellaEnvironmentOutput'),
    'core': ('Demo01.DeterministicPlaytest', 'BiellaGameplayMap', None),
    'feedback': ('Demo01.EventFeedback', 'BiellaGameplayMap', 'BiellaFeedbackOutput'),
    'settings': ('D08.SettingsReconstruction', 'BiellaGameplayMap', 'BiellaReleaseOutput'),
    'ui': ('D05.UISettingsLocalizationAccessibility', 'BiellaGameplayMap', 'BiellaD05Output'),
    'cinematic': ('D06.Cinematic', 'BiellaGameplayMap', None),
}


def launch_installed(root, state, output, scenario, settings_phase='read', timeout=360):
    import pwd
    from run_d01_042 import ensure_runtime_output
    from run_d01_044 import host_identity, monitor
    from run_d02_01 import runtime_has_task_error, reject_material_fallbacks
    root, state, output = root.resolve(), state.absolute(), output.absolute()
    directory, manifest = current(root)
    require(manifest['platform'] == 'Linux' and manifest['configuration'] == 'Development',
            'This native automation route is Linux Development diagnostics only')
    require(not output.exists(), 'Fresh runtime evidence directory required')
    require(not any(p.is_symlink() for p in (state, *state.parents)), 'Symlink state rejected')
    require(root not in state.parents and root != state, 'Per-user state must be outside installation')
    account = pwd.getpwnam('unreal')
    ensure_runtime_output(output, account)
    if not state.exists():
        ensure_runtime_output(state, account)
        for name in ('home', 'user', 'xdg-cache', 'xdg-config'):
            ensure_runtime_output(state / name, account)
    state_before = [identity(p) for p in sorted(state.rglob('*.ini'))]
    native, world, output_arg = SCENARIOS[scenario]
    report = {'task_id': 'D08-01', 'result': 'FAIL', 'observed': now(), 'package_id': manifest['package_id'],
              'manifest': identity(directory / 'manifest.json'), 'scenario': scenario, 'host': host_identity(),
              'orchestrator': identity(__file__),
              'state': str(state), 'settings_before': state_before,
              'capture_status': 'GENERATED_DRAFT_RUNTIME_EVIDENCE',
              'scope': 'Outside-editor Linux Development Vulkan package. Source/engine/cache/network hidden; not Win64 Shipping acceptance.'}
    write(output / 'validation.json', report)
    command = ['bwrap', '--die-with-parent', '--ro-bind', '/', '/', '--dev-bind', '/dev', '/dev',
               '--tmpfs', '/root', '--tmpfs', '/opt', '--tmpfs', '/home', '--tmpfs', '/mnt',
               '--tmpfs', '/tmp', '--chmod', '1777', '/tmp', '--tmpfs', '/var/tmp', '--chmod', '1777', '/var/tmp',
               '--tmpfs', '/var/cache', '--tmpfs', '/run', '--unshare-net', '--unshare-ipc',
               '--ro-bind', str(directory / 'payload'), '/tmp/package', '--bind', str(state), '/tmp/state',
               '--bind', str(state / 'home'), '/home/unreal', '--bind', str(output), '/tmp/evidence',
               '--chdir', '/tmp/package', '--', 'runuser', '-u', 'unreal', '--',
               'env', 'SDL_AUDIODRIVER=dummy', 'XDG_CACHE_HOME=/tmp/state/xdg-cache',
               'XDG_CONFIG_HOME=/tmp/state/xdg-config', 'xvfb-run', '-a', '-s', '-screen 0 1280x720x24',
               '/tmp/package/' + manifest['entrypoint'], '/Game/Maps/' + world,
               '-vulkan', '-NoVSync', '-windowed', '-ResX=1280', '-ResY=720', '-unattended',
               '-AudioMixer', '-nosplash', '-stdout', '-FullStdOutLogOutput', '-NoAsyncLoadingThread',
               '-UserDir=/tmp/state/user/', '-AbsLog=/tmp/evidence/runtime.engine.log',
               f'-ExecCmds=t.MaxFPS 60,r.VSync 0,Automation RunTests BiellaGames.{native}; SoftQuit']
    if output_arg:
        command += [f'-{output_arg}=/tmp/evidence']
    if scenario in ('core', 'feedback'):
        command += ['-UseFixedTimeStep', '-FPS=60', '-DeterministicAudio']
    if scenario == 'core':
        command += ['-BiellaTelemetry=/tmp/evidence/telemetry.jsonl', '-BiellaPlaytestSeed=1337']
    if scenario == 'population':
        command += ['-BiellaPopulationCount=4']
    if scenario == 'settings':
        command += ['-BiellaReleaseSettingsPhase=' + settings_phase]
    if scenario == 'cinematic':
        command += ['-BiellaD06Cinematic', '-BiellaTelemetry=/tmp/evidence/cinematic.telemetry.jsonl']
    write(output / 'command.json', command)
    try:
        report['runtime'] = monitor(command, output, timeout, process_names=('BiellaGames',))
        log = (output / 'runtime.stdout.log').read_text(errors='replace')
        require(report['runtime']['returncode'] == 0 and not report['runtime']['watchdog_failure'] and
                not report['runtime']['survivors'], 'Package process failed or did not tear down')
        require(report['runtime']['unreal_process_identities'], 'Native package PID was not sampled')
        require('**** TEST COMPLETE. EXIT CODE: 0 ****' in log and
                re.search(r'Result=\{Success\}.*Name=\{' + native.rsplit('.', 1)[1] + r'\}', log),
                'Native automation did not complete successfully')
        require(not runtime_has_task_error(log), 'Fatal/assert/content-load runtime diagnostic')
        reject_material_fallbacks(log)
        if scenario == 'content':
            from verify_d04_01 import verify
            report['verification'] = verify(output)
        elif scenario == 'population':
            from verify_d02_02 import verify
            report['verification'] = verify(output, 4)
        elif scenario == 'environment':
            from verify_d02_04 import verify
            report['verification'] = verify(output)
        elif scenario == 'core':
            from verify_d01_039 import read_capture
            _, report['verification'] = read_capture(output / 'telemetry.jsonl')
            report['verification']['scope'] = 'Single native gameplay trace; cross-process comparison is reported separately.'
        elif scenario == 'feedback':
            from run_d01_042 import decode_audio, REQUIRED_PHASES, STAGES
            from verify_d01_048 import verify_frame
            require(set(REQUIRED_PHASES) <= set(re.findall(r'D01_042_TEST PASS phase=(\w+)', log)),
                    'Feedback gameplay phases missing')
            particles = re.findall(r'D01_042_TEST PARTICLES cue=(\d+) count=(\d+) registered=true render_state=true', log)
            require(len(particles) == 4 and all(int(row[1]) > 0 for row in particles), 'Feedback runtime particles missing')
            require(len(re.findall(r'D01_042_TEST ATTR ([^\n]+)', log)) == 8 and 'D01_042_TEST DENSE ' in log,
                    'Event attribution or dense combat evidence missing')
            report['verification'] = {
                'frames': [verify_frame(identity(output / f'{stage}.png')) for stage in (*STAGES, 'dense_combat')],
                'audio': [decode_audio(output / f'{stage}.wav') for stage in STAGES]}
            require(len({item['sha256'] for item in report['verification']['audio']}) == 5,
                    'Distinct gameplay cues produced identical audio')
        elif scenario == 'settings':
            result = read(output / 'settings.json')
            require(result['phase'] == settings_phase and result['result'] == 'PASS', 'Settings probe did not pass')
            require(result['settings_path'].startswith('/tmp/state/user/'), 'Settings escaped per-user directory')
            report['verification'] = result
        elif scenario == 'ui':
            result = read(output / 'result.json')
            require(result['success'] and result['source'] == 'live_runtime', 'Native UI probe failed')
            phases = re.findall(r'D05_D01_TEST PASS phase=(\w+)', log)
            require({'localization', 'hud', 'sensitivity', 'motion_blur', 'readability',
                     'persistence', 'pause_settings'} <= set(phases), 'Native UI behavior evidence missing')
            report['verification'] = dict(result, phases=phases)
        elif scenario == 'cinematic':
            from run_d06_01_cinematic import validate_runtime
            native_run = dict(report['runtime'], timed_out=bool(report['runtime']['watchdog_failure']))
            report['verification'] = validate_runtime(native_run, output)
        report['diagnostics'] = [line[:1500] for line in log.splitlines() if re.search(r'\b(Warning|Error):', line)]
        verify_package(directory / 'payload', manifest)
        require(current(root)[1] == manifest, 'Active package changed during runtime')
        report['result'] = 'PASS'
    except (ValueError, OSError, KeyError, AssertionError, RuntimeError) as error:
        report['error'] = str(error)
        raise
    finally:
        report['settings_after'] = [identity(p) for p in sorted(state.rglob('*.ini'))]
        report['evidence'] = [identity(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'validation.json']
        write(output / 'validation.json', report)
    return {'result': report['result'], 'scenario': scenario, 'package_id': manifest['package_id'], 'output': str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    for operation, helper in (('build', 'build_d03_01_game.py'), ('build-editor', 'build_d03_01_editor.py'), ('cook', 'cook_d03_01_package.py'),
                              ('stage', 'stage_d03_01_package.py')):
        child = sub.add_parser(operation)
        child.set_defaults(helper=helper)
        child.add_argument('--output', type=Path, required=True)
        if operation == 'cook':
            child.add_argument('--workspace', type=Path, required=True)
            child.add_argument('--game-build', type=Path, required=True)
            child.add_argument('--editor-build', type=Path)
        if operation == 'stage':
            for name in ('cook', 'archive', 'dependencies'):
                child.add_argument('--' + name, type=Path, required=True)
    launch = sub.add_parser('launch')
    launch.add_argument('--install-root', type=Path, required=True)
    launch.add_argument('--state', type=Path, required=True)
    launch.add_argument('--output', type=Path, required=True)
    launch.add_argument('--scenario', choices=SCENARIOS, required=True)
    launch.add_argument('--settings-phase', choices=('legacy', 'write', 'read'), default='read')
    launch.add_argument('--timeout', type=int, default=360)
    source = sub.add_parser('source')
    source.add_argument('--build', type=Path, required=True)
    source.add_argument('--output', type=Path, default=ROOT / 'source-build-manifest.json')
    package = sub.add_parser('package')
    package.add_argument('--stage', type=Path, required=True)
    package.add_argument('--source', type=Path, default=ROOT / 'source-build-manifest.json')
    package.add_argument('--output', type=Path, default=ROOT / 'package-manifest.json')
    predecessor = sub.add_parser('predecessor')
    predecessor.add_argument('--stage', type=Path, required=True)
    predecessor.add_argument('--output', type=Path, default=ROOT / 'old-package-manifest.json')
    negative = sub.add_parser('negative')
    negative.add_argument('--install-root', type=Path, required=True)
    negative.add_argument('--workspace', type=Path, required=True)
    negative.add_argument('--output', type=Path, required=True)
    for operation in ('verify', 'install'):
        child = sub.add_parser(operation)
        child.add_argument('--payload', type=Path, required=True)
        child.add_argument('--manifest', type=Path, required=True)
        child.add_argument('--output', type=Path, required=True)
        if operation == 'install':
            child.add_argument('--install-root', type=Path, required=True)
            child.add_argument('--expected-current')
    args = parser.parse_args()
    try:
        if args.operation in ('build', 'build-editor', 'cook', 'stage'):
            command = [sys.executable, str(PROJECT / 'tests' / args.helper), '--task-id', 'D08-01']
            for key, value in vars(args).items():
                if key not in ('operation', 'helper') and value is not None:
                    command += ['--' + key.replace('_', '-'), str(value)]
            return subprocess.call(command, cwd=PROJECT)
        if args.operation == 'launch':
            result = launch_installed(args.install_root, args.state, args.output, args.scenario,
                                      args.settings_phase, args.timeout)
        elif args.operation == 'source':
            result = source_manifest(args.build.resolve(), args.output.resolve())
            result = {'result': 'PASS', 'material_input_digest': result['material_input_digest']}
        elif args.operation == 'package':
            result = package_manifest(args.stage.resolve(), args.source.resolve(), args.output.resolve())
        elif args.operation == 'predecessor':
            result = predecessor_manifest(args.stage.resolve(), args.output.resolve())
        elif args.operation == 'negative':
            result = negative_update(args.install_root, args.workspace, args.output)
        else:
            manifest = read(args.manifest)
            result = verify_package(args.payload, manifest) if args.operation == 'verify' else install(
                args.payload, manifest, args.install_root, args.expected_current)
            write(args.output, dict(result, task_id='D08-01', observed=now(), manifest=identity(args.manifest)))
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, KeyError, AssertionError, RuntimeError) as error:
        diagnostic = {'task_id': 'D08-01', 'time': now(), 'type': 'release_' + args.operation,
                      'status': 'CONTINUE', 'diagnostics': str(error)[:2000]}
        with LEDGER.open('a') as stream:
            stream.write(json.dumps(diagnostic) + '\n')
        print(json.dumps(diagnostic), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
