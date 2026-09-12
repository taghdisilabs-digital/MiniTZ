import{cp,mkdir,readFile,rm,writeFile}from"node:fs/promises";
import{createHash}from"node:crypto";
import{dirname,resolve}from"node:path";

const root=resolve(import.meta.dirname,"..");
const repo=resolve(root,"..");
const dist=resolve(root,"dist");
await rm(dist,{recursive:true,force:true});
await mkdir(resolve(dist,"data"),{recursive:true});
for(const file of["index.html","styles.css","app.js"])await cp(resolve(root,"src",file),resolve(dist,file));
await mkdir(resolve(dist,"portfolio"),{recursive:true});
await cp(resolve(dist,"index.html"),resolve(dist,"portfolio","index.html"));
await cp(resolve(root,"src","control"),resolve(dist,"control"),{recursive:true});
await cp(resolve(root,"src","live"),resolve(dist,"live"),{recursive:true});
await cp(resolve(root,"src","archive"),resolve(dist,"archive"),{recursive:true});
const liveApp=await readFile(resolve(dist,"live","app.js"));
const liveCss=await readFile(resolve(dist,"live","styles.css"));
const liveAppHash=createHash("sha256").update(liveApp).digest("hex").slice(0,12);
const liveCssHash=createHash("sha256").update(liveCss).digest("hex").slice(0,12);
await writeFile(resolve(dist,"live",`app.${liveAppHash}.js`),liveApp);
await writeFile(resolve(dist,"live",`styles.${liveCssHash}.css`),liveCss);
let liveHtml=await readFile(resolve(dist,"live","theatre","index.html"),"utf8");
liveHtml=liveHtml.replace('/live/app.js',`/live/app.${liveAppHash}.js`).replace('/live/styles.css',`/live/styles.${liveCssHash}.css`);
await writeFile(resolve(dist,"live","theatre","index.html"),liveHtml);
await cp(resolve(root,"src","investors"),resolve(dist,"investors"),{recursive:true});
await cp(resolve(root,"reference","investor-deck-v1"),resolve(dist,"investors","reference"),{recursive:true});
for(const file of["game-runtime-media.json","asset-resolution.json","control-runtime.json","investor-deck-manifest.json","locker-index.json","portfolio-index.json","portfolio-media.json"])await cp(resolve(root,"content",file),resolve(dist,"data",file));

const portfolioMedia=JSON.parse(await readFile(resolve(root,"content","portfolio-media.json"),"utf8"));
for(const item of portfolioMedia.items||[]){
  const source=resolve(repo,String(item.source_path||""));
  if(!source.startsWith(repo+"/"))throw new Error(`portfolio media escaped repo: ${item.source_path}`);
  const relativePublic=String(item.public_path||"").replace(/^\/+/,"");
  if(!relativePublic.startsWith("portfolio-media/"))throw new Error(`invalid portfolio public path: ${item.public_path}`);
  const target=resolve(dist,relativePublic);
  await mkdir(dirname(target),{recursive:true});
  await cp(source,target);
}

const csv=await readFile(resolve(root,"content","website-visual-assets.csv"),"utf8");
const lines=csv.trim().split(/\r?\n/);const headers=lines.shift().split(",");
const parse=line=>{const cells=[];let value="",quoted=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'){if(quoted&&line[i+1]==='"'){value+='"';i++}else quoted=!quoted}else if(c===","&&!quoted){cells.push(value);value=""}else value+=c}cells.push(value);return Object.fromEntries(headers.map((h,i)=>[h,cells[i]??""]))};
const assets=lines.filter(Boolean).map(parse);
await writeFile(resolve(dist,"data","website-visual-assets.json"),JSON.stringify({schema:"biella.website.visual-assets/v1",assets},null,2)+"\n");

const sourceCommit=process.env.BIELLA_SOURCE_COMMIT||"LOCAL_UNPUBLISHED";
const sourceTree=process.env.BIELLA_SOURCE_TREE||"UNKNOWN";
const environment=process.env.BIELLA_DEPLOY_ENV||"LOCAL";
const deploymentStatus=process.env.BIELLA_DEPLOYMENT_STATUS||"NOT_REMOTELY_DEPLOYED";
const ledger=JSON.parse(await readFile(resolve(repo,"docs/task-program/D_TASK_LEDGER.json"),"utf8"));
const tasks=ledger.tasks||[];
const completeStates=new Set(["COMPLETE","COMPLETE_ALREADY","COMPLETE_REUSE_REQUIRED"]);
const completed=tasks.filter(task=>completeStates.has(task.status)).length;
const d01=tasks.filter(task=>/^D01-\d+$/.test(task.task_id));
const d01Complete=d01.filter(task=>completeStates.has(task.status)).length;
const activeText=await readFile(resolve(repo,"docs/project-state/04_BIELLA_ACTIVE_TASK.md"),"utf8");
const activeId=(activeText.match(/^\s*id:\s*(\S+)/m)||[])[1]||"UNKNOWN";
const active=tasks.find(task=>task.task_id===activeId)||{};
const evidenceSources=["docs/task-program/D_TASK_LEDGER.json","docs/project-state/03_BIELLA_CURRENT_STATE.md","docs/project-state/04_BIELLA_ACTIVE_TASK.md","projects/biella-games/docs/PRODUCTION.md"];
const investorSnapshot={
 schema:"biella.website.investor-snapshot/v1",
 generated_at:new Date().toISOString(),
 source:{commit:sourceCommit,tree:sourceTree,branch:process.env.BIELLA_SOURCE_BRANCH||"main"},
 first_playable:{completed_tasks:d01Complete,total_tasks:d01.length,status:d01.length===50&&d01Complete===50?"VERIFIED_COMPLETE":"NOT_COMPLETE"},
 program:{completed_tasks:completed,total_tasks:tasks.length,remaining_tasks:tasks.length-completed,completed_percent:tasks.length?completed*100/tasks.length:0,completion_states:[...completeStates]},
 active_task:{id:activeId,title:active.title||"Unknown current task",status:active.status||"UNKNOWN",program:active.program||"UNKNOWN"},
 financial_posture:{product_proof:d01.length===50&&d01Complete===50?"VALIDATED":"OPEN",workflow_evidence:"VALIDATED",revenue_metrics:"OPEN",capital_metrics:"OPEN"},
 evidence_sources:evidenceSources,
 visual_reference:{manifest:"website/content/investor-deck-manifest.json",metric_authority:false}
};
await writeFile(resolve(dist,"data","investor-snapshot.json"),JSON.stringify(investorSnapshot,null,2)+"\n");

const html=await readFile(resolve(dist,"index.html"));
const artifactSha256=createHash("sha256").update(html).digest("hex");
const deployment={schema:"biella.website.deployment/v1",source_commit:sourceCommit,source_tree:sourceTree,source_branch:process.env.BIELLA_SOURCE_BRANCH||"main",environment,deployment_status:deploymentStatus,entrypoint_sha256:artifactSha256,generated_at:new Date().toISOString()};
await writeFile(resolve(dist,"deployment.json"),JSON.stringify(deployment,null,2)+"\n");
await writeFile(resolve(dist,"404.html"),html);
console.log(JSON.stringify({dist,...deployment,investor_snapshot:{completed_tasks:completed,total_tasks:tasks.length,active_task:activeId}},null,2));
