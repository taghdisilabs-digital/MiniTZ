# Biella D-Series Task Numbering Standard

Status: `OWNER_APPROVED_CANONICAL_NUMBERING`
Authority: Mahdi Taghdisi
Canonical task ID format: `D##-##`
Regex: `^D[0-9]{2}-[0-9]{2}$`

## Rule

All current and future task programs use one canonical task identity format: `D##-##`.

- `D00` = Biella Engine foundation / numbered implementation program.
- `D01` = Biella Games Demo 01. Canonical display IDs are `D01-01..D01-50`.
- `D02..D08` = later Biella Games production stages.
- `D09..D14` = Biella Universe website program.
- `D15..D24` = AAA Challenger Solo Founder proof program.

Program groups express product/program topology. `depends_on` is the authoritative technical execution order and may permit independent work across groups; numbering never invents false serialization.

## D01 rolling canonicalization

Existing runtime aliases `D01-001..D01-050` remain accepted as compatibility input so in-flight and historical evidence never stalls or becomes invalid solely because of numbering. Their canonical identities are `D01-01..D01-50`.

The production controller participates in the same identity system:
- legacy aliases are canonicalized before comparison;
- new durable task/state writes emit only `D##-##`;
- completed work is reused and never reopened solely for renumbering;
- future section planning allocates the next free `DXX-YY` in that section's program group;
- the generated task ledger is derived from current Project production state and is never an execution queue;
- failure to refresh the derived Drive ledger is telemetry-only and cannot stall task execution or critical Git/Drive continuity.

Historic task artifacts, evidence filenames, and commits retain their original aliases as provenance.

## Legacy identifier policy

Old identifiers are provenance aliases, not canonical Task IDs:
- `P0-*`, `P1-*`, `P2-*`, `P3-*`, `P4-*`;
- `BU-*`, `WEB-BU-*`;
- `AAA-SF-*`;
- `GAME-*`, `CFNPC-*`, `NVIDIA-*`;
- `BG-PROD-*`.

Do not create new tasks under those prefixes.

`BG-PROD-*` task packs are legacy planning sources. Current Games production compiles later work just-in-time from current accepted Games authority; old BG-PROD identities are not resurrected as a second 500-task queue.

Provider/implementation-specific legacy tasks (`CFNPC-*`, `NVIDIA-*`) are consumed inside the relevant canonical D task when still applicable. Provider choice never becomes Task identity.

## Identity and migration

1. Canonical IDs are stable after publication.
2. A title may be refined without changing its D ID when semantic identity is unchanged.
3. A materially different task receives a new free D ID and records `supersedes`.
4. Historic commits, artifacts, evidence filenames, Drive IDs, and raw task documents are never rewritten merely to remove an old identifier.
5. Legacy IDs remain searchable only through `legacy_aliases` / source references.
6. `D_TASK_MANIFEST.json` and Drive ledger are identity maps, not a queue, controller, progress ledger, or execution-state authority.
7. Current execution remains whatever current `03/04` + Project `PRODUCTION.md` state says.
8. New just-in-time tasks use the first free `DXX-YY` inside their correct program group.
9. New durable task identities use two digits after the hyphen. Three-digit D01/S aliases are compatibility inputs only and are canonicalized on subsequent state writes.

## Durable source order

When status or dependency evidence conflicts:
`current execution -> current GitHub -> current canonical Drive -> verified historical evidence -> reference/plan -> inference`.

This registry preserves status/evidence but does not override a newer current execution source.
