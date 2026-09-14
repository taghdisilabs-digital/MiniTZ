const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
let portfolio=null,media=null,activeFilter='All';
const statusLabel=s=>String(s||'UNKNOWN').replaceAll('_',' ');

function mediaElement(item,{compact=false}={}){
  const wrap=document.createElement('figure');wrap.className=compact?'media-thumb':'project-media';
  const el=document.createElement(item.kind==='video'?'video':'img');
  el.src=item.public_path;
  if(item.kind==='video'){el.muted=true;el.loop=true;el.playsInline=true;el.autoplay=compact;el.preload='metadata';}
  else{el.alt=item.title;el.loading='lazy';el.decoding='async';}
  wrap.append(el);
  if(compact){const cap=document.createElement('figcaption');cap.className='media-label';cap.textContent=`${item.title} · ${statusLabel(item.status)}`;wrap.append(cap);}
  return wrap;
}
function firstMedia(projectId){return media?.items?.find(item=>item.project_id===projectId)||null;}
function renderProjects(){
  const grid=$('[data-project-grid]');if(!grid||!portfolio)return;
  const shown=portfolio.items.filter(item=>activeFilter==='All'||item.category===activeFilter);
  grid.replaceChildren(...shown.map(item=>{
    const article=document.createElement('article');article.className='project-card';article.dataset.projectCard='';article.dataset.projectId=item.id;
    const m=firstMedia(item.id);if(m)article.append(mediaElement(m));else{const empty=document.createElement('div');empty.className='project-media empty';article.append(empty);}
    const copy=document.createElement('div');copy.className='project-copy';
    const meta=document.createElement('div');meta.className='project-meta';meta.innerHTML=`<span>${item.category}</span><span>${item.period}</span>`;
    const h=document.createElement('h3');h.textContent=item.title;
    const p=document.createElement('p');p.textContent=item.summary;
    const foot=document.createElement('div');foot.className='project-foot';
    const st=document.createElement('span');st.className=`status ${item.status.toLowerCase()}`;st.textContent=statusLabel(item.status);
    const link=document.createElement('a');link.className='evidence-link';link.href=item.evidence_url;link.textContent='Evidence ↗';if(/^https?:/.test(item.evidence_url)){link.target='_blank';link.rel='noreferrer';}
    foot.append(st,link);copy.append(meta,h,p,foot);article.append(copy);return article;
  }));
}
function renderFilters(){
  const host=$('[data-project-filters]');if(!host||!portfolio)return;
  const preferred=['All','MiniTZ','Games','Websites','Apps','Client Work','MiniTZ','Systems','Visual / IP'];
  const categories=new Set(portfolio.items.map(i=>i.category));
  const names=preferred.filter(n=>n==='All'||categories.has(n));
  host.replaceChildren(...names.map(name=>{const b=document.createElement('button');b.type='button';b.textContent=name;b.setAttribute('aria-pressed',String(name===activeFilter));b.addEventListener('click',()=>{activeFilter=name;$$('button',host).forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderProjects();});return b;}));
}
function renderPreview(){const host=$('[data-archive-preview]');if(!host||!media)return;const picks=media.items.slice(0,8);host.replaceChildren(...picks.map(i=>mediaElement(i,{compact:true})));}
async function loadPortfolio(){
  const [pr,mr]=await Promise.all([fetch('/data/portfolio-index.json',{cache:'no-store'}),fetch('/data/portfolio-media.json',{cache:'no-store'})]);
  if(!pr.ok||!mr.ok)throw new Error('portfolio data unavailable');portfolio=await pr.json();media=await mr.json();
  $('[data-project-count]').textContent=portfolio.items.length;$('[data-media-count]').textContent=media.items.length;renderFilters();renderProjects();renderPreview();
}
function applyLive(s){
  const p=s.production||{},coders=p.main_coders||{};const state=(s.connection?.state||'UNKNOWN')+' · '+(p.state||'UNKNOWN');
  $('[data-live-state]').textContent=state;$('[data-live-task]').textContent=`${p.task_id||'UNKNOWN'}${p.task_title?' · '+p.task_title:''}`;
  $('[data-live-resource]').textContent=p.active_coder||p.model||'UNKNOWN';$('[data-live-codex]').textContent=statusLabel(coders.codex);
}
async function refreshLive(){const r=await fetch('/live-api/snapshot',{cache:'no-store'});if(!r.ok)throw new Error(`live ${r.status}`);applyLive(await r.json());}
function connectLive(){try{const source=new EventSource('/live-api/events');source.onmessage=e=>{let v;try{v=JSON.parse(e.data)}catch{return}if(v.state!=='HEARTBEAT')setTimeout(()=>refreshLive().catch(()=>{}),300);};source.onerror=()=>{};}catch{}}
loadPortfolio().catch(()=>{});refreshLive().catch(()=>{$('[data-live-state]').textContent='LIVE DATA UNAVAILABLE';});connectLive();setInterval(()=>refreshLive().catch(()=>{}),15000);
