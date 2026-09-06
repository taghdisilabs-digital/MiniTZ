"""Read native death resource metadata and prove its package closure loads."""
import json
import os
from pathlib import Path
import unreal

project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
provenance = json.loads((project / 'SourceAssets/Characters/UE58Defeat.provenance.json').read_text())
registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(['/Game/Characters/Mannequins'], force_rescan=True)
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
    if isinstance(obj, unreal.AnimSequence):
        record.update(length=obj.get_play_length(), skeleton=obj.get_editor_property('skeleton').get_path_name(),
                      additive=str(obj.get_editor_property('additive_anim_type')),
                      root_motion=obj.get_editor_property('enable_root_motion'))
        assert obj.get_play_length() > 0
        assert obj.get_editor_property('additive_anim_type') == unreal.AdditiveAnimationType.AAT_NONE
    records.append(record)
Path(os.environ['BIELLA_D03_DEFEAT_REPORT']).write_text(json.dumps(dict(result='PASS', assets=records), indent=2) + '\n')
unreal.log('D03_DEFEAT_RESOURCE COMPLETE')
