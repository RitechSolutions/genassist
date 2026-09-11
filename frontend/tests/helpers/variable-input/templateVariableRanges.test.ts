import { describe, expect, it } from "vitest";
import {
  getVariableRanges,
  mergeRanges,
} from "@/helpers/variable-input/templateVariableRanges";
import { hasVariableSyntax } from "@/helpers/variable-input/templateVariableConstants";
import {
  findVariableAtPosition,
  snapCaretOutOfVariable,
} from "@/helpers/variable-input/templateVariableCaret";

describe("getVariableRanges", () => {
  it("finds the character ranges of {{variable}} spans", () => {
    expect(getVariableRanges("Hello {{name}}!")).toEqual([
      { start: 6, end: 14 },
    ]);
  });

  it("finds multiple variables", () => {
    expect(getVariableRanges("{{a}} and {{b}}")).toEqual([
      { start: 0, end: 5 },
      { start: 10, end: 15 },
    ]);
  });

  it("returns an empty array when there are no variables", () => {
    expect(getVariableRanges("no vars here")).toEqual([]);
  });
});

describe("mergeRanges", () => {
  it("returns an empty array for no ranges", () => {
    expect(mergeRanges([])).toEqual([]);
  });

  it("keeps disjoint ranges", () => {
    expect(
      mergeRanges([
        { start: 0, end: 2 },
        { start: 5, end: 7 },
      ])
    ).toEqual([
      { start: 0, end: 2 },
      { start: 5, end: 7 },
    ]);
  });

  it("merges overlapping ranges", () => {
    expect(
      mergeRanges([
        { start: 0, end: 5 },
        { start: 3, end: 8 },
      ])
    ).toEqual([{ start: 0, end: 8 }]);
  });

  it("merges adjacent ranges", () => {
    expect(
      mergeRanges([
        { start: 0, end: 5 },
        { start: 5, end: 9 },
      ])
    ).toEqual([{ start: 0, end: 9 }]);
  });

  it("sorts before merging", () => {
    expect(
      mergeRanges([
        { start: 5, end: 7 },
        { start: 0, end: 2 },
      ])
    ).toEqual([
      { start: 0, end: 2 },
      { start: 5, end: 7 },
    ]);
  });
});

describe("hasVariableSyntax", () => {
  it("is true when a {{variable}} is present", () => {
    expect(hasVariableSyntax("x {{y}}")).toBe(true);
    expect(hasVariableSyntax("{{ spaced }}")).toBe(true);
  });

  it("is false for plain strings and empty braces", () => {
    expect(hasVariableSyntax("plain")).toBe(false);
    expect(hasVariableSyntax("{{}}")).toBe(false);
  });

  it("is false for non-strings", () => {
    expect(hasVariableSyntax(123)).toBe(false);
    expect(hasVariableSyntax(null)).toBe(false);
    expect(hasVariableSyntax(undefined)).toBe(false);
  });
});

// Typing "{{" mid-field used to produce a range reaching all the way to the
// closing braces of the next variable, which highlighted the text between them
// as one variable and snapped the caret past it.
describe("half-typed {{ in a field that already has variables", () => {
  const VALUE =
    "Description: {{node.description}}\n" +
    "{{\n" +
    "Conversation history:\n" +
    "{{node.history}}";

  it("does not let the unclosed braces swallow the next variable", () => {
    const first = VALUE.indexOf("{{node.description}}");
    const second = VALUE.indexOf("{{node.history}}");

    expect(getVariableRanges(VALUE)).toEqual([
      { start: first, end: first + "{{node.description}}".length },
      { start: second, end: second + "{{node.history}}".length },
    ]);
  });

  it("leaves the caret just after the typed braces alone", () => {
    const caret = VALUE.indexOf("{{\n") + 2;
    expect(findVariableAtPosition(VALUE, caret)).toBeUndefined();
    expect(snapCaretOutOfVariable(VALUE, caret)).toBe(caret);
  });

  it("still reports the closed variables as variable syntax", () => {
    expect(hasVariableSyntax(VALUE)).toBe(true);
  });

  it("does not treat braces spanning a newline as a variable", () => {
    expect(getVariableRanges("{{\nnode.value}}")).toEqual([]);
  });

  it("does not treat nested opening braces as a variable", () => {
    expect(getVariableRanges("{{a{{b}}")).toEqual([{ start: 3, end: 8 }]);
  });
});
