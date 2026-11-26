import { describe, expect, it } from "vitest";

import {
  applyLiveStreamEvent,
  describeWork,
  newLiveTurn,
  settleLiveTurn,
  isThoughtText,
  stripThoughtMarker,
} from "@/views/AIAgents/Workflows/utils/assistantDraft";

describe("applyLiveStreamEvent", () => {
  it("lists narrated steps in order and marks them done with their outcome", () => {
    let turn = newLiveTurn(1000);
    turn = applyLiveStreamEvent(turn, { type: "step", id: "a", kind: "read", text: "Reading the workflow", phase: "start" });
    turn = applyLiveStreamEvent(turn, { type: "step", id: "a", kind: "read", text: "Reading the workflow", phase: "end", detail: "" });
    turn = applyLiveStreamEvent(turn, { type: "step", id: "b", kind: "edit", text: "Adding 3 steps", phase: "start" });
    expect(turn.steps).toEqual([
      { id: "a", kind: "read", text: "Reading the workflow", done: true, detail: undefined },
      { id: "b", kind: "edit", text: "Adding 3 steps", done: false },
    ]);
    turn = applyLiveStreamEvent(turn, { type: "step", id: "b", kind: "edit", text: "Adding 3 steps", phase: "end", detail: "3 of 3 applied" });
    expect(turn.steps[1]).toEqual({ id: "b", kind: "edit", text: "Adding 3 steps", done: true, detail: "3 of 3 applied" });
  });

  it("turns text written before a step into a thought, and keeps the final text as the reply", () => {
    let turn = newLiveTurn(1000);
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c1", text: "I'll add a classifier " });
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c1", text: "first." });
    expect(turn.text).toBe("I'll add a classifier first.");
    turn = applyLiveStreamEvent(turn, { type: "step", id: "s", kind: "edit", text: "Adding “Classifier”", phase: "start" });
    expect(turn.text).toBe("");
    expect(turn.steps.map((s) => [s.kind, s.text])).toEqual([
      ["thought", "I'll add a classifier first."],
      ["edit", "Adding “Classifier”"],
    ]);
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c2", text: "Done. " });
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c2", text: "The workflow classifies messages." });
    expect(turn.text).toBe("Done. The workflow classifies messages.");
    expect(turn.steps).toHaveLength(2);
  });

  it("folds text into a thought when a new model call starts writing without a step between", () => {
    let turn = newLiveTurn(1000);
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c1", text: "Let me think." });
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c2", text: "Here is the answer." });
    expect(turn.steps).toEqual([{ id: "thought-0", kind: "thought", text: "Let me think.", done: true }]);
    expect(turn.text).toBe("Here is the answer.");
  });

  it("ignores activity frames and a repeated start refreshes a step's text", () => {
    let turn = newLiveTurn(1000);
    turn = applyLiveStreamEvent(turn, { type: "activity", kind: "tool", phase: "start" });
    expect(turn.steps).toEqual([]);
    turn = applyLiveStreamEvent(turn, { type: "step", id: "x", kind: "read", text: "Reading a step", phase: "start" });
    turn = applyLiveStreamEvent(turn, { type: "step", id: "x", kind: "read", text: "Reading “Router”", phase: "start" });
    expect(turn.steps).toEqual([{ id: "x", kind: "read", text: "Reading “Router”", done: false }]);
  });
});

describe("settleLiveTurn / describeWork", () => {
  it("closes open steps and measures the work", () => {
    let turn = newLiveTurn(1000);
    turn = applyLiveStreamEvent(turn, { type: "step", id: "x", kind: "test", text: "Testing", phase: "start" });
    const settled = settleLiveTurn(turn, 13_400);
    expect(settled.steps).toEqual([{ id: "x", kind: "test", text: "Testing", done: true }]);
    expect(settled.workedMs).toBe(12_400);
    expect(describeWork(settled.steps, settled.workedMs)).toBe("Worked for 12s · 1 step");
    expect(describeWork([], 5000)).toBeNull();
    expect(describeWork(settled.steps, 75_000)).toBe("Worked for 1m 15s · 1 step");
    const change = { op: "add_node" as const, summary: "Added X", node_ids: ["x"] };
    expect(describeWork(settled.steps, 3000, [change, change])).toBe("Worked for 3s · 1 step · 2 changes");
    expect(describeWork(undefined, undefined, [change])).toBe("1 change");
  });

  it("keeps no steps for a turn that had none", () => {
    expect(settleLiveTurn(newLiveTurn(0), 500)).toEqual({ steps: undefined, workedMs: 500 });
  });
});


describe("thought marker", () => {
  it("tells a working note from reply text by its leading sign", () => {
    expect(isThoughtText("» Checking the calendar steps")).toBe(true);
    expect(isThoughtText("  »Checking")).toBe(true);
    expect(isThoughtText("I built the agent.")).toBe(false);
    expect(stripThoughtMarker("» Checking the calendar steps")).toBe("Checking the calendar steps");
    expect(stripThoughtMarker("I built the agent.")).toBe("I built the agent.");
  });

  it("folds a marked sentence into a thought without the sign", () => {
    let turn = newLiveTurn(1000);
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c1", text: "» Looking at the " });
    turn = applyLiveStreamEvent(turn, { type: "delta", call_id: "c1", text: "calendar steps." });
    turn = applyLiveStreamEvent(turn, { type: "step", id: "s1", kind: "lookup", text: "Looking up X", phase: "start" });
    expect(turn.steps.map((s) => [s.kind, s.text])).toEqual([
      ["thought", "Looking at the calendar steps."],
      ["lookup", "Looking up X"],
    ]);
    expect(turn.text).toBe("");
  });
});
