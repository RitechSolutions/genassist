import { describe, expect, it } from "vitest";

import {
  HEARTBEAT_INITIAL_INTERVAL_MS,
  HEARTBEAT_INTERVAL_STEP_MS,
  HEARTBEAT_MAX_INTERVAL_MS,
  getNextHeartbeatInterval,
} from "./useChat";

describe("getNextHeartbeatInterval", () => {
  it("steps up from the initial interval when no current interval is tracked yet", () => {
    expect(getNextHeartbeatInterval(undefined)).toBe(
      HEARTBEAT_INITIAL_INTERVAL_MS + HEARTBEAT_INTERVAL_STEP_MS,
    );
  });

  it("ramps by the fixed step on each successful poll instead of staying flat", () => {
    // Regression test: a prior change hardcoded this to always return
    // HEARTBEAT_INTERVAL_STEP_MS, which kept idle tabs polling (and logging)
    // every 5s forever instead of backing off toward the 30s cap.
    let interval: number | undefined = undefined;
    const observed: number[] = [];
    for (let i = 0; i < 6; i++) {
      interval = getNextHeartbeatInterval(interval);
      observed.push(interval);
    }
    expect(observed).toEqual([7000, 12000, 17000, 22000, 27000, 30000]);
  });

  it("caps at HEARTBEAT_MAX_INTERVAL_MS and never exceeds it on further polls", () => {
    expect(getNextHeartbeatInterval(HEARTBEAT_MAX_INTERVAL_MS)).toBe(
      HEARTBEAT_MAX_INTERVAL_MS,
    );
    expect(getNextHeartbeatInterval(HEARTBEAT_MAX_INTERVAL_MS + 1000)).toBe(
      HEARTBEAT_MAX_INTERVAL_MS,
    );
  });
});
