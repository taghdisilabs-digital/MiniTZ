# P3-12 Audio Production Repair Evidence

## Evidence status

| Field | Result |
| --- | --- |
| Task | P3-12 Audio Production, Processing, Mixing and Validation Pack durable repair |
| Evidence result | COMPLETE |
| Retained evidence schema | `biella.p3-12.retained-real-evidence/v1` |
| Authoritative Engine evidence schema | `biella.p3-12.durable-engine-evidence/v1` |
| Authoritative Engine status | `SUCCEEDED` |
| Validation verdict | `PASS` |
| Reconstruction | `PASS` |
| Unresolved importer failures | `0` |
| Current repair commit | `c99cb2d57f7dd710e97465fed4d961286b72050c`; tree `e0cf13164bc335342ef4d206569197f03366f710` |

This document records the retained REAL execution evidence and its successful import into a new authoritative Engine Run. It does not treat a provider fixture Run that remained `RUNNING` as completed, and it does not claim GPU execution.

## Accepted source identity

| Identity | Value |
| --- | --- |
| Accepted implementation commit | `3dcc194253bb54d2a171cf7230877af95231ebe7` |
| Accepted implementation tree | `8835d92e6651ea13ec5f02b87487f0520fb7bae6` |
| Accepted follow-on source commit supplied for this repair | `96f47758719b0d19efba74e6672b63b5abc7d2fb` |
| Cloudflare fixture observed source commit | `196c6af359a67961f165340b91f8178a6e7c827d` |
| Cloudflare fixture observed source tree | `6d08d971d22a1ecaea072e4261e9988e04336276` |
| Repair result source | Commit `c99cb2d57f7dd710e97465fed4d961286b72050c`; tree `e0cf13164bc335342ef4d206569197f03366f710` |

The three implementation files had the same hashes in the retained collector, the Cloudflare REAL qualification, and the authoritative importer:

| File | SHA-256 | Size |
| --- | --- | ---: |
| `src/biella/audio_pack.py` | `864017ddd61fd4900634a897f7eee5cc767f17548713758fd61806e1ea9afa70` | 25,692 |
| `src/biella/audio_tool.py` | `45232f37884ef80ea6c60f9d88170fca62ccf3c4735e5749c8c0e63cf710b346` | 75,849 |
| `src/biella/cloudflare_audio_model.py` | `24f4ac0d6ce3244922b76de0207e374c8dcbc11a49cdf42563c88fcd7c2b3bd5` | 41,730 |

## Retained package identity

| Record | Exact identity | Result |
|---|---|---|
| REAL archive | `/root/biella/evidence/p3-12/P3_12_FINAL_REAL_EVIDENCE.tar.gz` | SHA-256 `2ec11b1fe23b9fd49aed4dbc4e31ad709fb56aac0dbbf19a4b6e292499d290f1`; size `300400` bytes; verified |
| Archive manifest | `biella.p3-12.retained-real-evidence/v1` | `64` total members: `evidence/manifest.json`, `evidence/manifest.sha256`, and `62` exhaustively indexed payload members; `63` checksum entries cover the manifest and every payload |
| Engine import record | `/root/biella/evidence/p3-12/P3_12_ENGINE_EVIDENCE.json` | SHA-256 `792ae50346366ee16dfae48f55f07de73d9afe918d9694aa9d479324e1ea6b0a`; size `6723` bytes; schema `biella.p3-12.durable-engine-evidence/v1` |

The archive content identity is `content://sha256/2ec11b1fe23b9fd49aed4dbc4e31ad709fb56aac0dbbf19a4b6e292499d290f1?size=300400`. The authoritative import retained that exact content and reconstructed it with verdict `PASS`, Engine status `SUCCEEDED`, and `0` unresolved failures.

## Requirement results

| Requirement | Result | Exact evidence |
| --- | --- | --- |
| Decode | PASS | REAL WAV and MP3 metadata were obtained through FFmpeg/ffprobe 8.0.1 full decode; corrupt MP3 and media/container mismatch were rejected. |
| Source immutable | PASS | All `7` retained source records had identical initial and final hashes and bytes. |
| Operations | PASS | `11` explicit operations published new Artifact and Content identities: trim, segment, resample, mono conversion, MP3 conversion, filter, clean, normalize, master, preview, and export. |
| Mix | PASS | Exactly `2` processed stems, exact levels/timing/gain/pan/effects, a REAL mix output, measurements, and an editable session were retained. |
| Concurrency | PASS | Two distinct dispatched attempts were used and measured maximum active execution was `2`. |
| Failure recovery | PASS | The corrupt stem failed while the valid retry output remained retained; the Cloudflare MeloTTS HTTP 500 did not invalidate the successful Aura output. |
| Handoffs | PASS | Exact game and video integration bindings reference the retained mix output and target evidence. |

