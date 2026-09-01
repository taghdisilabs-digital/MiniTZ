# P3-13 Video Production Repair Evidence

## Evidence status

| Field | Result |
| --- | --- |
| Task | P3-13 Video Production, Editing, Compositing and Media Pipeline Pack durable repair |
| Evidence result | COMPLETE |
| Retained evidence schema | `biella.p3-13.retained-real-evidence/v1` |
| Authoritative Engine evidence schema | `biella.p3-13.durable-engine-evidence/v1` |
| Engine status | `SUCCEEDED` |
| Validation | `PASS`, accepted `true`, evidence state `CURRENT` |
| Reconstruction | `PASS` |
| Unresolved failures | `0` |

## Exact source identities

| Boundary | Commit | Tree |
| --- | --- | --- |
| Accepted implementation | `27f8958aa3f6a2847b5d506580f04bcc904db98e` | `c92b5e322259ccd7619a7d51dbe94f270942b10e` |
| Repaired video source and tests | `8133a5408babc142602f93e1af22cf8eb258a9db` | `c1679d62ba3f7ad65143292a0b2dbd282ae37603` |
| Retained collector base | `5f4070e75ebff6adace731777c68fcf606d85933` | `9ac28476ee6d84102839ed902b924fb487cf429f` |
| GitHub qualification | `fef638d87ec0799e7f94d806cf01da307c5e543d` | `566fa04e3cf080a96a44f9bab16d2785fc60d692` |

The repaired implementation has these exact content identities:

| Path | SHA-256 |
| --- | --- |
| `src/biella/video_frame_pipeline.py` | `f31f87d9debec5358191490a6338b2928ae44492890f83aff8715c6831fc5377` |
| `src/biella/video_pack.py` | `6d46d7c10088c61c61d9c36e899e8fc99068ad36af2ec4f762e4ee76f9c3a739` |
| `src/biella/video_tool.py` | `81b09c84580520bd0f462ad12cf02e343821cb61420114e58945494310b60cab` |

## Retained REAL package

| Record | Identity | Drive |
| --- | --- | --- |
| REAL archive | SHA-256 `32152eab780d65d27231f25d6f12993d16509d3065597bf1e5d2ee841efcf31f`; `1269361` bytes | `11y5PsDydFy47HOuuk7oRaXYD5700Eyr9` |
| Engine evidence | SHA-256 `8ec7e88ea6500cea9f94bbad8187e9dce771bbb356cbf03cc06a10c20b7d122f`; `13714` bytes | `1NK1k_Cu3g4lTQCkG6f9_x2aTEZPG4lwA` |
| L40S package gate | SHA-256 `ba0cb68ecff85e56574fdf377517259798e461b2760959682f90d0d20eadbe94`; `8519` bytes | `1huloSs7PkTSxNshXulbHX7GiSRjJclMk` |
| GitHub qualification | SHA-256 `c29be879d85c5eb2dfcfca609cdfb8122fb0df731c0f5e265512d195383610ba`; `1659` bytes | `1ibR3J2_YOAJ9Skuy51bUiE0Rq0FM36JK` |
| GitHub CI evidence | SHA-256 `b47ad9ddd7726826e61a3991e9ab1355587b621110c0aa716d8956143402f7f8`; `1508` bytes | `1oAhDR5odmPWyoAuNIGau63cjFVrXh2cT` |
| L40S wheel | SHA-256 `863c42d7331beb18a34bbe083209118189979b58edd0df14bcb439da0d14d980`; `898769` bytes | `1fRVCu6wh2oX6tbn6b2HXeju2HyFTHFaq` |
| GitHub wheel | SHA-256 `1bf3c9d56b8441235696127517896213ddfa4b4f9ef2e4842bccb68e256e7ed0`; `898769` bytes | `17aj2nmVhMsHhvnNTD05vokzDuyaq9-ow` |

Drive readback reproduced every listed SHA-256 and byte size. The archive contains `75` safe members: one manifest, one checksum index, and `73` exhaustively indexed payloads. It retains `31` Artifact-backed outputs and `7` primary video outputs.

## Requirement results

