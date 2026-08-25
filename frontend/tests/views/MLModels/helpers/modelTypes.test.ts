import { describe, expect, it } from "vitest";
import { MODEL_TYPE_OPTIONS, modelTypeLabel } from "@/views/MLModels/helpers/modelTypes";

describe("modelTypeLabel", () => {
  it("labels every option in the shared vocabulary", () => {
    for (const option of MODEL_TYPE_OPTIONS) {
      expect(modelTypeLabel(option.value)).toBe(option.label);
    }
  });

  it("falls back to the raw value for unknown types", () => {
    expect(modelTypeLabel("catboost")).toBe("catboost");
  });

  it("renders an em dash for missing types", () => {
    expect(modelTypeLabel(null)).toBe("—");
    expect(modelTypeLabel(undefined)).toBe("—");
    expect(modelTypeLabel("")).toBe("—");
  });
});
