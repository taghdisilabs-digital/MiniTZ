const set=(key,value)=>document.querySelectorAll(`[data-live="${key}"]`).forEach(el=>el.textContent=value);
const homeMedia=document.querySelector('[data-home-live-media]');
const homeState=document.querySelector('[data-home-live-state]');

function mediaNode(item){
  const wrap=document.createElement('figure');
  wrap.className='home-live-card';
  let media;
  if(item.kind==='video'){
    media=document.createElement('video');
    media.src=item.url;media.muted=true;media.loop=true;media.playsInline=true;media.autoplay=true;media.preload='metadata';
  }else{
    media=document.createElement('img');
    media.src=item.url;media.alt=`Biella production output: ${item.name}`;media.loading='lazy';media.decoding='async';
  }
  const cap=document.createElement('figcaption');
  const name=document.createElement('strong');name.textContent=item.name;
  const source=document.createElement('span');source.textContent=item.source_class||'CURRENT OUTPUT';
  cap.append(name,source);wrap.append(media,cap);return wrap;
}

async function refreshProof(){
  const response=await fetch('./data/investor-snapshot.json',{cache:'no-store'});
  if(!response.ok) throw new Error(`proof ${response.status}`);
  const s=await response.json();
  set('first-playable',`First playable ${s.first_playable.completed_tasks}/${s.first_playable.total_tasks}`);
}

async function refreshLive(){
  const response=await fetch('/live-api/snapshot',{cache:'no-store'});
  if(!response.ok) throw new Error(`live ${response.status}`);
  const s=await response.json();
  const p=s.production||{},progress=p.progress||{};
  set('program-complete',progress.total?`Program ${progress.completed}/${progress.total}`:'Program live');
  set('active-task',`${p.task_id||'UNKNOWN'} · ${p.state||'UNKNOWN'}`);
  set('program-line',`${progress.completed??'—'} of ${progress.total??'—'} production tasks · ${p.task_id||'UNKNOWN'} ${p.task_title||''}`);
  if(homeState)homeState.textContent=`${s.mode||'READ_ONLY_OBSERVER'} · ${(s.connection&&s.connection.state)||'UNKNOWN'} · ${p.state||'UNKNOWN'}`;
  if(homeMedia){
    const stage=s.stage||{};
    const items=[stage.primary,...(stage.showcase||[])].filter(Boolean).slice(0,3);
    if(items.length)homeMedia.replaceChildren(...items.map(mediaNode));
  }
}

refreshProof().catch(()=>{});
refreshLive().catch(()=>{if(homeState)homeState.textContent='VPS LIVE DATA UNAVAILABLE';});
setInterval(refreshLive,60000);
