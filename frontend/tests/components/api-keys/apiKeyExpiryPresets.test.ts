import { describe, expect, it } from "vitest";
import {
  API_KEY_EXPIRY_PRESET_VALUES,
  presetToExpiresInDays,
} from "@/components/api-keys/apiKeyExpiryPresets";

describe("API_KEY_EXPIRY_PRESET_VALUES", () => {
  it("lists the never/30/90/180/365 presets in order", () => {
    expect(API_KEY_EXPIRY_PRESET_VALUES).toEqual([
      { value: "never", label: "Never" },
      { value: "30", label: "30d" },
      { value: "90", label: "90d" },
      { value: "180", label: "180d" },
      { value: "365", label: "1y" },
    ]);
  });
});

describe("presetToExpiresInDays", () => {
  it("returns undefined for the 'never' preset", () => {
    expect(presetToExpiresInDays("never")).toBeUndefined();
  });

  it("returns undefined for an empty string", () => {
    expect(presetToExpiresInDays("")).toBeUndefined();
  });

  it("parses numeric day presets", () => {
    expect(presetToExpiresInDays("30")).toBe(30);
    expect(presetToExpiresInDays("90")).toBe(90);
    expect(presetToExpiresInDays("180")).toBe(180);
    expect(presetToExpiresInDays("365")).toBe(365);
  });

  it("parses a leading integer from a mixed string", () => {
    expect(presetToExpiresInDays("30abc")).toBe(30);
  });

  it("returns undefined for non-numeric input", () => {
    expect(presetToExpiresInDays("abc")).toBeUndefined();
    expect(presetToExpiresInDays("   ")).toBeUndefined();
  });
});
