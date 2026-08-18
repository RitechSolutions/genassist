import { describe, it, expect } from "vitest";
import { generatePythonTemplate } from "@/views/AIAgents/Workflows/utils/tools";

describe("generatePythonTemplate", () => {
  it("returns a non-empty string", () => {
    const tpl = generatePythonTemplate();
    expect(typeof tpl).toBe("string");
    expect(tpl.length).toBeGreaterThan(0);
  });

  it("includes the expected template markers", () => {
    const tpl = generatePythonTemplate();
    expect(tpl).toContain("# Generated Python function template");
    expect(tpl).toContain("parameter1 = params.get('parameter1', '')");
    expect(tpl).toContain("result = {");
    expect(tpl).toContain("except Exception as e:");
    expect(tpl).toContain("traceback.format_exc()");
  });

  it("is deterministic across calls", () => {
    expect(generatePythonTemplate()).toBe(generatePythonTemplate());
  });
});
