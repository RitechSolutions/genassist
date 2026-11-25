import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/services/api", () => ({
  getKnowledgeBaseSyncStatus: vi.fn(),
}));

import { getKnowledgeBaseSyncStatus } from "@/services/api";
import {
  describeSyncOutcome,
  describeSyncResult,
  isSyncInProgress,
  MANUAL_SYNC_TIMING,
  waitForManualSync,
} from "@/views/KnowledgeBase/utils/manualSync";

const mockStatus = vi.mocked(getKnowledgeBaseSyncStatus);
const POLL_MS = 10;
const TIMING = {
  pollStages: [
    { untilMs: 5_000, intervalMs: POLL_MS },
    { untilMs: 6_000, intervalMs: POLL_MS * 10 },
  ],
  finalPollIntervalMs: POLL_MS * 30,
  retryAfterFailureMs: POLL_MS * 10,
  giveUpAfterFailedMs: POLL_MS * 5,
  giveUpAfterFailedChecks: 3,
};

const waitFor = (runId?: string, signal?: AbortSignal, timing = TIMING) =>
  waitForManualSync("kb-1", runId, signal, timing);

beforeEach(() => {
  vi.useFakeTimers();
  mockStatus.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("isSyncInProgress", () => {
  it("is true only for a running sync", () => {
    expect(isSyncInProgress({ status: "running" })).toBe(true);
    expect(isSyncInProgress({ status: "succeeded" })).toBe(false);
    expect(isSyncInProgress({ status: "idle" })).toBe(false);
    expect(isSyncInProgress(null)).toBe(false);
  });
});

describe("waitForManualSync", () => {
  it("keeps polling while the sync is running, then returns its result", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockResolvedValueOnce({ status: "succeeded", run_id: "run-1", result: { status: "completed" } });

    const waiting = waitFor("run-1");
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);

    expect(await waiting).toEqual({ kind: "finished", result: { status: "completed" } });
    expect(mockStatus).toHaveBeenCalledTimes(3);
  });

  it("returns the error of a failed sync", async () => {
    mockStatus.mockResolvedValue({ status: "failed", run_id: "run-1", error: "S3 download failed" });

    expect(await waitFor("run-1")).toEqual({ kind: "failed", error: "S3 download failed" });
  });

  it("reports a running sync that ended without a result as stopped", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockResolvedValueOnce({ status: "idle" });

    const waiting = waitFor("run-1");
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);

    expect(await waiting).toEqual({ kind: "stopped" });
  });

  it("returns the result of a sync that finished between two checks", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockResolvedValueOnce({ status: "succeeded", run_id: "run-1", result: { status: "completed" } });

    const waiting = waitFor("run-1");
    await vi.advanceTimersByTimeAsync(POLL_MS * 2);

    expect(await waiting).toEqual({ kind: "finished", result: { status: "completed" } });
  });

  it("keeps its own run's result when a newer run is already in progress", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockResolvedValueOnce({
        status: "running",
        run_id: "run-2",
        previous: { status: "failed", run_id: "run-1", error: "Synchronization failed." },
      });

    const waiting = waitFor("run-1");
    await vi.advanceTimersByTimeAsync(POLL_MS * 2);

    expect(await waiting).toEqual({ kind: "failed", error: "Synchronization failed." });
    expect(mockStatus).toHaveBeenCalledTimes(2);
  });

  it("does not follow a newer run whose previous result is not its own", async () => {
    mockStatus.mockResolvedValue({
      status: "running",
      run_id: "run-3",
      previous: { status: "succeeded", run_id: "run-2", result: {} },
    });

    expect(await waitFor("run-1")).toEqual({ kind: "stopped" });
  });

  it("does not take an older run's result for the followed run", async () => {
    mockStatus.mockResolvedValue({ status: "succeeded", run_id: "older-run", result: { status: "completed" } });

    expect(await waitFor("run-1")).toEqual({ kind: "stopped" });
  });

  it("follows the run it finds in progress when it was given none", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-7" })
      .mockResolvedValueOnce({ status: "succeeded", run_id: "run-7", result: {} });

    const waiting = waitFor(undefined);
    await vi.advanceTimersByTimeAsync(POLL_MS * 2);

    expect(await waiting).toEqual({ kind: "finished", result: {} });
  });

  it("gives up only after enough failed checks over enough time", async () => {
    mockStatus
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockRejectedValue(new Error("network"));

    const waiting = waitFor("run-1");
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    expect(mockStatus).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(POLL_MS * 2);
    expect(mockStatus).toHaveBeenCalledTimes(6);
    await vi.advanceTimersByTimeAsync(POLL_MS);

    expect(await waiting).toEqual({ kind: "unknown" });
    expect(mockStatus).toHaveBeenCalledTimes(7);
  });

  it("does not give up on a single failed check after a long gap", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce({ status: "succeeded", run_id: "run-1", result: {} });
    const longGaps = { ...TIMING, pollStages: [], finalPollIntervalMs: POLL_MS * 30 };

    const waiting = waitFor("run-1", undefined, longGaps);
    await vi.advanceTimersByTimeAsync(POLL_MS * 30);
    await vi.advanceTimersByTimeAsync(POLL_MS * 10);

    expect(await waiting).toEqual({ kind: "finished", result: {} });
  });

  it("retries a failed check sooner than the slow interval, and gives up after three failures", async () => {
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockRejectedValue(new Error("network"));
    const longGaps = { ...TIMING, pollStages: [], finalPollIntervalMs: POLL_MS * 30 };

    const waiting = waitFor("run-1", undefined, longGaps);
    await vi.advanceTimersByTimeAsync(POLL_MS * 30);
    expect(mockStatus).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(POLL_MS * 10);
    expect(mockStatus).toHaveBeenCalledTimes(3);
    await vi.advanceTimersByTimeAsync(POLL_MS * 10);

    expect(await waiting).toEqual({ kind: "unknown" });
    expect(mockStatus).toHaveBeenCalledTimes(4);
  });

  it("checks less often the longer the sync runs", async () => {
    mockStatus.mockResolvedValue({ status: "running", run_id: "run-1" });
    const controller = new AbortController();
    const stages = {
      ...TIMING,
      pollStages: [
        { untilMs: POLL_MS * 3, intervalMs: POLL_MS },
        { untilMs: POLL_MS * 13, intervalMs: POLL_MS * 10 },
      ],
    };

    const waiting = waitFor("run-1", controller.signal, stages);
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    expect(mockStatus).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(POLL_MS * 9);
    expect(mockStatus).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(mockStatus).toHaveBeenCalledTimes(5);
    await vi.advanceTimersByTimeAsync(POLL_MS * 29);
    expect(mockStatus).toHaveBeenCalledTimes(5);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(mockStatus).toHaveBeenCalledTimes(6);

    controller.abort();
    await vi.advanceTimersByTimeAsync(POLL_MS * 30);
    expect(await waiting).toEqual({ kind: "aborted" });
  });

  it("uses the agreed check intervals", () => {
    expect(MANUAL_SYNC_TIMING).toEqual({
      pollStages: [
        { untilMs: 30_000, intervalMs: 2_000 },
        { untilMs: 300_000, intervalMs: 10_000 },
      ],
      finalPollIntervalMs: 30_000,
      retryAfterFailureMs: 10_000,
      giveUpAfterFailedMs: 60_000,
      giveUpAfterFailedChecks: 3,
    });
  });

  it("stops quietly when the page is left while a failing check is in flight", async () => {
    const controller = new AbortController();
    mockStatus
      .mockResolvedValueOnce({ status: "running", run_id: "run-1" })
      .mockRejectedValueOnce(new Error("network"))
      .mockRejectedValueOnce(new Error("network"))
      .mockImplementationOnce(() => {
        controller.abort();
        return Promise.reject(new Error("network"));
      });

    const waiting = waitFor("run-1", controller.signal, { ...TIMING, giveUpAfterFailedMs: 0 });
    await vi.advanceTimersByTimeAsync(POLL_MS * 4);

    expect(await waiting).toEqual({ kind: "aborted" });
  });

  it("stops quietly when the page stops following the sync", async () => {
    mockStatus.mockResolvedValue({ status: "running", run_id: "run-1" });
    const controller = new AbortController();

    const waiting = waitFor("run-1", controller.signal);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    controller.abort();
    await vi.advanceTimersByTimeAsync(POLL_MS);

    expect(await waiting).toEqual({ kind: "aborted" });
  });
});

