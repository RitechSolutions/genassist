import { describe, expect, it } from "vitest";
import {
  normalizeDateRange,
  toExactActivityParams,
  toExactInterval,
  toUtcBucketDateParams,
} from "./dateRange";

const day = (y: number, m: number, d: number, h = 0) => new Date(y, m - 1, d, h);

const offsetMinutes = (d: Date) => d.getTimezoneOffset();

describe("normalizeDateRange", () => {
  it("leaves a complete range untouched", () => {
    const range = { from: day(2026, 8, 1), to: day(2026, 8, 8) };
    expect(normalizeDateRange(range)).toEqual(range);
  });

  it("treats a from-only range as a single day", () => {
    const from = day(2026, 8, 1);
    expect(normalizeDateRange({ from, to: undefined })).toEqual({ from, to: from });
  });

  it("keeps an empty range undefined for all-time", () => {
    expect(normalizeDateRange(undefined)).toBeUndefined();
    expect(normalizeDateRange({ from: undefined, to: undefined })).toBeUndefined();
  });
});

describe("toExactInterval", () => {
  it("spans whole local days, end exclusive", () => {
    const interval = toExactInterval({ from: day(2026, 8, 1, 13), to: day(2026, 8, 3, 9) })!;
    expect(interval.start).toEqual(day(2026, 8, 1));
    expect(interval.endExclusive).toEqual(day(2026, 8, 4));
  });

  it("covers exactly one day for a from-only range", () => {
    const interval = toExactInterval({ from: day(2026, 8, 1), to: undefined })!;
    expect(interval.start).toEqual(day(2026, 8, 1));
    expect(interval.endExclusive).toEqual(day(2026, 8, 2));
  });

  it("keeps local midnight across a DST transition", () => {
    for (const [from, to] of [
      [day(2026, 3, 28), day(2026, 3, 30)],
      [day(2026, 11, 1), day(2026, 11, 3)],
    ]) {
      const interval = toExactInterval({ from, to })!;
      expect(interval.start.getHours()).toBe(0);
      expect(interval.endExclusive.getHours()).toBe(0);
      expect(interval.endExclusive.getDate()).toBe(to.getDate() + 1);
    }
  });
});

describe("toExactActivityParams", () => {
  it("emits both boundaries as UTC ISO strings", () => {
    const params = toExactActivityParams({ from: day(2026, 8, 1), to: day(2026, 8, 7) });
    expect(params.activity_from_datetime).toBe(day(2026, 8, 1).toISOString());
    expect(params.activity_to_datetime).toBe(day(2026, 8, 8).toISOString());
  });

  it("emits a complete one-day interval for a from-only range", () => {
    const params = toExactActivityParams({ from: day(2026, 8, 1), to: undefined });
    expect(params.activity_from_datetime).toBeDefined();
    expect(params.activity_to_datetime).toBeDefined();
    const spanMs =
      new Date(params.activity_to_datetime!).getTime() -
      new Date(params.activity_from_datetime!).getTime();
    expect(spanMs).toBeGreaterThan(0);
    expect(spanMs).toBeLessThanOrEqual(25 * 60 * 60 * 1000);
  });

  it("returns nothing for an empty range so callers can fall back to all-time", () => {
    expect(toExactActivityParams(undefined)).toEqual({});
  });
});

describe("toUtcBucketDateParams", () => {
  it("always returns both bounds for a from-only range", () => {
    const params = toUtcBucketDateParams({ from: day(2026, 8, 1), to: undefined });
    expect(params.from_date).toBeDefined();
    expect(params.to_date).toBeDefined();
  });

  it("expands to the UTC dates the local interval touches", () => {
    const range = { from: day(2026, 8, 1), to: day(2026, 8, 7) };
    const params = toUtcBucketDateParams(range);
    const west = offsetMinutes(range.from) > 0;
    const east = offsetMinutes(range.from) < 0;
    expect(params.from_date).toBe(east ? "2026-07-31" : "2026-08-01");
    expect(params.to_date).toBe(west ? "2026-08-08" : "2026-08-07");
  });

  it("matches the exact interval it is derived from", () => {
    const range = { from: day(2026, 8, 1), to: day(2026, 8, 7) };
    const interval = toExactInterval(range)!;
    const params = toUtcBucketDateParams(range);
    expect(params.from_date).toBe(interval.start.toISOString().slice(0, 10));
    expect(params.to_date).toBe(
      new Date(interval.endExclusive.getTime() - 1).toISOString().slice(0, 10),
    );
  });

  it("returns nothing for an empty range", () => {
    expect(toUtcBucketDateParams(undefined)).toEqual({});
  });
});

describe("agent performance parameter families", () => {
  it("builds a complete request from a first picker click", () => {
    const params = {
      ...toUtcBucketDateParams({ from: day(2026, 8, 1), to: undefined }),
      ...toExactActivityParams({ from: day(2026, 8, 1), to: undefined }),
    };
    for (const key of [
      "from_date",
      "to_date",
      "activity_from_datetime",
      "activity_to_datetime",
    ] as const) {
      expect(params[key]).toBeDefined();
    }
    expect(new Date(params.activity_from_datetime!).getTime()).toBeLessThan(
      new Date(params.activity_to_datetime!).getTime(),
    );
  });
});
