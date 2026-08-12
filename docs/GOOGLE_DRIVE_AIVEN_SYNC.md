# Google Drive → Aiven legal-data sync

This integration incrementally catalogs the Google Drive folder `junior-lawyer-data` into Aiven PostgreSQL.

## What it does

- Recursively walks the configured Drive folder.
- Creates `drive_sync_files` and `drive_sync_runs` automatically if they do not exist.
- Stores file metadata, Drive path, checksums, timestamps, and source links.
- Extracts searchable text from text/CSV/JSON/XML/Markdown, PDF, DOCX, and supported Google Workspace exports.
- Skips downloading unchanged files by comparing Drive modification/checksum metadata.
- Keeps oversized or unsupported files as metadata-only records instead of copying large blobs into PostgreSQL.
- Soft-marks files that disappear from the configured Drive tree only after a complete successful traversal.
- Records every run and its counts for audit/debugging.
- Runs every six hours and can also be started manually from GitHub Actions.

The raw legal corpus remains in Google Drive. Aiven acts as the durable database/catalog and searchable extracted-text layer; this avoids duplicating large binary files into PostgreSQL.

## Required GitHub Actions secrets

Create these in **Repository → Settings → Secrets and variables → Actions → Repository secrets**:

### `AIVEN_DATABASE_URL`

Use the PostgreSQL service URI from Aiven, including TLS/SSL parameters supplied by Aiven. Example shape only:

```text
postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

Do not commit the real URI to the repository.

### `GOOGLE_SERVICE_ACCOUNT_JSON`

Paste the complete Google service-account JSON object as the secret value. The sync also accepts the older project setting `STORAGE_GDRIVE_CREDENTIALS_JSON` when run outside the workflow, including its existing base64 format.

Do not commit the service-account JSON.

## Google Drive permission

1. Open the Google service-account JSON and copy its `client_email` value.
2. In Google Drive, share the existing `junior-lawyer-data` folder with that email.
3. **Viewer** permission is sufficient. The sync uses the read-only Drive scope.
4. Sharing the root folder is enough for normal inherited access to its children.

## Optional repository variable

If there is exactly one accessible folder named `junior-lawyer-data`, no folder variable is needed.

If more than one folder has that name, create this under **Repository → Settings → Secrets and variables → Actions → Variables**:

```text
GOOGLE_DRIVE_FOLDER_ID=<the exact root Drive folder ID>
```

The folder ID is the identifier in a Drive folder URL after `/folders/`.

## Running it

After the secrets are configured and this change is merged:

1. Open **Actions**.
2. Choose **Google Drive to Aiven sync**.
3. Choose **Run workflow** for the first run.
4. Leave `metadata_only` off for normal ingestion. Turn it on only when you want to refresh the catalog without downloading/extracting content.

Scheduled runs occur every six hours.

## Content-size behavior

By default, the sync downloads/extracts at most 25 MB per individual file. Larger ordinary files remain in the catalog with `content_state = 'too_large'` and their Drive link, rather than being copied into PostgreSQL.

For manual/local execution, the limit can be changed with:

```text
DRIVE_SYNC_CONTENT_MAX_MB=50
```

For a very large corpus, keep the raw binaries in Drive and raise this limit only when Aiven storage capacity has been sized accordingly.

## Tables

### `drive_sync_files`

Important fields include:

- `drive_file_id` — stable Google Drive identifier and primary key.
- `root_folder_id` — root used for this sync.
- `drive_path` — reconstructed path under the Drive root.
- `mime_type`, `size_bytes`, `modified_time`, `md5_checksum`.
- `content_sha256` — hash of downloaded/exported content when processed.
- `content_text` — extracted searchable text when supported and within the size limit.
- `content_state` — `stored`, `too_large`, `unsupported_content_type`, `metadata_only_by_config`, etc.
- `metadata` — extra source metadata in JSONB.
- `last_seen_at`, `synced_at`, `deleted_at` — synchronization state.

A PostgreSQL full-text GIN index is created over `content_text`.

### `drive_sync_runs`

Tracks status and counts for every run, including discovered, changed, unchanged, metadata-only, error, and soft-deleted totals.

## Local/manual command

From `apps/api`:

```bash
AIVEN_DATABASE_URL='...' \
GOOGLE_SERVICE_ACCOUNT_JSON='...' \
python scripts/sync_google_drive_to_aiven.py
```

Optional exact folder selection:

```bash
GOOGLE_DRIVE_FOLDER_ID='...' python scripts/sync_google_drive_to_aiven.py
```

Never paste production credentials into source files, commits, issues, or pull requests.
