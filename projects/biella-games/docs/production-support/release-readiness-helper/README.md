# Biella Games Release Readiness Helper

Status: `PROJECT_SUPPORT_NON_AUTHORITY`

Purpose: classify the exact remaining path from the current D17 visual slice to a truthful distributable without duplicating packaging logic.

The helper reads:
- `Build/AAA/D17-01/qualification.json`;
- `Build/AAA/D17-01/visual-assessment.json`;
- `Build/AAA/D17-08/qualification.json` when it exists;
- `Build/Release/D08-01/qualification.json`;
- the existing D17 packaging bridge and D08 release implementation/verifier.

Run:

```bash
python3 projects/biella-games/docs/production-support/release-readiness-helper/check_release_readiness.py
```

Use `--require-ready` only when a caller intentionally wants a nonzero exit until all visual, D17 evidence-package, and Win64 Shipping gates are actually qualified.

This package never creates a release candidate and never promotes Linux Development diagnostics into Win64 Shipping acceptance.
