import { describe, it, expect } from "vitest";
import {
  FEATURE_ENGINEERING_STRATEGY_OPTIONS,
  isRetiredFeatureStrategy,
  strategyOptionsFor,
} from "@/views/AIAgents/Workflows/nodeDialogs/training/featureEngineeringStrategies";

describe("feature engineering strategies", () => {
  it("normalize and standardize can't be picked for new features", () => {
    const values = FEATURE_ENGINEERING_STRATEGY_OPTIONS.map((o) => o.value);
    expect(values).toEqual(["custom_expression", "bin_numeric", "polynomial"]);
  });

  it("a feature saved with a retired strategy still shows it, marked retired", () => {
    const options = strategyOptionsFor("standardize");
    expect(options.at(-1)).toEqual({ value: "standardize", label: "Standardize (retired)" });
    expect(isRetiredFeatureStrategy("standardize")).toBe(true);
    expect(isRetiredFeatureStrategy("normalize")).toBe(true);
  });

  it("a current strategy gets only the current options", () => {
    expect(strategyOptionsFor("polynomial")).toEqual(FEATURE_ENGINEERING_STRATEGY_OPTIONS);
    expect(isRetiredFeatureStrategy("custom_expression")).toBe(false);
  });
});
