import { describe, it, expect } from "vitest";
import {
  nodeColors,
  nodeBgColors,
  nodeIconColors,
  getNodeColor,
  getNodeBgColor,
  getNodeIconColor,
} from "@/views/AIAgents/Workflows/utils/nodeColors";

describe("getNodeColor", () => {
  it("returns the mapped color for each known category", () => {
    for (const [category, color] of Object.entries(nodeColors)) {
      expect(getNodeColor(category)).toBe(color);
    }
  });

  it("returns specific expected values", () => {
    expect(getNodeColor("ai")).toBe("pink-600");
    expect(getNodeColor("routing")).toBe("orange-500");
  });

  it("falls back to the default for unknown categories", () => {
    expect(getNodeColor("does-not-exist")).toBe(nodeColors.default);
    expect(getNodeColor("")).toBe(nodeColors.default);
  });
});

describe("getNodeBgColor", () => {
  it("returns the mapped background for a known category", () => {
    expect(getNodeBgColor("ai")).toBe("bg-pink-50 dark:bg-[#330f21]");
    expect(getNodeBgColor("tools")).toBe(nodeBgColors.tools);
  });

  it("falls back to the default for unknown categories", () => {
    expect(getNodeBgColor("nope")).toBe(nodeBgColors.default);
  });
});

describe("getNodeIconColor", () => {
  it("returns the mapped icon color for a known category", () => {
    expect(getNodeIconColor("ai")).toBe("text-pink-600");
    expect(getNodeIconColor("integrations")).toBe(nodeIconColors.integrations);
  });

  it("falls back to the default for unknown categories", () => {
    expect(getNodeIconColor("nope")).toBe(nodeIconColors.default);
  });
});
