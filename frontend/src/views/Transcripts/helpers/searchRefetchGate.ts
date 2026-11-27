export const SEARCH_REFETCH_INTERVAL_MS = 30_000;

export interface SearchRefetchGate {
  /** Starts `refetch` unless one is running or the last search started or ended too recently. */
  tryStart: (refetch: () => Promise<unknown>) => boolean;
  /** Records a search the page started itself, so live updates wait the full interval. */
  markStarted: () => void;
}

interface SearchRefetchGateOptions {
  intervalMs?: number;
  clock?: () => number;
}

export function createSearchRefetchGate({
  intervalMs = SEARCH_REFETCH_INTERVAL_MS,
  clock = Date.now,
}: SearchRefetchGateOptions = {}): SearchRefetchGate {
  let isRunning = false;
  let lastActivityAt = Number.NEGATIVE_INFINITY;

  const markStarted = () => {
    lastActivityAt = clock();
  };

  const tryStart = (refetch: () => Promise<unknown>): boolean => {
    const activeRecently = clock() - lastActivityAt < intervalMs;
    if (isRunning || activeRecently) return false;

    isRunning = true;
    markStarted();
    void Promise.resolve()
      .then(refetch)
      .catch((error: unknown) => console.error("Search refetch failed", error))
      .finally(() => {
        isRunning = false;
        markStarted();
      });
    return true;
  };

  return { tryStart, markStarted };
}
