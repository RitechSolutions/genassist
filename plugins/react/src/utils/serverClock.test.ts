import { describe, expect, it } from "vitest";

import { measureClockOffsetMs, readUuidV7TimeMs } from "./serverClock";

const uuidV7At = (ms: number): string => {
  const hex = ms.toString(16).padStart(12, "0") + "7abc8def0123456789ab";
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};

const SERVER_MS = Date.UTC(2026, 9, 9, 10, 0, 0);

describe("readUuidV7TimeMs", () => {
  it("reads the creation time the server wrote into a UUIDv7 id", () => {
    expect(readUuidV7TimeMs(uuidV7At(SERVER_MS))).toBe(SERVER_MS);
  });

  it("returns null for ids that are not UUIDv7", () => {
    expect(readUuidV7TimeMs("3f2504e0-4f89-41d3-9a0c-0305e82c3301")).toBeNull();
    expect(readUuidV7TimeMs("not-an-id")).toBeNull();
  });
});

describe("measureClockOffsetMs", () => {
  it("measures how far this device's clock is behind or ahead of the server", () => {
    const twoDays = 2 * 24 * 60 * 60 * 1000;
    expect(measureClockOffsetMs(uuidV7At(SERVER_MS), SERVER_MS + twoDays)).toBe(-twoDays);
    expect(measureClockOffsetMs(uuidV7At(SERVER_MS), SERVER_MS - 5000)).toBe(5000);
  });

  it("assumes the clocks agree when the id carries no time", () => {
    expect(measureClockOffsetMs("3f2504e0-4f89-41d3-9a0c-0305e82c3301", SERVER_MS)).toBe(0);
  });
});
