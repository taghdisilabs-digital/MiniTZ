const set=(key,value)=>document.querySelectorAll(`[data-live="${key}"]`).forEach(el=>el.textContent=value);
async function refresh(){
  const response=await fetch('./data/investor-snapshot.json',{cache:'no-store'});
  if(!response.ok) throw new Error(`snapshot ${response.status}`);
  const s=await response.json();
  set('first-playable',`First playable ${s.first_playable.completed_tasks}/${s.first_playable.total_tasks}`);
  set('program-complete',`Program ${s.program.completed_tasks}/${s.program.total_tasks}`);
  set('active-task',`Executing ${s.active_task.id}`);
  set('program-line',`${s.program.completed_tasks} of ${s.program.total_tasks} completion-class tasks · ${s.active_task.id} ${s.active_task.title}`);
}
refresh().catch(()=>{});
setInterval(refresh,60000);
