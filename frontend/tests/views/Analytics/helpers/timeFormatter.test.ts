import { describe, expect, it } from "vitest";
import { formatResponseTime } from "@/views/Analytics/helpers/timeFormatter";

describe("formatResponseTime", () => {
  it("converts a percentage-like value to a millisecond scale", () => {
    expect(formatResponseTime("85.50%")).toBe("855ms");
    expect(formatResponseTime("100%")).toBe("1000ms");
    expect(formatResponseTime("0%")).toBe("0ms");
  });

  it("reads the leading numeric portion without a percent sign", () => {
    expect(formatResponseTime("12")).toBe("120ms");
  });

  it("returns '0ms' when there is no numeric value", () => {
    expect(formatResponseTime("no digits")).toBe("0ms");
    expect(formatResponseTime("")).toBe("0ms");
  });
});
