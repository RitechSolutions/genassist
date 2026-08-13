import { describe, expect, it } from "vitest";
import {
  getChangeBadgeColor,
  getChangeIconColor,
  getChangeTextColor,
} from "@/views/Analytics/helpers/badgeColors";

describe("getChangeBadgeColor", () => {
  it("maps each change type to a background class", () => {
    expect(getChangeBadgeColor("increase")).toBe("bg-green-200");
    expect(getChangeBadgeColor("decrease")).toBe("bg-red-200");
    expect(getChangeBadgeColor("neutral")).toBe("bg-zinc-200");
  });
});

describe("getChangeTextColor", () => {
  it("maps each change type to a text class", () => {
    expect(getChangeTextColor("increase")).toBe("text-green-600");
    expect(getChangeTextColor("decrease")).toBe("text-red-600");
    expect(getChangeTextColor("neutral")).toBe("text-zinc-600");
  });
});

describe("getChangeIconColor", () => {
  it("maps each change type to an icon color class", () => {
    expect(getChangeIconColor("increase")).toBe("text-green-700");
    expect(getChangeIconColor("decrease")).toBe("text-red-700");
    expect(getChangeIconColor("neutral")).toBe("text-zinc-600");
  });
});
