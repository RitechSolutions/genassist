import { describe, expect, it } from "vitest";
import formatDuration, { formatDuration as namedFormatDuration } from "@/helpers/duration";

describe("formatDuration", () => {
  it("exposes the same function as default and named export", () => {
    expect(formatDuration).toBe(namedFormatDuration);
  });

  it("formats sub-hour durations as m:ss", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(5)).toBe("0:05");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(600)).toBe("10:00");
  });

  it("formats hour-scale durations as h:mm:ss", () => {
    expect(formatDuration(3600)).toBe("1:00:00");
    expect(formatDuration(3661)).toBe("1:01:01");
  });

  it("coerces numeric strings", () => {
    expect(formatDuration("90")).toBe("1:30");
  });

  it("floors fractional seconds", () => {
    expect(formatDuration(65.9)).toBe("1:05");
  });

  it("clamps negative values to zero", () => {
    expect(formatDuration(-5)).toBe("0:00");
  });

  it("returns '0:00' for null, undefined and non-numeric input", () => {
    expect(formatDuration(null)).toBe("0:00");
    expect(formatDuration(undefined)).toBe("0:00");
    expect(formatDuration("abc")).toBe("0:00");
    expect(formatDuration(NaN)).toBe("0:00");
    expect(formatDuration(Infinity)).toBe("0:00");
  });
});
