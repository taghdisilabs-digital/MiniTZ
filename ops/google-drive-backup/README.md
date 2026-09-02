# Biella Google Drive Backup Map

This folder records the operational Google Drive/rclone paths and the upload method that worked on the L40S worker. It intentionally does **not** contain OAuth tokens, client secrets, refresh tokens, or the contents of `rclone.conf`.

## Access boundary

Treat the local PC side and the remote GPU side as separate identities.

- The **GPU SSH username may change** when the worker/provider/image changes.
- The GPU host/IP is currently `152.228.213.182`.
- The last observed GPU SSH username was `ubuntu`, but scripts/runbooks must not treat that username as permanent.
- Express the remote login as `<GPU_USER>@152.228.213.182` unless the current username has been freshly observed.
- The **PC local folder is stable** and must not be changed merely because the GPU username changes.
- Do not derive, rename, or relocate the PC local folder from the remote GPU username.
- The exact PC local folder path must be copied from the user's machine/current configuration when needed; do not invent it from remote state.

Example SSH form:

```text
ssh -i <PC_LOCAL_KEY_PATH> <GPU_USER>@152.228.213.182
```

Example SCP form:

```text
scp -i <PC_LOCAL_KEY_PATH> <PC_LOCAL_FILE_OR_FOLDER> <GPU_USER>@152.228.213.182:/home/<GPU_USER>/
```

The invariant is:

```text
PC local path = stable user-owned path
GPU username   = replaceable remote login detail
GPU filesystem = remote machine state
```

## Runtime host

- Hostname: `biella-l40s-worker`
- GPU address: `152.228.213.182`
- Last observed SSH user: `ubuntu` (replaceable; reobserve before relying on it)
- Root shell after login: `sudo -i`
- Full VPS backup script: `/root/FULL_GPU_VPS_BACKUP_TO_DRIVE.sh`
- Full VPS backup log: `/root/FULL_GPU_VPS_BACKUP_TO_DRIVE.log`
- Backup tmux session: `full-gpu-vps-backup`
- Historical/pre-Spark preservation root: `/root/_BIELLA_PRE_SPARK`

## rclone

- Working remote name: `gdrive:`
- Root-user default config path: `/root/.config/rclone/rclone.conf`
- Authoritative runtime command to print the actual config path:

```bash
rclone config file
```

- List configured remotes:

```bash
rclone listremotes
```

Do **not** commit or print the contents of `rclone.conf` into GitHub. The file can contain OAuth credentials/tokens.

## Google Drive recovery folders

### Current recovery root

- Name: `BIELLA_RECOVERY_NOW_2026-09-02`
- Drive folder ID: `1GMa4BPSsfVU73QlLpnBqwvtfsg_Gx3XR`

Children currently used:

- `01_ENGINE`
- `02_GAME`
- `03_WEBSITE`
- `04_BACKUPS`
- `05_2026-09-01_ORIGINALS`

### Current backup destination

- Name: `04_BACKUPS`
- Drive folder ID: `1jPnxkeZXrqL-6r8V25JDaJm2xF27a8DR`

Current full-GPU backup directories are created beneath that folder as:

```text
FULL_GPU_VPS_<UTC_TIMESTAMP>
```

The full backup script uses this exact folder as the rclone root with:

```bash
--drive-root-folder-id 1jPnxkeZXrqL-6r8V25JDaJm2xF27a8DR
```

### Previous GPT-5.6 evacuation destination

- Folder: `GPT56_HANDOFF_20260901T213353Z/controller_full`
- Drive folder ID: `1vf-6AcRl2qOlxF-qjm5KWx-5o13YjU60`

The successful controller archive was uploaded there as two large parts:

```text
CONTROLLER_BIELLA_FULL_20260901T222006Z.tar.zst.part-0
CONTROLLER_BIELLA_FULL_20260901T222006Z.tar.zst.part-1
```

Observed finalized Drive sizes:

```text
part-0 = 3,838,984,680 bytes
part-1 = 3,838,984,679 bytes
```

Checksum manifest name:

```text
CONTROLLER_BIELLA_FULL_20260901T222006Z.3.6G_PARTS_SHA256.txt
```

### Previous L40S main archive

- Folder name: `l40s_main`
- Drive folder ID: `1PF4NOtL15KxtBRl6msSO_UNCOnAp5O24`
- Archive name: `L40S_BIELLA_BACKUP_20260901T215628Z.tar.zst`
- Drive file ID: `1GyFBfhaWtLigBj_TwFnbZ0uJpueUjTP5`
- Size: `6,719,217,498` bytes

## Proven fast large-file upload settings

For evacuation, use one large file at a time. The proven fast path is sequential `copyto`, IPv4 binding, HTTP/2 disabled, then an `lsl` metadata/size check. **Do not run `rclone cat` between parts.**

```bash
rclone copyto \
  /absolute/path/to/PART \
  gdrive:REMOTE_NAME \
  --drive-root-folder-id DRIVE_FOLDER_ID \
  --bind 0.0.0.0 \
  --disable-http2 \
  --drive-chunk-size 128M \
  --contimeout 15s \
  --timeout 10m \
  --retries 10 \
  --low-level-retries 20 \
  --stats 10s \
  --progress
```

