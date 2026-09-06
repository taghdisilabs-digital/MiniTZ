"""Create editable rifle locomotion; -D03VerifyAnimation only reads saved data."""
import json
import os
from pathlib import Path
import unreal

source='/Game/Characters/Mannequins/Anims/Unarmed/BS_Idle_Walk_Run'
target='/Game/Characters/Presentation/BS_RifleLocomotion'
verify='-D03VerifyAnimation' in unreal.SystemLibrary.get_command_line()
lib=unreal.EditorAssetLibrary
original=unreal.load_asset(source)
assert original
def rifle(path):
    return path.replace('/Unarmed/','/Rifle/').replace('MF_Unarmed_','MF_Rifle_').replace('MM_Idle','MF_Rifle_Idle_ADS')
if not lib.does_asset_exist(target):
    assert not verify, 'Missing saved locomotion asset'
    assert lib.duplicate_asset(source,target)
if not verify:
    asset=unreal.load_asset(target)
    samples=list(asset.get_editor_property('sample_data'))
    for i,s in enumerate(samples):
        path=rifle(s.get_editor_property('animation').get_path_name().split('.')[0])
        anim=unreal.load_asset(path)
        assert anim, path
        s.set_editor_property('animation',anim)
        samples[i]=s
    asset.set_editor_property('sample_data',samples)
    assert lib.save_loaded_asset(asset,only_if_is_dirty=False)
asset=unreal.load_asset(target)
expected=original.get_editor_property('sample_data'); actual=asset.get_editor_property('sample_data')
assert len(expected)==len(actual)==27
records=[]
for e,a in zip(expected,actual):
    anim=a.get_editor_property('animation'); pos=a.get_editor_property('sample_value')
    assert anim.get_path_name()==rifle(e.get_editor_property('animation').get_path_name()), (anim.get_path_name(), rifle(e.get_editor_property('animation').get_path_name()), str(pos), str(e.get_editor_property('sample_value')))
    assert pos==e.get_editor_property('sample_value')
    assert anim.get_editor_property('skeleton')==asset.get_editor_property('skeleton')
    assert anim.get_editor_property('additive_anim_type')==unreal.AdditiveAnimationType.AAT_NONE
    # Shipped rifle clips extract root motion; the native instance uses
    # IgnoreRootMotion so the gameplay pawn remains the displacement authority.
    records.append(dict(animation=anim.get_path_name(),direction=pos.x,speed=pos.y,rate=a.get_editor_property('rate_scale'),root_motion=anim.get_editor_property('enable_root_motion')))
Path(os.environ['BIELLA_D03_ANIMATION_REPORT']).write_text(json.dumps(dict(result='PASS',mode='readback' if verify else 'author',target=target,samples=records),indent=2)+'\n')
unreal.log('D03_LOCOMOTION COMPLETE')
