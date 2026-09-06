const q=(s)=>document.querySelector(s);
const state={snapshot:null,source:null,stageKey:"",refreshTimer:null,elapsedBase:null,elapsedReceived:0,lastHeartbeat:null,staleAfter:25};
const els={
 connection:q('[data-connection]'),connectionDot:q('[data-connection-dot]'),clock:q('[data-clock]'),production:q('[data-production-state]'),taskId:q('[data-task-id]'),taskTitle:q('[data-task-title]'),taskSummary:q('[data-task-summary]'),operation:q('[data-operation]'),operationMeta:q('[data-operation-meta]'),progressLabel:q('[data-progress-label]'),progressBar:q('[data-progress-bar]'),model:q('[data-model]'),reasoning:q('[data-reasoning]'),heartbeat:q('[data-heartbeat]'),elapsed:q('[data-elapsed]'),commit:q('[data-commit]'),validation:q('[data-validation]'),stage:q('[data-stage]'),stageName:q('[data-stage-name]'),stageSource:q('[data-stage-source]'),background:q('[data-background-stack]'),feed:q('[data-feed]'),showcase:q('[data-showcase]'),showcaseCount:q('[data-showcase-count]'),gpuName:q('[data-gpu-name]'),gpuLoad:q('[data-gpu-load]'),gpuMeter:q('[data-gpu-meter]'),gpuPercent:q('[data-gpu-percent]'),vramMeter:q('[data-vram-meter]'),vram:q('[data-vram]'),hostLoad:q('[data-host-load]'),hostRam:q('[data-host-ram]')
};

