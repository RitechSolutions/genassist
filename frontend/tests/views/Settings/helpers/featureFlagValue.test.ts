import { describe, it, expect, vi, beforeEach } from "vitest";
import type { FeatureFlag } from "@/interfaces/featureFlag.interface";

const { getFeatureFlagsMock } = vi.hoisted(() => ({ getFeatureFlagsMock: vi.fn() }));

vi.mock("@/services/featureFlags", () => ({
  getFeatureFlags: getFeatureFlagsMock,
}));

import { isFeatureEnabled, getFeatureValue } from "@/views/Settings/helpers/featureFlagValue";

const flag = (over: Partial<FeatureFlag>): FeatureFlag => ({
  key: "k",
  val: "true",
  description: "",
  is_active: 1,
  ...over,
});

beforeEach(() => {
  getFeatureFlagsMock.mockReset();
});

describe("isFeatureEnabled", () => {
  it("is true for an active flag whose val is exactly 'true'", async () => {
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 1, val: "true" })]);
    await expect(isFeatureEnabled("x")).resolves.toBe(true);
  });

  it("is false when val is not exactly 'true'", async () => {
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 1, val: "false" })]);
    await expect(isFeatureEnabled("x")).resolves.toBe(false);
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 1, val: "1" })]);
    await expect(isFeatureEnabled("x")).resolves.toBe(false);
  });

  it("is false when the flag is inactive (is_active !== 1)", async () => {
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 0, val: "true" })]);
    await expect(isFeatureEnabled("x")).resolves.toBe(false);
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 2, val: "true" })]);
    await expect(isFeatureEnabled("x")).resolves.toBe(false);
  });

  it("is false when no flag matches the key", async () => {
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "other", val: "true" })]);
    await expect(isFeatureEnabled("x")).resolves.toBe(false);
  });

  it("is false when getFeatureFlags rejects", async () => {
    getFeatureFlagsMock.mockRejectedValue(new Error("boom"));
    await expect(isFeatureEnabled("x")).resolves.toBe(false);
  });
});

describe("getFeatureValue", () => {
  it("returns the raw val of the matching active flag", async () => {
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 1, val: "blue" })]);
    await expect(getFeatureValue("x")).resolves.toBe("blue");
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 1, val: "" })]);
    await expect(getFeatureValue("x")).resolves.toBe("");
  });

  it("returns null when the flag is inactive or missing", async () => {
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "x", is_active: 0, val: "blue" })]);
    await expect(getFeatureValue("x")).resolves.toBeNull();
    getFeatureFlagsMock.mockResolvedValue([flag({ key: "other", val: "blue" })]);
    await expect(getFeatureValue("x")).resolves.toBeNull();
  });

  it("returns null when getFeatureFlags rejects", async () => {
    getFeatureFlagsMock.mockRejectedValue(new Error("boom"));
    await expect(getFeatureValue("x")).resolves.toBeNull();
  });
});
