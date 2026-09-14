from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,sys
from PIL import Image
p=Path(__file__).resolve().parents[3];b=p/'Build/Presentation';sys.path.insert(0,str(p/'tests'))
from verify_d03_01_reconstruction import verify as views
from verify_d03_01_surfaces import verify as surfaces
from verify_d02_04 import verify as environment

def read(path):return json.loads(path.read_text())
def identity(path):return dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
def exact(e):
 q=identity(Path(e['path']));assert q==e,e['path'];return q

def main():
 names=['reconstruction-tsr-02','reconstruction-taa-01','reconstruction-environment-tsr-01','reconstruction-environment-taa-01','reconstruction-invalid-01','reconstruction-override-01']
 all_inputs={};runtimes=[];captures=[]
 for name in names:
  out=b/name;d=read(out/'validation.json');negative=name=='reconstruction-override-01'
  assert d['result']==('FAIL' if negative else 'PASS'),name
  assert d['identities_before']==d['identities_after'],name
  rt=d['runtime'];assert rt['returncode']==0 and not rt['timed_out'] and rt['log_finalization']['closed'],name
  assert d['protected_before'][-1]==d['protected_after'][-1];exact(d['protected_after'][-1])
  for e in d['identities_before']:
   if e['path'] in all_inputs:assert all_inputs[e['path']]==e,e['path']
   all_inputs[e['path']]=e
  if negative:
   assert d['error']=='Native view invariant failed: aa=4',d.get('error')
   control=read(out/'negative-readback.json');assert control['result']=='EXPECTED_NEGATIVE_CONTROL'
   replay=None
  else:
   replay=views(out,d['expected_profile']);assert replay==d['native_views'],name
   scenario=surfaces(out,4 if d['expected_profile']=='ProductionTSR' else 2,100) if d['scenario']=='surfaces' else environment(out)
   assert scenario==d['verification'],name
  for q in sorted((out/'captures').glob('*.png')):
   with Image.open(q) as im:
    im.load();assert im.size==(1280,720) and im.format=='PNG',q
   captures.append(identity(q))
  runtimes.append(dict(report=identity(out/'validation.json'),result='EXPECTED_NEGATIVE_CONTROL' if negative else 'PASS',views=replay))
 for e in all_inputs.values():exact(e)
 build=b/'reconstruction-build-01';result=read(build/'result.json');assert result['returncode']==0 and result['inputs_unchanged']
 source=read(build/'inputs-before.json');assert source==read(build/'inputs-after.json')
 for e in source:
  absolute=e|dict(path=str(p/e['path']));assert all_inputs[absolute['path']]==absolute;exact(absolute)
 preservation=read(b/'D03-01-reconstruction-preservation.json');assert preservation['result']=='PASS'
 controls=read(b/'reconstruction-controls-01/result.json');assert controls['result']=='PASS' and len(controls['controls'])==13
 for e in controls['source_inputs']+[controls['verifier']]:exact(e|dict(path=str(p/e['path'])))
 review=read(b/'reconstruction-visual-review-01.json')
 for e in review['inspected']:exact(e|dict(path=str(p/e['path'])))
 receipt=dict(schema='biella.d03_01.reconstruction_readback/v1',task_id='D03-01',task_status='CONTINUE',result='PASS',time=datetime.now(timezone.utc).isoformat(),unique_input_identities=len(all_inputs),all_inputs_match_current_bytes=True,build_source_files=len(source),build_source_matches_runtime=True,module=identity(p/'Binaries/Linux/libUnrealEditor-BiellaGames.so'),native_build=identity(build/'result.json'),runtimes=runtimes,captures=captures,controls=identity(b/'reconstruction-controls-01/result.json'),visual_review=identity(b/'reconstruction-visual-review-01.json'),preservation=identity(b/'D03-01-reconstruction-preservation.json'),publication={'owner':'Auto Feeder','remote_publication_claimed':False},limitations=['Linux Vulkan Development existing DDC; no cold shader/PSO or packaged qualification','Observed L40S supports TSR; unavailable-TSR hardware branch is source-reviewed but untested','Constructed native game-thread views and cvars; no generated frames or unsupported platform claims','Blockout art and limited camera/interaction coverage remain; full D03-01 is CONTINUE'])
 dest=b/'D03-01-reconstruction-final-readback-01.json';assert not dest.exists();dest.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(result='PASS',inputs=len(all_inputs),build_source_files=len(source),captures=len(captures),runtime_scenarios=len(names))))

if __name__=='__main__':
 try:main()
 except Exception as e:
  with Path('/mnt/biella-extra/biella-runtime/codex-production/failures.jsonl').open('a') as f:f.write(json.dumps(dict(task_id='D03-01',time=datetime.now(timezone.utc).isoformat(),type='reconstruction_final_readback',status='CONTINUE',diagnostics=str(e)))+'\n')
  raise