function setConnection(label){
  els.connection.textContent=label;
  els.connectionDot.className='connection-dot '+(label==='LIVE'?'live':label==='CONNECTING'||label==='RECONNECTING'?'':'stale');
}
function setProduction(label){
  els.production.textContent=label;
  els.production.dataset.state=label;
}
function number(v,fallback=0){return Number.isFinite(Number(v))?Number(v):fallback}
function pct(v){return Math.max(0,Math.min(100,number(v)))}
function shortSha(value){return value&&value!=='UNAVAILABLE'?String(value).slice(0,10):'UNAVAILABLE'}
function duration(seconds){
  if(seconds===null||seconds===undefined||!Number.isFinite(Number(seconds)))return '—';
  let s=Math.max(0,Math.floor(Number(seconds))),h=Math.floor(s/3600);s-=h*3600;const m=Math.floor(s/60);s-=m*60;
  return h?`${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`:`${m}m ${String(s).padStart(2,'0')}s`;
}
function ageText(iso){
  if(!iso)return 'NO HEARTBEAT';
  const age=Math.max(0,(Date.now()-Date.parse(iso))/1000);
  if(age<2)return 'NOW';
  if(age<60)return `${Math.floor(age)}s AGO`;
  return `${Math.floor(age/60)}m AGO`;
}
function eventTime(iso){
  if(!iso)return 'NOW';
  const d=new Date(iso);if(Number.isNaN(d.valueOf()))return 'NOW';
  return d.toLocaleTimeString([],{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function mediaNode(item,thumb=false){
  if(!item)return null;
  if(item.kind==='video'){
    const v=document.createElement('video');v.src=item.url;v.muted=true;v.loop=true;v.playsInline=true;v.autoplay=!thumb;v.preload=thumb?'metadata':'auto';if(!thumb)v.controls=true;return v;
  }
  const img=document.createElement('img');img.src=item.url;img.alt=thumb?'':`Current production output: ${item.name}`;img.loading=thumb?'lazy':'eager';img.decoding='async';return img;
}
function setStage(item,announce=true){
  if(!item)return;
  const key=item.url;
  if(state.stageKey===key)return;
  state.stageKey=key;
  const node=mediaNode(item,false);if(!node)return;
  els.stage.replaceChildren(node);
  els.stageName.textContent=item.name;
  els.stageSource.textContent=item.source_class||'LIVE OUTPUT';
  if(announce)pushFeed({category:'ARTIFACT',state:'CURRENT',text:`Stage updated · ${item.name}`,time:new Date().toISOString(),task_id:state.snapshot?.production?.task_id||''});
}
function renderBackground(items){
  const visuals=(items||[]).filter(x=>x.kind==='image').slice(0,3);
  els.background.replaceChildren(...visuals.map(item=>{const d=document.createElement('div');d.className='background-card';d.style.backgroundImage=`linear-gradient(rgba(4,5,8,.35),rgba(4,5,8,.86)),url("${item.url.replaceAll('"','%22')}")`;return d;}));
}
function renderShowcase(items){
  const list=(items||[]).slice(0,8);els.showcaseCount.textContent=String(list.length);
  const nodes=list.map(item=>{const b=document.createElement('button');b.type='button';b.className='showcase-card';b.title=`Show ${item.name} on stage`;const media=mediaNode(item,true);if(media)b.append(media);const label=document.createElement('span');label.textContent=item.name;b.append(label);b.addEventListener('click',()=>setStage(item,true));return b;});
  els.showcase.replaceChildren(...nodes);renderBackground(list);
}
function updateSystem(system){
  const gpu=system?.gpu||{},host=system?.host||{};
  els.gpuName.textContent=gpu.name||'Unavailable';
  const util=gpu.utilization_percent;els.gpuPercent.textContent=util===null||util===undefined?'—':`${Math.round(number(util))}%`;els.gpuMeter.style.width=`${pct(util)}%`;
  els.gpuLoad.textContent=gpu.temperature_c===null||gpu.temperature_c===undefined?'GPU telemetry unavailable':`${Math.round(number(gpu.temperature_c))}°C · ${number(gpu.power_w).toFixed(0)} W`;
  const used=number(gpu.memory_used_mib),total=number(gpu.memory_total_mib);els.vram.textContent=total?`${(used/1024).toFixed(1)} / ${(total/1024).toFixed(1)} GiB`:'—';els.vramMeter.style.width=`${total?pct(used*100/total):0}%`;
  els.hostLoad.textContent=host.load_1m===null||host.load_1m===undefined?'—':`${number(host.load_1m).toFixed(2)} / ${number(host.cpu_count)} CPU`;
  const ru=number(host.ram_used_mib),rt=number(host.ram_total_mib);els.hostRam.textContent=rt?`${(ru/1024).toFixed(1)} / ${(rt/1024).toFixed(1)} GiB RAM`:'RAM telemetry unavailable';
}
function applySnapshot(data){
  state.snapshot=data;state.lastHeartbeat=data.production?.heartbeat_at||null;state.staleAfter=number(data.connection?.stale_after_seconds,25);state.elapsedBase=data.generated_at?Date.parse(data.generated_at):Date.now();state.elapsedReceived=number(data.production?.elapsed_task_seconds,0);
  setConnection(data.connection?.state||'LIVE');setProduction(data.production?.state||'ERROR');
  els.taskId.textContent=data.production?.task_id||'UNKNOWN';els.taskTitle.textContent=data.production?.task_title||data.production?.task_id||'Unknown task';els.taskSummary.textContent=data.production?.task_summary||'No task summary available.';
  els.model.textContent=data.production?.model||'UNKNOWN';els.reasoning.textContent=data.production?.reasoning||'UNKNOWN';els.heartbeat.textContent=ageText(state.lastHeartbeat);els.elapsed.textContent=duration(state.elapsedReceived);
  const progress=data.production?.progress||{};els.progressLabel.textContent=progress.total?`${progress.completed} / ${progress.total} · ${progress.percent}%`:'NO TOTAL';els.progressBar.style.width=`${pct(progress.percent)}%`;
  const commit=data.production?.commit||{};els.commit.textContent=`${shortSha(commit.commit)} · ${commit.message||'source unavailable'}`;
  const op=data.production?.current_operation;if(op){els.operation.textContent=op.text||'Production state updated';els.operationMeta.textContent=`${op.category||'BIELLA'} · ${op.state||'INFO'} · ${eventTime(op.time)}`;}else{els.operation.textContent='Waiting for production event';els.operationMeta.textContent='BIELLA · WAITING';}
  const validation=data.production?.latest_validation;els.validation.textContent=validation?`${validation.category} ${validation.state} · ${eventTime(validation.time)}`:'NO RECENT RESULT';
  updateSystem(data.system||{});
  if(data.stage?.primary)setStage(data.stage.primary,state.stageKey!=='');renderShowcase(data.stage?.showcase||[]);
}
function pushFeed(event){
  if(!event||event.state==='HEARTBEAT')return;
  const row=document.createElement('div');row.className='feed-item';
  const time=document.createElement('time');time.textContent=eventTime(event.time);
  const kind=document.createElement('span');kind.className='event-kind';kind.dataset.kind=event.category||'TOOL';kind.textContent=event.category||'TOOL';
  const text=document.createElement('span');text.className='event-text';text.textContent=event.text||'Production update';
  const status=document.createElement('span');status.className='event-state '+(String(event.state).toLowerCase()==='failed'?'failed':'');status.textContent=event.state||'INFO';
  row.append(time,kind,text,status);els.feed.prepend(row);while(els.feed.children.length>100)els.feed.lastElementChild.remove();
}
function inferLiveState(event){
  if(!event||event.state!=='RUNNING')return;
  if(event.category==='COMMIT')setProduction('COMMITTING');
  else if(event.category==='TEST'||event.category==='BUILD')setProduction('VALIDATING');
  else setProduction('WORKING');
  els.operation.textContent=event.text||'Production activity';els.operationMeta.textContent=`${event.category||'TOOL'} · ${event.state} · ${eventTime(event.time)}`;
}
function scheduleRefresh(){clearTimeout(state.refreshTimer);state.refreshTimer=setTimeout(fetchSnapshot,1100)}
async function fetchSnapshot(){
  try{const response=await fetch('/live-api/snapshot',{cache:'no-store'});if(!response.ok)throw new Error(`snapshot ${response.status}`);applySnapshot(await response.json());}
  catch(error){if(!state.snapshot){setConnection('ERROR');setProduction('ERROR');els.operation.textContent='VPS snapshot unavailable';els.operationMeta.textContent=String(error.message||error);}}
}
function connect(){
  if(state.source)state.source.close();setConnection('CONNECTING');
  const source=new EventSource('/live-api/events');state.source=source;
  source.onopen=()=>{setConnection('RECONNECTING');fetchSnapshot();};
  source.onmessage=(message)=>{
    let event;try{event=JSON.parse(message.data)}catch{return}
    if(event.state==='HEARTBEAT'){state.lastHeartbeat=event.heartbeat_at||state.lastHeartbeat;updateSystem(event.system||{});if(state.lastHeartbeat&&((Date.now()-Date.parse(state.lastHeartbeat))/1000)<=state.staleAfter)setConnection('LIVE');return;}
    pushFeed(event);inferLiveState(event);scheduleRefresh();
  };
  source.onerror=()=>{setConnection('RECONNECTING');setProduction('RECONNECTING');};
}
function tick(){
  const now=new Date();els.clock.textContent=now.toLocaleTimeString([],{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
  if(state.elapsedBase!==null)els.elapsed.textContent=duration(state.elapsedReceived+Math.max(0,(Date.now()-state.elapsedBase)/1000));
  els.heartbeat.textContent=ageText(state.lastHeartbeat);
  if(state.lastHeartbeat){const age=(Date.now()-Date.parse(state.lastHeartbeat))/1000;if(age>state.staleAfter){setConnection('STALE');setProduction('STALE');}}
}
fetchSnapshot();connect();tick();setInterval(tick,1000);
