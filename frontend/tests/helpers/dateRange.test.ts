import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  normalizeDateRange,
  toExactActivityParams,
  toExactInterval,
  toInclusiveDateParams,
  toUtcBucketDateParams,
  utcDayEnd,
  utcDayStart,
} from "@/helpers/dateRange";

const originalTz = process.env.TZ;
beforeAll(() => {
  process.env.TZ = "America/Vancouver";
});
afterAll(() => {
  if (originalTz === undefined) delete process.env.TZ;
  else process.env.TZ = originalTz;
});

const day = (y: number, m: number, d: number, h = 0) => new Date(y, m - 1, d, h);

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
  it("spans whole UTC days of the picked dates, end exclusive", () => {
    const interval = toExactInterval({ from: day(2026, 8, 1, 13), to: day(2026, 8, 3, 9) })!;
    expect(interval.start.toISOString()).toBe("2026-08-01T00:00:00.000Z");
    expect(interval.endExclusive.toISOString()).toBe("2026-08-04T00:00:00.000Z");
  });

  it("covers exactly one UTC day for a from-only range", () => {
    const interval = toExactInterval({ from: day(2026, 8, 1), to: undefined })!;
    expect(interval.start.toISOString()).toBe("2026-08-01T00:00:00.000Z");
    expect(interval.endExclusive.toISOString()).toBe("2026-08-02T00:00:00.000Z");
  });
});

describe("toExactActivityParams", () => {
  it("emits the picked days as UTC midnights", () => {
    expect(toExactActivityParams({ from: day(2026, 8, 1), to: day(2026, 8, 7) })).toEqual({
      activity_from_datetime: "2026-08-01T00:00:00.000Z",
      activity_to_datetime: "2026-08-08T00:00:00.000Z",
    });
  });

  it("keeps a 24-hour day across the local DST change", () => {
    expect(toExactActivityParams({ from: day(2026, 11, 1), to: day(2026, 11, 1) })).toEqual({
      activity_from_datetime: "2026-11-01T00:00:00.000Z",
      activity_to_datetime: "2026-11-02T00:00:00.000Z",
    });
  });

  it("returns nothing for an empty range so callers can fall back to all-time", () => {
    expect(toExactActivityParams(undefined)).toEqual({});
  });
});

describe("toUtcBucketDateParams", () => {
  it("sends exactly the picked days", () => {
    expect(toUtcBucketDateParams({ from: day(2026, 8, 1), to: day(2026, 8, 7) })).toEqual({
      from_date: "2026-08-01",
      to_date: "2026-08-07",
    });
  });

  it("sends the one picked day for a from-only range", () => {
    expect(toUtcBucketDateParams({ from: day(2026, 8, 1), to: undefined })).toEqual({
      from_date: "2026-08-01",
      to_date: "2026-08-01",
    });
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

describe("UTC day bounds", () => {
  it("brackets the picked calendar day whatever the local time of the Date", () => {
    expect(utcDayStart(day(2026, 11, 1, 23))).toBe("2026-11-01T00:00:00.000Z");
    expect(utcDayEnd(day(2026, 11, 1, 23))).toBe("2026-11-01T23:59:59.999999Z");
  });
});

describe("toInclusiveDateParams", () => {
  it("sends nothing for all-time", () => {
    expect(toInclusiveDateParams(undefined)).toEqual({});
  });

  it("leaves the end open for a from-only pick", () => {
    expect(toInclusiveDateParams({ from: day(2026, 10, 1, 13), to: undefined })).toEqual({
      from_date: "2026-10-01",
    });
  });

  it("covers the whole last day", () => {
    expect(toInclusiveDateParams({ from: day(2026, 10, 1), to: day(2026, 10, 6) })).toEqual({
      from_date: "2026-10-01",
      to_date: "2026-10-06 23:59:59",
    });
  });
});
