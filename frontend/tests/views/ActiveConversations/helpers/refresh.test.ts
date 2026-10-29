import { describe, expect, it } from "vitest";
import {
  DASHBOARD_REFRESH_INTERVAL_MS,
  isDashboardDataStale,
} from "@/views/ActiveConversations/helpers/refresh";

const NOW_MS = 1_000_000;

describe("isDashboardDataStale", () => {
  it("skips the refresh when the tab returns soon after the last one", () => {
    expect(isDashboardDataStale(NOW_MS - 5_000, NOW_MS)).toBe(false);
  });

  it("refreshes once the data is a full cycle old", () => {
    expect(isDashboardDataStale(NOW_MS - DASHBOARD_REFRESH_INTERVAL_MS, NOW_MS)).toBe(true);
  });

  it("refreshes when nothing has been requested yet", () => {
    expect(isDashboardDataStale(0, NOW_MS)).toBe(true);
  });
});
