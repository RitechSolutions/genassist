import { describe, expect, it, vi } from "vitest";
import {
  VARIABLE_DRAG_TYPE,
  isVariableDrag,
  readVariableReference,
  setVariableDragData,
} from "@/helpers/variable-input/variableDragDrop";

/** A minimal DataTransfer stand-in: only the payload API is exercised. */
function makeDataTransfer(initial: Record<string, string> = {}): DataTransfer {
  const store: Record<string, string> = { ...initial };
  return {
    types: Object.keys(store),
    getData: (type: string) => store[type] ?? "",
    setData: vi.fn((type: string, value: string) => {
      store[type] = value;
    }),
  } as unknown as DataTransfer;
}

describe("setVariableDragData", () => {
  it("writes the raw path under the private type", () => {
    const dt = makeDataTransfer();
    setVariableDragData(dt, "source.prediction");
    expect(dt.setData).toHaveBeenCalledWith(
      VARIABLE_DRAG_TYPE,
      "source.prediction"
    );
  });

  it("marks the drag as a copy", () => {
    const dt = makeDataTransfer();
    setVariableDragData(dt, "a.b");
    expect(dt.effectAllowed).toBe("copy");
  });
});

describe("isVariableDrag", () => {
  it("is true for a drag carrying the private type", () => {
    expect(isVariableDrag(makeDataTransfer({ [VARIABLE_DRAG_TYPE]: "a" }))).toBe(
      true
    );
  });

  it("is false for text dragged in from elsewhere", () => {
    expect(isVariableDrag(makeDataTransfer({ "text/plain": "hello" }))).toBe(
      false
    );
  });

  it("is false for foreign JSON, which used to be accepted", () => {
    const dt = makeDataTransfer({ "application/json": '{"path":"x"}' });
    expect(isVariableDrag(dt)).toBe(false);
  });

  it("is false for a missing dataTransfer", () => {
    expect(isVariableDrag(null)).toBe(false);
  });
});

describe("readVariableReference", () => {
  it("wraps the dragged path for insertion", () => {
    const dt = makeDataTransfer({ [VARIABLE_DRAG_TYPE]: "source.prediction" });
    expect(readVariableReference(dt)).toBe("{{source.prediction}}");
  });

  it("leaves an already-wrapped path alone", () => {
    const dt = makeDataTransfer({ [VARIABLE_DRAG_TYPE]: "{{a.b}}" });
    expect(readVariableReference(dt)).toBe("{{a.b}}");
  });

  it("returns null when the payload is absent", () => {
    expect(readVariableReference(makeDataTransfer())).toBeNull();
  });
});
