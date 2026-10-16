import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import { latestQuestionKey, pinTop, spacerHeight } from "./useScrollManagement";

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

describe("latestQuestionKey", () => {
  const message = (speaker: ChatMessage["speaker"], extra: Partial<ChatMessage> = {}): ChatMessage => ({
    create_time: 1,
    start_time: 0,
    end_time: 0.01,
    speaker,
    text: "hi",
    ...extra,
  });

  it("keeps the same key when the server adds an id to the sent message", () => {
    const sent = message("customer", { client_id: "c_1" });
    expect(latestQuestionKey([sent, message("agent")])).toBe(
      latestQuestionKey([{ ...sent, message_id: "m_9" }, message("agent")]),
    );
  });

  it("changes when the visitor sends again", () => {
    const first = [message("customer", { client_id: "c_1" }), message("agent")];
    expect(latestQuestionKey([...first, message("customer", { client_id: "c_2" })])).not.toBe(latestQuestionKey(first));
  });
});
