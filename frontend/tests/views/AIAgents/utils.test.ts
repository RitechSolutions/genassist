import { describe, it, expect } from "vitest";
import type { Translation } from "@/interfaces/translation.interface";
import { pairsToObject, objectToPairs, getTranslationCount } from "@/views/AIAgents/utils";

describe("pairsToObject", () => {
  it("JSON-parses string values that are valid JSON", () => {
    expect(pairsToObject([{ key: "a", value: "123" }])).toEqual({ a: 123 });
    expect(pairsToObject([{ key: "a", value: "true" }])).toEqual({ a: true });
    expect(pairsToObject([{ key: "a", value: "null" }])).toEqual({ a: null });
    expect(pairsToObject([{ key: "a", value: '{"x":1}' }])).toEqual({ a: { x: 1 } });
    expect(pairsToObject([{ key: "a", value: "[1,2]" }])).toEqual({ a: [1, 2] });
    expect(pairsToObject([{ key: "a", value: '"quoted"' }])).toEqual({ a: "quoted" });
  });

  it("keeps the raw string when JSON.parse fails", () => {
    expect(pairsToObject([{ key: "a", value: "hello" }])).toEqual({ a: "hello" });
  });

  it("passes non-string values through untouched", () => {
    expect(pairsToObject([{ key: "a", value: 42 }])).toEqual({ a: 42 });
    expect(pairsToObject([{ key: "a", value: true }])).toEqual({ a: true });
    expect(pairsToObject([{ key: "a", value: null }])).toEqual({ a: null });
  });

  it("handles empty input and lets later keys overwrite earlier ones", () => {
    expect(pairsToObject([])).toEqual({});
    expect(
      pairsToObject([
        { key: "a", value: "1" },
        { key: "a", value: "2" },
      ])
    ).toEqual({ a: 2 });
  });
});

describe("objectToPairs", () => {
  it("converts entries to {key, value} preserving value types", () => {
    expect(objectToPairs({ a: 1, b: "x" })).toEqual([
      { key: "a", value: 1 },
      { key: "b", value: "x" },
    ]);
  });

  it("returns [] for an empty object", () => {
    expect(objectToPairs({})).toEqual([]);
  });
});

describe("getTranslationCount", () => {
  const t = (translations: Record<string, unknown>): Translation =>
    ({ key: "k", translations }) as unknown as Translation;

  it("returns 0 for null", () => {
    expect(getTranslationCount(null)).toBe(0);
  });

  it("returns 0 for an empty translations map", () => {
    expect(getTranslationCount(t({}))).toBe(0);
  });

  it("counts non-empty string translations", () => {
    expect(getTranslationCount(t({ en: "Hello", es: "Hola" }))).toBe(2);
  });

  it("excludes empty and whitespace-only strings", () => {
    expect(getTranslationCount(t({ en: "Hello", es: "", fr: "   " }))).toBe(1);
  });

  it("excludes non-string values", () => {
    expect(getTranslationCount(t({ en: "Hi", n: 5, b: true, z: null }))).toBe(1);
  });
});
