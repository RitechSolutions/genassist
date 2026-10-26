/** Wait before each /auth/me attempt while the permission list is still missing; the first one is immediate */
const PERMISSION_RETRY_DELAYS_MS = [0, 2_000, 5_000, 10_000];

/** Delay before the next attempt, or null once all attempts are used */
export const getPermissionRetryDelayMs = (attemptsMade: number): number | null =>
  PERMISSION_RETRY_DELAYS_MS[attemptsMade] ?? null;

/** "skipped" means no request was made (signed out, server down or offline) and does not use up a retry */
export type PermissionFetchResult = "answered" | "failed" | "skipped";

/**
 * Single owner of /auth/me requests: one at a time, spaced out after failures and
 * stopped once the server has answered, however often page guards ask.
 */
export class PermissionRequestGate {
  private failedAttempts = 0;
  private hasAnswer = false;
  private isFetching = false;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly fetchPermissions: () => Promise<PermissionFetchResult>) {}

  /** Fetches right away, unless a fetch is already running */
  async fetchNow(): Promise<void> {
    if (this.isFetching) return;
    this.isFetching = true;
    try {
      const result = await this.fetchPermissions();
      if (result === "answered") {
        this.hasAnswer = true;
        this.failedAttempts = 0;
      }
      if (result === "failed") this.failedAttempts += 1;
    } finally {
      this.isFetching = false;
    }
  }

  /** Asks again when still needed, waiting longer after each failure and giving up after the last retry */
  request(): void {
    const isAlreadyHandled = this.hasAnswer || this.isFetching || this.retryTimer !== null;
    if (isAlreadyHandled) return;
    const delayMs = getPermissionRetryDelayMs(this.failedAttempts);
    if (delayMs === null) return;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.fetchNow();
    }, delayMs);
  }

  dispose(): void {
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    this.retryTimer = null;
  }
}
