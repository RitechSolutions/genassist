import { describe, it, expect } from "vitest";
import {
  FEATURE_ENGINEERING_STRATEGY_OPTIONS,
  defaultsForStrategy,
  featureOutputColumns,
  isColumnTransformStrategy,
  isRetiredFeatureStrategy,
  outputColumnsHint,
  strategyOptionsFor,
} from "@/views/AIAgents/Workflows/nodeDialogs/training/featureEngineeringStrategies";

describe("feature engineering strategies", () => {
  it("normalize and standardize can't be picked for new features", () => {
    const values = FEATURE_ENGINEERING_STRATEGY_OPTIONS.map((o) => o.value);
    expect(values).toEqual([
      "custom_expression",
      "bin_numeric",
      "polynomial",
      "datetime_features",
      "log_transform",
      "math_transform",
      "quantile_transform",
      "power_transform",
      "pca",
    ]);
    expect(values).not.toContain("normalize");
    expect(values).not.toContain("standardize");
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

  it("the four column transforms start from valid defaults", () => {
    expect(defaultsForStrategy("log_transform")).toEqual({ replaceSourceColumns: false });
    expect(defaultsForStrategy("quantile_transform")).toEqual({
      quantileOutputDistribution: "uniform",
      nQuantiles: 1000,
      replaceSourceColumns: false,
    });
    expect(defaultsForStrategy("power_transform")).toEqual({
      powerMethod: "yeo-johnson",
      replaceSourceColumns: false,
    });
    expect(defaultsForStrategy("pca")).toEqual({
      pcaComponents: 2,
      pcaStandardize: true,
      replaceSourceColumns: true,
    });
    expect(defaultsForStrategy("custom_expression")).toEqual({});
    expect(["log_transform", "quantile_transform", "power_transform", "pca"].every((s) =>
      isColumnTransformStrategy(s as never)
    )).toBe(true);
    expect(isColumnTransformStrategy("polynomial")).toBe(false);
  });

  it("math function and date-time features start from valid defaults", () => {
    expect(defaultsForStrategy("math_transform")).toEqual({ mathFunction: "sqrt", replaceSourceColumns: false });
    expect(isColumnTransformStrategy("math_transform")).toBe(true);
    expect(defaultsForStrategy("datetime_features")).toEqual({
      datetimeParts: ["year", "month", "day", "day_of_week", "quarter", "hour", "is_weekend"],
    });
    expect(isColumnTransformStrategy("datetime_features")).toBe(false);
  });

  it("describes the output column names", () => {
    const base = { id: "f", newColumnName: "t" };
    expect(outputColumnsHint({ ...base, strategy: "log_transform", sourceColumns: ["a"] })).toBe("Creates t");
    expect(outputColumnsHint({ ...base, strategy: "log_transform", sourceColumns: ["a", "b"] })).toBe(
      "Creates t_a, t_b"
    );
    expect(outputColumnsHint({ ...base, strategy: "pca", sourceColumns: ["a", "b"] })).toBe("Creates t_1, t_2, ...");
    expect(
      outputColumnsHint({ ...base, strategy: "datetime_features", datetimeParts: ["year", "is_weekend"] })
    ).toBe("Creates t_year, t_is_weekend");
    expect(outputColumnsHint({ ...base, strategy: "datetime_features", datetimeParts: ["month", "hour"] })).toBe(
      "Creates t_month, t_hour (t_hour only if the values have a time of day)"
    );
    expect(outputColumnsHint({ ...base, strategy: "datetime_features", datetimeParts: [] })).toBe(
      "Choose at least one part"
    );
  });

  it("offers a date-time feature's part columns, not its bare name, to later features", () => {
    const base = { id: "f", newColumnName: "ts" };
    expect(featureOutputColumns({ ...base, strategy: "datetime_features", datetimeParts: ["month", "hour"] })).toEqual([
      "ts_month",
      "ts_hour",
    ]);
    expect(featureOutputColumns({ ...base, strategy: "datetime_features" })).toHaveLength(7);
    expect(featureOutputColumns({ ...base, strategy: "custom_expression" })).toEqual(["ts"]);
    expect(featureOutputColumns({ ...base, newColumnName: "", strategy: "custom_expression" })).toEqual([]);
  });
});
