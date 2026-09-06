import json,hashlib,os,subprocess,datetime
from pathlib import Path
p=Path.cwd(); b=p/'Build/Presentation'
prior=json.loads((b/'D03-01-seat-preservation.json').read_text())
refs=[(v['manifest'],v['commit']) for v in prior['manifests']]+[('Build/Presentation/D03-01-seat-file-manifest.json','6ab06eb0de3d73259552d82c37016a6b3fd415d2')]
allowed={v['path'] for v in prior['authorized_source_extensions']}
changed=subprocess.check_output(['git','diff','--name-only','--relative'],text=True).splitlines()
assert all(v.startswith('Source/') for v in changed),changed
allowed.update(changed)
proc=subprocess.Popen(['git','cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def blob(commit,rel):
 proc.stdin.write((commit+':projects/biella-games/'+rel+'\n').encode());proc.stdin.flush()
 h=proc.stdout.readline().split();assert len(h)==3 and h[1]==b'blob',h
 n=int(h[2]);data=proc.stdout.read(n);assert len(data)==n and proc.stdout.read(1)==b'\n'
 return data
local_cache={}
def local(rel):
 if rel not in local_cache:
  q=p/rel;v=os.readlink(q).encode() if q.is_symlink() else q.read_bytes();local_cache[rel]=(len(v),hashlib.sha256(v).hexdigest())
 return local_cache[rel]
report=dict(task_id='D03-01',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),result='PASS',manifests=[],total_entries=0,unchanged_entries=0,authorized_source_extensions=[],original_source_bytes_preserved_in_commits=True)
for rel,commit in refs:
 raw=blob(commit,rel);assert raw==(p/rel).read_bytes(),rel
 manifest=json.loads(raw);unchanged=0
 for e in manifest['files']:
  original=blob(commit,e['path']);assert len(original)==e.get('bytes',e.get('size')) and hashlib.sha256(original).hexdigest()==e['sha256'],e['path']
  n,digest=local(e['path'])
  if n==e.get('bytes',e.get('size')) and digest==e['sha256']: unchanged+=1
  else:
   assert e['path'] in allowed,e['path']
   report['authorized_source_extensions'].append(dict(path=e['path'],previous_commit=commit,previous_sha256=e['sha256'],current_sha256=digest,reason='Authorized D03 source/test extension; exact original remains in predecessor commit'))
 report['manifests'].append(dict(manifest=rel,sha256=hashlib.sha256(raw).hexdigest(),commit=commit,entries=len(manifest['files']),unchanged_entries=unchanged,manifest_bytes_preserved=True))
 report['total_entries']+=len(manifest['files']);report['unchanged_entries']+=unchanged
proc.stdin.close();assert proc.wait()==0
(b/'D03-01-reconstruction-preservation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('manifests','authorized_source_extensions')}))
