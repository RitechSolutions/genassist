import { describe, it, expect } from "vitest";
import {
  defaultMaxIterations,
  LOOP_MAX_ITERATIONS_CAP,
  maxIterationsForMode,
  normalizeMaxIterations,
} from "@/views/AIAgents/Workflows/nodeTypes/router/loopConfig";

describe("loop max iterations", () => {
  it("defaults per mode", () => {
    expect(defaultMaxIterations("forEach")).toBe(100);
    expect(defaultMaxIterations("repeatUntil")).toBe(5);
    expect(defaultMaxIterations(undefined)).toBe(100);
  });

  it("swaps an untouched default when the mode changes but keeps a chosen value", () => {
    expect(maxIterationsForMode(100, "forEach", "repeatUntil")).toBe(5);
    expect(maxIterationsForMode(5, "repeatUntil", "forEach")).toBe(100);
    expect(maxIterationsForMode(undefined, "forEach", "repeatUntil")).toBe(5);
    expect(maxIterationsForMode(12, "forEach", "repeatUntil")).toBe(12);
  });

  it("normalizes what was typed to a whole number within the server cap", () => {
    expect(normalizeMaxIterations("7", "forEach")).toBe(7);
    expect(normalizeMaxIterations("7.9", "forEach")).toBe(7);
    expect(normalizeMaxIterations("", "repeatUntil")).toBe(5);
    expect(normalizeMaxIterations("0", "forEach")).toBe(100);
    expect(normalizeMaxIterations("abc", "forEach")).toBe(100);
    expect(normalizeMaxIterations("999999", "forEach")).toBe(LOOP_MAX_ITERATIONS_CAP);
  });
});

describe("loop number fields", () => {
  it("normalizes whole numbers with a floor and a fallback", async () => {
    const { normalizeWholeNumber } = await import("@/views/AIAgents/Workflows/nodeTypes/router/loopConfig");
    expect(normalizeWholeNumber("5", 1, 1)).toBe(5);
    expect(normalizeWholeNumber("2.9", 1, 1)).toBe(2);
    expect(normalizeWholeNumber("0", 1, 1)).toBe(1);
    expect(normalizeWholeNumber("", 1, 1)).toBe(1);
    expect(normalizeWholeNumber("x", 1, 1)).toBe(1);
  });

  it("normalizes seconds, allowing fractions and capping at the maximum", async () => {
    const { normalizeSeconds, LOOP_MAX_DELAY_SECONDS } = await import(
      "@/views/AIAgents/Workflows/nodeTypes/router/loopConfig"
    );
    expect(normalizeSeconds("1.5")).toBe(1.5);
    expect(normalizeSeconds("")).toBe(0);
    expect(normalizeSeconds("-3")).toBe(0);
    expect(normalizeSeconds("abc")).toBe(0);
    expect(normalizeSeconds("600", LOOP_MAX_DELAY_SECONDS)).toBe(60);
    expect(normalizeSeconds("600")).toBe(600);
  });
});
