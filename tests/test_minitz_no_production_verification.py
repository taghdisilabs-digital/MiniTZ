from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_production_runner_has_no_verification_or_validation_progression_surface():
    text=(ROOT/'ops/local-ai/minitz_production_runner.py').read_text()
    for marker in (
        'MINITZ_VALIDATION_COMPLETION_FAMILY',
        'validation.completed',
        '_emit_validation_evidence(',
        'accepted_criteria',
        'FAMILY_RECEIPT',
        'ValidationCompletionFamily',
    ):
        assert marker not in text


def test_task_program_has_no_value_or_validation_gate_fields():
    text=(ROOT/'ops/local-ai/minitz_task_program.py').read_text()
    assert 'VALUE_GATE_PASSED' not in text
    assert 'review_state' not in text
    assert 'validation_receipt_sha256' not in text


def test_live_dashboard_has_no_validation_status_surface():
    projection=(ROOT/'ops/control_gateway/minitz_live_projection.py').read_text()
    app=(ROOT/'website/src/live/app.js').read_text()
    html=(ROOT/'website/src/index.html').read_text()
    assert 'latest_validation' not in projection
    assert '_quality_validation' not in projection
    assert 'data-validation' not in app
    assert 'data-validation' not in html


def test_production_evidence_has_no_validation_admission_layer():
    text=(ROOT/'ops/local-ai/minitz_production_evidence.py').read_text()
    for marker in (
        '_minitz_completion_contract',
        '_normalize_minitz_completion_family',
        '_admit_minitz_result',
        'ValidationCompletionFamily',
        'ValidationAuthorityError',
        'accepted_criteria',
    ):
        assert marker not in text
