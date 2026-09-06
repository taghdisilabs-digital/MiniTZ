import unreal, json
from pathlib import Path
out=Path(r"/root/biella/repos/biella-engine/projects/biella-games/Build/Presentation/seat-geometry-01")
mesh=unreal.load_asset('/Game/Vehicles/OffroadCar/SM_Offroad_Body')
task=unreal.AssetExportTask()
task.object=mesh
task.filename=str(out/'body.obj')
task.automated=True
task.prompt=False
task.exporter=unreal.StaticMeshExporterOBJ()
assert unreal.Exporter.run_asset_export_task(task), str(task.errors)
rig=unreal.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
a=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector())
c=a.skeletal_mesh_component;c.set_skeletal_mesh_asset(rig)
bones=[]
for i in range(c.get_num_bones()):
 n=c.get_bone_name(i);t=c.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_COMPONENT);v=t.translation;q=t.rotation
 bones.append(dict(name=str(n),parent=str(c.get_parent_bone(n)),position=[v.x,v.y,v.z],rotation=[q.x,q.y,q.z,q.w]))
actors.destroy_actor(a)
(out/'readback.json').write_text(json.dumps(dict(result='PASS',bones=bones),indent=2)+'\n')
