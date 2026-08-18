import { describe, it, expect } from "vitest";
import { replaceVariablesWithInputs } from "@/views/AIAgents/Workflows/utils/apiHelpers";

describe("replaceVariablesWithInputs", () => {
  it("replaces both @variable and {{variable}} forms", () => {
    expect(
      replaceVariablesWithInputs("Hello {{name}} and @name!", { name: "World" })
    ).toBe("Hello World and World!");
  });

  it("replaces every occurrence globally", () => {
    expect(replaceVariablesWithInputs("{{x}} {{x}} @x", { x: "1" })).toBe("1 1 1");
  });

  it("respects a word boundary for @variable (no partial match)", () => {
    expect(replaceVariablesWithInputs("@nameX", { name: "V" })).toBe("@nameX");
    expect(replaceVariablesWithInputs("@name.", { name: "V" })).toBe("V.");
  });

  it("only matches {{name}} without internal spaces", () => {
    expect(replaceVariablesWithInputs("{{ name }}", { name: "V" })).toBe("{{ name }}");
  });

  it("leaves text unchanged when a key is not present", () => {
    expect(replaceVariablesWithInputs("nothing here", { name: "V" })).toBe(
      "nothing here"
    );
  });

  it("returns the text unchanged with empty inputs", () => {
    expect(replaceVariablesWithInputs("{{a}} @b", {})).toBe("{{a}} @b");
  });

  it("applies multiple keys", () => {
    expect(
      replaceVariablesWithInputs("{{first}} {{second}}", {
        first: "1",
        second: "2",
      })
    ).toBe("1 2");
  });
});