### Decode facts

| Input | Observed metadata |
| --- | --- |
| Primary WAV | `pcm_s16le`, WAV, 48,000 Hz, stereo `FL/FR`, 16-bit `s16`, duration `0.24`, 11,520 samples, 1,536,000 bit/s, content SHA-256 `486dee19ee8c54f2b349cee154addc0e5663f702b4364828497b19087e2f68c2`, decoder `ffmpeg://8.0.1/pcm_s16le` |
| Primary MP3 | MP3, 48,000 Hz, stereo `FL/FR`, 32-bit `fltp`, duration `0.264`, 12,672 samples, 96,000 bit/s, content SHA-256 `5403c2531986fea4eb3a6f4ce758b42a39a70fdc4af98e50e42dc15708160866`, decoder `ffmpeg://8.0.1/mp3` |
| Corrupt MP3 | Rejected; no valid-audio claim was published |
| WAV claimed as MPEG | Rejected as a media/container mismatch |

The primary source Artifact and Content were:

- Artifact: `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_b7101e8f5e87410e9776f3fbde8c28b8/1`
- Content: `content://sha256/486dee19ee8c54f2b349cee154addc0e5663f702b4364828497b19087e2f68c2?size=46124`

### Explicit operation publications

| Operation | Artifact | Content |
| --- | --- | --- |
| trim | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_f93ba4167aa94d7797caf96b405f74e7/1` | `content://sha256/9f5b48b3f5228656231679f0f295d6bde33447bdb7d5d2db3a7ea9426d51f321?size=23084` |
| segment | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_fe0e498ec75c46fdb4af7c07e37343eb/1` | `content://sha256/4a7f9aed44cfb5feb40f2a37d427a7b00f701c5bed2b732bb2db07eb0ecb97f8?size=15404` |
| resample | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_2a6c9bbd65f94caf9b90fedff65c11e4/1` | `content://sha256/74d5761a3f51cd031344170e5efdf45769006e7b9814e36ed642946107afbbf6?size=23084` |
| convert mono | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_9c8715ed4ed74f059f518919fd1da770/1` | `content://sha256/7ea7c3444aaabdee03c76e85c3073a20374cf49238b2714bd771817f7976d033?size=23084` |
| convert MP3 | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_1121b280401e45f38e9de993fd7e2b88/1` | `content://sha256/5403c2531986fea4eb3a6f4ce758b42a39a70fdc4af98e50e42dc15708160866?size=3168` |
| filter | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_a4545b709e144f1d8226e008c2479509/1` | `content://sha256/e4e261b05ed6f238044ffb23dafe4f66122afad56a868ea2559888a001866019?size=46124` |
| clean | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_03f658a6c65e44078b08559eda8d1300/1` | `content://sha256/fe99a23cdcfc84eb1a9ef51e383876310f18a7d4deec16eef88215a08efda3ed?size=46124` |
| normalize | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_39c3b03fc59f453abd45f09f4777fc73/1` | `content://sha256/d795e46f709fe2ef2a9b21fc5285ce02469f6acb42974bd5b3b5b42b80331dba?size=46124` |
| master | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_b628cb7082334de08271613d1a5c4c5a/1` | `content://sha256/95a92e810a7c291c2da068a130af7409122406eb59d2c131c3738e346a38043f?size=46124` |
| preview | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_d27d52323fd341e4a5838012fac04aaa/1` | `content://sha256/19c7fb553c23df6fb8a39b543a847c7d1d39f98fbcdb150055bae879512aeb6e?size=19244` |
| export | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_7caca75b54fa4cc1b1f23caaae05fb64/1` | `content://sha256/e260b1c8b999f29c4ec6159ab1780c14e54757eb7e6d5d0d8fe4204375bf249d?size=46124` |

Implicit sample-rate conversion, implicit channel-layout conversion, and unscoped loudness/gain mutation were separately rejected.

### Mix, session, concurrency, recovery, and handoffs

