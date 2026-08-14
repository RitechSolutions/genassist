import { describe, expect, it } from "vitest";
import {
  formatCallDuration,
  formatTimeAgo,
  formatPercentage,
  getInitials,
} from "@/helpers/formatters";

describe("formatCallDuration", () => {
  describe("numeric seconds input", () => {
    it("formats sub-minute durations as seconds", () => {
      expect(formatCallDuration(0)).toBe("0s");
      expect(formatCallDuration(30)).toBe("30s");
      expect(formatCallDuration(59)).toBe("59s");
    });

    it("formats minute-scale durations as minutes and seconds", () => {
      expect(formatCallDuration(90)).toBe("1m 30s");
      expect(formatCallDuration(600)).toBe("10m 0s");
    });

    it("formats hour-scale durations as hours and minutes", () => {
      expect(formatCallDuration(3600)).toBe("1h 0m");
      expect(formatCallDuration(3700)).toBe("1h 1m");
    });

    it("truncates fractional seconds", () => {
      expect(formatCallDuration(90.9)).toBe("1m 30s");
    });
  });

  describe("HH:MM:SS string input", () => {
    it("rounds seconds up to a minute and formats hours", () => {
      expect(formatCallDuration("01:30:00")).toBe("1h 30m");
      expect(formatCallDuration("00:45:00")).toBe("45m");
    });

    it("counts any non-zero seconds as a whole extra minute", () => {
      expect(formatCallDuration("00:00:30")).toBe("1m");
      expect(formatCallDuration("00:00:00")).toBe("0m");
    });
  });

  describe("invalid / empty input", () => {
    it("returns '0m' for null, undefined and empty string", () => {
      expect(formatCallDuration(null)).toBe("0m");
      expect(formatCallDuration(undefined)).toBe("0m");
      expect(formatCallDuration("")).toBe("0m");
    });

    it("returns '0m' for malformed time strings", () => {
      expect(formatCallDuration("abc")).toBe("0m");
      expect(formatCallDuration("1:2")).toBe("0m");
      expect(formatCallDuration("aa:bb:cc")).toBe("0m");
    });
  });
});

describe("formatTimeAgo", () => {
  const secondsAgoIso = (s: number) =>
    new Date(Date.now() - s * 1000).toISOString();

  it("returns 'Just now' for under a minute", () => {
    expect(formatTimeAgo(secondsAgoIso(10))).toBe("Just now");
  });

  it("returns minutes for under an hour", () => {
    expect(formatTimeAgo(secondsAgoIso(120))).toBe("2 min ago");
  });

  it("returns hours for under a day", () => {
    expect(formatTimeAgo(secondsAgoIso(2 * 3600))).toBe("2 hours ago");
  });

  it("returns days for under a week", () => {
    expect(formatTimeAgo(secondsAgoIso(3 * 86400))).toBe("3 days ago");
  });

  it("returns weeks beyond a week", () => {
    expect(formatTimeAgo(secondsAgoIso(2 * 604800))).toBe("2 weeks ago");
  });
});

describe("formatPercentage", () => {
  it("multiplies a fraction by 100 and rounds", () => {
    expect(formatPercentage(0.5)).toBe("50%");
    expect(formatPercentage(1)).toBe("100%");
    expect(formatPercentage(0.855)).toBe("86%");
  });

  it("accepts numeric strings", () => {
    expect(formatPercentage("0.25")).toBe("25%");
  });

  it("returns '0%' for null, undefined and non-numeric values", () => {
    expect(formatPercentage(null)).toBe("0%");
    expect(formatPercentage(undefined)).toBe("0%");
    expect(formatPercentage("abc")).toBe("0%");
    expect(formatPercentage(0)).toBe("0%");
  });
});

describe("getInitials", () => {
  it("returns uppercased first letters of both names", () => {
    expect(getInitials("John", "Doe")).toBe("JD");
    expect(getInitials("john", "doe")).toBe("JD");
  });

  it("handles missing names", () => {
    expect(getInitials("Alice")).toBe("A");
    expect(getInitials()).toBe("");
  });
});
