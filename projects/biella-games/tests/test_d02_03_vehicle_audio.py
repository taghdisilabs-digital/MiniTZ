from pathlib import Path
import json
import wave

ROOT = Path(__file__).resolve().parents[1]


def test_vehicle_engine_audio_uses_imported_pcm_soundwave_not_procedural_queue():
    source = ROOT / 'SourceAssets/Audio/Vehicle/S_VehicleEngine.wav'
    manifest = ROOT / 'SourceAssets/Audio/Vehicle/manifest.json'
    imported = ROOT / 'Content/Vehicle/Audio/S_VehicleEngine.uasset'
    importer = ROOT / 'Content/Python/import_vehicle_audio.py'
    cpp = (ROOT/'Source/BiellaGames/Private/BiellaVehicle.cpp').read_text()
    test_cpp = (ROOT/'Source/BiellaGames/Private/Tests/BiellaVehicleTest.cpp').read_text()
    header = (ROOT/'Source/BiellaGames/Public/BiellaVehicle.h').read_text()
    assert source.is_file() and manifest.is_file() and importer.is_file() and imported.is_file()
    with wave.open(str(source)) as wav:
        assert wav.getframerate() == 48000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
        assert 1.5 <= wav.getnframes()/wav.getframerate() <= 3.0
    data = json.loads(manifest.read_text())
    assert data['asset_path'] == '/Game/Vehicle/Audio/S_VehicleEngine'
    assert 'S_VehicleEngine.S_VehicleEngine' in cpp
    assert 'SetPitchMultiplier' in cpp and 'SetVolumeMultiplier' in cpp
    assert 'USoundWaveProcedural' not in cpp + header + test_cpp
    assert 'QueueAudio' not in cpp
