import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { DateRange } from "react-day-picker";
import {
  toExpandedUTCDateRange,
  toMetricsApiParams,
  buildQueryString,
} from "@/helpers/analyticsParams";

const originalTz = process.env.TZ;
beforeAll(() => {
  process.env.TZ = "America/Vancouver";
});
afterAll(() => {
  if (originalTz === undefined) delete process.env.TZ;
  else process.env.TZ = originalTz;
});

const range = (): DateRange => ({
  from: new Date(2026, 1, 17),
  to: new Date(2026, 1, 20),
});

describe("toExpandedUTCDateRange", () => {
  it("returns an empty object without a range", () => {
    expect(toExpandedUTCDateRange(undefined)).toEqual({});
  });

  it("formats from/to as yyyy-MM-dd day strings", () => {
    expect(toExpandedUTCDateRange(range())).toEqual({
      from_date: "2026-02-17",
      to_date: "2026-02-20",
    });
  });

  it("omits the missing bound", () => {
    expect(toExpandedUTCDateRange({ from: new Date(2026, 1, 17) })).toEqual({
      from_date: "2026-02-17",
      to_date: undefined,
    });
  });
});

describe("toMetricsApiParams", () => {
  it("returns all-undefined without a range", () => {
    expect(toMetricsApiParams(undefined)).toEqual({
      from_date: undefined,
      to_date: undefined,
      agent_id: undefined,
      group_id: undefined,
    });
  });

  it("brackets the picked days in UTC, inclusive end at Postgres resolution", () => {
    const params = toMetricsApiParams(range());
    expect(params.from_date).toBe("2026-02-17T00:00:00.000Z");
    expect(params.to_date).toBe("2026-02-20T23:59:59.999999Z");
  });

  it("leaves the end open for a from-only pick", () => {
    const params = toMetricsApiParams({ from: new Date(2026, 1, 17) });
    expect(params.from_date).toBe("2026-02-17T00:00:00.000Z");
    expect(params.to_date).toBeUndefined();
  });

  it("treats 'all' agent and group as no filter", () => {
    const params = toMetricsApiParams(range(), "all", "all");
    expect(params.agent_id).toBeUndefined();
    expect(params.group_id).toBeUndefined();
  });

  it("passes a concrete agent id and drops group when an agent is set", () => {
    expect(toMetricsApiParams(range(), "agent-1", "grp-1").agent_id).toBe(
      "agent-1"
    );
    expect(toMetricsApiParams(range(), "agent-1", "grp-1").group_id).toBeUndefined();
  });

  it("uses group id only when no agent is selected", () => {
    const params = toMetricsApiParams(range(), undefined, "grp-1");
    expect(params.agent_id).toBeUndefined();
    expect(params.group_id).toBe("grp-1");
  });
});

describe("buildQueryString", () => {
  it("returns an empty string without params", () => {
    expect(buildQueryString(undefined)).toBe("");
    expect(buildQueryString({})).toBe("");
  });

  it("serializes provided params in a stable order", () => {
    expect(
      buildQueryString({
        from_date: "a",
        to_date: "b",
        agent_id: "x",
        group_id: "g",
        compare: "c",
      })
    ).toBe("?from_date=a&to_date=b&agent_id=x&group_id=g&compare=c");
  });

  it("only includes present keys", () => {
    expect(buildQueryString({ from_date: "a", agent_id: "x" })).toBe(
      "?from_date=a&agent_id=x"
    );
  });
});
