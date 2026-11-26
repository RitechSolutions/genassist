import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import { isAtBottom, pinTop, questionKey, spacerHeight, heldTop } from "./useScrollManagement";

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

  it("keeps a larger gap when a header floats over the list", () => {
    expect(pinTop(2000, 2060, VIEWPORT, 96)).toBe(1904);
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

describe('heldTop', () => {
  it('makes room for the full pin while the reply is awaited', () => {
    expect(heldTop(82, 0, true)).toBe(82);
  });

  it('caps the pin at the current scroll once the reply is in, so a short chat cannot scroll into empty space', () => {
    // "Hi" → short reply: the view never moved, so the spacer must not add 82px to scroll into.
    expect(heldTop(82, 0, false)).toBe(0);
    // Pinned and read in place: keep exactly the current view.
    expect(heldTop(82, 82, false)).toBe(82);
    // Scrolled past the pin (a long reply): the pin itself is the most room ever needed.
    expect(heldTop(82, 400, false)).toBe(82);
  });
});
