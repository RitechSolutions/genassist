import { describe, expect, it } from "vitest";
import { classifySendFailure, markUnreachable } from "./conversationErrors";

const httpError = (status: number, data?: unknown) =>
  Object.assign(new Error(`status ${status}`), { response: { status, data } });

describe("classifySendFailure", () => {
  it("treats a failed reply from a reachable server as reply_failed, not an outage", () => {
    // The SSE error frame of a failed turn: HTTP 200 stream carrying error_code 500.
    expect(classifySendFailure(httpError(500, { error: "An internal server error occurred." }))).toBe("reply_failed");
    expect(classifySendFailure(new Error("Stream ended before done"))).toBe("reply_failed");
    expect(classifySendFailure(httpError(400, { error_key: "SOMETHING" }))).toBe("reply_failed");
  });

  it("treats a bug in the widget's own code as reply_failed", () => {
    expect(classifySendFailure(new TypeError("Cannot read properties of undefined"))).toBe("reply_failed");
  });

  it("treats a request that never got a response as unreachable", () => {
    expect(classifySendFailure(markUnreachable(new TypeError("Failed to fetch")))).toBe("unreachable");
    expect(classifySendFailure({ isAxiosError: true, request: {}, code: "ERR_NETWORK" })).toBe("unreachable");
  });

  it("treats gateway errors as unreachable", () => {
    for (const status of [502, 503, 504]) expect(classifySendFailure(httpError(status))).toBe("unreachable");
  });

  it("recognises a switched-off agent by its error key", () => {
    expect(classifySendFailure(httpError(403, { error_key: "AGENT_INACTIVE" }))).toBe("agent_inactive");
  });
});

import type { ChatMessage } from "../types";
import { canRetrySend, markSendFailed, withoutFailedSend } from "./sendFailure";

const msg = (over: Partial<ChatMessage>): ChatMessage => ({
  create_time: 1,
  start_time: 0,
  end_time: 0.01,
  speaker: "customer",
  text: "hi",
  ...over,
});

describe("failed sends", () => {
  const sent = msg({ client_id: "c1", text: "photo please" });
  const other = msg({ client_id: "c0", text: "earlier" });
  const notice = msg({ speaker: "special", text: "Something went wrong", notice: "reply_failed", notice_for: "c1" });

  it("marks only the failed bubble and keeps what Retry resends", () => {
    const payload = { text: "photo please", attachments: [{ name: "a.png", type: "image/png", size: 1, url: "u" }] };
    const [first, second] = markSendFailed([other, sent], "c1", payload);
    expect(first).toBe(other);
    expect(second).toMatchObject({ send_failed: true, retry_payload: payload });
  });

  it("leaves the list alone when the failed message is unknown", () => {
    const list = [other, sent];
    expect(markSendFailed(list, undefined)).toBe(list);
  });

  it("removes the failed bubble and its notice before a retry, keeping everything else", () => {
    expect(withoutFailedSend([other, { ...sent, send_failed: true }, notice], "c1")).toEqual([other]);
  });

  it("offers Retry for a failed text message, and for a voice message only while its recording is kept", () => {
    const text = msg({ client_id: "t", send_failed: true, retry_payload: { text: "x" } });
    const voice = msg({ client_id: "v", send_failed: true, type: "audio" });
    expect(canRetrySend(text, () => false)).toBe(true);
    expect(canRetrySend(voice, (id) => id === "v")).toBe(true);
    expect(canRetrySend(voice, () => false)).toBe(false);
    expect(canRetrySend(msg({ client_id: "ok" }), () => true)).toBe(false);
  });
});

import { uploadFailureToast } from "./sendFailure";

describe("uploadFailureToast", () => {
  const t = (_key: string, fallback?: string) => fallback ?? "";

  it("says nothing when every upload worked", () => {
    expect(uploadFailureToast([], t)).toBeNull();
  });

  it("says 'not supported' only when the server refused the file type", () => {
    expect(uploadFailureToast([{ name: "a.exe", rejected: true }], t)).toBe("This file type is not supported.");
  });

  it("names the files whose upload failed, rather than blaming their type", () => {
    expect(uploadFailureToast([{ name: "photo.jpg", rejected: false }], t)).toBe(
      "Couldn't upload photo.jpg. Please try again.",
    );
    expect(
      uploadFailureToast(
        [
          { name: "a.exe", rejected: true },
          { name: "photo.jpg", rejected: false },
          { name: "scan.pdf", rejected: false },
        ],
        t,
      ),
    ).toBe("Couldn't upload photo.jpg, scan.pdf. Please try again.");
  });
});
