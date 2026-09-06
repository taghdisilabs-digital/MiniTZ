"""Import/read back the project-authored, centimeter-space cockpit wheel."""
import json
import os
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
target = '/Game/Vehicles/Presentation/SM_DriverSteeringWheel'
verify = '-D03VerifyDriverWheel' in unreal.SystemLibrary.get_command_line()
if not unreal.EditorAssetLibrary.does_asset_exist(target):
    assert not verify, 'Missing saved cockpit wheel'
    task = unreal.AssetImportTask()
    task.filename = str(project / 'SourceAssets/Vehicles/DriverSteeringWheel.fbx')
    task.destination_path = '/Game/Vehicles/Presentation'
    task.destination_name = 'SM_DriverSteeringWheel'
    task.automated = True
    task.save = True
    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.import_materials = False
    options.import_textures = False
    options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    options.automated_import_should_detect_type = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.auto_generate_collision = False
    task.options = options
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
assert unreal.EditorAssetLibrary.does_asset_exist(target)
mesh = unreal.load_asset(target)
assert isinstance(mesh, unreal.StaticMesh)
bounds = mesh.get_bounds()
extent = bounds.box_extent
assert 1 < extent.x < 4 and 14 < extent.y < 16 and 14 < extent.z < 16, str(extent)
assert bounds.origin.length() < 0.1
Path(os.environ['BIELLA_D03_SEAT_REPORT']).write_text(json.dumps(dict(
    result='PASS', mode='readback' if verify else 'import', asset=mesh.get_path_name(),
    extent=[extent.x, extent.y, extent.z], origin=[bounds.origin.x, bounds.origin.y, bounds.origin.z],
    material_slots=len(mesh.get_editor_property('static_materials'))
), indent=2) + '\n')
unreal.log('D03_DRIVER_WHEEL COMPLETE')