| Check | Result | Exact bounded evidence |
| --- | --- | --- |
| `inspect_decode` | PASS | REAL ffprobe and full FFmpeg decode; corrupt probe, decode and tool inputs rejected. |
| `source_immutable` | PASS | Video, frame-source and imported P3-12 audio before/after identities matched. |
| `timeline_edit` | PASS | Exact clips, tracks, edits, transitions, timebase and output; trim/edit durations matched within `0.05s`; color policy explicit. |
| `frames` | PASS | Decoder frames `0,1,2`, timestamps `0.0,0.5,1.0`, ordered publication; missing and duplicate frames rejected. |
| `audio_sync` | PASS | Exact imported P3-12 Artifact/Content provenance and explicit `preserve` stretch policy. |
| `subtitles` | PASS | English stream retained with packets and exact provenance Artifact. |
| `encode_mux` | PASS | Final stream order `video,audio,subtitle`; codecs `h264,aac,mov_text`; post-write verification passed. |
| `proxy_cache` | PASS | Proxy is cache-only and cannot replace source authority. |
| `concurrency` | PASS | Independent frame branches reached measured concurrency `>=2` with distinct attempts and ordered publication. |
| `failure_recovery` | PASS | Encode and worker failures retained; smallest invalidated boundaries recovered without invalidating successful outputs. |
| `game_handoff` | PASS | Exact `integration://game/p3-13/reference-video/v1` output/target bindings retained. |
| `l40s_qualification` | PASS | Repaired-source suite `16` tests PASS, strict mypy PASS, wheel retained; execution truth `CPU_ONLY_CUDA_HIDDEN`. |
| `generative` | `OPTIONAL_NOT_RUN` | No unsupported model/provider execution claim. |

The explicit operation contract is satisfied through the VideoTool, VideoFramePipeline, Artifact input registration, timeline bindings, mux bindings and optional VideoModelAdapter boundary for `inspect`, `import`, `generate`, `edit`, `trim`, `sequence`, `compose`, `frame_extract`, `frame_process`, `audio_sync`, `subtitle`, `transcode`, `encode`, `mux`, `thumbnail`, `preview`, `export` and `validate`.

## REAL runtime and remote gates

| Gate | Exact result |
| --- | --- |
| Collector runtime | FFmpeg `8.0.1-3ubuntu2+esm1`, SHA-256 `2347589466b8f0ca31bfc77b953289456bc7fc5c59ea813fa58135f12e5ef408`; ffprobe SHA-256 `80cfeb6c9448268ef92c72e65dcc55c1939e235a231093943a8c1f19dedcf108` |
| Focused local repair | `16` tests PASS; strict mypy PASS over three video sources; compile and diff checks PASS |
| L40S repaired-source gate | `16` tests PASS; strict mypy PASS; wheel built; CPU FFmpeg, CUDA hidden |
| L40S retained-package gate | `75` safe members; `74` checksum entries; `73` payloads; `11/11` declared videos probe and fully decode; corrupt fixture rejected; final mux has video, audio and subtitle; `3` ordered sequences and `9` frames; zero secret matches |
| GitHub Actions | Run `33554959677`; job `100013402450`; `SUCCESS`; `16 passed in 138.97s`; strict mypy PASS; compile and wheel build PASS |
| GitHub artifact | Artifact `9819033703`; API digest `sha256:7231d6a95f1fedca5ef31b075ecb45aab08d96da20f2d46d7a3b60c556e8e7b6`; size `895983` bytes |

The L40S host identity was observed as `NVIDIA L40S`, but the retained media gate truth is `CPU_FFMPEG_GPU_AVAILABLE_NOT_EXERCISED`. No GPU video-acceleration claim is made.

## Authoritative Engine evidence

