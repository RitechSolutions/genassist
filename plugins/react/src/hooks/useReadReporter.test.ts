import { describe, expect, it } from "vitest";

import { ChatMessage } from "../types";
import {
  countInboundAfter,
  firstInboundKeyAfter,
  messageIdentityKey,
} from "./useReadReporter";

/** Minimal ChatMessage builder — only the fields these helpers read. */
function msg(
  speaker: ChatMessage["speaker"],
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    create_time: 0,
    start_time: 0,
    end_time: 0,
    speaker,
    text: "",
    ...overrides,
  };
}

// A representative thread: agent greeting, a visitor line, two agent replies with a
// system banner in between. Only the "agent" messages are "inbound" for unread.
const A1 = msg("agent", { message_id: "a1", text: "hi", create_time: 100 });
const C1 = msg("customer", { message_id: "c1", text: "hey", create_time: 101 });
const A2 = msg("agent", { message_id: "a2", text: "reply1", create_time: 102 });
const S1 = msg("special", { type: "takeover", text: "Supervisor took over", create_time: 103 });
const A3 = msg("agent", { message_id: "a3", text: "reply2", create_time: 104 });
const THREAD = [A1, C1, A2, S1, A3];

describe("messageIdentityKey", () => {
  it("uses the server message_id when present", () => {
    expect(messageIdentityKey(A1)).toBe("a1");
  });

  it("falls back to a timestamp key when there is no message_id", () => {
    expect(messageIdentityKey(msg("agent", { create_time: 104 }))).toBe("t:104");
  });
});

describe("countInboundAfter", () => {
  it("counts every inbound message when nothing has been seen (null key)", () => {
    // Only the three agent messages count — the customer line and system banner don't.
    expect(countInboundAfter(THREAD, null)).toBe(3);
  });

  it("counts only inbound messages strictly after the seen marker", () => {
    expect(countInboundAfter(THREAD, "a1")).toBe(2); // a2, a3
    expect(countInboundAfter(THREAD, "a2")).toBe(1); // a3
  });

  it("returns zero once the newest inbound message has been seen", () => {
    expect(countInboundAfter(THREAD, "a3")).toBe(0);
  });

  it("treats an unknown key as 'nothing seen' (counts all inbound)", () => {
    expect(countInboundAfter(THREAD, "does-not-exist")).toBe(3);
  });

  it("never counts customer or special messages as unread", () => {
    const noAgents = [C1, S1, msg("customer", { message_id: "c2", create_time: 105 })];
    expect(countInboundAfter(noAgents, null)).toBe(0);
  });
});

describe("firstInboundKeyAfter (New messages divider anchor)", () => {
  it("returns the first inbound message after the divider marker", () => {
    expect(firstInboundKeyAfter(THREAD, "a1")).toBe("a2");
    expect(firstInboundKeyAfter(THREAD, "a2")).toBe("a3");
  });

  it("returns the first inbound message overall when the marker is null", () => {
    expect(firstInboundKeyAfter(THREAD, null)).toBe("a1");
  });

  it("returns null when there is no inbound message after the marker", () => {
    // The divider is suppressed when the caller is already caught up.
    expect(firstInboundKeyAfter(THREAD, "a3")).toBeNull();
  });

  it("skips intervening customer/special messages to the next agent reply", () => {
    // After a2 the next entry is a 'special' takeover banner; the divider still
    // anchors to the following agent reply (a3), not the banner.
    expect(firstInboundKeyAfter(THREAD, "a2")).toBe("a3");
  });
});
