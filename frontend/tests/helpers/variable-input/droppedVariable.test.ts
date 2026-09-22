import { describe, expect, it } from "vitest";
import {
  formatVariableReference,
  buildArrayItemPath,
  isPlainObject,
  isPrimitiveJsonValue,
  parseDroppedVariable,
} from "@/helpers/variable-input/droppedVariable";

// A minimal DataTransfer stand-in: only getData is exercised.
function makeDataTransfer(map: Record<string, string>): DataTransfer {
  return {
    getData: (type: string) => map[type] ?? "",
  } as unknown as DataTransfer;
}

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

describe("isPrimitiveJsonValue", () => {
  it("is true for null, primitives, and dates", () => {
    expect(isPrimitiveJsonValue(null)).toBe(true);
    expect(isPrimitiveJsonValue("str")).toBe(true);
    expect(isPrimitiveJsonValue(42)).toBe(true);
    expect(isPrimitiveJsonValue(true)).toBe(true);
    expect(isPrimitiveJsonValue(undefined)).toBe(true);
    expect(isPrimitiveJsonValue(new Date())).toBe(true);
  });

  it("is true for functions (typeof is not 'object')", () => {
    expect(isPrimitiveJsonValue(() => {})).toBe(true);
  });

  it("is false for plain objects and arrays", () => {
    expect(isPrimitiveJsonValue({})).toBe(false);
    expect(isPrimitiveJsonValue([])).toBe(false);
  });
});

describe("parseDroppedVariable", () => {
  it("parses an application/json payload with a primitive value", () => {
    const dt = makeDataTransfer({
      "application/json": JSON.stringify({ path: "source.x", value: 42 }),
    });
    expect(parseDroppedVariable(dt)).toEqual({
      path: "source.x",
      reference: "{{source.x}}",
      value: 42,
    });
  });

  it("parses an application/json payload with an object value", () => {
    const dt = makeDataTransfer({
      "application/json": JSON.stringify({
        path: "a.b",
        value: { nested: true },
      }),
    });
    expect(parseDroppedVariable(dt)).toEqual({
      path: "a.b",
      reference: "{{a.b}}",
      value: { nested: true },
    });
  });

  it("prefers json over text/plain when both are present", () => {
    const dt = makeDataTransfer({
      "application/json": JSON.stringify({ path: "json.path", value: 1 }),
      "text/plain": "text.path",
    });
    expect(parseDroppedVariable(dt)).toEqual({
      path: "json.path",
      reference: "{{json.path}}",
      value: 1,
    });
  });

  it("falls back to text/plain, deriving the path from the reference", () => {
    const dt = makeDataTransfer({ "text/plain": "foo.bar" });
    expect(parseDroppedVariable(dt)).toEqual({
      path: "foo.bar",
      reference: "{{foo.bar}}",
      value: undefined,
    });
  });

  it("strips braces from an already-wrapped text/plain value", () => {
    const dt = makeDataTransfer({ "text/plain": "{{foo}}" });
    expect(parseDroppedVariable(dt)).toEqual({
      path: "foo",
      reference: "{{foo}}",
      value: undefined,
    });
  });

  it("trims a text/plain value before wrapping and slicing", () => {
    const dt = makeDataTransfer({ "text/plain": "  x.y  " });
    expect(parseDroppedVariable(dt)).toEqual({
      path: "x.y",
      reference: "{{x.y}}",
      value: undefined,
    });
  });

  it("returns null when neither data type is present", () => {
    expect(parseDroppedVariable(makeDataTransfer({}))).toBeNull();
  });
});
