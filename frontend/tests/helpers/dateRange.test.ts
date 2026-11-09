import { format } from "date-fns";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  calendarToday,
  lastDaysDateRange,
  normalizeDateRange,
  toExactActivityParams,
  toExactInterval,
  toInclusiveDateParams,
  toUtcBucketDateParams,
  dayEndIso,
  dayStartIso,
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

describe("calendarToday", () => {
  afterEach(() => {
    process.env.TZ = "America/Vancouver";
    vi.useRealTimers();
  });

  it.each([
    ["Pacific/Kiritimati", "2026-10-30T11:53:00Z", "2026-10-30", "2026-10-31"],
    ["Asia/Tokyo", "2026-10-30T22:00:00Z", "2026-10-30", "2026-10-31"],
    ["America/Vancouver", "2026-10-31T02:00:00Z", "2026-10-31", "2026-11-01"],
    ["UTC", "2026-10-30T11:53:00Z", "2026-10-30", "2026-10-31"],
  ])("in %s at %s, Today is the UTC day the server counts", (tz, now, today, next) => {
    process.env.TZ = tz;
    const picked = calendarToday(new Date(now));
    expect(format(picked, "yyyy-MM-dd HH:mm")).toBe(`${today} 00:00`);
    expect(toExactActivityParams({ from: picked, to: picked })).toEqual({
      activity_from_datetime: `${today}T00:00:00.000Z`,
      activity_to_datetime: `${next}T00:00:00.000Z`,
    });
  });

  it("ends the last-7-days default on the UTC day", () => {
    process.env.TZ = "Pacific/Kiritimati";
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-30T11:53:00Z"));
    const range = lastDaysDateRange(7);
    expect(format(range.from!, "yyyy-MM-dd HH:mm")).toBe("2026-10-23 00:00");
    expect(format(range.to!, "yyyy-MM-dd HH:mm")).toBe("2026-10-30 00:00");
  });
});

describe("UTC day bounds", () => {
  it("brackets the picked calendar day whatever the local time of the Date", () => {
    expect(dayStartIso(day(2026, 11, 1, 23))).toBe("2026-11-01T00:00:00.000Z");
    expect(dayEndIso(day(2026, 11, 1, 23))).toBe("2026-11-01T23:59:59.999999Z");
  });
});

describe("in Local time mode", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", { getItem: () => "local" });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    process.env.TZ = "America/Vancouver";
  });

  it("spans Vancouver's 25-hour day when DST ends", () => {
    const interval = toExactInterval({ from: day(2026, 11, 1), to: day(2026, 11, 1) })!;
    expect(interval.start.toISOString()).toBe("2026-11-01T07:00:00.000Z");
    expect(interval.endExclusive.toISOString()).toBe("2026-11-02T08:00:00.000Z");
  });

  it("spans Berlin's 25-hour day when DST ends", () => {
    process.env.TZ = "Europe/Berlin";
    const interval = toExactInterval({ from: day(2026, 10, 25), to: day(2026, 10, 25) })!;
    expect(interval.start.toISOString()).toBe("2026-10-24T22:00:00.000Z");
    expect(interval.endExclusive.toISOString()).toBe("2026-10-25T23:00:00.000Z");
  });

  it("brackets the picked day in local time", () => {
    expect(dayStartIso(day(2026, 11, 1, 23))).toBe("2026-11-01T07:00:00.000Z");
    expect(dayEndIso(day(2026, 11, 1, 23))).toBe("2026-11-02T07:59:59.999999Z");
  });

  it("takes Today from the local clock", () => {
    process.env.TZ = "Pacific/Kiritimati";
    const picked = calendarToday(new Date("2026-10-30T11:53:00Z"));
    expect(format(picked, "yyyy-MM-dd HH:mm")).toBe("2026-10-31 00:00");
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
