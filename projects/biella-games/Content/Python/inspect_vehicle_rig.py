"""Read the installed vehicle rig, material closure and component-space reference bones."""
import json
import os
from pathlib import Path
import unreal

project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
provenance = json.loads((project / 'SourceAssets/Vehicles/UE58Offroad.provenance.json').read_text())
parts_path = project / 'SourceAssets/Vehicles/UE58OffroadParts.provenance.json'
if parts_path.exists():
    provenance['files'] += json.loads(parts_path.read_text())['files']
registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(['/Game/Vehicles'], force_rescan=True)
options = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True)
records = []
for item in provenance['files']:
    package = '/Game/' + item['local'].removeprefix('Content/').removesuffix('.uasset')
    obj = unreal.load_asset(package)
    assert obj is not None, package
    dependencies = [str(d) for d in registry.get_dependencies(package, options)]
    for dep in dependencies:
        if dep.startswith('/Game/'):
            assert unreal.load_asset(dep) is not None, 'Unresolved dependency ' + dep
    record = dict(path=package, cls=obj.get_class().get_name(), dependencies=dependencies)
    if isinstance(obj, unreal.StaticMesh):
        bounds = obj.get_bounds()
        record['bounds'] = dict(origin=[bounds.origin.x, bounds.origin.y, bounds.origin.z], extent=[bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z])
        record['materials'] = [m.material_interface.get_path_name() for m in obj.static_materials]
    records.append(record)

mesh = unreal.load_asset('/Game/Vehicles/OffroadCar/SKM_Offroad')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector())
component = actor.skeletal_mesh_component
component.set_skeletal_mesh_asset(mesh)
bones = []
for index in range(component.get_num_bones()):
    name = component.get_bone_name(index)
    transform = component.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_COMPONENT)
    p, q, s = transform.translation, transform.rotation, transform.scale3d
    bones.append(dict(name=str(name), parent=str(component.get_parent_bone(name)),
                      location=[p.x, p.y, p.z], rotation=[q.x, q.y, q.z, q.w], scale=[s.x, s.y, s.z]))
materials = []
for i in range(component.get_num_materials()):
    mat = component.get_material(i)
    materials.append(dict(path=mat.get_path_name(), vectors=[str(n) for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(mat)], scalars=[str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat)]))
actors.destroy_actor(actor)
output = Path(os.environ['BIELLA_D03_VEHICLE_REPORT'])
output.write_text(json.dumps(dict(result='PASS', assets=records, bones=bones, materials=materials, bounds=str(mesh.get_bounds()), nanite=str(mesh.get_editor_property('nanite_settings'))), indent=2) + '\n')
unreal.log('D03_VEHICLE_RIG COMPLETE')