describe("describeSyncResult", () => {
  it("reports the article counts of a Zendesk sync", () => {
    const result = {
      status: "completed",
      zendesk_sync_results: [{ result: { articles_added: 2, articles_updated: 1, articles_deleted: 0 } }],
    };

    expect(describeSyncResult(result, "zendesk")).toEqual({
      kind: "success",
      text: "Sync completed: 2 added, 1 updated, 0 removed.",
    });
  });

  it("reads the Salesforce results for a Salesforce knowledge base", () => {
    const result = {
      status: "completed",
      zendesk_sync_results: [],
      salesforce_sync_results: [{ result: { status: "failed", error: "Bad credentials" } }],
    };

    expect(describeSyncResult(result, "salesforce")).toEqual({ kind: "error", text: "Bad credentials" });
  });

  it("reports a skipped knowledge base with its reason", () => {
    const result = {
      zendesk_sync_results: [{ result: { per_kb: [{ status: "skipped", reason: "no datasource" }] } }],
    };

    expect(describeSyncResult(result, "zendesk")).toEqual({
      kind: "error",
      text: "Sync skipped: no datasource. Check schedule, datasource, or Zendesk connection.",
    });
  });

  it("reports a file sync without article counts as completed", () => {
    expect(describeSyncResult({ status: "completed" }, "s3")).toEqual({
      kind: "success",
      text: "Synchronization completed successfully.",
    });
  });

  it("reports an error status with its message", () => {
    expect(describeSyncResult({ status: "error", message: "kb_id is required" }, "s3")).toEqual({
      kind: "error",
      text: "kb_id is required",
    });
  });
});

describe("describeSyncOutcome", () => {
  it("has a message for every way a followed sync can end", () => {
    expect(describeSyncOutcome({ kind: "finished", result: { status: "completed" } }, "s3")?.kind).toBe("success");
    expect(describeSyncOutcome({ kind: "failed", error: "S3 download failed" }, "s3")).toEqual({
      kind: "error",
      text: "S3 download failed",
    });
    expect(describeSyncOutcome({ kind: "failed" }, "s3")?.text).toBe("Synchronization failed.");
    expect(describeSyncOutcome({ kind: "stopped" }, "s3")?.kind).toBe("error");
    expect(describeSyncOutcome({ kind: "unknown" }, "s3")?.kind).toBe("error");
  });

  it("has no message when the page stopped following the sync", () => {
    expect(describeSyncOutcome({ kind: "aborted" }, "s3")).toBeNull();
  });
});
