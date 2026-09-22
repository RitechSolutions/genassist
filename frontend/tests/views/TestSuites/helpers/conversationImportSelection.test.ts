import { describe, it, expect } from "vitest";
import {
  MAX_IMPORT_CONVERSATIONS,
  areAllSelected,
  countHiddenSelections,
  describeImportPlan,
  planImport,
  setManySelected,
  summarizeImportOutcome,
  toggleSelected,
} from "@/views/TestSuites/helpers/conversationImportSelection";
import type {
  ImportFromConversationsResult,
  ImportedConversationResult,
  TestCase,
} from "@/interfaces/testSuite.interface";

const outcome = (
  overrides: Partial<ImportFromConversationsResult> = {},
): ImportFromConversationsResult => ({
  cases: [],
  results: [],
  imported: 0,
  replaced: 0,
  failed: 0,
  ...overrides,
});

const entry = (
  overrides: Partial<ImportedConversationResult> = {},
): ImportedConversationResult => ({
  conversation_id: "c1",
  status: "imported",
  turns: 2,
  ...overrides,
});

const turns = (count: number): TestCase[] =>
  Array.from({ length: count }, () => ({ suite_id: "s1", input_data: {} }));

describe("toggleSelected", () => {
  it("adds a conversation that was not selected", () => {
    expect([...toggleSelected(new Set(), "a")]).toEqual(["a"]);
  });

  it("removes a conversation that was selected", () => {
    expect([...toggleSelected(new Set(["a", "b"]), "a")]).toEqual(["b"]);
  });

  it("never mutates the set it was given", () => {
    const original = new Set(["a"]);
    toggleSelected(original, "b");
    expect([...original]).toEqual(["a"]);
  });

  it("refuses to grow past the cap the API enforces", () => {
    const full = new Set(["a", "b", "c"]);
    expect(toggleSelected(full, "d", 3)).toBe(full);
  });

  it("still deselects at the cap, so a full selection is not stuck", () => {
    const full = new Set(["a", "b", "c"]);
    expect([...toggleSelected(full, "a", 3)]).toEqual(["b", "c"]);
  });
});

describe("areAllSelected", () => {
  it("is true only when every loaded conversation is selected", () => {
    expect(areAllSelected(["a", "b"], new Set(["a", "b"]))).toBe(true);
    expect(areAllSelected(["a", "b"], new Set(["a"]))).toBe(false);
  });

  it("is false for an empty list, so Select all is not offered with nothing to select", () => {
    expect(areAllSelected([], new Set(["a"]))).toBe(false);
  });
});

describe("setManySelected", () => {
  it("selects everything loaded without touching picks made before a filter changed", () => {
    const next = setManySelected(new Set(["hidden"]), ["a", "b"], true);
    expect([...next].sort()).toEqual(["a", "b", "hidden"]);
  });

  it("clears only what is loaded", () => {
    const next = setManySelected(new Set(["a", "b", "hidden"]), ["a", "b"], false);
    expect([...next]).toEqual(["hidden"]);
  });

  it("fills up to the cap instead of refusing the whole group", () => {
    const next = setManySelected(new Set(["a"]), ["b", "c", "d"], true, 3);
    expect([...next]).toEqual(["a", "b", "c"]);
  });

  it("clears a group even when the selection sits at the cap", () => {
    const next = setManySelected(new Set(["a", "b", "c"]), ["a", "b"], false, 3);
    expect([...next]).toEqual(["c"]);
  });

  it("caps at the API limit by default", () => {
    const ids = Array.from({ length: 120 }, (_, i) => `c${i}`);
    const next = setManySelected(new Set(), ids, true);
    expect(next.size).toBe(MAX_IMPORT_CONVERSATIONS);
  });
});

describe("countHiddenSelections", () => {
  it("is zero when every pick is on screen", () => {
    expect(countHiddenSelections(new Set(["a", "b"]), ["a", "b", "c"])).toBe(0);
  });

  it("counts picks the current filter no longer shows", () => {
    expect(countHiddenSelections(new Set(["a", "b", "c"]), ["a"])).toBe(2);
  });

  it("counts every pick when the list is empty", () => {
    expect(countHiddenSelections(new Set(["a", "b"]), [])).toBe(2);
  });

  it("is zero with nothing selected", () => {
    expect(countHiddenSelections(new Set(), ["a", "b"])).toBe(0);
  });
});

