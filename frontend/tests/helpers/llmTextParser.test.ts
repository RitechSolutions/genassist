import { describe, expect, it } from "vitest";
import {
  tryParseJson,
  findCodeFenceBlocks,
  findBalancedJsonCandidate,
  isRecord,
} from "@/helpers/llmTextParser";

describe("tryParseJson", () => {
  it("parses valid JSON", () => {
    expect(tryParseJson('{"a":1}')).toEqual({ a: 1 });
    expect(tryParseJson("[1,2]")).toEqual([1, 2]);
  });

  it("returns null on invalid JSON", () => {
    expect(tryParseJson("not json")).toBeNull();
    expect(tryParseJson("")).toBeNull();
  });
});

describe("findCodeFenceBlocks", () => {
  it("extracts a single ```json block, trimmed", () => {
    const text = "before\n```json\n{\"a\":1}\n```\nafter";
    expect(findCodeFenceBlocks(text)).toEqual(['{"a":1}']);
  });

  it("extracts multiple blocks including bare fences", () => {
    const text = "```json\nA\n```\nmid\n```\nB\n```";
    expect(findCodeFenceBlocks(text)).toEqual(["A", "B"]);
  });

  it("returns an empty array when there are no fences", () => {
    expect(findCodeFenceBlocks("plain text")).toEqual([]);
  });
});

describe("findBalancedJsonCandidate", () => {
  it("returns the balanced object starting at the index", () => {
    expect(findBalancedJsonCandidate('{"a":1}', 0)).toBe('{"a":1}');
  });

  it("walks nested structures", () => {
    expect(findBalancedJsonCandidate('{"a":{"b":2}}', 0)).toBe('{"a":{"b":2}}');
    expect(findBalancedJsonCandidate("[1,2,[3]]", 0)).toBe("[1,2,[3]]");
  });

  it("ignores braces inside strings", () => {
    expect(findBalancedJsonCandidate('{"k":"}"}', 0)).toBe('{"k":"}"}');
  });

  it("respects escaped quotes inside strings", () => {
    const text = '{"a":"x\\"y"}';
    expect(findBalancedJsonCandidate(text, 0)).toBe(text);
  });

  it("starts from an arbitrary index", () => {
    const text = 'prefix {"a":1} suffix';
    const start = text.indexOf("{");
    expect(findBalancedJsonCandidate(text, start)).toBe('{"a":1}');
  });

  it("returns null when it never balances", () => {
    expect(findBalancedJsonCandidate('{"a":1', 0)).toBeNull();
  });
});

describe("isRecord", () => {
  it("is true only for plain objects", () => {
    expect(isRecord({})).toBe(true);
    expect(isRecord({ a: 1 })).toBe(true);
  });

  it("is false for arrays, null and primitives", () => {
    expect(isRecord([])).toBe(false);
    expect(isRecord(null)).toBe(false);
    expect(isRecord(undefined)).toBe(false);
    expect(isRecord("s")).toBe(false);
    expect(isRecord(5)).toBe(false);
  });
});
