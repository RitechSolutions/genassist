import { describe, expect, it } from "vitest";
import { pricedCostPerCall } from "@/views/Analytics/helpers/llmUsageMetrics";

describe("pricedCostPerCall", () => {
  it("divides the priced cost by priced calls only", () => {
    expect(pricedCostPerCall({ cost_usd: 1, calls: 10, unpriced_calls: 5 })).toBe(0.2);
  });

  it("is null when no call was priced", () => {
    expect(pricedCostPerCall({ cost_usd: 0, calls: 4, unpriced_calls: 4 })).toBeNull();
    expect(pricedCostPerCall({ cost_usd: 0, calls: 0, unpriced_calls: 0 })).toBeNull();
  });
});
