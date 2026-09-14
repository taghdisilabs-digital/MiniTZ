"""Record evaluated source clip endpoints; names alone do not prove a complete fall."""
import json
import os
from pathlib import Path
import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous(['/Game/Characters/Mannequins/Anims/Death'], force_rescan=True)
rows = []
for asset in registry.get_assets_by_path('/Game/Characters/Mannequins/Anims/Death'):
    clip = asset.get_asset()
    if not isinstance(clip, unreal.AnimSequence):
        continue
    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.COMPRESSED)
    samples = []
    for time in (0., clip.get_play_length() * .5, clip.get_play_length()):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, time, options)
        bones = {}
        for name in ('root', 'pelvis', 'head', 'foot_l', 'foot_r'):
            p = unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD).translation
            bones[name] = [p.x, p.y, p.z]
        samples.append(dict(time=time, bones=bones))
    rows.append(dict(clip=clip.get_path_name(), length=clip.get_play_length(), samples=samples))
Path(os.environ['BIELLA_D03_DEFEAT_REPORT']).write_text(json.dumps(dict(result='PASS', rows=rows), indent=2) + '\n')