| Evidence | Identity or result |
| --- | --- |
| First processed stem | Artifact `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_729152a6cbb841c1a9b6144865aa687d/1`; Content `content://sha256/b257c5118500cf9a3d21f71756a872358a937c08e83783a83333a6d9cfcfcbef?size=46124` |
| Second processed stem | Artifact `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_48b42cbab12c4d26a4460b6b2947972f/1`; Content `content://sha256/3d1066cde0c557af1c90cea13b1c404d383a3825e4cd21ce801e430c61a4016c?size=46124` |
| First stem level | `{"effects":["highpass:80"],"gain_db":-3.0,"offset_seconds":0.0,"pan":-0.5}` |
| Second stem level | `{"effects":["lowpass:12000"],"gain_db":-6.0,"offset_seconds":0.02,"pan":0.5}` |
| Mix | Artifact `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_9a42543742af41449fdd3b6a3613e266/1`; Content `content://sha256/8ab73244a9d0d6e6fa9485906d0ec600eda0104cf73461be01ad09e4bf1f34b9?size=49964`; 48,000 Hz stereo; duration `0.26`; target `-18 LUFS` |
| Editable session | Artifact `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_5b4ca0e0c00e4895909df370e4c802eb/1`; Content `content://sha256/f2b115d2305f5b2dbc5003926b15ac8d738502b3cc2cd418b4d4ebb291d5ae7d?size=1763` |
| Concurrency | Distinct child attempts; measured maximum active `2` |
| Recovery output | Artifact `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_fe4430d8e48d403e98e0cb0881abe23d/1`; Content `content://sha256/b257c5118500cf9a3d21f71756a872358a937c08e83783a83333a6d9cfcfcbef?size=46124` |
| Handoff target | Artifact `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_f92e98499edc4b1e800bc71d3e79de1a/1`; Content `content://sha256/465923983be8dc42b903ada42262cd7904c8ee3b59ee61e1d8404bb49eca4dd9?size=20` |
| Game handoff | `integration://game/project-main/audio/v1` |
| Video handoff | `integration://video/project-main/audio/v1` |

The mix was produced by node attempt `natt_1278ec88cc924ffc81848cf2a7cea10d` with fence `1`. Measurements and decoded analysis are retained as indexed JSON payloads.

## REAL runtime and provider truth

### Local FFmpeg runtime

| Runtime | Identity |
| --- | --- |
| Audio runtime | `runtime://audio/ffmpeg-8.0.1-cpu` |
| FFmpeg | `/usr/bin/ffmpeg`, version `8.0.1-3ubuntu2+esm1`, SHA-256 `2347589466b8f0ca31bfc77b953289456bc7fc5c59ea813fa58135f12e5ef408`, size `453104` |
| ffprobe | `/usr/bin/ffprobe`, version `8.0.1-3ubuntu2+esm1`, SHA-256 `80cfeb6c9448268ef92c72e65dcc55c1939e235a231093943a8c1f19dedcf108`, size `216864` |
| Execution truth | REAL CPU FFmpeg; `gpu_acceleration_claimed=false` |

### Independent L40S-hosted runtime

The independent payload contains `input.wav`, `output.mp3`, `decoded.wav`, `probe.json`, and `receipt.json`. Its exact execution truth is `CPU_FFMPEG_ON_L40S`: the host has an L40S identity, but the audio execution did not claim GPU acceleration.

| Field | Value |
| --- | --- |
| Host label | `biella-gpu` |
| Receipt SHA-256 | `7f82646ae176a51367314c484e4344a08a440d36b196bac0b03ddebf391f7d47` |
| Receipt size | `1100` bytes |
| Imported receipt Artifact | `artifact://prj_f573cf7dda194c168dcc6185a50c22cf/art_bee372d9719a43e1a8ddce9b11121593/1` |
| Imported receipt Content | `content://sha256/7f82646ae176a51367314c484e4344a08a440d36b196bac0b03ddebf391f7d47?size=1100` |
| Exact-result qualification | Commit `c99cb2d57f7dd710e97465fed4d961286b72050c`; tree `e0cf13164bc335342ef4d206569197f03366f710`; archive identity `PASS` |
| Exact-result importer | `1 passed in 12.50s`; `CPU_ONLY_CUDA_HIDDEN`; provider calls and audio operation suite not rerun |
| Exact-result receipt | SHA-256 `a4b0dc9b0b8e360880faee867170b383702ee2c86506bf0bb82c3631e334ae6d`; size `3015`; Drive `15Q_msefmw9EEcTczQV4sUjb_puYxFIkS` |
| Exact-result wheel | SHA-256 `124d2b27036ae5b00b9ae1ae097f49001a579e878639086c30c9191c520a1c1d`; size `897848`; Drive `1nqxU2kM_EOpyT5SM4tDtuVCm8LPTR7J9` |

