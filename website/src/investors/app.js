const els=key=>[...document.querySelectorAll(`[data-live="${key}"]`)];
const set=(key,value)=>els(key).forEach(el=>el.textContent=value);
const fmtTime=value=>{try{return new Date(value).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'medium'});}catch{return value;}};
let staticSnapshot=null,source=null,timer=null;

function applyStatic(s){
  staticSnapshot=s;
  set('first-playable',`${s.first_playable.completed_tasks} / ${s.first_playable.total_tasks}`);
  const list=document.getElementById('evidence-sources');
  if(list)list.replaceChildren(...s.evidence_sources.map(src=>{const li=document.createElement('li');li.textContent=src;return li;}));
}
function applyLive(s){
  const p=s.production||{},progress=p.progress||{},commit=p.commit||{};
  const completed=Number(progress.completed||0),total=Number(progress.total||0),percent=total?completed*100/total:0;
  set('program-complete',total?`${completed} / ${total}`:'—');
  set('completed-count',String(completed));set('remaining-count',String(Math.max(0,total-completed)));set('program-percent',`${percent.toFixed(1)}%`);
  set('active-task',p.task_id||'UNKNOWN');set('active-task-title',p.task_title||p.task_summary||'Current production');
  const sha=commit.commit||'UNAVAILABLE';set('source-short',sha.slice(0,12));set('source-commit',sha);set('snapshot-time',fmtTime(s.generated_at));
  const status=document.getElementById('live-status');
  if(status)status.textContent=`Live VPS projection · ${completed}/${total||'—'} production tasks · ${p.task_id||'UNKNOWN'} · ${p.model||'UNKNOWN'} / ${p.reasoning||'UNKNOWN'}`;
}
async function refreshStatic(){const r=await fetch('../data/investor-snapshot.json',{cache:'no-store'});if(!r.ok)throw new Error(`static ${r.status}`);applyStatic(await r.json());}
async function refreshLive(){clearTimeout(timer);const r=await fetch('/live-api/snapshot',{cache:'no-store'});if(!r.ok)throw new Error(`live ${r.status}`);applyLive(await r.json());}
function schedule(delay=180){clearTimeout(timer);timer=setTimeout(()=>refreshLive().catch(()=>{}),delay);}
function connect(){
  if(source)source.close();source=new EventSource('/live-api/events');
  source.onopen=()=>schedule(0);source.onmessage=message=>{let event;try{event=JSON.parse(message.data)}catch{return}if(event.state!=='HEARTBEAT')schedule();};
  source.onerror=()=>{const el=document.getElementById('live-status');if(el)el.textContent='Live projection reconnecting…';};
}
refreshStatic().catch(()=>{});refreshLive().catch(error=>{const el=document.getElementById('live-status');if(el)el.textContent=`Live evidence unavailable: ${error.message}`;});connect();setInterval(()=>refreshLive().catch(()=>{}),15000);
