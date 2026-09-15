# MiniTZ OS final closure — revision 8

The owner-authorized frozen release satisfies the final material boundary.
The read-only Ubuntu 26.04 check verified the image, existing runtime boot proof,
explicit owner acceptance, and all 195 installed source files against this pair:

- Source: `07fc3844ab80c41d8bc6e4825386a3491a8de0347428b56eeabb2cc838d781e9`
- Raw image: `2353fbe2c932c43120938bcd27ca103f231825f2f978741078e9ce12f73a1080`
- Canonical image: `/root/attached-storage/minitz-os-sandbox/output/images/MiniTZ-OS-07fc3844ab80c41d.raw`

Task Program revision 127 has 35 completed predecessors and this final task as
its only working boundary. Task revision 8 has digest
`d5fff2506163cd5389093153513d6a9bda5eb7ad1077faf7b343c227804495b8`.
The program remains the only progression authority; this evidence does not
change it or select another task.

## Evidence

- `material-readback.json`: direct byte verification, exact owner instruction
  and acceptance read from the canonical program, existing boot proof and log
  hashes, installed source verification, and retained qualification evidence.
- `material-run.json`: executable command, collector/output hashes, exit 0;
  every canonical input was mounted read-only in Ubuntu 26.04.
- `closure-tests-run.json` and `closure-tests.log`: **10 passed**; closure guards
  plus frozen-release retention, candidate isolation, mismatched artifact
  rejection, and exact runtime proof checks. The final-status test returns
  while the task is working; the direct material readback independently checks
  every final material condition.
- `git-host-readback.json`: authenticated private GitHub `main` identity and
  matching local/remote commit before this evidence-only change; Ubuntu 24.04
  remains the host. `publication.json` records this evidence's remote readback.
- `evidence-index.json`: hashes of this bounded evidence set.

The later live source is
`58c6ff7d1bc2e2b0159efdf5f42125f57ac4f2413874a883ada6ec4fff8cc19e`.
The owner's 2026-09-15 21:31:46 UTC instruction reserves newer source for the
next cycle. This closure retains the accepted release without rebuilding or
replacing it. Only documentation/evidence changed in this task execution.

## Scope and preserved observations

No unresolved critical gap remains in the authorized frozen release cycle.
Completed predecessor work covers MiniTZ-native capabilities, resources,
credentials, task behavior, and donor retirement. The existing qualification
evidence was hash-checked and reused; those completed tasks were not replayed.
Raw secrets are excluded from the release source and this evidence.

The predecessor's offline Needs Setup/Needs Attention observations and limits
on live provider, desktop, VPN, and machine-recovery coverage remain recorded.
They are not relabeled Ready. Its earlier lack of boot/owner acceptance is
superseded by the exact existing runtime proof and explicit owner receipt.
The earlier truncated image was repaired and its current bytes verified; the
original truncation trigger remains unestablished. No image boot or machine
lifecycle action was performed during this closure.

The configured publication destination is private GitHub `main`. The raw image
remains at its canonical local output; the accepted qualification records no
configured remote raw-image destination.
