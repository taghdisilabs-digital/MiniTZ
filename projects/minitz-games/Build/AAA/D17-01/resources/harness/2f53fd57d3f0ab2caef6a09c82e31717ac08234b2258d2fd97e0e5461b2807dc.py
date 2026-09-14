#!/usr/bin/env python3
"""Run existing HUD behavior tests against a D17 raw run's exact native overlay.

These fixture-based tests qualify the HUD edit only. They do not count as the
uninterrupted challenger slice or as visual acceptance.
"""
import argparse
import json
from pathlib import Path
import pwd
import re

from run_d01_042 import ensure_runtime_output
from run_d01_044 import host_identity, monitor
from run_d02_01 import runtime_has_task_error, reject_material_fallbacks
from run_d08_01_release import current, identity, LEDGER, now, write


TESTS = {
    'hud': 'BiellaGames.Demo01.GameplayHUD',
    'settings': 'BiellaGames.D05.UISettingsLocalizationAccessibility',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--test', choices=TESTS, required=True)
    args = parser.parse_args()
    raw, output = args.raw_run.resolve(), args.output.resolve()
    try:
        resolved = json.loads((raw / 'resolved-package.json').read_text())
        exposed = json.loads((raw / 'exposed-package-verification.json').read_text())
        assert exposed['status'] == 'PASS' and exposed['runtime_id'] == resolved['runtime_id']
        template = json.loads((raw / 'command.json').read_text())
        base = json.loads((raw / 'package-verification.json').read_text())
        payload = Path(base['installed_payload'])
        _, manifest = current(payload.parents[2])
        assert manifest['package_id'] == resolved['base_package_id']
        native = resolved['native_delta']
        assert identity(native['path']) == native, 'Native delta changed since raw run'
        account = pwd.getpwnam('unreal')
        ensure_runtime_output(output, account)
        state = Path('/mnt/biella-extra/biella-runtime/d17-01') / output.name
        ensure_runtime_output(state, account)
        for name in ('home', 'user', 'xdg-cache', 'xdg-config'):
            ensure_runtime_output(state / name, account)

        command = template[:template.index('--chdir')]
        # Replace only mutable evidence/user-state bind sources. Keep the
        # immutable package/native overlay bindings identical to the raw run.
        for i, arg in enumerate(command):
            if arg == '--bind':
                destination = command[i + 2]
                replacements = {'/tmp/state': state, '/home/unreal': state / 'home',
                                '/tmp/evidence': output}
                if destination in replacements:
                    command[i + 1] = str(replacements[destination])
        name = TESTS[args.test]
        command += ['--chdir', '/tmp/package', '--', 'runuser', '-u', 'unreal', '--',
                    'env', 'SDL_AUDIODRIVER=dummy', 'XDG_CACHE_HOME=/tmp/state/xdg-cache',
                    'XDG_CONFIG_HOME=/tmp/state/xdg-config', 'xvfb-run', '-a', '-s',
                    '-screen 0 1280x720x24', '/tmp/package/' + manifest['entrypoint'],
                    '/Game/Maps/BiellaGameplayMap', '-vulkan', '-NoVSync', '-windowed',
                    '-ResX=1280', '-ResY=720', '-unattended', '-AudioMixer', '-nosplash',
                    '-stdout', '-FullStdOutLogOutput', '-NoAsyncLoadingThread',
                    '-UserDir=/tmp/state/user/', '-AbsLog=/tmp/evidence/runtime.engine.log',
                    f'-ExecCmds=t.MaxFPS 60,r.VSync 0,Automation RunTests {name}; SoftQuit']
        if args.test == 'settings':
            command += ['-BiellaD05Output=/tmp/evidence']
        write(output / 'command.json', command)
        report = dict(task_id='D17-01', result='INCOMPLETE', test=name, observed=now(),
                      scope='Existing fixture-based HUD regression; not raw slice proof',
                      runner=identity(__file__), native_delta=native,
                      runtime_id=resolved['runtime_id'],
                      resolved_package=identity(raw / 'resolved-package.json'), host=host_identity())
        write(output / 'validation.json', report)
        execution = monitor(command, output, 180, process_names=('BiellaGames',))
        write(output / 'execution.json', execution)
        log = (output / 'runtime.stdout.log').read_text(errors='replace')
        assert execution['returncode'] == 0 and not execution['watchdog_failure']
        assert not execution['survivors'] and execution['unreal_process_identities']
        assert '**** TEST COMPLETE. EXIT CODE: 0 ****' in log
        assert re.search(r'Result=\{Success\}.*Name=\{' + name.rsplit('.', 1)[1] + r'\}', log)
        assert not runtime_has_task_error(log)
        reject_material_fallbacks(log)
        if args.test == 'settings':
            result = json.loads((output / 'result.json').read_text())
            phases = re.findall(r'D05_D01_TEST PASS phase=(\w+)', log)
            assert result['success'] and result['source'] == 'live_runtime'
            assert {'localization', 'hud', 'sensitivity', 'motion_blur', 'readability',
                    'persistence', 'pause_settings'} <= set(phases)
            report['behavior'] = dict(result, phases=phases)
        else:
            assert 'D01_037_TEST COMPLETE widget=BiellaGameplayHUD source=authoritative_runtime' in log
            report['behavior'] = [line for line in log.splitlines() if 'D01_037_TEST' in line]
        assert identity(native['path']) == native
        report['result'] = 'PASS'
        write(output / 'validation.json', report)
        print(json.dumps(dict(test=name, result='PASS', output=str(output))))
    except Exception as exc:
        with LEDGER.open('a') as stream:
            stream.write(json.dumps(dict(task_id='D17-01', time=now(),
                                         type='hud_regression', status='FAILED',
                                         diagnostics=str(exc)[:1000], evidence=str(output))) + '\n')
        raise


if __name__ == '__main__':
    main()
