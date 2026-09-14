from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
required = [
    'BiellaGames.uproject',
    'Source/BiellaGames.Target.cs',
    'Source/BiellaGamesEditor.Target.cs',
    'Source/BiellaGames/BiellaGames.Build.cs',
    'Source/BiellaGames/BiellaGames.h',
    'Source/BiellaGames/BiellaGames.cpp',
    'Config/DefaultEngine.ini',
    'Config/DefaultGame.ini',
    'Content/.gitkeep',
    'Plugins/.gitkeep',
]
missing = [p for p in required if not (root / p).is_file()]
if missing:
    print('MISSING:', ', '.join(missing))
    sys.exit(1)

project = json.loads((root / 'BiellaGames.uproject').read_text(encoding='utf-8'))
assert project['FileVersion'] == 3
assert project['EngineAssociation'] == '5.8'
modules = project.get('Modules', [])
assert modules == [{'Name': 'BiellaGames', 'Type': 'Runtime', 'LoadingPhase': 'Default'}]

build = (root / 'Source/BiellaGames/BiellaGames.Build.cs').read_text(encoding='utf-8')
for token in ['Core', 'CoreUObject', 'Engine', 'InputCore', 'EnhancedInput']:
    assert token in build, token

engine_ini = (root / 'Config/DefaultEngine.ini').read_text(encoding='utf-8')
for token in [
    'DefaultGraphicsRHI=DefaultGraphicsRHI_DX12',
    'r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange=True',
    'r.DynamicGlobalIlluminationMethod=1',
    'r.ReflectionMethod=1',
    'r.Shadow.Virtual.Enable=1',
    'r.Nanite.ProjectEnabled=1',
]:
    assert token in engine_ini, token

print('STRUCTURAL_BOOTSTRAP_PASS')
