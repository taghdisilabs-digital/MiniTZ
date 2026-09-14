const q=(s)=>document.querySelector(s);
const qa=(s)=>[...document.querySelectorAll(s)];
const state={snapshot:null,source:null,lastHeartbeat:null,staleAfter:75,elapsedBase:null,elapsedReceived:0,locker:[],lockerFilter:'ALL'};
const text=(sel,value)=>{const el=q(sel);if(el)el.textContent=value??'—';};
const number=(v,f=0)=>Number.isFinite(Number(v))?Number(v):f;
const shortSha=(v)=>v?String(v).slice(0,10):'—';
const formatDuration=(seconds)=>{if(!Number.isFinite(Number(seconds)))return '—';let s=Math.max(0,Math.floor(Number(seconds))),h=Math.floor(s/3600);s-=h*3600;const m=Math.floor(s/60);s-=m*60;return h?`${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`:`${m}m ${String(s).padStart(2,'0')}s`;};
const ageText=(iso)=>{if(!iso)return 'NO SIGNAL';const age=Math.max(0,(Date.now()-Date.parse(iso))/1000);if(age<2)return 'NOW';if(age<60)return `${Math.floor(age)}s AGO`;return `${Math.floor(age/60)}m AGO`;};
const eventTime=(iso)=>{const d=new Date(iso||Date.now());return Number.isNaN(d.valueOf())?'NOW':d.toLocaleTimeString([],{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});};

function setConnection(label){
  qa('[data-connection]').forEach(el=>el.textContent=label);
  text('[data-connection-secondary]',label);
  qa('[data-connection-dot]').forEach(el=>{el.classList.toggle('live',label==='LIVE');});
}

function applySnapshot(data){
  state.snapshot=data;
  const p=data.production||{}, system=data.system||{}, gpu=system.gpu||{}, host=system.host||{}, local=system.local_ai||{};
  state.lastHeartbeat=p.heartbeat_at||null;
  state.staleAfter=number(data.connection?.stale_after_seconds,75);
  state.elapsedBase=data.generated_at?Date.parse(data.generated_at):Date.now();
  state.elapsedReceived=number(p.elapsed_task_seconds,0);
  setConnection(data.connection?.state||'LIVE');
  text('[data-task-id]',p.task_id||'—');
  text('[data-task-title]',p.task_title||'Current MiniTZ OS task');
  text('[data-task-summary]',p.task_summary||'Live task state is available.');
  text('[data-production-state]',p.state||p.task_status||'—');
  const progress=p.progress||{};
  text('[data-progress-label]',progress.total?`${progress.completed} / ${progress.total} · ${progress.percent}%`:'—');
  const op=p.current_operation;
  text('[data-operation]',op?.text||'Waiting for next activity');
  text('[data-operation-meta]',op?`${op.category||'WORK'} · ${op.state||'INFO'} · ${eventTime(op.time)}`:'—');
  const coders=p.main_coders||{};
  text('[data-coder-codex]',String(coders.codex||'NOT REPORTED').replaceAll('_',' '));
  text('[data-coder-agr]',String(coders.agr||'NOT REPORTED').replaceAll('_',' '));
  const commanders=p.commanders||{};
  text('[data-commander-state]',String(commanders.status||'NOT REPORTED').replaceAll('_',' '));
  text('[data-commander-meta]',commanders.total_lanes!==undefined?`${number(commanders.active)} active · ${number(commanders.inflight)} inflight · ${number(commanders.total_lanes,30)} total`:'No public commander summary');
  const boosts=p.boosts||{};
  text('[data-boost-state]',String(boosts.runtime_state||boosts.status||'NOT REPORTED').replaceAll('_',' '));
  if(Array.isArray(boosts.boosts)){
    const active=boosts.boosts.filter(x=>!['COMPLETE','NO_CURRENT_TASK'].includes(String(x.status||''))).length;
    text('[data-boost-meta]',`${active} assigned · ${number(boosts.total_boosts,boosts.boosts.length)} groups · ${number(boosts.total_commanders,30)} commanders`);
  }else text('[data-boost-meta]','Waiting for public Boost summary');
  text('[data-local-ai]',String(local.state||'NOT REPORTED').replaceAll('_',' '));
  text('[data-local-ai-meta]',local.vram_mib?`${(number(local.vram_mib)/1024).toFixed(1)} GiB resident`:'No resident-memory figure');
  text('[data-gpu-name]',gpu.name?`${gpu.name} · ${Math.round(number(gpu.utilization_percent))}%`:'NOT REPORTED');
  text('[data-gpu-load]',gpu.temperature_c!==null&&gpu.temperature_c!==undefined?`${Math.round(number(gpu.temperature_c))}°C · ${number(gpu.power_w).toFixed(0)} W`:'No live GPU load');
  const used=number(gpu.memory_used_mib),total=number(gpu.memory_total_mib);
  text('[data-vram]',total?`${(used/1024).toFixed(1)} / ${(total/1024).toFixed(1)} GiB`:'—');
  text('[data-host-load]',host.load_1m!==null&&host.load_1m!==undefined?`${number(host.load_1m).toFixed(2)} load · ${number(host.cpu_count)} CPU`:'—');
  const ru=number(host.ram_used_mib),rc=number(host.ram_cache_mib),rt=number(host.ram_total_mib);
  text('[data-host-ram]',rt?`${(ru/1024).toFixed(1)} active + ${(rc/1024).toFixed(1)} cache / ${(rt/1024).toFixed(1)} GiB RAM`:'—');
  const validation=p.latest_validation;
  text('[data-validation]',validation?`${validation.state} · ${eventTime(validation.time)}`:'WAITING');
  text('[data-commit]',shortSha(p.commit?.commit));
  text('[data-heartbeat]',ageText(state.lastHeartbeat));
  text('[data-continuity]',String(p.continuity_status||'—').replaceAll('_',' '));
  text('[data-elapsed]',formatDuration(state.elapsedReceived));
}

