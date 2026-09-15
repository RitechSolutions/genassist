import { describe, expect, it } from "vitest";
import {
  answerOf,
  answerToExpected,
  hasExpected,
  isPlainRecord,
  parseRecordObject,
  questionOf,
  questionToInput,
} from "@/views/TestSuites/helpers/recordFields";

describe("questionOf", () => {
  it("reads a lone string message", () => {
    expect(questionOf({ message: "Hello" })).toBe("Hello");
  });

  it("returns null when message has siblings, so the extra keys stay visible", () => {
    expect(questionOf({ message: "Hello", locale: "en" })).toBeNull();
  });

  it("returns null for a non-string message", () => {
    expect(questionOf({ message: { text: "Hello" } })).toBeNull();
  });

  it("returns null for another key, an empty object, or nothing", () => {
    expect(questionOf({ prompt: "Hello" })).toBeNull();
    expect(questionOf({})).toBeNull();
    expect(questionOf(null)).toBeNull();
    expect(questionOf(undefined)).toBeNull();
  });

  it("keeps an empty string, which is a real question value", () => {
    expect(questionOf({ message: "" })).toBe("");
  });
});

describe("answerOf", () => {
  // Mirrors backend normalize_text: a lone "value" or "text" key holding a string.
  it("unwraps the two keys the scorer unwraps", () => {
    expect(answerOf({ value: "24/7" })).toBe("24/7");
    expect(answerOf({ text: "24/7" })).toBe("24/7");
  });

  it("returns null for a key the scorer does NOT unwrap", () => {
    expect(answerOf({ answer: "24/7" })).toBeNull();
    expect(answerOf({ output: "24/7" })).toBeNull();
    expect(answerOf({ message: "24/7" })).toBeNull();
  });

  it("returns null once a second key is present, since that disables unwrapping", () => {
    expect(answerOf({ value: "24/7", note: "checked" })).toBeNull();
    expect(answerOf({ value: "24/7", text: "24/7" })).toBeNull();
  });

  it("returns null for a non-string value", () => {
    expect(answerOf({ value: 42 })).toBeNull();
    expect(answerOf({ value: { nested: true } })).toBeNull();
  });

  it("returns null for empty or absent expected output", () => {
    expect(answerOf({})).toBeNull();
    expect(answerOf(null)).toBeNull();
    expect(answerOf(undefined)).toBeNull();
  });
});

describe("hasExpected", () => {
  it("treats an empty object the same as absent", () => {
    expect(hasExpected({})).toBe(false);
    expect(hasExpected(null)).toBe(false);
    expect(hasExpected(undefined)).toBe(false);
    expect(hasExpected({ value: "x" })).toBe(true);
  });
});

describe("isPlainRecord", () => {
  it("is plain with a lone message and an unwrappable answer", () => {
    expect(isPlainRecord({ message: "Hi" }, { value: "Yo" })).toBe(true);
  });

  it("is plain with a lone message and no expected output at all", () => {
    expect(isPlainRecord({ message: "Hi" }, undefined)).toBe(true);
    expect(isPlainRecord({ message: "Hi" }, {})).toBe(true);
  });

  it("is not plain when either half is structured", () => {
    expect(isPlainRecord({ message: "Hi", locale: "en" }, { value: "Yo" })).toBe(false);
    expect(isPlainRecord({ message: "Hi" }, { answer: "Yo" })).toBe(false);
  });
});

describe("text round trip", () => {
  it("writes exactly one key on each side", () => {
    expect(questionToInput("Hi")).toEqual({ message: "Hi" });
    expect(answerToExpected("Yo")).toEqual({ value: "Yo" });
  });

  it("drops a blank answer rather than storing an empty wrapper", () => {
    expect(answerToExpected("")).toBeUndefined();
    expect(answerToExpected("   ")).toBeUndefined();
  });

  it("survives a round trip for every shape the text editor accepts", () => {
    for (const [question, answer] of [
      ["Hi", "Yo"],
      ["", "Yo"],
      ["Multi\nline", "Also\nmulti"],
      ['Quotes " and {braces}', "Yo"],
    ]) {
      const input = questionToInput(question);
      const expected = answerToExpected(answer);
      expect(questionOf(input)).toBe(question);
      expect(answerOf(expected)).toBe(answer);
    }
  });
});

describe("parseRecordObject", () => {
  it("accepts a JSON object", () => {
    expect(parseRecordObject('{"message":"Hi"}')).toEqual({
      ok: true,
      value: { message: "Hi" },
    });
  });

  it("rejects the scalars and arrays the API would reject", () => {
    expect(parseRecordObject("42").ok).toBe(false);
    expect(parseRecordObject('"Hi"').ok).toBe(false);
    expect(parseRecordObject("true").ok).toBe(false);
    expect(parseRecordObject("null").ok).toBe(false);
    expect(parseRecordObject('[{"message":"Hi"}]').ok).toBe(false);
  });

  it("rejects malformed JSON instead of silently wrapping it", () => {
    const result = parseRecordObject('{"message": "Hi"');
    expect(result.ok).toBe(false);
    expect(result.error).toBeTruthy();
  });
});
