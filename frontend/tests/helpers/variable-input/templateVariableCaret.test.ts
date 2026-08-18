import { describe, expect, it } from "vitest";
import {
  snapCaretOutOfVariable,
  snapToVariableBoundary,
  removeVariableAtCursor,
  deleteSelectionWithVariables,
  findVariableAtPosition,
} from "@/helpers/variable-input/templateVariableCaret";

// "ab{{x}}cd": the variable "{{x}}" occupies range { start: 2, end: 7 }.
//  index: a0 b1 {2 {3 x4 }5 }6 c7 d8   (length 9)
const VALUE = "ab{{x}}cd";

describe("snapCaretOutOfVariable", () => {
  it("snaps a caret strictly inside a variable to its end", () => {
    expect(snapCaretOutOfVariable(VALUE, 4)).toBe(7);
    expect(snapCaretOutOfVariable(VALUE, 3)).toBe(7);
    expect(snapCaretOutOfVariable(VALUE, 6)).toBe(7);
  });

  it("leaves a caret at the variable start untouched", () => {
    expect(snapCaretOutOfVariable(VALUE, 2)).toBe(2);
  });

  it("leaves a caret at the variable end untouched", () => {
    expect(snapCaretOutOfVariable(VALUE, 7)).toBe(7);
  });

  it("leaves a caret outside any variable untouched", () => {
    expect(snapCaretOutOfVariable(VALUE, 0)).toBe(0);
    expect(snapCaretOutOfVariable(VALUE, 8)).toBe(8);
  });

  it("returns the position unchanged when there are no variables", () => {
    expect(snapCaretOutOfVariable("plain", 2)).toBe(2);
  });
});

describe("snapToVariableBoundary", () => {
  it("snaps to the variable end when toEnd is true", () => {
    expect(snapToVariableBoundary(VALUE, 4, true)).toBe(7);
  });

  it("snaps to the variable start when toEnd is false", () => {
    expect(snapToVariableBoundary(VALUE, 4, false)).toBe(2);
  });

  it("leaves a boundary position unchanged (not strictly inside)", () => {
    expect(snapToVariableBoundary(VALUE, 2, false)).toBe(2);
    expect(snapToVariableBoundary(VALUE, 7, true)).toBe(7);
  });

  it("leaves a position outside any variable unchanged", () => {
    expect(snapToVariableBoundary(VALUE, 0, true)).toBe(0);
    expect(snapToVariableBoundary(VALUE, 8, false)).toBe(8);
  });
});

describe("removeVariableAtCursor - backspace", () => {
  it("removes the whole variable when the caret is just after it", () => {
    expect(removeVariableAtCursor(VALUE, 7, true)).toEqual({
      newValue: "abcd",
      newCursor: 2,
    });
  });

  it("removes the whole variable when the caret is inside it", () => {
    expect(removeVariableAtCursor(VALUE, 3, true)).toEqual({
      newValue: "abcd",
      newCursor: 2,
    });
  });

  it("returns null when the caret is at the very start", () => {
    expect(removeVariableAtCursor(VALUE, 0, true)).toBeNull();
  });

  it("returns null when the previous char is a normal char before a variable", () => {
    expect(removeVariableAtCursor(VALUE, 2, true)).toBeNull();
    expect(removeVariableAtCursor(VALUE, 1, true)).toBeNull();
  });

  it("returns null when the previous char is a normal char after a variable", () => {
    // cursor 8 -> prev 7 which is 'c', not part of the variable range [2,7).
    expect(removeVariableAtCursor(VALUE, 8, true)).toBeNull();
  });
});

describe("removeVariableAtCursor - delete", () => {
  it("removes the whole variable when the caret is at its start", () => {
    expect(removeVariableAtCursor(VALUE, 2, false)).toEqual({
      newValue: "abcd",
      newCursor: 2,
    });
  });

  it("removes the whole variable when the caret is inside it", () => {
    expect(removeVariableAtCursor(VALUE, 6, false)).toEqual({
      newValue: "abcd",
      newCursor: 2,
    });
  });

  it("returns null when the caret is at the end of the value", () => {
    expect(removeVariableAtCursor(VALUE, VALUE.length, false)).toBeNull();
  });

  it("returns null when the caret is at the variable end (past its range)", () => {
    expect(removeVariableAtCursor(VALUE, 7, false)).toBeNull();
  });

  it("returns null when the caret is before a variable on a normal char", () => {
    expect(removeVariableAtCursor(VALUE, 0, false)).toBeNull();
    expect(removeVariableAtCursor(VALUE, 1, false)).toBeNull();
  });
});

describe("deleteSelectionWithVariables", () => {
  it("expands a partial selection inside a variable to remove the whole variable", () => {
    expect(deleteSelectionWithVariables(VALUE, 3, 4)).toEqual({
      newValue: "abcd",
      newCursor: 2,
    });
  });

  it("removes a plain selection that does not touch a variable", () => {
    // select "ab"
    expect(deleteSelectionWithVariables(VALUE, 0, 2)).toEqual({
      newValue: "{{x}}cd",
      newCursor: 0,
    });
  });

  it("expands a selection that partially overlaps a variable and trailing text", () => {
    // select from index 1 through 8 -> merges with variable range to [1,8]
    expect(deleteSelectionWithVariables(VALUE, 1, 8)).toEqual({
      newValue: "ad",
      newCursor: 1,
    });
  });

  it("removes a selection spanning two variables entirely", () => {
    // "{{a}}xx{{b}}" -> ranges [0,5] and [7,12]
    const value = "{{a}}xx{{b}}";
    expect(deleteSelectionWithVariables(value, 1, 8)).toEqual({
      newValue: "",
      newCursor: 0,
    });
  });

  it("handles a plain string with no variables", () => {
    expect(deleteSelectionWithVariables("abcdef", 1, 3)).toEqual({
      newValue: "adef",
      newCursor: 1,
    });
  });
});

describe("findVariableAtPosition", () => {
  it("returns the range when the position is strictly inside a variable", () => {
    expect(findVariableAtPosition(VALUE, 4)).toEqual({ start: 2, end: 7 });
    expect(findVariableAtPosition(VALUE, 3)).toEqual({ start: 2, end: 7 });
    expect(findVariableAtPosition(VALUE, 6)).toEqual({ start: 2, end: 7 });
  });

  it("returns undefined at the variable boundaries", () => {
    expect(findVariableAtPosition(VALUE, 2)).toBeUndefined();
    expect(findVariableAtPosition(VALUE, 7)).toBeUndefined();
  });

  it("returns undefined outside any variable", () => {
    expect(findVariableAtPosition(VALUE, 0)).toBeUndefined();
    expect(findVariableAtPosition(VALUE, 8)).toBeUndefined();
  });

  it("returns undefined when there are no variables", () => {
    expect(findVariableAtPosition("plain", 2)).toBeUndefined();
  });
});