function pushEvent(event){
  if(!event||event.state==='HEARTBEAT')return;
  const feed=q('[data-feed]'); if(!feed)return;
  const row=document.createElement('div');row.className='event-row';
  const t=document.createElement('time');t.textContent=eventTime(event.time);
  const kind=document.createElement('span');kind.className='event-kind';kind.textContent=event.category||'WORK';
  const msg=document.createElement('span');msg.textContent=event.text||'MiniTZ OS activity';
  const status=document.createElement('span');status.className='event-state';status.textContent=event.state||'INFO';
  row.append(t,kind,msg,status);feed.prepend(row);
  while(feed.children.length>12)feed.lastElementChild.remove();
}

async function fetchSnapshot(){
  try{
    const response=await fetch('/live-api/snapshot',{cache:'no-store'});
    if(!response.ok)throw new Error(`snapshot ${response.status}`);
    applySnapshot(await response.json());
  }catch(error){
    if(!state.snapshot){setConnection('OFFLINE');text('[data-production-state]','OFFLINE');text('[data-operation]','Live projection unavailable');}
  }
}

function connectEvents(){
  if(state.source)state.source.close();
  const source=new EventSource('/live-api/events');state.source=source;
  source.onopen=()=>{setConnection('LIVE');fetchSnapshot();};
  source.onmessage=(message)=>{
    let event;try{event=JSON.parse(message.data)}catch{return;}
    if(event.state==='HEARTBEAT'){
      state.lastHeartbeat=event.heartbeat_at||state.lastHeartbeat;
      if(event.system&&state.snapshot)applySnapshot({...state.snapshot,system:event.system,production:{...state.snapshot.production,heartbeat_at:state.lastHeartbeat}});
      return;
    }
    pushEvent(event);setTimeout(fetchSnapshot,500);
  };
  source.onerror=()=>setConnection('RECONNECTING');
}

