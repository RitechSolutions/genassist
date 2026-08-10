/**
 * Best-effort extraction of a human-readable message from an API/network error.
 *
 * Handles the axios error shapes used across the app
 * (`response.data.error`, `response.data.message`, `response.data.detail` as a
 * string, a FastAPI validation array `[{ msg }]`, or a `{ "0": { msg } }` map)
 * as well as plain `Error` instances. Falls back to `fallback` when nothing
 * usable is found.
 */
export function extractErrorMessage(err: unknown, fallback: string): string {
  const e = (err ?? {}) as { response?: { data?: unknown }; message?: unknown };
  const data = e.response?.data;

  if (typeof data === "string" && data.trim()) return data;

  if (data && typeof data === "object") {
    const d = data as {
      error?: unknown;
      message?: unknown;
      detail?: unknown;
    };
    if (typeof d.error === "string" && d.error.trim()) return d.error;
    if (typeof d.message === "string" && d.message.trim()) return d.message;

    const detail = d.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
      const msg = (detail[0] as { msg?: unknown }).msg;
      if (msg) return String(msg);
    }
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const first = (detail as Record<string, { msg?: unknown }>)["0"];
      if (first?.msg) return String(first.msg);
    }
  }

  if (typeof e.message === "string" && e.message.trim()) return e.message;
  return fallback;
}
