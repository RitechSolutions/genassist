import { describe, expect, it } from "vitest";
import { optimizationConfigErrors, withoutOtherMethodsSettings } from "@/views/AIAgents/Workflows/nodeDialogs/training/optimizationLimits";

describe("optimizationConfigErrors (TM-17)", () => {
  it("refuses CV Folds below 2 or above 10", () => {
    expect(optimizationConfigErrors("random_search", { cvFolds: 1 }).cvFolds).toMatch(/from 2 to 10/);
    expect(optimizationConfigErrors("random_search", { cvFolds: 11 }).cvFolds).toMatch(/from 2 to 10/);
    expect(optimizationConfigErrors("grid_search", { cvFolds: 2.5 }).cvFolds).toBeDefined();
  });

  it("accepts CV Folds from 2 to 10 and an unset value", () => {
    expect(optimizationConfigErrors("grid_search", { cvFolds: 2 })).toEqual({});
    expect(optimizationConfigErrors("grid_search", { cvFolds: 10 })).toEqual({});
    expect(optimizationConfigErrors("grid_search", {})).toEqual({});
  });

  it("refuses Trials above 200 or below 1 for Bayesian Optimization", () => {
    expect(optimizationConfigErrors("bayesian_optimization", { nTrials: 201 }).nTrials).toMatch(/from 1 to 200/);
    expect(optimizationConfigErrors("bayesian_optimization", { nTrials: 0 }).nTrials).toBeDefined();
    expect(optimizationConfigErrors("bayesian_optimization", { nTrials: 200 })).toEqual({});
  });

  it("refuses Iterations above 200 for Random Search", () => {
    expect(optimizationConfigErrors("random_search", { nIter: 500 }).nIter).toBeDefined();
  });

  it("ignores a setting the chosen method doesn't use", () => {
    expect(optimizationConfigErrors("random_search", { nTrials: 500 })).toEqual({});
    expect(optimizationConfigErrors("none", { cvFolds: 1 })).toEqual({});
  });

  it("leaves a templated value to the run", () => {
    const config = { cvFolds: "{{folds}}" } as unknown as Record<string, number>;
    expect(optimizationConfigErrors("grid_search", config)).toEqual({});
  });

  it("drops the settings of other methods when the method changes", () => {
    const config = { cvFolds: 5, scoring: "f1", nIter: 0, nTrials: 0, timeoutSeconds: 0, gridPoints: 9 };
    expect(withoutOtherMethodsSettings("random_search", config)).toEqual({ cvFolds: 5, scoring: "f1", nIter: 0 });
    expect(withoutOtherMethodsSettings("bayesian_optimization", config)).toEqual({
      cvFolds: 5,
      scoring: "f1",
      nTrials: 0,
      timeoutSeconds: 0,
    });
  });
});
