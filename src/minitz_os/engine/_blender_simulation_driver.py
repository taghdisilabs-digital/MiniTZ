"""Adapter-local deterministic bounded Blender particle/procedural solver."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import random,sys
from typing import Any

def number(v: Any,n: str)->float:
 if isinstance(v,bool) or not isinstance(v,(int,float)):raise ValueError(n)
 return float(v)
def vec(v: Any,n: str)->tuple[float,float,float]:
 if not isinstance(v,list) or len(v)!=3:raise ValueError(n)
 return tuple(number(x,n) for x in v) # type: ignore[return-value]
def main()->None:
 import bpy # type: ignore[import-not-found]
 c=json.loads(Path(sys.argv[sys.argv.index("--")+1]).read_text(encoding="utf-8"))
 if not isinstance(c,dict) or c.get("simulation_type") not in {"particles","procedural"}:raise ValueError("simulation_type")
 a,b=int(c["frame_start"]),int(c["frame_end"]); count,sub,seed=int(c["particle_count"]),int(c["substeps"]),int(c["seed"])
 if b<a or not 1<=count<=256 or sub<1 or seed<0 or number(c["timestep"],"timestep")<=0:raise ValueError("bounds")
 g,iv=vec(c["gravity"],"gravity"),vec(c["initial_velocity"],"initial_velocity"); floor,restitution=number(c["floor_height"],"floor"),number(c["restitution"],"restitution")
 if not 0<=restitution<=1 or not isinstance(c.get("generator_ref"),str):raise ValueError("solver")
 scene=bpy.context.scene;prior=c.get("predecessor_state",[])
 if not prior:
  stored=scene.get("minitz_solver_state")
  if isinstance(stored,str):prior=json.loads(stored)
 if prior and (not isinstance(prior,list) or len(prior)!=count):raise ValueError("predecessor")
 if c.get("requires_predecessor_state") is True and not prior:raise ValueError("predecessor")
 rng=random.Random(seed); state=prior or [{"position":[rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(0,1)],"velocity":list(iv)} for _ in range(count)]
 scene.frame_start,scene.frame_end=a,b;dt=number(c["timestep"],"timestep")/sub
 for frame in range(a,b+1):
  for _ in range(sub):
   for p in state:
    for i in range(3):p["velocity"][i]+=g[i]*dt;p["position"][i]+=p["velocity"][i]*dt
    if p["position"][2]<floor:p["position"][2]=floor;p["velocity"][2]=abs(p["velocity"][2])*restitution
  scene.frame_set(frame)
  for i,p in enumerate(state):
   o=bpy.data.objects.get(f"MiniTZParticle_{i:03d}")
   if o is None:bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.03);o=bpy.context.object;o.name=f"MiniTZParticle_{i:03d}"
   o.location=p["position"];o.keyframe_insert(data_path="location",frame=frame)
 scene["minitz_solver_state"]=json.dumps(state,sort_keys=True,separators=(",",":"));out=Path(c["output_path"]);bpy.ops.wm.save_as_mainfile(filepath=str(out))
 m={"simulation_type":c["simulation_type"],"segment":c["segment"],"frame_start":a,"frame_end":b,"timestep":dt,"substeps":sub,"seed":seed,"generator_ref":c["generator_ref"],"solver_ref":c["solver_ref"],"runtime_ref":c["runtime_ref"],"particle_count":count,"state":state,"config_sha256":hashlib.sha256(json.dumps(c,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
 Path(str(out)+".json").write_text(json.dumps(m,sort_keys=True),encoding="utf-8");print("MINITZ_SIMULATION="+json.dumps(m,sort_keys=True))
if __name__=="__main__":main()
