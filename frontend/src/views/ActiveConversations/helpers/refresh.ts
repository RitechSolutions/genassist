/** How often the dashboard refreshes while its tab is visible */
export const DASHBOARD_REFRESH_INTERVAL_MS = 25_000;

/** A tab coming back into view refreshes only when its data is older than one refresh cycle */
export const isDashboardDataStale = (lastRequestedAtMs: number, nowMs: number = Date.now()): boolean =>
  nowMs - lastRequestedAtMs >= DASHBOARD_REFRESH_INTERVAL_MS;
