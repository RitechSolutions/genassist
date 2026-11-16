import { describe, expect, it } from "vitest";
import {
  draftReducer,
  draftStateOf,
  type DraftAction,
  type DraftState,
} from "@/views/AIAgents/Workflows/utils/promptEditorDraft";

const run = (state: DraftState, ...actions: DraftAction[]): DraftState =>
  actions.reduce(draftReducer, state);

describe("draftReducer", () => {
  it("brings back the pre-apply text on undo and the typed text on redo", () => {
    const typed = run(
      draftStateOf("A"),
      { type: "apply", content: "S", label: "suggestion accepted" },
      { type: "edit", content: "S x" },
    );
    const undone = draftReducer(typed, { type: "undo" });
    expect(undone.content).toBe("A");
    expect(undone.undo).toEqual([]);
    expect(undone.redo).toEqual([
      { content: "S x", label: "suggestion accepted" },
    ]);

    const redone = draftReducer(undone, { type: "redo" });
    expect(redone.content).toBe("S x");
    expect(redone.undo).toEqual([{ content: "A", label: "suggestion accepted" }]);
    expect(redone.redo).toEqual([]);
  });

  it("adds no step when the applied text equals the draft", () => {
    const state = draftStateOf("A");
    const next = draftReducer(state, {
      type: "apply",
      content: "A",
      label: "v1 applied",
    });
    expect(next).toBe(state);
    expect(next.undo).toEqual([]);
  });

  it("drops the redo steps when a new text is applied", () => {
    const undone = run(
      draftStateOf("A"),
      { type: "apply", content: "B", label: "v1 applied" },
      { type: "undo" },
    );
    expect(undone.redo).toHaveLength(1);
    const next = draftReducer(undone, {
      type: "apply",
      content: "C",
      label: "v2 applied",
    });
    expect(next.content).toBe("C");
    expect(next.redo).toEqual([]);
  });

  it("does nothing on undo or redo with an empty stack", () => {
    const state = draftStateOf("A");
    expect(draftReducer(state, { type: "undo" })).toBe(state);
    expect(draftReducer(state, { type: "redo" })).toBe(state);
  });

  it("keeps the newest 20 steps", () => {
    const applies: DraftAction[] = Array.from({ length: 25 }, (_, i) => ({
      type: "apply",
      content: `draft ${i + 1}`,
      label: `v${i + 1} applied`,
    }));
    const state = run(draftStateOf("draft 0"), ...applies);
    expect(state.undo).toHaveLength(20);
    expect(state.undo[0].content).toBe("draft 5");
    expect(state.content).toBe("draft 25");
  });

  it("names the redo step after the step it undid", () => {
    const undone = run(
      draftStateOf("A"),
      { type: "apply", content: "B", label: "v3 applied" },
      { type: "undo" },
    );
    expect(undone.redo[undone.redo.length - 1].label).toBe("v3 applied");
  });

  it("files nothing on redo when the restored text equals the draft", () => {
    const state = run(
      draftStateOf("A"),
      { type: "apply", content: "B", label: "v1 applied" },
      { type: "edit", content: "A" },
    );
    const undone = draftReducer(state, { type: "undo" });
    expect(undone.content).toBe("A");
    expect(undone.redo).toEqual([]);
  });

  it("keeps both stacks while typing and ignores an unchanged edit", () => {
    const applied = run(draftStateOf("A"), {
      type: "apply",
      content: "B",
      label: "v1 applied",
    });
    expect(draftReducer(applied, { type: "edit", content: "B" })).toBe(applied);
    const typed = draftReducer(applied, { type: "edit", content: "B x" });
    expect(typed.undo).toEqual([{ content: "A", label: "v1 applied" }]);
  });
});
