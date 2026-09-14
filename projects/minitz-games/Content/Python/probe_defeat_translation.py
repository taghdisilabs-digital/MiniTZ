"""Measure native death bone translations with and without skeleton retargeting."""
import json
import os
from pathlib import Path
import unreal

clip = unreal.load_asset('/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_01')
mesh = unreal.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny')
rows = []
for retarget in (True, False):
    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property('should_retarget', retarget)
    options.set_editor_property('optional_skeletal_mesh', mesh)
    options.set_editor_property('evaluation_type', unreal.AnimDataEvalType.COMPRESSED)
    for time in (0., .12, .5, 1.1):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, time, options)
        assert unreal.AnimPoseExtensions.is_valid(pose)
        bones = {}
        for name in ('root', 'pelvis', 'head', 'foot_l', 'foot_r'):
            p = unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD).translation
            bones[name] = [p.x, p.y, p.z]
        rows.append(dict(retarget=retarget, time=time, bones=bones))
Path(os.environ['BIELLA_D03_DEFEAT_REPORT']).write_text(json.dumps(dict(result='PASS', rows=rows), indent=2) + '\n')
