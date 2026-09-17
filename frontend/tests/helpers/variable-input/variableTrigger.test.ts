import { describe, expect, it } from "vitest";
import {
  detectVariableTrigger,
  replaceTriggerWithReference,
} from "@/helpers/variable-input/variableTrigger";

describe("detectVariableTrigger", () => {
  it("detects an empty trigger right after typing '{{'", () => {
    expect(detectVariableTrigger("{{", 2)).toEqual({ start: 0, query: "" });
  });

  it("captures the query typed after the braces", () => {
    expect(detectVariableTrigger("Hello {{clas", 12)).toEqual({
      start: 6,
      query: "clas",
    });
  });

  it("keeps dots in the query so nested paths can be searched", () => {
    expect(detectVariableTrigger("{{node.pre", 10)).toEqual({
      start: 0,
      query: "node.pre",
    });
  });

  it("returns null when there is no opening brace pair", () => {
    expect(detectVariableTrigger("plain text", 10)).toBeNull();
  });

  it("returns null once the variable has been closed", () => {
    expect(detectVariableTrigger("{{node.value}}", 14)).toBeNull();
  });

  it("returns null when a stray closing brace follows the trigger", () => {
    expect(detectVariableTrigger("{{node}", 7)).toBeNull();
  });

  it("returns null when a newline separates the braces from the caret", () => {
    expect(detectVariableTrigger("{{node\nmore", 11)).toBeNull();
  });

  it("uses the nearest opening braces when several are present", () => {
    expect(detectVariableTrigger("{{a}} and {{b", 13)).toEqual({
      start: 10,
      query: "b",
    });
  });

  it("ignores braces that start after the caret", () => {
    expect(detectVariableTrigger("abc{{def", 3)).toBeNull();
  });

  it("clamps a caret beyond the value length", () => {
    expect(detectVariableTrigger("{{ab", 99)).toEqual({ start: 0, query: "ab" });
  });

  it("returns null for a non-string value", () => {
    expect(
      detectVariableTrigger(undefined as unknown as string, 0)
    ).toBeNull();
  });
});

describe("replaceTriggerWithReference", () => {
  it("replaces the typed trigger with the full reference", () => {
    const trigger = { start: 6, query: "clas" };
    expect(
      replaceTriggerWithReference("Hello {{clas", trigger, "{{classifier}}", 12)
    ).toEqual({ value: "Hello {{classifier}}", cursor: 20 });
  });

  it("keeps the text that follows the caret", () => {
    const trigger = { start: 0, query: "n" };
    expect(
      replaceTriggerWithReference("{{n rest", trigger, "{{node}}", 3)
    ).toEqual({ value: "{{node}} rest", cursor: 8 });
  });

  it("absorbs a closing '}}' the user already typed", () => {
    const trigger = { start: 0, query: "n" };
    expect(
      replaceTriggerWithReference("{{n}}", trigger, "{{node}}", 3)
    ).toEqual({ value: "{{node}}", cursor: 8 });
  });

  it("leaves a single trailing brace alone", () => {
    const trigger = { start: 0, query: "n" };
    expect(replaceTriggerWithReference("{{n}", trigger, "{{node}}", 3)).toEqual({
      value: "{{node}}}",
      cursor: 8,
    });
  });
});
