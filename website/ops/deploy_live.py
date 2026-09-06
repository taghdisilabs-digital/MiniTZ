#!/usr/bin/env python3
import fcntl, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from PIL import Image
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/root/biella/repos/biella-engine')
WEB=REPO/'website'
STATE=Path('/mnt/biella-extra/website-live-deck/state.json')
RECEIPT=Path('/mnt/biella-extra/website-live-deck/deployment.json')
RELEASES=Path('/var/lib/biella-website/releases')
CURRENT=Path('/var/lib/biella-website/current')
LOCK=Path('/run/biella-website-live-deploy.lock')
RELEVANT=('website/','.github/workflows/website-production.yml','docs/task-program/D_TASK_LEDGER.json','docs/project-state/03_BIELLA_CURRENT_STATE.md','docs/project-state/04_BIELLA_ACTIVE_TASK.md','projects/biella-games/docs/PRODUCTION.md')

def run(args,cwd=REPO,env=None):
    return subprocess.check_output(args,cwd=cwd,env=env,text=True,stderr=subprocess.STDOUT).strip()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(obj,indent=2)+'\n'); os.replace(tmp,path)

def main():
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        head=run(['git','rev-parse','HEAD']); tree=run(['git','rev-parse','HEAD^{tree}'])
        remote=run(['git','ls-remote','origin','refs/heads/main']).split()[0]
        state=json.loads(STATE.read_text()) if STATE.exists() else {}
        if remote != head:
            write(STATE,{**state,'last_seen_commit':head,'last_status':'DEFERRED_REMOTE','updated_at':datetime.now(timezone.utc).isoformat()})
            return 0
        last=state.get('last_deployed_commit')
        if last == head: return 0
        relevant=True
        if last:
            try:
                changed=run(['git','diff','--name-only',f'{last}..{head}']).splitlines()
                relevant=any(any(p==r or (r.endswith('/') and p.startswith(r)) for r in RELEVANT) for p in changed)
            except subprocess.CalledProcessError:
                relevant=True
        if not relevant:
            write(STATE,{**state,'last_seen_commit':head,'last_status':'SKIPPED_IRRELEVANT','updated_at':datetime.now(timezone.utc).isoformat()})
            return 0
        env=os.environ.copy(); env.update(BIELLA_SOURCE_COMMIT=head,BIELLA_SOURCE_TREE=tree,BIELLA_SOURCE_BRANCH='main',BIELLA_DEPLOY_ENV='PRODUCTION',BIELLA_DEPLOYMENT_STATUS='PRODUCTION_DEPLOYED')
        subprocess.run(['node','scripts/build.mjs'],cwd=WEB,env=env,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        snap=json.loads((WEB/'dist/data/investor-snapshot.json').read_text())
        active_text=(REPO/'docs/project-state/04_BIELLA_ACTIVE_TASK.md').read_text()
        active=re.search(r'^\s*id:\s*(\S+)',active_text,re.M).group(1)
        assert snap['source']['commit']==head and snap['active_task']['id']==active
        assert snap['program']['completed_tasks']<=snap['program']['total_tasks']
        assert snap['first_playable']['status']=='VERIFIED_COMPLETE'
        page=(WEB/'dist/investors/index.html').read_text(); assert '105 / 219' not in page and '14h 55m' not in page
        release=RELEASES/head
        if release.exists(): shutil.rmtree(release)
        shutil.copytree(WEB/'dist',release)
        # FUNDRAISING_COPY: public/fundraising language is achievement-first.
        # Evidence remains the proof layer; it is not framed as a prohibition on creation.
        public_text=(release/'index.html').read_text()+'\n'+(release/'investors/index.html').read_text()
        for banned in ('does not manufacture it','without pretending','EVIDENCE-GATED','RUNTIME-GATED','Registered, not fabricated','Remote identity or no claim','ACCEPTANCE BOUNDARY','evidence before claims','remain evidence-gated','without inventing a speed claim','No fabricated ARR','pre-commercial'):
            assert banned not in public_text, banned
        assert 'creates, builds, manufactures, tests, debugs, validates, packages, deploys, and publishes' in public_text
        assert 'Capital accelerates an operating system already producing' in public_text
        # Approved deck images contain historical slide text. Render only scenic
        # regions on the live page so pixel text can never contradict live data.
        ref=WEB/'reference/investor-deck-v1'; live_ref=release/'investors/reference'
        crops={
            'scenic-ops.png':('01_founder_execution_engine.png',(900,0,1672,410)),
            'scenic-founder.png':('02_founder_directed_execution_system.png',(950,0,1672,620)),
            'scenic-games.png':('05_games_first_visible_proof.png',(920,0,1672,620)),
        }
        for name,(source,box) in crops.items():
            with Image.open(ref/source) as image: image.crop(box).save(live_ref/name,optimize=True)
        investor=release/'investors/index.html'; html=investor.read_text()
        replacements={
            './reference/02_founder_directed_execution_system.png':'./reference/scenic-founder.png',
            './reference/03_proven_progress.png':'./reference/scenic-ops.png',
            './reference/05_games_first_visible_proof.png':'./reference/scenic-games.png',
            './reference/07_execution_insights.png':'./reference/scenic-ops.png',
            './reference/09_financial_posture.png':'./reference/scenic-founder.png',
            './reference/10_professional_financial_framing.png':'./reference/scenic-founder.png',
        }
        for before,after in replacements.items(): html=html.replace(before,after)
        investor.write_text(html)
        assert not any(name in html for name in ('03_proven_progress.png','07_execution_insights.png','09_financial_posture.png','10_professional_financial_framing.png'))
        link=Path('/var/lib/biella-website/.current-new')
        try: link.unlink()
        except FileNotFoundError: pass
        link.symlink_to(release)
        os.replace(link,CURRENT)
        receipt={'schema':'biella.website.live-deploy/v1','source_commit':head,'source_tree':tree,'active_task':active,'program':snap['program'],'deployed_at':datetime.now(timezone.utc).isoformat(),'investor_page_sha256':sha(release/'investors/index.html'),'snapshot_sha256':sha(release/'data/investor-snapshot.json'),'status':'DEPLOYED_LOCAL_ORIGIN'}
        write(RECEIPT,receipt); write(STATE,{**state,'last_seen_commit':head,'last_deployed_commit':head,'last_overlay_digest':overlay,'last_status':'DEPLOYED','updated_at':receipt['deployed_at']})
        releases=sorted((p for p in RELEASES.iterdir() if p.is_dir()),key=lambda p:p.stat().st_mtime,reverse=True)
        for old in releases[5:]: shutil.rmtree(old,ignore_errors=True)
        return 0
if __name__=='__main__': raise SystemExit(main())
