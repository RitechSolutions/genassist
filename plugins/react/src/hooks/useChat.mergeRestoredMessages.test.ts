import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../types";
import { mergeRestoredMessages } from "./useChat";

const message = (overrides: Partial<ChatMessage>): ChatMessage => ({
  create_time: 1,
  start_time: 0,
  end_time: 0.01,
  speaker: "customer",
  text: "",
  ...overrides,
});

describe("mergeRestoredMessages", () => {
  it("keeps a message sent while the saved conversation was still being checked", () => {
    const stored = [message({ message_id: "m1", text: "first question" })];
    const sentDuringCheck = message({ client_id: "c_2", text: "second question" });

    expect(mergeRestoredMessages(stored, [sentDuringCheck])).toEqual([...stored, sentDuringCheck]);
  });

  it("does not repeat messages the stored history already has", () => {
    const stored = [
      message({ message_id: "m1", text: "first question" }),
      message({ client_id: "c_2", text: "second question" }),
    ];
    const shown = [message({ client_id: "c_2", text: "second question" }), message({ message_id: "m1" })];

    expect(mergeRestoredMessages(stored, shown)).toEqual(stored);
  });

  it("returns the stored history unchanged when nothing else is shown", () => {
    const stored = [message({ message_id: "m1" })];
    expect(mergeRestoredMessages(stored, [])).toEqual(stored);
  });
});
