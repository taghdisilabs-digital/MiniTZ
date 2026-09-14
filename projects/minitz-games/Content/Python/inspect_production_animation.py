"""Native read-only resource metadata and load/dependency verification."""
import json
import os
from pathlib import Path
import unreal

project=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
provenance=json.loads((project/'SourceAssets/Characters/UE58Mannequin.provenance.json').read_text())
registry=unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(['/Game/Characters/Mannequins'],force_rescan=True)
options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
                                             include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
records=[]; sequences=[]
for f in provenance['files']:
    package='/Game/'+f['local'].removeprefix('Content/').removesuffix('.uasset')
    obj=unreal.load_asset(package)
    assert obj is not None, package
    deps=[str(d) for d in registry.get_dependencies(package,options)]
    for dep in deps:
        if dep.startswith('/Game/'):
            assert unreal.EditorAssetLibrary.does_asset_exist(dep), 'Unresolved dependency '+dep
    records.append(dict(path=package,cls=obj.get_class().get_name(),dependencies=deps))
    if isinstance(obj,unreal.AnimSequence):
        sequences.append(dict(path=package,length=obj.get_play_length(),skeleton=obj.get_editor_property('skeleton').get_path_name(),
                              additive=str(obj.get_editor_property('additive_anim_type')),root_motion=obj.get_editor_property('enable_root_motion')))
bs=unreal.load_asset('/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run')
samples=[dict(animation=s.get_editor_property('animation').get_path_name(),value=str(s.get_editor_property('sample_value')),rate=s.get_editor_property('rate_scale')) for s in bs.get_editor_property('sample_data')]
params=unreal.MaterialEditingLibrary.get_vector_parameter_names(unreal.load_asset('/Game/Characters/Mannequins/Materials/M_Mannequin'))
report=dict(result='PASS',assets=records,sequences=sequences,blend_samples=samples,blend_parameters=str(bs.get_editor_property('blend_parameters')),material_vector_parameters=[str(p) for p in params])
Path(os.environ['BIELLA_D03_ANIMATION_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
unreal.log('D03_ANIMATION_RESOURCE COMPLETE')
