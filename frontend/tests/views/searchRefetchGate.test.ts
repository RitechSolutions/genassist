import { describe, expect, it, vi } from "vitest";
import {
  SEARCH_REFETCH_INTERVAL_MS,
  createSearchRefetchGate,
} from "@/views/Transcripts/helpers/searchRefetchGate";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function fakeClock(start = 0) {
  let time = start;
  return { now: () => time, set: (value: number) => (time = value) };
}

const flush = () => new Promise((done) => setTimeout(done, 0));

describe("createSearchRefetchGate", () => {
  it("starts the first refetch", async () => {
    const gate = createSearchRefetchGate({ clock: fakeClock().now });
    const refetch = vi.fn(() => Promise.resolve());

    expect(gate.tryStart(refetch)).toBe(true);
    await flush();
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("skips while a refetch is still running, even after the interval", async () => {
    const clock = fakeClock();
    const gate = createSearchRefetchGate({ clock: clock.now });
    const running = deferred();
    const refetch = vi.fn(() => running.promise);

    gate.tryStart(refetch);
    clock.set(SEARCH_REFETCH_INTERVAL_MS + 1);

    expect(gate.tryStart(refetch)).toBe(false);
    await flush();
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("waits the interval from when the last refetch finished", async () => {
    const clock = fakeClock();
    const gate = createSearchRefetchGate({ clock: clock.now });
    const running = deferred();
    const refetch = vi.fn(() => running.promise);

    gate.tryStart(refetch);
    clock.set(40_000);
    running.resolve();
    await flush();

    clock.set(40_000 + SEARCH_REFETCH_INTERVAL_MS - 1);
    expect(gate.tryStart(refetch)).toBe(false);
    clock.set(40_000 + SEARCH_REFETCH_INTERVAL_MS);
    expect(gate.tryStart(refetch)).toBe(true);
  });

  it("waits the interval after a search the page started itself", () => {
    const clock = fakeClock(5_000);
    const gate = createSearchRefetchGate({ clock: clock.now });
    const refetch = vi.fn(() => Promise.resolve());

    gate.markStarted();

    expect(gate.tryStart(refetch)).toBe(false);
    clock.set(5_000 + SEARCH_REFETCH_INTERVAL_MS);
    expect(gate.tryStart(refetch)).toBe(true);
  });

  it("opens again after a refetch that throws", async () => {
    const clock = fakeClock();
    const gate = createSearchRefetchGate({ clock: clock.now });
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const throwing = vi.fn((): Promise<unknown> => {
      throw new Error("boom");
    });

    gate.tryStart(throwing);
    await flush();
    clock.set(SEARCH_REFETCH_INTERVAL_MS);

    expect(gate.tryStart(vi.fn(() => Promise.resolve()))).toBe(true);
    expect(consoleError).toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
