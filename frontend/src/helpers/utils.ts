import { getApiUrlString } from "@/config/api";

// Single source of truth for `cn` lives in @/lib/utils; re-exported here so the
// existing `@/helpers/utils` import path keeps working.
export { cn } from "@/lib/utils";

export function formatDate(date: string | Date): string {
  const d = new Date(date);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/**
 * Locale date + time, with an em-dash fallback for empty/invalid values.
 * (e.g. "2/17/2026, 3:04:05 PM")
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

/**
 * Short month/day label for chart axes from a date-only string.
 * (e.g. "Feb 17")
 */
export function formatChartDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function getTimeFromDatetime(datetimeString: string): string {
  const date = new Date(datetimeString);
  const hours = date.getHours();
  const minutes = date.getMinutes();
  const seconds = date.getSeconds();

  return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

export const formatFeedbackDate = (timestamp: string) => {
  const date = new Date(timestamp);
  const month = date.toLocaleDateString('en-US', { month: 'long' });
  const day = date.getDate();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${month} ${day}, ${hours}:${minutes}`;
};

export function tryParse(value: any) {
  try {
    const first = JSON.parse(value);
    if (typeof first === "string") {
      try {
        return JSON.parse(first);
      } catch {
        return first;
      }
    }
    return first;
  } catch {
    return value;
  }
}

export function maskInput(inputVal: string, maxLength: number = 36): string {
  let maskSize = inputVal.length;  // default mask size
  if (inputVal.length > maxLength) {
    maskSize = maxLength;
  }
  return "*".repeat(maskSize);
}

export function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

export function downloadFile(fileUrl: string, filename: string) {
  try {
    const link = document.createElement("a");
    link.href = fileUrl;
    link.download = filename;
    link.click();
  } catch (error) {
    console.error("Failed to download file:", error);
    throw error;
  }
}

export type FileManagerFileUrlKind = "source" | "download";

export function getFileDownloadUrl(
  fileId: string,
  baseUrl: string,
  tenantId: string,
  kind: FileManagerFileUrlKind = "source"
): string {
  const segment = kind === "download" ? "download" : "source";
  let url = new URL(`file-manager/files/${fileId}/${segment}`, baseUrl).toString();

  if (tenantId) {
    url = url.includes("?") ? `${url}&X-Tenant-Id=${tenantId}` : `${url}?X-Tenant-Id=${tenantId}`;
  }

  return url;
}