| Identity | Exact value |
| --- | --- |
| Project | `prj_de760e9b27764d0f8754f7bcecc31c47` |
| Task | `tsk_138c4ada35c4401fa2339ce284fb67d9/1` |
| Run | `run_7dea687cfafe409bb132f7ff68fbd8e4` `SUCCEEDED` |
| Graph | `graph://prj_de760e9b27764d0f8754f7bcecc31c47/gph_f189fc9a80c94bb881bdc2a1a1b36157/1` |
| Graph SHA-256 | `98919717ccf11483a6ab8a5f983fe2a2151f29a64a62f17ea5c39f464cf8f3fe` |
| Integration node | `node://prj_de760e9b27764d0f8754f7bcecc31c47/gph_f189fc9a80c94bb881bdc2a1a1b36157/1/nod_86490aa965874ea7937c91cea6904625` |
| Retained package Artifact | `artifact://prj_de760e9b27764d0f8754f7bcecc31c47/art_24b9f850450243439121f2c1409ddb82/1` |
| Retained package Content | `content://sha256/32152eab780d65d27231f25d6f12993d16509d3065597bf1e5d2ee841efcf31f?size=1269361` |
| Integration Artifact | `artifact://prj_de760e9b27764d0f8754f7bcecc31c47/art_ab692d52172d4112baf0c52a6f7a6b99/1` |
| Integration Content | `content://sha256/20a42a2a90b897cd1c851174f32b42541c4f208fb040d6d7f3c8391019bf4263?size=3243` |
| Validation plan | `validation-plan://prj_de760e9b27764d0f8754f7bcecc31c47/vplan_cc82a22e25234d9583b987b5d3426eb7` |
| Validation aggregate SHA-256 | `88adf5cc6cc6448e7fe2f3bfd6b4ca86e2d9d1c6a98da5d7fd1c10971f088707` |
| Evidence event | `event://prj_de760e9b27764d0f8754f7bcecc31c47/evt_30faa1b561ff4aa589558e01ddedc8c6` |
| Acceptance event | `event://prj_de760e9b27764d0f8754f7bcecc31c47/evt_3e4732a151834e53bcadd2849f367dda` |

The immutable Graph contains `12` check Nodes plus the integration Node. The importer reconstructed `79` Artifacts and exact ContentRef bytes, `25` current ValidationResults, the ValidationAggregate, both Events, and the successful Run.

## Corrected six-KPI report

| KPI | Observed | ValidationResult |
| --- | ---: | --- |
| `invalid_video_container_claimed_valid` | `0` | `validation-result://prj_de760e9b27764d0f8754f7bcecc31c47/vresult_902d49384c9c4a43aca7490cd1abbfae` |
| `source_video_destructively_mutated` | `0` | `validation-result://prj_de760e9b27764d0f8754f7bcecc31c47/vresult_2479173198334eb0b8f0ffacb9196a0e` |
| `frame_order_lost` | `0` | `validation-result://prj_de760e9b27764d0f8754f7bcecc31c47/vresult_d5316336e1214aa187a138155851fa56` |
| `missing_frames_silently_replaced` | `0` | `validation-result://prj_de760e9b27764d0f8754f7bcecc31c47/vresult_762a2c5a573a48ed8831985725aa9dfd` |
| `audio_silently_stretched` | `0` | `validation-result://prj_de760e9b27764d0f8754f7bcecc31c47/vresult_31cf031b4d164ebbac533e6414e7e8ae` |
| `global_frame_rate_or_resolution_policy` | `0` | `validation-result://prj_de760e9b27764d0f8754f7bcecc31c47/vresult_d3748c649c1947ba9e715b1633942a93` |

## Bounded recovery and non-claims

The collector retained the exact bounded causes for attempts 1-10; attempt 11 alone produced the final archive. The authoritative importer initially refused three invalid preflight/integration boundaries without retaining final state: prefix-only secret matching, omitted retained L40S check topology, and forbidden non-semantic Artifact metadata. Focused regressions corrected those boundaries; the final import and reconstruction passed with zero unresolved failures.

No source authority was assigned to proxies. No missing frame was synthesized. No implicit audio stretch, frame-rate policy, resolution policy or color conversion was used. No generative provider execution or GPU media acceleration is claimed. No credential or plaintext capability is retained.

## Completion statement

P3-13 is complete at the evidence layer: repaired video contracts are remotely qualified, REAL editable media operations and outputs are retained with exact Artifact/Content provenance, the corrected six KPIs are all zero, the package passes independent L40S and GitHub gates, and a reconstructable authoritative Engine Run records current accepted validation and durable Events.