### Cloudflare Workers AI provider

| Provider result | Exact truth |
| --- | --- |
| Runtime | `runtime://cloudflare/workers-ai/v1` via `provider://cloudflare/workers-ai` |
| Aura | ModelCall `mcall_5c552cb17eed4afa98012c05276d17ff` `SUCCEEDED`; REAL provider MP3 was accepted and fully decoded |
| Aura MP3 | Artifact `artifact://prj_079d636f97494cd3b3e690c9d74d8fc3/art_65be5fafed824c2d8d7c2ce5fb207847/1`; Content `content://sha256/38cda8c0da345b1e3d330e934bfe27a1cd595ec6c8374b252640508b84a466b0?size=15516` |
| Aura decoded metadata | MP3, 22,050 Hz, mono `FC`, `fltp`, duration `2.5861224489795918`, 57,024 samples, 48,000 bit/s, decoder `ffmpeg://8.0.1/mp3` |
| Aura validation | Artifact `artifact://prj_079d636f97494cd3b3e690c9d74d8fc3/art_c55fe2e53fa44a839f2e38cbd1faaed5/1`; Content `content://sha256/b8e65981060590ecc9e319aacbaaea56c309f98a2f8bcfc65e2c9677a3b177ff?size=948` |
| MeloTTS | HTTP 500 observed; provider audio unavailable; failure categorized `PROVIDER_HTTP_FAILURE` |
| Provider fixture Run truth | Aura and MeloTTS fixture Run/Node states remained `RUNNING` with zero completion manifests because the exited process did not retain plaintext `ProjectAccess` authority |
| Authoritative resolution | The archive importer created the separate successful evidence Run recorded below; no fixture authority was forged or bypassed |
| GPU claim | None; `gpu_acceleration_claimed=false` |

Cloudflare fixture identities:

| Fixture | Run | Graph | Node | Event |
| --- | --- | --- | --- | --- |
| Aura | `run_87e80f4588a64a83bf925f611e062797` | `graph://prj_079d636f97494cd3b3e690c9d74d8fc3/gph_e8744a8eb9bd4e4a8d199581e0569977/1` | `nod_66eff8a4a48842efb321728baec0d50c` | `event://prj_079d636f97494cd3b3e690c9d74d8fc3/evt_3f5ed91c21d84a24ac4d3a1650f4b5f7` |
| MeloTTS | `run_f367d3648f4241aaa6fb4f9b61917f9d` | `graph://prj_c4166d6b8b144296b53b8cb33c306f39/gph_77b2896be44941e590a0569ac2cee295/1` | `nod_81cddbfe001a4db58592fad5da6a50a5` | `event://prj_c4166d6b8b144296b53b8cb33c306f39/evt_f38f19c0305843c3a9d7cee48caf97eb` |

The provider qualification secret scan passed with zero bearer-token pattern matches, zero exact account-ID matches, and zero exact API-token matches. Only sanitized logs are retained.

The retained Cloudflare qualification record is `/root/biella/evidence/p3-12/cloudflare-real/P3_12_CLOUDFLARE_REAL_QUALIFICATION.json`, SHA-256 `bbd5e74e36fef5c73afb8782374c4cd7e75936b8bbffa60682b77542eefd541f`, size `10965` bytes. It contains provider execution and qualification facts only; the authoritative imported task Run above supplies the durable `SUCCEEDED` task-level Engine identity.

## Result qualification and publication

| Evidence | Exact result |
| --- | --- |
| Local final gate | `25 passed, 2 skipped in 124.03s`; strict mypy `Success: no issues found in 3 source files`; bounded diff and compile checks passed |
| GitHub source readback | Commit `c99cb2d57f7dd710e97465fed4d961286b72050c`; tree `e0cf13164bc335342ef4d206569197f03366f710`; workflow blob `95fbf350767c4765b03fd93c29cd49740207d6f2`; importer-test blob `0f3a34dc36785615ccdf41dc339d4e7af44b3a79` |
| GitHub Actions | Run `33549462937`; job `99995052774`; `SUCCESS`; `24 passed, 3 skipped in 106.31s`; strict mypy passed; wheel build passed |
| GitHub artifact | Artifact `9817199535`; uploaded ZIP SHA-256 `5cfd38066639d1d3edeed7e78d7bcb6e5fad4616b7465387fb28c9ba0472d57b`; size `895086` |
| GitHub wheel | SHA-256 `55d709417453795e9b79c0851795049352c6e3b0c649c7e027af8efa6330e24f`; size `897848`; Drive `1J_FkQ5JCclF_HqhUXVKcW6_5X4Ceimy9` |
| GitHub CI evidence | SHA-256 `dfe72e551214c7325014144078c19418033fb5863323d3c755bcf841687cc2ad`; size `1576`; Drive `1829aDK2YRrF1ccBzx_V6IbxnSR83ZyvM`; CI explicitly does not claim KPI authority |
| Retained REAL archive | Drive `1RJFzKm16qIsYkHpyEDpzQn-QQwd7ll0A`; exact byte readback matched SHA-256 `2ec11b1fe23b9fd49aed4dbc4e31ad709fb56aac0dbbf19a4b6e292499d290f1` and size `300400` |
| Authoritative Engine evidence | Drive `10Ld2FhHzqvrHQxJBxv9MKPO4zWZKnsoV`; exact byte readback matched SHA-256 `792ae50346366ee16dfae48f55f07de73d9afe918d9694aa9d479324e1ea6b0a` and size `6723` |

