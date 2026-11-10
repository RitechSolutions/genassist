import { describe, it, expect } from "vitest";
import { onlyTaskTypeFor } from "@/views/AIAgents/Workflows/nodeDialogs/training/scoringOptions";

describe("onlyTaskTypeFor - Task Type locked to what the model supports", () => {
  it.each(["linear_regression", "ridge_regression", "lasso_regression", "elastic_net"])(
    "%s only supports regression",
    (modelType) => {
      expect(onlyTaskTypeFor(modelType)).toBe("regression");
    }
  );

  it("logistic_regression only supports classification", () => {
    expect(onlyTaskTypeFor("logistic_regression")).toBe("classification");
  });

  it("models that support both leave Task Type free", () => {
    expect(onlyTaskTypeFor("random_forest")).toBeUndefined();
    expect(onlyTaskTypeFor(undefined)).toBeUndefined();
  });
});
