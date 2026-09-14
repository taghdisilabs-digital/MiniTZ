from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'projects' / 'minitz-games'


def test_minitz_games_is_current_product_identity():
    project = json.loads((PROJECT / 'BiellaGames.uproject').read_text())
    game = (PROJECT / 'Config' / 'DefaultGame.ini').read_text()
    agents = (PROJECT / 'AGENTS.md').read_text()
    assert project['Description'].startswith('MiniTZ Games')
    assert 'ProjectName=MiniTZ Games' in game
    assert 'CompanyName=MiniTZ' in game
    assert agents.startswith('# MiniTZ Games')


def test_serialized_predecessor_identifiers_are_explicit_compatibility_only():
    manifest = json.loads((PROJECT / 'docs' / 'MINITZ_UNREAL_COMPATIBILITY.json').read_text())
    assert manifest['schema'] == 'minitz.unreal_compatibility/v1'
    assert manifest['authority'] == 'COMPATIBILITY_ONLY'
    assert manifest['product_identity'] == 'MiniTZ Games'
    assert manifest['may_drive_product_authority'] is False
    retained = set(manifest['retained_serialized_identifiers'])
    assert {'BiellaGames', 'BiellaLoadingScreen', '/Script/BiellaGames'} <= retained
    assert manifest['removal_requires_asset_resave'] is True
