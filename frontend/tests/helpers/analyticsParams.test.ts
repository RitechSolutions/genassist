import { describe, expect, it } from "vitest";
import type { DateRange } from "react-day-picker";
import {
  toExpandedUTCDateRange,
  toMetricsApiParams,
  buildQueryString,
} from "@/helpers/analyticsParams";

// Build dates from local components so the round-trip through
// start/end-of-day-UTC lands back on the same calendar day regardless of the
// runner's timezone.
const range: DateRange = {
  from: new Date(2026, 1, 17),
  to: new Date(2026, 1, 20),
};

describe("toExpandedUTCDateRange", () => {
  it("returns an empty object without a range", () => {
    expect(toExpandedUTCDateRange(undefined)).toEqual({});
  });

  it("formats from/to as yyyy-MM-dd day strings", () => {
    expect(toExpandedUTCDateRange(range)).toEqual({
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

  it("emits ISO from/to strings for a range", () => {
    const params = toMetricsApiParams(range);
    expect(typeof params.from_date).toBe("string");
    expect(typeof params.to_date).toBe("string");
    expect(params.from_date).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("treats 'all' agent and group as no filter", () => {
    const params = toMetricsApiParams(range, "all", "all");
    expect(params.agent_id).toBeUndefined();
    expect(params.group_id).toBeUndefined();
  });

  it("passes a concrete agent id and drops group when an agent is set", () => {
    expect(toMetricsApiParams(range, "agent-1", "grp-1").agent_id).toBe(
      "agent-1"
    );
    expect(toMetricsApiParams(range, "agent-1", "grp-1").group_id).toBeUndefined();
  });

  it("uses group id only when no agent is selected", () => {
    const params = toMetricsApiParams(range, undefined, "grp-1");
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
