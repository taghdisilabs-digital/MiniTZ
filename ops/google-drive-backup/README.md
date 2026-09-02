# Biella Google Drive Backup Map

This folder records the operational Google Drive/rclone paths and the upload method that worked on the L40S worker. It intentionally does **not** contain OAuth tokens, client secrets, refresh tokens, or the contents of `rclone.conf`.

## Runtime host

- Hostname: `biella-l40s-worker`
- SSH target: `ubuntu@152.228.213.182`
- Root shell: `sudo -i`
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

## Proven large-file upload settings

Use one large file at a time. The working path is sequential `copyto`, IPv4 binding, HTTP/2 disabled, then explicit readback.

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

Verify the finalized Drive object before proceeding:

```bash
rclone lsl \
  gdrive:REMOTE_NAME \
  --drive-root-folder-id DRIVE_FOLDER_ID \
  --bind 0.0.0.0 \
  --disable-http2
```

For the controller evacuation, the reliable part size was about 3.5-3.9 GiB. Parallel 512 MiB uploads repeatedly stalled around 4 GiB and are not the default evacuation path.

## Full remote-byte verification

For each uploaded part:

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

For a split archive, read every part back from Drive in exact original order and hash the reconstructed byte stream:

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

Compare `REMOTE_FULL_SHA` against the local compressed-stream SHA256 before considering the Drive copy verified.

## Current full GPU VPS backup format

The active script creates a compressed stream from the persistent filesystem and splits it into approximately 3.8 GiB pieces:

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

Current execution observed on 2026-09-02 created 17 parts for `FULL_GPU_VPS_20260902T033807Z`: sixteen approximately 3.8 GiB parts plus one approximately 2.0 GiB part.

## Completion gate

Do not delete the local source merely because rclone reports bytes transferred. The full-VPS script must finish with:

```text
BACKUP_VERIFIED=YES
SOURCE_DELETE_PERFORMED=NO
```

The verification path is:

```text
local archive/stream
-> ~3.8 GiB parts
-> sequential copyto
-> Drive lsl size check
-> per-part Drive byte SHA256
-> checksum/metadata upload
-> complete Drive reconstructed-stream SHA256
-> BACKUP_VERIFIED=YES
```

## Related runbook

See also:

```text
ops/GOOGLE_DRIVE_LARGE_BINARY_UPLOAD.md
```

That file records the large-binary upload failure mode and the proven sequential recovery procedure.