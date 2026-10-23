import { formatBytes } from "@/helpers/formatters";

/**
 * The message to show when a file is over the upload limit, or null when it
 * may be uploaded. A file exactly at the limit is allowed, as on the server.
 */
export const uploadSizeError = (
  file: { name: string; size: number },
  maxBytes?: number,
  maxLabel?: string,
): string | null => {
  if (!maxBytes || file.size <= maxBytes) return null;
  return (
    `${file.name} is ${formatBytes(file.size)}, which is larger than the ` +
    `maximum upload size of ${maxLabel || formatBytes(maxBytes)}.`
  );
};
