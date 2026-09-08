#!/usr/bin/env python3
"""Bind a real D17 recook to its source, install it, or run retained environment proof.

Reuses the existing exact-member package contract. It does not qualify AAA
visuals or substitute an automation fixture for the required raw slice.
"""
import argparse
import json
from pathlib import Path

from run_d08_01_release import (LEDGER, current, identity, install, launch_installed,
                               now, package_manifest, source_manifest, write)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'environment'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--install-root', type=Path, required=True)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--state', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.action == 'install':
            assert args.build and args.stage
            output.mkdir(parents=True, exist_ok=False)
            source_path = output / 'source-build.json'
            source = source_manifest(args.build.resolve(), source_path)
            source.update(task_id='D17-01', schema='biella.d17.source_build/v1')
            write(source_path, source)
            package_path = output / 'package-manifest.json'
            result = package_manifest(args.stage.resolve() / 'validation.json', source_path, package_path)
            manifest = json.loads(package_path.read_text())
            expected = (current(args.install_root)[1]['package_id']
                        if (args.install_root / 'CURRENT.json').exists() else None)
            installed = install(Path(result['payload']), manifest, args.install_root, expected)
            directory, readback = current(args.install_root)
            assert readback == manifest
            write(output / 'validation.json', dict(
                task_id='D17-01', result='PASS', observed=now(), runner=identity(__file__),
                package=identity(package_path), source=identity(source_path), install=installed,
                installed_manifest=identity(directory / 'manifest.json'),
                scope='Recooked Linux Development package, exact archive and installed-member readback; local only'))
        else:
            assert args.state
            result = launch_installed(args.install_root, args.state, output, 'environment', task_id='D17-01')
            write(output / 'd17-scope.json', dict(
                task_id='D17-01', runner=identity(__file__), result=result,
                scope='Existing environment fixture: damage, physics, traversal, switch, hazard and streaming; not raw slice'))
        print(json.dumps(dict(result='PASS', action=args.action, output=str(output))))
    except Exception as exc:
        with LEDGER.open('a') as stream:
            stream.write(json.dumps(dict(task_id='D17-01', time=now(), type='package_' + args.action,
                                         status='FAILED', diagnostics=str(exc)[:1000], evidence=str(output))) + '\n')
        raise


if __name__ == '__main__':
    main()
