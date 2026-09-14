#!/usr/bin/env python3
"""Negative controls against retained real runtime evidence; no synthetic pass fixture."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import re
import tempfile
from verify_d02_02 import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--count', type=int, required=True)
    args = parser.parse_args()
    verify(args.evidence, args.count)
    checks = {}
    with tempfile.TemporaryDirectory(prefix='biella-population-verifier-') as temp:
        root = Path(temp)
        def run(name, mutate):
            target = root/name
            shutil.copytree(args.evidence, target)
            mutate(target)
            try:
                verify(target, args.count)
            except (ValueError, AssertionError, KeyError) as error:
                checks[name] = dict(result='REJECTED', reason=str(error))
            else:
                raise AssertionError(f'Corrupted evidence accepted: {name}')
        def replace(path, old, new):
            value = path.read_text()
            assert old in value
            path.write_text(value.replace(old,new))
        def change_result(path,key,value):
            data=json.loads((path/'result.json').read_text());data[key]=value
            (path/'result.json').write_text(json.dumps(data))
        def change_frame(path,field,value):
            reader=csv.DictReader((path/'frames.csv').open());fields=reader.fieldnames;rows=list(reader)
            rows[len(rows)//2][field]=str(value)
            with (path/'frames.csv').open('w') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        def duplicate_spawn(path):
            log=path/'runtime.stdout.log';content=log.read_text()
            line=next(x for x in content.splitlines() if 'D02_POP SPAWN id=D02Pop_Street03_' in x)
            log.write_text(content+'\n'+line+'\n')
        def heal_resume(path):
            for name in ('events.log','runtime.stdout.log'):
                file=path/name
                file.write_text(re.sub(r'(event=resumed id=\S+ health=)[\d.]+',r'\g<1>999.000',file.read_text()))
        run('missing_continuity',lambda p: replace(p/'events.log','event=continuity_tombstones_pass','event=omitted'))
        run('duplicate_identity',duplicate_spawn)
        run('wrong_candidate',lambda p: change_result(p,'count',999))
        run('synthetic_timestep',lambda p: change_result(p,'fixed_timestep',True))
        run('missing_frame',lambda p: change_frame(p,'frame',0))
        run('forged_wall_interval',lambda p: change_frame(p,'wall_ms',9999))
        run('hidden_overlap',lambda p: change_frame(p,'overlap_pairs',1))
        run('impossible_population',lambda p: change_frame(p,'active',99))
        run('missing_autonomous_damage',lambda p: replace(p/'runtime.stdout.log','D01_SIGNAL DAMAGE','IGNORED_DAMAGE'))
        run('healed_resume',heal_resume)
        # A missing dynamic replan cannot pass merely because the arrival event exists.
        run('missing_obstacle_replan',lambda p: replace(p/'runtime.stdout.log','D02_POP PATH actor=BiellaPopulationInfected_','IGNORED_PATH actor=BiellaPopulationInfected_'))
    print(json.dumps(dict(result='PASS', real_baseline='PASS', rejected=len(checks),checks=checks),indent=2))

if __name__=='__main__':
    main()
