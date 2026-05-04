# Direct Browser → S3 Presigned PUT Upload

A new opt-in upload path for the file manager. Instead of streaming bytes
through the API, the client obtains a presigned PUT URL, uploads the file body
directly to S3, then notifies the server to finalize. The legacy
`/file-manager/upload` and `/file-manager/upload-session/*` endpoints are not
modified and remain the default.

## Activation

Two conditions must hold:

1. File manager is enabled (`FILE_MANAGER_ENABLED=true`) and the active provider is `s3`
   (via `FILE_MANAGER_PROVIDER=s3` and/or app settings `file_manager_provider="s3"`).
2. `FILES_DIRECT_S3_UPLOAD_ENABLED=true` (default `false`).

Optionally tune the URL lifetime via
`FILES_DIRECT_S3_PRESIGN_EXPIRES_SECONDS` (default `600`).

When the flag is off the new endpoints return `501` and the frontend falls
back to the existing chunked-session upload automatically.

### Frontend capability detection

The backend surfaces whether the capability is currently active via:

```http
GET /api/file-manager/settings
```

The response includes `values.direct_s3_upload_enabled` (boolean). This value is
**derived** from server config + active provider + app-settings activation; it is
not persisted as a user-editable setting.

## API

### 1. Presign

```http
POST /api/file-manager/upload-session/presign
Content-Type: application/json

{
  "original_filename": "report.pdf",
  "expected_size": 1048576,
  "content_type": "application/pdf"
}
```

Minimal request (no size / content-type constraints):

```http
POST /api/file-manager/upload-session/presign
Content-Type: application/json

{
  "original_filename": "report.pdf"
}
```

Response:

```json
{
  "session_id": "…",
  "file_id": "…",
  "object_key": "uploads/…uuid….pdf",
  "presigned_url": "https://…s3…?X-Amz-…",
  "method": "PUT",
  "required_headers": { "Content-Type": "application/pdf" },
  "expires_in": 600
}
```

A pending row in `files` is created upfront so `file_id` is stable across the
whole flow. A `files_upload_sessions` row is also persisted with
`status=awaiting_client_upload` and `upload_mode=direct_s3`.

Notes:

- `expected_size` is optional. If provided, the server validates it against
  `FILES_MAX_UPLOAD_BYTES` up-front, and validates the final uploaded size on
  finalize via S3 `HeadObject`.
- `content_type` is optional. If provided, it becomes part of the signature and
  the client MUST send the same `Content-Type` on the PUT. If omitted,
  `required_headers` will be empty and no `Content-Type` constraint is enforced
  by the signature.
- If the direct flow is disabled or the active provider is not `s3`, the presign
  endpoint returns `501` (feature-gated; clients should fall back to the legacy
  upload endpoints).

### 2. Direct PUT to S3

```bash
curl -X PUT "$PRESIGNED_URL" \
  -H "Content-Type: application/pdf" \
  --upload-file ./report.pdf
```

The `Content-Type` header MUST match the value the server signed with, or S3
returns `SignatureDoesNotMatch`.

### 3. Finalize

```http
POST /api/file-manager/upload-session/{session_id}/finalize
Content-Type: application/json

{ "success": true, "etag": "…optional…" }
```

The server then performs `HeadObject` on the key, validates the actual size
against `expected_size` (when provided) and the global cap
(`FILES_MAX_UPLOAD_BYTES`), updates the placeholder `files` row in place, and
returns an
`UploadFileResponse`-shaped payload identical to the one produced by the
legacy `/complete` endpoint.

On the failure path the client should send:

```json
{ "success": false, "error_message": "S3 PUT failed: 403 Forbidden" }
```

The server then best-effort deletes the partial S3 object and soft-deletes the
placeholder `files` row, marks the session `failed`, and returns `400`.

Idempotency: if a previous finalize succeeded, re-sending `{ "success": true }`
returns the already-computed result without modifying the file again.

## Required S3 bucket CORS

The browser PUT requires explicit CORS on the bucket, including exposing the
`ETag` response header so the client can record it.

Example (JSON CORS configuration):

```json
[
  {
    "AllowedOrigins": ["https://app.example.com"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

For the GET redirect path used by `download_file` / `get_file_source`, you may
also want a separate CORS rule allowing `GET` from the same origins.

## Security caveats

- A presigned PUT URL grants temporary upload authority for a single key.
  Keep `FILES_DIRECT_S3_PRESIGN_EXPIRES_SECONDS` short (default 10 min).
- Presigned PUT cannot strictly enforce an upper-bound size pre-upload. The
  server enforces the limit on finalize via `HeadObject` and rejects oversize
  uploads, deleting the object.
- The signed `Content-Type` constrains what the client can declare, but the
  client can still send arbitrary bytes. Treat `Content-Type` as advisory and
  re-derive trust on download where needed.
- Object keys are server-allocated UUIDs under `uploads/`; the client never
  picks the key.

## Cleanup task

`app.tasks.file_upload_session_tasks.cleanup_stale_direct_upload_sessions`
runs every 5 minutes by default (toggle via
`CELERY_ENABLE_CLEANUP_STALE_DIRECT_UPLOADS_TASK`). It marks
`awaiting_client_upload` rows older than
`2 * FILES_DIRECT_S3_PRESIGN_EXPIRES_SECONDS` as `failed`, best-effort deletes
their S3 object and soft-deletes the placeholder `files` row.

## Rollback

- Set `FILES_DIRECT_S3_UPLOAD_ENABLED=false`.
- Restart the API. The frontend will see `values.direct_s3_upload_enabled=false`
  on `/api/file-manager/settings` and resume using the existing `/upload` and
  `/upload-session` flows.
- No data migration is needed: existing files in S3 remain valid because the
  `files` table schema and the `UploadFileResponse` shape are unchanged.

## Phase 2 (sketch)

For files >5 GB or resumable uploads, switch to S3 multipart presigning:

1. `POST /upload-session/presign` accepts a new `mode: "multipart"` flag and
   returns `multipart_upload_id`, `object_key`, and per-part presigned URLs
   (`upload_part`).
2. The client uploads each part directly, recording `(part_number, etag)`.
3. `POST /upload-session/{session_id}/finalize` carries the parts list; the
   server calls `complete_multipart_upload` then runs the same HEAD/finalize
   logic as today.
4. The existing `multipart_upload_id`, `object_key`, `parts_json` columns
   added in migration `00074` already match this shape.
