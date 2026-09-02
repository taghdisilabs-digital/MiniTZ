# Google Drive Large Binary Upload — Proven Biella Procedure

Use this runbook when evacuating large controller/GPU archives to Google Drive with `rclone`.

## Observed failure to avoid

Do not default to many parallel 512 MiB uploads for evacuation work. In the 2026-09-02 controller evacuation, `rclone copy` with 8 parallel transfers reached 4 GiB sent while Google Drive had finalized zero files, then stalled. A second parallel attempt finalized only a subset before stalling again.

Do not interpret an individual rclone transfer line showing `100%` as durable completion. The file is durable only after the `copyto` command returns successfully and Drive readback confirms the remote object.

## Proven working pattern

For a roughly 7–8 GiB archive, split into two files so each file is about 3.5–3.9 GiB, then upload one file at a time.

Example:

```bash
SRC="/path/to/ARCHIVE.tar.zst"
OUT="/path/to/upload-parts"
mkdir -p "$OUT"

split -n 2 -d -a 1 \
  "$SRC" \
  "$OUT/$(basename "$SRC").part-"

ls -lh "$OUT"
```

Create local SHA256 evidence before upload:

```bash
cd "$OUT"
sha256sum *.part-* | tee SHA256SUMS.txt
```

## Upload one part at a time

Use IPv4 binding and disable HTTP/2. Do not run multiple large `copyto` commands concurrently unless current evidence proves that path healthy.

```bash
rclone copyto \
  /absolute/path/to/ARCHIVE.tar.zst.part-0 \
  gdrive:ARCHIVE.tar.zst.part-0 \
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

After that command returns successfully, verify the remote object before uploading the next part:

```bash
rclone lsl \
  gdrive:ARCHIVE.tar.zst.part-0 \
  --drive-root-folder-id DRIVE_FOLDER_ID
```

Then repeat the same `copyto` + `lsl` sequence for `part-1`, `part-2`, etc.

Upload the checksum manifest last:

```bash
rclone copyto \
  /absolute/path/to/SHA256SUMS.txt \
  gdrive:ARCHIVE.PARTS_SHA256.txt \
  --drive-root-folder-id DRIVE_FOLDER_ID \
  --bind 0.0.0.0
```

## Full remote-byte verification

For a split archive, the strongest deletion gate is to read every uploaded part back from Drive in lexical/original order, concatenate the byte stream, and compare its SHA256 with the original archive SHA256.

```bash
ORIGINAL_SHA="$(sha256sum /absolute/path/to/ARCHIVE.tar.zst | awk '{print $1}')"

REMOTE_SHA="$(
  for PART in \
    ARCHIVE.tar.zst.part-0 \
    ARCHIVE.tar.zst.part-1
  do
    rclone cat "gdrive:$PART" \
      --drive-root-folder-id DRIVE_FOLDER_ID \
      --bind 0.0.0.0 \
      --disable-http2
  done | sha256sum | awk '{print $1}'
)"

printf 'ORIGINAL_SHA=%s\nREMOTE_SHA=%s\n' "$ORIGINAL_SHA" "$REMOTE_SHA"
test "$REMOTE_SHA" = "$ORIGINAL_SHA"
```

Only after that comparison succeeds is the split Drive copy verified as reconstructing the exact original archive bytes.

## Persistent execution

For uploads that must survive an SSH/window disconnect, run one upload in `tmux`:

```bash
tmux new-session -d -s drive-upload \
  'rclone copyto /absolute/path/to/PART gdrive:PART --drive-root-folder-id DRIVE_FOLDER_ID --bind 0.0.0.0 --disable-http2 --drive-chunk-size 128M --contimeout 15s --timeout 10m --retries 10 --low-level-retries 20 --stats 10s --progress 2>&1 | tee /root/drive-upload.log'
```

Attach with:

```bash
tmux attach -t drive-upload
```

Detach without stopping the upload with `Ctrl+b`, then `d`.

## Biella evacuation rule

Do not delete the local source, `_BIELLA_PRE_SPARK`, controller origin material, GPU origin material, or another sole surviving copy merely because bytes were reported as transferred. Keep the source until Drive contains the intended objects and the required byte/digest verification succeeds.

For emergency evacuation, prefer the smallest proven path: existing verified archive -> ~3.5–3.9 GiB parts -> sequential `copyto` -> Drive object readback -> checksum manifest -> reconstructed remote SHA256. Do not introduce parallelism, alternate backup formats, or additional infrastructure unless the active task requires it.
