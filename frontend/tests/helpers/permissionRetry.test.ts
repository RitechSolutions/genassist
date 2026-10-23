import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  PermissionRequestGate,
  type PermissionFetchResult,
  getPermissionRetryDelayMs,
} from "@/helpers/permissionRetry";

describe("getPermissionRetryDelayMs", () => {
  it("asks again straight away the first time", () => {
    expect(getPermissionRetryDelayMs(0)).toBe(0);
  });

  it("waits longer before each further attempt", () => {
    expect(getPermissionRetryDelayMs(1)).toBe(2_000);
    expect(getPermissionRetryDelayMs(2)).toBe(5_000);
    expect(getPermissionRetryDelayMs(3)).toBe(10_000);
  });

  it("stops once all attempts are used, so a failing server is not polled forever", () => {
    expect(getPermissionRetryDelayMs(4)).toBeNull();
  });
});

describe("PermissionRequestGate", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const gateAnswering = (result: PermissionFetchResult) => {
    const fetchPermissions = vi.fn(async () => result);
    return { fetchPermissions, gate: new PermissionRequestGate(fetchPermissions) };
  };

  it("ignores any number of asks from page guards while one retry is already waiting", async () => {
    const { fetchPermissions, gate } = gateAnswering("failed");
    await gate.fetchNow();

    for (let i = 0; i < 50; i++) gate.request();
    await vi.advanceTimersByTimeAsync(2_000);

    expect(fetchPermissions).toHaveBeenCalledTimes(2);
  });

  it("waits 2, 5 and 10 seconds between failed attempts and then gives up", async () => {
    const { fetchPermissions, gate } = gateAnswering("failed");
    await gate.fetchNow();

    for (const waitMs of [2_000, 5_000, 10_000]) {
      const callsBefore = fetchPermissions.mock.calls.length;
      gate.request();
      await vi.advanceTimersByTimeAsync(waitMs - 1);
      expect(fetchPermissions).toHaveBeenCalledTimes(callsBefore);
      await vi.advanceTimersByTimeAsync(1);
      expect(fetchPermissions).toHaveBeenCalledTimes(callsBefore + 1);
    }

    gate.request();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchPermissions).toHaveBeenCalledTimes(4);
  });

  it("stops asking once the server has answered", async () => {
    const { fetchPermissions, gate } = gateAnswering("answered");
    await gate.fetchNow();

    gate.request();
    await vi.advanceTimersByTimeAsync(60_000);

    expect(fetchPermissions).toHaveBeenCalledTimes(1);
  });

  it("asks straight away after a skipped load, since a down server did not use up a retry", async () => {
    const { fetchPermissions, gate } = gateAnswering("skipped");
    await gate.fetchNow();

    gate.request();
    await vi.advanceTimersByTimeAsync(0);

    expect(fetchPermissions).toHaveBeenCalledTimes(2);
  });

  it("runs only one fetch at a time", async () => {
    let finish: (result: PermissionFetchResult) => void = () => {};
    const fetchPermissions = vi.fn(() => new Promise<PermissionFetchResult>((resolve) => { finish = resolve; }));
    const gate = new PermissionRequestGate(fetchPermissions);

    const first = gate.fetchNow();
    void gate.fetchNow();
    gate.request();
    finish("answered");
    await first;

    expect(fetchPermissions).toHaveBeenCalledTimes(1);
  });
});
