import { useCallback, useEffect, useState } from "react";
import type { DateRange } from "react-day-picker";

/**
 * Globally-shared date range, persisted to localStorage so a range selected on
 * one page (dashboard, analytics, conversations, audit logs, ...) carries over
 * to every other page and survives a full reload.
 *
 * Usage is a drop-in replacement for `useState<DateRange | undefined>`:
 *
 *   const [dateRange, setDateRange] = usePersistedDateRange({
 *     from: subDays(new Date(), 30),
 *     to: new Date(),
 *   });
 *
 * Pass a different `storageKey` to persist an independent range (e.g. the
 * analytics "compare period") under its own slot, while sharing it across the
 * pages that expose it:
 *
 *   const [compare, setCompare] = usePersistedDateRange(
 *     undefined,
 *     COMPARE_DATE_RANGE_STORAGE_KEY,
 *   );
 *
 * The `defaultValue` is only used the very first time, when nothing has been
 * persisted yet. After that, the last selected range wins everywhere.
 */
export const DATE_RANGE_STORAGE_KEY = "genassist_date_range";
export const COMPARE_DATE_RANGE_STORAGE_KEY = "genassist_compare_date_range";

// Same-tab sync: the `storage` event only fires in *other* tabs, so we emit a
// custom event to keep multiple mounted consumers in this tab in sync too.
const DATE_RANGE_CHANGE_EVENT = "genassist:date-range-change";

type StoredDateRange = { from?: string; to?: string };

function serialize(range: DateRange | undefined): string {
  const payload: StoredDateRange = {
    from: range?.from instanceof Date ? range.from.toISOString() : undefined,
    to: range?.to instanceof Date ? range.to.toISOString() : undefined,
  };
  return JSON.stringify(payload);
}

function parseDate(value: string | undefined): Date | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

function deserialize(raw: string | null): DateRange | undefined {
  if (!raw) return undefined;
  try {
    const parsed = JSON.parse(raw) as StoredDateRange;
    const from = parseDate(parsed.from);
    const to = parseDate(parsed.to);
    if (!from && !to) return undefined;
    return { from, to };
  } catch {
    return undefined;
  }
}

function readStored(storageKey: string): DateRange | undefined {
  try {
    return deserialize(localStorage.getItem(storageKey));
  } catch {
    return undefined;
  }
}

export function usePersistedDateRange(
  defaultValue: DateRange | undefined,
  storageKey: string = DATE_RANGE_STORAGE_KEY,
): [DateRange | undefined, (value: DateRange | undefined) => void] {
  const [value, setValue] = useState<DateRange | undefined>(() => {
    const stored = readStored(storageKey);
    return stored ?? defaultValue;
  });

  const setPersisted = useCallback(
    (next: DateRange | undefined) => {
      setValue(next);
      try {
        localStorage.setItem(storageKey, serialize(next));
      } catch {
        // Ignore write errors (e.g. storage full / unavailable).
      }
      // Notify other mounted consumers of this same key in this tab.
      window.dispatchEvent(
        new CustomEvent(DATE_RANGE_CHANGE_EVENT, { detail: { key: storageKey } }),
      );
    },
    [storageKey],
  );

  // Keep this instance in sync when its range is changed elsewhere — either in
  // another tab (`storage`) or by another consumer in this tab (custom event).
  useEffect(() => {
    const sync = () => setValue(readStored(storageKey) ?? undefined);

    const onStorage = (event: StorageEvent) => {
      if (event.key === storageKey) sync();
    };
    const onCustom = (event: Event) => {
      const detailKey = (event as CustomEvent<{ key?: string }>).detail?.key;
      if (detailKey === storageKey) sync();
    };

    window.addEventListener("storage", onStorage);
    window.addEventListener(DATE_RANGE_CHANGE_EVENT, onCustom);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(DATE_RANGE_CHANGE_EVENT, onCustom);
    };
  }, [storageKey]);

  return [value, setPersisted];
}
