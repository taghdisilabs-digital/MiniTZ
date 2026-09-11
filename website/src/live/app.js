const film=document.querySelector('[data-film]');
const line=document.querySelector('[data-film-line]');
const context=document.querySelector('[data-context]');
const replay=document.querySelector('[data-replay]');
const progress=document.querySelector('[data-film-progress]');

const beats=[
  {at:0,line:'I can code.',context:'After school · outside',a:'#a36235',b:'#2c201b'},
  {at:1500,line:'I can build.',context:'Independent shop · working day',a:'#81613d',b:'#32261d'},
  {at:3000,line:'I can create.',context:'At home · afternoon light',a:'#a47b53',b:'#3e2f25'},
  {at:4500,line:'I can design.',context:'Workshop · unfinished work',a:'#53636a',b:'#1f292d'},
  {at:6000,line:'I can make.',context:'City street · in motion',a:'#786844',b:'#252522'},
  {at:7500,line:'I can code.',context:'Construction site · daylight',a:'#75634e',b:'#282725'},
  {at:9000,line:'I can build.',context:'Kitchen · steam · service',a:'#6a6259',b:'#252221'},
  {at:10000,line:'I can create.',context:'Studio · pigment · hands',a:'#6d4c48',b:'#292024'},
  {at:11000,line:'I can automate.',context:'Garage · work lights',a:'#4d5557',b:'#1e2325'},
  {at:12000,line:'I can make.',context:'Home · ordinary afternoon',a:'#806450',b:'#2b231e'},
  {at:13000,line:'I can build.',context:'Workshop · weathered hands',a:'#695746',b:'#27211d'},
  {at:14000,line:'I can.',context:'Face · eyes · certainty',a:'#3b3030',b:'#171313'},
  {at:14700,line:'I can.',context:'Different person · same certainty',a:'#353b3d',b:'#151819'},
  {at:15300,line:'I can.',context:'Calm · direct · certain',a:'#443a32',b:'#181513'}
];

let timers=[];
let progressTimer=null;
let startedAt=0;
function clearRun(){
  timers.forEach(clearTimeout);
  timers=[];
  cancelAnimationFrame(progressTimer);
}
function setBeat(beat){
  film.classList.add('is-changing');
  setTimeout(()=>{
    line.textContent=beat.line;
    context.textContent=beat.context;
    film.style.setProperty('--wash-a',beat.a);
    film.style.setProperty('--wash-b',beat.b);
    film.classList.remove('is-changing');
  },170);
}
function tick(){
  const elapsed=Math.min(performance.now()-startedAt,20000);
  progress.style.width=`${elapsed/200}%`;
  if(elapsed<20000) progressTimer=requestAnimationFrame(tick);
}
function play(){
  clearRun();
  film.className='film';
  film.style.removeProperty('--wash-a');
  film.style.removeProperty('--wash-b');
  line.textContent=beats[0].line;
  context.textContent=beats[0].context;
  progress.style.width='0';
  startedAt=performance.now();  beats.slice(1).forEach(beat=>timers.push(setTimeout(()=>setBeat(beat),beat.at)));
  timers.push(setTimeout(()=>{
    film.classList.add('is-black');
    line.textContent='';
    context.textContent='';
  },16000));
  timers.push(setTimeout(()=>film.classList.add('is-reveal'),17000));
  timers.push(setTimeout(()=>film.classList.add('show-tagline'),18500));
  progressTimer=requestAnimationFrame(tick);
}

replay?.addEventListener('click',play);
if(matchMedia('(prefers-reduced-motion: reduce)').matches){
  film.classList.add('is-black','is-reveal','show-tagline');
  progress.style.width='100%';
}else{
  play();
}
