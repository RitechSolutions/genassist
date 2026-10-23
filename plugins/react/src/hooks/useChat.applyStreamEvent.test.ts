import { describe, expect, it } from "vitest";

import { applyStreamEvent } from "./useChat";

const NOW = 1_760_000_000;

describe("applyStreamEvent", () => {
  it("labels the latest running kind and drops it when that kind ends", () => {
    let reply = applyStreamEvent(null, { type: "activity", kind: "knowledge", phase: "start" }, NOW);
    reply = applyStreamEvent(reply, { type: "activity", kind: "tool", phase: "start" }, NOW);
    reply = applyStreamEvent(reply, { type: "activity", kind: "tool", phase: "end" }, NOW);

    expect(reply.running).toEqual(["knowledge"]);
  });

  it("ignores an end for a kind that is not running", () => {
    const reply = applyStreamEvent(null, { type: "activity", kind: "knowledge", phase: "start" }, NOW);

    expect(applyStreamEvent(reply, { type: "activity", kind: "tool", phase: "end" }, NOW)).toBe(reply);
  });

  it("appends text from the same model call and restarts on a new one", () => {
    let reply = applyStreamEvent(null, { type: "delta", call_id: "run-1", text: "Hel" }, NOW);
    reply = applyStreamEvent(reply, { type: "delta", call_id: "run-1", text: "lo" }, NOW);
    expect(reply.text).toBe("Hello");

    reply = applyStreamEvent(reply, { type: "delta", call_id: "run-2", text: "Hi" }, NOW);
    expect(reply).toEqual({ text: "Hi", callId: "run-2", running: [], createTime: NOW });
  });

  it("clears scratch text when a tool starts", () => {
    let reply = applyStreamEvent(null, { type: "delta", call_id: "run-1", text: "Let me check" }, NOW);
    reply = applyStreamEvent(reply, { type: "activity", kind: "tool", phase: "start" }, NOW + 1);

    expect(reply).toEqual({ text: "", callId: null, running: ["tool"], createTime: NOW });
  });
});
