from pathlib import Path
import copy,hashlib,json,sys,datetime
p=Path.cwd();sys.path.insert(0,str(p/'tests'))
from verify_d03_01_reconstruction import read_rows,verify_rows
base=p/'Build/Presentation';out=base/'reconstruction-controls-01';out.mkdir()
source=base/'reconstruction-taa-01';views=read_rows(source/'native-views.csv');frames=read_rows(source/'frames.csv')
def identity(path):return dict(path=str(path.relative_to(p)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
positive=verify_rows(views,frames,'NativeTAA');target=next(i for i,v in enumerate(views) if v['frame']==frames[len(frames)//2]['frame'] and v['view']==0)
mutations={'actual_aa':('aa',4),'requested_aa':('requested_aa',4),'resolution':('screen_percentage',67),'temporal_upscale':('temporal_upsampling',1),'dynamic_resolution':('dynamic_res',1),'lumen_gi':('gi',0),'lumen_reflections':('reflections',0),'virtual_shadows':('vsm',0),'nanite':('nanite',0),'external_upscaler':('external_upscaler',1),'nonfinite':('aa',float('nan'))}
results=[]
for name,mutation in [*mutations.items(),('missing_view',None),('unordered_views',None)]:
 candidate=copy.deepcopy(views)
 if mutation:candidate[target][mutation[0]]=mutation[1]
 elif name=='missing_view':candidate=[r for r in candidate if r['frame']!=views[target]['frame']]
 else:candidate.reverse()
 try:verify_rows(candidate,frames,'NativeTAA')
 except (AssertionError,KeyError,ValueError) as e:results.append(dict(name=name,result='EXPECTED_REJECTION',row=target,mutation=([mutation[0],str(mutation[1])] if mutation else name),diagnostic=str(e)))
 else:raise AssertionError('False pass '+name)
report=dict(task_id='D03-01',result='PASS',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),positive_replay=positive,source_inputs=[identity(source/name) for name in ['native-views.csv','frames.csv','validation.json']],verifier=identity(p/'tests/verify_d03_01_reconstruction.py'),controls=results,scope='Offline evidence corruption sensitivity; does not simulate unsupported hardware or claim rendered negative controls')
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(results),'controls')
