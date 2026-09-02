import { describe, expect, it } from "vitest";
import {
  formatDateTime,
  formatDuration,
  formatMessageTime,
} from "@/views/ActiveConversations/helpers/format";

describe("formatDuration", () => {
  it("delegates to the shared duration formatter", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(3661)).toBe("1:01:01");
  });

  it("treats undefined as zero seconds", () => {
    expect(formatDuration(undefined)).toBe("0:00");
  });

  it("clamps negative values to zero via the shared formatter", () => {
    expect(formatDuration(-5)).toBe("0:00");
  });
});

describe("formatDateTime", () => {
  it("prefixes today's timestamps with 'Today, '", () => {
    const todayNoon = new Date();
    todayNoon.setHours(12, 0, 0, 0);
    expect(formatDateTime(todayNoon.toISOString()).startsWith("Today, ")).toBe(
      true,
    );
  });

  it("prefixes yesterday's timestamps with 'Yesterday, '", () => {
    const yesterdayNoon = new Date();
    yesterdayNoon.setDate(yesterdayNoon.getDate() - 1);
    yesterdayNoon.setHours(12, 0, 0, 0);
    expect(
      formatDateTime(yesterdayNoon.toISOString()).startsWith("Yesterday, "),
    ).toBe(true);
  });

  it("formats older dates as '<date>, <time>' without a relative prefix", () => {
    const result = formatDateTime("2020-01-15T10:30:00");
    expect(result.startsWith("Today,")).toBe(false);
    expect(result.startsWith("Yesterday,")).toBe(false);
    expect(result).toContain(", ");
  });
});

describe("formatMessageTime", () => {
  it("returns an empty string for falsy input", () => {
    expect(formatMessageTime(undefined)).toBe("");
    expect(formatMessageTime("")).toBe("");
    expect(formatMessageTime(0)).toBe("");
  });

  it("formats ISO-like strings using their literal local time", () => {
    // A datetime string with no timezone is parsed as local and formatted as
    // local, so the HH:MM:SS is deterministic regardless of the runner's zone.
    expect(formatMessageTime("2023-06-15T14:05:09")).toBe("14:05:09");
  });

  it("formats space-separated datetime strings using their literal local time", () => {
    expect(formatMessageTime("2023-06-15 14:05:09")).toBe("14:05:09");
  });

  it("treats a bare numeric string as unix seconds", () => {
    expect(formatMessageTime("1600000000")).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });

  it("treats a number as unix seconds", () => {
    expect(formatMessageTime(1600000000)).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });

  it("returns an empty string for a non-numeric bare string", () => {
    expect(formatMessageTime("abc")).toBe("");
  });

  it("returns an empty string when the parsed date is invalid", () => {
    expect(formatMessageTime("not-a-date T")).toBe("");
  });
});