describe("planImport", () => {
  it("counts a conversation already in the dataset as a refresh", () => {
    const plan = planImport(["a", "b"], new Map([["a", 4]]));
    expect(plan).toEqual({
      total: 2,
      added: 1,
      refreshed: 1,
      replacedTurns: 4,
    });
  });

  it("totals the turns every refresh throws away", () => {
    const plan = planImport(
      ["a", "b", "c"],
      new Map([
        ["a", 4],
        ["c", 3],
      ]),
    );
    expect(plan.refreshed).toBe(2);
    expect(plan.replacedTurns).toBe(7);
  });

  it("treats a first-time selection as all added", () => {
    const plan = planImport(["a", "b"], new Map());
    expect(plan).toEqual({ total: 2, added: 2, refreshed: 0, replacedTurns: 0 });
  });
});

describe("describeImportPlan", () => {
  it("promises the dataset is kept when nothing is replaced", () => {
    const text = describeImportPlan(planImport(["a", "b"], new Map()), "Refunds");
    expect(text).toContain("2 conversations");
    expect(text).toContain('"Refunds"');
    expect(text).toContain("keeping everything already in the dataset");
  });

  it("warns about the turns a refresh destroys", () => {
    const text = describeImportPlan(
      planImport(["a", "b"], new Map([["a", 4]])),
      "Refunds",
    );
    expect(text).toContain("1 conversation already in this dataset");
    expect(text).toContain("replacing 4 turns");
    expect(text).toContain("Any edits or turns you added to them are lost");
  });

  it("drops the add clause when every pick is a refresh", () => {
    const text = describeImportPlan(
      planImport(["a"], new Map([["a", 1]])),
      "Refunds",
    );
    expect(text).not.toContain("This adds");
    expect(text).toContain("replacing 1 turn");
  });

  it("uses singular wording for one conversation", () => {
    const text = describeImportPlan(planImport(["a"], new Map()), "Refunds");
    expect(text).toContain("1 conversation to");
  });
});

describe("summarizeImportOutcome", () => {
  it("reports a clean run with its turn count", () => {
    const summary = summarizeImportOutcome(
      outcome({ imported: 2, cases: turns(7), results: [entry(), entry()] }),
    );
    expect(summary.anySucceeded).toBe(true);
    expect(summary.successMessage).toBe("Imported 2 conversations (7 turns).");
    expect(summary.errorMessage).toBeNull();
  });

  it("separates refreshed conversations from new ones", () => {
    const summary = summarizeImportOutcome(
      outcome({ imported: 1, replaced: 2, cases: turns(9) }),
    );
    expect(summary.successMessage).toBe(
      "Imported 1 conversation and refreshed 2 (9 turns).",
    );
  });

  it("says refreshed when nothing was new", () => {
    const summary = summarizeImportOutcome(
      outcome({ replaced: 1, cases: turns(3) }),
    );
    expect(summary.successMessage).toBe("Refreshed 1 conversation (3 turns).");
  });

  it("names the reason when exactly one conversation fails", () => {
    const summary = summarizeImportOutcome(
      outcome({
        imported: 1,
        failed: 1,
        cases: turns(2),
        results: [
          entry(),
          entry({
            conversation_id: "c2",
            status: "failed",
            turns: 0,
            detail: "No question and answer turns to import.",
          }),
        ],
      }),
    );
    expect(summary.errorMessage).toBe(
      "1 conversation could not be imported. No question and answer turns to import.",
    );
    expect(summary.failures.map((f) => f.conversation_id)).toEqual(["c2"]);
  });

  it("falls back to a count when several fail, so the toast stays readable", () => {
    const summary = summarizeImportOutcome(
      outcome({
        failed: 2,
        results: [
          entry({ status: "failed", detail: "Conversation not found." }),
          entry({ conversation_id: "c2", status: "failed", detail: "Empty." }),
        ],
      }),
    );
    expect(summary.errorMessage).toBe("2 conversations could not be imported.");
    expect(summary.successMessage).toBeNull();
    expect(summary.anySucceeded).toBe(false);
  });

  it("reports both toasts for a partial run", () => {
    const summary = summarizeImportOutcome(
      outcome({
        imported: 1,
        failed: 2,
        cases: turns(4),
        results: [
          entry(),
          entry({ conversation_id: "c2", status: "failed" }),
          entry({ conversation_id: "c3", status: "failed" }),
        ],
      }),
    );
    expect(summary.successMessage).toBe("Imported 1 conversation (4 turns).");
    expect(summary.errorMessage).toBe("2 conversations could not be imported.");
  });
});
