import { describe, expect, it } from "vitest";
import {
  formatCallDuration,
  parsePercentValue,
  formatExactDuration,
  parseDurationToSeconds,
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

describe("formatExactDuration", () => {
  describe("numeric seconds input", () => {
    it("formats seconds only", () => {
      expect(formatExactDuration(0)).toBe("0s");
      expect(formatExactDuration(45)).toBe("45s");
    });

    it("formats minutes and seconds", () => {
      expect(formatExactDuration(514)).toBe("8m 34s");
      expect(formatExactDuration(600)).toBe("10m 0s");
    });

    it("formats hours, minutes and seconds", () => {
      expect(formatExactDuration(3600)).toBe("1h 0m 0s");
      expect(formatExactDuration(3725)).toBe("1h 2m 5s");
    });
  });

  describe("HH:MM:SS string input", () => {
    it("does not round leftover seconds up to the next minute", () => {
      expect(formatExactDuration("0:08:34")).toBe("8m 34s");
      expect(formatExactDuration("00:00:30")).toBe("30s");
      expect(formatExactDuration("00:45:01")).toBe("45m 1s");
    });

    it("keeps seconds past the hour mark", () => {
      expect(formatExactDuration("01:30:12")).toBe("1h 30m 12s");
      expect(formatExactDuration("23:59:59")).toBe("23h 59m 59s");
    });
  });

  describe("day-prefixed string input from the backend", () => {
    it("parses totals of 24h and beyond", () => {
      expect(formatExactDuration("1 day, 0:00:00")).toBe("24h 0m 0s");
      expect(formatExactDuration("2 days, 7:33:20")).toBe("55h 33m 20s");
    });
  });

  describe("invalid input", () => {
    it("falls back to 0s", () => {
      expect(formatExactDuration(null)).toBe("0s");
      expect(formatExactDuration(undefined)).toBe("0s");
      expect(formatExactDuration("")).toBe("0s");
      expect(formatExactDuration("abc")).toBe("0s");
      expect(formatExactDuration("1:2")).toBe("0s");
      expect(formatExactDuration(-5)).toBe("0s");
    });
  });
});

describe("parseDurationToSeconds", () => {
  it("converts supported shapes to seconds", () => {
    expect(parseDurationToSeconds(514)).toBe(514);
    expect(parseDurationToSeconds("0:08:34")).toBe(514);
    expect(parseDurationToSeconds("1 day, 0:00:00")).toBe(86400);
    expect(parseDurationToSeconds("2 days, 7:33:20")).toBe(200000);
  });

  it("returns null for unparseable input", () => {
    expect(parseDurationToSeconds("aa:bb:cc")).toBeNull();
    expect(parseDurationToSeconds(null)).toBeNull();
  });
});

describe("parsePercentValue", () => {
  it("strips the percent suffix the backend adds", () => {
    expect(parsePercentValue("86.0%")).toBe(86);
    expect(parsePercentValue("0.00%")).toBe(0);
    expect(parsePercentValue(" 42.5% ")).toBe(42.5);
  });

  it("passes finite numbers through", () => {
    expect(parsePercentValue(90)).toBe(90);
    expect(parsePercentValue(0)).toBe(0);
  });

  it("returns null rather than NaN for unusable input", () => {
    expect(parsePercentValue("N/A")).toBeNull();
    expect(parsePercentValue("")).toBeNull();
    expect(parsePercentValue(null)).toBeNull();
    expect(parsePercentValue(undefined)).toBeNull();
    expect(parsePercentValue(NaN)).toBeNull();
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

  it("drops the plural 's' for a single unit", () => {
    expect(formatTimeAgo(secondsAgoIso(3600))).toBe("1 hour ago");
    expect(formatTimeAgo(secondsAgoIso(86400))).toBe("1 day ago");
    expect(formatTimeAgo(secondsAgoIso(604800))).toBe("1 week ago");
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
