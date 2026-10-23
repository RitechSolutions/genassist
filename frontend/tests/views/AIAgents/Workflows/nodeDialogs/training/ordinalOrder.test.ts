import { describe, it, expect } from "vitest";
import {
  mappingFromOrder,
  orderFromMapping,
} from "@/views/AIAgents/Workflows/nodeDialogs/training/ordinalOrder";

describe("ordinal order helpers (DP-5)", () => {
  it("turns a value order into positions 0, 1, 2, ...", () => {
    expect(mappingFromOrder(["Low", "Medium", "High"])).toEqual({ Low: 0, Medium: 1, High: 2 });
  });

  it("reads a mapping back in position order", () => {
    expect(orderFromMapping({ High: 2, Low: 0, Medium: 1 })).toEqual(["Low", "Medium", "High"]);
  });

  it("reads a mapping with non-consecutive positions in order", () => {
    expect(orderFromMapping({ small: 1, large: 3, medium: 2 })).toEqual(["small", "medium", "large"]);
  });

  it("treats a missing mapping as an empty order", () => {
    expect(orderFromMapping(undefined)).toEqual([]);
    expect(mappingFromOrder([])).toEqual({});
  });
});
