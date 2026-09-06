#!/usr/bin/env python3
"""Native input-driven skeletal animation evidence, including cancellation."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import pwd
import re
from run_d01_039 import DEFAULT_EDITOR, PROJECT, file_identity, source_revision, write_json
from run_d01_042 import ensure_runtime_output
from run_d02_01 import identities, monitor, reject_material_fallbacks, runtime_has_task_error

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expect-missing-rig',action='store_true',help='Initial RED control only')
    a=p.parse_args(); out=a.output.resolve()
    assert not out.exists(), 'Use a fresh output directory'
    account=pwd.getpwnam('unreal'); ensure_runtime_output(out,account)
    protected=[PROJECT.parents[1]/'docs/project-state/03_BIELLA_CURRENT_STATE.md',PROJECT.parents[1]/'docs/project-state/04_BIELLA_ACTIVE_TASK.md',PROJECT/'docs/PRODUCTION.md']
    def inputs(): return identities(DEFAULT_EDITOR)+[file_identity(Path(__file__))]
    report=dict(task_id='D03-01',result='FAIL',revision=source_revision(),scope='skeletal locomotion/jump integration',
                capture_status='GENERATED_DRAFT', fixture='Population AI frozen; native game/input/movement/animation/rendering',
                identities_before=inputs(), protected_before=[file_identity(x) for x in protected])
    try:
        cmd=['runuser','-u','unreal','--','env','SDL_AUDIODRIVER=dummy','xvfb-run','-a','-s','-screen 0 1280x720x24',
             str(DEFAULT_EDITOR),str(PROJECT/'BiellaGames.uproject'),'/Game/Maps/BiellaOpenWorldMap','-game','-vulkan','-NoVSync',
             '-windowed','-ResX=1280','-ResY=720','-unattended','-AudioMixer','-nosplash','-stdout','-FullStdOutLogOutput',
             f'-AbsLog={out}/runtime.engine.log',f'-BiellaAnimationOutput={out}',
             '-ExecCmds=t.MaxFPS 0,r.VSync 0,r.MotionBlurQuality 0,r.DynamicRes.OperationMode 0,Automation RunTests BiellaGames.D03.Animation; SoftQuit']
        report['runtime']=monitor(cmd,out,210)
        log=(out/'runtime.stdout.log').read_text(errors='replace')
        result=json.loads((out/'result.json').read_text(encoding='utf-8-sig'))
        assert not report['runtime']['timed_out'] and report['runtime']['log_finalization']['closed'], 'Incomplete runtime'
        report['identities_after']=inputs(); report['protected_after']=[file_identity(x) for x in protected]
        assert report['identities_before']==report['identities_after'], 'Inputs changed during run'
        # 03/04 are volatile controller continuity, retained as evidence only.
        stable=lambda items: [x for x in items if x['path']==str(PROJECT/'docs/PRODUCTION.md')]
        assert stable(report['protected_before'])==stable(report['protected_after']), 'Stable Project production authority changed'
        if a.expect_missing_rig:
            assert not result['success'] and result['error']=='missing_live_skeletal_presentation', 'RED did not catch missing runtime rig'
            report['result']='EXPECTED_RED'
        else:
            assert report['runtime']['returncode']==0 and '**** TEST COMPLETE. EXIT CODE: 0 ****' in log, 'Unreal process failed'
            assert re.search(r'Result=\{Success\}.*Name=\{Animation\}',log) and result['success'], 'Animation scenario failed'
            assert not runtime_has_task_error(log), 'Runtime error'
            reject_material_fallbacks(log)
            rows=list(csv.DictReader((out/'poses.csv').open(encoding='utf-8-sig')))
            assert len(rows)>100 and {3,4,5,7,8,9,10,11,12,13,14,15,16,17,18} <= {int(r['phase']) for r in rows}, 'Missing pose/lifecycle phases'
            from PIL import Image
            for label in ('idle','forward','right','backward','jump','land','npc_gaits','seat','dismount'):
                with Image.open(out/'captures'/f'{label}.png') as im:
                    assert im.size==(1280,720) and max(hi-lo for lo,hi in im.convert('RGB').getextrema())>100, 'Invalid capture'
            report['pose_frames']=len(rows); report['result']='PASS'
    except (AssertionError,OSError,ValueError,KeyError) as e: report['error']=str(e)
    if report['result']!='PASS':
        with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:
            f.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),type='animation_validation',
                                   status='CONTINUE',diagnostics=report.get('error','Expected RED: missing live skeletal presentation'),evidence=str(out)))+'\n')
    write_json(out/'validation.json',report)
    print(json.dumps({k:report[k] for k in ('task_id','result','scope')} | {'output':str(out),'error':report.get('error')},indent=2))
    return 0 if report['result'] in ('PASS','EXPECTED_RED') else 1

if __name__=='__main__': raise SystemExit(main())
