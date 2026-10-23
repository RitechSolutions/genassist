/** Returns a runner that shares one in-flight run of `task` between overlapping callers. */
export function createSingleFlight<T>(): (task: () => Promise<T>) => Promise<T> {
  let inFlight: Promise<T> | null = null;
  return (task) => {
    if (!inFlight) {
      inFlight = task().finally(() => {
        inFlight = null;
      });
    }
    return inFlight;
  };
}
