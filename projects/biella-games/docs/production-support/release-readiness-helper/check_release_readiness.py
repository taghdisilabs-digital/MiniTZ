#!/usr/bin/env python3
"""Classify visual/evidence/release readiness from existing D17 and D08 evidence."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
D17 = PROJECT / 'Build/AAA/D17-01'
D17_08 = PROJECT / 'Build/AAA/D17-08/qualification.json'
D08 = PROJECT / 'Build/Release/D08-01'


def read(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def identity(path):
    path = Path(path)
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path.relative_to(PROJECT)), 'sha256': digest, 'bytes': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-ready', action='store_true')
    args = parser.parse_args()

    d17q_path = D17 / 'qualification.json'
    visual_path = D17 / 'visual-assessment.json'
    d08q_path = D08 / 'qualification.json'
    d17q, visual, d08q, d1708 = map(read, (d17q_path, visual_path, d08q_path, D17_08))

    structural = {
        'd17_qualification_readable': isinstance(d17q, dict),
        'd17_visual_assessment_readable': isinstance(visual, dict),
        'd08_release_qualification_readable': isinstance(d08q, dict),
        'd17_packaging_bridge_present': (PROJECT / 'tests/package_d17_01.py').is_file(),
        'd08_packaging_implementation_present': (PROJECT / 'tests/run_d08_01_release.py').is_file(),
        'd08_verifier_present': (PROJECT / 'tests/verify_d08_01_release.py').is_file(),
    }
    major_defects = visual.get('major_defects', []) if isinstance(visual, dict) else []
    d17_integrity = isinstance(d17q, dict) and d17q.get('evidence_integrity') == 'VERIFIED'
    d17_visual_ready = isinstance(visual, dict) and visual.get('zero_major_defects') is True
    d17_accepted = isinstance(d17q, dict) and d17q.get('accepted') is True
    d1708_closed = isinstance(d1708, dict) and (
        d1708.get('accepted') is True or d1708.get('status') in ('COMPLETE', 'COMPLETE_ALREADY'))
    linux_lineage = isinstance(d08q, dict) and d08q.get('linux_diagnostic_lineage') == 'PASS'
    win64_shipping = isinstance(d08q, dict) and d08q.get('release_candidate') is True

    gates = {
        'd17_evidence_integrity_verified': d17_integrity,
        'zero_major_visual_defects': d17_visual_ready,
        'd17_slice_accepted': d17_accepted,
        'd17_08_evidence_package_closed': d1708_closed,
        'd08_linux_diagnostic_lineage_reusable': linux_lineage,
        'win64_shipping_release_candidate_qualified': win64_shipping,
    }
    next_gates = []
    if major_defects:
        next_gates.append({'gate': 'visual_finish', 'defects': [item.get('id') for item in major_defects],
                           'source': 'Build/AAA/D17-01/visual-assessment.json'})
    if not d17_accepted:
        next_gates.append({'gate': 'd17_slice_acceptance', 'source': 'Build/AAA/D17-01/qualification.json'})
    if not d1708_closed:
        next_gates.append({'gate': 'd17_08_truthful_evidence_package',
                           'source': 'docs/task-guides/D17-08.md'})
    if not win64_shipping:
        next_gates.append({'gate': 'win64_shipping_qualification',
                           'source': 'Build/Release/D08-01/qualification.json',
                           'rule': 'reuse D08 exact package/update mechanisms on a verified Windows UE 5.8.2 resource'})

    ready = all((d17_integrity, d17_visual_ready, d17_accepted, d1708_closed, win64_shipping))
    report = {
        'schema': 'biella.games.release_readiness_helper/v1',
        'result': 'PASS' if all(structural.values()) else 'FAIL',
        'release_readiness': 'READY' if ready else 'NOT_READY',
        'structural_checks': structural,
        'gates': gates,
        'major_visual_defects': major_defects,
        'next_gates': next_gates,
        'evidence': {
            'd17_qualification': identity(d17q_path),
            'visual_assessment': identity(visual_path),
            'd17_08_qualification': identity(D17_08),
            'd08_qualification': identity(d08q_path),
            'd17_package_bridge': identity(PROJECT / 'tests/package_d17_01.py'),
            'd08_release_implementation': identity(PROJECT / 'tests/run_d08_01_release.py'),
            'd08_release_verifier': identity(PROJECT / 'tests/verify_d08_01_release.py'),
        },
        'rule': 'This helper classifies existing evidence only; it never creates or accepts a release package.',
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if report['result'] != 'PASS':
        return 1
    return 0 if (ready or not args.require_ready) else 2


if __name__ == '__main__':
    raise SystemExit(main())
