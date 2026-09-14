#!/usr/bin/env python3
"""Author terrace route and verify saved packages in a separate native process."""
import argparse
import json
import pwd
from pathlib import Path
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_043 import finalize_log
from run_d02_01 import runtime_has_task_error
from run_d08_01_release import LEDGER, now


def identities():
    return {str(p.relative_to(PROJECT)): file_identity(p)
            for root in ('Content', 'Source', 'Config') for p in sorted((PROJECT/root).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); out = args.output.resolve()
    assert not out.exists(), 'Keep previous receipts; use fresh output'
    ensure_runtime_output(out, pwd.getpwnam('unreal'))
    before = identities()
    report = dict(task_id='D17-02', result='FAIL', inputs_before=before, runs=[],
                  author=file_identity(PROJECT/'Content/Python/author_terrace_route.py'),
                  spec=file_identity(PROJECT/'SourceAssets/Environment/terrace-route.json'))
    try:
        for mode in ('author', 'readback'):
            previous = identities()
            cmd = ['runuser', '-u', 'unreal', '--', 'env', f'BIELLA_D17_TERRACE_REPORT={out}/{mode}.json',
                str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')), str(PROJECT/'BiellaGames.uproject'),
                '-run=pythonscript', f'-script={PROJECT}/Content/Python/author_terrace_route.py',
                '-EnablePlugins=PythonScriptPlugin', '-unattended', '-nullrhi', '-nosound', '-nop4',
                '-stdout', '-FullStdOutLogOutput']
            if mode == 'readback': cmd.append('-D17VerifyTerraceRoute')
            write_json(out/f'{mode}-command.json', cmd)
            run = runtime_run(cmd, out/f'{mode}.log', 600)
            run['log_finalization'] = finalize_log(out/f'{mode}.log')
            run['log'] = file_identity(out/f'{mode}.log'); report['runs'].append(run)
            log = (out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode']==0 and not run['timed_out'] and run['log_finalization']['closed']
            assert not runtime_has_task_error(log) and 'D17_TERRACE_ROUTE COMPLETE' in log
            if mode == 'readback': assert previous == identities(), 'Readback changed saved inputs'
        authored = json.loads((out/'author.json').read_text())
        readback = json.loads((out/'readback.json').read_text())
        assert authored['edited_actor_paths'] == readback['edited_actor_paths']
        assert authored['preserved_colliders'] == readback['preserved_colliders']
        assert authored['spec_sha256'] == readback['spec_sha256'] == report['spec']['sha256']
        allowed = {'Content/Maps/BiellaOpenWorldMap.umap', 'Content/Environment/TerraceRoute/SM_TerraceRoute.uasset'}
        allowed.update('Content/'+p.removeprefix('/Game/')+'.uasset' for p in authored['edited_actor_packages'])
        assert authored['lights'] == readback['lights']
        assert authored['material_packages'] == readback['material_packages']
        assert authored['shader_sha256'] == readback['shader_sha256']
        assert authored['nanite_settings'] == readback['nanite_settings']
        allowed.update('Content/'+p.removeprefix('/Game/')+'.uasset' for p in authored['material_packages'])
        after = identities()
        changed = {p: v for p, v in after.items() if before.get(p) != v}
        assert before.keys() <= after.keys(), 'Preexisting source removed'
        assert set(changed) <= allowed, sorted(set(changed)-allowed)
        report.update(result='PASS', changed_inputs=changed, allowed_packages=sorted(allowed),
                      all_other_source_geometry_materials_config_unchanged=True,
                      fresh_process_readback_verified=True, slice_acceptance=False)
    except Exception as error:
        report['error'] = repr(error)
        with LEDGER.open('a') as f:
            f.write(json.dumps(dict(task_id='D17-02',time=now(),type='terrace_route_authoring',status='FAILED',
                                   diagnostics=repr(error),evidence=str(out)))+'\n')
    write_json(out/'validation.json', report)
    print(json.dumps({k: report.get(k) for k in ('result','error')}))
    return int(report['result'] != 'PASS')


if __name__ == '__main__': raise SystemExit(main())
