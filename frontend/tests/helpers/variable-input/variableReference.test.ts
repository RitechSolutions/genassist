import { describe, expect, it } from "vitest";
import {
  formatVariableReference,
  buildArrayItemPath,
  isPlainObject,
  insertReferenceAt,
} from "@/helpers/variable-input/variableReference";

describe("formatVariableReference", () => {
  it("wraps a bare path in template braces", () => {
    expect(formatVariableReference("source.x")).toBe("{{source.x}}");
  });

  it("trims surrounding whitespace before wrapping", () => {
    expect(formatVariableReference("  source.x  ")).toBe("{{source.x}}");
  });

  it("leaves an already-wrapped path unchanged", () => {
    expect(formatVariableReference("{{source.x}}")).toBe("{{source.x}}");
  });

  it("trims then returns an already-wrapped path unchanged", () => {
    expect(formatVariableReference("  {{source.x}}  ")).toBe("{{source.x}}");
  });

  it("wraps an empty string into empty braces", () => {
    expect(formatVariableReference("")).toBe("{{}}");
  });

  it("wraps when only the opening braces are present", () => {
    expect(formatVariableReference("{{only start")).toBe("{{{{only start}}");
  });
});

describe("buildArrayItemPath", () => {
  it("builds an indexed path", () => {
    expect(buildArrayItemPath("source.prediction", 0)).toBe(
      "source.prediction[0]"
    );
  });

  it("supports arbitrary indexes", () => {
    expect(buildArrayItemPath("a", 5)).toBe("a[5]");
    expect(buildArrayItemPath("a", -1)).toBe("a[-1]");
  });
});

describe("isPlainObject", () => {
  it("is true for plain objects", () => {
    expect(isPlainObject({})).toBe(true);
    expect(isPlainObject({ a: 1 })).toBe(true);
  });

  it("is false for arrays, null, and dates", () => {
    expect(isPlainObject([])).toBe(false);
    expect(isPlainObject(null)).toBe(false);
    expect(isPlainObject(new Date())).toBe(false);
  });

  it("is false for primitives and functions", () => {
    expect(isPlainObject("str")).toBe(false);
    expect(isPlainObject(42)).toBe(false);
    expect(isPlainObject(undefined)).toBe(false);
    expect(isPlainObject(() => {})).toBe(false);
  });
});

describe("insertReferenceAt", () => {
  it("returns the reference alone for an empty field", () => {
    expect(insertReferenceAt("", "{{a}}", 0)).toEqual({
      value: "{{a}}",
      cursor: 5,
    });
  });

  it("appends without a leading space after whitespace", () => {
    expect(insertReferenceAt("Hi ", "{{a}}", 3)).toEqual({
      value: "Hi {{a}}",
      cursor: 8,
    });
  });

  it("adds a separating space when it would fuse with a word", () => {
    expect(insertReferenceAt("Hi", "{{a}}", 2)).toEqual({
      value: "Hi {{a}}",
      cursor: 8,
    });
  });

  it("pads both sides when inserting mid-word", () => {
    expect(insertReferenceAt("ab", "{{x}}", 1)).toEqual({
      value: "a {{x}} b",
      cursor: 7,
    });
  });

  it("skips padding only on the side that touches punctuation", () => {
    expect(insertReferenceAt("a,b", "{{x}}", 2)).toEqual({
      value: "a,{{x}} b",
      cursor: 7,
    });
    expect(insertReferenceAt("a,b", "{{x}}", 1)).toEqual({
      value: "a {{x}},b",
      cursor: 7,
    });
  });

  it("never pads at the very start of the value", () => {
    expect(insertReferenceAt("abc", "{{x}}", 0)).toEqual({
      value: "{{x}} abc",
      cursor: 5,
    });
  });

  it("clamps a position past the end of the value", () => {
    expect(insertReferenceAt("ab ", "{{x}}", 99)).toEqual({
      value: "ab {{x}}",
      cursor: 8,
    });
  });

  it("puts the caret after the reference including any added space", () => {
    const result = insertReferenceAt("word", "{{x}}", 4);
    expect(result.value.slice(0, result.cursor)).toBe("word {{x}}");
  });
});
