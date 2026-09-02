import { describe, expect, it } from "vitest";
import { parseValueToSegments } from "@/helpers/variable-input/templateVariableHighlight";

describe("parseValueToSegments", () => {
  it("returns an empty array for an empty string", () => {
    expect(parseValueToSegments("")).toEqual([]);
  });

  it("returns a single text segment for a plain string", () => {
    expect(parseValueToSegments("hello world")).toEqual([
      { type: "text", content: "hello world" },
    ]);
  });

  it("returns a single variable segment for a lone {{variable}}", () => {
    expect(parseValueToSegments("{{name}}")).toEqual([
      { type: "variable", content: "{{name}}" },
    ]);
  });

  it("splits surrounding text from a variable", () => {
    expect(parseValueToSegments("Hello {{name}}!")).toEqual([
      { type: "text", content: "Hello " },
      { type: "variable", content: "{{name}}" },
      { type: "text", content: "!" },
    ]);
  });

  it("handles two adjacent variables with no text between them", () => {
    expect(parseValueToSegments("{{a}}{{b}}")).toEqual([
      { type: "variable", content: "{{a}}" },
      { type: "variable", content: "{{b}}" },
    ]);
  });

  it("handles variables separated by text", () => {
    expect(parseValueToSegments("{{a}} and {{b}}")).toEqual([
      { type: "variable", content: "{{a}}" },
      { type: "text", content: " and " },
      { type: "variable", content: "{{b}}" },
    ]);
  });

  it("preserves internal whitespace inside a variable", () => {
    expect(parseValueToSegments("x {{ a b }} y")).toEqual([
      { type: "text", content: "x " },
      { type: "variable", content: "{{ a b }}" },
      { type: "text", content: " y" },
    ]);
  });

  it("treats empty braces {{}} as plain text (regex requires content)", () => {
    expect(parseValueToSegments("{{}}")).toEqual([
      { type: "text", content: "{{}}" },
    ]);
  });

  it("treats unterminated braces as text", () => {
    expect(parseValueToSegments("{{incomplete")).toEqual([
      { type: "text", content: "{{incomplete" },
    ]);
  });

  it("keeps a trailing stray brace as a separate text segment", () => {
    expect(parseValueToSegments("{{a}}}")).toEqual([
      { type: "variable", content: "{{a}}" },
      { type: "text", content: "}" },
    ]);
  });

  it("does not carry regex lastIndex state across calls", () => {
    // VARIABLE_PATTERN is a non-global regex, so repeated calls stay consistent.
    const first = parseValueToSegments("{{a}}");
    const second = parseValueToSegments("{{a}}");
    expect(first).toEqual(second);
    expect(second).toEqual([{ type: "variable", content: "{{a}}" }]);
  });
});