function renderLocker(){
  const root=q('[data-locker-list]');if(!root)return;
  const entries=state.locker.filter(e=>state.lockerFilter==='ALL'||e.type===state.lockerFilter);
  if(!entries.length){root.replaceChildren(Object.assign(document.createElement('p'),{className:'locker-loading',textContent:'No verified entries in this view.'}));return;}
  const nodes=entries.map(entry=>{
    const article=document.createElement('article');article.className='locker-entry';article.dataset.type=entry.type;
    const opener=document.createElement('button');opener.type='button';opener.setAttribute('aria-expanded','false');
    const time=document.createElement('time');time.dateTime=entry.timestamp;time.textContent=new Date(entry.timestamp).toLocaleDateString([],{year:'numeric',month:'short',day:'2-digit'});
    const type=document.createElement('span');type.className='locker-type';type.textContent=entry.type;
    const title=document.createElement('h3');title.textContent=entry.title;
    const toggle=document.createElement('span');toggle.className='toggle';toggle.textContent='+';toggle.setAttribute('aria-hidden','true');
    opener.append(time,type,title,toggle);
    const drawer=document.createElement('div');drawer.className='locker-drawer';
    const inner=document.createElement('div');inner.className='locker-drawer-inner';
    const detail=document.createElement('div');detail.className='locker-detail';
    const summary=document.createElement('p');summary.className='locker-summary';summary.textContent=entry.summary;detail.append(summary);
    const tags=document.createElement('div');tags.className='locker-tags';(entry.capability_tags||[]).forEach(tag=>{const s=document.createElement('span');s.textContent=tag;tags.append(s);});detail.append(tags);
    if(entry.media?.length){const media=document.createElement('div');media.className='locker-media';entry.media.forEach(item=>{if(item.kind==='image'){const img=document.createElement('img');img.src=item.url;img.alt=item.alt||entry.title;img.loading='lazy';img.decoding='async';media.append(img);}});detail.append(media);}
    const proof=document.createElement('div');proof.className='locker-proof';const label=document.createElement('b');label.textContent='Evidence';const p=document.createElement('p');p.textContent=entry.evidence_summary;proof.append(label,p);detail.append(proof);
    inner.append(detail);drawer.append(inner);article.append(opener,drawer);
    opener.addEventListener('click',()=>{const open=!article.classList.contains('is-open');article.classList.toggle('is-open',open);opener.setAttribute('aria-expanded',String(open));});
    return article;
  });
  root.replaceChildren(...nodes);
}

async function loadLocker(){
  try{const r=await fetch('/data/locker-index.json',{cache:'no-store'});if(!r.ok)throw new Error();const data=await r.json();state.locker=Array.isArray(data.entries)?data.entries:[];renderLocker();}
  catch{const root=q('[data-locker-list]');if(root)root.textContent='Verified Locker index is temporarily unavailable.';}
}

function setupExperience(){
  const film=q('[data-final-film]'),play=q('[data-film-play]');
  if(film&&play){
    play.addEventListener('click',async()=>{
      film.muted=false;
      film.volume=1;
      film.currentTime=0;
      try{
        await film.play();
        play.classList.add('is-hidden');
      }catch{
        play.querySelector('span').textContent='Tap again to play';
      }
    });
    film.addEventListener('ended',()=>{
      play.classList.remove('is-hidden');
      const label=play.querySelector('span');if(label)label.textContent='Replay the film';
    });
  }
  const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('is-visible');}),{threshold:.14,rootMargin:'0px 0px -6% 0px'});
  qa('.reveal-on-scroll').forEach(el=>observer.observe(el));
  qa('[data-locker-filter]').forEach(btn=>btn.addEventListener('click',()=>{state.lockerFilter=btn.dataset.lockerFilter;qa('[data-locker-filter]').forEach(b=>b.classList.toggle('is-active',b===btn));renderLocker();}));
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&film&&!film.paused)film.pause();});
}

function tick(){
  text('[data-heartbeat]',ageText(state.lastHeartbeat));
  if(state.elapsedBase!==null)text('[data-elapsed]',formatDuration(state.elapsedReceived+Math.max(0,(Date.now()-state.elapsedBase)/1000)));
  if(state.lastHeartbeat&&((Date.now()-Date.parse(state.lastHeartbeat))/1000)>state.staleAfter)setConnection('STALE');
}

setupExperience();loadLocker();fetchSnapshot();connectEvents();tick();
setInterval(tick,1000);setInterval(fetchSnapshot,5000);
