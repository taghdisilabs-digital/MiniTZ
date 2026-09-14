# D03-01 ground package qualification

D03-01 remains **CONTINUE**. This increment qualifies the cosmetic playable-world ground from commit `01429b124d6b78c2c576299f82edb5aaa87167e8` in an isolated Linux Development package. It preserves earlier evidence and does not advance the task.

The cook harness now checks the exact editor build and copies every module in the current module manifest, including the loading-screen module. The packaged runtime harness supports visible-ground and hidden-ground controls. A dedicated aggregate verifier connects source, native build, cook, archive and runtime evidence and checks matched captures.

## Evidence

- `ground-game-build-01` and `ground-build-04` supply the exact native/editor lineage for 93 source files. No C++ changes were needed for this package increment.
- `ground-cook-01`: PASS, fresh isolated DDC, empty cache before cook; 1,445.263 seconds. Canonical inputs and both editor modules were unchanged. The cook generated 43 cooked files.
- `ground-stage-01`: preserved failure because the cook appended its known Android editor configuration to the isolated snapshot. `ground-cook-config-repair-01` verified that sole side effect, kept its private backup outside the repository, and restored the exact canonical snapshot configuration. No token values are recorded.
- `ground-stage-02`: PASS. All 33 staged members match the extracted archive members exactly.
- `ground-package-tsr-01`: PASS, ProductionTSR/SM6; observed renderer capabilities and authored architecture proxies verified.
- `ground-package-taa-01`: PASS, NativeTAA/SM5; observed supported fallback and authored architecture verified.
- `ground-package-hidden-01`: expected negative control. Native runtime completed successfully; the verifier failed solely on `Ground runtime invariants failed` because the cosmetic ground was hidden. Collision, navigation, floor authority and ray invariants still held.
- `ground-package-environment-01`: PASS, 1,436 native frames, median 16.741 ms. Shared hazard damage was 15.213/15.212/15.212 health over 1.485 seconds. Panel destruction, safe-floor behavior, streaming persistence and five captures passed the existing environment verifier.
- `ground-package-verification-01.json`: PASS, 997 exact input/runtime identities, ten matched static poses, forty pixel checks. Four independent fresh runtime states had host/editor/cache roots hidden. Native timing was variable; no generated frames were used.
- `ground-package-visual-review-01.json`: seven exact PNGs directly inspected; eleven exact candidate captures retained with the canonical visual manifest.

## Native measurements

These are observed uncapped surface-test frame times at 1280×720 on one workstation, not a hardware-tier acceptance claim.

| Profile | Sample | Frames | Wall p50 ms | Wall p95 ms | GPU p50 ms |
| --- | --- | ---: | ---: | ---: | ---: |
| TSR/SM6 | Stationary | 240 | 14.525 | 17.697 | 6.380 |
| TSR/SM6 | Camera pan | 225 | 15.210 | 18.371 | 6.489 |
| TAA/SM5 | Stationary | 292 | 12.289 | 14.584 | 3.607 |
| TAA/SM5 | Camera pan | 253 | 13.778 | 15.271 | 3.639 |

## Canonical candidate and publication

`/root/biella/artifacts/games/D03-01/BiellaGames-Linux-Development-D03-01-ground-candidate-01.tar.zst`

481,133,192 bytes; SHA-256 `9f2b59d9220bbc760d617de63cbace9a58fef4db62fbaa8acc245f1ff4bab373`.

Exact selected captures and their source identities are at `/root/biella/artifacts/games/D03-01/ground-package-visual-review-01/manifest.json`. These artifacts remain GENERATED_DRAFT. Auto Feeder owns GitHub/Drive publication and canonical task transition; no remote publication is claimed here.

## Remaining D03 work

The large tested ground voids are filled, but the thin distant black horizon strip, flat open margins, sparse world art and broader production lighting/art remain. This evidence covers two static margin regions and representative gameplay; it does not establish fine temporal quality, final frame-time budgets or final art acceptance. Fresh task caches do not mean the OS page cache was flushed. Dummy audio does not qualify perceived audio mix quality.

The earlier cold-start static-display/motion failure in `D03-01-automatic-pso-progress.md` is still open. These four package runs did not enable or qualify loading-screen/startup motion. Additional VFX/audio coverage and final production presentation qualification also remain within D03-01.