## Authoritative Engine import

The post-suite authoritative importer record is `/root/biella/evidence/p3-12/P3_12_ENGINE_EVIDENCE.json` at SHA-256 `792ae50346366ee16dfae48f55f07de73d9afe918d9694aa9d479324e1ea6b0a` and size `6723` bytes. It records schema `biella.p3-12.durable-engine-evidence/v1`, Engine status `SUCCEEDED`, reconstruction `PASS`, validation accepted `true`, validation verdict `PASS`, and `0` unresolved failures.

| Identity | Exact value |
|---|---|
| Project | `prj_508b975a98994bfb9dc6331ade2b2c11` |
| Task | `project_ref=prj_508b975a98994bfb9dc6331ade2b2c11`, `task_id=tsk_840b513f777042e6809d49fb8a4c3b48`, revision `1` |
| Run | `project_ref=prj_508b975a98994bfb9dc6331ade2b2c11`, `run_id=run_20eb839e899c47428de78b991d319640` |
| Graph | `graph://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1` |
| Graph SHA-256 | `cb7718887e70d473d19a66e643ac1a5d1e25bde90f72fa2ac418b88fc7a1aca3` |
| Run-state SHA-256 | `5407c2e28591b7fa1ed817afc06870bc08c0f5017e4f4c27106bee49e73bfa4a` |
| Integration node | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_1ad097ce61d64e2e8a0d43c0a1db8b45` |
| Acceptance event | `event://prj_508b975a98994bfb9dc6331ade2b2c11/evt_2734b8e54fdc47c18f7eeaee258de95e` |
| Evidence event | `event://prj_508b975a98994bfb9dc6331ade2b2c11/evt_0c36b8817b944c678f35a9562c06534e` |
| Retained package Artifact | `artifact://prj_508b975a98994bfb9dc6331ade2b2c11/art_be13bca5301945fbb98162a44a8ccc79/1` |
| Retained package Content | `content://sha256/2ec11b1fe23b9fd49aed4dbc4e31ad709fb56aac0dbbf19a4b6e292499d290f1?size=300400` |
| Integration Artifact | `artifact://prj_508b975a98994bfb9dc6331ade2b2c11/art_67782ac61fbe4590a2179b05a5c8fe4f/1` |
| Integration Content | `content://sha256/8c94a546b02a59e31c76c5ab02cb74aa76ff2feac49ffacb13b28201eb776acf?size=13304` |
| Validation plan | `validation-plan://prj_508b975a98994bfb9dc6331ade2b2c11/vplan_3639a9b10a264a4ebb7820cc0e5d1602` |
| Validation aggregate SHA-256 | `96f256154e7ab55678e8235864513a072a08df0a0d84319fa7463b7d034071dc` |

### Imported check nodes

