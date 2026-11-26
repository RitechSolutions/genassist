import type { ChatMessage } from "../types";

/** A failed visitor message, marked "Not delivered" with what Retry resends (text messages). */
export function markSendFailed(
  messages: ChatMessage[],
  clientId: string | undefined,
  retryPayload?: ChatMessage["retry_payload"],
): ChatMessage[] {
  if (!clientId) return messages;
  return messages.map((m) =>
    m.client_id === clientId
      ? { ...m, send_failed: true, ...(retryPayload ? { retry_payload: retryPayload } : {}) }
      : m,
  );
}

/** The conversation without a failed message and the notice that reported it (before a retry resends it). */
export function withoutFailedSend(messages: ChatMessage[], clientId: string): ChatMessage[] {
  return messages.filter((m) => m.client_id !== clientId && m.notice_for !== clientId);
}

/** Whether Retry can resend this failed message: text carries its payload; a voice
 *  recording only lives in memory, so `hasRecording` says whether it is still there. */
export function canRetrySend(message: ChatMessage, hasRecording: (clientId: string) => boolean): boolean {
  if (!message.send_failed || !message.client_id) return false;
  return Boolean(message.retry_payload) || hasRecording(message.client_id);
}

/**
 * The toast for files that did not upload. "Not supported" only when the server refused
 * every one of them for their type; otherwise the upload itself failed, so say that and
 * name the files, since they can be retried.
 */
export function uploadFailureToast(
  failures: Array<{ name: string; rejected: boolean }>,
  t: (key: string, fallback?: string) => string,
): string | null {
  if (failures.length === 0) return null;
  if (failures.every((f) => f.rejected)) {
    return t("fileUpload.fileTypeNotSupported", "This file type is not supported.");
  }
  const names = failures.filter((f) => !f.rejected).map((f) => f.name).join(", ");
  return t("fileUpload.uploadFailed", "Couldn't upload {name}. Please try again.").replace("{name}", names);
}
