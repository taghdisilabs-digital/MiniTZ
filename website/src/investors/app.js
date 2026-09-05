const els = key => [...document.querySelectorAll(`[data-live="${key}"]`)];
const set = (key,value) => els(key).forEach(el => el.textContent = value);
const fmtTime = value => { try { return new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'medium'}); } catch { return value; } };
async function refresh(){
  const response = await fetch('../data/investor-snapshot.json',{cache:'no-store'});
  if(!response.ok) throw new Error(`snapshot ${response.status}`);
  const s = await response.json();
  set('first-playable',`${s.first_playable.completed_tasks} / ${s.first_playable.total_tasks}`);
  set('program-complete',`${s.program.completed_tasks} / ${s.program.total_tasks}`);
  set('completed-count',String(s.program.completed_tasks));
  set('remaining-count',String(s.program.remaining_tasks));
  set('program-percent',`${s.program.completed_percent.toFixed(1)}%`);
  set('active-task',s.active_task.id);
  set('active-task-title',s.active_task.title);
  set('source-short',s.source.commit.slice(0,12));
  set('source-commit',s.source.commit);
  set('snapshot-time',fmtTime(s.generated_at));
  const list=document.getElementById('evidence-sources');
  if(list){list.replaceChildren(...s.evidence_sources.map(src=>{const li=document.createElement('li');li.textContent=src;return li;}));}
  const status=document.getElementById('live-status');
  if(status) status.textContent=`Verified snapshot loaded · ${s.program.completed_tasks}/${s.program.total_tasks} completion-class tasks · active ${s.active_task.id}`;
}
refresh().catch(error=>{const el=document.getElementById('live-status');if(el)el.textContent=`Live evidence unavailable: ${error.message}`;});
setInterval(refresh,60000);
