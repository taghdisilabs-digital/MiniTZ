from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'projects/biella-games'
CONTRACT = GAME / 'docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md'


def test_visual_final_layer_contract_exists_and_rejects_current_prototype_baseline():
    text = CONTRACT.read_text()
    for marker in (
        'AAA_REALISTIC_RUNTIME_BAR', 'BASELINE_NOT_VISUAL_ACCEPTANCE',
        'NO_PLACEHOLDER_OR_PRIMITIVE_FOCAL_ART', 'PLAYER_RIVAL_INFECTED_ARENA_PRESSURE',
        'PHYSICALLY_COHERENT_PBR', 'DENSE_VERTICAL_WORLD', 'INFECTION_ARCHITECTURE_INTEGRATION',
        'LIGHTING_ATMOSPHERE_DEPTH', 'GAMEPLAY_DISTANCE_READABILITY', 'NO_SCREENSHOT_ONLY_PASS',
        'NO_REVIEW_ONLY_LOOP', 'VISUAL_DEFECT_BUDGET_ZERO_MAJOR',
    ):
        assert marker in text
    assert 'Build/Release/D08-01/runtime/new-feedback-01/dense_combat.png' in text
    assert 'Build/Release/D08-01/runtime/new-environment-02/captures/hazard_active.png' in text


def test_all_d17_tasks_bind_exact_visual_contract_and_capture_runtime_evidence():
    digest = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    mapping = {x['task_id']: x for x in json.loads((ROOT/'docs/task-program/D_NEXT_100_TASKS.json').read_text())['tasks']}
    for i in range(1, 9):
        task = f'D17-0{i}'
        guide = (GAME/'docs/task-guides'/f'{task}.md').read_text()
        assert 'VISUAL_FINAL_LAYER_ACCEPTANCE.md' in guide
        assert 'NO_PASS_ON_CURRENT_D08_BASELINE' in guide
        assert 'RAW_GAMEPLAY_CAPTURE_REQUIRED' in guide
        ref = next(x for x in mapping[task]['source_refs'] if x['path'] == 'projects/biella-games/docs/VISUAL_FINAL_LAYER_ACCEPTANCE.md')
        assert ref['sha256'] == digest


def test_d17_visual_creation_tasks_have_hard_rejection_and_iteration_rules():
    for task in ('D17-05','D17-06','D17-07'):
        text = (GAME/'docs/task-guides'/f'{task}.md').read_text()
        assert 'REJECT_AND_FIX_MAJOR_VISUAL_DEFECTS' in text
        assert 'COMPARE_BASELINE_TO_FINAL' in text
        assert 'DO_NOT_LOWER_QUALITY_TO_PASS' in text
        assert 'CREATE_FIX_VALIDATE_REPEAT' in text


def test_visual_contract_is_system_instruction_not_owner_wait_gate():
    for rel in ('docs/project-state/07_BIELLA_PRODUCTION_SYSTEM.md','docs/project-state/BIELLA_PROJECT_INSTRUCTIONS.md','ops/workstation/AGENTS.md'):
        text=(ROOT/rel).read_text()
        assert 'VISUAL_FINAL_LAYER_ACCEPTANCE' in text
        assert 'VISUAL_QUALITY_IS_EXECUTION_WORK_NOT_OWNER_WAIT' in text
        assert 'NO_PASS_ON_CURRENT_D08_BASELINE' in text
