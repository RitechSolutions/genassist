import { describe, expect, it, vi } from "vitest";

import { createSingleFlight } from "./singleFlight";

describe("createSingleFlight", () => {
  it("lets callers that overlap share one run", async () => {
    const runOnce = createSingleFlight<string>();
    let finish: (value: string) => void = () => {};
    const task = vi.fn(() => new Promise<string>((resolve) => { finish = resolve; }));

    const first = runOnce(task);
    const second = runOnce(task);
    finish("done");

    await expect(Promise.all([first, second])).resolves.toEqual(["done", "done"]);
    expect(task).toHaveBeenCalledTimes(1);
  });

  it("starts a new run once the previous one has finished", async () => {
    const runOnce = createSingleFlight<number>();
    const task = vi.fn(async () => task.mock.calls.length);

    await runOnce(task);
    await runOnce(task);

    expect(task).toHaveBeenCalledTimes(2);
  });

  it("starts a new run after a failed one", async () => {
    const runOnce = createSingleFlight<string>();

    await expect(runOnce(async () => { throw new Error("boom"); })).rejects.toThrow("boom");
    await expect(runOnce(async () => "recovered")).resolves.toBe("recovered");
  });
});
