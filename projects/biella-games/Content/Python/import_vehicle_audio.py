"""Import/verify D02-03 native vehicle engine PCM SoundWave."""
import hashlib
import json
from pathlib import Path
import wave
import unreal

PROJECT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
ROOT = PROJECT / 'SourceAssets/Audio/Vehicle'
DEST = '/Game/Vehicle/Audio'
NAME = 'S_VehicleEngine'

def require(condition, message):
    if not condition:
        raise RuntimeError('D02_03_AUDIO FAIL: ' + message)

manifest = json.loads((ROOT / 'manifest.json').read_text())
source = ROOT / (NAME + '.wav')
require(hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_sha256'], 'source digest')
asset_path = DEST + '/' + NAME
asset = unreal.EditorAssetLibrary.load_asset(asset_path) if unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
if not asset:
    task = unreal.AssetImportTask()
    task.set_editor_property('filename', str(source))
    task.set_editor_property('destination_path', DEST)
    task.set_editor_property('destination_name', NAME)
    task.set_editor_property('automated', True)
    task.set_editor_property('replace_existing', False)
    task.set_editor_property('save', False)
    task.set_editor_property('factory', unreal.SoundFactory())
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
require(isinstance(asset, unreal.SoundWave), 'native SoundWave missing')
asset.set_editor_property('looping', True)
asset.set_editor_property('loading_behavior', unreal.SoundWaveLoadingBehavior.FORCE_INLINE)
asset.set_sound_asset_compression_type(unreal.SoundAssetCompressionType.PCM)
unreal.EditorAssetLibrary.set_metadata_tag(asset, 'D02.SourceSHA256', manifest['source_sha256'])
unreal.EditorAssetLibrary.set_metadata_tag(asset, 'D02.Status', 'GENERATED_DRAFT')
require(unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False), 'save failed')
require(asset.get_editor_property('num_channels') == 1, 'channels')
require(asset.get_editor_property('imported_sample_rate') == 48000, 'sample rate')
require(asset.get_editor_property('looping'), 'looping')
require(asset.get_editor_property('loading_behavior') == unreal.SoundWaveLoadingBehavior.FORCE_INLINE, 'inline loading')
require(asset.get_sound_asset_compression_type() == unreal.SoundAssetCompressionType.PCM, 'PCM')
export = PROJECT / 'Saved/D02-03/AudioReadback/S_VehicleEngine.wav'
export.parent.mkdir(parents=True, exist_ok=True)
task = unreal.AssetExportTask(); task.set_editor_property('object', asset); task.set_editor_property('filename', str(export)); task.set_editor_property('automated', True); task.set_editor_property('prompt', False); task.set_editor_property('replace_identical', True); task.set_editor_property('exporter', unreal.SoundExporterWAV())
require(unreal.Exporter.run_asset_export_task(task), 'native export failed')
with wave.open(str(source)) as a, wave.open(str(export)) as b:
    require(a.getparams() == b.getparams(), 'roundtrip format')
    require(a.readframes(a.getnframes()) == b.readframes(b.getnframes()), 'roundtrip PCM')
report = {'task_id':'D02-03','result':'PASS','asset':asset.get_path_name(),'source_sha256':manifest['source_sha256'],'native_roundtrip_pcm':'PASS','status':'GENERATED_DRAFT'}
(PROJECT/'Build/Vehicles').mkdir(parents=True, exist_ok=True)
(PROJECT/'Build/Vehicles/D02-03-audio-asset.json').write_text(json.dumps(report, indent=2)+'\n')
unreal.log('D02_03_AUDIO COMPLETE ' + json.dumps(report, sort_keys=True))
