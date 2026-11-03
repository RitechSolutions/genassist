import { afterEach, describe, expect, it, vi } from "vitest";
import { readTimeZoneMode } from "@/helpers/timeZone";

const stubStored = (value: string | null) =>
  vi.stubGlobal("localStorage", { getItem: () => value });

describe("readTimeZoneMode", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("defaults to UTC when the browser has no storage", () => {
    expect(readTimeZoneMode()).toBe("utc");
  });

  it("defaults to UTC when nothing is saved", () => {
    stubStored(null);
    expect(readTimeZoneMode()).toBe("utc");
  });

  it("treats an unknown saved value as UTC", () => {
    stubStored("garbage");
    expect(readTimeZoneMode()).toBe("utc");
  });

  it("reads a saved Local choice", () => {
    stubStored("local");
    expect(readTimeZoneMode()).toBe("local");
  });
});
