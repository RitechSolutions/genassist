import { describe, expect, it } from "vitest";
import { accuracyColorClass } from "@/views/TestSuites/helpers/evaluationMetrics";

describe("accuracyColorClass", () => {
  it("is green at or above 0.9", () => {
    expect(accuracyColorClass(0.9)).toBe("text-green-600");
    expect(accuracyColorClass(1)).toBe("text-green-600");
  });

  it("is amber between 0.7 and 0.9", () => {
    expect(accuracyColorClass(0.7)).toBe("text-amber-600");
    expect(accuracyColorClass(0.85)).toBe("text-amber-600");
  });

  it("is red below 0.7", () => {
    expect(accuracyColorClass(0.69)).toBe("text-red-600");
    expect(accuracyColorClass(0)).toBe("text-red-600");
  });
});