After the command returns, confirm the finalized Drive object and expected size:

```bash
rclone lsl \
  gdrive:REMOTE_NAME \
  --drive-root-folder-id DRIVE_FOLDER_ID \
  --bind 0.0.0.0 \
  --disable-http2
```

Then move immediately to the next part.

For the controller evacuation, the reliable part size was about 3.5-3.9 GiB. Parallel 512 MiB uploads repeatedly stalled around 4 GiB and are not the default evacuation path.

The fast operational sequence is:

```text
copyto(part N)
-> wait for copyto to return
-> lsl size check
-> copyto(part N+1)
```

## Do not confuse Drive finalization with readback

When rclone shows a file at `100%` but still shows:

```text
Transferred: 0 / 1
```

it is still inside `copyto`, waiting for Drive finalization and/or an internal retry. The displayed transfer rate can decay from MiB/s to KiB/s or bytes/s while no new payload bytes are moving. That slowdown is **not** a SHA256 readback.

If rclone reports more transmitted bytes than the file size (for example 7.4 GiB transmitted for one 3.7 GiB file), that indicates an upload retry/retransmission inside `copyto`; it does not mean a second verification download is occurring.

## Optional full remote-byte verification — never in the evacuation upload loop

`rclone cat` downloads the remote object back from Google Drive. Running it after every uploaded part adds one complete download of every part and can roughly double the network traffic for the backup.

For the 2026-09-02 full GPU backup, 17 parts represented roughly 61 GiB of compressed backup data. Per-part `rclone cat` verification would therefore add roughly another 61 GiB of Drive-to-worker traffic and substantial extra wall-clock time.

Do **not** put this operation between sequential uploads unless Mahdi explicitly requests cryptographic remote-byte verification or the active task contract requires it.

If explicit byte-for-byte verification is required later, run it as a separate post-upload operation:

```bash
REMOTE_SHA="$(
  rclone cat gdrive:REMOTE_NAME \
    --drive-root-folder-id DRIVE_FOLDER_ID \
    --bind 0.0.0.0 \
    --disable-http2 \
  | sha256sum \
  | awk '{print $1}'
)"
```

For a split archive, a full reconstructed-stream check is likewise a separate optional post-upload operation:

```bash
REMOTE_FULL_SHA="$(
  {
    for PART in PART_0000 PART_0001 PART_0002; do
      rclone cat "gdrive:$PART" \
        --drive-root-folder-id DRIVE_FOLDER_ID \
        --bind 0.0.0.0 \
        --disable-http2
    done
  } | sha256sum | awk '{print $1}'
)"
```

This is stronger cryptographic assurance, but it is **not the default evacuation transfer path**.

## Current full GPU VPS backup format

The active backup created a compressed stream from the persistent filesystem and split it into approximately 3.8 GiB pieces:

```text
/FULL_GPU_VPS_BACKUP_STAGING_<UTC_TIMESTAMP>/
  FULL_GPU_VPS_<UTC_TIMESTAMP>.tar.zst.part-0000
  FULL_GPU_VPS_<UTC_TIMESTAMP>.tar.zst.part-0001
  ...
  PARTS.sha256
  FULL_STREAM.sha256
  BACKUP_METADATA.txt
```

Included: persistent filesystem rooted at `/`.

Excluded runtime pseudo-filesystems:

```text
/proc
/sys
/dev
/run
```

The 2026-09-02 execution created 17 parts for `FULL_GPU_VPS_20260902T033807Z`: sixteen parts of `3,984,588,800` bytes plus final part `0016` of `2,142,394,289` bytes.

## Status vocabulary and completion gates

Do not collapse upload presence and cryptographic byte-readback into one ambiguous word.

Use these exact meanings:

```text
FAST_EVACUATION_COMPLETE=YES
```

means every expected unique part exists in Drive and each Drive object has the expected byte size. This is the normal fast evacuation completion state.

```text
BYTE_READBACK_VERIFIED=YES
```

means a separate `rclone cat`/SHA256 operation downloaded the remote bytes and matched the expected digest. Do not claim this unless that operation was actually performed.

```text
SOURCE_DELETE_PERFORMED=NO
```

means the upload procedure itself did not delete the source.

The default evacuation path is therefore:

```text
local archive/stream
-> ~3.5-3.9 GiB parts
-> sequential copyto
-> Drive lsl size check
-> next part
-> all expected unique parts present at expected sizes
-> FAST_EVACUATION_COMPLETE=YES
```

Do not add per-part `rclone cat`, full reconstructed-stream downloads, alternate backup formats, parallel transfer layers, or extra infrastructure unless explicitly requested or required by the active task.

## Related runbook

See also:

```text
ops/GOOGLE_DRIVE_LARGE_BINARY_UPLOAD.md
```

That file records the large-binary upload failure mode and the proven sequential recovery procedure.