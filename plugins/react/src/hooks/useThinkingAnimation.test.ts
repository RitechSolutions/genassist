import { describe, expect, it } from "vitest";

import type { ActivityKind } from "../types";
import { IDLE_PACE, paceLabel } from "./useThinkingAnimation";

type Span = [from: number, to: number, kind: ActivityKind];

function play(steps: Span[], until: number): string[] {
  const kindAt = (t: number) => steps.find(([from, to]) => t >= from && t < to)?.[2];
  let pace = paceLabel(IDLE_PACE, kindAt(0), 0);
  const changes = [`0 ${pace.shown ?? "thinking"}`];
  for (let t = 10; t <= until; t += 10) {
    const next = paceLabel(pace, kindAt(t), t);
    if (next.shown !== pace.shown) changes.push(`${t} ${next.shown ?? "thinking"}`);
    pace = next;
  }
  return changes;
}

describe("paceLabel", () => {
  it("keeps a quick step's label up instead of flipping back to the thinking phrase", () => {
    expect(play([[1060, 1090, "tool"], [2130, 2170, "tool"]], 3170)).toEqual(["0 thinking", "1060 tool"]);
  });

  it("holds the thinking phrase long enough to read before a step right after sending", () => {
    expect(play([[50, 80, "tool"]], 2000)).toEqual(["0 thinking", "800 tool"]);
  });

  it("holds each step's label long enough to read before the next", () => {
    expect(play([[1000, 1100, "knowledge"], [1200, 1300, "tool"]], 3000)).toEqual([
      "0 thinking",
      "1000 knowledge",
      "1800 tool",
    ]);
  });
});
