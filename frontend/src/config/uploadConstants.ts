/** Axios: 0 = no client-side timeout (large uploads can exceed any fixed window). */
export const API_UPLOAD_TIMEOUT_MS = 0;

/** Use chunked session upload when a single file exceeds this size (bytes). */
export const FILES_UPLOAD_SESSION_THRESHOLD_BYTES =
  Number(import.meta.env.VITE_FILES_UPLOAD_SESSION_THRESHOLD_BYTES) > 0
    ? Number(import.meta.env.VITE_FILES_UPLOAD_SESSION_THRESHOLD_BYTES)
    : 15 * 1024 * 1024;

/** Must stay <= backend FILES_UPLOAD_MAX_CHUNK_BYTES (default 20 MiB). */
export const FILES_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024;

// Backward-compatible exports
export const KNOWLEDGE_UPLOAD_SESSION_THRESHOLD_BYTES =
  FILES_UPLOAD_SESSION_THRESHOLD_BYTES;
export const KNOWLEDGE_UPLOAD_CHUNK_SIZE = FILES_UPLOAD_CHUNK_SIZE;
