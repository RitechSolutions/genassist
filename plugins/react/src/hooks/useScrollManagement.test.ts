import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import { isAtBottom, pinTop, questionKey, spacerHeight } from "./useScrollManagement";

const VIEWPORT = 700;

describe("pinTop", () => {
  it("pins a short question near the top with a sliver of the previous message above", () => {
    expect(pinTop(2000, 2060, VIEWPORT)).toBe(1976);
  });

  it("puts a tall question's bottom at mid-screen so the reply still shows", () => {
    expect(pinTop(2000, 2600, VIEWPORT)).toBe(2250);
  });

  it("never scrolls above the start of the chat", () => {
    expect(pinTop(10, 70, VIEWPORT)).toBe(0);
  });
});

describe("spacerHeight", () => {
  it("reserves the room a short reply leaves so the question can stay pinned", () => {
    expect(spacerHeight(1976, VIEWPORT, 2200)).toBe(476);
  });

  it("shrinks as the reply grows and is gone once the reply fills the screen", () => {
    expect(spacerHeight(1976, VIEWPORT, 2500)).toBe(176);
    expect(spacerHeight(1976, VIEWPORT, 2900)).toBe(0);
  });
});

describe("isAtBottom", () => {
  it("counts a visitor beside a short reply's spacer as at the bottom", () => {
    expect(isAtBottom({ scrollHeight: 2676, scrollTop: 1976, clientHeight: VIEWPORT })).toBe(true);
  });

  it("does not count a reader left at the top of a reply that outgrew the screen", () => {
    expect(isAtBottom({ scrollHeight: 2900, scrollTop: 1976, clientHeight: VIEWPORT })).toBe(false);
  });
});

describe("questionKey", () => {
  it("keeps the same key when the server adds an id to the sent message", () => {
    const sent: ChatMessage = { create_time: 1, start_time: 0, end_time: 0.01, speaker: "customer", text: "hi", client_id: "c_1" };
    expect(questionKey({ ...sent, message_id: "m_9" })).toBe("c_1");
  });
});
