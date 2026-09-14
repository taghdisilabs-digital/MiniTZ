#!/usr/bin/env python3
"""Run the observed-caster repair and strict fresh-process native readback."""
import argparse
import json
import pwd
from pathlib import Path
from author_d17_02_terrace import identities
from run_d01_039 import PROJECT, DEFAULT_EDITOR, file_identity, runtime_run, write_json
from run_d01_042 import ensure_runtime_output
from run_d01_043 import finalize_log
from run_d02_01 import runtime_has_task_error
from run_d08_01_release import LEDGER, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reuse-author', type=Path, help='Preserved native author directory; run only fresh read-only validation')
    args = parser.parse_args(); out = args.output.resolve()
    assert not out.exists(), 'Preserve prior attempts; fresh output required'
    ensure_runtime_output(out, pwd.getpwnam('unreal'))
    before = identities()
    engine_cube = DEFAULT_EDITOR.parents[2]/'Content/BasicShapes/Cube.uasset'
    report = dict(task_id='D17-02', result='FAIL', inputs_before=before, runs=[],
        author=file_identity(PROJECT/'Content/Python/author_traversal_shadows.py'),
        diagnosis=file_identity(PROJECT/'Build/AAA/D17-02/shadow-casters-01/diagnosis.json'),
        engine_cube_before=file_identity(engine_cube))
    try:
        author_dir = args.reuse_author.resolve() if args.reuse_author else out
        if args.reuse_author:
            previous_report = json.loads((author_dir/'validation.json').read_text())
            author_run = previous_report['runs'][0]
            assert author_run['returncode'] == 0 and not author_run['timed_out'] and author_run['log_finalization']['closed']
            assert file_identity(author_dir/'author.log') == author_run['log']
            assert 'D17_TRAVERSAL_SHADOWS COMPLETE' in (author_dir/'author.log').read_text()
            before = previous_report['inputs_before']
            # The readback script itself is the only newly edited material input.
            before['Content/Python/author_traversal_shadows.py'] = identities()['Content/Python/author_traversal_shadows.py']
            report.update(inputs_before=before, reused_author=file_identity(author_dir/'author.json'),
                reused_validation=file_identity(author_dir/'validation.json'))
        for mode in (('readback',) if args.reuse_author else ('author', 'readback')):
            previous = identities()
            cmd = ['runuser', '-u', 'unreal', '--', 'env', f'BIELLA_D17_SHADOW_REPORT={out}/{mode}.json',
                f'BIELLA_D17_SHADOW_AUTHOR={author_dir}/author.json',
                str(DEFAULT_EDITOR.with_name('UnrealEditor-Cmd')), str(PROJECT/'BiellaGames.uproject'),
                '-run=pythonscript', f'-script={PROJECT}/Content/Python/author_traversal_shadows.py',
                '-EnablePlugins=PythonScriptPlugin', '-unattended', '-nullrhi', '-nosound', '-nop4',
                '-stdout', '-FullStdOutLogOutput']
            if mode == 'readback': cmd.append('-D17VerifyTraversalShadows')
            write_json(out/f'{mode}-command.json', cmd)
            run = runtime_run(cmd, out/f'{mode}.log', 600)
            run['log_finalization'] = finalize_log(out/f'{mode}.log')
            run['log'] = file_identity(out/f'{mode}.log'); report['runs'].append(run)
            log = (out/f'{mode}.log').read_text(errors='replace')
            assert run['returncode'] == 0 and not run['timed_out'] and run['log_finalization']['closed']
            assert not runtime_has_task_error(log) and 'D17_TRAVERSAL_SHADOWS COMPLETE' in log
            if mode == 'readback': assert previous == identities(), 'Readback changed saved inputs'
        authored = json.loads((author_dir/'author.json').read_text())
        readback = json.loads((out/'readback.json').read_text())
        for key in ('actors_after', 'engine_cube', 'meshes_after', 'nanite_settings', 'material_packages', 'mesh_packages', 'spec_sha256', 'baseline_sha256', 'render_bounds_after', 'material_usage'):
            assert authored[key] == readback[key], key
        assert authored['spec_sha256'] == report['diagnosis']['sha256']
        allowed = {'Content/Maps/BiellaOpenWorldMap.umap'}
        for key in ('material_packages', 'mesh_packages', 'edited_actor_packages'):
            allowed.update('Content/'+p.split('.')[0].removeprefix('/Game/')+'.uasset' for p in authored[key])
        # Rebuilding a diagnosed mesh can update its external actor descriptor.
        # Every actor's transform, mesh, collision and presentation is still exact-checked above.
        allowed.update('Content/'+p.removeprefix('/Game/')+'.uasset' for p in readback['diagnostic_actor_packages'])
        after = identities()
        changed = {p: v for p, v in after.items() if before.get(p) != v}
        assert before.keys() <= after.keys(), 'Preexisting source removed'
        assert set(changed) <= allowed, sorted(set(changed)-allowed)
        assert file_identity(engine_cube) == report['engine_cube_before'], 'Engine source asset changed'
        report.update(result='PASS', changed_inputs=changed, allowed_packages=sorted(allowed),
            all_unrelated_source_and_content_unchanged=True,
            fresh_process_readback_verified=True, slice_acceptance=False)
    except Exception as error:
        report['error'] = repr(error)
        with LEDGER.open('a') as f:
            f.write(json.dumps(dict(task_id='D17-02', time=now(), type='traversal_shadow_authoring',
                status='FAILED', diagnostics=repr(error), evidence=str(out)))+'\n')
    write_json(out/'validation.json', report)
    print(json.dumps({k: report.get(k) for k in ('result', 'error')}))
    return int(report['result'] != 'PASS')


if __name__ == '__main__': raise SystemExit(main())
