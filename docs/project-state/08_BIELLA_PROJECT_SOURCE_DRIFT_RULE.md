# 08 — BIELLA PROJECT SOURCE DRIFT RULE

```yaml
schema: biella.project_source_drift/v3
mode: mandatory_maintenance_rule
trigger: material_drift_observed
source_pack_evolution: lossless_valid_progress_capabilities_evidence
```

## Live-first rule
Before any Biella project-dependent delivery, perform a scoped live READ-ONLY inspection: actual Git branch/HEAD/tree/worktree, current `03/04`, relevant runtime/process/session state, and directly touched source/evidence. Read GitHub/Drive too when remote identity/publication matters. Project Sources and model/chat memory never substitute for live state.

If live status cannot be observed, mark `LIVE_STATUS_UNAVAILABLE`; do not guess current facts, IDs, commands, code assumptions, or completion. UNKNOWN stays UNKNOWN.

Authority: CURRENT_EXECUTION_STATE > CURRENT_GITHUB_SOURCE > CURRENT_CANONICAL_DRIVE > VERIFIED_HISTORICAL_EVIDENCE > REFERENCE_OR_PLAN > INFERENCE.

## Material drift
Includes changed commit/tree/branch/worktree truth; active task/status/session/directive changes; controller/runtime/process behavior changes; capability/provider-route changes; canonical path/Drive/publication changes; stable `07` behavior superseded by accepted source; removed authority; or runtime evidence contradicting claimed capability state.

## Required response
1. Reobserve only the smallest facts needed; go deeper on conflict/high impact.
2. Continue from higher-authority current evidence.
3. Treat stale source values as superseded.
4. Generate COMPLETE replacements for affected Project Sources only: no TODO/TBD/placeholders, guessed values, fake IDs, omitted required content, or stub code.
5. Replace Project Sources directly only if a tool actually supports it; otherwise name exact files to replace and provide them.
6. Never rewrite unaffected stable files or turn UNKNOWN into a guess.
7. Preserve independently valid progress, capabilities, reusable methods, failures, evidence identities, and continuity. A refresh may replace stale volatile facts but may not silently delete useful verified capability merely for brevity or simplification.

## File maintenance
- `03`: replace volatile facts after real transitions or material drift.
- `04`: replace at task boundary, authoritative directive change, or material active-task drift.
- `05/06`: update only when sequencing/evidence mapping changes.
- `07`: update only when stable production behavior changes.
- `08`: update when Project Source maintenance law changes.
- `provider-registry.json`: replace when routes/definitions change.
- `BIELLA_PRODUCTION_RUNTIME_SOURCE.zip`: rebuild only when included runtime behavior source changes; otherwise preserve exact verified bytes.
- `BIELLA_CHATGPT_PROJECT_INSTRUCTIONS.md`: update when ChatGPT operating law changes; always <= 8,000 characters.
- Source-pack refreshes must retain all unaffected valid source files and add newly authoritative source files without silently dropping useful prior capability/evidence.

## External-project learning firewall
External/customer projects are not Biella Projects. Their brand, visual guidance, copy, rules, source bodies, repository identity, Cloudflare/Git state, and project histories must not enter Biella Project Sources. Only sanitized project-neutral coding/engineering methods or lessons may become reusable candidates after independent relevance/verification.

## Required notice
On material drift state exactly: `Project Source drift detected: replacement source files were generated/identified.` Name affected files and never claim ChatGPT Project Source replacement unless a tool actually performed it.
