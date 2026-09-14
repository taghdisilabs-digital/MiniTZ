# D01-50 — Drive closure and exact readback

Result: **PASS — worker boundary, PRE_TRANSITION**.
Verified 2026-09-05 at 17:01:39 UTC. Source commit
`1d14a28f7b79b1079169592b3a35ebcfd3d1436c`, tree
`4ea805d37c94028b982b6f63885425146b04b02b`.

The existing Auto Feeder publication contains the canonical Demo queue,
completed acceptance pointers and package identity. Fresh Drive readback
matched all three continuity files byte for byte against both this Git
revision and the current local files. This receipt is task evidence, not
another production-state authority.

| Canonical Drive record | Preserved file ID | Exact bytes |
| --- | --- | ---: |
| `Biella/CURRENT/03_BIELLA_CURRENT_STATE.md` | `1wiWcdWt4hmTf3narsLw4OqGu_ueKOSa4` | 5386 |
| `Biella/CURRENT/04_BIELLA_ACTIVE_TASK.md` | `1liutA8evH6rPjk-U4tgR13l_kqBrx-DF` | 789 |
| `Biella/PROJECTS/GAMES/PRODUCTION.md` | `1LUVUz0iG_xL7eOkF1OEBtJ2R9a455eqx` | 27955 |

Both canonical folder IDs passed. File identities, sizes and modification
times remained unchanged across each readback. The verifier rejects missing,
duplicate, wrong-ID and wrong-type objects; those rejection cases also passed
a local check. Full remote metadata, SHA-256 pairs, source/evidence identities
and validation time are in [D01-050-validation.json](D01-050-validation.json).

The Project queue contains all 50 ordered Demo IDs, with D01-01 through D01-49
complete and D01-50 pending. The stale `completed_demo_tasks: 54` aggregate in
03 is preserved; the Project's Demo rows establish the actual 49/50 boundary.
This receipt does not claim that Drive already contains D01-50's completion
transition. The Auto Feeder owns subsequent GitHub/Drive publication and the
canonical state transition. This worker performed zero Drive writes and did
not change 03, 04 or PRODUCTION.

The published D01-46 row binds
`/root/biella/artifacts/games/D01-46/BiellaGames-Linux-x64-D01-46.tar.zst`:
297346213 bytes, SHA-256
`c1085849f0919865a40191b9a40a5883be662b032766d4ef6620fa4f4b315bc8`.
The archive was freshly hashed. All 73 recorded gameplay files still match
D01-48, and the current gameplay source matches package-source commit
`00c7243077403d9ebfb812318cd23a3a5b13641f`.
The receipt binds D01-46/47/48 acceptance documents and D01-48 validation and
replay evidence to their committed bytes. D01-49's previously verified GitHub
commit/tree is preserved and checked locally for exact tree and ancestry;
D01-50 performs no new GitHub publication or remote GitHub verification.

D01-48's protected-state snapshots match their historical Git revision
`c4c981eca4bc3cc6ee36da2ccee36d58a7ef2bc3`. The unmodified D01-48 verifier
expects those historical bytes at today's mutable paths and therefore fails
on 03 after normal Feeder progression. D01-50 verifies historical identities
against Git and current identities against Drive; it does not rewrite the
predecessor evidence or claim a fresh full D01-48 replay.

Acceptance remains the existing automated Linux x64 Development slice with
primitive blockout assets. Final AAA content, owner visual acceptance, human
playtesting, Windows/Shipping qualification and physical audio output remain
outside that evidence. D01-44 performance scope is unchanged. Media remains
`GENERATED_DRAFT`; Engine P4-06 remains `INCOMPLETE_DEFERRED`.

Reproduce the read-only check while this pre-transition boundary is current,
from the repository root:

```sh
python3 -B projects/biella-games/tests/verify_d01_050.py
```

The command emits a new receipt to stdout and fails on changed identities or
bytes. After the Feeder advances, retain this receipt as historical evidence
of its exact source revision; a new active boundary is not expected to match
this task's pre-transition guard. No gameplay build or runtime rerun was
needed for the Drive closure task. Only this task's verifier and evidence
are committed locally.
