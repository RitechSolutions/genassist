import { describe, expect, it } from "vitest";
import { parseStoredDateRange } from "./usePersistedDateRange";

describe("parseStoredDateRange", () => {
  it("reports nothing stored for a missing entry", () => {
    expect(parseStoredDateRange(null)).toBeNull();
    expect(parseStoredDateRange("")).toBeNull();
  });

  it("reports nothing stored for unparseable content", () => {
    expect(parseStoredDateRange("not json")).toBeNull();
  });

  it("reads a legacy ISO range", () => {
    const parsed = parseStoredDateRange(
      JSON.stringify({ from: "2026-08-01T00:00:00.000Z", to: "2026-08-08T00:00:00.000Z" }),
    );
    expect(parsed?.value?.from).toEqual(new Date("2026-08-01T00:00:00.000Z"));
    expect(parsed?.value?.to).toEqual(new Date("2026-08-08T00:00:00.000Z"));
  });

  it("keeps a from-only range", () => {
    const parsed = parseStoredDateRange(JSON.stringify({ from: "2026-08-01T00:00:00.000Z" }));
    expect(parsed?.value?.from).toEqual(new Date("2026-08-01T00:00:00.000Z"));
    expect(parsed?.value?.to).toBeUndefined();
  });

  it("distinguishes a cleared range from nothing stored", () => {
    const cleared = parseStoredDateRange("{}");
    expect(cleared).not.toBeNull();
    expect(cleared?.value).toBeUndefined();
  });

  it("treats invalid dates as nothing stored", () => {
    expect(parseStoredDateRange(JSON.stringify({ from: "nonsense", to: "nonsense" }))?.value).toBeUndefined();
  });
});