| Check | Status | Attempt | Node |
|---|---|---|---|
| `decode` | `SUCCEEDED` | `natt_3baef2578ab244799615a85b35c22d6b` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_63dbfe6aa8a743a9a76136aad06726e1` |
| `source_immutable` | `SUCCEEDED` | `natt_38f7ea188c98477ab1c0c0816229b624` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_c266a73de64b4dea92fb73cbd9a676d0` |
| `operations` | `SUCCEEDED` | `natt_511c6dd931c64963b4a51bafb0f7fa45` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_8b26611062324258bd91c05b3c55c4e7` |
| `mix` | `SUCCEEDED` | `natt_ea342edb46444a3b82736154d9fe1304` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_f56c49c38aa94c7985b9b2acaf2ea918` |
| `concurrency` | `SUCCEEDED` | `natt_1bf9087eaf4446f5b8106c215d77e59a` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_5410c85f17404a98b9fe2d5e40f7259a` |
| `failure_recovery` | `SUCCEEDED` | `natt_91cfd2b47bde4326a58b768006d2c4f8` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_6f95e37217d84f7fb8265639305996ab` |
| `handoffs` | `SUCCEEDED` | `natt_2ec4bab003c8459789f3ef406af1ebce` | `node://prj_508b975a98994bfb9dc6331ade2b2c11/gph_f062ff81113b48359b3c1f5be6fb9f5d/1/nod_5ed721fa9f76404189f3aebaf7aa854b` |

### Imported validation results

```text
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_e5cd308f22d64bf0a9bde2b84b8b34f4
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_5332ee04596440cfa3d7d0a5875a9679
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_6b1b2b6ef9de4a44b0d6ede69762900e
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_f48c3b12dfa2447cb50b93506facb815
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_bdd4fb1799f44d91afed4180219a2216
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_43376174dedc469a814906ee8bd73376
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_83510de6f3d14773b6e3ea9c6600e92f
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_60c1b851dafe424e8570c6b9ffd7d692
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_af1bd47ff47b4de69f9595cf49712238
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_9ca1d2d1cbb1464995f283b59ffc3bd5
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_79711e6458d446c5b629af591342410e
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_6fc44f171a5043cf8076440ac713d9ed
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_cf88f32cbf854d3ea0fc649d85b973a7
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_b3a245b2a83547869fe433185d02b80b
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_edeb23ee9f12419eb69a380551aa79bb
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_f7e68a6c7e8b4e909ca33efb2e029cfa
validation-result://prj_508b975a98994bfb9dc6331ade2b2c11/vresult_13ee2ec727f245a591fab75b2aaf8c15
```

## KPI results

| KPI | Observed |
| --- | ---: |
| `invalid_audio_claimed_valid` | `0` |
| `source_audio_destructively_mutated` | `0` |
| `project_loudness_target_globalized` | `0` |
| `implicit_sample_rate_or_channel_conversion` | `0` |
| `mix_without_exact_stem_identity` | `0` |

The authoritative importer reconstructed these five values from the retained checks and recorded the same zero values in the successful evidence Run.

## Bounded collector retry history

The final retained package came from the fourth collector invocation. The history is recorded because the requested single-invocation condition was not literally met; only the fourth invocation produced an archive.

| Invocation | Boundary reached | Result | Effect on final package |
| ---: | --- | --- | --- |
| 1 | Pre-audio evidence import | Rejected a collector-only, non-semantic `retained_path` Artifact metadata key | No REAL audio operation and no archive |
| 2 | Explicit operation evidence wrapping | Raw-output `validate()` returned decoded metadata without an Engine `analysis_ref`; the collector was corrected to publish canonical analysis JSON Artifacts | No archive |
| 3 | All 11 explicit operations, then concurrent stem processing | The collector's second fixture was 0.26 seconds against the accepted 0.24-second stem contract; the accepted `_wav()` fixture was restored | No archive |
| 4 | Full decode, operations, mix, concurrency, recovery, handoffs, archive construction, and internal validation | PASS | Sole retained final package |

The failed collector workspaces were bounded to `/root/biella/evidence/p3-12/.collector-work` and removed before the next invocation. Cloudflare and L40S provider executions were not rerun by these collector retries; their completed bytes were imported and indexed. Repository source files were not changed by the collector.

## Security and non-claims

- No credential, bearer token, account identifier, or plaintext `ProjectAccess` capability is included in this document.
- The Cloudflare qualification secret scan was `PASS` and retained only sanitized logs.
- No GPU acceleration claim is made for the local, L40S-hosted, or Cloudflare audio execution.
- The Cloudflare fixture Runs remained `RUNNING`; only the separate authoritative importer Run is claimed `SUCCEEDED`.
- The repair commit/tree and six raw Drive artifact identities above were remotely read back; publication of this evidence record is bound separately by the continuity close.

## Completion statement

P3-12 durable evidence is complete at the evidence layer: the retained package is hash-addressed and internally validated; all seven requirement checks are `PASS`; all five KPI counters are zero; REAL local, independent L40S-hosted, and Cloudflare provider evidence is retained without a GPU claim; and the authoritative importer created a `SUCCEEDED` Engine Run with accepted validation, evidence and acceptance events, and zero unresolved failures.
